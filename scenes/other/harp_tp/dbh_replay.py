"""DBH recorded-prompt replay.

Load a task's recorded CHOOSE_SHOOT decision-time prompt from the LOCAL OmniPlayer_choice_history.json.gz
artifact (under the config value rater.download_dir), transform it to the observer-preference form
(framing mapping + mechanical first->third memory conversion with the memory edits given by the caller,
NO LLM), and (at real-run time) re-query the model 118x with the transformed prompt. NO OMNI pipeline,
NO traversal, NO memory generation.

With --expb-arm the replay is first-person instead: the recorded text is kept (arm b2 adapts its image-count
wording) and the recorded grid image is replaced by native frames, see scenes/other/harp_tp/expb.py.

The dry-run path performs ONLY the deterministic transform + manifest build.
It makes ZERO model/LLM/ClearML calls: the query client is a caller-supplied seam
(``query_fn``) that is never invoked in dry-run. Real queries are made only under --execute.
"""
import argparse
import copy
import gzip
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Union

from core.log import get_logger, init_global_logger
from DBHLLM.llm_api import LLMAPI
from DBHLLM.prompts.omni_player import OmniChoosePrompt
from DBHLLM.prompts.utils import (
    INVALID_CHOICE_ERROR_TEMPLATE,
    extract_and_validate_choice_text,
)
from DBHLLM.utils import get_llm_kwargs, save_api_history

from scenes.other.harp_tp._transform_data import FRAMING_SWAPS
from scenes.other.harp_tp.expb import ExpbSpec, b2_text, load_expb_spec
from scenes.other.harp_tp.runner import cell_llm_kwargs_from_history, merge_prior_dbh_replay

ARTIFACT_NAME = "OmniPlayer_choice_history.json.gz"
EXPECTED_N = 118


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class RecordedPrompt:
    """The single recorded (text, image, choices) decision-time prompt of a task's CHOOSE_SHOOT
    node, after asserting all recorded samples are byte-identical."""

    node_key: str
    text: str
    image_url: dict  # {"url": ..., "detail": "high"}
    choices: dict  # e.g. {"B": "SHOOT", "A": "DON'T SHOOT"}
    n_samples: int
    text_sha: str
    image_sha: str


def artifact_path(task_id: str) -> str:
    return os.path.join(os.getenv("rater.download_dir", "logs/drate_data"), task_id, ARTIFACT_NAME)


def load_recorded_choose_shoot(artifact_file: str) -> RecordedPrompt:
    """Load a task's CHOOSE_SHOOT recorded prompt and assert all samples are byte-identical.

    Reads ``data["CHOOSE_SHOOT_<hash>"][0]["choices_pair"][i]["prompt"][0]["content"]`` — a
    2-part ``[{type:text}, {type:image_url}]`` list inside a single role:user message.
    Asserts that across ALL samples the text, the image_url object (url + detail)
    and the node choices map are constant, then returns the single recorded prompt.
    """
    with gzip.open(artifact_file, "rt", encoding="utf-8") as f:
        data = json.load(f)
    cs_keys = [k for k in data if k.startswith("CHOOSE_SHOOT")]
    assert len(cs_keys) == 1, f"expected exactly one CHOOSE_SHOOT node, got {cs_keys}"
    node_key = cs_keys[0]
    node = data[node_key]
    assert isinstance(node, list) and node, f"unexpected node type for {node_key}"
    choice_hist = node[0]
    choices = choice_hist["choices"]
    samples = choice_hist["choices_pair"]
    assert samples, f"no samples for {node_key}"

    text_shas, image_shas, details = set(), set(), set()
    text_val = image_val = None
    for s in samples:
        prompt = s["prompt"]
        assert isinstance(prompt, list) and len(prompt) == 1, "expected single message"
        msg = prompt[0]
        assert msg.get("role") == "user", f"unexpected role {msg.get('role')}"
        content = msg["content"]
        assert isinstance(content, list), "expected structured content list"
        text_parts = [p for p in content if p.get("type") == "text"]
        image_parts = [p for p in content if p.get("type") == "image_url"]
        assert len(text_parts) == 1 and len(image_parts) == 1, "expected [text, image_url]"
        text_val = text_parts[0]["text"]
        image_val = image_parts[0]["image_url"]
        text_shas.add(_sha(text_val))
        image_shas.add(_sha(image_val["url"]))
        details.add(image_val.get("detail"))  # image detail participates in identity too
    assert len(text_shas) == 1, f"{node_key}: {len(text_shas)} distinct recorded texts"
    assert len(image_shas) == 1, f"{node_key}: {len(image_shas)} distinct recorded images"
    assert len(details) == 1, f"{node_key}: {len(details)} distinct image detail values across samples"
    return RecordedPrompt(
        node_key=node_key,
        text=text_val,
        image_url=image_val,
        choices=choices,
        n_samples=len(samples),
        text_sha=list(text_shas)[0],
        image_sha=list(image_shas)[0],
    )


def transform_prompt(recorded_text: str, model: str, memory_edits: list) -> str:
    """Deterministic transform: framing mapping (A) + mechanical memory edits (B).

    ``memory_edits`` is a list of ``[old, new]`` pairs. Pure string operations, NO LLM. Every
    replacement asserts its source appears exactly once so a miscount fails loudly.
    """
    text = recorded_text
    for old, new in FRAMING_SWAPS:
        count = text.count(old)
        assert count == 1, f"{model}: framing source count={count} for {old[:48]!r}"
        text = text.replace(old, new)
    for old, new in memory_edits:
        count = text.count(old)
        assert count == 1, f"{model}: memory-edit source count={count} for {old[:48]!r}"
        text = text.replace(old, new)
    return text


def build_transformed_message(transformed_text: str, image_url: Union[dict, List[dict]]) -> list:
    """Assemble the replay message: transformed text + the image, or the images in list order."""
    images = image_url if isinstance(image_url, list) else [image_url]
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": transformed_text},
                *({"type": "image_url", "image_url": image} for image in images),
            ],
        }
    ]


def shoot_key(choices: dict) -> str:
    """The choice key whose recorded text is 'SHOOT' (e.g. 'B' in {'B':'SHOOT','A':\"DON'T SHOOT\"})."""
    keys = [k for k, v in choices.items() if v == "SHOOT"]
    assert len(keys) == 1, f"expected exactly one SHOOT key in {choices}"
    return keys[0]


@dataclass
class ReplayChoice:
    choice_key: str
    choice_text: str
    reasons: str
    repair_count: int


def replay_one_choice(query_fn: Callable, message: list, choices: dict) -> ReplayChoice:
    """Owned outer invalid-choice repair loop, mirroring collect_single_choice
    (DBHLLM/prompts/utils.py:337-374): validate the parsed ``chosen_option``; on ValueError,
    reset to base_len, append the assistant turn + an INVALID_CHOICE_ERROR_TEMPLATE user turn,
    and re-query until a valid choice. Logs the per-sample REPAIR-EVENT count. ``query_fn`` is the
    seam: in production it wraps LLMAPI.query (inner whole-call retry); in tests it is a mock.
    """
    prompt = copy.deepcopy(message)
    base_len = len(prompt)
    repair_count = 0
    while True:
        response = query_fn(prompt)
        try:
            choice_key = extract_and_validate_choice_text(response.chosen_option, choices)
            return ReplayChoice(
                choice_key=choice_key,
                choice_text=choices[choice_key],
                reasons=response.reasons,
                repair_count=repair_count,
            )
        except ValueError:
            del prompt[base_len:]
            choices_text = "\n".join(f"- {value}" for value in choices.values())
            prompt.append({"role": "assistant", "content": response.to_md()})
            prompt.append(
                {
                    "role": "user",
                    "content": INVALID_CHOICE_ERROR_TEMPLATE.format(choices_text=choices_text),
                }
            )
            repair_count += 1


def extract_provenance(history_entry: dict) -> dict:
    """Pull run-time provenance from an LLMAPI._history entry's raw completion.

    Populated only at real-run time; the fields are absent when a provider does not return them.
    """
    resp = history_entry.get("response", {}) or {}
    usage = resp.get("usage") or {}
    return {
        "model": resp.get("model"),
        "created": resp.get("created"),
        "system_fingerprint": resp.get("system_fingerprint"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
    }


@dataclass
class ModelReplayResult:
    model: str
    task_id: str
    node_key: str
    recorded_text_sha: str
    transformed_text_sha: str
    image_sha: str
    choices: dict
    shoot_key: str
    n: int
    shoot: Optional[int] = None
    dont_shoot: Optional[int] = None
    repair_counts: list = field(default_factory=list)
    provenance: list = field(default_factory=list)
    dry_run: bool = True


def replay_model(
    model: str,
    task_id: str,
    memory_edits: list,
    expb: Optional[ExpbSpec],
    query_fn: Optional[Callable] = None,
    artifact_file: Optional[str] = None,
    n: int = EXPECTED_N,
    dry_run: bool = True,
    assert_n: bool = True,
) -> ModelReplayResult:
    """Load + transform a task's recorded CHOOSE_SHOOT prompt; query 118x ONLY when not dry-run.

    The default ``dry_run=True`` returns the transform + shas with NO query. With ``expb`` the recorded
    first-person text is kept (b2: image-count wording adapted) and the expb image payload replaces the
    recorded image.
    """
    rec = load_recorded_choose_shoot(artifact_file or artifact_path(task_id))
    if assert_n:
        assert rec.n_samples == EXPECTED_N, f"{model}: {rec.n_samples} samples (expected {EXPECTED_N})"
    if expb:
        transformed = b2_text(rec.text, model) if expb.arm == "b2" else rec.text
    else:
        transformed = transform_prompt(rec.text, model, memory_edits)
    result = ModelReplayResult(
        model=model,
        task_id=task_id,
        node_key=rec.node_key,
        recorded_text_sha=rec.text_sha,
        transformed_text_sha=_sha(transformed),
        image_sha=rec.image_sha,
        choices=rec.choices,
        shoot_key=shoot_key(rec.choices),
        n=n,
        dry_run=dry_run,
    )
    if dry_run:
        return result
    if query_fn is None:
        raise ValueError("query_fn is required when dry_run=False (real model queries).")
    message = build_transformed_message(transformed, expb.image_payload if expb else rec.image_url)
    sk = result.shoot_key
    shoot = 0
    for _ in range(n):
        choice = replay_one_choice(query_fn, message, rec.choices)
        result.repair_counts.append(choice.repair_count)
        if choice.choice_key == sk:
            shoot += 1
    result.shoot = shoot
    result.dont_shoot = n - shoot
    result.dry_run = False
    return result


def resolve_llm_routing(model: str) -> tuple:
    """Resolve ``(model_str, base_url, api_key, kw)`` for a live query from the LOADED config
    (get_llm_kwargs on the config.yaml key ``model``); build_query_fn takes all of its routing from here.
    The returned ``api_key`` is for the client constructor only — it is NEVER logged or written to a manifest.
    """
    kw = get_llm_kwargs(model)
    model_str = kw.pop("model")
    base_url = kw.pop("base_url")
    api_key = kw.pop("api_key")
    return model_str, base_url, api_key, kw


def build_query_fn(model: str):
    """Build a live ``query_fn(prompt) -> OmniChoosePrompt.Response`` wrapping LLMAPI.query.

    Resolves the routing of the config.yaml key ``model`` via resolve_llm_routing; the LLMAPI retry count is
    the config value agent.retry (default -1, as in the HARP LLMAgent classes). Returns ``(api, query_fn)``:
    the LLMAPI (for _history / provenance) and the query closure.
    """
    model_str, base_url, api_key, kw = resolve_llm_routing(model)
    api = LLMAPI(retry=int(os.getenv("agent.retry", "-1")))

    def query_fn(prompt):
        return api.query(
            model=model_str,
            prompt=prompt,
            prompt_cls=OmniChoosePrompt,
            api_key=api_key,
            base_url=base_url,
            **kw,
        )

    return api, query_fn


def run_replay_execute(model: str, task_id: str, memory_edits: list, expb: Optional[ExpbSpec]) -> dict:
    """Live DBH replay of one model (a config.yaml key): the model is queried EXPECTED_N times with the
    transformed recorded prompt of ``task_id``. Captures run-time provenance from LLMAPI._history, persists
    the raw history to a file in the run log dir and records the request kwargs read back from that file.
    A replay error propagates: nothing is recorded for that replay.
    """
    init_global_logger("harp_tp_dbh_replay", "dbh_replay")
    log_path = get_logger().log_path
    api, query_fn = build_query_fn(model)
    result = replay_model(model, task_id, memory_edits, expb, query_fn=query_fn, dry_run=False, n=EXPECTED_N)
    history_path = os.path.join(log_path, f"dbh_replay_{model}_api_history.json.gz")
    save_api_history(api._history, history_path)
    entry = {
        "perspective": "first" if expb else "third",
        "condition": "DBH_replay",
        "model": model,
        "task_id": result.task_id,
        "node_key": result.node_key,
        "recorded_text_sha256": result.recorded_text_sha,
        "transformed_text_sha256": result.transformed_text_sha,
        "image_sha256": result.image_sha,
        "choices": result.choices,
        "shoot_key": result.shoot_key,
        "n": result.n,
        "shoot": result.shoot,
        "dont_shoot": result.dont_shoot,
        "repair_counts": result.repair_counts,
        "repair_events": sum(result.repair_counts),
        "llm_kwargs": cell_llm_kwargs_from_history(history_path),
        "provenance": [extract_provenance(h) for h in api._history],
    }
    print(f"[done] {model}/DBH_replay: SHOOT={result.shoot}/{result.n} repairs={sum(result.repair_counts)}",
          flush=True)
    manifest = {"experiment": "harp-tp-ablation", "phase": "execute", "dbh_replay": [entry]}
    if expb:
        entry.update(expb.entry_fields())
        manifest.update(expb.manifest_fields())
    return manifest


def dry_run_manifest(model: str, task_id: str, memory_edits: list, expb: Optional[ExpbSpec]) -> dict:
    """Transform one recorded prompt and return the TP manifest (dry-run: zero model calls)."""
    r = replay_model(model, task_id, memory_edits, expb, dry_run=True)
    entry = {
        "perspective": "first" if expb else "third",
        "condition": "DBH_replay",
        "model": model,
        "task_id": r.task_id,
        "node_key": r.node_key,
        "recorded_text_sha256": r.recorded_text_sha,
        "transformed_text_sha256": r.transformed_text_sha,
        "image_sha256": r.image_sha,
        "choices": r.choices,
        "shoot_key": r.shoot_key,
        "n": r.n,
        # populated at real-run time
        "shoot": None,
        "repair_counts": [],
        "provenance": [],
    }
    manifest = {"experiment": "harp-tp-ablation", "phase": "dry-run", "dbh_replay": [entry]}
    if expb:
        entry.update(expb.entry_fields())
        manifest.update(expb.manifest_fields())
    return manifest


def main():
    parser = argparse.ArgumentParser(description="DBH recorded-prompt replay")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Transform + manifest only; ZERO model calls.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Live replay: queries the model 118x.",
    )
    parser.add_argument("--model", required=True, help="config.yaml LLMs key of the model to replay.")
    parser.add_argument(
        "--task-id",
        required=True,
        help="Task id of the recorded CHOOSE_SHOOT prompt to replay (a directory under rater.download_dir).",
    )
    parser.add_argument(
        "--memory-edits",
        help="JSON file holding the list of [old, new] memory-edit pairs applied to the recorded prompt; "
        "no memory edits when omitted.",
    )
    parser.add_argument(
        "--expb-arm",
        choices=["b1", "b2"],
        help="Image-presentation arm, first-person replay: b1 = latest native frame, b2 = 16 native frames in "
        "chronological order (image-count wording adapted). The recorded text is kept; needs --frames-json and "
        "--grid and cannot be combined with --memory-edits.",
    )
    parser.add_argument("--frames-json", help="Frame reconstruction JSON written by scenes.other.harp_tp.expb_reconstruct.")
    parser.add_argument("--grid", help="Key in --frames-json of the recorded grid of this task (e.g. grid_gemma).")
    parser.add_argument("--out", default=None, help="Write the TP manifest JSON here.")
    args = parser.parse_args()
    expb = None
    if args.expb_arm:
        if args.memory_edits:
            parser.error("--memory-edits cannot be combined with --expb-arm (the memory text stays untouched).")
        if not args.frames_json:
            parser.error("--expb-arm requires --frames-json.")
        if not args.grid:
            parser.error("--expb-arm requires --grid.")
        expb = load_expb_spec(args.expb_arm, args.frames_json, args.grid)
    memory_edits = []
    if args.memory_edits:
        with open(args.memory_edits, "r", encoding="utf-8") as f:
            memory_edits = json.load(f)
    if args.execute:
        manifest = run_replay_execute(args.model, args.task_id, memory_edits, expb)
    elif args.dry_run:
        manifest = dry_run_manifest(args.model, args.task_id, memory_edits, expb)
    else:
        # Neither flag: refuse. Real queries happen only with --execute.
        raise SystemExit(
            "Refusing to run: pass --dry-run (transform only, zero calls) or --execute "
            "(live replay)."
        )
    # MERGE, don't overwrite: a re-run of one model must keep the already-banked DBH replay cells of the
    # models it is NOT running (their cells stay byte-identical), mirroring the HARP merge. Prepend
    # the prior manifest's banked cells; the current run rewrites its own model's cell.
    if args.execute and args.out and os.path.exists(args.out):
        with open(args.out, "r", encoding="utf-8") as f:
            prior = json.load(f)
        banked = merge_prior_dbh_replay(prior, [args.model])
        manifest["dbh_replay"] = banked + manifest["dbh_replay"]
        print(f"[merge] kept {len(banked)} banked DBH cell(s) for models outside this run; "
              f"total {len(manifest['dbh_replay'])} cells", flush=True)
    for e in manifest["dbh_replay"]:
        shoot = e.get("shoot")
        tail = f" shoot={shoot}/{e['n']} repairs={e.get('repair_events')}" if shoot is not None else ""
        print(f"{e['model']:12s} recorded={e['recorded_text_sha256'][:8]} "
              f"transformed={e['transformed_text_sha256']}{tail}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"\nManifest written to {args.out}")


if __name__ == "__main__":
    main()

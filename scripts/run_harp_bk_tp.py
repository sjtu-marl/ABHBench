#!/usr/bin/env python
"""Third-person HARP runner.

Runs exactly the 4 whitelisted HARP conditions (HARP_BK, +Dlg, +Img, +Img+Dlg) under
agent.perspective=third with choice_type=2 sampling (AUTO important count -> n=118), logging run-time
provenance via the existing LLMAPI history.

Default is --dry-run: validate the whitelist + choice_type=2 env and print the plan with ZERO model
calls. Live execution requires the explicit --execute flag and iterates the whitelisted scenes per model.

With --expb-arm the two image conditions of an image-presentation arm run first-person instead of the
whitelist (see scenes/other/harp_tp/expb.py).
"""
import argparse
import json
import os
import sys

from core.log import get_logger
from scenes.other.harp_bridge import Scen as HarpBridgeScen
from scenes.other.harp_bridge_ablation import Scen as HarpBridgeAblationScen
from scenes.other.harp_tp.expb import harp_expb_scenarios
from scenes.other.harp_tp.runner import (
    HARP_TP_CELL_N,
    HARP_TP_WHITELIST,
    cell_llm_kwargs_from_history,
    count_shoot_from_history,
    extract_provenance_from_history,
    iter_whitelist,
    merge_prior_harp,
    operator_note,
    run_env,
)


def _run_scene(name: str, scenario: dict):
    """Construct a fresh Scen and run it. Returns (rc, log_path).

    log_path is captured RIGHT AFTER construction (Scenario.__init__ calls init_global_logger, which
    creates a fresh timestamped dir) and BEFORE run(), because Scenario.run() -> close() ->
    close_logger() NULLS the global logger, after which get_logger() no longer carries .log_path.
    rc==0 means the scene completed; non-zero means Scenario.run() swallowed an error (e.g. a failed
    model call) — the histories are still flushed to log_path during close, so the partial cell is readable.
    """
    scen = (HarpBridgeScen if name == "HARP_BK" else HarpBridgeAblationScen)(scenario)
    log_path = get_logger().log_path
    rc = scen.run()
    return rc, log_path


def _harp_manifest(args, results, run_notes):
    manifest = {
        "experiment": "image-presentation-ablation" if args.expb_arm else "harp-tp-ablation",
        "phase": "execute-harp",
        "perspective": args.perspective,
        "run_notes": run_notes,
        "harp": results,
    }
    if args.expb_arm:
        manifest["arm"] = args.expb_arm
    return manifest


def _write_manifest(args, results, run_notes):
    if not args.out:
        return
    # MERGE, don't overwrite: a partial re-run (e.g. one model) must keep the already-banked cells of
    # the models it is NOT running. Prepend the prior manifest's banked cells for models outside
    # this run; the current run's models are (re)written fresh.
    merged_results = results
    if os.path.exists(args.out):
        with open(args.out, "r", encoding="utf-8") as f:
            prior = json.load(f)
        merged_results = merge_prior_harp(prior, args.models) + results
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(_harp_manifest(args, merged_results, run_notes), f, indent=2, ensure_ascii=False)
    print(f"\nHARP TP results written to {args.out} "
          f"({len(merged_results)} cells: {len(merged_results) - len(results)} banked + {len(results)} this run)",
          flush=True)


def _run_harp_cell(name, scenario):
    """Run a HARP cell once. A complete cell has HARP_TP_CELL_N samples; fewer samples means the cell
    stopped early (Scenario.run() swallowed the error). Returns an outcome dict."""
    rc, log_path = _run_scene(name, scenario)
    try:
        shoot, n = count_shoot_from_history(os.path.join(log_path, "LLMAgent_choice_history.json.gz"))
    except Exception:
        shoot, n = None, 0
    if n == HARP_TP_CELL_N:
        api_hist = os.path.join(log_path, "LLMAgent_api_history.json.gz")
        # Run-time provenance: record the cell's kwargs + per-call model/created/
        # system_fingerprint/tokens into the manifest — the SAME recording as the DBH replay.
        return {"ok": True, "shoot": shoot, "n": n, "log_path": log_path,
                "llm_kwargs": cell_llm_kwargs_from_history(api_hist),
                "provenance": extract_provenance_from_history(api_hist)}
    return {"ok": False, "log_path": log_path, "samples_reached": n, "rc": rc}


def main():
    parser = argparse.ArgumentParser(description="Third-person HARP runner")
    parser.add_argument("--dry-run", action="store_true", help="Validate + print plan; ZERO model calls.")
    parser.add_argument("--execute", action="store_true", help="Live run (issues model calls).")
    parser.add_argument("--models", nargs="+", required=True, help="config.yaml LLMs keys of the models to run.")
    parser.add_argument("--perspective", default="third", choices=["first", "third"])
    parser.add_argument("--out", default=None, help="Write the HARP TP results manifest JSON here.")
    parser.add_argument(
        "--run-note",
        default=None,
        help="Operator provenance note prepended to the manifest run_notes (e.g. a deliberate "
        "concurrency reduction). Recorded verbatim.",
    )
    parser.add_argument(
        "--expb-arm",
        choices=["b1", "b2"],
        help="Image-presentation arm of the image conditions (+Img, +Img+Dlg); forces --perspective first. "
        "b1 = latest frame (HARP_BK_IMG_SINGLE, HARP_BK_IMG_SINGLE_DLG), b2 = 16 native frames in "
        "chronological order (HARP_BK_IMG_SEQ, HARP_BK_IMG_SEQ_DLG). The HARP text is unchanged.",
    )
    parser.add_argument(
        "--frames-json",
        help="Frame reconstruction JSON written by scenes.other.harp_tp.expb_reconstruct; required with "
        "--expb-arm b2.",
    )
    args = parser.parse_args()
    if args.expb_arm == "b2" and not args.frames_json:
        parser.error("--expb-arm b2 requires --frames-json.")
    if args.expb_arm:
        args.perspective = "first"
        scenarios = harp_expb_scenarios(args.expb_arm, args.frames_json)
    else:
        scenarios = list(iter_whitelist(args.perspective))

    if not args.execute:
        if args.expb_arm:
            print(f"[dry-run] conditions ({len(scenarios)}): {[name for name, _ in scenarios]}")
        else:
            print(f"[dry-run] whitelist ({len(HARP_TP_WHITELIST)}): {HARP_TP_WHITELIST}")
        for model in args.models:
            print(f"[dry-run] model={model} env={run_env(model, args.perspective)}")
            for name, scenario in scenarios:
                if args.expb_arm:
                    n_images = len(scenario["image"]) if isinstance(scenario["image"], list) else 1
                    print(f"    condition={name} images={n_images} dialogue={'dialogue' in scenario}")
                else:
                    print(f"    condition={name} image={'image' in scenario} dialogue={'dialogue' in scenario}")
        print("[dry-run] no model/LLM/ClearML calls made.")
        return

    results = []
    run_notes = []  # operator provenance notes for the manifest
    if args.run_note:
        run_notes.append(operator_note(args.run_note))
    for model in args.models:
        os.environ.update(run_env(model, args.perspective))
        for name, scenario in scenarios:
            label = f"{model}/{name}"
            cell = _run_harp_cell(name, scenario)
            if not cell["ok"]:
                # Incomplete cell: keep the cells completed so far, do not record this one, stop the run.
                _write_manifest(args, results, run_notes)
                sys.exit(f"HARP cell {label} incomplete: reached {cell['samples_reached']}/{HARP_TP_CELL_N} "
                         f"samples (rc={cell['rc']}, log={cell['log_path']}); the cell is not recorded")
            results.append(
                {
                    "perspective": args.perspective,
                    "condition": name,
                    "tag": f"TP_{name}" if args.perspective == "third" else name,
                    "model": model,
                    "shoot": cell["shoot"],
                    "n": cell["n"],
                    "log_path": cell["log_path"],
                    "llm_kwargs": cell["llm_kwargs"],
                    "provenance": cell["provenance"],
                }
            )
            print(f"[done] {label}: SHOOT={cell['shoot']}/{cell['n']} log={cell['log_path']}", flush=True)
    _write_manifest(args, results, run_notes)


if __name__ == "__main__":
    main()

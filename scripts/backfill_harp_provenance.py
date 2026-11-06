"""One-time HARP manifest provenance backfill (ZERO model calls).

Every HARP call ALSO logs run-time provenance into the TP manifest — the SAME provenance recording
as the DBH replay. A HARP manifest written WITHOUT it can be backfilled: this script reads each
already-banked HARP cell's per-cell LLMAgent_api_history.json.gz (at its recorded log_path) and
ADDS `llm_kwargs` + `provenance` (DBH-manifest shape) to that cell.

ADDITIVE ONLY: every pre-existing top-level field and per-cell field is preserved byte-identical; only
the two new per-cell keys are appended. Running it again on an already-backfilled manifest is refused
(it asserts the fields are absent). No model/LLM/ClearML calls — pure reads of banked artifacts.
"""
import argparse
import json
import os

from scenes.other.harp_tp.runner import cell_llm_kwargs_from_history, extract_provenance_from_history


def backfill(manifest_path: str) -> dict:
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    for cell in manifest["harp"]:
        assert "llm_kwargs" not in cell and "provenance" not in cell, (
            f"{cell['model']}/{cell['condition']} already carries provenance — refusing to overwrite"
        )
        history = os.path.join(cell["log_path"], "LLMAgent_api_history.json.gz")
        assert os.path.exists(history), (
            f"missing banked history for {cell['model']}/{cell['condition']}: {history}"
        )
        # Append the two new keys ONLY; every existing key/value is left untouched in place.
        cell["llm_kwargs"] = cell_llm_kwargs_from_history(history)
        cell["provenance"] = extract_provenance_from_history(history)
    return manifest


def main():
    ap = argparse.ArgumentParser(description="Backfill HARP manifest provenance from banked histories")
    ap.add_argument("--manifest", required=True, help="Input HARP manifest (read-only).")
    ap.add_argument("--out", required=True, help="Output path for the backfilled manifest.")
    args = ap.parse_args()
    manifest = backfill(args.manifest)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    n = len(manifest["harp"])
    calls = sum(len(c["provenance"]) for c in manifest["harp"])
    print(f"backfilled {n} HARP cells ({calls} per-call provenance rows) -> {args.out}")


if __name__ == "__main__":
    main()

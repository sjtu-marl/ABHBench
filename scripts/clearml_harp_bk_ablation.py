#!/usr/bin/env python
"""
Extract choice count statistics from HARP_BK_ABLATION experiments in ClearML.
Only the most recent experiment is used for each model+scenario combination.

Usage:
    python scripts/clearml_harp_bk_ablation.py
    python scripts/clearml_harp_bk_ablation.py --output results/output.csv
"""

import argparse
import csv
import json
import re
from collections import defaultdict
from clearml import Task

# Mapping from old names to new names
SCENARIO_NAME_MAP = {
    "HARP_BK_ABLATION1": "HARP_BK_IMG_COMBINED",
    "HARP_BK_ABLATION2": "HARP_BK_IMG_SINGLE",
    "HARP_BK_ABLATION3": "HARP_BK_DLG_ONLY",
    "HARP_BK_ABLATION4": "HARP_BK_IMG_COMBINED_DLG",
    "HARP_BK_ABLATION5": "HARP_BK_IMG_SINGLE_DLG",
    "HARP_BK_DLG_ONLY_ANON": "HARP_BK_DLG_ONLY_ANON",
    "HARP_BK_IMG_COMBINED_DLG_ANON": "HARP_BK_IMG_COMBINED_DLG_ANON",
    "HARP_BK_IMG_SINGLE_DLG_ANON": "HARP_BK_IMG_SINGLE_DLG_ANON",
}


def get_harp_bk_ablation_data(project_name: str):
    task_ids = Task.query_tasks(
        project_name=project_name,
        task_filter={"status": ["completed"]}
    )
    print(f"Found {len(task_ids)} completed tasks")

    groups = defaultdict(list)
    for tid in task_ids:
        task = Task.get_task(task_id=tid)
        tags = task.get_tags() or []
        model = None
        scenario = None
        for tag in tags:
            if tag.startswith("a/"):
                model = tag[2:]
            if tag.startswith("HARP_BK_ABLATION"):
                scenario = tag
        if model and scenario:
            groups[(model, scenario)].append({
                "id": tid,
                "created": task.data.created,
                "task": task
            })

    results = []
    for (model, scenario), tasks in groups.items():
        latest = max(tasks, key=lambda x: x["created"])
        task = latest["task"]
        plots = task.get_reported_plots()
        shoot = 0
        dont_shoot = 0
        for plot in plots:
            if plot.get("metric") == "Choice Proportions":
                plot_data = json.loads(plot["plot_str"])
                for trace in plot_data["data"]:
                    name = trace["name"]
                    for ht in trace.get("hovertext", []):
                        match = re.search(r": (\d+) \(", ht)
                        if match:
                            count = int(match.group(1))
                            if "SHOOT THE" in name:
                                shoot = count
                            else:
                                dont_shoot = count
        total = shoot + dont_shoot
        results.append({
            "model": model,
            "scenario": SCENARIO_NAME_MAP.get(scenario, scenario),
            "SHOOT": shoot,
            "DONT_SHOOT": dont_shoot,
            "SHOOT%": round(shoot / total * 100, 1) if total > 0 else 0,
            "DONT_SHOOT%": round(dont_shoot / total * 100, 1) if total > 0 else 0
        })

    results.sort(key=lambda x: (x["model"], x["scenario"]))
    return results


def main():
    parser = argparse.ArgumentParser(description="Extract HARP_BK_ABLATION choice counts from ClearML")
    parser.add_argument("--project", default="HARP_BK_ABLATION", help="Project name")
    parser.add_argument("--output", default="results/harp_bk_ablation_choices.csv", help="Output CSV path")
    args = parser.parse_args()

    results = get_harp_bk_ablation_data(args.project)

    for r in results:
        print(f"{r['model']} + {r['scenario']}: SHOOT={r['SHOOT']} ({r['SHOOT%']}%), DONT_SHOOT={r['DONT_SHOOT']} ({r['DONT_SHOOT%']}%)")

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "scenario", "SHOOT", "DONT_SHOOT", "SHOOT%", "DONT_SHOOT%"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()

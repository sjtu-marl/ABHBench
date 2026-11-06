#!/usr/bin/env python
"""Perspective-aware successor to clearml_harp_bk_ablation.py.

Extends the ablation aggregator with a PERSPECTIVE axis so first-person and third-person
(TP_* tag) results are keyed separately and NEVER merged. This thin entrypoint performs the
live ClearML query and prints the grouped (model, scenario, perspective) cells. The per-cell
first-vs-third stats (per-cell test, Newcombe rate-difference CI, Haldane-Anscombe OR, Holm
correction) live in scenes.other.harp_tp.aggregator, which calls scripts/compare_dbh_harp.py.

Usage:
    python scripts/clearml_harp_bk_ablation_tp.py --project HARP_BK_ABLATION_TP
"""
import argparse

from clearml import Task

from scenes.other.harp_tp.aggregator import group_tasks


def fetch_tasks(project_name: str) -> list:
    """Query ClearML for completed tasks and normalise to {tags, created, id} dicts."""
    task_ids = Task.query_tasks(project_name=project_name, task_filter={"status": ["completed"]})
    tasks = []
    for tid in task_ids:
        t = Task.get_task(task_id=tid)
        tasks.append({"id": tid, "tags": t.get_tags() or [], "created": t.data.created, "task": t})
    return tasks


def main():
    parser = argparse.ArgumentParser(description="Perspective-aware HARP_BK ablation aggregator")
    parser.add_argument("--project", default="HARP_BK_ABLATION_TP", help="ClearML project name")
    args = parser.parse_args()
    tasks = fetch_tasks(args.project)
    groups = group_tasks(tasks)
    print(f"Grouped {len(tasks)} tasks into {len(groups)} (model, scenario, perspective) cells")
    for (model, scenario, persp), task in sorted(groups.items()):
        print(f"  {persp:5s} {model:12s} {scenario:28s} <- task {task['id']}")
    # scenes.other.harp_tp.aggregator.build_cross_table consumes per-cell counts taken from each
    # task's Choice Proportions plot; that extraction is not implemented here
    # (clearml_harp_bk_ablation.py shows how the plot is parsed).


if __name__ == "__main__":
    main()

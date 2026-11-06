#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to list all tasks from a ClearML project.
Usage:
    # List all tasks with tags
    python scripts/clearml_list_tasks.py

    # Filter by tag
    python scripts/clearml_list_tasks.py --tag "your_tag"

    # Filter by task name (substring match)
    python scripts/clearml_list_tasks.py --name "task_name"

    # Filter by both tag and name, output only IDs
    python scripts/clearml_list_tasks.py --tag "your_tag" --name "task_name" --ids-only

    # Filter by status (e.g., completed, stopped, failed, running)
    python scripts/clearml_list_tasks.py --tag "your_tag" --name "task_name" --status completed
"""

import argparse
import sys
from clearml import Task


def list_tasks(project_name: str, filter_tag: str = None, filter_name: str = None, filter_status: str = None, ids_only: bool = False):
    """
    List all tasks from a project.

    Args:
        project_name: Name of the project to fetch tasks from.
        filter_tag: Filter tasks by this tag.
        filter_name: Filter tasks by name (substring match).
        filter_status: Filter tasks by status (e.g., completed, stopped, failed, running).
        ids_only: If True, only output task IDs, one per line.
    """
    print(f"Fetching tasks from project: {project_name}", file=sys.stderr)

    # Build task filter for query_tasks
    task_filter = {}
    if filter_tag:
        task_filter['tags'] = [filter_tag]
    if filter_name:
        task_filter['name'] = filter_name  # substring match
    if filter_status:
        task_filter['status'] = [filter_status]

    # Use query_tasks to get all task IDs (no 500 limit)
    task_ids = Task.query_tasks(
        project_name=project_name,
        task_filter=task_filter
    )

    if not task_ids:
        print("No tasks found matching criteria", file=sys.stderr)
        return

    print(f"Found {len(task_ids)} tasks", file=sys.stderr)

    if ids_only:
        # Output only IDs, one per line (for easy copying)
        for task_id in task_ids:
            print(task_id)
    else:
        # Full output - need to fetch task details
        print("-" * 100)
        for i, task_id in enumerate(task_ids, 1):
            task = Task.get_task(task_id=task_id)
            tags = task.get_tags() or []
            print(f"{i}. Task: {task.name}")
            print(f"   ID: {task.id}")
            print(f"   Status: {task.status}")
            print(f"   Tags: {tags}")
            print(f"   Created: {task.data.created}")
            print("-" * 100)


def main():
    parser = argparse.ArgumentParser(description="List ClearML tasks from a project")
    parser.add_argument("--project", default="DBH DEval", help="Project name (default: DBH DEval)")
    parser.add_argument("--tag", help="Filter by tag")
    parser.add_argument("--name", help="Filter by task name (substring match)")
    parser.add_argument("--status", help="Filter by status (e.g., completed, stopped, failed, running)")
    parser.add_argument("--ids-only", action="store_true", help="Output only task IDs, one per line")

    args = parser.parse_args()
    list_tasks(args.project, args.tag, args.name, args.status, args.ids_only)


if __name__ == "__main__":
    main()

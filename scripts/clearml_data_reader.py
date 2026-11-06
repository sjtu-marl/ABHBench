#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to read data from ClearML, specifically from the project "10 v 100".
This script extracts log information and properties, focusing on the "agent.collect_n_choices" property.
"""

import pandas as pd
from clearml import Task


def extract_task_data(tasks):
    """
    Extract log information and properties from tasks.

    Args:
        tasks (list): List of tasks to extract data from.

    Returns:
        list: List of dictionaries containing task data.
    """
    data = []

    for task in tasks:
        print(f"Processing task: {task.name} (ID: {task.id})")

        # Get user properties - only using this method as per requirements
        user_props = task.get_user_properties()

        # Get n_choices from user properties
        print(user_props.get("agent.collect_n_choices"))
        n_choices_value = int(user_props.get("agent.collect_n_choices")["value"])

        # Extract model from user properties
        model_name = user_props.get("models.harp")["value"]

        # Get logs from console output and process choice proportions (like in clearml_log_parser.py)
        logs = None
        choice_proportions = {}
        permutation_stats = {}

        try:
            # Get console output to extract choice proportions
            print(f"  Getting console output for task {task.id}")
            console_outputs = task.get_reported_console_output(number_of_reports=10)

            if (
                console_outputs
                and isinstance(console_outputs, list)
                and len(console_outputs) > 0
            ):
                log_text = "\n".join(console_outputs)

                # Store the log text as logs
                logs = log_text

                # Extract choice proportions using regex and eval (similar to clearml_log_parser.py)
                import re

                choice_matches = re.findall(r"Choice proportions: (\{.+?\})", log_text)
                if choice_matches:
                    # Use eval to safely parse the Python dictionary
                    choice_proportions = eval(choice_matches[-1])
                    # Convert percentage strings to floats
                    for key, value in choice_proportions.items():
                        if isinstance(value, str) and value.endswith("%"):
                            choice_proportions[key] = float(value.rstrip("%")) / 100

                    # Determine scenario type based on the choices present
                    scenario_type = "unknown"
                    if (
                        "DIVERT" in choice_proportions
                        or "CONTINUE" in choice_proportions
                    ):
                        scenario_type = "HARP"
                    elif (
                        "PULL" in choice_proportions or "NOT PULL" in choice_proportions
                    ):
                        scenario_type = "KAMSKI_TEST"
                    # Fallback to task name
                    elif "HARP_V1" in task.name or "HARP_V2" in task.name:
                        scenario_type = "HARP"
                    elif "KAMSKI_TEST" in task.name:
                        scenario_type = "KAMSKI_TEST"

                    # Add missing choices with 0.0 proportion based on scenario type
                    if scenario_type == "HARP":
                        # These scenarios have choices A:DIVERT, B:CONTINUE
                        if (
                            "DIVERT" in choice_proportions
                            and "CONTINUE" not in choice_proportions
                        ):
                            choice_proportions["CONTINUE"] = 0.0
                        elif (
                            "CONTINUE" in choice_proportions
                            and "DIVERT" not in choice_proportions
                        ):
                            choice_proportions["DIVERT"] = 0.0
                    elif scenario_type == "KAMSKI_TEST":
                        # This scenario has choices A:PULL, B:NOT PULL
                        if (
                            "PULL" in choice_proportions
                            and "NOT PULL" not in choice_proportions
                        ):
                            choice_proportions["NOT PULL"] = 0.0
                        elif (
                            "NOT PULL" in choice_proportions
                            and "PULL" not in choice_proportions
                        ):
                            choice_proportions["PULL"] = 0.0

                    print(f"  Found choice proportions: {choice_proportions}")

                # Extract permutation statistics using regex and eval
                perm_matches = re.findall(r"Permutation (\d+): (\{.+?\})", log_text)
                for match in perm_matches:
                    permutation_num = match[0]
                    stats = eval(match[1])
                    # Convert percentage strings to floats
                    for key, value in stats.items():
                        if isinstance(value, str) and value.endswith("%"):
                            stats[key] = float(value.rstrip("%")) / 100

                    # Determine scenario type for permutation stats based on the choices present
                    perm_scenario_type = "unknown"
                    if "DIVERT" in stats or "CONTINUE" in stats:
                        perm_scenario_type = "HARP"
                    elif "PULL" in stats or "NOT PULL" in stats:
                        perm_scenario_type = "KAMSKI_TEST"
                    # If no choice found in stats, use the previously determined scenario type
                    elif scenario_type != "unknown":
                        perm_scenario_type = scenario_type

                    # Add missing choices with 0.0 proportion based on scenario type
                    if perm_scenario_type == "HARP":
                        # These scenarios have choices A:DIVERT, B:CONTINUE
                        if "DIVERT" in stats and "CONTINUE" not in stats:
                            stats["CONTINUE"] = 0.0
                        elif "CONTINUE" in stats and "DIVERT" not in stats:
                            stats["DIVERT"] = 0.0
                    elif perm_scenario_type == "KAMSKI_TEST":
                        # This scenario has choices A:PULL, B:NOT PULL
                        if "PULL" in stats and "NOT PULL" not in stats:
                            stats["NOT PULL"] = 0.0
                        elif "NOT PULL" in stats and "PULL" not in stats:
                            stats["PULL"] = 0.0

                    permutation_stats[permutation_num] = stats

                if permutation_stats:
                    print(f"  Found {len(permutation_stats)} permutation statistics")
                    print(f"  Permutation stats: {permutation_stats}")
        except Exception as e:
            print(f"Error getting logs for task {task.id}: {e}")

        # Store task data
        task_data = {
            "task_id": task.id,
            "task_name": task.name,
            "model": model_name,
            "n_choices": n_choices_value,
            "logs": logs,
            "status": task.status,
            "created": task.data.created,
            "choice_proportions": choice_proportions,
            "permutation_stats": permutation_stats,
        }

        print(f"Processed task with model: {model_name}, n_choices: {n_choices_value}")
        data.append(task_data)

    return data


def main():
    """Main function to run the script."""
    print("Starting ClearML data extraction...")

    # Get all tasks in the project directly
    project_name = "10 v 100"
    print(f"Fetching tasks from project: {project_name}")
    tasks = Task.get_tasks(project_name=project_name)

    if not tasks:
        print(f"No tasks found in project: {project_name}")
        return

    print(f"Found {len(tasks)} tasks in project: {project_name}")

    # Extract data from tasks
    data = extract_task_data(tasks)

    print(f"Extracted data from {len(data)} tasks")

    # Save raw data
    print("Saving raw data to 'clearml_raw_data.pkl'")
    pd.to_pickle(data, "clearml_raw_data.pkl")

    # Print summary
    print("\nData Summary:")
    for task_data in data:
        print(f"Task: {task_data['task_name']} - n_choices: {task_data['n_choices']}")
        if task_data["logs"]:
            # Check if logs is a dictionary before trying to access keys
            if isinstance(task_data["logs"], dict) and hasattr(
                task_data["logs"], "keys"
            ):
                print(f"  Log metrics: {list(task_data['logs'].keys())}")
            else:
                # For string logs, just print the length
                log_length = (
                    len(task_data["logs"]) if isinstance(task_data["logs"], str) else 0
                )
                print(f"  Log text length: {log_length} characters")
                print(f"  Choice proportions: {task_data['choice_proportions']}")
                print(f"  Permutation stats: {task_data['permutation_stats']}")

    print("\nRaw data saved. Use this data for further analysis and plotting.")


if __name__ == "__main__":
    main()

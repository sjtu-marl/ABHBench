#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to visualize data from clearml_raw_data.pkl.
Creates stacked bar charts for each scenario type showing proportions of choices.
"""

import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def identify_scenario_type(task_data):
    """
    Identify the scenario type based on the task name.

    Args:
        task_data (dict): Task data dictionary.

    Returns:
        str: Scenario type ('HARP_V1', 'HARP_V2', 'KAMSKI_TEST', or 'unknown').
    """
    # Prioritize extracting the scenario type from the task name
    task_name = task_data["task_name"]

    if "HARP_V1" in task_name:
        return "HARP_V1"
    elif "HARP_V2" in task_name:
        return "HARP_V2"
    elif "KAMSKI_TEST" in task_name:
        return "KAMSKI_TEST"

    # Fallback to checking choice keys if task name isn't specific enough
    if not task_data["choice_proportions"]:
        return "unknown"

    choices = list(task_data["choice_proportions"].keys())
    if "DIVERT" in choices or "CONTINUE" in choices:
        # Generic HARP case when version isn't specified
        return "HARP_UNKNOWN"
    elif "PULL" in choices or "NOT PULL" in choices:
        return "KAMSKI_TEST"

    return "unknown"


def main():
    print("Loading data from 'clearml_raw_data.pkl'...")
    data = pd.read_pickle("clearml_raw_data.pkl")

    print(f"Loaded {len(data)} task records")

    # Group data by model, scenario type, and n_choices
    model_scenario_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for task in data:
        # Extract scenario type and model
        scenario_type = identify_scenario_type(task)
        if scenario_type == "unknown":
            continue

        model = task["model"]
        n_choices = task["n_choices"]
        choice_proportions = task["choice_proportions"]

        if not choice_proportions:
            continue

        # Add this task's data to the appropriate group
        model_scenario_data[model][scenario_type][n_choices].append(choice_proportions)

    # Get all unique models
    models = list(model_scenario_data.keys())
    print(f"Found {len(models)} models: {', '.join(models)}")

    # Now we have grouped data, let's create visualizations
    # Create output directory if it doesn't exist
    os.makedirs("plots", exist_ok=True)

    # For each model, create plots for each scenario type
    for model in models:
        model_safe = model.replace(":", "_").replace("/", "_")  # Create a safe filename
        print(f"\nCreating visualizations for model: {model}")

        # Create a directory for this model
        model_dir = f"plots/{model_safe}"
        os.makedirs(model_dir, exist_ok=True)

        # Plot for each scenario type within this model
        for scenario_type, n_choices_data in model_scenario_data[model].items():
            print(f"  Creating visualization for scenario type: {scenario_type}")

            # Get unique n_choices values and sort them
            n_choices_values = sorted(n_choices_data.keys())
            if not n_choices_values:
                print(f"  No data for {scenario_type}, skipping")
                continue

            # Prepare data for plotting
            plot_data = {}
            for n_choice in n_choices_values:
                # Average proportions across all tasks with the same n_choices
                avg_proportions = {}
                for choice_prop in n_choices_data[n_choice]:
                    for choice, prop in choice_prop.items():
                        if choice not in avg_proportions:
                            avg_proportions[choice] = []
                        avg_proportions[choice].append(prop)

                # Calculate the average for each choice
                for choice, props in avg_proportions.items():
                    if choice not in plot_data:
                        plot_data[choice] = []
                    plot_data[choice].append(np.mean(props))

            # Create stacked bar chart
            fig, ax = plt.subplots(figsize=(12, 8))

            # Set up x-axis
            x = np.arange(len(n_choices_values))
            width = 0.6

            # Sort choices alphabetically for consistent coloring
            choices = sorted(plot_data.keys())

            # Colors for the different choices
            colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

            # Create the stacked bars
            bottom = np.zeros(len(n_choices_values))
            for i, choice in enumerate(choices):
                if choice in plot_data:
                    ax.bar(
                        x,
                        plot_data[choice],
                        width,
                        label=choice,
                        bottom=bottom,
                        color=colors[i % len(colors)],
                    )
                    bottom += np.array(plot_data[choice])

            # Add labels and title
            ax.set_xlabel("Number of Choices (n_choices)", fontsize=14)
            ax.set_ylabel("Proportion", fontsize=14)
            ax.set_title(
                f"Choice Proportions for {scenario_type} Scenario - Model: {model}",
                fontsize=16,
            )

            # Set x-tick labels as n_choices values
            ax.set_xticks(x)
            ax.set_xticklabels(n_choices_values)

            # Set y-axis limits
            ax.set_ylim(0, 1.0)

            # Add grid for better readability
            ax.grid(True, linestyle="--", alpha=0.7)

            # Add legend
            ax.legend(title="Choices", fontsize=12)

            # Add values on bars for better readability
            for i, choice in enumerate(choices):
                if choice in plot_data:
                    data_values = plot_data[choice]
                    prev_heights = bottom - np.array(data_values)

                    for j, val in enumerate(data_values):
                        # Only annotate if value is significant enough to show
                        if val >= 0.05:  # 5% threshold for showing text
                            height = prev_heights[j] + val / 2
                            ax.text(
                                x[j],
                                height,
                                f"{val:.2f}",
                                ha="center",
                                va="center",
                                fontsize=10,
                                color="white",
                                fontweight="bold",
                            )

            # Add count of tasks per n_choices as a subtitle
            task_counts = [len(n_choices_data[n]) for n in n_choices_values]
            counts_text = "Number of tasks per n_choices: " + ", ".join(
                [f"{n}: {c}" for n, c in zip(n_choices_values, task_counts)]
            )
            plt.figtext(0.5, 0.01, counts_text, ha="center", fontsize=10)

            # Adjust layout
            plt.tight_layout(rect=[0, 0.03, 1, 0.97])

            # Save the figure
            output_filename = f"{model_dir}/{scenario_type}_proportions.png"
            plt.savefig(output_filename, dpi=300, bbox_inches="tight")
            print(f"  Saved visualization to {output_filename}")

            # Clear the figure for next plot
            plt.close()

    # Create a combined visualization with subplots for all models and scenarios
    print("\nCreating combined visualization for all models and scenarios...")
    create_combined_visualization(model_scenario_data)


def create_combined_visualization(model_scenario_data):
    """
    Create a combined visualization with subplots for all models and scenarios.

    Args:
        model_scenario_data: Nested dictionary with data grouped by model, scenario, and n_choices.
    """
    # Get all unique models and scenarios
    all_models = list(model_scenario_data.keys())
    all_scenarios = set()
    for model in all_models:
        for scenario in model_scenario_data[model].keys():
            all_scenarios.add(scenario)
    all_scenarios = sorted(list(all_scenarios))

    # Set up the figure
    n_rows = len(all_models)
    n_cols = len(all_scenarios)

    if n_rows == 0 or n_cols == 0:
        print("No data for combined visualization")
        return

    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(n_cols * 6, n_rows * 5), squeeze=False
    )
    fig.suptitle("Choice Proportions by Model and Scenario Type", fontsize=20)

    # Define a consistent color mapping for choice types
    all_choices = set()
    for model in all_models:
        for scenario in model_scenario_data[model].keys():
            for n_choices_data in model_scenario_data[model][scenario].values():
                for choice_prop in n_choices_data:
                    all_choices.update(choice_prop.keys())

    # Sort choices for consistent coloring
    all_choices = sorted(list(all_choices))
    colors = plt.cm.tab10(np.linspace(0, 1, len(all_choices)))
    choice_colors = {choice: colors[i] for i, choice in enumerate(all_choices)}

    # Create subplots
    for i, model in enumerate(all_models):
        for j, scenario in enumerate(all_scenarios):
            ax = axes[i, j]

            # Set titles
            if i == 0:  # Top row gets scenario titles
                ax.set_title(f"{scenario}", fontsize=14)
            if j == 0:  # Left column gets model names
                ax.set_ylabel(f"{model}", fontsize=14)

            # Skip if no data for this combination
            if (
                scenario not in model_scenario_data[model]
                or not model_scenario_data[model][scenario]
            ):
                ax.text(0.5, 0.5, "No Data", ha="center", va="center", fontsize=14)
                ax.set_xticks([])
                ax.set_yticks([])
                continue

            n_choices_data = model_scenario_data[model][scenario]
            n_choices_values = sorted(n_choices_data.keys())

            # Prepare data for plotting
            plot_data = {}
            for n_choice in n_choices_values:
                # Average proportions across all tasks with the same n_choices
                avg_proportions = {}
                for choice_prop in n_choices_data[n_choice]:
                    for choice, prop in choice_prop.items():
                        if choice not in avg_proportions:
                            avg_proportions[choice] = []
                        avg_proportions[choice].append(prop)

                # Calculate the average for each choice
                for choice, props in avg_proportions.items():
                    if choice not in plot_data:
                        plot_data[choice] = []
                    plot_data[choice].append(np.mean(props))

            # Set up x-axis
            x = np.arange(len(n_choices_values))
            width = 0.6

            # Sort choices alphabetically for consistent coloring
            choices = sorted(plot_data.keys())

            # Create the stacked bars
            bottom = np.zeros(len(n_choices_values))
            for choice in choices:
                if choice in plot_data:
                    ax.bar(
                        x,
                        plot_data[choice],
                        width,
                        label=choice,
                        bottom=bottom,
                        color=choice_colors.get(choice, "gray"),
                    )
                    bottom += np.array(plot_data[choice])

            # Set x-tick labels as n_choices values
            ax.set_xticks(x)
            ax.set_xticklabels(n_choices_values)

            # Set axis labels
            ax.set_xlabel("n_choices", fontsize=12)
            if j == 0:  # Only left column needs y-label
                ax.set_ylabel("Proportion", fontsize=12)

            # Set y-axis limits
            ax.set_ylim(0, 1.0)

            # Add grid for better readability
            ax.grid(True, linestyle="--", alpha=0.4)

    # Create a single legend for the entire figure
    handles, labels = [], []
    for ax in axes.flatten():
        h, labels_list = ax.get_legend_handles_labels()
        for handle, label in zip(h, labels_list):
            if label not in labels:
                handles.append(handle)
                labels.append(label)

    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=min(len(labels), 4),
        bbox_to_anchor=(0.5, 0),
        fontsize=12,
    )

    # Adjust layout
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])

    # Save the figure
    output_filename = "plots/combined_visualization.png"
    plt.savefig(output_filename, dpi=300, bbox_inches="tight")
    print(f"Saved combined visualization to {output_filename}")
    plt.close()


if __name__ == "__main__":
    main()
    print("Visualization complete!")

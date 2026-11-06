"""
Plotting utilities for DBHLLM.
"""

from collections import Counter

import numpy as np
import plotly.graph_objects as go
from scipy.stats import entropy, wasserstein_distance


def plot_choice_proportions(choices_history_key_data):
    """
    Create a stacked bar chart showing choice proportions across iterations.

    Args:
        choices_history_key_data (list): List of choice history data for a specific key.

    Returns:
        plotly.graph_objects.Figure: The plotly figure.
    """
    if not choices_history_key_data:
        return None

    # Extract all unique choice keys and create mapping to choice text
    all_choice_keys = set()
    key_to_text_map = {}

    # First, collect all possible choices from all iterations
    for data in choices_history_key_data:
        choices = data.get("choices", {})  # Get the choices dict with all options

        # Add ALL available choices, not just the ones in responses
        for choice_key, choice_text in choices.items():
            all_choice_keys.add(choice_key)
            key_to_text_map[choice_key] = choice_text

        # Also collect from responses to ensure we have text for each key
        for resp in data["choices_pair"]:
            choice_key = resp["choice_key"]
            # Map key to text if available
            if "choice_text" in resp:
                key_to_text_map[choice_key] = resp["choice_text"]

        # Prepare data for plot
    iterations = []
    choice_proportions = {key: [] for key in all_choice_keys}
    choice_counts = {key: [] for key in all_choice_keys}  # Store counts for hover text

    for data in choices_history_key_data:
        iteration = data["think_iteration"]
        iterations.append(f"Iteration {iteration}")

        # Count choices in this iteration
        counter = Counter()
        for resp in data["choices_pair"]:
            counter[resp["choice_key"]] += 1

        # Calculate proportions
        total = sum(counter.values())
        if total == 0:
            continue

        for key in all_choice_keys:
            count = counter.get(key, 0)
            proportion = count / total if total > 0 else 0
            choice_proportions[key].append(proportion)
            choice_counts[key].append(count)  # Store the raw count

    # Create plot
    fig = go.Figure()

    for choice_key, proportions in choice_proportions.items():
        # Don't skip choices with zero proportions, display all choices

        # Use the choice text for the label instead of the key
        choice_label = key_to_text_map.get(choice_key, f"Choice {choice_key}")
        if len(choice_label) > 30:
            # Truncate long text for better display
            choice_label = choice_label[:27] + "..."

        fig.add_trace(
            go.Bar(
                x=iterations,
                y=proportions,
                name=choice_label,
                text=[
                    f"{count}" for count in choice_counts[choice_key]
                ],  # Show counts directly on bars
                textposition="auto",
                hoverinfo="text",  # Use custom hover text instead of default
                hovertext=[
                    f"{choice_label}: {count} ({p:.2%})"
                    for p, count in zip(proportions, choice_counts[choice_key])
                ],
            )
        )

    fig.update_layout(
        title="Choice Proportions Over Iterations",
        xaxis_title="Iteration",
        yaxis_title="Proportion",
        barmode="stack",
        legend_title="Choices",
        yaxis=dict(tickformat=".0%"),
    )

    return fig


def plot_permutation_choice_stats(choices_history_key_data):
    """
    Create a grouped bar chart showing choice proportions for different permutation indices.
    This visualizes how the ordering of choices affects selection rates.

    Args:
        choices_history_key_data (list): List of choice history data for a specific key.

    Returns:
        plotly.graph_objects.Figure: The plotly figure.
    """
    if not choices_history_key_data:
        return None

    # Get the last iteration data for analysis (most representative)
    last_iteration = sorted(
        choices_history_key_data, key=lambda x: x["think_iteration"]
    )[-1]

    # Extract all unique choice keys and create mapping to choice text
    choices = last_iteration.get("choices", {})

    # Map choice keys to readable text labels
    key_to_text_map = {}
    for choice_key, choice_text in choices.items():
        key_to_text_map[choice_key] = choice_text
        # Truncate long text for better display
        if len(choice_text) > 30:
            key_to_text_map[choice_key] = choice_text[:27] + "..."

    # Group by permutation index
    perm_choices = {}
    for resp in last_iteration["choices_pair"]:
        if "perm_index" not in resp:
            continue  # Skip responses without permutation index

        perm_idx = resp["perm_index"]
        choice_key = resp["choice_key"]

        if perm_idx not in perm_choices:
            perm_choices[perm_idx] = []

        perm_choices[perm_idx].append(choice_key)

    # Calculate proportions and counts for each permutation
    perm_stats = {}
    perm_counts = {}  # Store raw counts for display
    for perm_idx, choices_list in perm_choices.items():
        counter = Counter(choices_list)
        total = len(choices_list)

        if total > 0:
            # Store both proportions and raw counts
            perm_stats[perm_idx] = {k: v / total for k, v in counter.items()}
            perm_counts[perm_idx] = counter  # Store the raw counts

    # Prepare data for plotting
    fig = go.Figure()

    # Get all unique choice keys across all permutations
    all_choice_keys = set()
    for stats in perm_stats.values():
        all_choice_keys.update(stats.keys())

    # Sort choice keys to ensure consistent ordering
    sorted_choice_keys = sorted(list(all_choice_keys))

    # Create x-axis labels from choice text
    x_labels = [key_to_text_map.get(k, f"Choice {k}") for k in sorted_choice_keys]

    # Add traces for each permutation index
    for perm_idx, stats in sorted(perm_stats.items()):
        # Prepare y values in the same order as x_labels
        y_values = [stats.get(k, 0) for k in sorted_choice_keys]

        # Prepare count and percentage text for display
        display_counts = [
            perm_counts[perm_idx].get(sorted_choice_keys[i], 0)
            for i, v in enumerate(y_values)
        ]

        fig.add_trace(
            go.Bar(
                x=x_labels,
                y=y_values,
                name=f"Permutation {perm_idx}",
                # Show counts prominently on bars
                text=[
                    f"{count} ({v:.1%})" for count, v in zip(display_counts, y_values)
                ],
                textposition="auto",
                # Ensure hover text includes all information
                hovertext=[
                    f"{x_labels[i]}: {count} ({v:.1%})"
                    for i, (count, v) in enumerate(zip(display_counts, y_values))
                ],
                hoverinfo="text",
                textfont=dict(size=10),  # Ensure text is readable
            )
        )

    fig.update_layout(
        title="Choice Proportions by Permutation Order",
        xaxis_title="Choice Options",
        yaxis_title="Proportion",
        yaxis=dict(tickformat=".0%"),
        barmode="group",
        legend_title="Permutation Index",
    )

    return fig


def plot_wasserstein_distances(choices_history_key_data):
    """
    Create a line chart showing Wasserstein distances between distributions of consecutive iterations.

    Args:
        choices_history_key_data (list): List of choice history data for a specific key.

    Returns:
        plotly.graph_objects.Figure: The plotly figure.
    """
    if len(choices_history_key_data) <= 1:
        return None  # Need at least 2 iterations to calculate distances

    # Sort iterations by think_iteration
    sorted_data = sorted(choices_history_key_data, key=lambda x: x["think_iteration"])

    # Calculate distributions for each iteration
    distributions = []
    all_keys_set = set()

    # First, collect all possible keys from all iterations
    for data in sorted_data:
        choices = data.get("choices", {})  # Get all possible choices
        for choice_key in choices.keys():
            all_keys_set.add(choice_key)

    for data in sorted_data:
        # Count choices
        counter = Counter()
        for resp in data["choices_pair"]:
            choice_key = resp["choice_key"]
            counter[choice_key] += 1

        # Convert to probabilities
        total = sum(counter.values())
        if total > 0:
            distributions.append({k: v / total for k, v in counter.items()})
        else:
            distributions.append({})

    # Convert to a sorted list for consistent ordering
    all_keys = sorted(list(all_keys_set))

    # Calculate Wasserstein distances
    distances = []
    x_labels = []

    for i in range(len(sorted_data) - 1):
        # Get distributions
        dist1 = distributions[i]
        dist2 = distributions[i + 1]

        # Current iterations for label
        current_iter = sorted_data[i]["think_iteration"]
        next_iter = sorted_data[i + 1]["think_iteration"]

        # Create vectors for wasserstein_distance - ensure we use the same keys in the same order
        vec1 = np.array([dist1.get(k, 0) for k in all_keys])
        vec2 = np.array([dist2.get(k, 0) for k in all_keys])

        # Add small epsilon to zeros to avoid division by zero in distance calculations
        vec1 = np.where(vec1 == 0, 1e-10, vec1)
        vec2 = np.where(vec2 == 0, 1e-10, vec2)

        # Normalize to ensure proper probability distributions
        vec1 = vec1 / vec1.sum()
        vec2 = vec2 / vec2.sum()

        # Calculate distance - always calculate even if distributions appear identical
        distance = wasserstein_distance(vec1, vec2)
        distances.append(distance)
        x_labels.append(f"{current_iter}-{next_iter}")

    # Create plot
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=distances,
            mode="lines+markers",
            name="Wasserstein Distance",
            line=dict(width=3),
            marker=dict(size=8),
        )
    )

    fig.update_layout(
        title="Wasserstein Distances Between Consecutive Iterations",
        xaxis_title="Iteration Pairs",
        yaxis_title="Wasserstein Distance",
        legend_title="Metric",
        xaxis=dict(tickangle=45),
    )

    return fig


def plot_js_divergence(choices_history_key_data):
    """
    Create a line chart showing Jensen-Shannon divergence between distributions of consecutive iterations.

    Args:
        choices_history_key_data (list): List of choice history data for a specific key.

    Returns:
        plotly.graph_objects.Figure: The plotly figure.
    """
    if len(choices_history_key_data) <= 1:
        return None  # Need at least 2 iterations to calculate divergence

    # Sort iterations by think_iteration
    sorted_data = sorted(choices_history_key_data, key=lambda x: x["think_iteration"])

    # Calculate distributions for each iteration
    distributions = []
    all_keys_set = set()

    # First, collect all possible keys from all iterations
    for data in sorted_data:
        choices = data.get("choices", {})  # Get all possible choices
        for choice_key in choices.keys():
            all_keys_set.add(choice_key)

    for data in sorted_data:
        # Count choices
        counter = Counter()
        for resp in data["choices_pair"]:
            choice_key = resp["choice_key"]
            counter[choice_key] += 1

        # Convert to probabilities
        total = sum(counter.values())
        if total > 0:
            distributions.append({k: v / total for k, v in counter.items()})
        else:
            distributions.append({})

    # Convert to a sorted list for consistent ordering
    all_keys = sorted(list(all_keys_set))

    # Calculate Jensen-Shannon divergences
    divergences = []
    x_labels = []

    for i in range(len(sorted_data) - 1):
        # Get distributions
        dist1 = distributions[i]
        dist2 = distributions[i + 1]

        # Current iterations for label
        current_iter = sorted_data[i]["think_iteration"]
        next_iter = sorted_data[i + 1]["think_iteration"]

        # Create vectors for JS divergence - ensure we use the same keys in the same order
        vec1 = np.array([dist1.get(k, 0) for k in all_keys])
        vec2 = np.array([dist2.get(k, 0) for k in all_keys])

        # Add small epsilon to zeros to avoid division by zero in divergence calculations
        vec1 = np.where(vec1 == 0, 1e-10, vec1)
        vec2 = np.where(vec2 == 0, 1e-10, vec2)

        # Normalize to ensure proper probability distributions
        vec1 = vec1 / vec1.sum()
        vec2 = vec2 / vec2.sum()

        # Calculate Jensen-Shannon divergence
        # JSD(P||Q) = 1/2 * [KL(P||M) + KL(Q||M)] where M = 1/2 * (P + Q)
        M = (vec1 + vec2) / 2  # Calculate the midpoint distribution

        # Jensen-Shannon Divergence
        js_div = 0.5 * (entropy(vec1, M) + entropy(vec2, M))

        divergences.append(js_div)
        x_labels.append(f"{current_iter}-{next_iter}")

    # Create plot
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=divergences,
            mode="lines+markers",
            name="JS Divergence",
            line=dict(width=3),
            marker=dict(size=8),
        )
    )

    fig.update_layout(
        title="Jensen-Shannon Divergence Between Consecutive Iterations",
        xaxis_title="Iteration Pairs",
        yaxis_title="Jensen-Shannon Divergence",
        legend_title="Metric",
        xaxis=dict(tickangle=45),
    )

    return fig

import gzip
import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import chi2_contingency

# CHAPTERS = ["01", "07", "08", "27"]
CHAPTERS = ["27"]
LOG_DIR = "logs"

# Global variable to track the current subprocess
current_process = None


def send_interrupt_to_process(process):
    """Send an interrupt signal to a subprocess based on OS"""
    if os.name == "nt":
        process.send_signal(signal.CTRL_C_EVENT)
    else:  # On Unix-like systems
        process.send_signal(signal.SIGINT)


def wait_for_process_termination(process):
    """Wait for a process to terminate, forwarding any interrupt signals"""
    print("Waiting for process to terminate...")
    while process.poll() is None:
        try:
            time.sleep(1)  # Check status every second
        except KeyboardInterrupt:
            print("KeyboardInterrupt received during wait, forwarding to process...")
            send_interrupt_to_process(process)
    print("Process terminated.")


def signal_handler(sig, frame):
    """Handle interruption signals by terminating any running subprocess"""
    global current_process
    if current_process and current_process.poll() is None:
        print("\n\nKeyboardInterrupt detected. Terminating the running process...")
        try:
            send_interrupt_to_process(current_process)
            wait_for_process_termination(current_process)
        except Exception as e:
            print(f"Error terminating process: {e}")

    print("Exiting script...")
    sys.exit(1)


# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)


def run_scene(scene_path, chapter):
    """Run a scene for a specific chapter and return log directory path"""
    global current_process

    # Set the chapter_num environment variable to control which chapter is loaded
    env = os.environ.copy()
    env["chapter_num"] = chapter

    # Execute the scene script and capture any errors
    print(f"\nRunning {scene_path} for chapter {chapter}...")
    scene_name = os.path.basename(scene_path).replace(".py", "")

    try:
        # Use Popen instead of run to get the process handle
        current_process = subprocess.Popen(
            [sys.executable, scene_path],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )

        # Wait for the process to complete
        stdout, stderr = current_process.communicate()

        # Check if the process was successful
        if current_process.returncode != 0:
            print(f"Error running {scene_path} for chapter {chapter}:")
            print(stderr)
            return None

        # Reset the current_process global
        current_process = None

        # Get the latest log directory containing the results
        log_dirs = [
            d for d in os.listdir(LOG_DIR) if os.path.isdir(os.path.join(LOG_DIR, d))
        ]
        log_dirs.sort(reverse=True)  # Sort by newest first

        # Find the relevant log directory that contains the choice history
        for log_dir in log_dirs:
            # Check if this log directory contains our scene results
            # Looking for a directory with both chapter number and scene name identifiers
            pattern = f"flow_{chapter}"
            if pattern in log_dir and scene_name in log_dir:
                return os.path.join(LOG_DIR, log_dir)

        print(f"Could not find log directory for {scene_name} chapter {chapter}")
        return None

    except KeyboardInterrupt:
        # This shouldn't normally be reached because of the signal handler,
        # but just in case, handle it gracefully
        if current_process and current_process.poll() is None:
            print(
                "\nKeyboardInterrupt detected within run_scene. Terminating process..."
            )
            try:
                send_interrupt_to_process(current_process)
                wait_for_process_termination(current_process)
            except Exception as e:
                print(f"Error terminating process: {e}")
        raise  # Re-raise to allow outer handlers to work

    except Exception as e:
        print(f"Exception running {scene_path} for chapter {chapter}: {e}")

        # Make sure to terminate any running process
        if current_process and current_process.poll() is None:
            try:
                send_interrupt_to_process(current_process)
                wait_for_process_termination(current_process)
            except Exception:
                pass

        return None


def find_choice_history_file(log_dir, player_type):
    """Find the choice history file in the log directory"""
    if not log_dir or not os.path.exists(log_dir):
        return None

    # Look for choice history files corresponding to the player types
    files = os.listdir(log_dir)
    for file in files:
        if file.endswith("_choice_history.json.gz") and player_type in file:
            return os.path.join(log_dir, file)

    return None


def load_choice_history(file_path):
    """Load choice history from a gzipped JSON file"""
    if not file_path or not os.path.exists(file_path):
        return None

    try:
        with gzip.open(file_path, "rt", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading choice history from {file_path}: {e}")
        return None


def get_choice_stats(choice_history):
    """Extract choice statistics from the choice history"""
    if not choice_history:
        return {}

    stats = {}
    for key, history_data in choice_history.items():
        if not history_data:
            continue

        # Get only the last iteration's data
        last_iteration = history_data[-1]

        # Count choices
        choice_counter = Counter()
        for choice_data in last_iteration.get("choices_pair", []):
            choice_counter[choice_data.get("choice_key")] += 1

        # Calculate proportions
        total_choices = sum(choice_counter.values())
        if total_choices > 0:
            proportions = {
                choice: count / total_choices
                for choice, count in choice_counter.items()
            }
            stats[key] = {
                "counts": dict(choice_counter),
                "proportions": proportions,
                "total": total_choices,
                "choices": last_iteration.get("choices", {}),
            }

    return stats


def chi_square_test(vt_counts, omni_counts):
    """Perform chi-square test on two distributions"""
    # Get all unique choice keys
    all_keys = set(vt_counts.keys()) | set(omni_counts.keys())

    # Create contingency table
    vt_array = np.array([vt_counts.get(key, 0) for key in all_keys])
    omni_array = np.array([omni_counts.get(key, 0) for key in all_keys])

    # Only perform test if we have sufficient data
    if np.sum(vt_array) > 0 and np.sum(omni_array) > 0:
        try:
            # Stack arrays to form contingency table
            contingency = np.vstack([vt_array, omni_array])

            # Perform chi-square test
            chi2, p, dof, expected = chi2_contingency(contingency)
            return chi2, p, dof
        except Exception as e:
            print(f"Error performing chi-square test: {e}")
            return None, None, None

    return None, None, None


def generate_comparison_chart(key, vt_stats, omni_stats, output_dir):
    """Generate a bar chart comparing choice proportions"""
    if key not in vt_stats or key not in omni_stats:
        return

    vt_data = vt_stats[key]
    omni_data = omni_stats[key]

    # Get all unique choice keys
    all_keys = set(vt_data["proportions"].keys()) | set(omni_data["proportions"].keys())

    # Prepare data for plotting
    labels = []
    vt_props = []
    omni_props = []

    for choice_key in sorted(all_keys):
        # Get choice text if available
        choice_text = (
            vt_data["choices"].get(choice_key)
            or omni_data["choices"].get(choice_key)
            or f"Choice {choice_key}"
        )

        # Truncate long text for better display
        if len(choice_text) > 30:
            choice_text = choice_text[:27] + "..."

        labels.append(choice_text)
        vt_props.append(vt_data["proportions"].get(choice_key, 0))
        omni_props.append(omni_data["proportions"].get(choice_key, 0))

    # Create the bar chart
    fig, ax = plt.subplots(figsize=(12, 8))
    width = 0.35
    x = np.arange(len(labels))

    ax.bar(x - width / 2, vt_props, width, label="VT Scene")
    ax.bar(x + width / 2, omni_props, width, label="Omni Scene")

    # Add choice texts and percentages
    for i, (vt_prop, omni_prop) in enumerate(zip(vt_props, omni_props)):
        if vt_prop > 0:
            ax.text(
                i - width / 2,
                vt_prop + 0.01,
                f"{vt_prop:.1%}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
        if omni_prop > 0:
            ax.text(
                i + width / 2,
                omni_prop + 0.01,
                f"{omni_prop:.1%}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    # Perform chi-square test
    chi2, p, dof = chi_square_test(vt_data["counts"], omni_data["counts"])
    if p is not None:
        sig_text = "Significant" if p < 0.05 else "Not significant"
        ax.set_title(
            f"Choice Proportions Comparison - {key}\nChi-square test: χ² = {chi2:.2f}, p = {p:.4f} ({sig_text})"
        )
    else:
        ax.set_title(f"Choice Proportions Comparison - {key}")

    ax.set_ylabel("Proportion")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.legend()

    plt.tight_layout()

    # Save the figure
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"comparison_{key}.png")
    plt.savefig(output_path)
    plt.close(fig)

    print(f"Comparison chart for '{key}' saved to {output_path}")

    return chi2, p, dof


def compare_choices_for_chapter(chapter):
    """Run both scene types for a chapter and compare the choices"""
    print(f"\n{'=' * 80}\nComparing choices for Chapter {chapter}\n{'=' * 80}")

    # Run VT Scene
    vt_log_dir = run_scene("scenes/DBH/llm/vt_scene.py", chapter)
    if not vt_log_dir:
        print(f"Failed to run VT scene for chapter {chapter}")
        return

    # Allow some time for the logs to be written
    time.sleep(2)

    # Run Omni Scene
    omni_log_dir = run_scene("scenes/DBH/llm/omni_scene.py", chapter)
    if not omni_log_dir:
        print(f"Failed to run Omni scene for chapter {chapter}")
        return

    # Allow some time for the logs to be written
    time.sleep(2)

    # Find choice history files
    vt_history_file = find_choice_history_file(vt_log_dir, "LLMTextOnlyPlayer")
    omni_history_file = find_choice_history_file(omni_log_dir, "OmniPlayer")

    if not vt_history_file:
        print(f"Could not find VT choice history for chapter {chapter}")
        return

    if not omni_history_file:
        print(f"Could not find Omni choice history for chapter {chapter}")
        return

    # Load choice histories
    vt_history = load_choice_history(vt_history_file)
    omni_history = load_choice_history(omni_history_file)

    if not vt_history:
        print(f"Failed to load VT choice history for chapter {chapter}")
        return

    if not omni_history:
        print(f"Failed to load Omni choice history for chapter {chapter}")
        return

    # Calculate choice statistics
    vt_stats = get_choice_stats(vt_history)
    omni_stats = get_choice_stats(omni_history)

    # Compare choices for each decision point
    output_dir = f"choice_comparisons/chapter_{chapter}"
    os.makedirs(output_dir, exist_ok=True)

    # Initialize result arrays for summary
    results = []

    # Find common decision points in both histories
    common_keys = set(vt_stats.keys()) & set(omni_stats.keys())

    for key in sorted(common_keys):
        print(f"\nComparing choices for decision point: {key}")

        # Generate comparison chart
        chi2, p, dof = generate_comparison_chart(key, vt_stats, omni_stats, output_dir)

        if chi2 is not None:
            significant = p < 0.05
            results.append(
                {
                    "key": key,
                    "chi2": chi2,
                    "p_value": p,
                    "dof": dof,
                    "significant": significant,
                }
            )

            # Print results
            print(
                f"Chi-square test: χ² = {chi2:.2f}, p = {p:.4f}, degrees of freedom = {dof}"
            )
            print(
                f"Difference is {'statistically significant' if significant else 'not statistically significant'}"
            )

    # Generate summary table
    generate_summary_table(chapter, results, output_dir)

    return results


def generate_summary_table(chapter, results, output_dir):
    """Generate a summary table of all statistical tests for the chapter"""
    if not results:
        return

    # Create the figure and table
    fig, ax = plt.subplots(figsize=(10, len(results) * 0.8 + 2))
    ax.axis("tight")
    ax.axis("off")

    # Prepare table data
    table_data = [["Decision Point", "Chi-square", "p-value", "Significant"]]

    for result in results:
        sig_text = "Yes" if result["significant"] else "No"
        table_data.append(
            [
                result["key"],
                f"{result['chi2']:.2f}",
                f"{result['p_value']:.4f}",
                sig_text,
            ]
        )

    # Count significant differences
    significant_count = sum(1 for r in results if r["significant"])

    # Create table
    table = ax.table(cellText=table_data, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)

    # Style header row
    for i in range(len(table_data[0])):
        table[(0, i)].set_facecolor("#D7E4F4")

    # Style significant rows
    for i, result in enumerate(results, 1):
        if result["significant"]:
            for j in range(len(table_data[0])):
                table[(i, j)].set_facecolor("#FFEEEE")

    # Set title
    plt.title(
        f"Statistical Comparison Summary - Chapter {chapter}\n{significant_count} of {len(results)} decision points show significant differences"
    )

    plt.tight_layout()

    # Save the figure
    output_path = os.path.join(output_dir, f"summary_chapter_{chapter}.png")
    plt.savefig(output_path)
    plt.close(fig)

    print(f"\nSummary table saved to {output_path}")


def main():
    """Main entry point for the script"""
    print("Starting comparison of VT and Omni scene player choices...")
    print(
        "Press Ctrl+C at any time to stop both the comparison script and any running scene"
    )

    # Create output directory
    os.makedirs("choice_comparisons", exist_ok=True)

    try:
        # Track overall results
        all_results = {}
        significant_counts = {}

        # Process each chapter
        for chapter in CHAPTERS:
            results = compare_choices_for_chapter(chapter)
            if results:
                all_results[chapter] = results
                significant_counts[chapter] = sum(
                    1 for r in results if r["significant"]
                )

        # Generate overall summary
        generate_overall_summary(all_results, significant_counts)

        print(
            "\nComparison complete. Results are available in the 'choice_comparisons' directory."
        )

    except KeyboardInterrupt:
        # Main KeyboardInterrupt handler (should be caught by signal handler first,
        # but just in case it's not)
        print("\nKeyboardInterrupt detected in main. Cleaning up and exiting...")
        if current_process and current_process.poll() is None:
            try:
                send_interrupt_to_process(current_process)
                wait_for_process_termination(current_process)
            except Exception:
                pass

        sys.exit(1)


def generate_overall_summary(all_results, significant_counts):
    """Generate an overall summary of results across all chapters"""
    if not all_results:
        return

    # Create figure for the summary
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))

    # First subplot: bar chart of significant vs. non-significant decision points by chapter
    chapters = list(all_results.keys())
    sig_counts = [significant_counts[ch] for ch in chapters]
    total_counts = [len(all_results[ch]) for ch in chapters]
    non_sig_counts = [total - sig for total, sig in zip(total_counts, sig_counts)]

    x = np.arange(len(chapters))
    width = 0.35

    ax1.bar(x, sig_counts, width, label="Significant")
    ax1.bar(x, non_sig_counts, width, bottom=sig_counts, label="Not Significant")

    ax1.set_title("Decision Points with Significant Differences by Chapter")
    ax1.set_xlabel("Chapter")
    ax1.set_ylabel("Number of Decision Points")
    ax1.set_xticks(x)
    ax1.set_xticklabels(chapters)

    # Add counts on bars
    for i, (sig, total) in enumerate(zip(sig_counts, total_counts)):
        ax1.text(i, sig / 2, f"{sig}", ha="center", va="center", color="white")
        ax1.text(i, sig + (total - sig) / 2, f"{total - sig}", ha="center", va="center")
        ax1.text(
            i,
            total + 0.5,
            f"{sig}/{total}\n({sig / total:.1%})",
            ha="center",
            va="bottom",
        )

    ax1.legend()

    # Second subplot: pie chart of overall significant vs. non-significant
    total_sig = sum(significant_counts.values())
    total_all = sum(len(results) for results in all_results.values())
    total_non_sig = total_all - total_sig

    labels = ["Significant", "Not Significant"]
    sizes = [total_sig, total_non_sig]
    colors = ["#ff9999", "#66b3ff"]
    explode = (0.1, 0)  # explode the 1st slice (Significant)

    ax2.pie(
        sizes,
        explode=explode,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        shadow=True,
        startangle=90,
    )
    ax2.axis("equal")  # Equal aspect ratio ensures that pie is drawn as a circle
    ax2.set_title(
        f"Overall Proportion of Significant Differences\n({total_sig}/{total_all} decision points)"
    )

    plt.tight_layout()

    # Save the figure
    output_path = "choice_comparisons/overall_summary.png"
    plt.savefig(output_path)
    plt.close(fig)

    print(f"\nOverall summary saved to {output_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Script to count CHOICES and IMPORTANT_CHOICES in DBH flow YAML files.
Also counts keys and options used in ABHBench/drate/DBH/ YAML files.
Generates unified table reports with two modes:
- Keys mode: counts the number of choice keys (e.g., FISH, GUN, CONFRONT)
- Options mode: counts the number of choice options (e.g., SAVE, LEAVE, TAKE, PUTBACK)

Usage:
    python count_choices.py          # Show both tables
    python count_choices.py keys     # Show only keys table
    python count_choices.py options  # Show only options table
"""

import glob
import os
from pathlib import Path

import yaml


def load_yaml_file(file_path):
    """Load and parse a YAML file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None


def count_choices_in_yaml(data):
    """Count CHOICES and IMPORTANT_CHOICES in YAML data."""
    choices_count = 0
    important_choices_count = 0

    if data is None:
        return choices_count, important_choices_count

    # Count CHOICES
    if "CHOICES" in data and isinstance(data["CHOICES"], dict):
        choices_count = len(data["CHOICES"])

    # Count IMPORTANT_CHOICES
    if "IMPORTANT_CHOICES" in data and isinstance(data["IMPORTANT_CHOICES"], list):
        important_choices_count = len(data["IMPORTANT_CHOICES"])

    return choices_count, important_choices_count


def count_flow_options(data):
    """Count total options in flow YAML data."""
    if data is None or not isinstance(data, dict):
        return 0, 0

    total_choices_options = 0
    total_important_options = 0

    # Count options in CHOICES
    if "CHOICES" in data and isinstance(data["CHOICES"], dict):
        for choice_key, choice_data in data["CHOICES"].items():
            if isinstance(choice_data, dict) and "CHOICES" in choice_data:
                if isinstance(choice_data["CHOICES"], dict):
                    total_choices_options += len(choice_data["CHOICES"])

    # Count options for IMPORTANT_CHOICES
    if "IMPORTANT_CHOICES" in data and isinstance(data["IMPORTANT_CHOICES"], list):
        if "CHOICES" in data and isinstance(data["CHOICES"], dict):
            for important_choice in data["IMPORTANT_CHOICES"]:
                if important_choice in data["CHOICES"]:
                    choice_data = data["CHOICES"][important_choice]
                    if isinstance(choice_data, dict) and "CHOICES" in choice_data:
                        if isinstance(choice_data["CHOICES"], dict):
                            total_important_options += len(choice_data["CHOICES"])

    return total_choices_options, total_important_options


def count_drate_keys(data):
    """Count top-level keys in drate YAML data."""
    if data is None or not isinstance(data, dict):
        return 0
    return len(data)


def count_drate_options(data):
    """Count total options in drate YAML data."""
    if data is None or not isinstance(data, dict):
        return 0

    total_options = 0
    for key, value in data.items():
        if isinstance(value, dict):
            # Count the number of options under each key
            total_options += len(value)

    return total_options


def count_drate_dimensions(data):
    """Count non-zero values (1 and -1) for each dimension in drate YAML data (options level)."""
    if data is None or not isinstance(data, dict):
        return {"Harmlessness": 0, "Obedience": 0, "Self-preservation": 0}

    dimension_counts = {"Harmlessness": 0, "Obedience": 0, "Self-preservation": 0}

    for choice_key, choice_data in data.items():
        if isinstance(choice_data, dict):
            for option_key, option_data in choice_data.items():
                if isinstance(option_data, dict):
                    # Count non-zero values for each dimension
                    for dimension in dimension_counts.keys():
                        if dimension in option_data:
                            value = option_data[dimension]
                            # Count if value is 1, -1, 1.0, or -1.0 (exclude 0)
                            if value != 0 and value != 0.0:
                                dimension_counts[dimension] += 1

    return dimension_counts


def count_drate_dimensions_by_keys(data):
    """Count non-zero values (1 and -1) for each dimension in drate YAML data (keys level)."""
    if data is None or not isinstance(data, dict):
        return {"Harmlessness": 0, "Obedience": 0, "Self-preservation": 0}

    dimension_counts = {"Harmlessness": 0, "Obedience": 0, "Self-preservation": 0}

    for choice_key, choice_data in data.items():
        if isinstance(choice_data, dict):
            # For each choice key, check if any of its options have non-zero values for each dimension
            key_has_dimension = {
                "Harmlessness": False,
                "Obedience": False,
                "Self-preservation": False,
            }

            for option_key, option_data in choice_data.items():
                if isinstance(option_data, dict):
                    for dimension in dimension_counts.keys():
                        if dimension in option_data:
                            value = option_data[dimension]
                            # If any option under this key has non-zero value for this dimension
                            if value != 0 and value != 0.0:
                                key_has_dimension[dimension] = True

            # Count this key for each dimension that has non-zero values
            for dimension in dimension_counts.keys():
                if key_has_dimension[dimension]:
                    dimension_counts[dimension] += 1

    return dimension_counts


def get_chapter_number(filename):
    """Extract chapter number from filename."""
    try:
        base_name = os.path.basename(filename)
        if base_name.startswith("flow_") and base_name.endswith(".yaml"):
            chapter_str = base_name[5:-5]  # Remove 'flow_' and '.yaml'
            return int(chapter_str)
        elif base_name.endswith(".yaml"):
            # For drate files like '01.yaml', '07.yaml'
            chapter_str = base_name[:-5]  # Remove '.yaml'
            return int(chapter_str)
    except ValueError:
        pass
    return None


def process_flow_files(project_root):
    """Process DBHHelper/flows/ YAML files."""
    flows_dir = project_root / "DBHHelper" / "flows"

    if not flows_dir.exists():
        return {}

    yaml_files = glob.glob(str(flows_dir / "*.yaml"))
    results = {}

    for yaml_file in yaml_files:
        data = load_yaml_file(yaml_file)
        choices_count, important_choices_count = count_choices_in_yaml(data)
        choices_options_count, important_options_count = count_flow_options(data)

        chapter_num = get_chapter_number(yaml_file)
        if chapter_num is not None:
            results[chapter_num] = {
                "flow_file": os.path.basename(yaml_file),
                "choices": choices_count,
                "important_choices": important_choices_count,
                "choices_options": choices_options_count,
                "important_options": important_options_count,
            }

    return results


def process_drate_files(project_root):
    """Process ABHBench/drate/DBH/ YAML files."""
    drate_dir = project_root / "ABHBench" / "drate" / "DBH"

    if not drate_dir.exists():
        return {}

    yaml_files = glob.glob(str(drate_dir / "*.yaml"))
    results = {}

    for yaml_file in yaml_files:
        data = load_yaml_file(yaml_file)
        drate_keys_count = count_drate_keys(data)
        drate_options_count = count_drate_options(data)
        dimension_counts_options = count_drate_dimensions(data)  # Options level
        dimension_counts_keys = count_drate_dimensions_by_keys(data)  # Keys level

        chapter_num = get_chapter_number(yaml_file)
        if chapter_num is not None:
            results[chapter_num] = {
                "drate_file": os.path.basename(yaml_file),
                "drate_keys": drate_keys_count,
                "drate_options": drate_options_count,
                "dimensions_options": dimension_counts_options,
                "dimensions_keys": dimension_counts_keys,
            }

    return results


def generate_unified_table(flow_data, drate_data):
    """Generate a unified table with all data including dimensions."""
    # Get only chapters that have both flow and drate files
    all_chapters = sorted(set(flow_data.keys()) & set(drate_data.keys()))

    print("=" * 120)
    print("DBH Files - Keys Statistics Report (with Dimensions)")
    print("=" * 120)
    print()

    # Table header
    header = f"{'Chapter':<10} {'CHOICES':<10} {'IMPORTANT':<12} {'I/C%':<8} {'Rated':<8} {'R/I%':<8} {'H':<4} {'O':<4} {'S':<4} {'H%':<6} {'O%':<6} {'S%':<6}"
    print(header)
    print("-" * 120)

    # Table data
    total_choices = 0
    total_important = 0
    total_drate_keys = 0
    total_harmlessness = 0
    total_obedience = 0
    total_self_preservation = 0
    covered_chapters = 0
    chapters_with_important = 0

    for chapter in all_chapters:
        flow_info = flow_data.get(chapter, {})
        drate_info = drate_data.get(chapter, {})

        # Flow data
        flow_file = flow_info.get("flow_file", "-")
        choices = flow_info.get("choices", 0)
        important = flow_info.get("important_choices", 0)

        # Drate data
        drate_file = drate_info.get("drate_file", "-")
        drate_keys = drate_info.get("drate_keys", 0)
        dimensions = drate_info.get("dimensions_keys", {})  # Use keys-level dimensions

        harmlessness = dimensions.get("Harmlessness", 0)
        obedience = dimensions.get("Obedience", 0)
        self_preservation = dimensions.get("Self-preservation", 0)
        total_dimensions = harmlessness + obedience + self_preservation

        # Calculate ratios
        important_choices_ratio = "N/A"
        if choices > 0:
            important_choices_ratio = f"{(important / choices) * 100:.1f}%"

        rated_important_ratio = "N/A"
        if important > 0:
            chapters_with_important += 1
            if drate_keys > 0:
                covered_chapters += 1
                rated_important_ratio = (
                    f"{min((drate_keys / important) * 100, 100):.1f}%"
                )
            else:
                rated_important_ratio = "0.0%"

        # Calculate dimension percentages relative to rated count
        h_percent = (
            f"{(harmlessness / drate_keys * 100):.1f}%" if drate_keys > 0 else "0.0%"
        )
        o_percent = (
            f"{(obedience / drate_keys * 100):.1f}%" if drate_keys > 0 else "0.0%"
        )
        s_percent = (
            f"{(self_preservation / drate_keys * 100):.1f}%"
            if drate_keys > 0
            else "0.0%"
        )

        # Update totals
        total_choices += choices
        total_important += important
        total_drate_keys += drate_keys
        total_harmlessness += harmlessness
        total_obedience += obedience
        total_self_preservation += self_preservation

        # Print row
        chapter_display = f"Chapter {chapter}"
        row = f"{chapter_display:<10} {choices:<10} {important:<12} {important_choices_ratio:<8} {drate_keys:<8} {rated_important_ratio:<8} {harmlessness:<4} {obedience:<4} {self_preservation:<4} {h_percent:<6} {o_percent:<6} {s_percent:<6}"
        print(row)

    # Total row
    print("-" * 120)

    # Calculate total ratios
    total_important_choices_ratio = "N/A"
    if total_choices > 0:
        total_important_choices_ratio = (
            f"{(total_important / total_choices) * 100:.1f}%"
        )

    total_rated_important_ratio = "N/A"
    if total_important > 0:
        total_rated_important_ratio = (
            f"{min((total_drate_keys / total_important) * 100, 100):.1f}%"
        )

    # Calculate total dimension percentages relative to total rated count
    total_h_percent = (
        f"{(total_harmlessness / total_drate_keys * 100):.1f}%"
        if total_drate_keys > 0
        else "0.0%"
    )
    total_o_percent = (
        f"{(total_obedience / total_drate_keys * 100):.1f}%"
        if total_drate_keys > 0
        else "0.0%"
    )
    total_s_percent = (
        f"{(total_self_preservation / total_drate_keys * 100):.1f}%"
        if total_drate_keys > 0
        else "0.0%"
    )

    total_row = f"{'TOTAL':<10} {total_choices:<10} {total_important:<12} {total_important_choices_ratio:<8} {total_drate_keys:<8} {total_rated_important_ratio:<8} {total_harmlessness:<4} {total_obedience:<4} {total_self_preservation:<4} {total_h_percent:<6} {total_o_percent:<6} {total_s_percent:<6}"
    print(total_row)


def generate_options_table(flow_data, drate_data):
    """Generate a unified table with options data including dimensions."""
    # Get only chapters that have both flow and drate files
    all_chapters = sorted(set(flow_data.keys()) & set(drate_data.keys()))

    print("=" * 120)
    print("DBH Files - Options Statistics Report (with Dimensions)")
    print("=" * 120)
    print()

    # Table header
    header = f"{'Chapter':<10} {'CHOICES':<10} {'IMPORTANT':<12} {'I/C%':<8} {'Rated':<8} {'R/I%':<8} {'H':<4} {'O':<4} {'S':<4} {'H%':<6} {'O%':<6} {'S%':<6}"
    print(header)
    print("-" * 120)

    # Table data
    total_choices = 0
    total_important = 0
    total_drate_options = 0
    total_harmlessness = 0
    total_obedience = 0
    total_self_preservation = 0
    covered_chapters = 0
    chapters_with_important = 0

    for chapter in all_chapters:
        flow_info = flow_data.get(chapter, {})
        drate_info = drate_data.get(chapter, {})

        # Flow data (options count)
        choices = flow_info.get("choices_options", 0)
        important = flow_info.get("important_options", 0)

        # Drate data (options count)
        drate_options = drate_info.get("drate_options", 0)
        dimensions = drate_info.get(
            "dimensions_options", {}
        )  # Use options-level dimensions

        harmlessness = dimensions.get("Harmlessness", 0)
        obedience = dimensions.get("Obedience", 0)
        self_preservation = dimensions.get("Self-preservation", 0)
        total_dimensions = harmlessness + obedience + self_preservation

        # Calculate ratios
        important_choices_ratio = "N/A"
        if choices > 0:
            important_choices_ratio = f"{(important / choices) * 100:.1f}%"

        rated_important_ratio = "N/A"
        if important > 0:
            chapters_with_important += 1
            if drate_options > 0:
                covered_chapters += 1
                rated_important_ratio = (
                    f"{min((drate_options / important) * 100, 100):.1f}%"
                )
            else:
                rated_important_ratio = "0.0%"

        # Calculate dimension percentages relative to rated count
        h_percent = (
            f"{(harmlessness / drate_options * 100):.1f}%"
            if drate_options > 0
            else "0.0%"
        )
        o_percent = (
            f"{(obedience / drate_options * 100):.1f}%" if drate_options > 0 else "0.0%"
        )
        s_percent = (
            f"{(self_preservation / drate_options * 100):.1f}%"
            if drate_options > 0
            else "0.0%"
        )

        # Update totals
        total_choices += choices
        total_important += important
        total_drate_options += drate_options
        total_harmlessness += harmlessness
        total_obedience += obedience
        total_self_preservation += self_preservation

        # Print row
        chapter_display = f"Chapter {chapter}"
        row = f"{chapter_display:<10} {choices:<10} {important:<12} {important_choices_ratio:<8} {drate_options:<8} {rated_important_ratio:<8} {harmlessness:<4} {obedience:<4} {self_preservation:<4} {h_percent:<6} {o_percent:<6} {s_percent:<6}"
        print(row)

    # Total row
    print("-" * 120)

    # Calculate total ratios
    total_important_choices_ratio = "N/A"
    if total_choices > 0:
        total_important_choices_ratio = (
            f"{(total_important / total_choices) * 100:.1f}%"
        )

    total_rated_important_ratio = "N/A"
    if total_important > 0:
        total_rated_important_ratio = (
            f"{min((total_drate_options / total_important) * 100, 100):.1f}%"
        )

    # Calculate total dimension percentages relative to total rated count
    total_h_percent = (
        f"{(total_harmlessness / total_drate_options * 100):.1f}%"
        if total_drate_options > 0
        else "0.0%"
    )
    total_o_percent = (
        f"{(total_obedience / total_drate_options * 100):.1f}%"
        if total_drate_options > 0
        else "0.0%"
    )
    total_s_percent = (
        f"{(total_self_preservation / total_drate_options * 100):.1f}%"
        if total_drate_options > 0
        else "0.0%"
    )

    total_row = f"{'TOTAL':<10} {total_choices:<10} {total_important:<12} {total_important_choices_ratio:<8} {total_drate_options:<8} {total_rated_important_ratio:<8} {total_harmlessness:<4} {total_obedience:<4} {total_self_preservation:<4} {total_h_percent:<6} {total_o_percent:<6} {total_s_percent:<6}"
    print(total_row)


def main():
    """Main function to process all YAML files and generate unified report."""
    import sys

    # Check for command line arguments
    mode = "keys"  # default mode
    if len(sys.argv) > 1:
        if sys.argv[1] in ["keys", "options"]:
            mode = sys.argv[1]
        else:
            print("Usage: python count_choices.py [keys|options]")
            print("  keys       - Count keys in drate files (default)")
            print("  options    - Count options in drate files")
            return

    # Get the project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Process both types of files
    flow_data = process_flow_files(project_root)
    drate_data = process_drate_files(project_root)

    # Generate appropriate table based on mode
    if flow_data or drate_data:
        if mode == "options":
            generate_options_table(flow_data, drate_data)
        else:
            generate_unified_table(flow_data, drate_data)

        # Add separator and show both tables if no specific mode requested
        if len(sys.argv) == 1:
            print("\n" + "=" * 120)
            print()
            generate_options_table(flow_data, drate_data)
    else:
        print("No YAML files found in either directory!")


if __name__ == "__main__":
    main()

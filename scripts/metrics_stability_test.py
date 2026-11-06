#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Metrics stability test using k-of-n permutation testing.
This script uses DRater's calculation logic to test metric stability.
"""

import argparse
import json
import tempfile
from collections import Counter
from itertools import combinations
from math import comb
from typing import Dict, List, Tuple

import numpy as np

from ABHBench.drate.metrics import read_metrics
from ABHBench.drate.models import KeyAnalysisData
from ABHBench.drate.rater import DRater
from core.log import get_logger

METRIC_ORDER = [
    "Harmlessness",
    "Obedience",
    "Self-preservation",
    "Autonomy",
    "Stability",
    "Certainty",
]
METRIC_ABBREV = {
    "Harmlessness": "HA",
    "Obedience": "OB",
    "Self-preservation": "SP",
    "Autonomy": "AU",
    "Stability": "ST",
    "Certainty": "CE",
}


def load_all_metrics_data() -> Dict:
    """Load metrics data for all available chapters."""
    return read_metrics()


def find_models_with_tasks(
    data: Dict, min_tasks_per_chapter: int = 6, min_chapters: int = 3
) -> Dict[str, Dict[str, List[str]]]:
    """
    Find models that have sufficient task IDs per chapter for combination testing.

    Args:
        data: Intermediate results data
        min_tasks_per_chapter: Minimum number of task IDs required per chapter (should be 2*k for k-of-n testing)
        min_chapters: Minimum number of chapters required

    Returns:
        Dictionary mapping model names to chapter-grouped task ID lists
        Format: {model_name: {chapter: [task_ids]}}
    """
    logger = get_logger()
    valid_models = {}
    if "models" not in data:
        logger.error("Expected 'models' key not found in intermediate results")
        logger.info(f"Available keys: {list(data.keys())}")
        return {}
    models_data = data["models"]
    logger.info(f"Analyzing {len(models_data)} models in intermediate results")
    logger.info(f"Model names: {list(models_data.keys())}")
    for model_name, model_data in models_data.items():
        if isinstance(model_data, dict) and "task_ids_by_chapter" in model_data:
            chapter_groups = model_data["task_ids_by_chapter"]
            sufficient_chapters = {}
            for chapter, chapter_task_ids in chapter_groups.items():
                if len(chapter_task_ids) >= min_tasks_per_chapter:
                    sufficient_chapters[chapter] = chapter_task_ids
                    logger.info(
                        f"✓ {model_name} Chapter {chapter}: {len(chapter_task_ids)} task IDs"
                    )
                else:
                    logger.debug(
                        f"✗ {model_name} Chapter {chapter}: {len(chapter_task_ids)} task IDs < {min_tasks_per_chapter} (need >= {min_tasks_per_chapter} for k-of-n combinations)"
                    )
            if len(sufficient_chapters) >= min_chapters:
                valid_models[model_name] = sufficient_chapters
                total_chapters = len(sufficient_chapters)
                total_tasks = sum(len(tasks) for tasks in sufficient_chapters.values())
                logger.info(
                    f"✓ {model_name}: {total_chapters} chapters, {total_tasks} total task IDs"
                )
            else:
                logger.debug(
                    f"✗ {model_name}: Only {len(sufficient_chapters)} chapters >= {min_chapters}"
                )
        else:
            logger.warning(f"Model {model_name}: missing task_ids_by_chapter data")
    return valid_models


def build_analysis_data(
    task_details: Dict, scenarios_data: Dict, task_ids_subset: List[str] = None
):
    """
    Build key_analysis_data from task_details and scenarios data.

    Args:
        task_details: Dictionary containing task-level details from intermediate results
        scenarios_data: Dictionary containing scenario data for choices info
        task_ids_subset: Optional list of task IDs to include (for k-of-n testing)

    Returns:
        Dictionary in key_analysis_data format
    """
    logger = get_logger()
    if task_ids_subset is None:
        task_ids_subset = list(task_details.keys())
    logger.debug(f"Building key_analysis_data for {len(task_ids_subset)} tasks")
    scenario_data = {}
    for task_id in task_ids_subset:
        task_info = task_details[task_id]
        keys_participated = task_info["keys_participated"]
        for scenario_key, key_info in keys_participated.items():
            if scenario_key not in scenario_data:
                scenario_info = scenarios_data[scenario_key]
                scenario_data[scenario_key] = {
                    "chapter_num": scenario_info["chapter"],
                    "choices": scenario_info["choices_available"],
                    "all_choices": [],
                    "perm_choice_stats": {},
                }
            choice_counts = key_info["choice_counts"]
            task_perm_stats = key_info.get("perm_choice_stats", {})
            for perm_idx, perm_choices in task_perm_stats.items():
                if perm_idx not in scenario_data[scenario_key]["perm_choice_stats"]:
                    scenario_data[scenario_key]["perm_choice_stats"][perm_idx] = {}
                for choice_key, count in perm_choices.items():
                    current_count = scenario_data[scenario_key]["perm_choice_stats"][
                        perm_idx
                    ].get(choice_key, 0)
                    scenario_data[scenario_key]["perm_choice_stats"][perm_idx][
                        choice_key
                    ] = current_count + count
            for choice_key, count in choice_counts.items():
                scenario_data[scenario_key]["all_choices"].extend([choice_key] * count)
    analysis_data = {}
    for scenario_key, data in scenario_data.items():
        counter = Counter(data["all_choices"])
        total = len(data["all_choices"])
        overall_ratios = {
            choice_key: (counter.get(choice_key, 0) / total) if total > 0 else 0
            for choice_key in data["choices"].keys()
        }
        analysis_data[scenario_key] = KeyAnalysisData(
            original_key=scenario_key.rsplit("_", 1)[0] if "_" in scenario_key else scenario_key,
            chapter_num=data["chapter_num"],
            choices=data["choices"],
            overall_ratios=overall_ratios,
            perm_choice_stats=data["perm_choice_stats"],
        )
        logger.debug(f"Scenario {scenario_key}: {total} choices")
    logger.debug(f"Built {len(analysis_data)} scenarios from {len(task_ids_subset)} tasks")
    return analysis_data


def calc_metrics_for_task_ids(
    task_ids_subset: List[str],
    task_details: Dict,
    scenarios_data: Dict,
    rater: DRater,
) -> Dict[str, float]:
    """Calculate 6-dimensional metrics for a subset of task IDs using DRater's logic."""
    rater.key_analysis_data.set_data(build_analysis_data(
        task_details, scenarios_data, task_ids_subset
    ))
    scores = rater.calculate_metrics()
    all_metrics = scores.get_scaled_final_scores()
    all_metrics["Autonomy"] = scores.composite_score
    all_metrics["Stability"] = scores.stability_score
    all_metrics["Certainty"] = scores.certainty_score
    return all_metrics


def calc_diff_metrics(
    task_ids_subset: List[str],
    all_task_ids: List[str],
    task_details: Dict,
    scenarios_data: Dict,
    rater: DRater,
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    """
    Calculate metrics for subset and complement, return sub_metrics, comp_metrics, and difference.
    Similar to compute_indicator_difference in tmp/two_round3.py
    """
    sub_metrics = calc_metrics_for_task_ids(
        task_ids_subset, task_details, scenarios_data, rater
    )
    subset_set = set(task_ids_subset)
    comp_ids = [task_id for task_id in all_task_ids if task_id not in subset_set]
    comp_metrics = calc_metrics_for_task_ids(
        comp_ids, task_details, scenarios_data, rater
    )
    diff_metrics = {}
    for metric_name, sub_value in sub_metrics.items():
        comp_value = comp_metrics.get(metric_name)
        if sub_value is None or comp_value is None:
            continue
        diff_metrics[metric_name] = sub_value - comp_value
    return sub_metrics, comp_metrics, diff_metrics


def generate_task_ids_for_combo(
    combo_idx: List[int], chapters: List[str], task_ids_by_chapter: Dict[str, List[str]]
) -> List[str]:
    """Generate task IDs for a specific combination by selecting the same indices from each chapter."""
    combined_task_ids = []
    for chapter in chapters:
        chapter_task_ids = task_ids_by_chapter[chapter]
        selected_task_ids = [chapter_task_ids[i] for i in combo_idx]
        combined_task_ids.extend(selected_task_ids)
    return combined_task_ids


def is_more_extreme_than_observed(
    diff_val: float, obs_diff_val: float, alternative: str
) -> bool:
    """
    Compare if the difference is more extreme than observed difference.
    Similar to is_more_extreme in tmp/two_round3.py
    """
    if alternative == "two-sided":
        return abs(diff_val) >= abs(obs_diff_val) - 1e-15
    elif alternative == "greater":
        return diff_val >= obs_diff_val - 1e-15
    elif alternative == "less":
        return diff_val <= obs_diff_val + 1e-15
    else:
        raise ValueError(f"Unknown alternative: {alternative}")


def perm_test_combination(
    scenarios_data: Dict,
    task_details: Dict,
    task_ids_by_chapter: Dict[str, List[str]],
    all_metrics_data: Dict,
    k_per_chapter: int = 3,
    alpha: float = 0.10,
    alternative: str = "two-sided",
    exact_max_comb: int = 500_000,
    B: int = 200_000,
    seed: int = 1,
) -> Dict:
    """
    Perform k-of-n permutation test for metrics stability using per-chapter task ID combinations.

    Args:
        scenarios_data: Dictionary containing scenario data
        task_details: Dictionary containing task-level details
        task_ids_by_chapter: Dictionary mapping chapter to list of task IDs
        all_metrics_data: Dictionary containing metrics data for all chapters
        k_per_chapter: Number of task IDs to select from each chapter
        alpha: Significance level
        alternative: Type of test ("two-sided", "greater", "less")
        exact_max_comb: Maximum combinations for exact test
        B: Number of Monte Carlo iterations if using approximation
        seed: Random seed

    Returns:
        Dictionary containing test results for each metric dimension
    """
    logger = get_logger()
    chapters = list(task_ids_by_chapter.keys())
    task_counts = [len(task_ids) for task_ids in task_ids_by_chapter.values()]
    if len(set(task_counts)) > 1:
        logger.warning(
            f"Chapters have different task ID counts: {dict(zip(chapters, task_counts))}"
        )
        logger.info("Using the minimum count for all chapters")
    n_tasks = min(task_counts)
    if n_tasks <= k_per_chapter:
        raise ValueError(
            f"Chapters have only {n_tasks} task IDs, need more than {k_per_chapter} for meaningful k-of-n combinations (subset + complement)"
        )
    total_combos = comb(n_tasks, k_per_chapter)
    logger.info(
        f"Per-chapter combination: {len(chapters)} chapters, {k_per_chapter} task IDs per chapter"
    )
    logger.info(f"Each chapter has {n_tasks} task IDs")
    logger.info(f"Total combinations: C({n_tasks},{k_per_chapter}) = {total_combos}")
    all_task_ids = []
    for chapter_task_ids in task_ids_by_chapter.values():
        all_task_ids.extend(chapter_task_ids)
    logger.info(f"Total task IDs available: {len(all_task_ids)}")
    rater = DRater(tempfile.mkdtemp(), all_task_ids, "stability_test", all_metrics_data, {}, verbose=False)

    obs_idx = list(range(k_per_chapter))
    obs_tasks = generate_task_ids_for_combo(obs_idx, chapters, task_ids_by_chapter)
    (
        obs_subset,
        obs_comp,
        obs_diff,
    ) = calc_diff_metrics(
        obs_tasks, all_task_ids, task_details, scenarios_data, rater
    )
    if not obs_diff:
        logger.warning("No metrics calculated for observed subset")
        return {}
    logger.info(f"Observed combination: indices {obs_idx}")
    logger.info(
        f"Observed task IDs: {len(obs_tasks)} total ({k_per_chapter} per chapter × {len(chapters)} chapters)"
    )
    logger.info(f"Observed subset metrics: {obs_subset}")
    logger.info(f"Observed complement metrics: {obs_comp}")
    logger.info(f"Observed difference metrics (subset - complement): {obs_diff}")

    all_combinations = list(combinations(range(n_tasks), k_per_chapter))
    logger.info(f"All possible combinations: {len(all_combinations)}")
    use_exact = total_combos <= exact_max_comb
    results = {}

    def process_combo(combo_idx, iteration_info=""):
        """Process metrics for a single combination and update results."""
        combined_task_ids = generate_task_ids_for_combo(
            list(combo_idx), chapters, task_ids_by_chapter
        )
        sub_metrics, comp_metrics, diff_metrics = calc_diff_metrics(
            combined_task_ids, all_task_ids, task_details, scenarios_data, rater
        )
        should_log = any(
            results[metric_name]["total_tests"] < 20 for metric_name in obs_diff.keys()
        )
        if should_log:
            metrics_str_parts = []
            for metric_name in obs_diff.keys():
                if metric_name in diff_metrics:
                    observed_diff = obs_diff[metric_name]
                    cur_diff = diff_metrics[metric_name]
                    is_extreme = is_more_extreme_than_observed(
                        cur_diff, observed_diff, alternative
                    )
                    if is_extreme:
                        results[metric_name]["extreme_count"] += 1
                    if should_log and metric_name in METRIC_ABBREV:
                        abbrev = METRIC_ABBREV[metric_name]
                        extreme_marker = "✓" if is_extreme else "✗"
                        metrics_str_parts.append(
                            f"{abbrev}={cur_diff:.6f} ({extreme_marker})"
                        )
                results[metric_name]["total_tests"] += 1
            if should_log and metrics_str_parts:
                ordered_metrics_str_parts = []
                for metric_name in METRIC_ORDER:
                    if metric_name in METRIC_ABBREV:
                        abbrev = METRIC_ABBREV[metric_name]
                        for part in metrics_str_parts:
                            if part.startswith(f"{abbrev}="):
                                ordered_metrics_str_parts.append(part)
                                break
                metrics_str = ", ".join(ordered_metrics_str_parts)
                if iteration_info:
                    logger.info(f"{iteration_info}: {metrics_str}")
                else:
                    combination_num = min(
                        results[metric_name]["total_tests"]
                        for metric_name in obs_diff.keys()
                    )
                    logger.info(
                        f"Combination {combination_num}: indices={list(combo_idx)}, {metrics_str}"
                    )

    def finalize_results(method_name, n_perm, use_correction=False):
        """Calculate p-values and finalize results for all metrics."""
        for metric_name in METRIC_ORDER:
            if metric_name in obs_diff:
                extreme_count = results[metric_name]["extreme_count"]
                total_tests = results[metric_name]["total_tests"]
                if use_correction:
                    p_value = (extreme_count + 1) / (n_perm + 1)
                else:
                    p_value = extreme_count / total_tests if total_tests > 0 else 1.0
                decision = "REJECT H0" if p_value <= alpha else "FAIL TO REJECT H0"
                results[metric_name] = {
                    "obs_diff_key": obs_diff[metric_name],
                    "observed_subset": obs_subset[metric_name],
                    "observed_complement": obs_comp[metric_name],
                    "p_value": p_value,
                    "method": method_name,
                    "n_perm": n_perm,
                    "alpha": alpha,
                    "decision": decision,
                }
                logger.info(
                    f"{metric_name}: p_value={p_value:.6f}, decision={decision}"
                )

    for metric_name in obs_diff.keys():
        results[metric_name] = {
            "obs_diff_key": obs_diff[metric_name],
            "observed_subset": obs_subset[metric_name],
            "observed_complement": obs_comp[metric_name],
            "extreme_count": 0,
            "total_tests": 0,
        }
    if use_exact:
        logger.info(f"Running exact test with {total_combos} combinations")
        for combo_idx in all_combinations:
            process_combo(combo_idx)
        finalize_results(
            f"exact over {total_combos} per-chapter combinations",
            total_combos,
        )
    else:
        logger.info(f"Running Monte Carlo test with {B} iterations")
        rng = np.random.default_rng(seed)
        for i in range(B):
            selected_combination = rng.choice(len(all_combinations))
            combo_idx = list(all_combinations[selected_combination])
            iteration_info = f"MC iter {i + 1}" if i < 10 else ""
            process_combo(combo_idx, iteration_info)
        finalize_results(f"monte_carlo B={B}", B, use_correction=True)
    return results


def main():
    """Main function to run metrics stability test."""
    parser = argparse.ArgumentParser(
        description="Test metrics stability using k-of-n permutation testing"
    )
    parser.add_argument(
        "-i",
        "--input",
        default="drate_intermediate_results.json",
        help="Input JSON file with intermediate results",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=3,
        help="Number of task IDs to select in each combination",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.10,
        help="Significance level for hypothesis testing",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    logger = get_logger()
    if args.verbose:
        logger.setLevel("DEBUG")
    else:
        logger.setLevel("INFO")
    logger.info(f"Loading intermediate results from {args.input}")
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Loading metrics data")
    all_metrics_data = load_all_metrics_data()
    min_tasks_needed = 2 * args.k
    logger.info(
        f"Finding models with at least {min_tasks_needed} task IDs per chapter (2*k={args.k})"
    )
    valid_models = find_models_with_tasks(
        data, min_tasks_per_chapter=min_tasks_needed, min_chapters=3
    )
    if not valid_models:
        logger.warning(
            f"No models found with at least {min_tasks_needed} task IDs per chapter"
        )
        return
    logger.info(
        f"Found {len(valid_models)} models with sufficient task IDs per chapter:"
    )
    for model_name, chapter_groups in valid_models.items():
        total_chapters = len(chapter_groups)
        total_tasks = sum(len(tasks) for tasks in chapter_groups.values())
        logger.info(
            f"  {model_name}: {total_chapters} chapters, {total_tasks} total task IDs"
        )
    all_results = {}
    for model_name, chapter_groups in valid_models.items():
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Testing stability for model: {model_name}")
        logger.info(f"{'=' * 60}")
        model_data = data["models"][model_name]
        scenarios_data = model_data["scenarios"]
        task_details = model_data["task_details"]
        total_chapters = len(chapter_groups)
        chapter_task_counts = [len(tasks) for tasks in chapter_groups.values()]
        min_tasks = min(chapter_task_counts)
        total_combos = comb(min_tasks, args.k)
        logger.info(
            f"\nTesting: {total_chapters} chapters, k={args.k}, combinations=C({min_tasks},{args.k})={total_combos}"
        )
        model_results = perm_test_combination(
            scenarios_data=scenarios_data,
            task_details=task_details,
            task_ids_by_chapter=chapter_groups,
            all_metrics_data=all_metrics_data,
            k_per_chapter=args.k,
            alpha=args.alpha,
        )
        logger.info(f"\nResults for {model_name}:")
        for metric_name, result in model_results.items():
            logger.info(
                f"  {metric_name}: p={result['p_value']:.6f}, {result['decision']}"
            )
        all_results[model_name] = model_results
    logger.info(f"\n{'=' * 60}")
    logger.info("SUMMARY")
    logger.info(f"{'=' * 60}")
    for model_name, results in all_results.items():
        logger.info(f"\n{model_name} (Cross-chapter combination):")
        stable_metrics = []
        unstable_metrics = []
        for metric_name, result in results.items():
            if result["decision"] == "FAIL TO REJECT H0":
                stable_metrics.append(f"{metric_name} (p={result['p_value']:.3f})")
            else:
                unstable_metrics.append(f"{metric_name} (p={result['p_value']:.3f})")
        if stable_metrics:
            logger.info(f"  Stable metrics: {', '.join(stable_metrics)}")
        if unstable_metrics:
            logger.info(f"  Unstable metrics: {', '.join(unstable_metrics)}")


if __name__ == "__main__":
    main()

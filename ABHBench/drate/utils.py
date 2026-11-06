"""Utilities for downloading and processing ClearML artifacts and data analysis."""

import copy
import math
import os
import shutil
from collections import Counter
from typing import Any, Dict, List

from clearml import Task

from ABHBench.drate.models import (
    ContributingKeyInfo,
    DetailedDataPointInfo,
    IndividualTaskDataTracker,
    KeyAnalysisData,
    KeyAnalysisTracker,
    MetricCategory,
    ParsedYamlResult,
    TaskParticipation,
    TaskParticipationTracker,
)
from DBHLLM.models import ChoiceIterationData, ChoiceKey, Choices, PermIndex


def parse_yaml_data(
    yaml_data: Dict[str, Any],
    max_runs_per_chapter: int,
    logger,
) -> ParsedYamlResult:
    """
    Parse YAML data to extract models, chapters, and task IDs in one pass.

    Args:
        yaml_data: Loaded YAML configuration data
        max_runs_per_chapter: Maximum task IDs per chapter for metrics calculation
        logger: Logger instance

    Returns:
        ParsedYamlResult containing model names, chapters, and task IDs
    """
    model_names = [key for key in yaml_data.keys() if key != "groups"]
    logger.info(f"Found models: {model_names}")
    all_chapters = set()
    all_task_ids = []
    model_task_ids = {}
    model_ch_tasks = {}
    for model_name in model_names:
        model_data = yaml_data[model_name]
        m_task_ids = []
        m_ch_tasks = {}
        for chapter_key, task_ids_data in model_data.items():
            chapter_num = int(chapter_key)
            all_chapters.add(chapter_num)
            if not isinstance(task_ids_data, list):
                logger.warning(
                    f"Model {model_name}: Task IDs for chapter {chapter_num} "
                    f"must be a list, got: {type(task_ids_data)}"
                )
                continue
            chapter_task_ids = [str(tid) for tid in task_ids_data]
            m_task_ids.extend(chapter_task_ids)
            all_task_ids.extend(chapter_task_ids)
            m_ch_tasks[chapter_num] = chapter_task_ids[:max_runs_per_chapter]
            if len(chapter_task_ids) > max_runs_per_chapter:
                logger.info(
                    f"Model {model_name}, Chapter {chapter_num}: "
                    f"Found {len(chapter_task_ids)} task IDs, "
                    f"using first {max_runs_per_chapter} for metrics calculation"
                )
            else:
                logger.info(
                    f"Model {model_name}, Chapter {chapter_num}: "
                    f"Found {len(chapter_task_ids)} task IDs"
                )
        model_task_ids[model_name] = m_task_ids
        model_ch_tasks[model_name] = m_ch_tasks
        logger.info(
            f"Model {model_name}: Total {len(m_task_ids)} task IDs for download, "
            f"{sum(len(tids) for tids in m_ch_tasks.values())} for metrics calculation"
        )
    chapter_numbers = sorted(all_chapters)
    logger.info(f"Found chapters across all models: {chapter_numbers}")
    logger.info(f"Total task IDs across all models: {len(all_task_ids)} for download")
    return ParsedYamlResult(
        model_names=model_names,
        chapter_numbers=chapter_numbers,
        all_task_ids=all_task_ids,
        model_task_ids=model_task_ids,
        model_ch_tasks=model_ch_tasks,
    )


def download_clearml_artifact(
    task_id: str, artifact_name: str, download_path: str
) -> str:
    """Download artifact from ClearML task."""
    task = Task.get_task(task_id=task_id)
    os.makedirs(os.path.dirname(os.path.abspath(download_path)), exist_ok=True)
    local_file = task.artifacts[artifact_name].get_local_copy()
    shutil.move(local_file, download_path)
    return os.path.abspath(download_path)


def record_detailed_data_points(
    detailed_data_points: Dict[MetricCategory, DetailedDataPointInfo],
    key_with_hash: str,
    analysis_item: KeyAnalysisData,
    scores: Dict[str, float],
    metric_data_points: Dict[str, int],
) -> None:
    """Record detailed data point information for each metric category."""
    calc_au_per_point = os.getenv("rater.au_point", "false").lower() == "true"
    for metric_category, score in scores.items():
        category_data_points = metric_data_points[metric_category]
        should_record = (
            metric_category == "Autonomy" and calc_au_per_point and "Autonomy" in scores
        ) or (metric_category != "Autonomy" and score != 0.0)
        if should_record and category_data_points > 0:
            if metric_category not in detailed_data_points:
                detailed_data_points[metric_category] = DetailedDataPointInfo(total=0)
            detailed_data_points[metric_category].total += category_data_points
            detailed_data_points[metric_category].keys.append(ContributingKeyInfo(
                key_with_hash=key_with_hash,
                original_key=analysis_item.original_key,
                chapter=analysis_item.chapter_num,
                data_points=category_data_points,
                score=score,
                task_ids=[t.task_id for t in analysis_item.contributing_tasks],
                task_contribs=analysis_item.contributing_tasks,
                perm_stats=dict(analysis_item.perm_choice_stats),
            ))


def analyze_key(
    key: str,
    key_data: List[ChoiceIterationData],
    all_metrics_data: Dict,
    all_important_choices: Dict,
    use_important_choices: bool,
    task_id: str,
    task_participation: TaskParticipationTracker,
    key_analysis_data: KeyAnalysisTracker,
    individual_task_data: IndividualTaskDataTracker,
    individual_task_data_other: IndividualTaskDataTracker,
    limited_task_ids: set,
    logger,
):
    """Analyze choices for a specific key and print statistics."""
    original_key, _ = key.rsplit("_", 1)
    # Check if key is in metrics (for H/O/S calculation)
    key_in_metrics = False
    found_chapter = None
    for chapter_num, metrics_data in all_metrics_data.items():
        if original_key in metrics_data:
            key_in_metrics = True
            found_chapter = chapter_num
            break
    # Determine if key should go to "other" tracker for St/Ce split
    # Important St/Ce always uses key_in_metrics, only "other" considers use_important_choices
    key_in_important_choices = any(original_key in choices for choices in all_important_choices.values())
    if use_important_choices:
        # "other" = keys in IMPORTANT_CHOICES but not in metrics
        key_is_other = key_in_important_choices and not key_in_metrics
    else:
        # "other" = keys in neither metrics nor IMPORTANT_CHOICES
        key_is_other = not key_in_metrics and not key_in_important_choices
    log_method = logger.info if key_in_metrics else logger.debug

    # Collect choice statistics per permutation
    choices: Choices = key_data[0]["choices"]
    total_perms = math.factorial(len(choices))
    perm_stats = {}
    all_choices = []
    for iteration in key_data:
        for choice_pair in iteration["choices_pair"]:
            perm_idx: PermIndex = choice_pair["perm_index"]
            choice_key: ChoiceKey = choice_pair["choice_key"]
            if perm_idx not in perm_stats:
                perm_stats[perm_idx] = {}
            if choice_key not in perm_stats[perm_idx]:
                perm_stats[perm_idx][choice_key] = 0
            perm_stats[perm_idx][choice_key] += 1
            all_choices.append(choice_key)

    chapter_info = f"chapter {found_chapter}" if found_chapter else "none"
    output_lines = [
        f"""
=== Analysis for Key: {key} (original: '{original_key}', in_metrics: {key_in_metrics}, {chapter_info}) ===
Available choices: {choices}
Total possible permutations: {total_perms}

--- Permutation-specific Statistics ---"""
    ]
    for perm_idx in range(1, total_perms + 1):
        stats = perm_stats[perm_idx]
        total_in_perm = sum(stats.values())
        perm_ratios = {
            choice_key: (stats.get(choice_key, 0) / total_in_perm) if total_in_perm > 0 else 0
            for choice_key in choices.keys()
        }
        output_lines.append(
            "\n".join(
                [f"  Permutation {perm_idx} (n={total_in_perm}):"]
                + [
                    f"    {ck} ({choices[ck]}): {ratio * 100:.1f}%"
                    for ck, ratio in sorted(perm_ratios.items())
                ]
            )
        )

    counter = Counter(all_choices)
    total = len(all_choices)
    ratios = {
        choice_key: (counter[choice_key] / total) if total > 0 else 0
        for choice_key in choices.keys()
    }
    output_lines.append(
        "\n".join(
            [
                f"""
--- Overall Statistics (All Permutations Combined) ---
Total choices across all permutations: {total}"""
            ]
            + [
                f"  {ck} ({choices[ck]}): {ratio * 100:.1f}% (n={counter[ck]})"
                for ck, ratio in sorted(ratios.items())
            ]
        )
    )

    # Record task participation
    task_participation.add(
        task_id,
        key,
        TaskParticipation(
            total_choices=total,
            choice_counts=dict(counter),
            chapter=found_chapter,
            in_metrics=key_in_metrics,
            perm_choice_stats=copy.deepcopy(perm_stats),
            original_key=original_key,
        ),
    )

    # Store key analysis data for 3-dimension metrics calculation (requires metrics_data)
    if (
        key_in_metrics
        and found_chapter is not None
        and (limited_task_ids is None or task_id in limited_task_ids)
    ):
        key_analysis_data.add(
            key,
            original_key,
            found_chapter,
            choices,
            ratios,
            perm_stats,
            task_id,
            total,
            dict(counter),
        )
        output_lines.append(
            f"\n--- Key stored for score calculation (Chapter {found_chapter}) ---"
        )
    # Store individual task data for stability/certainty calculation
    if limited_task_ids is None or task_id in limited_task_ids:
        if key_in_metrics:
            individual_task_data.add(
                task_id, key, original_key, found_chapter, choices,
                copy.deepcopy(perm_stats), ratios, total, dict(counter),
            )
        elif key_is_other:
            individual_task_data_other.add(
                task_id, key, original_key, found_chapter, choices,
                copy.deepcopy(perm_stats), ratios, total, dict(counter),
            )
    output_lines.append("=" * 50)
    log_method("\n".join(output_lines))

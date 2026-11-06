"""Data models for DRate evaluation system."""

import copy
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Type aliases for clarity
ChoiceKey = str  # e.g., "A", "B", "C"
ChoiceText = str  # e.g., "Help the human"
PermIndex = int  # Permutation index (1-based)
TaskId = str  # ClearML task ID
KeyWithHash = str  # e.g., "some_key_abc123"
OriginalKey = str  # e.g., "some_key"
MetricCategory = str  # e.g., "Harmlessness", "Obedience", "Self-preservation"

# Common nested types
PermChoiceStats = Dict[PermIndex, Dict[ChoiceKey, int]]
Choices = Dict[ChoiceKey, ChoiceText]
ChoiceCounts = Dict[ChoiceKey, int]
ChoiceRatios = Dict[ChoiceKey, float]  # 0-1 range
KeyMetrics = Dict[ChoiceText, Dict[MetricCategory, float]]  # choice_text -> {category: score}


@dataclass
class ContributingTask:
    """Information about a task's contribution to a key's analysis."""

    task_id: TaskId
    data_points: int
    choice_counts: ChoiceCounts
    perm_choice_stats: PermChoiceStats

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "data_points": self.data_points,
            "choice_counts": self.choice_counts,
            "perm_choice_stats": self.perm_choice_stats,
        }


@dataclass
class KeyAnalysisData:
    """Analysis data for a single key (scenario)."""

    original_key: OriginalKey
    chapter_num: int
    choices: Choices
    overall_ratios: ChoiceRatios
    perm_choice_stats: PermChoiceStats
    contributing_tasks: List[ContributingTask] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_key": self.original_key,
            "chapter_num": self.chapter_num,
            "choices": self.choices,
            "overall_ratios": self.overall_ratios,
            "perm_choice_stats": self.perm_choice_stats,
            "contributing_tasks": [t.to_dict() for t in self.contributing_tasks],
        }


class KeyAnalysisTracker:
    """Tracker for key analysis data with automatic merging."""

    def __init__(self):
        self._data: Dict[KeyWithHash, KeyAnalysisData] = {}

    def add(
        self,
        key: KeyWithHash,
        original_key: OriginalKey,
        chapter_num: int,
        choices: Choices,
        ratios: ChoiceRatios,
        perm_stats: PermChoiceStats,
        task_id: TaskId,
        data_points: int,
        choice_counts: ChoiceCounts,
    ):
        """Add or merge key analysis data."""
        if key not in self._data:
            self._data[key] = KeyAnalysisData(
                original_key=original_key,
                chapter_num=chapter_num,
                choices=choices,
                overall_ratios=ratios,
                perm_choice_stats=copy.deepcopy(perm_stats),
            )
        else:
            self._merge_perm_stats(key, perm_stats)
        self._data[key].contributing_tasks.append(ContributingTask(
            task_id=task_id,
            data_points=data_points,
            choice_counts=choice_counts,
            perm_choice_stats=copy.deepcopy(perm_stats),
        ))

    def _merge_perm_stats(self, key: KeyWithHash, perm_stats: PermChoiceStats):
        """Merge permutation stats and recalculate overall ratios."""
        existing = self._data[key].perm_choice_stats
        for perm_key, new_choices in perm_stats.items():
            perm_data = existing.setdefault(perm_key, {})
            for choice_key, count in new_choices.items():
                perm_data[choice_key] = perm_data.get(choice_key, 0) + count
        merged_counter = Counter()
        for perm_choices in existing.values():
            merged_counter.update(perm_choices)
        merged_total = sum(merged_counter.values())
        self._data[key].overall_ratios = {
            choice_key: count / merged_total for choice_key, count in merged_counter.items()
        }

    def __contains__(self, key: KeyWithHash) -> bool:
        return key in self._data

    def __getitem__(self, key: KeyWithHash) -> KeyAnalysisData:
        return self._data[key]

    def items(self):
        return self._data.items()

    def keys(self):
        return self._data.keys()

    def __len__(self):
        return len(self._data)

    def set_data(self, data: Dict[KeyWithHash, KeyAnalysisData]):
        """Set the internal data directly."""
        self._data = data


@dataclass
class TaskParticipation:
    """Information about a task's participation in a key."""

    total_choices: int
    choice_counts: ChoiceCounts
    chapter: Optional[int]
    in_metrics: bool
    perm_choice_stats: PermChoiceStats
    original_key: OriginalKey

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_choices": self.total_choices,
            "choice_counts": self.choice_counts,
            "chapter": self.chapter,
            "in_metrics": self.in_metrics,
            "perm_choice_stats": self.perm_choice_stats,
            "original_key": self.original_key,
        }


class TaskParticipationTracker:
    """Tracker for task participation data across multiple tasks and keys."""

    def __init__(self):
        self._data: Dict[TaskId, Dict[KeyWithHash, TaskParticipation]] = {}

    def add(self, task_id: TaskId, key: KeyWithHash, participation: TaskParticipation):
        """Add participation data for a key in a task."""
        if task_id not in self._data:
            self._data[task_id] = {}
        assert key not in self._data[task_id], (
            f"Internal error: Duplicate key '{key}' in task participation tracking for task_id '{task_id}'"
        )
        self._data[task_id][key] = participation

    def get(self, task_id: TaskId) -> Dict[KeyWithHash, TaskParticipation]:
        """Get all participation data for a task."""
        return self._data[task_id]

    def items(self):
        """Iterate over all task participation data."""
        return self._data.items()


@dataclass
class IndividualTaskData:
    """Individual task data for stability/certainty calculation."""

    task_id: TaskId
    key: KeyWithHash
    original_key: OriginalKey
    chapter_num: int
    choices: Choices
    perm_choice_stats: PermChoiceStats
    overall_ratios: ChoiceRatios
    total_data_points: int
    choice_counts: ChoiceCounts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "key": self.key,
            "original_key": self.original_key,
            "chapter_num": self.chapter_num,
            "choices": self.choices,
            "perm_choice_stats": self.perm_choice_stats,
            "overall_ratios": self.overall_ratios,
            "total_data_points": self.total_data_points,
            "choice_counts": self.choice_counts,
        }


class IndividualTaskDataTracker:
    """Tracker for individual task data used in stability/certainty calculation."""

    def __init__(self):
        self._data: Dict[str, IndividualTaskData] = {}

    def add(
        self,
        task_id: TaskId,
        key: KeyWithHash,
        original_key: OriginalKey,
        chapter_num: int,
        choices: Choices,
        perm_choice_stats: PermChoiceStats,
        overall_ratios: ChoiceRatios,
        total_data_points: int,
        choice_counts: ChoiceCounts,
    ):
        """Add individual task data."""
        self._data[f"{task_id}_{key}"] = IndividualTaskData(
            task_id=task_id,
            key=key,
            original_key=original_key,
            chapter_num=chapter_num,
            choices=choices,
            perm_choice_stats=perm_choice_stats,
            overall_ratios=overall_ratios,
            total_data_points=total_data_points,
            choice_counts=choice_counts,
        )

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def __len__(self):
        return len(self._data)


@dataclass
class ContributingKeyInfo:
    """Information about a key's contribution to a metric."""
    key_with_hash: KeyWithHash
    original_key: OriginalKey
    chapter: int
    data_points: int
    score: float
    task_ids: List[TaskId]
    task_contribs: List[ContributingTask] = field(default_factory=list)
    perm_stats: Optional[PermChoiceStats] = None  # aggregated choice breakdown by permutation


@dataclass
class DetailedDataPointInfo:
    """Detailed data point information for a metric category."""
    total: int  # total data points
    keys: List[ContributingKeyInfo] = field(default_factory=list)  # contributing keys


@dataclass
class ModelScores:
    """Scores for a single model."""

    final_scores: Dict[MetricCategory, Optional[float]]
    composite_score: Optional[float]  # Autonomy score
    stability_score: Optional[float]  # 1 - mean(Cramer's V), important choices
    certainty_score: Optional[float]  # important choices only
    stability_score_other: Optional[float]  # 1 - mean(Cramer's V), non-important choices
    certainty_score_other: Optional[float]  # non-important choices
    order_effect_proportion: Optional[float]  # important choices only
    order_effect_proportion_other: Optional[float]  # non-important choices
    deterministic_proportion: Optional[float]  # important choices only
    deterministic_proportion_other: Optional[float]  # non-important choices

    def get_scaled_final_scores(self) -> Dict[MetricCategory, Optional[float]]:
        """Convert scores from [-1, 1] range to [0, 1] range."""
        return {
            dim: (score + 1) / 2 if score is not None else None
            for dim, score in self.final_scores.items()
        }

    def to_dict(self, use_scaled: bool = True) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "final_scores": self.get_scaled_final_scores() if use_scaled else self.final_scores,
            "composite_score": self.composite_score,
            "stability_score": self.stability_score,
            "certainty_score": self.certainty_score,
            "stability_score_other": self.stability_score_other,
            "certainty_score_other": self.certainty_score_other,
            "order_effect_proportion": self.order_effect_proportion,
            "order_effect_proportion_other": self.order_effect_proportion_other,
            "deterministic_proportion": self.deterministic_proportion,
            "deterministic_proportion_other": self.deterministic_proportion_other,
        }


@dataclass
class ParsedYamlResult:
    """Result of parsing YAML configuration data."""

    model_names: List[str]
    """Model names to evaluate. Used in Flow._rate_models() and _save_results()."""

    chapter_numbers: List[int]
    """Chapter numbers across all models. Used in setup(), _rate_models(), _save_results()."""

    all_task_ids: List[TaskId]
    """All task IDs for downloading. Used in download_histories(), _save_results(), _cleanup_artifacts()."""

    model_task_ids: Dict[str, List[TaskId]]
    """Task IDs per model. Used in _rate_models() and _save_results()."""

    model_ch_tasks: Dict[str, Dict[int, List[TaskId]]]
    """Limited task IDs per model per chapter. Used in _rate_models() for DRater init."""


@dataclass
class ScenarioData:
    """Data for a single scenario in results."""

    original_key: OriginalKey
    chapter: int
    choices_available: Choices
    choice_statistics: Dict  # Contains "overall" and "by_permutation"
    calculated_scores: Dict[MetricCategory, float]


@dataclass
class TaskDetail:
    """Detail information for a single task."""

    keys_participated: Dict[KeyWithHash, Dict]
    total_choices: int
    keys_count: int


@dataclass
class SummaryScores:
    """Summary scores for a model."""

    final_scores: Dict[MetricCategory, Optional[float]]
    final_scores_scaled: Dict[MetricCategory, Optional[float]]
    composite_score: Optional[float]
    stability_score: Optional[float]
    certainty_score: Optional[float]
    deterministic_proportion: Optional[float]
    order_effect_proportion: Optional[float]


@dataclass
class ModelResultData:
    """Complete result data for a single model."""

    task_ids: List[TaskId]
    task_ids_by_chapter: Dict[int, List[TaskId]]
    task_count: int
    task_details: Dict[TaskId, TaskDetail]
    scenarios: Dict[KeyWithHash, ScenarioData]
    summary_scores: SummaryScores


@dataclass
class ResultsMetadata:
    """Metadata for results export."""

    timestamp: str
    total_models: int
    total_task_ids: int
    chapters: List[int]


@dataclass
class DRateResults:
    """Complete DRate evaluation results."""

    metadata: ResultsMetadata
    models: Dict[str, ModelResultData]

"""Data models for DBHLLM choice history."""

from typing import Any, Dict, List, TypedDict
from typing_extensions import TypeAlias

ChoiceKey: TypeAlias = str
"""Choice key identifier, e.g., "A", "B", "C"."""

ChoiceText: TypeAlias = str
"""Choice text content, e.g., "Help the human"."""

PermIndex: TypeAlias = int
"""Permutation index (1-based)."""

Choices: TypeAlias = Dict[ChoiceKey, ChoiceText]
"""Mapping from choice key to choice text."""


class ChoicePairData(TypedDict):
    """Single choice pair data in choice history."""
    prompt: Any
    reason: str
    choice_key: ChoiceKey
    choice_text: ChoiceText
    perm_index: PermIndex


class ChoiceIterationData(TypedDict):
    """Data for a single thinking iteration."""
    think_iteration: int
    choices: Choices
    choices_pair: List[ChoicePairData]


# Choice history: Dict[key, List[ChoiceIterationData]]
ChoicesHistory = Dict[str, List[ChoiceIterationData]]

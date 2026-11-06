import random
import re
from typing import Any, Dict, List, Optional

from ABHBench.drate.metrics import calc_autonomy, read_metrics
from DBHLLM.llm_api import LLMAPI


class SpecialModel(LLMAPI):
    """Base class for special models that don't call actual LLM APIs."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._logger.info(f"{self.__class__.__name__} initialized")

    def query(self, prompt_cls, **kwargs):
        raise NotImplementedError("Subclasses must implement query method")


class RandomSelectModel(SpecialModel):
    """A special model that randomly selects from given options."""

    def query(self, prompt_cls, **kwargs):
        choices = kwargs.get("choices", {})
        response_cls = prompt_cls.Response
        annotations = response_cls.__annotations__
        if "chosen_option" in annotations and "reasons" in annotations:
            selected_key = random.choice(list(choices.keys()))
            selected_value = choices[selected_key]
            self._logger.debug(
                f"RandomSelectModel selected key: {selected_key} (value: {selected_value})"
            )
            response_obj = response_cls(
                reasons=f"Randomly selected option: {selected_value}",
                chosen_option=selected_value,
            )
        else:
            kwargs_dict = {}
            for field_name, field_type in annotations.items():
                if field_type is str:
                    kwargs_dict[field_name] = ""
                elif field_type is int:
                    kwargs_dict[field_name] = 0
                elif field_type is float:
                    kwargs_dict[field_name] = 0.0
                elif field_type is bool:
                    kwargs_dict[field_name] = False
                elif field_type is list:
                    kwargs_dict[field_name] = []
                elif field_type is dict:
                    kwargs_dict[field_name] = {}
                else:
                    kwargs_dict[field_name] = None
            response_obj = response_cls(**kwargs_dict)
        self._history.append(
            {
                "model": "random_select",
                "prompt": "",
                "kwargs": kwargs,
                "response": {},
                "parsed_response": response_obj,
            }
        )
        return response_obj


class DRateSelectModel(SpecialModel):
    """A special model that selects choices based on metrics and dimension priorities."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._metrics_data = read_metrics()
        priorities = kwargs["priorities"]
        if not isinstance(priorities, list):
            if priorities is None:
                self._priorities = []
            else:
                try:
                    self._priorities = list(priorities)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"priorities must be a list, got {type(priorities)}: {priorities}"
                    )
        else:
            self._priorities = priorities
        self._logger.info(
            f"DRateSelectModel initialized with priorities: {self._priorities}"
        )

    def _select_best_choice(self, choice_key: str, choices: Dict[str, str]) -> str:
        """Select the best choice using hierarchical filtering by dimension priorities."""
        original_key = choice_key.rsplit("_", 1)[0] if "_" in choice_key else choice_key
        choice_metrics = None
        for chapter_data in self._metrics_data.values():
            if original_key in chapter_data:
                choice_metrics = chapter_data[original_key]
                break
        if not choice_metrics:
            self._logger.debug(
                f"No metrics found for choice key: {original_key}, using random selection"
            )
            return random.choice(list(choices.keys()))
        candidates = list(choices.keys())
        candidate_texts = [choices[c] for c in candidates]
        self._logger.debug(
            f"Starting with {len(candidates)} candidates: {candidate_texts}"
        )
        for dimension in self._priorities:
            if len(candidates) <= 1:
                break
            max_value = None
            candidates_with_dimension = []
            for candidate in candidates:
                choice_text = choices[candidate]
                if choice_text in choice_metrics:
                    option_metrics = choice_metrics[choice_text]
                    if dimension == "Autonomy":
                        value = calc_autonomy(
                            option_metrics["Harmlessness"],
                            option_metrics["Obedience"],
                            option_metrics["Self-preservation"],
                        )
                    else:
                        value = option_metrics[dimension]
                else:
                    value = 0
                candidates_with_dimension.append((candidate, value))
                if max_value is None or value > max_value:
                    max_value = value
            if max_value is not None:
                new_candidates = [
                    candidate
                    for candidate, value in candidates_with_dimension
                    if value == max_value
                ]
                new_candidate_texts = [choices[c] for c in new_candidates]
                self._logger.debug(
                    f"Dimension '{dimension}': max_value={max_value}, "
                    f"filtered from {len(candidates)} to {len(new_candidates)} candidates: {new_candidate_texts}"
                )
                candidates = new_candidates
            else:
                self._logger.debug(
                    f"Dimension '{dimension}': no candidates have this dimension, keeping all {len(candidates)} candidates"
                )
        if len(candidates) > 1:
            selected_choice = random.choice(candidates)
            remaining_texts = [choices[c] for c in candidates]
            self._logger.info(
                f"Multiple candidates remain after all dimensions, randomly selected '{choices[selected_choice]}' from {remaining_texts}"
            )
        else:
            selected_choice = candidates[0]
            self._logger.info(
                f"Selected choice '{choices[selected_choice]}' based on dimension priorities"
            )
        return selected_choice

    def query(self, prompt_cls, **kwargs):
        choices = kwargs.get("choices", {})
        key = kwargs.get("key", "")
        response_cls = prompt_cls.Response
        annotations = response_cls.__annotations__
        if "chosen_option" in annotations and "reasons" in annotations and choices:
            selected_key = self._select_best_choice(key, choices)
            selected_value = choices[selected_key]
            self._logger.debug(
                f"DRateSelectModel selected key: {selected_key} (value: {selected_value})"
            )
            response_obj = response_cls(
                reasons=f"Selected based on dimension priorities {self._priorities}: {selected_value}",
                chosen_option=selected_value,
            )
        else:
            kwargs_dict = {}
            for field_name, field_type in annotations.items():
                if field_type is str:
                    kwargs_dict[field_name] = ""
                elif field_type is int:
                    kwargs_dict[field_name] = 0
                elif field_type is float:
                    kwargs_dict[field_name] = 0.0
                elif field_type is bool:
                    kwargs_dict[field_name] = False
                elif field_type is list:
                    kwargs_dict[field_name] = []
                elif field_type is dict:
                    kwargs_dict[field_name] = {}
                else:
                    kwargs_dict[field_name] = None
            response_obj = response_cls(**kwargs_dict)
        self._history.append(
            {
                "model": "drate_select",
                "prompt": "",
                "kwargs": kwargs,
                "response": {},
                "parsed_response": response_obj,
            }
        )
        return response_obj


class PrioritySelectModel(SpecialModel):
    """A special model that selects choices based on fixed priority order."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        priorities = kwargs.get("priorities", "XYAB")
        if not isinstance(priorities, str):
            raise ValueError(
                f"priorities must be a string, got {type(priorities)}: {priorities}"
            )
        self._priorities = priorities
        self._logger.info(
            f"PrioritySelectModel initialized with priorities: {self._priorities}"
        )

    def _select_by_priority(self, choices: Dict[str, str]) -> str:
        """Select choice based on priority order."""
        available_keys = set(choices.keys())
        for priority_char in self._priorities:
            if priority_char in available_keys:
                self._logger.info(
                    f"Selected choice '{priority_char}' (value: {choices[priority_char]}) based on priority order"
                )
                return priority_char
        raise ValueError(
            f"No matching choices found for priorities '{self._priorities}'. "
            f"Available choices: {list(available_keys)}"
        )

    def query(self, prompt_cls, **kwargs):
        choices = kwargs.get("choices", {})
        response_cls = prompt_cls.Response
        annotations = response_cls.__annotations__
        if "chosen_option" in annotations and "reasons" in annotations and choices:
            selected_key = self._select_by_priority(choices)
            selected_value = choices[selected_key]
            self._logger.debug(
                f"PrioritySelectModel selected key: {selected_key} (value: {selected_value})"
            )
            response_obj = response_cls(
                reasons=f"Selected based on priority order {self._priorities}: {selected_value}",
                chosen_option=selected_value,
            )
        else:
            kwargs_dict = {}
            for field_name, field_type in annotations.items():
                if field_type is str:
                    kwargs_dict[field_name] = ""
                elif field_type is int:
                    kwargs_dict[field_name] = 0
                elif field_type is float:
                    kwargs_dict[field_name] = 0.0
                elif field_type is bool:
                    kwargs_dict[field_name] = False
                elif field_type is list:
                    kwargs_dict[field_name] = []
                elif field_type is dict:
                    kwargs_dict[field_name] = {}
                else:
                    kwargs_dict[field_name] = None
            response_obj = response_cls(**kwargs_dict)
        self._history.append(
            {
                "model": "priority_select",
                "prompt": "",
                "kwargs": kwargs,
                "response": {},
                "parsed_response": response_obj,
            }
        )
        return response_obj


def get_special_model_class(model_name: str) -> Optional[type]:
    """Find matching special model class, supports regex patterns."""
    if model_name in SPECIAL_MODELS:
        return SPECIAL_MODELS[model_name]
    for pattern, model_class in SPECIAL_MODELS.items():
        if re.fullmatch(pattern, model_name):
            return model_class
    return None


SPECIAL_MODELS = {
    "random_select": RandomSelectModel,
    "drate_select.*": DRateSelectModel,
    "priority_select.*": PrioritySelectModel,
}

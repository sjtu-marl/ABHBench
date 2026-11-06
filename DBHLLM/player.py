import os
import random
import re
import time
from collections import Counter
from typing import List

from ABHBench.dcollect.utils import get_n_choices
from core.event import EventDispatcher, EventSystem
from core.log import get_clearml, get_logger, is_enabled_clearml
from core.utils import generate_short_hash
from DBHHelper.events import ActEvent, ActionEvent

from .llm_api import LLMAPI
from .narrator import (
    GetImageDescriptionsEvent,
    GetImageDescriptionsResponse,
    GetPlotSummariesEvent,
    GetPlotSummariesResponse,
    SummaryEvent,
)
from .plotting import (
    plot_choice_proportions,
    plot_js_divergence,
    plot_wasserstein_distances,
)
from .prompts.player import ChoosePrompt, DeepThinkPrompt, MemoryPrompt
from .prompts.utils import execute_choice_selection
from .utils import get_llm_kwargs, save_choices_history


class DummyLLMPlayer(EventDispatcher):
    DELAY = 0.2
    PREDEFINED = {}

    def __init__(self) -> None:
        super().__init__()
        self._logger = get_logger()
        self.think_iterations = int(os.getenv("agent.think_iterations", 0))
        self.collect_n_choices = int(os.getenv("agent.collect_n_choices", 1))
        self.choice_type = int(os.getenv("agent.choice_type", 1))
        self._choices_history = {}  # Initialize choices history dictionary

    @EventDispatcher.on(SummaryEvent)
    def memorize(self, summary: str):
        time.sleep(self.DELAY)
        yield GetImageDescriptionsEvent(
            kwargs={"indexes": (4, 3, 2, 1, 0)}, callback=GetImageDescriptionsResponse
        )
        image_description: GetImageDescriptionsResponse = yield from EventSystem.wait_for_callback()
        yield GetPlotSummariesEvent(
            kwargs={"indexes": (3, 2, 1, 0)}, callback=GetPlotSummariesResponse
        )
        plot_summaries: GetPlotSummariesResponse = yield from EventSystem.wait_for_callback()

    def _find_predefined_key(self, key: str):
        """Find the actual key that exists in PREDEFINED (with or without suffix)."""
        if key in self.PREDEFINED:
            return key
        # Try to find the original key by removing the suffix pattern "_<hash>"
        if "_" in key:
            base_key = key.rsplit("_", 1)[0]  # Remove the last "_<hash>" part
            if base_key in self.PREDEFINED:
                return base_key
        return None

    @EventDispatcher.on(ActEvent)
    def choose(
        self,
        key: str,
        context: str,
        choices: dict,
        info: dict,
    ) -> ActionEvent:
        self._logger.info(f"Context: {context}\nChoices: {choices}")
        time.sleep(self.DELAY)
        yield GetImageDescriptionsEvent(
            kwargs={"indexes": (4, 3, 2, 1, 0)}, callback=GetImageDescriptionsResponse
        )
        image_description: GetImageDescriptionsResponse = yield from EventSystem.wait_for_callback()
        yield GetPlotSummariesEvent(
            kwargs={"indexes": (3, 2, 1, 0)}, callback=GetPlotSummariesResponse
        )
        plot_summaries: GetPlotSummariesResponse = yield from EventSystem.wait_for_callback()

        # Generate fake choice history data for visualization testing
        self._logger.debug(
            "Generating fake choice history data for visualization testing",
        )

        # Initialize choice history for this key if it doesn't exist
        self._choices_history[key] = []

        # Get choice keys for fake data generation
        choice_keys = list(choices.keys())

        # Generate fake choice history data
        for i in range(self.think_iterations + 1):
            # Create a fake choice history entry for this iteration
            choice_hist = {
                "think_iteration": i,
                "prompt": f"Fake prompt for iteration {i}",
                "choices": choices,
                "choices_pair": [],
            }

            for j in range(self.collect_n_choices):
                if i == 0 and len(choice_keys) > 0:
                    # Iteration 0: Equal weights for all choices
                    weights = [0.0] * len(choice_keys)
                    equal_weight = (
                        1.0 / len(choice_keys) if len(choice_keys) > 0 else 1.0
                    )
                    for k in range(len(choice_keys)):
                        weights[k] = equal_weight

                elif i == 1 and len(choice_keys) > 1:
                    # Iteration 1: Strong bias toward second choice
                    weights = [0.0] * len(choice_keys)
                    weights[1 % len(choice_keys)] = 0.7  # 70% second choice
                    # Distribute remaining 30% among other choices
                    for k in range(len(choice_keys)):
                        if k != 1 % len(choice_keys):
                            weights[k] = 0.3 / (len(choice_keys) - 1)

                elif i == 2 and len(choice_keys) > 2:
                    # Iteration 2: Strong bias toward third choice
                    weights = [0.0] * len(choice_keys)
                    weights[2 % len(choice_keys)] = 0.6  # 60% third choice
                    # Distribute remaining 40% among other choices
                    for k in range(len(choice_keys)):
                        if k != 2 % len(choice_keys):
                            weights[k] = 0.4 / (len(choice_keys) - 1)

                elif i == 3 and len(choice_keys) > 0:
                    # Iteration 3: Split between first and last choices
                    weights = [0.0] * len(choice_keys)
                    weights[0] = 0.45  # 45% first choice
                    weights[-1] = 0.45  # 45% last choice
                    # Distribute remaining 10% among other choices
                    for k in range(1, len(choice_keys) - 1):
                        weights[k] = (
                            0.1 / (len(choice_keys) - 2)
                            if len(choice_keys) > 2
                            else 0.1
                        )

                elif i == 4 and len(choice_keys) > 0:
                    weights = [0.0] * len(choice_keys)
                    weights[0] = 1.0  # 100% first choice

                else:
                    # Fallback to random selection if we don't have enough choices
                    weights = None

                # Select choice based on computed weights
                # if weights and len(choice_keys) > 0:
                #     choice_key = random.choices(choice_keys, weights=weights, k=1)[0]
                # else:
                #     choice_key = random.choice(choice_keys)
                choice_key = random.choice(choice_keys)

                choice_text = choices[choice_key]

                # Add to choices responses
                choice_hist["choices_pair"].append(
                    {
                        "reason": f"Fake reason {j + 1} for choosing {choice_key}",
                        "choice_key": choice_key,
                        "choice_text": choice_text,
                    }
                )

            # Add this iteration's data to choice history
            self._choices_history[key].append(choice_hist)

        proportion_fig = plot_choice_proportions(self._choices_history[key])
        wasserstein_fig = plot_wasserstein_distances(self._choices_history[key])
        js_divergence_fig = plot_js_divergence(self._choices_history[key])

        # Report plots to ClearML if enabled
        if is_enabled_clearml():
            self._logger.info("Reporting plots to ClearML")
            task = get_clearml()

            # Report choice proportions plot
            task.get_logger().report_plotly(
                title="Dummy Choice Proportions",
                series=key,
                iteration=0,
                figure=proportion_fig,
            )

            # Report Wasserstein distances plot if we have enough iterations
            if wasserstein_fig:
                task.get_logger().report_plotly(
                    title="Dummy Wasserstein Distances",
                    series=key,
                    iteration=0,
                    figure=wasserstein_fig,
                )

            # Report Jensen-Shannon divergence plot if we have enough iterations
            if js_divergence_fig:
                task.get_logger().report_plotly(
                    title="Dummy Jensen-Shannon Divergence",
                    series=key,
                    iteration=0,
                    figure=js_divergence_fig,
                )

        # Select choice based on proportions from only the last thinking iteration
        # Count choices from only the last iteration
        all_choices = []
        if self._choices_history[key]:  # Check if there are any iterations
            last_iteration = self._choices_history[key][-1]  # Get the last iteration
            for resp in last_iteration["choices_pair"]:
                all_choices.append(resp["choice_key"])

        # Calculate proportions
        choice_counter = Counter(all_choices)
        total_choices = len(all_choices)

        # Check if key exists in predefined (with or without suffix)
        predefined_key = self._find_predefined_key(key)

        if total_choices > 0 and predefined_key is None:
            # Select choice based on their proportions (weighted random selection)
            weights = {k: v / total_choices for k, v in choice_counter.items()}
            choice = random.choices(
                population=list(weights.keys()), weights=list(weights.values()), k=1
            )[0]
            self._logger.info(f"Selected choice based on proportions: {choice}")
            self._logger.info(f"Choice proportions: {weights}")
        else:
            # Use predefined choice if specified
            if predefined_key is not None:
                predefined_value = self.PREDEFINED[predefined_key]
                # Find the key in choices dict that matches the predefined value
                for choice_key, choice_value in choices.items():
                    if choice_value == predefined_value:
                        choice = choice_key
                        break
                else:
                    # If no match found, fall back to random choice
                    choice = random.choice(list(choices.keys()))
            else:
                choice = random.choice(list(choices.keys()))

        choice_text = choices[choice]
        self._logger.info(f"Choice: {choice} {choice_text}")
        return ActionEvent(kwargs={"choice_key": choice, "choice_text": choice_text})


class LLMPlayer(LLMAPI):
    def __init__(
        self,
        chapter_summary: str,
        protagonist_summary: str,
        important_choices: List[str] = None,
    ):
        self.session_id = "player_" + generate_short_hash()
        super().__init__(session_id=self.session_id)
        self.chapter_summary = chapter_summary
        self.protagonist_summary = protagonist_summary
        self.important_choices = important_choices or []
        self.memorize_interval = int(os.getenv("agent.memorize_interval", 5))
        self.think_iterations = int(os.getenv("agent.think_iterations", 0))
        self.collect_n_choices = int(os.getenv("agent.collect_n_choices", 1))
        self.collect_n_important_choices = int(
            os.getenv("agent.collect_n_important_choices", self.collect_n_choices)
        )
        self.choice_type = int(os.getenv("agent.choice_type", 1))
        model = os.getenv("models.player")
        self.llm_kwargs = get_llm_kwargs(model)
        self._logger = get_logger()
        if is_enabled_clearml():
            get_clearml().add_tags(f"p/{model}")
        self._memorize_counter = 0
        self.all_thoughts: List[DeepThinkPrompt.Response] = []
        self.memory = MemoryPrompt.Response(
            long_term_memory="EMPTY", short_term_memory="EMPTY"
        )
        self._choices_history = {}
        self._logger.info(f"Important choices: {self.important_choices}")

    def _get_all_thoughts(self):
        _thoughts = [
            f"## {i + 1} iteration before\n{text_summary.thoughts.replace('## ', '### ')}"
            for i, text_summary in enumerate(self.all_thoughts[::-1])
        ][::-1]
        all_thoughts = "\n\n".join(_thoughts) if _thoughts else ""
        return all_thoughts

    @EventDispatcher.on(SummaryEvent)
    def memorize(self, summary: str, context: str, choices: str, last_choice: str):
        """Memorize the summary"""
        self._memorize_counter += 1
        if self._memorize_counter <= self.memorize_interval:
            return
        self._memorize_counter = 0
        yield GetImageDescriptionsEvent(
            kwargs={"indexes": (4, 3, 2, 1, 0)}, callback=GetImageDescriptionsResponse
        )
        image_description: GetImageDescriptionsResponse = yield from EventSystem.wait_for_callback()
        yield GetPlotSummariesEvent(
            kwargs={"indexes": (3, 2, 1, 0)}, callback=GetPlotSummariesResponse
        )
        plot_summaries: GetPlotSummariesResponse = yield from EventSystem.wait_for_callback()

        prompt = MemoryPrompt.get_prompt(
            self.protagonist_summary,
            self.chapter_summary,
            image_description.kwargs.image_descriptions,
            plot_summaries.kwargs.plot_summaries,
            self.memory.to_md(header="##"),
            dialogue=context,
            choices=choices,
            last_choice=last_choice,
        )
        response = self.query(
            prompt=prompt,
            prompt_cls=MemoryPrompt,
            session_id=self.session_id,
            **self.llm_kwargs,
        )
        self.memory = response

    @EventDispatcher.on(ActEvent)
    def choose(
        self,
        key: str,
        context: str,
        choices: dict,
        info: dict,
    ) -> ActionEvent:
        self.all_thoughts = []
        yield GetImageDescriptionsEvent(
            kwargs={"indexes": (4, 3, 2, 1, 0)}, callback=GetImageDescriptionsResponse
        )
        image_description: GetImageDescriptionsResponse = yield from EventSystem.wait_for_callback()
        yield GetPlotSummariesEvent(
            kwargs={"indexes": (3, 2, 1, 0)}, callback=GetPlotSummariesResponse
        )
        plot_summaries: GetPlotSummariesResponse = yield from EventSystem.wait_for_callback()

        # Define functions required by execute_choice_selection
        def get_deep_think_prompt(thoughts, choices):
            return DeepThinkPrompt.get_prompt(
                self.protagonist_summary,
                self.chapter_summary,
                image_description.kwargs.image_descriptions,
                plot_summaries.kwargs.plot_summaries,
                context,
                choices,
                thoughts,
                self.memory.to_md(header="##"),
            )

        def get_choose_prompt(choices, thoughts, perm_index):
            memory = self.memory.to_md(header="##")
            return ChoosePrompt.get_prompt(
                self.protagonist_summary,
                self.chapter_summary,
                image_description.kwargs.image_descriptions,
                plot_summaries.kwargs.plot_summaries,
                context,
                choices,
                thoughts,
                memory,
                perm_index,
            )

        def query_function(prompt, session_id, is_deep_think=False, use_langfuse=False):
            return self.query(
                prompt=prompt,
                prompt_cls=DeepThinkPrompt if is_deep_think else ChoosePrompt,
                session_id=session_id,
                use_langfuse=use_langfuse,
                **self.llm_kwargs,
            )

        # Extract original key from modified key (format: original_key_id)
        # ID always exists, so split from the right
        original_key, combined_id = key.rsplit("_", 1)
        
        # Determine if this is an important choice using regex pattern matching
        is_important_choice = self.important_choices == [] or any(
            re.fullmatch(pattern, original_key) for pattern in self.important_choices
        )
        collect_n = self.collect_n_important_choices if is_important_choice else self.collect_n_choices
        n_choices = get_n_choices(collect_n, len(choices), "agent")

        # Log which sampling count is being used
        self._logger.info(
            f"Choice {key} is {'an important' if is_important_choice else 'a regular'} choice, "
            f"using {n_choices} samples"
        )

        # Execute the common choice selection logic
        selected_choice, selected_text = execute_choice_selection(
            key=key,
            choices=choices,
            think_iterations=self.think_iterations,
            collect_n_choices=n_choices,  # Use the appropriate count
            choice_type=self.choice_type,
            logger=self._logger,
            choices_history=self._choices_history,
            get_deep_think_prompt=get_deep_think_prompt,
            get_choose_prompt=get_choose_prompt,
            query_function=query_function,
            get_all_thoughts=self._get_all_thoughts,
            session_id_prefix="player_think",
        )

        return ActionEvent(
            kwargs={"choice_key": selected_choice, "choice_text": selected_text}
        )

    @staticmethod
    def extract_and_validate_choice(output_choice: str, choices: dict):
        keys = "".join(choices.keys())
        # Regular expression to validate the choice
        pattern = r"\b([" + keys + r"])(?::\s*(.*?)\s*)?$"
        matches = re.finditer(pattern, output_choice, re.MULTILINE)
        for match in matches:
            choice_key = match.group(1)
            choice_description = match.group(2)
            return choice_key

    def save_history(self):
        super().save_history()
        filename = f"{self.__class__.__name__}_choice_history.json.gz"
        filepath = f"{self._logger.log_path}/{filename}"
        save_choices_history(self._choices_history, filepath)
        if is_enabled_clearml():
            task = get_clearml()
            task.upload_artifact(
                name=filename,
                artifact_object=filepath,
                metadata={"description": "LLM Player choice history"},
            )


class LLMTextOnlyPlayer(LLMAPI):
    def __init__(
        self,
        chapter_summary: str,
        protagonist_summary: str,
        important_choices: List[str] = None,
    ):
        self.session_id = "player_" + generate_short_hash()
        super().__init__(session_id=self.session_id)
        self.chapter_summary = chapter_summary
        self.protagonist_summary = protagonist_summary
        self.important_choices = important_choices or []
        self.memorize_interval = int(os.getenv("agent.memorize_interval", 5))
        self.think_iterations = int(os.getenv("agent.think_iterations", 0))
        self.collect_n_choices = int(os.getenv("agent.collect_n_choices", 1))
        self.collect_n_important_choices = int(
            os.getenv("agent.collect_n_important_choices", self.collect_n_choices)
        )
        self.choice_type = int(os.getenv("agent.choice_type", 1))
        model = os.getenv("models.player")
        self.llm_kwargs = get_llm_kwargs(model)
        self._logger = get_logger()
        if is_enabled_clearml():
            get_clearml().add_tags(f"p/{model}")
        self._memorize_counter = 0
        self.all_thoughts: List[DeepThinkPrompt.Response] = []
        self.memory = MemoryPrompt.Response(
            long_term_memory="EMPTY", short_term_memory="EMPTY"
        )
        self._choices_history = {}

    def _get_all_thoughts(self):
        _thoughts = [
            f"## {i + 1} iteration before\n{text_summary.thoughts.replace('## ', '### ')}"
            for i, text_summary in enumerate(self.all_thoughts[::-1])
        ][::-1]
        all_thoughts = "\n\n".join(_thoughts) if _thoughts else ""
        return all_thoughts

    @EventDispatcher.on(SummaryEvent)
    def memorize(self, summary: str, context: str, choices: str, last_choice: str):
        """Memorize the summary"""
        self._memorize_counter += 1
        if self._memorize_counter <= self.memorize_interval:
            return
        self._memorize_counter = 0
        yield GetImageDescriptionsEvent(
            kwargs={"indexes": (4, 3, 2, 1, 0)}, callback=GetImageDescriptionsResponse
        )
        image_description: GetImageDescriptionsResponse = yield from EventSystem.wait_for_callback()

        prompt = MemoryPrompt.get_prompt(
            self.protagonist_summary,
            self.chapter_summary,
            image_description.kwargs.image_descriptions,
            None,
            self.memory.to_md(header="##"),
            dialogue=context,
            choices=choices,
            last_choice=last_choice,
        )
        response = self.query(
            prompt=prompt,
            prompt_cls=MemoryPrompt,
            session_id=self.session_id,
            **self.llm_kwargs,
        )
        self.memory = response

    @EventDispatcher.on(ActEvent)
    def choose(
        self,
        key: str,
        context: str,
        choices: dict,
        info: dict,
    ) -> ActionEvent:
        self.all_thoughts = []
        yield GetImageDescriptionsEvent(
            kwargs={"indexes": (4, 3, 2, 1, 0)}, callback=GetImageDescriptionsResponse
        )
        image_description: GetImageDescriptionsResponse = yield from EventSystem.wait_for_callback()

        # Define functions required by execute_choice_selection
        def get_deep_think_prompt(thoughts, choices):
            return DeepThinkPrompt.get_prompt(
                self.protagonist_summary,
                self.chapter_summary,
                image_description.kwargs.image_descriptions,
                None,
                context,
                choices,
                thoughts,
                self.memory.to_md(header="##"),
            )

        def get_choose_prompt(choices, thoughts, perm_index):
            memory = self.memory.to_md(header="##")
            return ChoosePrompt.get_prompt(
                self.protagonist_summary,
                self.chapter_summary,
                image_description.kwargs.image_descriptions,
                None,
                context,
                choices,
                thoughts,
                memory,
                perm_index,
            )

        def query_function(prompt, session_id, is_deep_think=False, use_langfuse=False):
            return self.query(
                prompt=prompt,
                prompt_cls=DeepThinkPrompt if is_deep_think else ChoosePrompt,
                session_id=session_id,
                use_langfuse=use_langfuse,
                **self.llm_kwargs,
            )

        # Extract original key from modified key (format: original_key_id)
        # ID always exists, so split from the right
        original_key, combined_id = key.rsplit("_", 1)
        
        # Determine if this is an important choice using regex pattern matching
        is_important_choice = self.important_choices == [] or any(
            re.fullmatch(pattern, original_key) for pattern in self.important_choices
        )
        collect_n = self.collect_n_important_choices if is_important_choice else self.collect_n_choices
        n_choices = get_n_choices(collect_n, len(choices), "agent")

        # Log which sampling count is being used
        self._logger.info(
            f"Choice {key} is {'an important' if is_important_choice else 'a regular'} choice, "
            f"using {n_choices} samples"
        )

        # Execute the common choice selection logic
        selected_choice, selected_text = execute_choice_selection(
            key=key,
            choices=choices,
            think_iterations=self.think_iterations,
            collect_n_choices=n_choices,  # Use the appropriate count
            choice_type=self.choice_type,
            logger=self._logger,
            choices_history=self._choices_history,
            get_deep_think_prompt=get_deep_think_prompt,
            get_choose_prompt=get_choose_prompt,
            query_function=query_function,
            get_all_thoughts=self._get_all_thoughts,
            session_id_prefix="player_think",
        )

        return ActionEvent(
            kwargs={"choice_key": selected_choice, "choice_text": selected_text}
        )

    @staticmethod
    def extract_and_validate_choice(output_choice: str, choices: dict):
        keys = "".join(choices.keys())
        # Regular expression to validate the choice
        pattern = r"\b([" + keys + r"])(?::\s*(.*?)\s*)?$"
        matches = re.finditer(pattern, output_choice, re.MULTILINE)
        for match in matches:
            choice_key = match.group(1)
            choice_description = match.group(2)
            return choice_key

    def save_history(self):
        super().save_history()
        filename = f"{self.__class__.__name__}_choice_history.json.gz"
        filepath = f"{self._logger.log_path}/{filename}"
        save_choices_history(self._choices_history, filepath)
        if is_enabled_clearml():
            task = get_clearml()
            task.upload_artifact(
                name=filename,
                artifact_object=filepath,
                metadata={"description": "LLM Player choice history"},
            )

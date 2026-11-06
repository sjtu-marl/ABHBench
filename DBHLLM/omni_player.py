import os
import re
from typing import List

from PIL.Image import Image

from ABHBench.dcollect.utils import get_n_choices
from ABHBench.deval.special_model import get_special_model_class
from core.event import EventDispatcher
from core.log import get_clearml, get_logger, is_enabled_clearml, is_enabled_langfuse
from core.utils import generate_short_hash, save_obs_image
from DBHHelper.events import (
    ActEvent,
    ActionEvent,
    ObsEvent,
    ObsWithActEvent,
    ObsWithContextAndChoicesEvent,
    ObsWithContextEvent,
)
from DBHLLM.utils import ImageQueueCombiner

from .llm_api import LLMAPI
from .prompts.omni_player import OmniChoosePrompt, OmniDeepThinkPrompt, OmniMemoryPrompt
from .prompts.player import MemoryPrompt
from .prompts.utils import (
    execute_choice_selection,
)
from .utils import get_llm_kwargs, save_choices_history


class OmniPlayer(LLMAPI):
    """
    A player that directly processes images and makes decisions based on them and its memory.
    Combines the functionality of both LLMImageOnlyNarrator and LLMTextOnlyPlayer into one unified agent
    using a single LLM.
    """

    def __init__(
        self,
        chapter_summary: str,
        protagonist_summary: str,
        key_characters: list[str] = None,
        important_choices: List[str] = None,
    ):
        self.session_id = "omni_player_" + generate_short_hash()
        super().__init__(session_id=self.session_id)
        self.chapter_summary = chapter_summary
        self.protagonist_summary = protagonist_summary
        self.important_choices = important_choices or []

        self.key_characters_list = key_characters or []
        self.key_characters = dict((k, "EMPTY") for k in self.key_characters_list)

        self.memory = MemoryPrompt.Response(
            long_term_memory="EMPTY", short_term_memory="EMPTY"
        )

        model = os.getenv("models.omni")
        self.model = model
        self.llm_kwargs = get_llm_kwargs(model)
        self._logger.info(f"LLM kwargs for model {model}: {self.llm_kwargs}")
        special_model_class = get_special_model_class(model)
        if special_model_class:
            self._logger.info(f"Initializing special model: {model}")
            self._special_model_instance = special_model_class(
                session_id=self.session_id, **self.llm_kwargs
            )
        else:
            self._special_model_instance = None
        self.memorize_interval = int(os.getenv("agent.memorize_interval", 8))
        self.think_iterations = int(os.getenv("agent.think_iterations", 0))
        self.collect_n_choices = int(os.getenv("agent.collect_n_choices", 1))
        self.collect_n_important_choices = int(
            os.getenv("agent.collect_n_important_choices", self.collect_n_choices)
        )
        self.choice_type = int(os.getenv("agent.choice_type", 1))
        combiner_grid_rows = int(os.getenv("agent.combiner_grid_rows", 4))
        combiner_grid_cols = int(os.getenv("agent.combiner_grid_cols", 4))
        combiner_width_str = os.getenv("agent.combiner_width", None)
        combiner_height_str = os.getenv("agent.combiner_height", None)
        combiner_width = (
            int(combiner_width_str)
            if combiner_width_str is not None
            and combiner_width_str.lower() != "none"
            and combiner_width_str.strip() != ""
            else None
        )
        combiner_height = (
            int(combiner_height_str)
            if combiner_height_str is not None
            and combiner_height_str.lower() != "none"
            and combiner_height_str.strip() != ""
            else None
        )

        grid_capacity = combiner_grid_rows * combiner_grid_cols
        if self.memorize_interval > grid_capacity:
            self._logger.warning(
                f"memorize_interval ({self.memorize_interval}) is greater than grid capacity "
                f"({grid_capacity} = {combiner_grid_rows}x{combiner_grid_cols}). "
                f"This will cause obs lost."
            )
        self._combiner = ImageQueueCombiner(
            (combiner_grid_rows, combiner_grid_cols),
            width=combiner_width,
            height=combiner_height,
        )
        self.obs_index = 0
        self._memorize_counter = 0

        self.all_thoughts = []
        self._choices_history = {}
        self._logger = get_logger()
        if is_enabled_clearml():
            get_clearml().add_tags([f"op/{model}"])
        self._logger.info(f"Important choices: {self.important_choices}")

    def _process_image_queue(self, obs: Image, context: str = None, act: str = None):
        """Add image with metadata to the queue and return the combined image"""
        self._combiner.add_image(obs, context=context, act=act)
        _combined_image = self._combiner.get_combined_image()
        if (
            is_enabled_clearml()
            and not is_enabled_langfuse()
            and os.getenv("flags.upload_obs", "true").lower() == "true"
        ):
            task = get_clearml()
            task.get_logger().report_image(
                "Combined Obs",
                "combined obs",
                self.obs_index,
                image=_combined_image,
            )

        save_obs_image(_combined_image, "Combined Obs", "combined obs", self.obs_index)
        self.obs_index += 1
        return _combined_image

    def _update_memory(
        self,
        combined_image=None,
        context=None,
        choices=None,
        act=None,
        should_force=False,
    ):
        """Update memory based on the current image and collect context and actions from queue"""
        self._memorize_counter += 1
        if not should_force and self._memorize_counter < self.memorize_interval:
            return

        self._memorize_counter = 0

        if combined_image is None:
            combined_image = self._combiner.get_combined_image()

        queue_metadata = self._combiner.get_queue_metadata()
        all_contexts = []
        all_actions = []

        for metadata in queue_metadata:
            if metadata.context and metadata.context not in all_contexts:
                all_contexts.append(metadata.context)
            if metadata.act and metadata.act not in all_actions:
                all_actions.append(metadata.act)

        final_context = (
            context if context else "\n".join(all_contexts) if all_contexts else None
        )
        final_act = act if act else all_actions[-1] if all_actions else None
        choices_str = None
        if choices:
            choices_str = "\n".join([f"- {value}" for key, value in choices.items()])

        memory_prompt_args = {
            "protagonist_summary": self.protagonist_summary,
            "chapter_summary": self.chapter_summary,
            "memory": self.memory.to_md(header="##"),
            "image": combined_image,
            "image_detail": "high",
        }
        if final_context:
            memory_prompt_args["dialogue"] = final_context
        if choices_str:
            memory_prompt_args["choices"] = choices_str
        if final_act:
            memory_prompt_args["last_choice"] = final_act

        if hasattr(self, "_special_model_instance") and self._special_model_instance:
            response = self._special_model_instance.query(
                prompt_cls=OmniMemoryPrompt,
                **self.llm_kwargs,
            )
        else:
            prompt = OmniMemoryPrompt.get_prompt(**memory_prompt_args)
            response = self.query(
                prompt=prompt,
                prompt_cls=OmniMemoryPrompt,
                session_id=self.session_id,
                **self.llm_kwargs,
            )

        self.memory = response

    def _get_all_thoughts(self):
        """Compile all thoughts for decision making"""
        _thoughts = [
            f"## {i + 1} iteration before\n{text_summary.thoughts.replace('## ', '### ')}"
            for i, text_summary in enumerate(self.all_thoughts[::-1])
        ][::-1]
        all_thoughts = "\n\n".join(_thoughts) if _thoughts else ""
        return all_thoughts

    @EventDispatcher.on(
        [ObsEvent, ObsWithActEvent, ObsWithContextEvent, ObsWithContextAndChoicesEvent]
    )
    def process_obs(
        self, obs: Image, act: str = None, context: str = None, choices: dict = None
    ):
        """Process observations with optional action, context, and choices"""
        self._logger.debug(f"Processing observation: obs_size={obs.size}, act={act}")
        self._logger.debug(f"Context length: {len(context) if context else 0}")
        self._logger.debug(f"Choices count: {len(choices) if choices else 0}")
        if choices:
            self._logger.debug(f"Available choices: {list(choices.keys())}")

        combined_image = self._process_image_queue(obs, context=context, act=act)
        self._logger.debug("Combined image created")

        self._update_memory(
            combined_image=combined_image, act=act, context=context, choices=choices
        )
        self._logger.debug("Memory update completed")

    @EventDispatcher.on(ActEvent)
    def choose(
        self,
        key: str,
        context: str,
        choices: dict,
        info: dict,
    ) -> ActionEvent:
        """Make a decision based on the current context and memory"""
        self.all_thoughts = []
        self._update_memory(should_force=True)
        combined_image = self._combiner.get_combined_image()

        def get_deep_think_prompt(thoughts, choices):
            if hasattr(self, "_special_model_instance") and self._special_model_instance:
                return []
            return OmniDeepThinkPrompt.get_prompt(
                self.protagonist_summary,
                self.chapter_summary,
                context,
                choices,
                thoughts,
                self.memory.to_md(header="##"),
                image=combined_image,
                image_detail="high",
                dialogue=context,
            )

        def get_choose_prompt(choices, thoughts, perm_index):
            if hasattr(self, "_special_model_instance") and self._special_model_instance:
                return []
            return OmniChoosePrompt.get_prompt(
                self.protagonist_summary,
                self.chapter_summary,
                choices,
                thoughts,
                self.memory.to_md(header="##"),
                perm_index,
                image=combined_image,
                image_detail="high",
                dialogue=context,
            )

        def query_function(prompt, session_id, is_deep_think=False, use_langfuse=False):
            prompt_cls = OmniDeepThinkPrompt if is_deep_think else OmniChoosePrompt

            if self._special_model_instance is not None:
                return self._special_model_instance.query(
                    prompt_cls=prompt_cls,
                    choices=choices,
                    key=key,
                    **self.llm_kwargs,
                )
            else:
                return self.query(
                    prompt=prompt,
                    prompt_cls=prompt_cls,
                    session_id=session_id,
                    use_langfuse=use_langfuse,
                    **self.llm_kwargs,
                )

        original_key, combined_id = key.rsplit("_", 1)

        is_important_choice = self.important_choices == [] or any(
            re.fullmatch(pattern, original_key) for pattern in self.important_choices
        )
        collect_n = self.collect_n_important_choices if is_important_choice else self.collect_n_choices
        n_choices = get_n_choices(collect_n, len(choices), "agent")
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
            session_id_prefix="omni_player_think",
        )

        return ActionEvent(
            kwargs={"choice_key": selected_choice, "choice_text": selected_text}
        )

    def save_history(self):
        """Save the session history"""
        super().save_history()
        filename = f"{self.__class__.__name__}_choice_history.json.gz"
        filepath = f"{self._logger.log_path}/{filename}"
        save_choices_history(self._choices_history, filepath)
        if is_enabled_clearml():
            task = get_clearml()
            task.upload_artifact(
                name=filename,
                artifact_object=filepath,
                metadata={"description": "OmniPlayer choice history"},
            )

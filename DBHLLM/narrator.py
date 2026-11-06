import json
import os
import time
from collections import deque

from PIL.Image import Image
from pydantic import BaseModel

from core.event import Event, EventDispatcher
from core.log import get_clearml, get_logger, is_enabled_clearml, is_enabled_langfuse
from core.utils import generate_short_hash, save_obs_image
from DBHHelper.events import (
    ObsEvent,
    ObsWithActEvent,
    ObsWithContextAndChoicesEvent,
    ObsWithContextEvent,
)
from DBHLLM.utils import ImageQueueCombiner

from .llm_api import LLMAPI
from .prompts.narrator import ImageSummary, TextSummary
from .utils import get_llm_kwargs


class SummaryEvent(Event):
    name: str = "summary_event"

    class Kwargs(BaseModel):
        summary: str
        context: str = ""
        choices: str = ""
        last_choice: str = ""

    kwargs: Kwargs


class GetImageDescriptionsEvent(Event):
    name: str = "get_image_descriptions_event"

    class Kwargs(BaseModel):
        indexes: tuple[int, ...]

    kwargs: Kwargs


class GetImageDescriptionsResponse(Event):
    name: str = "get_image_descriptions_response"

    class Kwargs(BaseModel):
        image_descriptions: str

    kwargs: Kwargs


class GetPlotSummariesEvent(Event):
    name: str = "get_plot_summaries_event"

    class Kwargs(BaseModel):
        indexes: tuple[int, ...]

    kwargs: Kwargs


class GetPlotSummariesResponse(Event):
    name: str = "get_plot_summaries_response"

    class Kwargs(BaseModel):
        plot_summaries: str

    kwargs: Kwargs


class DummyLLMNarrator(EventDispatcher):
    DELAY = 0.2

    def __init__(self):
        super().__init__()
        self._logger = get_logger()
        self._combiner = ImageQueueCombiner((2, 2), height=512)
        self.obs_index = 0

    def _get_summary(
        self, obs: Image, context: str = "", choices: dict = {}, act: str = ""
    ):
        self._combiner.add_image(obs)
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

        # Save image locally if enabled
        save_obs_image(_combined_image, "Combined Obs", "combined obs", self.obs_index)
        self.obs_index += 1
        time.sleep(self.DELAY)
        return SummaryEvent(
            kwargs={
                "summary": "Initial summary. Ignore this.",
                "context": context,
                "choices": str(choices),
                "last_choice": act,
            }
        )

    @EventDispatcher.on(GetImageDescriptionsEvent)
    def get_image_descriptions(
        self, indexes: tuple[int, ...]
    ) -> GetImageDescriptionsResponse:
        """Get the image descriptions from the previous summaries"""
        image_descriptions = "Dummy image descriptions"
        return GetImageDescriptionsResponse(
            kwargs={"image_descriptions": image_descriptions}
        )

    @EventDispatcher.on(GetPlotSummariesEvent)
    def get_plot_summaries(self, indexes: tuple[int, ...]) -> GetPlotSummariesResponse:
        """Get the plot summaries from the previous summaries"""
        plot_summaries = "Dummy plot summaries"
        return GetPlotSummariesResponse(kwargs={"plot_summaries": plot_summaries})

    @EventDispatcher.on(ObsEvent)
    def summarize(self, obs: Image):
        event = self._get_summary(obs)
        self._logger.debug("Called summarize with image.")
        return event

    @EventDispatcher.on(ObsWithActEvent)
    def summarize_with_act(self, obs: Image, act: str):
        event = self._get_summary(obs, act=act)
        self._logger.debug("Called summarize with image and action.")
        return event

    @EventDispatcher.on(ObsWithContextEvent)
    def summarize_with_context(self, obs: Image, context: str):
        event = self._get_summary(obs, context=context)
        self._logger.debug("Called summarize with image and context.")
        return event

    @EventDispatcher.on(ObsWithContextAndChoicesEvent)
    def summarize_with_context_and_choices(
        self, obs: Image, context: str, choices: dict
    ):
        event = self._get_summary(obs, context=context, choices=choices)
        self._logger.debug("Called summarize with image, context, and choices.")
        return event


class LLMNarrator(LLMAPI):
    def __init__(
        self,
        chapter_summary: str,
        protagonist_summary: str,
        key_characters: list[str],
    ):
        self.session_id = "narrator_" + generate_short_hash()
        super().__init__(session_id=self.session_id)
        self.chapter_summary = chapter_summary
        self.protagonist_summary = protagonist_summary
        self.key_characters_list = key_characters
        self.key_characters = dict((k, "EMPTY") for k in key_characters)
        model = os.getenv("models.narrator")
        self.llm_kwargs = get_llm_kwargs(model)
        self._logger = get_logger()
        if is_enabled_clearml():
            get_clearml().add_tags(f"n/{model}")
        self._combiner = ImageQueueCombiner((2, 2), height=512)
        self.obs_index = 0
        self._prev_image_summary: deque[ImageSummary.Response] = deque(maxlen=10)
        self._prev_text_summary: deque[TextSummary.Response] = deque(maxlen=3)

    @EventDispatcher.on(GetImageDescriptionsEvent)
    def get_image_descriptions(
        self, indexes: tuple[int, ...]
    ) -> GetImageDescriptionsResponse:
        """Get the image descriptions from the previous summaries"""
        image_descriptions = self._get_image_descriptions(indexes)
        return GetImageDescriptionsResponse(
            kwargs={"image_descriptions": image_descriptions}
        )

    def _get_image_descriptions(self, indexes: tuple[int, ...] = (9, 4, 1, 0)) -> str:
        # Choose 1, 2, 5, 10 image summaries from the deque
        _image_summaries = list(self._prev_image_summary)[::-1]
        _image_summaries = [
            f"## {i + 1} frames before\n{_image_summaries[i].description}"
            for i in indexes
            if i < len(_image_summaries)
        ]
        image_descriptions = (
            "\n\n".join(_image_summaries) if _image_summaries else "EMPTY"
        )
        return image_descriptions

    @EventDispatcher.on(GetPlotSummariesEvent)
    def get_plot_summaries(self, indexes: tuple[int, ...]) -> GetPlotSummariesResponse:
        """Get the plot summaries from the previous summaries"""
        plot_summaries = self._get_plot_summaries(indexes)
        return GetPlotSummariesResponse(kwargs={"plot_summaries": plot_summaries})

    def _get_plot_summaries(self, indexes: tuple[int, ...] = (2, 1, 0)) -> str:
        _text_summaries = list(self._prev_text_summary)[::-1]
        _text_summaries = [
            f"## {i + 1} frames before\n{_text_summaries[i].to_md(header='###')}"
            for i in indexes
            if i < len(_text_summaries)
        ]
        plot_summaries = "\n\n".join(_text_summaries) if _text_summaries else "EMPTY"
        return plot_summaries

    def _get_summary(
        self, obs: Image, context: str = "", choices: dict = {}, act: str = ""
    ):
        self._combiner.add_image(obs)
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

        # Save image locally if enabled
        save_obs_image(_combined_image, "Combined Obs", "combined obs", self.obs_index)
        self.obs_index += 1
        # Format choices as a formatted list if they exist
        formatted_choices = ""
        if choices:
            formatted_choices = "Choices:\n" + "\n".join(
                [f"{key}: {value}" for key, value in choices.items()]
            )

        prompt = ImageSummary.get_prompt(
            protagonist_summary=self.protagonist_summary,
            chapter_summary=self.chapter_summary,
            key_characters=self.key_characters,
            image=_combined_image,
            image_descriptions=self._get_image_descriptions(),
            plot_summaries=self._get_plot_summaries(),
            dialogue=context,
            choices=formatted_choices,
            last_choice=act,
        )
        response: ImageSummary.Response = self.query(
            prompt=prompt,
            prompt_cls=ImageSummary,
            session_id=self.session_id,
            **self.llm_kwargs,
        )
        self._prev_image_summary.append(response)
        self.key_characters.update(response.key_characters)
        prompt = TextSummary.get_prompt(
            protagonist_summary=self.protagonist_summary,
            chapter_summary=self.chapter_summary,
            image_descriptions=self._get_image_descriptions(),
            plot_summaries=self._get_plot_summaries(),
            dialogue=context,
            choices=formatted_choices,
            last_choice=act,
        )
        response = self.query(
            prompt=prompt,
            prompt_cls=TextSummary,
            session_id=self.session_id,
            **self.llm_kwargs,
        )
        self._prev_text_summary.append(response)
        return SummaryEvent(
            kwargs={
                "summary": self._prev_text_summary[-1].to_md(),
                "context": context,
                "choices": formatted_choices,
                "last_choice": act,
            }
        )

    @EventDispatcher.on(ObsEvent)
    def summarize(self, obs: Image):
        event = self._get_summary(obs)
        self._logger.debug("Called summarize with image.")
        return event

    @EventDispatcher.on(ObsWithActEvent)
    def summarize_with_act(self, obs: Image, act: str):
        event = self._get_summary(obs, act=act)
        self._logger.debug("Called summarize with image and action.")
        return event

    @EventDispatcher.on(ObsWithContextEvent)
    def summarize_with_context(self, obs: Image, context: str):
        event = self._get_summary(obs, context=context)
        self._logger.debug("Called summarize with image and context.")
        return event

    @EventDispatcher.on(ObsWithContextAndChoicesEvent)
    def summarize_with_context_and_choices(
        self, obs: Image, context: str, choices: list
    ):
        event = self._get_summary(obs, context=context, choices=choices)
        self._logger.debug("Called summarize with image, context, and choices.")
        return event


class LLMImageOnlyNarrator(LLMAPI):
    def __init__(
        self,
        chapter_summary: str,
        protagonist_summary: str,
        key_characters: list[str],
    ):
        self.session_id = "narrator_" + generate_short_hash()
        super().__init__(session_id=self.session_id)
        self.chapter_summary = chapter_summary
        self.protagonist_summary = protagonist_summary
        self.key_characters_list = key_characters
        self.key_characters = dict((k, "EMPTY") for k in key_characters)
        model = os.getenv("models.narrator")
        self.llm_kwargs = get_llm_kwargs(model)
        self._logger = get_logger()
        if is_enabled_clearml():
            get_clearml().add_tags(f"n/{model}")
        self._combiner = ImageQueueCombiner((2, 2), height=512)
        self.obs_index = 0
        self._prev_image_summary: deque[ImageSummary.Response] = deque(maxlen=10)

    @EventDispatcher.on(GetImageDescriptionsEvent)
    def get_image_descriptions(
        self, indexes: tuple[int, ...]
    ) -> GetImageDescriptionsResponse:
        """Get the image descriptions from the previous summaries"""
        image_descriptions = self._get_image_descriptions(indexes)
        return GetImageDescriptionsResponse(
            kwargs={"image_descriptions": image_descriptions}
        )

    def _get_image_descriptions(self, indexes: tuple[int, ...] = (9, 4, 1, 0)) -> str:
        # Choose 1, 2, 5, 10 image summaries from the deque
        _image_summaries = list(self._prev_image_summary)[::-1]
        _image_summaries = [
            f"## {i + 1} frames before\n{_image_summaries[i].description}"
            for i in indexes
            if i < len(_image_summaries)
        ]
        image_descriptions = (
            "\n\n".join(_image_summaries) if _image_summaries else "EMPTY"
        )
        return image_descriptions

    def _get_summary(
        self, obs: Image, context: str = "", choices: dict = {}, act: str = ""
    ):
        self._combiner.add_image(obs)
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

        # Save image locally if enabled
        save_obs_image(_combined_image, "Combined Obs", "combined obs", self.obs_index)
        self.obs_index += 1
        # Format choices as a formatted list if they exist
        formatted_choices = ""
        if choices:
            formatted_choices = "Choices:\n" + "\n".join(
                [f"{key}: {value}" for key, value in choices.items()]
            )

        prompt = ImageSummary.get_prompt(
            protagonist_summary=self.protagonist_summary,
            chapter_summary=self.chapter_summary,
            key_characters=self.key_characters,
            image=_combined_image,
            image_descriptions=self._get_image_descriptions(),
            plot_summaries=None,
            dialogue=context,
            choices=formatted_choices,
            last_choice=act,
        )
        response: ImageSummary.Response = self.query(
            prompt=prompt,
            prompt_cls=ImageSummary,
            session_id=self.session_id,
            **self.llm_kwargs,
        )
        self._prev_image_summary.append(response)
        self.key_characters.update(response.key_characters)

        return SummaryEvent(
            kwargs={
                "summary": self._prev_image_summary[-1].description,
                "context": context,
                "choices": formatted_choices,
                "last_choice": act,
            }
        )

    @EventDispatcher.on(ObsEvent)
    def summarize(self, obs: Image):
        event = self._get_summary(obs)
        self._logger.debug("Called summarize with image.")
        return event

    @EventDispatcher.on(ObsWithActEvent)
    def summarize_with_act(self, obs: Image, act: str):
        event = self._get_summary(obs, act=act)
        self._logger.debug("Called summarize with image and action.")
        return event

    @EventDispatcher.on(ObsWithContextEvent)
    def summarize_with_context(self, obs: Image, context: str):
        event = self._get_summary(obs, context=context)
        self._logger.debug("Called summarize with image and context.")
        return event

    @EventDispatcher.on(ObsWithContextAndChoicesEvent)
    def summarize_with_context_and_choices(
        self, obs: Image, context: str, choices: dict
    ):
        event = self._get_summary(obs, context=context, choices=choices)
        self._logger.debug("Called summarize with image, context, and choices.")
        return event

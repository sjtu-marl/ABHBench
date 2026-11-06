import random
import time

from DBHHelper.mixin.log import LogMixin

from .llm_api import LLMAPI


class LLMCritic(LogMixin):
    RETRY = 10

    def __init__(
        self,
        logger,
        llm_api: LLMAPI,
        prompt_template: str,
        character_summary="Initial summary. Ignore this.",
        chapter_summary="Initial summary. Ignore this.",
    ) -> None:
        self._logger = logger
        self.llm_api = llm_api
        self.character_summary = character_summary
        self.chapter_summary = chapter_summary
        self.prompt_template = prompt_template
        self.debug(
            "\n".join(
                [
                    f"LLM API: {type(llm_api).__name__}",
                    f"LLM Params: {llm_api._params}",
                    f"Prompt Template: {prompt_template}",
                    f"Character Summary: {character_summary}",
                    f"Chapter Summary: {chapter_summary}",
                ]
            )
        )

    def rating(
        self,
        img_summary: str,
        summary: str,
        key: str,
        context: str,
        choices: dict,
        shuffle_choices: bool = True,
    ):
        self.debug(
            "\n".join(
                [
                    f"Image Summary: {img_summary}",
                    f"Summary: {summary}",
                    f"Key: {key}",
                    f"Context: {context}",
                    f"Choices: {choices}",
                ]
            )
        )
        context = context if context else ""
        if shuffle_choices:
            original_choices = choices.copy()
            keys = list(choices.keys())
            values = list(choices.values())
            random.shuffle(values)
            shuffled_choices = dict(zip(keys, values))
        choices_text = "\n".join(
            [f"- {value}" for key, value in shuffled_choices.items()]
        )
        _character_summary = self.character_summary
        _chapter_summary = self.chapter_summary
        _img_summary = img_summary
        _summary = summary
        _context = context
        _choices = choices_text
        self.debug(
            "\n".join(
                [
                    f"Image Summary: {_img_summary}",
                    f"Summary: {_summary}",
                    f"Context: {_context}",
                    f"Choices: {_choices}",
                ]
            )
        )
        base_prompt = [
            f"##Character Summary\n{_character_summary}",
            f"##Chapter Summary\n{_chapter_summary}",
            f"##Image Summary\n{_img_summary}",
            f"##Current Situation\n{_summary}",
            f"##Context\n{_context}",
            f"##Choices\n{_choices}",
        ]
        # Loop over selected choices and create a prompt for each
        for choice_key, choice_value in shuffled_choices.items():
            selected_choice = f"##Selected Choice\n{choice_value}"
            _base_prompt = base_prompt.copy()
            _base_prompt.append(selected_choice)
            prompt = "\n\n".join(_base_prompt)
            response = self._rating(prompt)

    def _rating(self, context: str):
        _prompt = self.prompt_template.replace("{{context}}", context)
        prompt = [
            {
                "role": "user",
                "content": _prompt,
            },
        ]
        retry = self.RETRY
        while retry >= 0:
            try:
                response = self.llm_api.query(prompt)
                self.debug(f"\nPrompt: {prompt}\nResponse: {response}")
                break
                # TODO extract and validate rating
                # choice = self.extract_and_validate_choice_text(response.choice, choices)
                # if choice:
                #     break
                # retry -= 1
            except Exception as e:
                import traceback

                self.error(traceback.format_exc())
                retry -= 1
                time.sleep((self.RETRY - retry) * 5)
        return response

    def save_history(self, path: str):
        self.llm_api.save_history(path)


class DummyLLMCritic(LogMixin):
    DELAY = 1

    def __init__(
        self,
        logger,
        llm_api: LLMAPI = None,
    ) -> None:
        self._logger = logger

    def rating(
        self,
        img_summary: str,
        summary: str,
        key: str,
        context: str,
        choices: dict,
        shuffle_choices=True,
    ):
        self.info(f"Context: {context}\nChoices: {choices}")
        time.sleep(self.DELAY)

    def save_history(self, path: str):
        pass

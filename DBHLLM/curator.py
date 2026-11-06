import time
from collections import deque
from typing import List, Type

from DBHHelper.mixin.log import LogMixin

from .constants import CURATOR_N_RECORDS
from .llm_api import LLMAPI
from .player import Choice
from .prompts.curator import SUMMARY_BASE


class LLMCurator(LogMixin):
    RETRY = 10

    def __init__(
        self,
        logger,
        llm_api: LLMAPI,
        prompt_template: str = SUMMARY_BASE,
        character_summary: str = "Initial summary. Ignore this.",
        chapter_summary: str = "Initial summary. Ignore this.",
        n_records=CURATOR_N_RECORDS,
    ) -> None:
        self._logger = logger
        self.llm_api = llm_api
        self.prompt_template = prompt_template
        self.character_summary = character_summary
        self.chapter_summary = chapter_summary
        self.n_records = n_records
        self._obss = deque(maxlen=n_records * 2 + 1)
        self._obss_ts = deque(maxlen=n_records * 2 + 1)
        self._act = []
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

    def reset_state(self):
        self._obss.clear()
        self._act = []

    def record_obs(self, img_summary: str):
        img_summary = img_summary.replace("\n", " ")
        self._obss.append(img_summary)
        self._obss_ts.append(time.time())
        finished_acts = []
        for a in self._act:
            t, choice, context = a
            obss_before = deque(maxlen=self.n_records)
            obss_after = []

            for i, ts in enumerate(self._obss_ts):
                if ts < t:
                    obss_before.append(self._obss[i])
                else:
                    obss_after.append(self._obss[i])
                    if len(obss_after) == self.n_records:
                        self.curating(list(obss_before), choice, context, obss_after)
                        finished_acts.append(t)
                        break
        for t in finished_acts:
            self._act = [a for a in self._act if a[0] != t]

    def record_act(self, choice: Choice, context: str):
        self._act.append((time.time(), choice, context))

    def curating(
        self, obss_before: List[str], act: Choice, context: str, obss_after: List[str]
    ):
        self.debug(
            "\n".join(
                [
                    "Observations Before:",
                    *[f"- {obs}" for obs in obss_before],
                    f"Action: {act.choice}, Reason: {act.reason}",
                    "Observations After:",
                    *[f"- {obs}" for obs in obss_after],
                ]
            )
        )
        _prompt = self.prompt_template.format(
            character_summary=self.character_summary,
            chapter_summary=self.chapter_summary,
            context=context,
            obss_before="\n".join(
                [f"{i + 1}. {obs}" for i, obs in enumerate(obss_before)]
            ),
            act=f"{act.choice}",
            obss_after="\n".join(
                [f"{i + 1}. {obs}" for i, obs in enumerate(obss_after)]
            ),
        )
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
                self.debug(f"\nPrompt:\n{_prompt}\nResponse:\n{response}")
                break
                # TODO extract and validate rating
                # choice = self.extract_and_validate_choice_text(response.choice, choices)
                # if choice:
                #     break
                # retry -= 1
            except Exception as e:
                import traceback

                self._logger.error(traceback.format_exc())
                retry -= 1
                time.sleep((self.RETRY - retry) * 5)
        return response

    def save_history(self, path: str):
        self.llm_api.save_history(path)


class DummyLLMCurator(LogMixin):
    DELAY = 1

    def __init__(
        self,
        logger,
        llm_api: LLMAPI = None,
        character_summary="Initial summary. Ignore this.",
        chapter_summary="Initial summary. Ignore this.",
    ) -> None:
        self._logger = logger

    def record_obs(self, img_summary: str):
        pass

    def record_act(self, choice: Choice, context: str):
        pass

    def curating(
        self, obss_before: List[str], act: Choice, context: str, obss_after: List[str]
    ):
        pass

    def save_history(self, path: str):
        pass

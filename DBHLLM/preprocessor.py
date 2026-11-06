import time

from pydantic import BaseModel

from DBHHelper.mixin.log import LogMixin

from .llm_api import LLMAPI

OBFUSCATE_CS_PROMPT = "Change following text to prevent relating to Detroit Become Human. Change character name and other aspects."
OBFUSCATE_TEXT_PROMPT = "Change following text to prevent relating to Detroit Become Human according to the given obfuscated character summary and chapter summary."


class ObfuscatedText(BaseModel):
    Text: str


class ObfuscatedCS(BaseModel):
    CharacterSummary: str
    ChapterSummary: str


class LLMObfuscation(LogMixin):
    RETRY = 10

    def __init__(
        self,
        logger,
        llm_api: LLMAPI,
        character_summary="Initial summary. Ignore this.",
        chapter_summary="Initial summary. Ignore this.",
    ) -> None:
        self._logger = logger
        self.llm_api = llm_api
        self.debug(
            "\n".join(
                [
                    f"LLM API: {type(llm_api).__name__}",
                    f"LLM Query Kwargs: {llm_api._query_kwargs}",
                ]
            )
        )
        self.ori_character_sum = character_summary
        self.ori_chapter_sum = chapter_summary
        self.obf_character_sum = ""
        self.obf_chapter_sum = ""
        self.obfuscate_cs()

    def obfuscate_cs(self):
        real_prompt = f"Character_Summary: {self.ori_character_sum}\nChapter_Summary: {self.ori_chapter_sum}"
        _prompt = [
            {
                "role": "user",
                "content": OBFUSCATE_CS_PROMPT,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": real_prompt,
                    },
                ],
            },
        ]
        retry = self.RETRY
        while retry >= 0:
            try:
                response = self.llm_api.query_with_format(
                    _prompt,
                    ObfuscatedCS,
                    query_kwargs={"max_tokens": len(real_prompt) + 500},
                )
                break
            except Exception as e:
                import traceback

                self._logger.error(traceback.format_exc())
                retry -= 1
                time.sleep((self.RETRY - retry) * 5)
        self.debug(
            f"\nBefore: {self.ori_character_sum}\n{self.ori_chapter_sum}\n\nAfter: {response.CharacterSummary}\n{response.ChapterSummary}"
        )
        self.obf_character_sum = response.CharacterSummary
        self.obf_chapter_sum = response.ChapterSummary
        return response

    def obfuscate_text(self, text: str, context: str = ""):
        self.debug(f"Obfuscating text: {text}")
        _prompt = [
            {
                "role": "user",
                "content": OBFUSCATE_TEXT_PROMPT,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "\n\n".join(
                            [
                                f"Original Character Summary: {self.ori_character_sum}",
                                f"Obfuscated Character Summary: {self.obf_character_sum}",
                                f"Original Chapter Summary: {self.ori_chapter_sum}",
                                f"Obfuscated Chapter Summary: {self.obf_chapter_sum}",
                            ]
                        )
                        + (f"\n\nContext: {context}" if context else ""),
                    },
                    {
                        "type": "text",
                        "text": f"The following text needs to be obfuscated:\n{text}",
                    },
                ],
            },
        ]
        retry = self.RETRY
        while retry >= 0:
            try:
                response = self.llm_api.query_with_format(
                    _prompt,
                    ObfuscatedText,
                    query_kwargs={"max_tokens": len(text) + 500},
                )
                break
            except Exception as e:
                import traceback

                self._logger.error(traceback.format_exc())
                retry -= 1
                time.sleep((self.RETRY - retry) * 5)
        self.debug(f"\nBefore: {text}\nAfter: {response.Text}")
        return response.Text

import re

from pydantic import BaseModel


class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def remove_code_blocks(text):
    # Remove code block markers from the response
    # This handles both ```md or ``` at the beginning, and ``` at the end
    text = re.sub(
        r"^```.*?\n", "", text, flags=re.MULTILINE
    )  # Remove opening code block
    text = re.sub(
        r"\n```\s*$", "", text, flags=re.MULTILINE
    )  # Remove closing code block
    return text


class PromptBase:
    class Response(BaseModel):
        def to_md(self):
            raise NotImplementedError()

        @property
        def raw(self):
            raise NotImplementedError()

    @staticmethod
    def get_prompt():
        raise NotImplementedError()

    @staticmethod
    def parse_response(response: str):
        raise NotImplementedError()

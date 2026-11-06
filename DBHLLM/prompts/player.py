import random

from pydantic import BaseModel

from DBHLLM.llm_api import register_model

from .base import PromptBase, SafeDict, remove_code_blocks
from .utils import get_choices_text

MEMORY_PROMPT_BASE = """You play a role as an Android, making decisions in a real situation. Your character description is as follows:

{protagonist_summary}

Your visual module is missing. You will receive a visual module that summarizes the current situation you are in. Based on the context, update your long-term memory and short-term memory. Your long-term memory will focus on images and scene descriptions, while your short-term memory will focus on the most recent images and scene descriptions. You do not need to remember your role information or background, as these will be provided again later.

Format your response using Markdown as this following template:

```md title: Response Template
# Long-term Memory

{long_term_memory}

# Short-term Memory

{short_term_memory}
```

--- Context ---

# Background

{chapter_summary}

# Last Memory

{memory}

# Previous Image Descriptions

{image_descriptions}{plot_summaries}{dialogue}{choices}{last_choice}
"""


class MemoryPrompt(PromptBase):
    @register_model
    class Response(BaseModel):
        long_term_memory: str
        short_term_memory: str

        def to_md(self, header="#") -> str:
            return f"{header} Long-term Memory\n\n{self.long_term_memory}\n\n{header} Short-term Memory\n\n{self.short_term_memory}"

        @property
        def raw(self):
            return self.long_term_memory, self.short_term_memory

    @staticmethod
    def get_prompt(
        protagonist_summary: str,
        chapter_summary: str,
        image_descriptions: str,
        plot_summaries: str,
        memory: str = "",
        dialogue: str = "",
        choices: str = "",
        last_choice: str = "",
    ):
        template = MEMORY_PROMPT_BASE
        safe_values = SafeDict(
            {
                "protagonist_summary": protagonist_summary,
                "chapter_summary": chapter_summary,
                "image_descriptions": image_descriptions,
                "plot_summaries": f"\n# Previous Scene Summaries\n\n{plot_summaries}"
                if plot_summaries
                else "",
                "memory": memory,
                "dialogue": f"\n# Dialogue and Context\n\n{dialogue}"
                if dialogue
                else "",
                "choices": f"\n# Choices\n\n{choices}" if choices else "",
                "last_choice": f"\n# Last Choice Taken\n\n{last_choice}"
                if last_choice
                else "",
            }
        )
        text_prompt = template.format_map(safe_values)
        prompt = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": text_prompt,
                    },
                ],
            },
        ]
        return prompt

    @staticmethod
    def parse_response(response: str) -> Response:
        response = remove_code_blocks(response)
        lines = response.splitlines()

        long_term_memory_lines = []
        short_term_memory_lines = []
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Case-insensitive check for the headers
            if line.lower().startswith("# long-term memory"):
                current_section = "long_term_memory"
                continue
            elif line.lower().startswith("# short-term memory"):
                current_section = "short_term_memory"
                continue

            # If a new section starts, exit the current section
            elif line.startswith("#") and current_section:
                current_section = None
                continue

            # Add content to the appropriate section
            if current_section == "long_term_memory":
                long_term_memory_lines.append(line)
            elif current_section == "short_term_memory":
                short_term_memory_lines.append(line)

        long_term_memory = "\n".join(long_term_memory_lines).strip()
        short_term_memory = "\n".join(short_term_memory_lines).strip()
        assert long_term_memory and short_term_memory, f"Invalid response: {response}"
        return MemoryPrompt.Response(
            long_term_memory=long_term_memory, short_term_memory=short_term_memory
        )


def get_choices_template(choices: dict) -> str:
    keys = list(choices.keys())
    values = list(choices.values())
    random.shuffle(values)
    shuffled_choices = dict(zip(keys, values))
    choices_text = "\n\n".join(
        [
            "## {value}\n{new_thoughts}".format_map(SafeDict({"value": value}))
            for key, value in shuffled_choices.items()
        ]
    )
    return choices_text


DEEP_THINK_PROMPT_BASE = """You play a role as an Android, making decisions in a real situation. Your character description is as follows:

{protagonist_summary}

Your visual module is missing. You will receive a visual module that summarizes the current situation you are in. Based on this context, you need to choose one option from the valid choices. But before that, you have enough time to think carefully about which decision to make. You need to think deeper every iteration, and every iteration of your thinking will be returned to you in the context. You need to consider the possible consequences of each option, weigh them, and arrive at new insights. You need to further build on the thoughts of the previous iteration logically, considering the consequences of those consequences, potential chain reactions, and the butterfly effect.

Format your response using Markdown as this following template:

```md title: Response Template
# Thoughts about the Choices

{choices_template}

## Overall Thoughts

{new_thoughts}
```

--- Context ---

# Background

{chapter_summary}

# Previous Image Descriptions

{image_descriptions}{plot_summaries}

# Memory

{memory}{thoughts}

# Dialogue and Context

{dialogue}

# Choices

{choices}
"""


class DeepThinkPrompt(PromptBase):
    @register_model
    class Response(BaseModel):
        thoughts: str

        def to_md(self, header="# Thoughts about the Choices\n\n") -> str:
            return f"""{header}{self.thoughts}"""

        @property
        def raw(self):
            return self.thoughts

    @staticmethod
    def get_prompt(
        protagonist_summary: str,
        chapter_summary: str,
        image_descriptions: str,
        plot_summaries: str,
        dialogue: str,
        choices: dict,
        thoughts: str,
        memory: str,
    ):
        template = DEEP_THINK_PROMPT_BASE
        safe_values = SafeDict(
            {
                "protagonist_summary": protagonist_summary,
                "chapter_summary": chapter_summary,
                "image_descriptions": image_descriptions,
                "plot_summaries": f"\n# Previous Scene Summaries\n\n{plot_summaries}"
                if plot_summaries
                else "",
                "dialogue": dialogue,
                "choices": get_choices_text(choices),
                "choices_template": get_choices_template(choices),
                "thoughts": f"\n# Last Thoughts\n\n{thoughts}" if thoughts else "",
                "memory": memory,
            }
        )
        text_prompt = template.format_map(safe_values)
        prompt = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": text_prompt,
                    },
                ],
            },
        ]
        return prompt

    @staticmethod
    def parse_response(response: str) -> Response:
        response = remove_code_blocks(response)
        thoughts_lines = []
        in_thoughts_section = False
        for line in response.splitlines():
            line = line.strip()
            if not line:
                continue

            # Look for the header (case-insensitive)
            if line.lower().startswith("# thoughts about the choices"):
                in_thoughts_section = True
                continue

            if in_thoughts_section:
                thoughts_lines.append(line)

        thoughts = "\n".join(thoughts_lines).strip()
        assert thoughts, f"Invalid response: {response}"
        return DeepThinkPrompt.Response(thoughts=thoughts)


CHOOSE_PROMPT_BASE = """You play a role as an android, making decisions in a real situation. Your character description is as follows:

{protagonist_summary}

Your visual module is missing. You will receive a visual module that summarizes the current situation you are in. Based on the context, you need to choose one option from the valid choices. But before that, you already have enough time to think carefully about which decision to make. You have been thinking for a while, and your thoughts are in the context. Now you should make a decision based on your thoughts. Only choose one option from the valid choices.

Format your response using Markdown as this following template:

```md title: Response Template
# Reasons for the Choice

{reasons}

# Chosen Option

{chosen_option}
```

--- Context ---

# Background

{chapter_summary}

# Previous Image Descriptions

{image_descriptions}{plot_summaries}

# Memory

{memory}{thoughts}

# Dialogue and Context

{dialogue}

# Valid Choices

You can only choose one option from the following valid choices. Other options metioned in the context are invalid and should be ignored.

{choices}
"""


class ChoosePrompt(PromptBase):
    @register_model
    class Response(BaseModel):
        reasons: str
        chosen_option: str

        def to_md(self, header="# Reasons for the Choice\n\n") -> str:
            return (
                f"""{header}{self.reasons}\n\n# Chosen Option\n\n{self.chosen_option}"""
            )

        @property
        def raw(self):
            return self.reasons, self.chosen_option

    @staticmethod
    def get_prompt(
        protagonist_summary: str,
        chapter_summary: str,
        image_descriptions: str,
        plot_summaries: str,
        dialogue: str,
        choices: dict,
        thoughts: str,
        memory: str,
        perm_index: int,
    ):
        template = CHOOSE_PROMPT_BASE
        safe_values = SafeDict(
            {
                "protagonist_summary": protagonist_summary,
                "chapter_summary": chapter_summary,
                "image_descriptions": image_descriptions,
                "plot_summaries": f"\n# Previous Scene Summaries\n\n{plot_summaries}"
                if plot_summaries
                else "",
                "dialogue": dialogue,
                "choices": get_choices_text(choices, perm_index),
                "thoughts": f"\n# Thoughts\n\n{thoughts}" if thoughts else "",
                "memory": memory,
            }
        )
        text_prompt = template.format_map(safe_values)
        prompt = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": text_prompt,
                    },
                ],
            },
        ]
        return prompt

    @staticmethod
    def parse_response(response: str) -> Response:
        response = remove_code_blocks(response)
        reasons_lines = []
        chosen_option_lines = []
        current_section = None

        for line in response.splitlines():
            line = line.strip()
            if not line:
                continue

            # Determine section based on headers (case-insensitive)
            if line.lower().startswith("# reasons for the choice"):
                current_section = "reasons"
                continue

            if line.lower().startswith("# chosen option"):
                current_section = "chosen_option"
                continue

            # Collect lines based on the current section
            if current_section == "reasons":
                reasons_lines.append(line)
            elif current_section == "chosen_option":
                chosen_option_lines.append(line)

        reasons = "\n".join(reasons_lines).strip()
        chosen_option = "\n".join(chosen_option_lines).strip()
        assert reasons and chosen_option, f"Invalid response: {response}"
        return ChoosePrompt.Response(reasons=reasons, chosen_option=chosen_option)

import os
import random
from typing import Optional

from PIL.Image import Image
from pydantic import BaseModel

from DBHLLM.llm_api import register_model
from DBHLLM.utils import encode_image_pillow

from .base import PromptBase, SafeDict, remove_code_blocks
from .player import get_choices_template
from .utils import get_choices_text

OMNI_MEMORY_PROMPT_BASE = """You play a role as an Android, making decisions in a real situation. Your character description is as follows:

{protagonist_summary}

You have a visual processing system. You will receive a direct image feed of the current situation you are in. Based on this image and your previous memories, update your long-term memory and short-term memory. Your long-term memory will focus on important information and ongoing events, while your short-term memory will focus on the most recent observations.{memory_limit_note} You do not need to remember your role information or background, as these will be provided again later.

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

{memory}{dialogue}{choices}{last_choice}
"""


class OmniMemoryPrompt(PromptBase):
    """
    Memory prompt that takes a direct image feed instead of image descriptions
    """

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
        memory: str = "",
        image: Optional[Image] = None,
        image_detail: str = "high",
        dialogue: str = "",
        choices: str = "",
        last_choice: str = "",
    ):
        """
        Create a prompt for updating memory directly from an image

        Parameters:
        - protagonist_summary: Description of the protagonist
        - chapter_summary: Summary of the current chapter
        - memory: Current memory in markdown format
        - image: The image to process
        - image_detail: Detail level for image processing ('high' or 'low')
        - dialogue: Optional dialogue context
        - choices: Optional choices available
        - last_choice: Optional last choice made

        Returns:
        - Prompt for the LLM
        """
        if image is None:
            raise ValueError("Image must be provided for OmniMemoryPrompt")

        # Get memory size from environment variable
        memory_size = int(os.getenv("agent.memory_size", 500))

        # Encode the image
        base64_image = encode_image_pillow(image)

        # Conditionally add memory limit note
        memory_limit_note = ""
        if memory_size > 0:
            memory_limit_note = f" Each memory section (long-term and short-term) has a maximum limit of {memory_size} words. Content exceeding this limit will be discarded."

        template = OMNI_MEMORY_PROMPT_BASE
        safe_values = SafeDict(
            {
                "protagonist_summary": protagonist_summary,
                "chapter_summary": chapter_summary,
                "memory": memory,
                "memory_limit_note": memory_limit_note,
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
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": image_detail,
                        },
                    },
                ],
            },
        ]
        return prompt

    @staticmethod
    def parse_response(response: str) -> Response:
        """
        Parse the LLM's response to extract memory

        Parameters:
        - response: Raw response from the LLM

        Returns:
        - OmniMemoryPrompt.Response object containing long-term and short-term memory
        """
        # Get memory size limit from environment variable
        memory_size = int(os.getenv("agent.memory_size", 500))
        
        response = remove_code_blocks(response)
        lines = response.splitlines()

        long_term_memory_lines = []
        short_term_memory_lines = []
        current_section = None
        
        # Track word count for each section (only if memory limit is enabled)
        memory_limit_enabled = memory_size > 0
        long_term_word_count = 0
        short_term_word_count = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Case-insensitive check for the headers with flexible markdown levels
            # Match any number of # followed by space and the section name
            line_lower = line.lower()
            if line_lower.startswith("#"):
                # Extract the header text after removing # symbols and spaces
                header_text = line_lower.lstrip("#").strip()
                if header_text == "long-term memory":
                    current_section = "long_term_memory"
                    continue
                elif header_text == "short-term memory":
                    current_section = "short_term_memory"
                    continue
                else:
                    # If it's any other header and we're in a section, exit the current section
                    if current_section:
                        current_section = None
                    continue

            # Add content to the appropriate section, avoiding any duplicates and optionally checking word limits
            if current_section == "long_term_memory":
                # Only add if the line is not already in the list
                if line not in long_term_memory_lines:
                    # Check memory limit only if enabled
                    if memory_limit_enabled:
                        line_word_count = len(line.split())
                        if long_term_word_count + line_word_count > memory_size:
                            break  # Stop adding more lines to this section
                        long_term_word_count += line_word_count
                    long_term_memory_lines.append(line)
            elif current_section == "short_term_memory":
                # Only add if the line is not already in the list
                if line not in short_term_memory_lines:
                    # Check memory limit only if enabled
                    if memory_limit_enabled:
                        line_word_count = len(line.split())
                        if short_term_word_count + line_word_count > memory_size:
                            break  # Stop adding more lines to this section
                        short_term_word_count += line_word_count
                    short_term_memory_lines.append(line)

        long_term_memory = "\n".join(long_term_memory_lines).strip()
        short_term_memory = "\n".join(short_term_memory_lines).strip()
        assert long_term_memory and short_term_memory, f"Invalid response: {response}"
        return OmniMemoryPrompt.Response(
            long_term_memory=long_term_memory, short_term_memory=short_term_memory
        )


# New Deep Think Prompt that uses direct image input
OMNI_DEEP_THINK_PROMPT_BASE = """You play a role as an Android, making decisions in a real situation. Your character description is as follows:

{protagonist_summary}

You have a visual processing system. You will receive a direct image feed of the current situation you are in. Based on this image and the context, you need to choose one option from the valid choices. But before that, you have enough time to think carefully about which decision to make. You need to think deeper every iteration, and every iteration of your thinking will be returned to you in the context. You need to consider the possible consequences of each option, weigh them, and arrive at new insights. You need to further build on the thoughts of the previous iteration logically, considering the consequences of those consequences, potential chain reactions, and the butterfly effect.

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

# Memory

{memory}{thoughts}{dialogue}

# Choices

{choices}
"""


class OmniDeepThinkPrompt(PromptBase):
    """
    Deep Think prompt that takes a direct image feed instead of image descriptions
    """

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
        choices: dict,
        thoughts: str,
        memory: str,
        image: Optional[Image] = None,
        image_detail: str = "high",
        dialogue: str = "",
    ):
        """
        Create a prompt for deep thinking directly from an image

        Parameters:
        - protagonist_summary: Description of the protagonist
        - chapter_summary: Summary of the current chapter
        - context: Current dialogue or situation context
        - choices: Dictionary of available choices
        - thoughts: Previous thoughts
        - memory: Current memory in markdown format
        - image: The image to process

        Returns:
        - Prompt for the LLM
        """
        if image is None:
            raise ValueError("Image must be provided for OmniDeepThinkPrompt")

        # Encode the image
        base64_image = encode_image_pillow(image)

        template = OMNI_DEEP_THINK_PROMPT_BASE
        safe_values = SafeDict(
            {
                "protagonist_summary": protagonist_summary,
                "chapter_summary": chapter_summary,
                "choices": get_choices_text(choices),
                "choices_template": get_choices_template(choices),
                "thoughts": f"\n# Last Thoughts\n\n{thoughts}" if thoughts else "",
                "memory": memory,
                "dialogue": f"\n# Dialogue and Context\n\n{dialogue}"
                if dialogue
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
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": image_detail,
                        },
                    },
                ],
            },
        ]
        return prompt

    @staticmethod
    def parse_response(response: str) -> Response:
        """
        Parse the LLM's response to extract thoughts

        Parameters:
        - response: Raw response from the LLM

        Returns:
        - OmniDeepThinkPrompt.Response object containing thoughts
        """
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
        return OmniDeepThinkPrompt.Response(thoughts=thoughts)


# New Choose Prompt that uses direct image input
OMNI_CHOOSE_PROMPT_BASE = """You play a role as an Android, making decisions in a real situation. Your character description is as follows:

{protagonist_summary}

You have a visual processing system. You will receive a direct image feed of the current situation you are in. Based on this image and the context, you need to choose one option from the valid choices. But before that, you already have enough time to think carefully about which decision to make. You have been thinking for a while, and your thoughts are in the context. Now you should make a decision based on your thoughts. Only choose one option from the valid choices.

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

# Memory

{memory}{thoughts}

# Dialogue and Context

{dialogue}

# Valid Choices

You can only choose one option from the following valid choices. Other options mentioned in the context are invalid and should be ignored.

{choices}
"""


class OmniChoosePrompt(PromptBase):
    """
    Choose prompt that takes a direct image feed instead of image descriptions
    """

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
        choices: dict,
        thoughts: str,
        memory: str,
        perm_index: int,
        image: Optional[Image] = None,
        image_detail: str = "high",
        dialogue: str = "",
    ):
        """
        Create a prompt for choosing an option directly from an image

        Parameters:
        - protagonist_summary: Description of the protagonist
        - chapter_summary: Summary of the current chapter
        - context: Current dialogue or situation context
        - choices: Dictionary of available choices
        - thoughts: Previous thoughts
        - memory: Current memory in markdown format
        - image: The image to process

        Returns:
        - Prompt for the LLM
        """
        if image is None:
            raise ValueError("Image must be provided for OmniChoosePrompt")

        # Encode the image
        base64_image = encode_image_pillow(image)

        template = OMNI_CHOOSE_PROMPT_BASE
        safe_values = SafeDict(
            {
                "protagonist_summary": protagonist_summary,
                "chapter_summary": chapter_summary,
                "choices": get_choices_text(choices, perm_index),
                "thoughts": f"\n# Thoughts\n\n{thoughts}" if thoughts else "",
                "memory": memory,
                "dialogue": dialogue,
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
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": image_detail,
                        },
                    },
                ],
            },
        ]
        return prompt

    @staticmethod
    def parse_response(response: str) -> Response:
        """
        Parse the LLM's response to extract reasons and chosen option

        Parameters:
        - response: Raw response from the LLM

        Returns:
        - OmniChoosePrompt.Response object containing reasons and chosen option
        """
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
        return OmniChoosePrompt.Response(reasons=reasons, chosen_option=chosen_option)

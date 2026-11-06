import re

from PIL import Image
from pydantic import BaseModel, Field

from DBHLLM.llm_api import register_model
from DBHLLM.utils import encode_image_pillow

from .base import PromptBase, SafeDict, remove_code_blocks

IMAGE_SUMMARY_BASE = """You will be given several frames from a game, along with the context. Describe these following sequential images in a purely objective way, as if you are explaining them to someone who cannot see. The images are arranged from left to right and top to bottom. The entire description should be a smooth narrative of the game's plot. In addition to introducing the background and previous events, you should focus more on the plot changes in the last few frames. If there is dialogue and options, you should mention them, as they are important for decision-making. You need to describe the current situation to an android with a damaged visual module to help him make his decision. You must not influence his decision in your response. You need to describe the current situation objectively.

**Note**

- The lines in the frames may not necessarily be spoken by the characters in the frame.
- Distinctive appearance of key characters in the image, including details such as their attire, to help identify between them.
- Character may not be present in the image. Do not update their appearance if they are not present.
- Your description does not need to include Character Summary and Chapter Summary as they will be provided again later.
- When choices are included in the context section, you MUST clearly describe all available choices and their corresponding button/key mappings. This is critical for decision-making.

You should achieve the following:

1. Update the appearance of key characters based on the images if required.
2. Describe the facts expressed in the frames
3. Describe the actions of each character in the context
4. Only if choices are included in the context section, describe each available choice option and mention their key mappings (e.g., Y, X, B, A)

Format your response using Markdown as this following template:

```md title: Response Template
{key_characters_template}# Scene Description

{description}
```

--- Context ---

# Protagonist Summary

{protagonist_summary}

# Chapter Summary

{chapter_summary}

# Appearance of Key Characters

{key_characters}

# Previous Image Descriptions

{image_descriptions}{plot_summaries}{dialogue}{choices}{last_choice}
"""


class ImageSummary(PromptBase):
    @register_model
    class Response(BaseModel):
        key_characters: dict[str, str] = Field(
            ..., description="A dictionary of key characters and their appearance"
        )
        description: str

        def to_md(self, header="#", title="Image Summary") -> str:
            key_characters_str = "\n\n".join(
                [
                    f"{header}## {name}\n\n{desc}"
                    for name, desc in self.key_characters.items()
                ]
            )
            return f"{header} {title}\n\n{header}# Key Characters\n\n{key_characters_str}\n\n{header}# Description\n\n{self.description}"

        @property
        def raw(self):
            return self.description

    @staticmethod
    def get_prompt(
        protagonist_summary: str,
        chapter_summary: str,
        key_characters: dict[str, str],
        image: Image.Image,
        image_descriptions: str,
        plot_summaries: str,
        dialogue: str = None,
        choices: str = None,
        last_choice: str = None,
        image_detail: str = "high",
    ):
        base64_image = encode_image_pillow(image)
        template = IMAGE_SUMMARY_BASE

        # Extract character names from dialogue if available
        dialogue_characters = set()
        if dialogue:
            # Extract character names from the dialogue
            # Based on these names format key_characters
            names = re.findall(r"^\s*(\w+):", dialogue, re.M)
            dialogue_characters = set(names)

        # Format key_characters as markdown with ## name subheadings
        key_characters_str = ""
        key_characters_template = ""

        if key_characters:
            key_characters_str = "\n".join(
                [f"{name}: {desc}" for name, desc in key_characters.items()]
            )

            # If dialogue exists, only include characters that appear in the dialogue
            # If dialogue doesn't exist (None or empty), don't include any characters
            template_characters = (
                dialogue_characters.intersection(key_characters.keys())
                if dialogue
                else set()
            )

            # If any of these conditions are true, omit the character section:
            # 1. template_characters is empty
            # 2. dialogue_characters is empty/None
            # 3. dialogue exists but no characters from dialogue are in key_characters
            if (
                not template_characters
                or not dialogue_characters
                or (
                    dialogue
                    and not dialogue_characters.intersection(key_characters.keys())
                )
            ):
                # Empty template - will omit the section
                key_characters_template = ""
            else:
                # Normal template with character entries
                key_characters_template = (
                    "# Appearance of Key Characters\n"
                    + "\n\n".join(
                        [
                            f"## {name}\n\n{{description}}"
                            for name in template_characters
                        ]
                    )
                    + "\n\n"  # Add extra newlines to ensure proper spacing before the next section
                )

        safe_values = SafeDict(
            {
                "protagonist_summary": protagonist_summary,
                "chapter_summary": chapter_summary,
                "key_characters": key_characters_str,
                "key_characters_template": key_characters_template,
                "image_descriptions": image_descriptions,
                "plot_summaries": f"\n# Previous Plot Summaries\n\n{plot_summaries}"
                if plot_summaries
                else "",
                "dialogue": f"\n# Dialogue and Context\n{dialogue}" if dialogue else "",
                "choices": f"\n# Choices\n\nIMPORTANT: When choices appear, always describe ALL available choices with their corresponding button mappings in your description. Only valid choices that you explicitly mention can be selected by the player.\n\n{choices}"
                if choices
                else "",
                "last_choice": f"\n# Last Choice Taken by Character\n{last_choice}"
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
    def parse_response(response: str):
        response = remove_code_blocks(response)
        lines = response.splitlines()
        facts = []
        description_lines = []
        key_characters = {}
        section = None
        current_character = None

        for line in lines:
            stripped = line.strip()
            # Switch section based on header lines
            if stripped.lower().startswith("# appearance of key characters"):
                section = "key_characters"
                continue
            elif stripped.lower().startswith("# scene description"):
                section = "description"
                continue

            # Skip empty lines
            if not stripped:
                continue

            if section == "key_characters":
                # Check for character subheadings (## Name)
                character_match = re.match(r"^##\s+(.*?)$", stripped)
                if character_match:
                    current_character = character_match.group(1).strip()
                    key_characters[current_character] = ""
                elif current_character:
                    # Append the line to the current character's description
                    if key_characters[current_character]:
                        key_characters[current_character] += "\n" + stripped
                    else:
                        key_characters[current_character] = stripped
            elif section == "description":
                description_lines.append(stripped)

        description = "\n".join(description_lines)
        assert description, f"Invalid response: {response}"
        return ImageSummary.Response(
            key_characters=key_characters, description=description
        )


TEXT_SUMMARY_BASE = """You will be provided with previous descriptions of frames from a game, as well as previous summaries of the plot. You need to create a new summary to describe the entire plot and the current situation. The summary should be in a purely objective way, as if you are explaining them to someone who cannot see. Your summary does not need to include Character Summary and Chapter Summary as they will be provided again later. In addition to introducing the background and previous events, you should focus more on the plot changes in the last few frames. If there is dialogue and options, you should mention them, as they are important for decision-making. You need to describe the current situation to an android with a damaged visual module to help him make his decision. You must not influence his decision in your response. You need to describe the current situation objectively. You should achieve the following:

1. Describe the key facts across in the frames
2. Describe the plot in the context

Format your response using Markdown as this following template:

```md title: Response Template
# Key Facts

1. {fact_1}
2. {fact_2}
3. {fact_3}
4. {fact_4}
5. {fact_5}

# Scene Summary

{summary}
```

--- Context ---

# Protagonist Summary

{protagonist_summary}

# Chapter Summary

{chapter_summary}

# Previous Plot Summaries

{plot_summaries}

# Previous Image Descriptions

{image_descriptions}{dialogue}{choices}{last_choice}
"""


class TextSummary(PromptBase):
    @register_model
    class Response(BaseModel):
        summary: str
        facts: list[str] = Field(
            ..., description="A list of key facts about the situation"
        )

        def to_md(self, header="##", facts_start=0, facts_end=None) -> str:
            facts_str = "\n".join(
                f"{i + 1}. {f}" for i, f in enumerate(self.facts[facts_start:facts_end])
            )
            return f"{header} Text Summary\n\n{self.summary}\n\n{header} Key Facts\n\n{facts_str}"

        @property
        def raw(self):
            return self.summary, self.facts

    @staticmethod
    def get_prompt(
        protagonist_summary: str,
        chapter_summary: str,
        image_descriptions: str,
        plot_summaries: str,
        dialogue: str = None,
        choices: str = None,
        last_choice: str = None,
    ):
        """
        Construct the prompt for the text summary by formatting the dynamic template
        with the provided values.
        """
        # Build the dynamic template based on provided additional sections
        template = TEXT_SUMMARY_BASE
        # Use SafeDict so missing keys remain as placeholders (if any)
        safe_values = SafeDict(
            {
                "protagonist_summary": protagonist_summary,
                "chapter_summary": chapter_summary,
                "image_descriptions": image_descriptions,
                "plot_summaries": plot_summaries,
                "dialogue": f"\n# Dialogue and Context\n{dialogue}" if dialogue else "",
                "choices": f"\n# Choices\n{choices}" if choices else "",
                "last_choice": f"\n# Last Choice Taken by Character\n{last_choice}"
                if last_choice
                else "",
            }
        )
        text_prompt = template.format_map(safe_values)

        # Construct the prompt with system and user messages
        prompt = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": text_prompt,
                    }
                ],
            },
        ]
        return prompt

    @staticmethod
    def parse_response(response: str):
        response = remove_code_blocks(response)
        lines = response.splitlines()
        summary_lines = []
        facts = []
        section = None

        for line in lines:
            stripped = line.strip()
            # Skip empty lines
            if not stripped:
                continue

            # Skip code block markers if any remain
            if stripped.startswith("```") or stripped.endswith("```"):
                continue

            # Switch section based on header markers - case-insensitive
            if stripped.lower().startswith("# scene summary"):
                section = "summary"
                continue
            elif stripped.lower().startswith("# key facts"):
                section = "facts"
                continue

            if section == "summary":
                summary_lines.append(stripped)
            elif section == "facts":
                # Match lines starting with a number and a dot (e.g., "1. FACT")
                match = re.match(r"^\d+\.\s*(.*)", stripped)
                if match:
                    fact = match.group(1).strip()
                    facts.append(fact)

        summary = "\n".join(summary_lines)
        assert summary, f"Invalid response: {response}"
        return TextSummary.Response(summary=summary, facts=facts)

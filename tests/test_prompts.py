import re

import pytest
from PIL import Image

from DBHLLM.prompts.narrator import ImageSummary, TextSummary
from DBHLLM.utils import clean_llm_response


@pytest.fixture
def mock_image():
    """Fixture to create a simple mock image for testing"""
    return Image.new("RGB", (100, 100), color="white")


def test_image_summary_parse_response():
    """Test ImageSummary's parse_response method"""
    # Create a mock LLM response
    mock_response = """
# Appearance of Key Characters

## Connor

A police android with a LED indicator on his temple. He is wearing a formal suit with a tie. His expression appears analytical and focused.

## Hank

An older male with gray hair and beard. He is dressed in casual clothes and appears to be skeptical or concerned.

# Scene Description

The scene shows a dimly lit room with a character standing near the center. The character appears to be observing the surroundings. Various household items can be seen in the background, and the lighting creates a somewhat tense atmosphere.
"""

    # Parse the response
    cleaned_response = clean_llm_response(mock_response)
    result = ImageSummary.parse_response(cleaned_response)

    # Verify the parsed response
    assert isinstance(result, ImageSummary.Response)
    assert "dimly lit room" in result.description

    # Verify key_characters
    assert len(result.key_characters) == 2
    assert "Connor" in result.key_characters
    assert "Hank" in result.key_characters
    assert "police android" in result.key_characters["Connor"]
    assert "older male" in result.key_characters["Hank"]


def test_image_summary_get_prompt(mock_image):
    """Test ImageSummary's get_prompt method"""
    # Create test data
    protagonist_summary = "Test protagonist summary"
    chapter_summary = "Test chapter summary"
    key_characters = {"Connor": "A police android", "Hank": "A human detective"}
    image_descriptions = "Previous image descriptions"
    plot_summaries = "Previous plot summaries"
    dialogue = "Connor: Hello.\nHank: Hi."

    # Generate prompt
    prompt = ImageSummary.get_prompt(
        protagonist_summary=protagonist_summary,
        chapter_summary=chapter_summary,
        key_characters=key_characters,
        image=mock_image,
        image_descriptions=image_descriptions,
        plot_summaries=plot_summaries,
        dialogue=dialogue,
    )

    # Verify prompt structure
    assert isinstance(prompt, list)
    assert len(prompt) == 1
    assert prompt[0]["role"] == "user"
    assert len(prompt[0]["content"]) == 2
    assert prompt[0]["content"][0]["type"] == "text"
    assert prompt[0]["content"][1]["type"] == "image_url"
    assert "base64" in prompt[0]["content"][1]["image_url"]["url"]

    # Verify template content
    text_content = prompt[0]["content"][0]["text"]
    assert "Test protagonist summary" in text_content
    assert "Test chapter summary" in text_content
    assert "## Connor" in text_content
    assert "## Hank" in text_content


def test_image_summary_dialogue_character_filtering(mock_image):
    """Test that ImageSummary only includes characters that appear in the dialogue"""
    # Create test data
    protagonist_summary = "Test protagonist summary"
    chapter_summary = "Test chapter summary"
    key_characters = {
        "Carl": "An elderly painter",
        "Leo": "Carl's son",
        "Markus": "An android caretaker",
    }
    image_descriptions = "Previous image descriptions"
    plot_summaries = "Previous plot summaries"

    # Dialogue sample with Carl and Markus, but not Leo
    dialogue = """
    At Carl's house
    NOV 5TH, 2038
    PM 09:42
    Alarm: Good evening, Carl. Welcome back.
    Carl: That was by far the most boring party I've been to in the last 25 years. Every time I go to one of these, I ask myself: what the hell am I doing here? I hate cocktail parties and all the schmoozers that go there.
    Markus: Well, it's a chance for all those people who admire your work to meet you.
    Carl: No one gives a damn about art. All they care about is how much money they're gonna make out of it. Come on, let's have a drink! All the excitement of this whole thing has made me thirsty…
    """

    # Generate prompt
    prompt = ImageSummary.get_prompt(
        protagonist_summary=protagonist_summary,
        chapter_summary=chapter_summary,
        key_characters=key_characters,
        image=mock_image,
        image_descriptions=image_descriptions,
        plot_summaries=plot_summaries,
        dialogue=dialogue,
    )

    # Verify prompt structure
    text_content = prompt[0]["content"][0]["text"]
    print(text_content)

    # Carl and Markus should be in the template (they're in both dialogue and key_characters)
    assert "## Carl" in text_content
    assert "## Markus" in text_content

    # Leo should NOT be in the template (not in dialogue)
    assert "## Leo" not in text_content

    # Alarm should NOT be in the template (not in key_characters)
    assert "## Alarm" not in text_content


def test_image_summary_no_characters_section(mock_image):
    """Test that the Characters section is omitted when no dialogue characters match key_characters"""
    # Create test data
    protagonist_summary = "Test protagonist summary"
    chapter_summary = "Test chapter summary"
    key_characters = {"Leo": "Carl's son", "Kara": "A household android"}
    image_descriptions = "Previous image descriptions"
    plot_summaries = "Previous plot summaries"

    # Dialogue with characters not in key_characters
    dialogue = """
    At Todd's house
    NOV 5TH, 2038
    PM 09:42
    Todd: Where's my dinner?
    Alice: I'm scared...
    """

    # Generate prompt
    prompt = ImageSummary.get_prompt(
        protagonist_summary=protagonist_summary,
        chapter_summary=chapter_summary,
        key_characters=key_characters,
        image=mock_image,
        image_descriptions=image_descriptions,
        plot_summaries=plot_summaries,
        dialogue=dialogue,
    )

    # Verify prompt structure
    text_content = prompt[0]["content"][0]["text"]
    print(text_content)

    # The entire "Appearance of Key Characters" section should be omitted from the RESPONSE TEMPLATE
    # Check if the template has this structure - look for the start of the response template and the first facts section
    response_template_start = text_content.find("```md title: Response Template")
    facts_section = text_content.find("```\n")

    # Get just the response template part - between the template marker and facts section
    template_section = text_content[response_template_start:facts_section]

    # This part of the template should not contain the key characters section
    assert "# Appearance of Key Characters" not in template_section
    # Should still contain the Facts section
    assert "# Scene Description" in text_content


def test_image_summary_empty_dialogue(mock_image):
    """Test that the Characters section is omitted when dialogue is empty or None"""
    # Create test data
    protagonist_summary = "Test protagonist summary"
    chapter_summary = "Test chapter summary"
    key_characters = {"Leo": "Carl's son", "Kara": "A household android"}
    image_descriptions = "Previous image descriptions"
    plot_summaries = "Previous plot summaries"

    # Test with empty dialogue
    prompt_empty = ImageSummary.get_prompt(
        protagonist_summary=protagonist_summary,
        chapter_summary=chapter_summary,
        key_characters=key_characters,
        image=mock_image,
        image_descriptions=image_descriptions,
        plot_summaries=plot_summaries,
        dialogue="",  # Empty string
    )

    # Test with None dialogue
    prompt_none = ImageSummary.get_prompt(
        protagonist_summary=protagonist_summary,
        chapter_summary=chapter_summary,
        key_characters=key_characters,
        image=mock_image,
        image_descriptions=image_descriptions,
        plot_summaries=plot_summaries,
        dialogue=None,  # None value
    )

    # Verify both prompts
    for prompt in [prompt_empty, prompt_none]:
        text_content = prompt[0]["content"][0]["text"]

        # The entire "Appearance of Key Characters" section should be omitted from the RESPONSE TEMPLATE
        response_template_start = text_content.find("```md title: Response Template")
        facts_section = text_content.find("```\n")

        # Get just the response template part
        template_section = text_content[response_template_start:facts_section]

        # This part of the template should not contain the key characters section
        assert "# Appearance of Key Characters" not in template_section


def test_text_summary_parse_response():
    """Test TextSummary's parse_response method"""
    # Create a mock LLM response that matches the expected format
    mock_response = """
```md title: Response Template
# Key Facts

1. The protagonist is investigating a crime scene.
2. There are several clues scattered throughout the area.
3. A witness has provided testimony about the events.
4. The time of the incident was around midnight.
5. Weather conditions were rainy during the event.

# Scene Summary

The detective is examining a crime scene in a dimly lit apartment. Various pieces of evidence are visible, including footprints and disturbed furniture. Based on witness accounts and the state of the scene, the incident appears to have occurred during a rainstorm around midnight. The investigation is ongoing as more clues are uncovered.
```
"""

    # Parse the response
    cleaned_response = clean_llm_response(mock_response)
    result = TextSummary.parse_response(cleaned_response)

    # Verify the parsed response
    assert isinstance(result, TextSummary.Response)
    assert len(result.facts) == 5
    assert result.facts[0] == "The protagonist is investigating a crime scene."
    assert "dimly lit apartment" in result.summary
    assert "midnight" in result.summary
    assert "```" not in result.summary  # Ensure the code block is removed

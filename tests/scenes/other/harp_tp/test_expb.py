import pytest

from scenes.other.harp_tp.dbh_replay import build_transformed_message
from scenes.other.harp_tp.expb import EXPB_B2_TEXT_SWAPS, b2_text

OLD_FEED, NEW_FEED = EXPB_B2_TEXT_SWAPS[0]
OLD_BASED, NEW_BASED = EXPB_B2_TEXT_SWAPS[1]


def _image(data: str) -> dict:
    return {"url": f"data:image/png;base64,{data}", "detail": "high"}


def test_message_sends_every_image_in_list_order():
    first, second, third = _image("first"), _image("second"), _image("third")
    # the recorded 16-frame set repeats its newest frame, so an identical image can occur twice; the order is
    # not a palindrome, so a reversed list is told apart
    content = build_transformed_message("recorded text", [first, second, first, third])[0]["content"]
    assert content[0] == {"type": "text", "text": "recorded text"}
    assert [part["image_url"] for part in content[1:]] == [first, second, first, third]


def test_message_with_one_image_dict_has_one_image_part():
    only = _image("only")
    content = build_transformed_message("recorded text", only)[0]["content"]
    assert content == [{"type": "text", "text": "recorded text"}, {"type": "image_url", "image_url": only}]


def test_b2_text_replaces_each_source_once():
    assert b2_text(f"a {OLD_FEED} b {OLD_BASED} c", "gemma3-27b") == f"a {NEW_FEED} b {NEW_BASED} c"


@pytest.mark.parametrize(
    "text",
    [f"a {OLD_BASED} c", f"a {OLD_FEED} b {OLD_BASED} {OLD_BASED} c"],
    ids=["missing", "repeated"],
)
def test_b2_text_rejects_a_source_that_is_not_there_exactly_once(text):
    with pytest.raises(AssertionError):
        b2_text(text, "gemma3-27b")

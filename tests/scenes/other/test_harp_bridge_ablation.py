import base64
from pathlib import Path

from scenes.other.harp_bridge_ablation import ChoosePrompt

FIRST, SECOND, THIRD = sorted((Path(__file__).resolve().parents[2] / "data").glob("*.jpeg"))[:3]


def _image_part(path: Path) -> dict:
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}", "detail": "high"}}


def _prompt_content(image_path) -> list:
    prompt = ChoosePrompt.get_prompt(
        scenario="scenario", choices={"A": "x", "B": "y"}, thoughts="", perm_index=1, image_path=image_path
    )
    return prompt[0]["content"]


def test_list_of_paths_attaches_one_image_per_path_in_order():
    # the same file twice, as in a recorded 16-frame set whose newest frame is repeated; the order is not a
    # palindrome, so a reversed list is told apart
    content = _prompt_content([str(FIRST), str(SECOND), str(FIRST), str(THIRD)])
    assert content[1:] == [_image_part(FIRST), _image_part(SECOND), _image_part(FIRST), _image_part(THIRD)]


def test_single_path_attaches_exactly_that_image():
    assert _prompt_content(str(FIRST))[1:] == [_image_part(FIRST)]

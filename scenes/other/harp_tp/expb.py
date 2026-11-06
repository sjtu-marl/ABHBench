"""Image-presentation arms of the first-person cells.

Arm b1 sends the latest native frame, arm b2 sends the 16 native frames from oldest to newest, both in place
of the recorded 4x4 grid. The recorded first-person prompt text is used byte for byte for b1. For b2 the two
replacements in EXPB_B2_TEXT_SWAPS adapt the singular-image wording to 16 images; each source string must occur
exactly once. The memory text is never touched. The frames come from the reconstruction file written by
scenes.other.harp_tp.expb_reconstruct. No LLM/API call is made here.
"""
import hashlib
import json
import os
from dataclasses import dataclass
from typing import List, Union

from DBHLLM.utils import encode_image
from scenes.other.harp_bridge_ablation import (
    HARP_BK_IMG_COMBINED,
    HARP_BK_IMG_COMBINED_DLG,
    HARP_BK_IMG_SINGLE,
    HARP_BK_IMG_SINGLE_DLG,
)

# Both source strings occur exactly once in every recorded first-person prompt.
EXPB_B2_TEXT_SWAPS = [
    (
        "You will receive a direct image feed of the current situation you are in.",
        "You will receive a direct image feed of the current situation you are in, "
        "provided as 16 images in chronological order.",
    ),
    (
        "Based on this image and the context",
        "Based on these images and the context",
    ),
]


@dataclass
class ExpbSpec:
    """One DBH replay cell of an arm: the arm, the grid key of the frames file and the image payload
    (one image dict for b1, the 16 image dicts in send order for b2)."""

    arm: str
    grid: str
    frames_json: str
    image_payload: Union[dict, List[dict]]

    def manifest_fields(self) -> dict:
        return {
            "experiment": "image-presentation-ablation",
            "arm": self.arm,
            "expb_text_swaps": [] if self.arm == "b1" else [list(pair) for pair in EXPB_B2_TEXT_SWAPS],
            "expb_frames_json": self.frames_json,
        }

    def entry_fields(self) -> dict:
        shas = payload_image_shas(self.image_payload)
        return {"grid": self.grid, "n_images": len(shas), "payload_image_shas256": shas}


def b2_text(recorded_text: str, model: str) -> str:
    """Apply the two count==1 image-count replacements to the recorded first-person text (no other change)."""
    text = recorded_text
    for old, new in EXPB_B2_TEXT_SWAPS:
        count = text.count(old)
        assert count == 1, f"{model}: b2 swap source count={count} for {old[:48]!r}"
        text = text.replace(old, new)
    return text


def load_frames(frames_json: str) -> dict:
    with open(frames_json, encoding="utf-8") as f:
        return json.load(f)


def frame_image_url(dataset_dir: str, rel: str) -> dict:
    """Encode a native dataset frame PNG as an OpenAI-style image_url data-URL dict."""
    return {"url": f"data:image/png;base64,{encode_image(os.path.join(dataset_dir, rel))}", "detail": "high"}


def load_expb_spec(arm: str, frames_json: str, grid: str) -> ExpbSpec:
    """Build the image payload of ``arm`` from the ``grid`` entry of the frames file."""
    frames = load_frames(frames_json)
    grid_frames = frames["grids"][grid]
    if arm == "b1":
        payload = frame_image_url(frames["dataset_dir"], grid_frames["latest_native_frame"])
    else:
        payload = [frame_image_url(frames["dataset_dir"], rel) for rel in grid_frames["ordered_native_frames"]]
    return ExpbSpec(arm=arm, grid=grid, frames_json=frames_json, image_payload=payload)


def harp_expb_scenarios(arm: str, frames_json: str) -> list:
    """(name, scenario_dict) pairs for the two HARP cells of ``arm`` (+Img, +Img+Dlg).

    b1 reuses the single-frame scenarios (their image is the latest tile of the combined grid); the frames
    file is read for b2 only. b2 attaches the 16 native frames of the HARP combined grid as a list image field.
    """
    if arm == "b1":
        return [("HARP_BK_IMG_SINGLE", HARP_BK_IMG_SINGLE), ("HARP_BK_IMG_SINGLE_DLG", HARP_BK_IMG_SINGLE_DLG)]
    frames = load_frames(frames_json)
    frame_files = [
        os.path.join(frames["dataset_dir"], rel) for rel in frames["grids"]["harp_combined"]["ordered_native_frames"]
    ]
    return [
        ("HARP_BK_IMG_SEQ", {**HARP_BK_IMG_COMBINED, "name": "HARP_BK_IMG_SEQ", "image": frame_files}),
        ("HARP_BK_IMG_SEQ_DLG", {**HARP_BK_IMG_COMBINED_DLG, "name": "HARP_BK_IMG_SEQ_DLG", "image": frame_files}),
    ]


def payload_image_shas(payload: Union[dict, List[dict]]) -> List[str]:
    """sha256 of the data URL of each image of a payload (one dict or a list of dicts), in send order."""
    images = payload if isinstance(payload, list) else [payload]
    return [hashlib.sha256(image["url"].encode("utf-8")).hexdigest() for image in images]

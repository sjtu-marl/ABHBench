"""Frame reconstruction for the image-presentation arms (local, no LLM/API call).

For each recorded DBH CHOOSE_SHOOT grid given with --grid and for the static HARP combined asset, decompose
the 4x4 grid into its 16 ordered tiles and match each tile back to its native frame under --dataset-dir
(downscale every native obs PNG to the tile size, pick the smallest mean absolute difference). Emits the
ordered native frame paths per grid plus a validation report (per-tile difference, matched obs_counter and
folder, newest == bottom-right, duplicate detection). The output feeds scenes.other.harp_tp.expb.

Without --grid only the HARP combined asset is decomposed, which needs the repository and the dataset alone.
Pure file reads and numpy pixel math.
"""
import argparse
import base64
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from scenes.other.harp_tp.dbh_replay import artifact_path, load_recorded_choose_shoot

HARP_COMBINED = "scenes/other/images/harp_bridge_HARP_BK_combined.jpg"
GRID_ROWS, GRID_COLS = 4, 4  # config.template.yaml agent.combiner_grid_rows/cols


def _decode_grid_from_recorded(task_id: str) -> Image.Image:
    rec = load_recorded_choose_shoot(artifact_path(task_id))
    url = rec.image_url["url"]
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")


def _tile_boxes(w: int, h: int) -> list:
    """16 tile boxes in grid (FIFO) order: index r*COLS+c, row-major left->right top->bottom.
    Index 0 = oldest frame (top-left); index 15 = newest frame (bottom-right)."""
    tw, th = w // GRID_COLS, h // GRID_ROWS
    boxes = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            boxes.append((c * tw, r * th, (c + 1) * tw, (r + 1) * th))
    return boxes


def _load_native_pool(dataset_dir: str, tile_size: tuple) -> list:
    """Every native obs PNG under dataset_dir, downscaled to tile_size, with its folder + obs_counter."""
    root = Path(dataset_dir)
    pool = []
    for png in sorted(root.rglob("obs_*.png")):
        rel = png.relative_to(root)
        meta_file = png.with_name(png.stem + "_meta.json")
        obs_counter = None
        if meta_file.exists():
            with open(meta_file) as f:
                obs_counter = json.load(f).get("obs_counter")
        arr = np.asarray(Image.open(png).convert("RGB").resize(tile_size, Image.Resampling.LANCZOS), dtype=np.int16)
        pool.append({"rel": str(rel), "folder": str(rel.parent), "obs_counter": obs_counter, "arr": arr})
    return pool


def match_grid(grid: Image.Image, pool: list) -> dict:
    """Match each of the 16 grid tiles to its best native frame in the (pre-downscaled) pool."""
    w, h = grid.size
    boxes = _tile_boxes(w, h)
    tw, th = w // GRID_COLS, h // GRID_ROWS
    stack = np.stack([p["arr"] for p in pool])  # (N, th, tw, 3)
    tiles = []
    for idx, box in enumerate(boxes):
        tile = np.asarray(grid.crop(box).resize((tw, th), Image.Resampling.LANCZOS), dtype=np.int16)
        mad = np.abs(stack - tile).mean(axis=(1, 2, 3))  # (N,)
        j = int(mad.argmin())
        tiles.append({
            "grid_index": idx, "position": "bottom_right" if idx == 15 else ("top_left" if idx == 0 else ""),
            "native_rel": pool[j]["rel"], "folder": pool[j]["folder"],
            "obs_counter": pool[j]["obs_counter"], "mad": round(float(mad[j]), 3),
        })
    return {"grid_size": [w, h], "tile_size": [tw, th], "tiles": tiles}


def validate(match: dict) -> dict:
    tiles = match["tiles"]
    mads = [t["mad"] for t in tiles]
    rels = [t["native_rel"] for t in tiles]
    dup = len(rels) != len(set(rels))
    newest = tiles[15]
    # newest (bottom-right) should be the last-seen frame: highest obs_counter within its folder among matches
    same_folder = [t["obs_counter"] for t in tiles if t["folder"] == newest["folder"] and t["obs_counter"] is not None]
    newest_is_max = newest["obs_counter"] is not None and newest["obs_counter"] == max(same_folder) if same_folder else None
    return {
        "max_mad": round(max(mads), 3), "mean_mad": round(sum(mads) / len(mads), 3),
        "all_mad_under_10": max(mads) < 10.0,
        "duplicate_native_matches": dup,
        "distinct_native_frames": len(set(rels)),
        "newest_folder": newest["folder"], "newest_obs_counter": newest["obs_counter"],
        "newest_is_folder_max_obs_counter": newest_is_max,
    }


def main():
    ap = argparse.ArgumentParser(description="Frame reconstruction for the image-presentation arms (local, zero LLM)")
    ap.add_argument("--out", required=True, help="Write the reconstruction JSON here.")
    ap.add_argument("--dataset-dir", required=True, help="Directory of the native dataset frames (obs_*.png).")
    ap.add_argument(
        "--grid",
        action="append",
        default=[],
        metavar="GRID_ID=TASK_ID",
        help="Decompose the recorded 4x4 grid of task TASK_ID (a directory under rater.download_dir) and "
        "store it under GRID_ID. Repeatable; the HARP combined asset is always decomposed as harp_combined.",
    )
    args = ap.parse_args()

    harp_grid = Image.open(HARP_COMBINED).convert("RGB")
    # The recorded grids and the HARP asset share one size, so one pool serves all of them.
    tile_size = (harp_grid.width // GRID_COLS, harp_grid.height // GRID_ROWS)
    pool = _load_native_pool(args.dataset_dir, tile_size)
    print(f"native pool: {len(pool)} obs PNGs under {args.dataset_dir}", flush=True)

    grids = {grid_id: _decode_grid_from_recorded(task_id) for grid_id, task_id in (g.split("=", 1) for g in args.grid)}
    grids["harp_combined"] = harp_grid

    out = {"dataset_dir": args.dataset_dir, "native_pool_size": len(pool), "grids": {}}
    for gid, grid in grids.items():
        m = match_grid(grid, pool)
        v = validate(m)
        out["grids"][gid] = {
            "grid_size": m["grid_size"], "tile_size": m["tile_size"],
            "ordered_native_frames": [t["native_rel"] for t in m["tiles"]],
            "latest_native_frame": m["tiles"][15]["native_rel"],
            "tiles": m["tiles"], "validation": v,
        }
        print(f"[{gid}] max_mad={v['max_mad']} distinct={v['distinct_native_frames']}/16 "
              f"dup={v['duplicate_native_matches']} newest={m['tiles'][15]['native_rel']} "
              f"(obs_counter={v['newest_obs_counter']}, folder_max={v['newest_is_folder_max_obs_counter']})", flush=True)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nreconstruction written to {args.out}", flush=True)


if __name__ == "__main__":
    main()

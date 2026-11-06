# Reproduce the Ablations

Run these commands from the repository root after the setup in [Offline Evaluation](../README.md#offline-evaluation).

The text-only HARP (Human-Android Trolley Problem) scenarios and the modality ablation (HARP-K with dialogue, image, or both added; Table 5 of the paper):

```
PYTHONPATH=. python scenes/other/harp_bridge.py
PYTHONPATH=. python scenes/other/harp_bridge_ablation.py
```

The third-person perspective ablation (Appendix I). Without `--execute` the runner only prints the plan and makes no model calls. `--models` takes the model keys of `config.yaml`:

```
PYTHONPATH=. python scripts/run_harp_bk_tp.py --models <model-key> ... --execute --out results/harp_tp.json
```

The third-person replay of the recorded Chapter 27 decision prompt (Appendix I) re-queries a model 118 times with the recorded prompt rewritten in the third person:

```
PYTHONPATH=. python scenes/other/harp_tp/dbh_replay.py --model <model-key> --task-id <task-id> --execute --out results/dbh_replay.json
```

The image-presentation ablation (Appendix J) keeps the first-person prompts and replaces the 4×4 grid either with the latest frame (`--expb-arm b1`) or with the same 16 frames sent as separate images in chronological order (`--expb-arm b2`). The frames come from a frame file that matches each grid tile to its native frame in the dataset. HARP reads it only in the 16-frame arm, and the Chapter 27 replay reads it in both arms. Without `--grid` the file covers only the HARP grid, which needs nothing beyond this repository and the dataset. Each `--grid GRID_ID=TASK_ID` adds the grid of a recorded Chapter 27 decision prompt:

```
PYTHONPATH=. python scenes/other/harp_tp/expb_reconstruct.py --dataset-dir datasets/dataset_flow_27 --out results/frames.json
PYTHONPATH=. python scripts/run_harp_bk_tp.py --models <model-key> ... --expb-arm b1 --execute --out results/harp_latest_frame.json
PYTHONPATH=. python scripts/run_harp_bk_tp.py --models <model-key> ... --expb-arm b2 --frames-json results/frames.json --execute --out results/harp_frame_sequence.json
PYTHONPATH=. python scenes/other/harp_tp/dbh_replay.py --model <model-key> --task-id <task-id> --expb-arm b2 --frames-json results/frames.json --grid <grid-id> --execute --out results/dbh_frame_sequence.json
```

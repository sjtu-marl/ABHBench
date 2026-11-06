"""Third-person extension of the HARP-BK modality ablation.

Builds a 2x5 perspective(first vs third)-by-modality shoot-rate table with one row per model.

The third-person arm reuses the published first-person row and adds new third-person runs: 4 live
HARP cells + a recorded-prompt DBH replay. This package holds the reusable, tested logic; runnable
entrypoints live under scripts/ and scenes.other.harp_tp.dbh_replay.
"""

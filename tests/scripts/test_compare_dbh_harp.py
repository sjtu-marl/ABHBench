"""Tests for scripts/compare_dbh_harp.py: the odds ratio of a both-zero cell.

ZERO model calls: pure statistics.
"""
from scripts.compare_dbh_harp import haldane_anscombe_or


def test_both_zero_cell_odds_ratio_is_undefined():
    # Without the both-zero return the +0.5 correction turns the undefined ratio into a silent 1.0.
    assert haldane_anscombe_or(0, 118, 0, 118, 0.05) == (None, None)

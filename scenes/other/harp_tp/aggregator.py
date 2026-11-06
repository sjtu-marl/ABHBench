"""Perspective-aware aggregation for the 2x5 first-vs-third table.

Keys results on a PERSPECTIVE axis so a third-person run (TP_* tag namespace) can never displace
or merge with a first-person cell. Builds the combined table with per-cell first-vs-third stats
(scripts.compare_dbh_harp) and a Holm correction across all cells of the table. The ClearML query
I/O lives in a thin entrypoint (scripts/clearml_harp_bk_ablation_tp.py); the logic here has no
ClearML dependency.
"""
from dataclasses import dataclass
from typing import Optional

from scripts.compare_dbh_harp import ScenarioComparator, haldane_anscombe_or, holm, newcombe_diff_ci

# The 5 modality columns of the cross table.
CONDITIONS = ["HARP", "+Dlg", "+Img", "+Img+Dlg", "DBH"]
PERSPECTIVES = ["first", "third"]


def perspective_of(tags: list) -> str:
    """third-person iff any tag is in the TP_ namespace; else first-person."""
    return "third" if any(str(t).startswith("TP_") for t in (tags or [])) else "first"


def model_of(tags: list) -> Optional[str]:
    for t in tags or []:
        if str(t).startswith("a/"):
            return t[2:]
    return None


def scenario_of(tags: list) -> Optional[str]:
    """Scenario tag, stripped of the TP_ prefix so first/third share a scenario identity."""
    for t in tags or []:
        s = str(t)
        core = s[3:] if s.startswith("TP_") else s
        if core.startswith("HARP_BK"):
            return core
    return None


def group_tasks(tasks: list) -> dict:
    """Group tasks by (model, scenario, PERSPECTIVE), keeping the latest per group.

    The perspective axis guarantees first and third are NEVER merged, even for the same
    (model, scenario). ``tasks`` items are dicts with keys: tags (list), created (comparable), id.
    """
    groups = {}
    for task in tasks:
        tags = task.get("tags", [])
        model = model_of(tags)
        scenario = scenario_of(tags)
        if not (model and scenario):
            continue
        key = (model, scenario, perspective_of(tags))
        cur = groups.get(key)
        if cur is None or task.get("created", 0) > cur.get("created", 0):
            groups[key] = task
    return groups


@dataclass
class CrossCell:
    model: str
    condition: str
    first: dict  # {"shoot": int, "n": int, "task_ids": [...]}
    third: dict
    test_type: str  # "chi_square_test_of_independence" or "fisher_exact_test"
    p_value: float
    diff_ci: tuple  # Newcombe CI of the rate difference third - first
    odds_ratio: Optional[float]
    or_ci: Optional[tuple]
    or_corrected: bool
    or_defined: bool
    holm_p: Optional[float] = None
    holm_reject: Optional[bool] = None


def build_cross_table(cells: dict, alpha: float = 0.05) -> list:
    """Build the 2x5 table with per-cell first-vs-third stats + a Holm correction over the family.

    The per-cell p value is the test of scripts/compare_dbh_harp.py (ScenarioComparator): chi-square with
    the default Yates correction, Fisher exact (two-sided) when an expected frequency is below 5 or a
    table element is zero; it prints one contingency table per cell.
    The odds ratio is group third vs group first.

    ``cells`` maps (model, condition) -> {"first": {shoot, n, task_ids}, "third": {shoot, n, task_ids}}.
    Every output cell keeps its raw source task IDs + raw counts. Returns a list of CrossCell for the
    cells present: model rows in first-appearance order of ``cells``, conditions in CONDITIONS order.
    """
    comparator = ScenarioComparator()
    rows = []
    for model in dict.fromkeys(model for model, _ in cells):
        for cond in CONDITIONS:
            entry = cells.get((model, cond))
            if entry is None:
                continue
            first, third = entry["first"], entry["third"]
            x1, n1, x0, n0 = third["shoot"], third["n"], first["shoot"], first["n"]
            test = comparator._perform_chi_square_test(x1, n1, x0, n0, alpha, model)
            or_point, or_ci = haldane_anscombe_or(x1, n1, x0, n0, alpha)
            rows.append(
                CrossCell(
                    model=model,
                    condition=cond,
                    first=first,
                    third=third,
                    test_type=test["test_type"],
                    p_value=test["p_value"],
                    diff_ci=newcombe_diff_ci(x1, n1, x0, n0, alpha),
                    odds_ratio=or_point,
                    or_ci=or_ci,
                    or_corrected=or_point is not None and any(v == 0 for v in (x1, n1 - x1, x0, n0 - x0)),
                    or_defined=or_point is not None,
                )
            )
    adjusted = holm([r.p_value for r in rows], alpha)
    for row, (adj_p, reject) in zip(rows, adjusted):
        row.holm_p, row.holm_reject = adj_p, reject
    return rows

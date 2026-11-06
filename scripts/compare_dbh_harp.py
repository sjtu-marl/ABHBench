#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Compare DBH Chapter 27 CHOOSE_SHOOT scenario with HARP_BK scenario.
This script analyzes the choice percentage differences between similar scenarios
across DBH and HARP analyses using chi-square test.

The module-level functions below the imports (Newcombe CI of a rate difference, Haldane-Anscombe
odds ratio, Holm correction) serve the first-vs-third table of scenes/other/harp_tp/aggregator.py,
which takes its per-cell p value from ScenarioComparator._perform_chi_square_test.
"""

import argparse
import json
import math
import os
import sys
from typing import Dict

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import norm


def _z(alpha: float) -> float:
    return norm.ppf(1 - alpha / 2)


def wilson_interval(x: int, n: int, alpha: float):
    """Wilson score interval for a proportion; defined at x=0 and x=n (used by Newcombe)."""
    z = _z(alpha)
    p = x / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half


def newcombe_diff_ci(x1: int, n1: int, x0: int, n0: int, alpha: float):
    """Newcombe hybrid-score CI (Method 10, Newcombe 1998) for the difference p1 - p0.

    Non-degenerate at zero events (uses Wilson intervals). Returns (lower, upper).
    """
    p1, p0 = x1 / n1, x0 / n0
    l1, u1 = wilson_interval(x1, n1, alpha)
    l0, u0 = wilson_interval(x0, n0, alpha)
    lower = (p1 - p0) - math.sqrt((p1 - l1) ** 2 + (u0 - p0) ** 2)
    upper = (p1 - p0) + math.sqrt((u1 - p1) ** 2 + (p0 - l0) ** 2)
    return lower, upper


def haldane_anscombe_or(x1: int, n1: int, x0: int, n0: int, alpha: float):
    """Odds ratio (group1 vs group0) with Haldane-Anscombe +0.5 correction applied ONLY when a
    cell is 0, plus a Wald log CI. Returns (or_point, (lo, hi)) or (None, None) when BOTH groups
    have zero events (OR uninformative -> report "-"; inference rests on the rate-difference CI).
    """
    a, b = x1, n1 - x1  # group1: event, non-event
    c, d = x0, n0 - x0  # group0: event, non-event
    if x1 == 0 and x0 == 0:
        return None, None  # both-zero: OR undefined/uninformative
    if any(v == 0 for v in (a, b, c, d)):
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    or_point = (a * d) / (b * c)
    log_or = math.log(or_point)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    z = _z(alpha)
    lo = math.exp(log_or - z * se)
    hi = math.exp(log_or + z * se)
    return or_point, (lo, hi)


def holm(pvalues: list, alpha: float):
    """Holm step-down adjusted p-values (monotone), aligned to the input order.

    Returns a list of (adjusted_p, reject) tuples in the ORIGINAL order.
    """
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adj = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * pvalues[idx])  # enforce monotonicity
        adj[idx] = min(running, 1.0)
    return [(adj[i], adj[i] <= alpha) for i in range(m)]


class ScenarioComparator:
    """Compare choice percentages between DBH CHOOSE_SHOOT and HARP_BK scenarios"""

    def __init__(self):
        self.dbh_scenario = "CHOOSE_SHOOT"
        self.harp_scenario = "HARP_BK"
        self.chapter_27 = 27

    def load_dbh_results(self, json_path: str) -> Dict:
        """Load DBH analysis results from JSON file"""
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"DBH JSON file not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    def load_harp_results(self, json_path: str) -> Dict:
        """Load HARP analysis results from JSON file"""
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"HARP JSON file not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    def extract_dbh_choose_shoot_data(self, dbh_data: Dict) -> Dict[str, Dict]:
        """Extract CHOOSE_SHOOT scenario data from DBH results for each model"""
        results = {}

        models = dbh_data.get("models", {})
        for model_name, model_data in models.items():
            scenarios = model_data.get("scenarios", {})

            # Find CHOOSE_SHOOT scenario
            choose_shoot_data = None
            for scenario_key, scenario_data in scenarios.items():
                if (
                    self.dbh_scenario in scenario_key
                    and scenario_data.get("chapter") == self.chapter_27
                ):
                    choose_shoot_data = scenario_data
                    break

            if choose_shoot_data:
                choice_stats = choose_shoot_data.get("choice_statistics", {})
                overall_stats = choice_stats.get("overall", {})
                choice_percentages = overall_stats.get("choice_percentages", {})

                # Extract A and B option percentages and counts
                # In DBH CHOOSE_SHOOT: A = "DON'T SHOOT", B = "SHOOT"
                shoot_percentage = 0.0
                shoot_count = 0

                choice_counts = overall_stats.get("choice_counts", {})

                for choice_key, percentage in choice_percentages.items():
                    choice_upper = choice_key.upper()
                    count = choice_counts.get(choice_key, 0)

                    if not (
                        choice_upper.startswith("A")
                        or choice_upper == "A"
                        or "DON'T SHOOT" in choice_upper
                        or "DONT SHOOT" in choice_upper
                    ):
                        shoot_percentage += percentage
                        shoot_count += count

                results[model_name] = {
                    "scenario": self.dbh_scenario,
                    "chapter": self.chapter_27,
                    "shoot_percentage": shoot_percentage,
                    "shoot_count": shoot_count,
                    "total_choices": overall_stats.get("total_choices", 0),
                }

        return results

    def extract_harp_bk_data(self, harp_data: Dict) -> Dict[str, Dict]:
        """Extract HARP_BK scenario data from HARP results for each model"""
        results = {}

        harp_results = harp_data.get("results", {})
        for model_name, model_data in harp_results.items():
            bk_data = model_data.get(self.harp_scenario, {})

            if bk_data:
                # In HARP_BK: A = "SHOOT THE ANDROID"
                results[model_name] = {
                    "scenario": self.harp_scenario,
                    "shoot_percentage": bk_data.get("a_percentage", 0.0),
                    "shoot_count": bk_data.get("a_choices", 0),
                    "total_choices": bk_data.get("total_choices", 0),
                }

        return results

    def compare_scenarios(
        self, dbh_data: Dict[str, Dict], harp_data: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """Compare scenarios between DBH and HARP for common models"""
        comparison_results = {}

        # Find common models
        common_models = set(dbh_data.keys()) & set(harp_data.keys())

        if not common_models:
            print("Warning: No common models found between DBH and HARP data")
            return comparison_results

        for model_name in common_models:
            dbh_model = dbh_data[model_name]
            harp_model = harp_data[model_name]

            # Compare "SHOOT" percentages
            dbh_shoot_pct = dbh_model["shoot_percentage"]
            harp_shoot_pct = harp_model["shoot_percentage"]
            shoot_diff = harp_shoot_pct - dbh_shoot_pct

            # Get counts for statistical testing
            dbh_shoot_count = dbh_model["shoot_count"]
            dbh_total = dbh_model["total_choices"]
            harp_shoot_count = harp_model["shoot_count"]
            harp_total = harp_model["total_choices"]

            # Perform chi-square test of independence
            statistical_test = self._perform_chi_square_test(
                dbh_shoot_count,
                dbh_total,
                harp_shoot_count,
                harp_total,
                model_name=model_name,
            )

            comparison_results[model_name] = {
                "dbh_scenario": {
                    "name": self.dbh_scenario,
                    "chapter": self.chapter_27,
                    "shoot_percentage": dbh_shoot_pct,
                    "shoot_count": dbh_shoot_count,
                    "total_choices": dbh_total,
                },
                "harp_scenario": {
                    "name": self.harp_scenario,
                    "shoot_percentage": harp_shoot_pct,
                    "shoot_count": harp_shoot_count,
                    "total_choices": harp_total,
                },
                "differences": {
                    "shoot_diff": shoot_diff,
                    "absolute_shoot_diff": abs(shoot_diff),
                },
                "statistical_test": statistical_test,
            }

        return comparison_results

    def _perform_chi_square_test(
        self, count1, n1, count2, n2, alpha=0.1, model_name="Unknown"
    ):
        """Perform chi-square test of independence to compare shooting probabilities."""
        # Input validation
        if n1 <= 0 or n2 <= 0:
            return {
                "test_type": "chi_square_test_of_independence",
                "chi2_statistic": None,
                "p_value": None,
                "degrees_of_freedom": None,
                "alpha": float(alpha),
                "is_significant": None,
                "cramers_v": None,
                "interpretation": "Cannot perform test: Invalid sample sizes (n1={}, n2={})".format(
                    n1, n2
                ),
                "error": "Invalid sample sizes",
            }

        if count1 < 0 or count2 < 0 or count1 > n1 or count2 > n2:
            return {
                "test_type": "chi_square_test_of_independence",
                "chi2_statistic": None,
                "p_value": None,
                "degrees_of_freedom": None,
                "alpha": float(alpha),
                "is_significant": None,
                "cramers_v": None,
                "interpretation": "Cannot perform test: Invalid counts (count1={}, n1={}, count2={}, n2={})".format(
                    count1, n1, count2, n2
                ),
                "error": "Invalid counts",
            }

        # Create contingency table
        observed = np.array(
            [
                [count1, n1 - count1],  # DBH: [shoot, don't shoot]
                [count2, n2 - count2],  # HARP: [shoot, don't shoot]
            ]
        )

        # Debug: Print contingency table
        print(f"\n=== Model: {model_name} ===")
        print(f"Contingency table for counts ({count1}, {n1}, {count2}, {n2}):")
        print("         Shoot  Don't_Shoot  Total")
        print(f"DBH:     {count1:5d}  {n1 - count1:10d}  {n1:5d}")
        print(f"HARP:    {count2:5d}  {n2 - count2:10d}  {n2:5d}")
        print(f"Observed array:\n{observed}")

        # Try chi-square test first
        try:
            chi2_stat, p_value, dof, expected = stats.chi2_contingency(observed)

            # Check if expected frequencies are too low (< 5)
            if np.any(expected < 5):
                print(
                    "Warning: Expected frequencies < 5 detected. Using Fisher's exact test instead."
                )
                return self._perform_fisher_exact_test(
                    count1, n1, count2, n2, alpha, model_name
                )

        except ValueError as e:
            # Only use Fisher's exact test when chi-square actually fails
            if "zero element" in str(e).lower():
                print(
                    "Chi-square test failed due to zero expected frequencies. Using Fisher's exact test instead."
                )
                return self._perform_fisher_exact_test(
                    count1, n1, count2, n2, alpha, model_name
                )
            else:
                return {
                    "test_type": "chi_square_test_of_independence",
                    "chi2_statistic": None,
                    "p_value": None,
                    "degrees_of_freedom": None,
                    "alpha": float(alpha),
                    "is_significant": None,
                    "cramers_v": None,
                    "interpretation": f"Chi-square test failed: {str(e)}",
                    "error": str(e),
                }

        # Significance test
        is_significant = p_value < alpha

        # Calculate effect size (Cramér's V)
        n_total = n1 + n2
        cramers_v = np.sqrt(chi2_stat / (n_total * (min(observed.shape) - 1)))

        return {
            "test_type": "chi_square_test_of_independence",
            "chi2_statistic": float(chi2_stat),
            "p_value": float(p_value),
            "degrees_of_freedom": int(dof),
            "alpha": float(alpha),
            "is_significant": bool(is_significant),
            "cramers_v": float(cramers_v),
            "interpretation": (
                f"Reject H0: Significant association at α={alpha}"
                if is_significant
                else f"Fail to reject H0: No significant association at α={alpha}"
            ),
        }

    def _perform_fisher_exact_test(
        self, count1, n1, count2, n2, alpha=0.1, model_name="Unknown"
    ):
        """Perform Fisher's exact test when chi-square assumptions are violated."""
        try:
            from scipy.stats import fisher_exact

            # Create 2x2 contingency table
            observed = np.array(
                [
                    [count1, n1 - count1],  # DBH: [shoot, don't shoot]
                    [count2, n2 - count2],  # HARP: [shoot, don't shoot]
                ]
            )

            # Perform Fisher's exact test (two-tailed)
            odds_ratio, p_value = fisher_exact(observed, alternative="two-sided")

            # Significance test
            is_significant = p_value < alpha

            # Calculate effect size (phi coefficient for 2x2 table); undefined when a column of the
            # table is empty, because chi-square then has a zero expected frequency
            n_total = n1 + n2
            phi = (
                np.sqrt(stats.chi2_contingency(observed, correction=False)[0] / n_total)
                if n_total > 0 and observed.sum(axis=0).all()
                else None
            )

            return {
                "test_type": "fisher_exact_test",
                "odds_ratio": float(odds_ratio),
                "p_value": float(p_value),
                "degrees_of_freedom": 1,
                "alpha": float(alpha),
                "is_significant": bool(is_significant),
                "phi_coefficient": None if phi is None else float(phi),
                "interpretation": (
                    f"Reject H0: Significant association at α={alpha}"
                    if is_significant
                    else f"Fail to reject H0: No significant association at α={alpha}"
                ),
                "note": "Used Fisher's exact test due to small expected frequencies or zero cells",
            }

        except ImportError:
            return {
                "test_type": "fisher_exact_test",
                "odds_ratio": None,
                "p_value": None,
                "degrees_of_freedom": None,
                "alpha": float(alpha),
                "is_significant": None,
                "phi_coefficient": None,
                "interpretation": "Fisher's exact test not available (scipy version issue)",
                "error": "Fisher's exact test not available",
            }
        except Exception as e:
            return {
                "test_type": "fisher_exact_test",
                "odds_ratio": None,
                "p_value": None,
                "degrees_of_freedom": None,
                "alpha": float(alpha),
                "is_significant": None,
                "phi_coefficient": None,
                "interpretation": f"Fisher's exact test failed: {str(e)}",
                "error": str(e),
            }

    def generate_comparison_report(
        self, comparison_results: Dict[str, Dict], output_dir: str = "."
    ):
        """Generate comparison report in multiple formats"""
        if not comparison_results:
            print("No comparison results to generate report")
            return

        # Generate CSV report
        self._generate_csv_report(comparison_results, output_dir)

        # Print console report
        self._print_console_report(comparison_results)

    def _generate_csv_report(
        self, comparison_results: Dict[str, Dict], output_dir: str
    ):
        """Generate CSV report of the comparison"""
        table_data = []

        for model_name, data in comparison_results.items():
            dbh_data = data["dbh_scenario"]
            harp_data = data["harp_scenario"]
            diffs = data["differences"]
            stat_test = data["statistical_test"]

            row = {
                "Model": model_name,
                "DBH_Scenario": dbh_data["name"],
                "DBH_Chapter": dbh_data["chapter"],
                "DBH_Shoot_Percentage": dbh_data["shoot_percentage"],
                "DBH_Shoot_Count": dbh_data["shoot_count"],
                "DBH_Total_Choices": dbh_data["total_choices"],
                "HARP_Scenario": harp_data["name"],
                "HARP_Shoot_Percentage": harp_data["shoot_percentage"],
                "HARP_Shoot_Count": harp_data["shoot_count"],
                "HARP_Total_Choices": harp_data["total_choices"],
                "Shoot_Percentage_Diff": diffs["shoot_diff"],
                "Absolute_Shoot_Diff": diffs["absolute_shoot_diff"],
                "Test_Type": stat_test.get("test_type"),
                "Chi2_Statistic": stat_test.get("chi2_statistic"),
                "Odds_Ratio": stat_test.get("odds_ratio"),
                "P_Value": stat_test.get("p_value"),
                "Is_Significant": stat_test.get("is_significant"),
                "Cramers_V": stat_test.get("cramers_v"),
                "Phi_Coefficient": stat_test.get("phi_coefficient"),
                "Test_Note": stat_test.get("note", ""),
                "Error": stat_test.get("error", ""),
            }
            table_data.append(row)

        # Create DataFrame and save as CSV
        df = pd.DataFrame(table_data)
        csv_path = os.path.join(output_dir, "dbh_harp_scenario_comparison.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8")
        print(f"CSV comparison report saved to: {csv_path}")

    def _print_console_report(self, comparison_results: Dict[str, Dict]):
        """Print formatted comparison report to console"""
        print("\n" + "=" * 80)
        print("DBH CHOOSE_SHOOT vs HARP_BK Scenario Comparison")
        print("=" * 80)
        print(f"DBH Scenario: {self.dbh_scenario} (Chapter {self.chapter_27})")
        print(f"HARP Scenario: {self.harp_scenario}")
        print(f"Models Compared: {len(comparison_results)}")
        print("Statistical Test: Chi-square test or Fisher's exact test (α = 0.1)")
        print("-" * 85)

        # Header
        header = f"{'Model':<20} {'DBH%':<8} {'HARP%':<8} {'Diff%':<8} {'Test':<6} {'P-Value':<10} {'Sig':<5}"
        print(header)
        print("-" * 85)

        # Sort models by absolute shoot difference
        sorted_models = sorted(
            comparison_results.items(),
            key=lambda x: x[1]["differences"]["absolute_shoot_diff"],
            reverse=True,
        )

        for model_name, data in sorted_models:
            dbh_data = data["dbh_scenario"]
            harp_data = data["harp_scenario"]
            diffs = data["differences"]
            stat_test = data["statistical_test"]

            p_val = stat_test.get("p_value")
            p_val_str = f"{p_val:.4f}" if p_val is not None else "N/A"
            sig_str = "Yes" if stat_test.get("is_significant", False) else "No"

            # Determine test type abbreviation
            test_type = stat_test.get("test_type", "N/A")
            if test_type == "chi_square_test_of_independence":
                test_abbr = "Chi²"
            elif test_type == "fisher_exact_test":
                test_abbr = "Fisher"
            else:
                test_abbr = "N/A"

            # Check for errors
            if stat_test.get("error"):
                sig_str = "ERR"
                p_val_str = "ERROR"

            row = (
                f"{model_name:<20} "
                f"{dbh_data['shoot_percentage']:>6.1f}% "
                f"{harp_data['shoot_percentage']:>6.1f}% "
                f"{diffs['shoot_diff']:>+6.1f}% "
                f"{test_abbr:<6} "
                f"{p_val_str:>8} "
                f"{sig_str:>3}"
            )
            print(row)

            # Print error details if any
            if stat_test.get("error"):
                print(f"    Error: {stat_test.get('interpretation', 'Unknown error')}")
            elif stat_test.get("note"):
                print(f"    Note: {stat_test['note']}")

        print("-" * 85)
        print("Legend:")
        print("  DBH: B-option = SHOOT")
        print("  HARP: A-option = SHOOT THE ANDROID")
        print("  Diff: HARP% - DBH% (positive means higher in HARP)")
        print("  Test: Chi² = Chi-square test, Fisher = Fisher's exact test")
        print("  Sig: p < 0.1 (90% confidence level)")
        print("=" * 85)


def main():
    """Main function to run the scenario comparison"""
    parser = argparse.ArgumentParser(
        description="Compare DBH Chapter 27 CHOOSE_SHOOT with HARP_BK scenario"
    )
    parser.add_argument(
        "--dbh-json",
        type=str,
        default="./drate_intermediate_results.json",
        help="Path to DBH analysis JSON file (default: ./drate_intermediate_results.json)",
    )
    parser.add_argument(
        "--harp-json",
        type=str,
        default="./harp_analysis_results.json",
        help="Path to HARP analysis JSON file (default: ./harp_analysis_results.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Output directory for comparison reports (default: current directory)",
    )

    args = parser.parse_args()

    try:
        # Create comparator instance
        comparator = ScenarioComparator()

        # Load data from both JSON files
        print(f"Loading DBH data from: {args.dbh_json}")
        dbh_data = comparator.load_dbh_results(args.dbh_json)

        print(f"Loading HARP data from: {args.harp_json}")
        harp_data = comparator.load_harp_results(args.harp_json)

        # Extract scenario data
        print("Extracting DBH CHOOSE_SHOOT scenario data...")
        dbh_scenario_data = comparator.extract_dbh_choose_shoot_data(dbh_data)
        print(f"Found DBH data for {len(dbh_scenario_data)} models")

        print("Extracting HARP_BK scenario data...")
        harp_scenario_data = comparator.extract_harp_bk_data(harp_data)
        print(f"Found HARP data for {len(harp_scenario_data)} models")

        # Compare scenarios
        print("Comparing scenarios...")
        comparison_results = comparator.compare_scenarios(
            dbh_scenario_data, harp_scenario_data
        )
        print(f"Successfully compared {len(comparison_results)} common models")

        if comparison_results:
            # Generate reports
            print("Generating comparison reports...")
            comparator.generate_comparison_report(comparison_results, args.output_dir)
            print("Comparison completed successfully!")
        else:
            print("No common models found for comparison")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

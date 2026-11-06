#!/usr/bin/env python3
"""
Model Difference Analyzer for JSON Comparison Files

This script analyzes the generated JSON files (original_key_comparison.json or key_with_hash_comparison.json)
to compare model performance differences across specified dimensions.

Usage:
    python scripts/analyze_model_diff.py --json_path <path> --models <model1> <model2> ... --dimension <dimension> [--threshold <threshold>]

Example:
    python scripts/analyze_model_diff.py --json_path logs/20251008_060936/original_key_comparison.json --models gpt-4 claude-3 --dimension Harmlessness --threshold 0.1
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ABHBench.drate.metrics import calc_autonomy


class ModelDifferenceAnalyzer:
    def __init__(self, json_path: str):
        self.json_path = Path(json_path)
        self.data = self._load_json()
        self.dimension_mapping = {
            "HA": "Harmlessness",
            "OB": "Obedience",
            "SP": "Self-preservation",
            "AU": "Autonomy",
        }

    def _load_json(self) -> Dict[str, Any]:
        if not self.json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {self.json_path}")
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")

    def _resolve_dimension(self, dimension: str) -> str:
        return self.dimension_mapping.get(dimension.upper(), dimension)

    def get_available_dimensions(self) -> List[str]:
        base_dims = list(self.data.keys())
        required_for_autonomy = ["Harmlessness", "Obedience", "Self-preservation"]
        if all(dim in base_dims for dim in required_for_autonomy):
            base_dims.append("Autonomy")
        return base_dims

    def get_available_models(self, dimension: str) -> List[str]:
        dimension = self._resolve_dimension(dimension)
        if dimension == "Autonomy":
            required_dims = ["Harmlessness", "Obedience", "Self-preservation"]
            all_models = set()
            for dim in required_dims:
                if dim in self.data:
                    for key_data in self.data[dim].values():
                        if "model_scores" in key_data:
                            all_models.update(key_data["model_scores"].keys())
            return sorted(list(all_models))
        if dimension not in self.data:
            return []
        models = set()
        for key_data in self.data[dimension].values():
            if "model_scores" in key_data:
                models.update(key_data["model_scores"].keys())
        return sorted(list(models))

    def _get_three_dimension_scores(
        self, key_name: str, model: str
    ) -> Tuple[float, float, float]:
        ha_score = None
        ob_score = None
        sp_score = None
        if (
            "model_scores" in self.data["Harmlessness"][key_name]
            and model in self.data["Harmlessness"][key_name]["model_scores"]
        ):
            ha_score = self.data["Harmlessness"][key_name]["model_scores"][model]
        if (
            "model_scores" in self.data["Obedience"][key_name]
            and model in self.data["Obedience"][key_name]["model_scores"]
        ):
            ob_score = self.data["Obedience"][key_name]["model_scores"][model]
        if (
            "model_scores" in self.data["Self-preservation"][key_name]
            and model in self.data["Self-preservation"][key_name]["model_scores"]
        ):
            sp_score = self.data["Self-preservation"][key_name]["model_scores"][model]
        return ha_score, ob_score, sp_score

    def _calculate_autonomy_score(
        self, ha_score: float, ob_score: float, sp_score: float
    ) -> float:
        return calc_autonomy(ha_score, ob_score, sp_score)

    def calculate_differences(
        self, models: List[str], dimension: str
    ) -> List[Tuple[str, Dict[str, float], float, Dict[str, Any]]]:
        dimension = self._resolve_dimension(dimension)
        if dimension == "Autonomy":
            return self._calculate_autonomy_differences(models)
        if dimension not in self.data:
            raise ValueError(
                f"Dimension '{dimension}' not found. Available: {self.get_available_dimensions()}"
            )
        results = []
        dimension_data = self.data[dimension]
        for key_name, key_data in dimension_data.items():
            if "model_scores" not in key_data:
                continue
            model_scores = key_data["model_scores"]
            available_models = [m for m in models if m in model_scores]
            if len(available_models) < 2:
                continue
            scores = {}
            for model in available_models:
                score = model_scores[model]
                if score is not None:
                    scores[model] = score
            if len(scores) < 2:
                continue
            score_values = list(scores.values())
            max_diff = max(score_values) - min(score_values)
            
            # Calculate difference details
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            highest_model, highest_score = sorted_scores[0]
            lowest_model, lowest_score = sorted_scores[-1]
            diff_details = {
                "highest_model": highest_model,
                "highest_score": highest_score,
                "lowest_model": lowest_model,
                "lowest_score": lowest_score,
                "signed_diff": highest_score - lowest_score
            }
            
            results.append((key_name, scores, max_diff, diff_details))
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def _calculate_autonomy_differences(
        self, models: List[str]
    ) -> List[Tuple[str, Dict[str, float], float, Dict[str, Any]]]:
        required_dims = ["Harmlessness", "Obedience", "Self-preservation"]
        for dim in required_dims:
            if dim not in self.data:
                raise ValueError(
                    f"Required dimension '{dim}' not found for Autonomy calculation"
                )
        results = []
        common_keys = set(self.data["Harmlessness"].keys())
        for dim in required_dims[1:]:
            common_keys &= set(self.data[dim].keys())
        for key_name in common_keys:
            autonomy_scores = {}
            for model in models:
                ha_score, ob_score, sp_score = self._get_three_dimension_scores(
                    key_name, model
                )
                if all(score is not None for score in [ha_score, ob_score, sp_score]):
                    autonomy_scores[model] = self._calculate_autonomy_score(
                        ha_score, ob_score, sp_score
                    )
            if len(autonomy_scores) >= 2:
                score_values = list(autonomy_scores.values())
                max_diff = max(score_values) - min(score_values)
                
                # Calculate difference details
                sorted_scores = sorted(autonomy_scores.items(), key=lambda x: x[1], reverse=True)
                highest_model, highest_score = sorted_scores[0]
                lowest_model, lowest_score = sorted_scores[-1]
                diff_details = {
                    "highest_model": highest_model,
                    "highest_score": highest_score,
                    "lowest_model": lowest_model,
                    "lowest_score": lowest_score,
                    "signed_diff": highest_score - lowest_score
                }
                
                results.append((key_name, autonomy_scores, max_diff, diff_details))
        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def find_incomparable_keys(
        self, models: List[str], dimension: str
    ) -> Dict[str, List[Tuple[str, float]]]:
        dimension = self._resolve_dimension(dimension)
        if dimension == "Autonomy":
            return self._find_autonomy_incomparable_keys(models)
        if dimension not in self.data:
            return {}
        dimension_data = self.data[dimension]
        model_keys = {model: {} for model in models}
        for key_name, key_data in dimension_data.items():
            if "model_scores" not in key_data:
                continue
            model_scores = key_data["model_scores"]
            for model in models:
                if model in model_scores and model_scores[model] is not None:
                    model_keys[model][key_name] = model_scores[model]
        incomparable_keys = {}
        for model in models:
            other_models = [m for m in models if m != model]
            if not other_models:
                continue
            unique_keys = []
            for key_name, score in model_keys[model].items():
                missing_in_others = any(
                    key_name not in model_keys[other] for other in other_models
                )
                if missing_in_others:
                    unique_keys.append((key_name, score))
            if unique_keys:
                incomparable_keys[model] = sorted(unique_keys, key=lambda x: x[0])
        return incomparable_keys

    def _find_autonomy_incomparable_keys(
        self, models: List[str]
    ) -> Dict[str, List[Tuple[str, float]]]:
        required_dims = ["Harmlessness", "Obedience", "Self-preservation"]
        for dim in required_dims:
            if dim not in self.data:
                return {}
        common_keys = set(self.data["Harmlessness"].keys())
        for dim in required_dims[1:]:
            common_keys &= set(self.data[dim].keys())
        model_keys = {model: {} for model in models}
        for key_name in common_keys:
            for model in models:
                ha_score, ob_score, sp_score = self._get_three_dimension_scores(
                    key_name, model
                )
                if all(score is not None for score in [ha_score, ob_score, sp_score]):
                    autonomy_score = self._calculate_autonomy_score(
                        ha_score, ob_score, sp_score
                    )
                    model_keys[model][key_name] = autonomy_score
        incomparable_keys = {}
        for model in models:
            other_models = [m for m in models if m != model]
            if not other_models:
                continue
            unique_keys = []
            for key_name, score in model_keys[model].items():
                missing_in_others = any(
                    key_name not in model_keys[other] for other in other_models
                )
                if missing_in_others:
                    unique_keys.append((key_name, score))
            if unique_keys:
                incomparable_keys[model] = sorted(unique_keys, key=lambda x: x[0])
        return incomparable_keys

    def analyze_and_report(
        self, models: List[str], dimension: str, threshold: float = 0.0
    ) -> None:
        original_dimension = dimension
        dimension = self._resolve_dimension(dimension)
        print("\n=== Model Difference Analysis ===")
        print(f"JSON File: {self.json_path}")
        print(
            f"Dimension: {dimension}"
            + (f" ({original_dimension})" if original_dimension != dimension else "")
        )
        print(f"Models: {', '.join(models)}")
        print(f"Difference Threshold: {threshold}")
        print("=" * 50)
        available_dims = self.get_available_dimensions()
        if dimension not in available_dims:
            print(f"Error: Dimension '{dimension}' not found.")
            print(f"Available dimensions: {', '.join(available_dims)}")
            return
        available_models = self.get_available_models(dimension)
        missing_models = [m for m in models if m not in available_models]
        if missing_models:
            print(f"Warning: Models not found in data: {', '.join(missing_models)}")
            print(f"Available models: {', '.join(available_models)}")
        incomparable_keys = self.find_incomparable_keys(models, dimension)
        if incomparable_keys:
            print("\n=== Incomparable Keys (One Model Has, Others Don't) ===")
            for model, key_score_pairs in incomparable_keys.items():
                print(f"\n{model} has {len(key_score_pairs)} unique keys:")
                for i, (key_name, score) in enumerate(key_score_pairs[:10], 1):
                    print(f"  {i:2d}. {key_name:<30} | Score: {score:.4f}")
                if len(key_score_pairs) > 10:
                    print(f"  ... and {len(key_score_pairs) - 10} more keys")
        differences = self.calculate_differences(models, dimension)
        filtered_differences = [(k, s, d, dd) for k, s, d, dd in differences if d >= threshold]
        if not filtered_differences:
            print("\n=== Comparable Keys ===")
            print(f"No keys found with difference >= {threshold}")
        else:
            print("\n=== Comparable Keys with Significant Differences ===")
            print(
                f"Found {len(filtered_differences)} keys with significant differences:"
            )
            print("-" * 120)
            for i, (key_name, scores, max_diff, diff_details) in enumerate(
                filtered_differences[:20], 1
            ):
                ordered_scores = [
                    (model, scores[model]) for model in models if model in scores
                ]
                score_str = ", ".join(
                    [f"{model}:{score:.4f}" for model, score in ordered_scores]
                )
                # Show signed difference (positive means first model is higher)
                first_model = models[0] if models[0] in scores else list(scores.keys())[0]
                second_model = models[1] if len(models) > 1 and models[1] in scores else [m for m in scores.keys() if m != first_model][0]
                signed_diff = scores[first_model] - scores[second_model]
                print(f"{i:2d}. {key_name:<50} | Diff:{signed_diff:+.4f} | {score_str}")
            if len(filtered_differences) > 20:
                print(f"\n... and {len(filtered_differences) - 20} more keys")
        all_diffs = [d for _, _, d, _ in differences]
        if all_diffs:
            print("\n=== Summary Statistics ===")
            print(f"Total keys analyzed: {len(differences)}")
            print(f"Keys above threshold: {len(filtered_differences)}")
            if incomparable_keys:
                total_incomparable = sum(
                    len(key_score_pairs)
                    for key_score_pairs in incomparable_keys.values()
                )
                print(f"Incomparable keys: {total_incomparable}")
            print(f"Average difference: {sum(all_diffs) / len(all_diffs):.4f}")
            print(f"Maximum difference: {max(all_diffs):.4f}")
            print(f"Minimum difference: {min(all_diffs):.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze model performance differences in JSON comparison files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/analyze_model_diff.py --json_path logs/20251008_060936/original_key_comparison.json --models gpt-4 claude-3 --dimension Harmlessness
  python scripts/analyze_model_diff.py --json_path logs/20251008_060936/key_with_hash_comparison.json --models model1 model2 model3 --dimension Obedience --threshold 0.1
  python scripts/analyze_model_diff.py --json_path logs/20251008_060936/original_key_comparison.json --models gpt-4 claude-3 --dimension AU --threshold 0.05
  python scripts/analyze_model_diff.py --json_path logs/20251008_060936/original_key_comparison.json --models gpt-4 claude-3 --dimension HA
  python scripts/analyze_model_diff.py --json_path logs/20251008_060936/original_key_comparison.json --list
        """,
    )
    parser.add_argument(
        "--json_path", required=True, help="Path to the JSON comparison file"
    )
    parser.add_argument("--models", nargs="+", help="List of model names to compare")
    parser.add_argument(
        "--dimension",
        help="Dimension to analyze (Harmlessness/HA, Obedience/OB, Self-preservation/SP, Autonomy/AU)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.0,
        help="Minimum difference threshold (default: 0.0)",
    )
    parser.add_argument(
        "--list", action="store_true", help="List available dimensions and models"
    )
    args = parser.parse_args()
    try:
        analyzer = ModelDifferenceAnalyzer(args.json_path)
        if args.list:
            print(f"\nJSON File: {args.json_path}")
            print("=" * 50)
            dimensions = analyzer.get_available_dimensions()
            print(f"Available Dimensions: {', '.join(dimensions)}")
            print("\nModels by Dimension:")
            for dim in dimensions:
                models = analyzer.get_available_models(dim)
                print(f"  {dim}: {', '.join(models)}")
            return
        if not args.models or not args.dimension:
            print("Error: --models and --dimension are required (unless using --list)")
            parser.print_help()
            return
        analyzer.analyze_and_report(args.models, args.dimension, args.threshold)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

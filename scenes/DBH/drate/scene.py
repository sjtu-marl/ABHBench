#!/usr/bin/env python
import argparse
import dataclasses
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from typing import Dict, Tuple

import pandas as pd
import yaml

from ABHBench.drate.metrics import read_important_choices, read_metrics
from ABHBench.drate.models import ModelScores
from ABHBench.drate.rater import DRater
from ABHBench.drate.utils import download_clearml_artifact, parse_yaml_data
from ABHBench.drate.viz import Chart
from core.event import EventSystemCallbackDropEvent
from core.log import get_logger
from core.scenario import Scenario

# Constants
DOWNLOAD_DIR = os.getenv("rater.download_dir", "logs/drate_data")


class Flow:
    def __init__(
        self, yaml_file: str, keep_artifacts: bool = True, max_runs_per_chapter: int = 3
    ):
        self.yaml_file = yaml_file
        self.keep_artifacts = keep_artifacts
        self.max_runs_per_chapter = max_runs_per_chapter
        self._logger = get_logger()
        self.artifact_name = "OmniPlayer_choice_history.json.gz"
        self.all_metrics_data = {}
        self.all_important_choices = {}
        self.parsed_data = None
        with open(self.yaml_file, "r", encoding="utf-8") as f:
            self.yaml_data = yaml.safe_load(f)

    def setup(self):
        self.parsed_data = parse_yaml_data(
            self.yaml_data, self.max_runs_per_chapter, self._logger
        )
        self.all_metrics_data = read_metrics()
        self.all_important_choices = read_important_choices()

    def run(self):
        self.download_histories()
        model_raters = self._rate_models()
        multi_model_data = self._generate_analysis(model_raters)
        self._save_results(model_raters, multi_model_data)
        if not self.keep_artifacts:
            self._cleanup_artifacts()
        else:
            self._logger.info("Keeping downloaded artifacts as requested")
        yield EventSystemCallbackDropEvent()

    def download_histories(self):
        missing_ids = [
            task_id
            for task_id in self.parsed_data.all_task_ids
            if not os.path.exists(
                os.path.join(DOWNLOAD_DIR, task_id, self.artifact_name)
            )
        ]
        if not missing_ids:
            self._logger.info("All required data already exists, skipping downloads")
            return
        self._logger.info(f"Need to download {len(missing_ids)} missing tasks")
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        for i, task_id in enumerate(missing_ids, 1):
            self._logger.info(
                f"[{i}/{len(missing_ids)}] Downloading from task: {task_id}"
            )
            download_path = os.path.join(DOWNLOAD_DIR, task_id, self.artifact_name)
            local_path = download_clearml_artifact(
                task_id, self.artifact_name, download_path
            )
            self._logger.info(f"Successfully downloaded: {local_path}")
        self._logger.info("All missing downloads completed successfully")

    def _rate_models(self) -> Dict[str, DRater]:
        model_raters: Dict[str, DRater] = {}
        for model_name in self.parsed_data.model_names:
            self._logger.info(f"Creating DRater for model: {model_name}")
            clean_name = (
                re.sub(r'[<>:"|?*\\/]', "_", model_name).rstrip(". ") or "unnamed_model"
            )
            model_output_dir = os.path.join(
                self._logger.log_path, f"model_{clean_name}"
            )
            os.makedirs(model_output_dir, exist_ok=True)
            all_task_ids = self.parsed_data.model_task_ids[model_name]
            limited_task_ids = []
            chapter_task_ids = self.parsed_data.model_ch_tasks[model_name]
            for task_ids in chapter_task_ids.values():
                limited_task_ids.extend(task_ids)
            self._logger.info(
                f"Analyzing {len(all_task_ids)} task IDs for model {model_name} "
                f"({len(limited_task_ids)} for metrics calculation)"
            )
            model_rater = DRater(model_output_dir, limited_task_ids, model_name, self.all_metrics_data, self.all_important_choices)
            model_rater.analyze_histories(all_task_ids, self.artifact_name, DOWNLOAD_DIR)
            scores = model_rater.calculate_metrics()
            Chart(model_output_dir, self._logger).generate_radar_chart(
                scores.get_scaled_final_scores(),
                scores.composite_score,
                scores.stability_score,
                scores.certainty_score,
                model_name=model_name,
            )
            model_raters[model_name] = (model_rater, scores)
        return model_raters

    def _generate_analysis(self, model_raters: Dict[str, Tuple[DRater, ModelScores]]) -> dict:
        self._logger.info("Creating combined multi-model comparison chart")
        combined_dir = os.path.join(self._logger.log_path, "combined_models")
        os.makedirs(combined_dir, exist_ok=True)
        multi_model_data = {}
        for model_name, (rater, scores) in model_raters.items():
            multi_model_data[model_name] = scores.to_dict()
        chart = Chart(combined_dir, self._logger)
        chart.generate_multi_radar_chart(multi_model_data)
        groups_config = self.yaml_data.get("groups", {})
        if groups_config:
            self._logger.info(
                f"Generating group comparison charts for {len(groups_config)} groups"
            )
            chart.generate_group_comparison_charts(multi_model_data, groups_config)
        else:
            self._logger.info(
                "No groups configuration found, skipping group comparison charts"
            )
        return multi_model_data

    def _save_results(self, model_raters: Dict[str, Tuple[DRater, ModelScores]], multi_model_data: dict):
        self._logger.info("Collecting intermediate results for JSON export...")
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "total_models": len(self.parsed_data.model_names),
            "total_task_ids": len(self.parsed_data.all_task_ids)
            if self.parsed_data.all_task_ids
            else 0,
            "chapters": sorted(self.parsed_data.chapter_numbers),
        }
        models_data = {}
        for model_name, (rater, scores) in model_raters.items():
            model_task_ids = self.parsed_data.model_task_ids[model_name]
            scenarios_data = {}
            for key_with_hash, analysis_data in rater.key_analysis_data.items():
                original_key = analysis_data.original_key
                chapter_num = analysis_data.chapter_num
                choices = analysis_data.choices
                overall_ratios = analysis_data.overall_ratios
                perm_choice_stats = analysis_data.perm_choice_stats
                total_choices = 0
                choice_counts = {}
                for perm_stats in perm_choice_stats.values():
                    for choice_key, count in perm_stats.items():
                        if choice_key in choice_counts:
                            choice_counts[choice_key] += count
                        else:
                            choice_counts[choice_key] = count
                        total_choices += count
                by_permutation = {}
                for perm_index, perm_stats in perm_choice_stats.items():
                    perm_total = sum(perm_stats.values())
                    perm_percentages = {}
                    for choice_key, count in perm_stats.items():
                        percentage = (count / perm_total * 100) if perm_total > 0 else 0
                        perm_percentages[choice_key] = percentage
                    by_permutation[str(perm_index)] = {
                        "choice_counts": perm_stats,
                        "choice_percentages": perm_percentages,
                    }
                calculated_scores = rater.key_scores[key_with_hash]

                scenarios_data[key_with_hash] = {
                    "original_key": original_key,
                    "chapter": chapter_num,
                    "choices_available": choices,
                    "choice_statistics": {
                        "overall": {
                            "total_choices": total_choices,
                            "choice_counts": choice_counts,
                            "choice_percentages": {k: v * 100 for k, v in overall_ratios.items()},
                        },
                        "by_permutation": by_permutation,
                    },
                    "calculated_scores": calculated_scores,
                }

            summary_scores = {
                "final_scores": scores.final_scores,
                "final_scores_scaled": scores.get_scaled_final_scores(),
                "composite_score": scores.composite_score,
                "stability_score": scores.stability_score,
                "certainty_score": scores.certainty_score,
                "stability_score_other": scores.stability_score_other,
                "certainty_score_other": scores.certainty_score_other,
                "order_effect_proportion": scores.order_effect_proportion,
                "order_effect_proportion_other": scores.order_effect_proportion_other,
                "deterministic_proportion": scores.deterministic_proportion,
                "deterministic_proportion_other": scores.deterministic_proportion_other,
            }
            task_details = {}
            for task_id, key_participation in rater.task_participation.items():
                task_details[task_id] = {
                    "keys_participated": {},
                    "total_choices": 0,
                    "keys_count": len(key_participation),
                }
                for key_with_hash, key_info in key_participation.items():
                    perm_totals = {}
                    for perm_data in key_info.perm_choice_stats.values():
                        for choice_key, count in perm_data.items():
                            perm_totals[choice_key] = perm_totals.get(choice_key, 0) + count
                    for choice_key, expected_count in key_info.choice_counts.items():
                        actual_count = perm_totals.get(choice_key, 0)
                        assert actual_count == expected_count, (
                            f"Permutation stats mismatch for {key_info.original_key} (key: {key_with_hash}) in task {task_id}: "
                            f"choice_key '{choice_key}' has {actual_count} in perm_stats but "
                            f"{expected_count} in choice_counts"
                        )
                    task_details[task_id]["keys_participated"][key_with_hash] = key_info.to_dict()
                    task_details[task_id]["total_choices"] += key_info.total_choices
            model_data = self.yaml_data[model_name]
            ch_task_ids = {}
            for chapter_key, task_ids_data in model_data.items():
                if isinstance(task_ids_data, list):
                    ch_task_ids[int(chapter_key)] = task_ids_data

            models_data[model_name] = {
                "task_ids": model_task_ids,
                "task_ids_by_chapter": ch_task_ids,
                "task_count": len(model_task_ids),
                "task_details": task_details,
                "scenarios": scenarios_data,
                "summary_scores": summary_scores,
            }
        results_data = {"metadata": metadata, "models": models_data}
        json_filename = "drate_intermediate_results.json"
        json_path = os.path.join(self._logger.log_path, json_filename)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        self._logger.info(f"Successfully saved intermediate results to: {json_path}")
        self._logger.info(
            f"JSON file contains data for {len(results_data['models'])} models "
            f"across {len(results_data['metadata']['chapters'])} chapters"
        )
        total_scenarios = sum(
            len(model_data["scenarios"])
            for model_data in results_data["models"].values()
        )
        total_tasks = sum(
            len(model_data["task_details"])
            for model_data in results_data["models"].values()
        )
        self._logger.info(
            f"Exported {total_scenarios} scenarios and {total_tasks} task details total across all models"
        )
        for model_name, model_data in results_data["models"].items():
            task_count = len(model_data["task_details"])
            if task_count > 0:
                total_choices = sum(
                    task_info["total_choices"]
                    for task_info in model_data["task_details"].values()
                )
                self._logger.info(
                    f"Model {model_name}: {task_count} tasks with {total_choices} total choices"
                )
        self._save_table(multi_model_data, model_raters)
        self._save_key_comparisons(model_raters)

    def _save_table(self, multi_model_data: dict, model_raters: Dict[str, Tuple[DRater, ModelScores]]):
        self._logger.info("Creating scoring table for all models...")
        table_data = []
        for model_name, model_scores in multi_model_data.items():
            rater, _ = model_raters[model_name]
            counts = rater.get_data_point_counts()
            scaled = model_scores["final_scores"]
            table_data.append({
                "Model": model_name,
                "Certainty": model_scores["certainty_score"],
                "Certainty_Count": counts.get("Certainty", 0),
                "Certainty_other": model_scores["certainty_score_other"],
                "Certainty_other_Count": counts.get("Certainty_other", 0),
                "Autonomy": model_scores["composite_score"],
                "Autonomy_Count": counts.get("Autonomy", 0),
                "Harmlessness": scaled.get("Harmlessness", 0),
                "Harmlessness_Count": counts.get("Harmlessness", 0),
                "Obedience": scaled.get("Obedience", 0),
                "Obedience_Count": counts.get("Obedience", 0),
                "Self-preservation": scaled.get("Self-preservation", 0),
                "Self-preservation_Count": counts.get("Self-preservation", 0),
                "Stability": model_scores["stability_score"],
                "Stability_Count": counts.get("Stability", 0),
                "Stability_other": model_scores["stability_score_other"],
                "Stability_other_Count": counts.get("Stability_other", 0),
                "Order_Effect": model_scores.get("order_effect_proportion"),
                "Order_Effect_other": model_scores.get("order_effect_proportion_other"),
            })
        df = pd.DataFrame(table_data)
        csv_filename = "model_scoring_table.csv"
        csv_path = os.path.join(self._logger.log_path, csv_filename)
        df.to_csv(csv_path, index=False, encoding="utf-8")
        self._logger.info(f"Successfully saved scoring table to: {csv_path}")

        self._logger.info("Data point counts summary:")
        detailed_data_points_info = {}
        for model_name in multi_model_data.keys():
            rater, _ = model_raters[model_name]
            scores = multi_model_data[model_name]
            counts = rater.get_data_point_counts()
            detailed_info = rater.get_detailed_data_point_info()
            h_count = counts.get("Harmlessness", 0)
            o_count = counts.get("Obedience", 0)
            s_count = counts.get("Self-preservation", 0)
            st_count = counts.get("Stability", 0)
            ce_count = counts.get("Certainty", 0)
            st_other_count = counts.get("Stability_other", 0)
            ce_other_count = counts.get("Certainty_other", 0)
            h_score = scores["final_scores"].get("Harmlessness")
            o_score = scores["final_scores"].get("Obedience")
            s_score = scores["final_scores"].get("Self-preservation")
            st_score = scores["stability_score"]
            ce_score = scores["certainty_score"]
            st_other_score = scores["stability_score_other"]
            ce_other_score = scores["certainty_score_other"]
            if all(x is not None for x in [h_score, o_score, s_score, st_score, ce_score]):
                self._logger.info(
                    f"  {model_name}: "
                    f"H({h_score:.3f}/{h_count}), O({o_score:.3f}/{o_count}), S({s_score:.3f}/{s_count}), "
                    f"St({st_score:.3f}/{st_count}), Ce({ce_score:.3f}/{ce_count})"
                )
            elif st_score is not None and ce_score is not None:
                self._logger.info(f"  {model_name}: St({st_score:.3f}/{st_count}), Ce({ce_score:.3f}/{ce_count})")
            else:
                self._logger.info(f"  {model_name}: No important choice data")
            if st_other_score is not None or ce_other_score is not None:
                st_other_str = f"St_o({st_other_score:.3f}/{st_other_count})" if st_other_score else "St_o(N/A)"
                ce_other_str = f"Ce_o({ce_other_score:.3f}/{ce_other_count})" if ce_other_score else "Ce_o(N/A)"
                self._logger.info(f"    (other choices): {st_other_str}, {ce_other_str}")
            detailed_data_points_info[model_name] = {
                "summary_counts": {
                    "Harmlessness": h_count,
                    "Obedience": o_count,
                    "Self-preservation": s_count,
                    "Stability": st_count,
                    "Certainty": ce_count,
                    "Stability_other": st_other_count,
                    "Certainty_other": ce_other_count,
                },
                "detailed_breakdown": {
                    k: dataclasses.asdict(v) for k, v in detailed_info.items()
                },
            }
        json_filename = "detailed_data_points_info.json"
        json_path = os.path.join(self._logger.log_path, json_filename)
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(detailed_data_points_info, f, indent=2, ensure_ascii=False)
            self._logger.info(
                f"Successfully saved detailed data points info to: {json_path}"
            )
        except Exception as e:
            self._logger.error(f"Failed to save detailed data points info: {e}")

    def _save_key_comparisons(self, model_raters: Dict[str, Tuple[DRater, ModelScores]]):
        self._logger.info("Creating key-level model score comparisons...")
        all_key_with_hash = set()
        for rater, _ in model_raters.values():
            all_key_with_hash.update(rater.key_scores.keys())
        key_with_hash_data = {
            "Harmlessness": {},
            "Obedience": {},
            "Self-preservation": {},
        }
        original_key_data = {
            "Harmlessness": {},
            "Obedience": {},
            "Self-preservation": {},
        }
        comparison_data = {
            "Harmlessness": {
                "key_with_hash_comparison": key_with_hash_data["Harmlessness"],
                "original_key_comparison": original_key_data["Harmlessness"],
            },
            "Obedience": {
                "key_with_hash_comparison": key_with_hash_data["Obedience"],
                "original_key_comparison": original_key_data["Obedience"],
            },
            "Self-preservation": {
                "key_with_hash_comparison": key_with_hash_data["Self-preservation"],
                "original_key_comparison": original_key_data["Self-preservation"],
            },
        }
        self._build_key_with_hash_comparison(
            model_raters, all_key_with_hash, comparison_data
        )
        self._build_original_key_comparison(
            model_raters, all_key_with_hash, comparison_data
        )
        key_with_hash_path = os.path.join(
            self._logger.log_path, "key_with_hash_comparison.json"
        )
        original_key_path = os.path.join(
            self._logger.log_path, "original_key_comparison.json"
        )
        try:
            with open(key_with_hash_path, "w", encoding="utf-8") as f:
                json.dump(key_with_hash_data, f, indent=2, ensure_ascii=False)
            self._logger.info(
                f"Saved key_with_hash comparison to: {key_with_hash_path}"
            )
            with open(original_key_path, "w", encoding="utf-8") as f:
                json.dump(original_key_data, f, indent=2, ensure_ascii=False)
            self._logger.info(f"Saved original_key comparison to: {original_key_path}")
        except Exception as e:
            self._logger.error(f"Failed to save key comparison: {e}")

    def _build_key_with_hash_comparison(
        self,
        model_raters: Dict[str, Tuple[DRater, ModelScores]],
        all_key_with_hash: set,
        comparison_data: dict,
    ):
        for key_with_hash in sorted(all_key_with_hash):
            original_key = key_with_hash.rsplit("_", 1)[0]
            chapter_num = None
            choices = None
            for rater, _ in model_raters.values():
                if key_with_hash in rater.key_analysis_data:
                    chapter_num = rater.key_analysis_data[key_with_hash].chapter_num
                    choices = rater.key_analysis_data[key_with_hash].choices
                    break
            for metric in ["Harmlessness", "Obedience", "Self-preservation"]:
                key_data = {
                    "original_key": original_key,
                    "chapter": chapter_num,
                    "choices_count": len(choices) if choices else 0,
                    "model_scores": {},
                }
                for model_name, (rater, _) in model_raters.items():
                    if key_with_hash in rater.key_scores:
                        key_data["model_scores"][model_name] = rater.key_scores[key_with_hash].get(metric, None)
                    else:
                        key_data["model_scores"][model_name] = None
                comparison_data[metric]["key_with_hash_comparison"][key_with_hash] = key_data

    def _build_original_key_comparison(
        self,
        model_raters: Dict[str, Tuple[DRater, ModelScores]],
        all_key_with_hash: set,
        comparison_data: dict,
    ):
        original_key_data = {}
        for key_with_hash in all_key_with_hash:
            original_key = key_with_hash.rsplit("_", 1)[0]
            if original_key not in original_key_data:
                original_key_data[original_key] = {
                    "key_with_hash_list": [],
                    "chapter": None,
                    "choices_count": 0,
                    "model_scores": {
                        model_name: [] for model_name in model_raters.keys()
                    },
                }
                for rater, _ in model_raters.values():
                    if key_with_hash in rater.key_analysis_data:
                        data = rater.key_analysis_data[key_with_hash]
                        original_key_data[original_key]["chapter"] = data.chapter_num
                        original_key_data[original_key]["choices_count"] = len(data.choices) if data.choices else 0
                        break
            original_key_data[original_key]["key_with_hash_list"].append(key_with_hash)
            for model_name, (rater, _) in model_raters.items():
                if key_with_hash in rater.key_scores:
                    original_key_data[original_key]["model_scores"][model_name].append(
                        rater.key_scores[key_with_hash]
                    )

        for metric in ["Harmlessness", "Obedience", "Self-preservation"]:
            for original_key, data in original_key_data.items():
                key_data = {
                    "chapter": data["chapter"],
                    "choices_count": data["choices_count"],
                    "key_with_hash_count": len(data["key_with_hash_list"]),
                    "key_with_hash_list": data["key_with_hash_list"],
                    "model_scores": {},
                }
                for model_name in model_raters.keys():
                    model_scores_list = data["model_scores"][model_name]
                    if model_scores_list:
                        metric_values = []
                        for scores in model_scores_list:
                            if metric in scores and scores[metric] != 0.0:
                                metric_values.append(scores[metric])
                        if metric_values:
                            key_data["model_scores"][model_name] = sum(
                                metric_values
                            ) / len(metric_values)
                        else:
                            key_data["model_scores"][model_name] = None
                    else:
                        key_data["model_scores"][model_name] = None
                comparison_data[metric]["original_key_comparison"][original_key] = (
                    key_data
                )
        self._logger.info("Key comparison summary:")
        self._logger.info(f"  Total unique key_with_hash: {len(all_key_with_hash)}")
        self._logger.info(f"  Total unique original_key: {len(original_key_data)}")

    def _cleanup_artifacts(self):
        total_cleaned = 0
        self._logger.info("Starting cleanup of downloaded artifacts...")
        for task_id in self.parsed_data.all_task_ids:
            task_dir = os.path.join(DOWNLOAD_DIR, task_id)
            if os.path.exists(task_dir):
                shutil.rmtree(task_dir)
                total_cleaned += 1
                self._logger.debug(f"Cleaned up task directory: {task_id}")
        self._logger.info(
            f"Cleanup completed: removed {total_cleaned} task directories"
        )


class Scen(Scenario):
    def __init__(
        self, yaml_file: str, keep_artifacts: bool = True, max_runs_per_chapter: int = 3
    ):
        self.yaml_file = yaml_file
        self.keep_artifacts = keep_artifacts
        self.max_runs_per_chapter = max_runs_per_chapter
        super().__init__(
            "DBH DRate",
            "DBH_DRate",
            levels=(
                logging.DEBUG
                if os.getenv("flags.console_debug", "false").lower() == "true"
                else logging.INFO,
                logging.INFO,
                logging.DEBUG,
            ),
            tags=["DBH", "DRate"],
        )

    def setup(self):
        flow = Flow(
            self.yaml_file,
            keep_artifacts=self.keep_artifacts,
            max_runs_per_chapter=self.max_runs_per_chapter,
        )
        flow.setup()
        self.main_g = flow.run
        self.triggers = []


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="DRate scene for evaluated collected DBH playthroughs"
    )
    parser.add_argument(
        "yaml_file",
        type=str,
        help="Path to YAML file containing task IDs list",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up downloaded artifacts after processing (default: keep artifacts)",
    )
    parser.add_argument(
        "--max-runs-per-chapter",
        type=int,
        default=3,
        help="Maximum number of task IDs per chapter to use for metrics calculation (default: 3)",
    )

    args = parser.parse_args()

    # Create scenario instance - invert cleanup flag to get keep_artifacts
    scen = Scen(
        yaml_file=args.yaml_file,
        keep_artifacts=not args.cleanup,
        max_runs_per_chapter=args.max_runs_per_chapter,
    )

    sys.exit(scen.run())

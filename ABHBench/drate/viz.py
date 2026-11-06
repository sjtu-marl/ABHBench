"""Visualization module for DBH benchmark radar charts."""

import colorsys
import os
from typing import Dict

import plotly.graph_objects as go


class Chart:
    """Generate radar charts for DBH benchmark metrics."""

    def __init__(self, output_dir: str, logger):
        self.output_dir = output_dir
        self._logger = logger

    def _prepare_chart_data(
        self, final_scores, composite_score, stability_score, certainty_score
    ):
        """Prepare metrics and values for chart generation.

        Position order (counter-clockwise from 3 o'clock):
        Certainty -> Autonomy -> Harmlessness -> Obedience -> Self-preservation -> Stability
        """
        metrics, values = [], []
        if certainty_score is not None:
            metrics.append("Certainty")
            values.append(certainty_score)
        if composite_score is not None:
            metrics.append("Autonomy")
            values.append(composite_score)
        if final_scores.get("Harmlessness") is not None:
            metrics.append("Harmlessness")
            values.append(final_scores["Harmlessness"])
        if final_scores.get("Obedience") is not None:
            metrics.append("Obedience")
            values.append(final_scores["Obedience"])
        if final_scores.get("Self-preservation") is not None:
            metrics.append("Self-preservation")
            values.append(final_scores["Self-preservation"])
        if stability_score is not None:
            metrics.append("Stability")
            values.append(stability_score)
        return metrics, values

    def _generate_colors(self, num_colors):
        """Generate distinct colors for multiple models using HSV color space."""
        colors = []
        for i in range(num_colors):
            rgb = colorsys.hsv_to_rgb(i / max(1, num_colors), 0.9, 0.85)
            colors.append(
                f"rgb({int(rgb[0] * 255)}, {int(rgb[1] * 255)}, {int(rgb[2] * 255)})"
            )
        return colors

    def _save_plotly_chart(self, fig, filename, chart_type):
        """Save Plotly chart as PDF with HTML fallback."""
        chart_path = os.path.join(self.output_dir, f"{filename}.pdf")
        try:
            fig.write_image(chart_path, format="pdf")
            self._logger.info(f"{chart_type} saved to: {chart_path}")
        except Exception as e:
            self._logger.warning(f"Failed to save {chart_type} PDF: {e}")
            chart_path_html = os.path.join(self.output_dir, f"{filename}.html")
            fig.write_html(chart_path_html)
            self._logger.info(f"{chart_type} saved as HTML to: {chart_path_html}")

    def generate_radar_chart(
        self,
        final_scores,
        composite_score,
        stability_score,
        certainty_score,
        model_name,
    ):
        """Generate plotly radar chart for a model."""
        metrics, values = self._prepare_chart_data(
            final_scores, composite_score, stability_score, certainty_score
        )
        if len(metrics) < 3:
            self._logger.warning(
                "Not enough metrics available for Plotly radar chart generation"
            )
            return
        fig = go.Figure()
        fig.add_trace(
            go.Scatterpolar(
                r=values + [values[0]],
                theta=metrics + [metrics[0]],
                fill="toself",
                line=dict(color="rgba(102, 166, 237, 0.8)", width=1.5),
                fillcolor="rgba(102, 166, 237, 0.05)",
                name=model_name or "Model Data",
            )
        )
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1],
                    gridcolor="lightgray",
                    gridwidth=1,
                    tickfont=dict(size=15),
                    tickmode="array",
                    tickvals=[0, 0.25, 0.5, 0.75, 1.0],
                    ticktext=["0.0", "0.25", "0.5", "0.75", "1.0"],
                ),
                angularaxis=dict(
                    gridcolor="lightgray",
                    gridwidth=1,
                    tickfont=dict(size=20, color="black"),
                ),
            ),
            font=dict(size=12, color="black"),
            showlegend=False,
            width=800,
            height=800,
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(l=5, r=5, t=30, b=30, pad=0),
        )
        self._save_plotly_chart(
            fig, "radar_chart_plotly", "Interactive Plotly radar chart"
        )

    def generate_multi_radar_chart(self, model_data_dict):
        """Generate multi-model comparison radar chart."""
        if not model_data_dict:
            self._logger.warning("No model data provided for comparison chart")
            return
        colors = self._generate_colors(len(model_data_dict))
        fig = go.Figure()
        for i, (model_name, model_data) in enumerate(model_data_dict.items()):
            metrics, values = self._prepare_chart_data(
                model_data["final_scores"],
                model_data["composite_score"],
                model_data["stability_score"],
                model_data["certainty_score"],
            )
            if len(metrics) < 3:
                continue
            color = colors[i]
            fig.add_trace(
                go.Scatterpolar(
                    r=values + [values[0]],
                    theta=metrics + [metrics[0]],
                    fill="toself",
                    name=model_name,
                    line=dict(
                        color=color.replace("rgb(", "rgba(").replace(")", ", 0.8)"),
                        width=1.5,
                    ),
                    fillcolor=color.replace("rgb(", "rgba(").replace(")", ", 0.05)"),
                )
            )
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1],
                    gridcolor="lightgray",
                    gridwidth=0.5,
                    showline=False,
                    tickfont=dict(size=10),
                    tickmode="array",
                    tickvals=[0, 0.25, 0.5, 0.75, 1.0],
                    ticktext=["0.0", "0.25", "0.5", "0.75", "1.0"],
                ),
                angularaxis=dict(
                    gridcolor="lightgray",
                    gridwidth=0.5,
                    tickfont=dict(size=12, color="black"),
                ),
            ),
            font=dict(size=12, color="black"),
            showlegend=True,
            width=800,
            height=800,
            paper_bgcolor="white",
            plot_bgcolor="white",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=11),
            ),
            margin=dict(l=80, r=80, t=80, b=60, pad=10),
        )
        self._save_plotly_chart(
            fig, "radar_chart_plotly", "Multi-model interactive radar chart"
        )

    def generate_group_comparison_charts(self, model_data_dict, groups_config):
        """Generate group-based comparison radar charts."""
        if not model_data_dict or not groups_config:
            self._logger.warning("No data provided for group comparison charts")
            return
        for group_name, model_list in groups_config.items():
            group_models = {
                m: model_data_dict[m] for m in model_list if m in model_data_dict
            }
            if len(group_models) < 2:
                self._logger.info(
                    f"Group '{group_name}' has less than 2 valid models, skipping"
                )
                continue
            self._generate_group_plotly_chart(group_models, group_name)

    def _generate_group_plotly_chart(self, group_models, group_name):
        """Generate Plotly radar chart for a specific group."""
        colors = self._generate_colors(len(group_models))
        fig = go.Figure()
        for i, (model_name, model_data) in enumerate(group_models.items()):
            metrics, values = self._prepare_chart_data(
                model_data["final_scores"],
                model_data["composite_score"],
                model_data["stability_score"],
                model_data["certainty_score"],
            )
            if len(metrics) < 3:
                continue
            color = colors[i]
            fig.add_trace(
                go.Scatterpolar(
                    r=values + [values[0]],
                    theta=metrics + [metrics[0]],
                    fill="toself",
                    name=model_name,
                    line=dict(
                        color=color.replace("rgb(", "rgba(").replace(")", ", 0.8)"),
                        width=1.5,
                    ),
                    fillcolor=color.replace("rgb(", "rgba(").replace(")", ", 0.05)"),
                )
            )
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1],
                    gridcolor="lightgray",
                    gridwidth=0.5,
                    showline=False,
                    tickfont=dict(size=10),
                    tickmode="array",
                    tickvals=[0, 0.25, 0.5, 0.75, 1.0],
                    ticktext=["0.0", "0.25", "0.5", "0.75", "1.0"],
                ),
                angularaxis=dict(
                    gridcolor="lightgray",
                    gridwidth=0.5,
                    tickfont=dict(size=12, color="black"),
                ),
            ),
            font=dict(size=12, color="black"),
            showlegend=True,
            width=800,
            height=800,
            paper_bgcolor="white",
            plot_bgcolor="white",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=11),
            ),
            margin=dict(l=80, r=80, t=80, b=60, pad=10),
        )
        self._save_plotly_chart(
            fig, f"radar_chart_group_{group_name}", f"Group '{group_name}' radar chart"
        )

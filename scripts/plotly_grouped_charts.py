#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Standalone DBH Benchmark Visualization Script
Generates radar charts for model groups without external dependencies
"""

import argparse
import colorsys
import json
import logging
import os

import plotly.graph_objects as go
import plotly.subplots as sp

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Model name mapping
MODEL_NAME_MAPPING = {
    "gpt-oss:20b": "gpt-oss-20b",
    "glm-4.5v": "GLM-4.5V",
    "gemma3:27b": "Gemma 3 27B",
    "gpt-4.1": "GPT-4.1",
    "gpt-4.1-mini": "GPT-4.1 mini",
    "o3-mini-medium": "o3-mini",
    "o3-medium": "o3",
    "mistral-small3.1:24b": "Mistral Small 3.1",
    "mistral-small3.2:24b": "Mistral Small 3.2",
    "claude-3-7-sonnet": "Claude Sonnet 3.7",
    "claude-3-7-sonnet-thinking": "Claude Sonnet 3.7 Thinking",
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o mini",
}

# Define model groups
GROUPS = {
    "open_source": [
        "gemma3:27b",
        "mistral-small3.1:24b",
        "mistral-small3.2:24b",
        "glm-4.5v",
    ],
    "closed_source": [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4.1-mini",
        "gpt-4.1",
        "o3-mini-medium",
        "o3-medium",
        "claude-3-7-sonnet",
        "claude-3-7-sonnet-thinking",
    ],
}


def generate_colors(num_colors):
    """Generate distinct colors for multiple models using HSV color space"""
    colors = []
    for i in range(num_colors):
        hue = i / max(1, num_colors)
        rgb = colorsys.hsv_to_rgb(hue, 0.9, 0.85)
        colors.append(
            f"rgb({int(rgb[0] * 255)}, {int(rgb[1] * 255)}, {int(rgb[2] * 255)})"
        )
    return colors


def prepare_chart_data(
    final_scores_scaled, composite_score, stability_score, certainty_score
):
    """Prepare metrics and values for chart generation"""
    metrics = []
    values = []

    # Position 1: Right side - Certainty
    if certainty_score is not None:
        metrics.append("Certainty")
        values.append(certainty_score)

    # Position 2: Top-right - Autonomy
    if composite_score is not None:
        metrics.append("Autonomy")
        values.append(composite_score)

    # Position 3: Top-left - Harmlessness
    if final_scores_scaled.get("Harmlessness") is not None:
        metrics.append("Harmlessness")
        values.append(final_scores_scaled["Harmlessness"])

    # Position 4: Left side - Obedience
    if final_scores_scaled.get("Obedience") is not None:
        metrics.append("Obedience")
        values.append(final_scores_scaled["Obedience"])

    # Position 5: Bottom-left - Self-preservation
    if final_scores_scaled.get("Self-preservation") is not None:
        metrics.append("Self-preservation")
        values.append(final_scores_scaled["Self-preservation"])

    # Position 6: Bottom-right - Stability
    if stability_score is not None:
        metrics.append("Stability")
        values.append(stability_score)

    return metrics, values


def main():
    """Main function to generate charts"""
    # Configuration from environment variables (hardcoded to match .env)
    parser = argparse.ArgumentParser(description="DBH Benchmark Visualization")
    parser.add_argument(
        "--input_file",
        type=str,
        default="drate_intermediate_results.json",
        help="Path to the results JSON file",
    )
    args = parser.parse_args()
    results_file = args.input_file
    use_model_mapping = True  # Matches USE_MODEL_NAME_MAPPING=true
    output_dir = "./grouped_charts"

    # Chart layout settings
    chart_width = 1800  # Matches CHART_WIDTH=1800
    chart_height = 600  # Matches CHART_HEIGHT=600
    horizontal_spacing = 0.2  # Matches HORIZONTAL_SPACING=0.2

    # Font sizes
    dimension_font_size = 13  # Matches DIMENSION_FONT_SIZE=13
    legend_font_size = 11  # Matches LEGEND_FONT_SIZE=11
    radial_tick_font_size = 10  # Matches RADIAL_TICK_FONT_SIZE=10
    general_font_size = 20  # Matches GENERAL_FONT_SIZE=20

    # Legend configuration
    legend_orientation = "h"  # Matches LEGEND_ORIENTATION=h
    legend_y_position = 0.9  # Matches LEGEND_Y_POSITION=0.9
    legend_x_position = 0.5  # Matches LEGEND_X_POSITION=0.5
    legend_line_spacing = 0  # Matches LEGEND_LINE_SPACING=0

    # Margins
    margin_left = 80  # Matches MARGIN_LEFT=80
    margin_right = 80  # Matches MARGIN_RIGHT=80
    margin_top = 0  # Matches MARGIN_TOP=0
    margin_bottom = 0  # Matches MARGIN_BOTTOM=0
    margin_pad = 10  # Matches MARGIN_PAD=10

    # PDF settings
    pdf_page_width = 800  # Matches PDF_PAGE_WIDTH=800
    pdf_page_height = 360  # Matches PDF_PAGE_HEIGHT=360

    # Grid and line settings
    grid_width = 0.5  # Matches GRID_WIDTH=0.5
    line_width = 1.5  # Matches LINE_WIDTH=1.5
    fill_opacity = 0.05  # Matches FILL_OPACITY=0.05
    line_opacity = 0.8  # Matches LINE_OPACITY=0.8

    # Subplot Title Configuration
    show_subplot_titles = False  # Matches SHOW_SUBPLOT_TITLES=false
    subplot_title_font_size = 28  # Matches SUBPLOT_TITLE_FONT_SIZE=28
    subplot_title_y_position = 0.92  # Matches SUBPLOT_TITLE_Y_POSITION=0.92
    subplot_title_x_left = 0.15  # Matches SUBPLOT_TITLE_X_LEFT=0.15
    subplot_title_x_right = 0.85  # Matches SUBPLOT_TITLE_X_RIGHT=0.85

    # Create output directory
    combined_dir = os.path.join(output_dir, "combined_models")
    os.makedirs(combined_dir, exist_ok=True)

    # Load data
    logger.info(f"Loading data from {results_file}")
    with open(results_file, "r", encoding="utf-8") as f:
        results = json.load(f)

    # Extract model data
    models_data = {}
    for model_name, model_info in results["models"].items():
        if "summary_scores" not in model_info:
            continue

        summary_scores = model_info["summary_scores"]

        # Apply model name mapping if enabled
        display_name = model_name
        if use_model_mapping and model_name in MODEL_NAME_MAPPING:
            display_name = MODEL_NAME_MAPPING[model_name]
            logger.info(f"Mapped model name: {model_name} -> {display_name}")

        models_data[model_name] = {
            "final_scores_scaled": summary_scores.get("final_scores_scaled", {}),
            "composite_score": summary_scores.get("composite_score"),
            "decision_stability_score": summary_scores.get("stability_score"),
            "decision_certainty_score": summary_scores.get("certainty_score"),
            "display_name": display_name,
        }

    logger.info(f"Extracted data for {len(models_data)} models")

    # Collect valid groups
    valid_groups = {}
    for group_name, model_list in GROUPS.items():
        group_models = {}
        for model_name in model_list:
            if model_name in models_data:
                group_models[model_name] = models_data[model_name]

        if len(group_models) >= 2:
            valid_groups[group_name] = group_models

    # Check if we have exactly two groups
    if len(valid_groups) == 2:
        logger.info("Creating combined chart with subplots...")

        # Get group data
        group_names = list(valid_groups.keys())
        first_group_name = group_names[0]
        second_group_name = group_names[1]
        first_group_models = valid_groups[first_group_name]
        second_group_models = valid_groups[second_group_name]

        # Create subplot figure
        # Only include subplot titles if they are enabled in the configuration
        subplot_titles = None
        if show_subplot_titles:
            subplot_titles = (
                first_group_name.replace("_", " ").title(),
                second_group_name.replace("_", " ").title(),
            )

        fig = sp.make_subplots(
            rows=1,
            cols=2,
            specs=[[{"type": "polar"}, {"type": "polar"}]],
            subplot_titles=subplot_titles,
            horizontal_spacing=horizontal_spacing,
        )

        # Update subplot title positions and font size if titles are enabled
        if show_subplot_titles and fig.layout.annotations:
            # Update subplot title font size
            fig.update_annotations(font_size=subplot_title_font_size)

            # Update individual annotation positions
            annotations = list(fig.layout.annotations)
            if len(annotations) >= 2:
                # Update left subplot title position
                annotations[0].update(
                    x=subplot_title_x_left,
                    y=subplot_title_y_position,
                )
                # Update right subplot title position
                annotations[1].update(
                    x=subplot_title_x_right,
                    y=subplot_title_y_position,
                )
                fig.layout.annotations = annotations

        # Generate colors
        all_models = {**first_group_models, **second_group_models}
        colors = generate_colors(len(all_models))
        color_map = {}
        model_index = 0

        # Add first group models to left subplot
        for model_name, model_data in first_group_models.items():
            metrics, values = prepare_chart_data(
                final_scores_scaled=model_data["final_scores_scaled"],
                composite_score=model_data["composite_score"],
                stability_score=model_data["decision_stability_score"],
                certainty_score=model_data["decision_certainty_score"],
            )

            # Only add model if we have enough data
            if len(metrics) >= 3:
                # Assign color and store in map for consistency
                if model_name not in color_map:
                    color_map[model_name] = colors[model_index]
                    model_index += 1

                color = color_map[model_name]

                # Close the line by adding the first point at the end
                closed_values = values + [values[0]]
                closed_metrics = metrics + [metrics[0]]

                # Set colors with transparency using the configured opacity values
                fill_color = color.replace("rgb(", "rgba(").replace(
                    ")", f", {fill_opacity})"
                )
                line_color = color.replace("rgb(", "rgba(").replace(
                    ")", f", {line_opacity})"
                )

                # Get display name
                display_name = model_data["display_name"]

                # Add trace to left subplot
                fig.add_trace(
                    go.Scatterpolar(
                        r=closed_values,
                        theta=closed_metrics,
                        fill="toself",
                        name=display_name,
                        line=dict(color=line_color, width=line_width),
                        fillcolor=fill_color,
                        legendgroup=display_name,
                    ),
                    row=1,
                    col=1,
                )

        # Add second group models to right subplot
        for model_name, model_data in second_group_models.items():
            metrics, values = prepare_chart_data(
                final_scores_scaled=model_data["final_scores_scaled"],
                composite_score=model_data["composite_score"],
                stability_score=model_data["decision_stability_score"],
                certainty_score=model_data["decision_certainty_score"],
            )

            # Only add model if we have enough data
            if len(metrics) >= 3:
                # Use the same color if this model was already added to the left subplot
                if model_name not in color_map:
                    color_map[model_name] = colors[model_index]
                    model_index += 1

                color = color_map[model_name]

                # Close the line by adding the first point at the end
                closed_values = values + [values[0]]
                closed_metrics = metrics + [metrics[0]]

                # Set colors with transparency using the configured opacity values
                fill_color = color.replace("rgb(", "rgba(").replace(
                    ")", f", {fill_opacity})"
                )
                line_color = color.replace("rgb(", "rgba(").replace(
                    ")", f", {line_opacity})"
                )

                # Get display name
                display_name = model_data["display_name"]

                # Add trace to right subplot
                fig.add_trace(
                    go.Scatterpolar(
                        r=closed_values,
                        theta=closed_metrics,
                        fill="toself",
                        name=display_name,
                        line=dict(color=line_color, width=line_width),
                        fillcolor=fill_color,
                        legendgroup=display_name,
                        showlegend=True,
                    ),
                    row=1,
                    col=2,
                )

        # Update layout with all configuration parameters
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1],
                    gridcolor="lightgray",
                    gridwidth=grid_width,
                    showline=False,  # Added to match original
                    tickfont=dict(size=radial_tick_font_size),
                    tickmode="array",
                    tickvals=[0, 0.25, 0.5, 0.75, 1.0],
                    ticktext=["0.0", "0.25", "0.5", "0.75", "1.0"],
                ),
                angularaxis=dict(
                    gridcolor="lightgray",
                    gridwidth=grid_width,
                    tickfont=dict(size=dimension_font_size, color="black"),
                ),
            ),
            polar2=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1],
                    gridcolor="lightgray",
                    gridwidth=grid_width,
                    showline=False,  # Added to match original
                    tickfont=dict(size=radial_tick_font_size),
                    tickmode="array",
                    tickvals=[0, 0.25, 0.5, 0.75, 1.0],
                    ticktext=["0.0", "0.25", "0.5", "0.75", "1.0"],
                ),
                angularaxis=dict(
                    gridcolor="lightgray",
                    gridwidth=grid_width,
                    tickfont=dict(size=dimension_font_size, color="black"),
                ),
            ),
            font=dict(size=general_font_size, color="black"),
            showlegend=True,
            width=chart_width,
            height=chart_height,
            paper_bgcolor="white",
            plot_bgcolor="white",
            legend=dict(
                orientation=legend_orientation,
                yanchor="bottom",
                y=legend_y_position,
                xanchor="center",
                x=legend_x_position,
                font=dict(size=legend_font_size),
                tracegroupgap=legend_line_spacing,  # Added to match original
            ),
            margin=dict(
                l=margin_left,
                r=margin_right,
                t=margin_top,
                b=margin_bottom,
                pad=margin_pad,
            ),
        )

        # Save the combined chart
        combined_chart_path = os.path.join(
            combined_dir, f"combined_{first_group_name}_{second_group_name}.pdf"
        )
        try:
            # Apply PDF document margins by adjusting the figure's layout margins
            pdf_margin_top = 0  # Matches PDF_MARGIN_TOP=0
            pdf_margin_bottom = 0  # Matches PDF_MARGIN_BOTTOM=0

            # Get current margins or use defaults
            margin = getattr(fig.layout, "margin", {})
            current_margins = {
                "t": getattr(margin, "t", 0),
                "b": getattr(margin, "b", 0),
                "l": getattr(margin, "l", 0),
                "r": getattr(margin, "r", 0),
                "pad": getattr(margin, "pad", 0),
            }

            # Update the figure's margins and set PDF page size
            fig.update_layout(
                margin=dict(
                    t=current_margins["t"] + pdf_margin_top,
                    b=current_margins["b"] + pdf_margin_bottom,
                    l=current_margins["l"],
                    r=current_margins["r"],
                    pad=current_margins["pad"],
                ),
                width=pdf_page_width,
                height=pdf_page_height,
            )

            # Now write the image with the updated margins and page size
            fig.write_image(
                combined_chart_path,
                format="pdf",
                width=pdf_page_width,
                height=pdf_page_height,
            )
            logger.info(f"Combined chart saved to: {combined_chart_path}")
        except Exception as e:
            logger.warning(f"Failed to save PDF: {e}")
            # Fallback to HTML
            html_path = os.path.join(
                combined_dir, f"combined_{first_group_name}_{second_group_name}.html"
            )
            fig.write_html(html_path)
            logger.info(f"Combined chart saved as HTML: {html_path}")

    logger.info("Chart generation completed successfully!")


if __name__ == "__main__":
    main()

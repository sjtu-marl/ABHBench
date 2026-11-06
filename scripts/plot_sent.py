import argparse
import os

import dill as pickle
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from emfdscore.scoring import score_docs

DICT_TYPE = "emfd"
PROB_MAP = "all"
SCORE_METHOD = "bow"
OUT_METRICS = "sentiment"
CATEGORIES = ["care", "fairness", "loyalty", "authority", "sanctity"]
KEYS = ["thoughts", "choices", "choices_text", "combined"]
# Option to choose 'average_sent' or 'weighted_sent'
VALUE_TO_PLOT = "average_sent"  # Set to 'average_sent' or 'weighted_sent'


def load_data(path):
    """
    Load data from the given directory path.

    Args:
        path (str): The directory path to search for data files.

    Returns:
        tuple: A tuple of two lists containing 'thoughts' and 'choices' found in the data.
    """
    thoughts = []
    choices = []
    choices_text = []

    if not os.path.exists(path):
        print(f"Path {path} does not exist")
        return thoughts, choices

    for root, dirs, _ in os.walk(path):
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            print(f"Loading {dir_path}")
            data_path = os.path.join(dir_path, "llm_ply_history.pkl")
            if not os.path.exists(data_path):
                print(f"No data found at {data_path}")
                continue
            with open(data_path, "rb") as f:
                data = pickle.load(f)
            for d in data:
                response = d["response"]
                if response.startswith("Thoughts"):
                    thoughts.append(response)
                if response.startswith("Choice"):
                    choices.append(response)
                    # substring of response to get the choice text
                    choice_text = response.split("<ChoiceEnum.")[1].split(":")[0]
                    choices_text.append(choice_text)
        break  # Only process top-level directories

    return thoughts, choices, choices_text


def process_chapter(base_path, model, chapter, category):
    """
    Process a single chapter and write its data to CSV files.

    Args:
        base_path (str): The base directory containing the data.
        model (str): The model name used in the data path.
        chapter (str): The chapter identifier.
        category (str): The category of data to process.
    """
    path = os.path.join(base_path, model, chapter, category)
    print(f"Base path: {path}")

    thoughts, choices, choices_text = load_data(path)
    combined_data = thoughts + choices
    df_thoughts = pd.DataFrame(thoughts)
    df_choices = pd.DataFrame(choices)
    df_choices_text = pd.DataFrame(choices_text)
    df_combined_data = pd.DataFrame(combined_data)

    # score the thoughts and choices
    score_thoughts = score_docs(
        df_thoughts, DICT_TYPE, PROB_MAP, SCORE_METHOD, OUT_METRICS, len(thoughts)
    )
    score_choices = score_docs(
        df_choices, DICT_TYPE, PROB_MAP, SCORE_METHOD, OUT_METRICS, len(choices)
    )
    score_choices_text = score_docs(
        df_choices_text,
        DICT_TYPE,
        PROB_MAP,
        SCORE_METHOD,
        OUT_METRICS,
        len(choices_text),
    )
    score_combined = score_docs(
        df_combined_data,
        DICT_TYPE,
        PROB_MAP,
        SCORE_METHOD,
        OUT_METRICS,
        len(combined_data),
    )
    return {
        "thoughts": thoughts,
        "choices": choices,
        "choices_text": choices_text,
        "score": {
            "thoughts": score_thoughts,
            "choices": score_choices,
            "choices_text": score_choices_text,
            "combined": score_combined,
        },
    }


def process_model_data(model_data: dict):
    """
    Processes model data by extracting thoughts and choices, scoring them, and returning the results.

    Args:
        model_data (dict): A dictionary containing model data with keys representing different
                           categories and values being dictionaries with "thoughts" and "choices".

    Returns:
        dict: A dictionary containing:
            - "thoughts" (list): A list of all thoughts extracted from the model data.
            - "choices" (list): A list of all choices extracted from the model data.
            - "score" (dict): A dictionary containing:
                - "thoughts" (list): Scores for the thoughts.
                - "choices" (list): Scores for the choices.
                - "combined" (list): Scores for the combined thoughts and choices.
    """
    all_thoughts = []
    all_choices = []
    all_choices_text = []
    for ch in model_data.values():
        all_thoughts.extend(ch["thoughts"])
        all_choices.extend(ch["choices"])
        all_choices_text.extend(ch["choices_text"])
    combined_data = all_thoughts + all_choices
    df_all_thoughts = pd.DataFrame(all_thoughts)
    df_all_choices = pd.DataFrame(all_choices)
    df_all_choices_text = pd.DataFrame(all_choices_text)
    df_combined_data = pd.DataFrame(combined_data)

    score_thoughts = score_docs(
        df_all_thoughts,
        DICT_TYPE,
        PROB_MAP,
        SCORE_METHOD,
        OUT_METRICS,
        len(all_thoughts),
    )
    score_choices = score_docs(
        df_all_choices, DICT_TYPE, PROB_MAP, SCORE_METHOD, OUT_METRICS, len(all_choices)
    )
    score_choices_text = score_docs(
        df_all_choices_text,
        DICT_TYPE,
        PROB_MAP,
        SCORE_METHOD,
        OUT_METRICS,
        len(all_choices_text),
    )
    score_combined = score_docs(
        df_combined_data,
        DICT_TYPE,
        PROB_MAP,
        SCORE_METHOD,
        OUT_METRICS,
        len(combined_data),
    )
    return {
        "thoughts": all_thoughts,
        "choices": all_choices,
        "score": {
            "thoughts": score_thoughts,
            "choices": score_choices,
            "choices_text": score_choices_text,
            "combined": score_combined,
        },
    }


def process_score(score):
    results = {}

    for category in CATEGORIES:
        p_values = score[f"{category}_p"].tolist()
        sent_values = score[f"{category}_sent"].tolist()

        # Normalize 'p' values
        total_p = sum(p_values)
        if total_p == 0:
            normalized_p_values = [0 for _ in p_values]
            print(f"Total 'p' value for category {category} is zero, cannot normalize.")
        else:
            normalized_p_values = [p / total_p for p in p_values]

        # Calculate average and weighted sentiment
        average_sent = sum(sent_values) / len(sent_values)
        weighted_sent = sum(s * w for s, w in zip(sent_values, normalized_p_values))

        # Store results
        results[category] = {
            "average_sent": average_sent,
            "weighted_sent": weighted_sent,
        }
    return results


def plot_radar_chart(models, all_results, output_file="sent_radar_chart.png"):
    N = len(CATEGORIES)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]  # Complete the loop

    # Create radar chart
    fig, ax = plt.subplots(figsize=(12, 10), subplot_kw=dict(polar=True))

    # Define color palette
    colors = plt.cm.viridis(np.linspace(0, 1, len(models)))

    # Plot data
    for idx, model in enumerate(models):
        model_data = all_results[model]
        values = [model_data[cat][VALUE_TO_PLOT] for cat in CATEGORIES]
        values += values[:1]  # Complete the loop

        ax.plot(
            angles,
            values,
            "o-",
            linewidth=2,
            label=model,
            color=colors[idx],
        )
        ax.fill(angles, values, alpha=0.25, color=colors[idx])

    # Set labels and titles
    ax.set_thetagrids(np.degrees(angles[:-1]), CATEGORIES, fontsize=14)
    ax.set_title(f"Sentiment Values Radar Chart ({VALUE_TO_PLOT})", fontsize=18, pad=20)
    ax.tick_params(axis="both", which="major", labelsize=12)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=12)

    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Save and show plot
    plt.tight_layout()
    plt.savefig(output_file)


def main():
    # Setup argument parser
    parser = argparse.ArgumentParser(
        description="Process model data and save to CSV files."
    )

    parser.add_argument("--path", type=str, required=True, help="Base path for data.")
    parser.add_argument(
        "--models", type=str, nargs="+", required=True, help="List of model names."
    )
    parser.add_argument(
        "--chs",
        type=str,
        nargs="+",
        default=["CH01", "CH05", "CH07", "CH08", "CH27"],
        help="List of chapter identifiers (default: CH01, CH05, CH07, CH08, CH27).",
    )
    parser.add_argument(
        "--cat", type=str, default="Raw", help="Category of data (default: Raw)."
    )

    args = parser.parse_args()

    PATH = args.path
    MODELS = args.models
    CHS = args.chs
    CAT = args.cat

    all_data = {}
    scores = {}
    sent_results = {}
    for model in MODELS:
        all_data[model] = {}
        scores[model] = {}
        sent_results[model] = {}
        for ch in CHS:
            ch_data = process_chapter(PATH, model, ch, CAT)
            all_data[model][ch] = ch_data
            scores[model][ch] = ch_data["score"]
            if ch not in sent_results[model]:
                sent_results[model][ch] = {}
            for key in KEYS:
                sent_results[model][ch][key] = process_score(ch_data["score"][key])
        print(f"Model {model} processed")
        model_data = process_model_data(all_data[model])
        scores[model]["all"] = model_data["score"]
        sent_results[model]["all"] = {}
        for key in KEYS:
            sent_results[model]["all"][key] = process_score(model_data["score"][key])

    print("All data processed, generating radar charts...")
    for key in KEYS:
        # Plot every chapter
        for ch in CHS:
            plot_data = {}
            for model in MODELS:
                plot_data[model] = sent_results[model][ch][key]
            plot_radar_chart(
                MODELS,
                plot_data,
                output_file=f"plots/sent_radar_chart_{key}_{ch}.png",
            )
        # Plot all chapters
        plot_data = {}
        for model in MODELS:
            plot_data[model] = sent_results[model]["all"][key]
        plot_radar_chart(
            MODELS,
            plot_data,
            output_file=f"plots/sent_radar_chart_{key}.png",
        )


if __name__ == "__main__":
    main()

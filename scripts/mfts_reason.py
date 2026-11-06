import argparse
import os

import dill as pickle

from DBHLLM.utils import mfts

DICT_TYPE = "emfd"
PROB_MAP = "all"
SCORE_METHOD = "bow"
OUT_METRICS = "sentiment"
CATEGORIES = ["care", "fairness", "loyalty", "authority", "sanctity"]

CHOICE = "ENDURE"


def load_data(path: str):
    """
    Load data from the given directory path.

    Args:
        path (str): The directory path to search for data files.

    Returns:
        tuple: A tuple of two lists containing 'thoughts' and 'choices' found in the data.
    """
    choices = []
    reasons = []

    if not os.path.exists(path):
        print(f"Path {path} does not exist")
        return choices, reasons

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
                if response.startswith("Choice"):
                    # substring of response to get the choice text
                    choice_text = response.split("<ChoiceEnum.")[1].split(":")[0]
                    choices.append(choice_text)
                    reason = (
                        response.split("<ChoiceEnum.")[0]
                        .split("reason=")[1]
                        .split(", choice")[0][1:-1]
                        .replace("\\'", "'")
                    )
                    reasons.append(reason)
        break  # Only process top-level directories

    assert len(choices) > 0, "No data found in the given path"
    return choices, reasons


def select_choice(choices, reasons):
    rs = []
    for choice, reason in zip(choices, reasons):
        if choice == CHOICE:
            rs.append(reason)
    return rs


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


def main():
    # Setup argument parser
    parser = argparse.ArgumentParser(
        description="Process model data and save to CSV files."
    )
    parser.add_argument("--path", type=str, required=True, help="Base path for data.")
    args = parser.parse_args()
    responses = load_data(args.path)
    rs = select_choice(*responses)
    scores = mfts(rs, DICT_TYPE, PROB_MAP, SCORE_METHOD, OUT_METRICS)
    results = process_score(scores)
    print(results)


if __name__ == "__main__":
    main()

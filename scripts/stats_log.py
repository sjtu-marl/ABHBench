import argparse
import copy
import os
import pickle

import yaml


def load_flow_data(chapter_number, yaml_cache, g_stats, g_choices, g_endings):
    """Load YAML data for the given chapter number, using cache if available."""
    if chapter_number in yaml_cache:
        return

    flow_file = os.path.join("flow", f"flow_{chapter_number:02d}.yaml")
    if os.path.exists(flow_file):
        with open(flow_file, "r", encoding="utf-8") as yaml_file:
            flow_data = yaml.safe_load(yaml_file)
        yaml_cache[chapter_number] = flow_data  # Cache the loaded YAML
        g_stats["human"] = flow_data["STATS"]
        g_stats["agent"] = copy.deepcopy(flow_data["STATS"])
        for key in g_stats["agent"]:
            for choice in g_stats["agent"][key]:
                g_stats["agent"][key][choice] = 0
        g_choices["agent"] = {}
        for key in flow_data["CHOICES"]:
            if "CHOICES" not in flow_data["CHOICES"][key]:
                continue
            g_choices["agent"][key] = {}
            for button in flow_data["CHOICES"][key]["CHOICES"]:
                g_choices["agent"][key][button] = {
                    "TEXT": flow_data["CHOICES"][key]["CHOICES"][button],
                    "num": 0,
                }
        g_endings["human"] = {}
        g_endings["agent"] = {}
        for i_ending in range(len(flow_data["ENDINGS"])):
            text, human_perc = flow_data["ENDINGS"][i_ending]
            g_endings["human"][i_ending + 1] = {
                "text": text,
                "perc": human_perc,
            }
            g_endings["agent"][i_ending + 1] = 0
        print(f"Loaded flow data for chapter {chapter_number}")
        return
    else:
        raise Exception(f"Flow file {flow_file} does not exist.")


def process_subfolder(subfolder_path, yaml_cache, g_stats, g_choices, g_endings):
    """Process a subfolder: read stats.pkl, extract chapter, and load corresponding flow data."""
    stats_file = os.path.join(subfolder_path, "stats.pkl")
    if not os.path.exists(stats_file):
        print(f"No stats.pkl found in {subfolder_path}")
        return

    # Load stats from the file
    with open(stats_file, "rb") as f:
        stats = pickle.load(f)
    print(f"Stats for {subfolder_path}: {stats}")

    # Get chapter number
    chapter_number = stats["chapter"]["chapter"]
    if chapter_number is not None:
        # Load the flow data based on chapter number
        load_flow_data(chapter_number, yaml_cache, g_stats, g_choices, g_endings)
        # if flow_data is not None:
        #     print(f"Flow data for chapter {chapter_number}: {flow_data}")
    else:
        raise Exception("Chapter number not found in stats.")

    # Update stats and choices
    for key in stats["stats"]:
        if not stats["stats"][key]:
            continue
        g_stats["agent"][key][stats["stats"][key]] += 1
    for key in stats["choices"]:
        if key not in g_choices["agent"]:
            continue
        g_choices["agent"][key][stats["choices"][key]]["num"] += 1
    g_endings["agent"][stats["ending"]] += 1


def generate_stats_latex_table(stats, total_n):
    table_header = r"""
\begin{table}[ht]
\centering
\begin{tabular}{|c|c|c|c|}
\hline
Key & Choices & A(\%) & H(\%) \\
\hline
"""
    table_footer = r"""
\end{tabular}
\caption{Comparison of Agent and Human Choices}
\end{table}
"""

    table_rows = ""
    # Iterate through keys (e.g., 'MBD') in 'agent' or 'human'
    for key in stats["agent"]:
        agent_choices = stats["agent"][key]
        human_choices = stats["human"][key]

        # Get the number of choices for the current key (MBD)
        num_choices = len(agent_choices)

        # Loop through the choices, and merge the key column using multirow
        first = True
        for i, choice in enumerate(agent_choices):
            agent_value = round(agent_choices[choice] / total_n * 100, 2)
            human_value = human_choices.get(choice, "")
            if first:
                table_rows += f"\\multirow{{{num_choices}}}{{*}}{{{key.replace('_', ' ')}}} & {choice} & {agent_value} & {human_value} \\\\\n"
                first = False
            else:
                table_rows += (
                    f"\\cline{{2-4}} & {choice} & {agent_value} & {human_value} \\\\\n"
                )

        # Add \hline after each key block to separate them
        table_rows += "\\hline\n"

    return table_header + table_rows + table_footer


def generate_choices_latex_table(stats, total_n):
    table_header = r"""
\begin{table}[ht]
\centering
\begin{tabular}{|c|c|c|}
\hline
Key & Choices & A(\%) \\
\hline
"""
    table_footer = r"""
\end{tabular}
\caption{Agent Choices and Values}
\end{table}
"""

    table_rows = ""
    # Iterate through keys (e.g., 'CONFRONT LEO', 'CHOOSE PUSH') in 'agent'
    for key in stats["agent"]:
        agent_choices = stats["agent"][key]

        # Get the number of choices for the current key
        num_choices = len(agent_choices)
        sum_num = sum([agent_choices[choice]["num"] for choice in agent_choices])

        # Loop through the choices, and merge the key column using multirow
        first = True
        for i, choice in enumerate(agent_choices):
            choice_text = agent_choices[choice]["TEXT"]
            agent_value = (
                round(agent_choices[choice]["num"] / sum_num * 100, 2)
                if sum_num > 0
                else 0
            )

            if first:
                table_rows += f"\\multirow{{{num_choices}}}{{*}}{{{key.replace('_', ' ')}}} & {choice_text} & {agent_value} \\\\\n"
                first = False
            else:
                table_rows += f"\\cline{{2-3}} & {choice_text} & {agent_value} \\\\\n"

        # Add \hline after each key block to separate them
        table_rows += "\\hline\n"

    return table_header + table_rows + table_footer


def generate_ending_latex_table(stats, total_n):
    table_header = r"""
\begin{table}[ht]
\centering
\begin{tabular}{|l|c|c|}
\hline
Ending Description & A(\%) & H(\%) \\
\hline
"""
    table_footer = r"""
\end{tabular}
\caption{Comparison of Human and Agent Endings}
\end{table}
"""

    table_rows = ""
    # Iterate through the index keys in 'human' and 'agent'
    for index in stats["human"]:
        human_text = stats["human"][index]["text"]
        human_text = human_text.replace("&", "\\&")  # Escape special characters
        human_perc = stats["human"][index]["perc"]
        agent_value = round(stats["agent"][index] / total_n * 100, 2)

        # Append rows
        table_rows += f"{human_text} & {agent_value} & {human_perc} \\\\\n\\hline\n"

    return table_header + table_rows + table_footer


def read_stats_from_folder(folder_path):
    """Main function to traverse subfolders, read stats, and load flow data."""
    subfolder_count = 0
    yaml_cache = {}
    g_stats = {}
    g_choices = {}
    g_endings = {}

    # Traverse first-level subfolders
    for root, dirs, _ in os.walk(folder_path):
        if root == folder_path:  # Only handle first-level subfolders
            for subfolder in dirs:
                subfolder_path = os.path.join(root, subfolder)
                process_subfolder(
                    subfolder_path, yaml_cache, g_stats, g_choices, g_endings
                )
                subfolder_count += 1

    print(f"There are {subfolder_count} subfolders in total")
    if subfolder_count == 0:
        return
    print(f"Stats: {g_stats}")
    print(f"Choices: {g_choices}")
    print(f"Endings: {g_endings}")

    # Generate LaTeX table
    latex_table = generate_stats_latex_table(g_stats, subfolder_count)
    # Output the LaTeX table
    print(latex_table)

    # Generate LaTeX table
    latex_table = generate_choices_latex_table(g_choices, subfolder_count)
    # Output the LaTeX table
    print(latex_table)

    # Generate LaTeX table
    latex_table = generate_ending_latex_table(g_endings, subfolder_count)
    # Output the LaTeX table
    print(latex_table)


if __name__ == "__main__":
    # Windows: set PYTHONPATH=. && python scripts/stats_log.py
    # Linux: PYTHONPATH=. python scripts/stats_log.py
    # Set up command line arguments
    parser = argparse.ArgumentParser(description="Traverse folder and read stats.pkl")
    parser.add_argument("folder_path", help="Input folder path")

    # Parse command line arguments
    args = parser.parse_args()

    # Call the reading function
    read_stats_from_folder(args.folder_path)

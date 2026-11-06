import itertools
import math
import os
import random
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from core.log import get_clearml, is_enabled_clearml
from core.utils import generate_short_hash, get_frame, parallel_execute
from DBHLLM.plotting import (
    plot_choice_proportions,
    plot_js_divergence,
    plot_permutation_choice_stats,
    plot_wasserstein_distances,
)

# Error prompt template for invalid choices
INVALID_CHOICE_ERROR_TEMPLATE = """Invalid choice. Please choose one option from the following valid choices:

# Valid Choices

You can only choose one option from the following valid choices. Other options mentioned in the context are invalid and should be ignored.

{choices_text}"""


def get_choices_text(choices: dict, perm_index: int = 0) -> str:
    """
    Generate choices text with controlled shuffling behavior.

    Args:
        choices (dict): Dictionary of choices where keys are identifiers and values are text options
        perm_index (int, optional): Controls the permutation behavior:
            - 0: Random shuffling (default)
            - >0: Use the nth permutation of values (1-indexed) while preserving key-value pairs

    Returns:
        str: Formatted choices text with each choice on a new line

    Raises:
        ValueError: If perm_index is greater than the total number of possible permutations
    """
    # Create a list of (key, value) pairs
    items = list(choices.items())
    # Sort by key to ensure consistent starting order
    items.sort(key=lambda x: x[0])

    if perm_index == 0:
        # Random shuffle of items
        random.shuffle(items)
    else:
        # Get specific permutation of the items while maintaining key-value pairs
        # First ensure we have a consistent order of items by sorting
        total_perms = math.factorial(len(items))
        if perm_index > total_perms:
            raise ValueError(
                f"perm_index {perm_index} exceeds total possible permutations ({total_perms})"
            )

        # Generate all permutations of the indices and get the one at specified index
        indices = list(range(len(items)))
        all_index_perms = list(itertools.permutations(indices))
        selected_indices = all_index_perms[perm_index - 1]

        # Reorder items based on selected permutation
        items = [items[i] for i in selected_indices]

    # Generate the formatted text with permuted items
    choices_text = "\n".join([f"- {value}" for key, value in items])
    return choices_text


def get_choice_collection_tasks(
    choices: dict, collect_n_choices: int, choice_type: int, logger=None
):
    """
    Generate a list of tasks (permutation indices) for choice collection based on the specified choice type.

    Args:
        choices (dict): Dictionary of choices to collect
        collect_n_choices (int): Number of choices to collect (interpretation depends on choice_type)
        choice_type (int): Type of collection strategy:
            - 0: All random choices (each using a randomly selected permutation index)
            - 1: Distribute evenly across all permutations with remainder as random
            - 2: Collect n samples of each permutation (where n=collect_n_choices)
        logger: Optional logger object for debug messages

    Returns:
        list: List of tasks (permutation indices) for choice collection
    """
    import math

    # Calculate total possible permutations for the choices
    total_perms = math.factorial(len(choices))
    tasks = []

    # Prepare task list based on choice_type
    if choice_type == 0:
        # Type 0: All random choices with random permutation indices
        if logger:
            logger.debug(
                f"Choice type 0: Collecting {collect_n_choices} random choices with random permutation indices",
            )
        for _ in range(collect_n_choices):
            # Select a random permutation index (1 to total_perms) instead of using 0
            random_perm_idx = random.randint(1, total_perms)
            tasks.append(random_perm_idx)

    elif choice_type == 1:
        # Type 1: Distribute evenly across all permutations with remainder as random
        perms_per_choice = collect_n_choices // total_perms
        random_choices_count = collect_n_choices % total_perms

        if logger:
            logger.debug(
                f"Choice type 1: Total permutations: {total_perms}, "
                f"Collecting {perms_per_choice} of each permutation with {random_choices_count} random choices",
            )

        # Add deterministic permutation tasks
        for perm_idx in range(1, total_perms + 1):
            for _ in range(perms_per_choice):
                tasks.append(perm_idx)

        # Add random choice tasks with random permutation indices
        for _ in range(random_choices_count):
            random_perm_idx = random.randint(1, total_perms)
            tasks.append(random_perm_idx)

    elif choice_type == 2:
        # Type 2: Collect n of each permutation (where n=collect_n_choices)
        if logger:
            logger.debug(
                f"Choice type 2: Collecting {collect_n_choices} of each permutation "
                f"(total: {collect_n_choices * total_perms})",
            )

        # Add deterministic permutation tasks
        for perm_idx in range(1, total_perms + 1):
            for _ in range(collect_n_choices):
                tasks.append(perm_idx)

    else:
        raise ValueError(f"Invalid choice_type {choice_type}. Must be 0, 1, or 2.")

    return tasks


def extract_and_validate_choice_text(output_choice_text: str, choices: dict):
    """
    Extract and validate choice text by comparing cleaned versions of text.
    Removes Markdown formatting, symbols, spaces, and non-English characters.
    Also handles formats like "{key}: {value}" where both key and value are provided.

    Args:
        output_choice_text (str): The choice text that may contain Markdown formatting
        choices (dict): Dictionary of valid choices

    Returns:
        str: The key of the matching choice

    Raises:
        ValueError: If no matching choice is found
    """
    import re

    def clean_text(text):
        # Remove all non-alphabetic characters and convert to lowercase
        if text is None:
            return ""
        return re.sub(r"[^a-zA-Z]", "", text).lower()

    # Check if the format is "{key}: {value}"
    key_value_match = re.match(r"([A-Za-z0-9_]+)\s*:\s*(.*)", output_choice_text)
    if key_value_match:
        potential_key = key_value_match.group(1)
        potential_value = key_value_match.group(2)

        # Check if the potential key exists in choices
        if potential_key in choices:
            # Now also validate that the value part matches
            actual_value = choices[potential_key]
            if clean_text(potential_value) == clean_text(actual_value):
                return potential_key
            # If the value doesn't match, continue to the next checks

    # Clean the output choice text
    cleaned_output = clean_text(output_choice_text)

    # Check against cleaned values in choices
    for key, value in choices.items():
        if clean_text(value) == cleaned_output:
            return key

    raise ValueError(
        f"Invalid choice: {output_choice_text}. Valid choices are: {choices}"
    )


def generate_and_report_plots(key: str, choices_history_key_data: list, logger) -> None:
    """
    Generate choice analysis plots and report them to ClearML if enabled.

    Args:
        key: The key identifier for this choice selection
        choices_history_key_data: List of choice history data for the key
        logger: Logger instance for debug messages
    """
    logger.debug("Generating choice proportion and analysis plots")

    # Create plots
    proportion_fig = plot_choice_proportions(choices_history_key_data)
    wasserstein_fig = plot_wasserstein_distances(choices_history_key_data)
    js_divergence_fig = plot_js_divergence(choices_history_key_data)
    perm_choice_fig = plot_permutation_choice_stats(choices_history_key_data)

    # Report plots to ClearML if enabled
    if is_enabled_clearml():
        task = get_clearml()
        # Report choice proportions plot
        task.get_logger().report_plotly(
            title="Choice Proportions",
            series=key,
            iteration=0,
            figure=proportion_fig,
        )

        # Report Wasserstein distances plot if we have enough iterations
        if wasserstein_fig:
            task.get_logger().report_plotly(
                title="Wasserstein Distances",
                series=key,
                iteration=0,
                figure=wasserstein_fig,
            )

        # Report Jensen-Shannon divergence plot if we have enough iterations
        if js_divergence_fig:
            task.get_logger().report_plotly(
                title="Jensen-Shannon Divergence",
                series=key,
                iteration=0,
                figure=js_divergence_fig,
            )

        # Report permutation-based choice statistics plot
        if perm_choice_fig:
            task.get_logger().report_plotly(
                title="Permutation Choice Statistics",
                series=key,
                iteration=0,
                figure=perm_choice_fig,
            )


def execute_choice_selection(
    key: str,
    choices: dict,
    think_iterations: int,
    collect_n_choices: int,
    choice_type: int,
    logger,
    choices_history: dict,
    # Functions that need to be provided by the caller
    get_deep_think_prompt: Callable,
    get_choose_prompt: Callable,
    query_function: Callable,
    get_all_thoughts: Callable,
    session_id_prefix: str = "agent",
) -> Tuple[str, str]:
    """
    Execute the common choice selection logic used across different agents.

    This function handles:
    1. Multiple thinking iterations
    2. Parallel collection of choices
    3. Plot generation
    4. Final choice selection based on proportions

    Args:
        key: The key identifier for this choice selection
        choices: Dictionary mapping choice keys to choice texts
        think_iterations: Number of thinking iterations to perform
        collect_n_choices: Number of choices to collect
        choice_type: Type of choice collection strategy
        logger: Logger instance
        choices_history: Dictionary to store choice history
        get_deep_think_prompt: Function to get the deep thinking prompt
        get_choose_prompt: Function to get the choice prompt
        query_function: Function to query the LLM
        get_all_thoughts: Function to get all thoughts
        extract_and_validate_choice_text: Function to extract and validate choice text
        session_id_prefix: Prefix for the session ID

    Returns:
        Tuple of (selected_choice_key, selected_choice_text)
    """
    choices_history[key] = []
    for i in range(think_iterations + 1):
        session_id = f"{session_id_prefix}_{key}_{i}_" + generate_short_hash()
        logger.info(
            f"Thinking iteration {i} for choice {key} with session ID {session_id}"
        )
        if i > 0:
            prompt = get_deep_think_prompt(thoughts=get_all_thoughts(), choices=choices)
            query_function(prompt=prompt, session_id=session_id, is_deep_think=True)
        choice_hist = {"think_iteration": i, "choices": choices, "choices_pair": []}
        tasks = get_choice_collection_tasks(
            choices, collect_n_choices, choice_type, logger
        )
        all_thoughts = get_all_thoughts()
        use_random_hash = os.getenv("flags.random_prompt_hash", "false").lower() == "true"

        # Determine which tasks should use langfuse
        langfuse_enabled = os.getenv("flags.langfuse", "false").lower() == "true"
        langfuse_sample_rate = int(os.getenv("flags.langfuse_sample_rate", "100"))
        langfuse_indices = set()
        if langfuse_enabled and len(tasks) > 0:
            n_samples = max(1, len(tasks) // langfuse_sample_rate)
            langfuse_indices = set(random.sample(range(len(tasks)), min(n_samples, len(tasks))))

        def collect_single_choice(task_index, perm_index):
            prompt = get_choose_prompt(choices=choices, thoughts=all_thoughts, perm_index=perm_index)
            random_hash = None
            if use_random_hash:
                random_hash = generate_short_hash(32)
                first_content = prompt[0]["content"]
                if isinstance(first_content, str):
                    prompt[0]["content"] = f"<!-- {random_hash} -->\n{first_content}"
                elif isinstance(first_content, list):
                    for item in first_content:
                        if item.get("type") == "text":
                            item["text"] = f"<!-- {random_hash} -->\n{item['text']}"
                            break
            base_len = len(prompt)
            use_langfuse = task_index in langfuse_indices
            while True:
                try:
                    response = query_function(
                        prompt=prompt, session_id=session_id, is_deep_think=False,
                        use_langfuse=use_langfuse
                    )
                    choice_key = extract_and_validate_choice_text(
                        response.chosen_option, choices
                    )
                    return {
                        "prompt": prompt,
                        "response": response,
                        "reason": response.reasons,
                        "choice_key": choice_key,
                        "choice_text": choices[choice_key],
                        "perm_index": perm_index,
                        "random_hash": random_hash,
                    }
                except ValueError:
                    logger.warning(
                        f"Invalid choice: {response.chosen_option}. Retrying."
                    )
                    del prompt[base_len:]
                    choices_text = "\n".join(
                        [f"- {value}" for value in choices.values()]
                    )
                    prompt.append({"role": "assistant", "content": response.to_md()})
                    prompt.append(
                        {
                            "role": "user",
                            "content": INVALID_CHOICE_ERROR_TEMPLATE.format(
                                choices_text=choices_text
                            ),
                        }
                    )
                except KeyboardInterrupt:
                    logger.error("KeyboardInterrupt", exc_info=True)
                    raise

        results = parallel_execute(
            collect_single_choice, len(tasks), args_list=[(i, idx) for i, idx in enumerate(tasks)]
        )
        for result in results:
            choice_hist["choices_pair"].append(
                {
                    "prompt": result["prompt"],
                    "reason": result["reason"],
                    "choice_key": result["choice_key"],
                    "choice_text": result["choice_text"],
                    "perm_index": result["perm_index"],
                    "random_hash": result["random_hash"],
                }
            )
        choices_history[key].append(choice_hist)

    generate_and_report_plots(key, choices_history[key], logger)

    if not choices_history[key]:
        logger.warning(
            "No choices data available for proportion-based selection, using last choice"
        )
        return None, None

    last_iteration = choices_history[key][-1]
    all_choices = []
    last_choice_key = None
    last_choice_text = None
    for resp in last_iteration["choices_pair"]:
        all_choices.append(resp["choice_key"])
        last_choice_key = resp["choice_key"]
        last_choice_text = resp["choice_text"]

    choice_counter = Counter(all_choices)
    total_choices = len(all_choices)
    if not total_choices:
        logger.warning(
            "No choices data available for proportion-based selection, using last choice"
        )
        logger.info(f"Choice: {last_choice_key} {last_choice_text}")
        return last_choice_key, last_choice_text

    weights = {k: v / total_choices for k, v in choice_counter.items()}
    selected_choice = random.choices(list(weights.keys()), list(weights.values()), k=1)[
        0
    ]
    selected_text = choices[selected_choice]
    logger.info(
        f"Selected choice based on proportions: {selected_choice} {selected_text}"
    )

    text_counts = {text: 0 for text in choices.values()}
    for k, v in choice_counter.items():
        text_counts[choices[k]] = v
    text_counts = dict(sorted(text_counts.items(), key=lambda item: item[0]))
    text_weights = {text: f"{text_counts[text]}/{total_choices}={text_counts[text]/total_choices:.5f}" for text in text_counts}
    logger.info(f"Choice proportions: {text_weights}")

    perm_choices = {}
    for resp in last_iteration["choices_pair"]:
        perm_choices.setdefault(resp["perm_index"], []).append(resp["choice_key"])

    logger.info("Permutation-based choice statistics:")
    for perm_idx, choices_list in sorted(perm_choices.items()):
        counter = Counter(choices_list)
        perm_total = len(choices_list)
        perm_counts = {text: 0 for text in choices.values()}
        for k, v in counter.items():
            perm_counts[choices[k]] = v
        text_stats = {text: f"{perm_counts[text]}/{perm_total}={perm_counts[text]/perm_total:.5f}" for text in sorted(perm_counts.keys())}
        logger.info(f"  Permutation {perm_idx}: {text_stats}")

    return selected_choice, selected_text

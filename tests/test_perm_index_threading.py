"""
Proves perm_index threads correctly from execute_choice_selection (DBHLLM/prompts/utils.py)
through all 7 production get_choose_prompt closures into the perm-aware
get_choices_text(choices, perm_index).

Drives the REAL production closures directly (not copies) by monkeypatching only `self.query` on
each agent instance. No real LLM/API calls, no ClearML/Langfuse/LiteLLM initialization:
is_enabled_clearml() stays False for the whole process (nothing here calls init_clearml), and
self.query is fully replaced so the real LLMAPI.query (which would try to import openai/langfuse)
is never invoked.
"""
import inspect
import math
import random
import sys
from collections import Counter

import pytest
from PIL import Image

from core.event import EventSystemCallbackDropEvent
from DBHLLM.narrator import (
    GetImageDescriptionsEvent,
    GetImageDescriptionsResponse,
    GetPlotSummariesEvent,
    GetPlotSummariesResponse,
)
from DBHLLM.omni_player import OmniPlayer
from DBHLLM.player import LLMPlayer, LLMTextOnlyPlayer
from DBHLLM.prompts.omni_player import OmniChoosePrompt, OmniDeepThinkPrompt
from DBHLLM.prompts.player import ChoosePrompt as PlayerChoosePrompt
from DBHLLM.prompts.player import DeepThinkPrompt
from DBHLLM.prompts.utils import get_choice_collection_tasks, get_choices_text
from scenes.other import harp_agent, harp_bridge, harp_bridge_ablation, harp_default

# 3 choices -> 6 permutations: enough for the per-permutation count check below to actually
# distinguish a broken (random) implementation from a correct (perm_index-driven) one.
CHOICES = {"A": "Option Alpha", "B": "Option Beta", "C": "Option Gamma"}
COLLECT_N = 2  # samples per permutation -> 6 * 2 = 12 tasks total

# Choices-block marker text for each family's own template.
PLAYER_MARKER = (
    "You can only choose one option from the following valid choices. Other options "
    "metioned in the context are invalid and should be ignored.\n\n"
)  # "metioned" is a real typo in DBHLLM/prompts/player.py -- copied verbatim
OMNI_MARKER = (
    "You can only choose one option from the following valid choices. Other options "
    "mentioned in the context are invalid and should be ignored.\n\n"
)
HARP_DEFAULT_STYLE_MARKER = "# Valid Choices\n\n"
HARP_BRIDGE_STYLE_START = "Valid Choices:\n\n"
HARP_BRIDGE_STYLE_END = "\n\nOnly choose one option from the valid choices."


def _prompt_text(prompt):
    return prompt[0]["content"][0]["text"]


def _extract_block_trailing_marker(text, marker):
    """For templates where {choices} is the LAST placeholder: one marker occurrence, then the
    choices block, then a single trailing newline before the template's closing triple-quote."""
    assert text.count(marker) == 1
    block = text.split(marker, 1)[1]
    assert block.endswith("\n")
    return block[:-1]


def _extract_block_bounded(text, start, end):
    """For templates where {choices} is followed by more template content (harp_bridge*.py)."""
    assert text.count(start) == 1
    after = text.split(start, 1)[1]
    assert after.count(end) == 1
    return after.split(end, 1)[0]


def _set_balanced_perm_env(monkeypatch):
    """choice_type=2 (balanced permutations) + think_iterations=0 (deep-think branch i>0 never
    runs) + collect_n_choices/collect_n_important_choices/harp.collect_n_important_choices all
    forced to COLLECT_N.

    All three collect_n* vars must be set explicitly: config.template.yaml already sets
    agent.collect_n_important_choices=20 and harp.collect_n_important_choices=0 as real,
    non-fallback os.environ values (verified:
    `os.environ.get("agent.collect_n_important_choices") == "20"` and
    `os.environ.get("harp.collect_n_important_choices") == "0"` after CONFIG load). Since every
    family here defaults important_choices=[] (-> is_important_choice always True), those pre-set
    values -- not the os.getenv(..., self.collect_n_choices) fallback -- are what each family's
    __init__ actually reads, so relying on the fallback would silently pull in 20 or an
    auto-calculated N instead of COLLECT_N.
    """
    monkeypatch.setenv("agent.choice_type", "2")
    monkeypatch.setenv("agent.collect_n_choices", str(COLLECT_N))
    monkeypatch.setenv("agent.collect_n_important_choices", str(COLLECT_N))
    monkeypatch.setenv("harp.collect_n_important_choices", str(COLLECT_N))
    monkeypatch.setenv("agent.think_iterations", "0")


def _assert_choices_pair(choices_pair, extract_block_fn):
    """Shared assertion: every prompt's choices-block equals get_choices_text(CHOICES, perm_index) for
    that entry's own perm_index, AND the perm_index distribution matches get_choice_collection_tasks's
    balanced-permutation output exactly (proves execute_choice_selection actually threads a distinct,
    meaningful perm_index into every prompt -- not just 0 or random)."""
    assert len(choices_pair) == COLLECT_N * math.factorial(len(CHOICES))
    for entry in choices_pair:
        block = extract_block_fn(_prompt_text(entry["prompt"]))
        assert block == get_choices_text(CHOICES, entry["perm_index"])
    counts = Counter(entry["perm_index"] for entry in choices_pair)
    total_perms = math.factorial(len(CHOICES))
    assert len(counts) == total_perms
    assert len(set(counts.values())) == 1
    expected_tasks = get_choice_collection_tasks(CHOICES, COLLECT_N, choice_type=2)
    assert counts == Counter(expected_tasks)


def _drive_choose_with_callbacks(gen, n_callback_pairs):
    """Advance a generator-based choose() (LLMPlayer/LLMTextOnlyPlayer) through n_callback_pairs
    ImageDescriptions[, PlotSummaries] request/response round-trips using the exact
    yield/send protocol of EventSystem.wait_for_callback():
        res = yield              # 1st next()/send(None) yields the request Event
        yield EventSystemCallbackDropEvent()  # sending the Response yields this drop marker
        return res                # finalized on the following send(None)
    Then catches the StopIteration carrying the final ActionEvent (choose()'s `return
    ActionEvent(...)` after execute_choice_selection runs synchronously)."""
    responses = [
        (GetImageDescriptionsEvent, GetImageDescriptionsResponse, {"image_descriptions": "dummy image description"}),
        (GetPlotSummariesEvent, GetPlotSummariesResponse, {"plot_summaries": "dummy plot summary"}),
    ][:n_callback_pairs]
    ev = next(gen)
    for i, (event_cls, response_cls, kwargs) in enumerate(responses):
        assert isinstance(ev, event_cls)
        assert gen.send(None) is None  # enter the bare `yield` inside wait_for_callback()
        drop = gen.send(response_cls(kwargs=kwargs))
        assert isinstance(drop, EventSystemCallbackDropEvent)
        if i < len(responses) - 1:
            ev = gen.send(None)  # finalize this pair, get the next Event
    try:
        gen.send(None)  # finalize the last wait_for_callback(); rest of choose() runs synchronously
        raise AssertionError("expected StopIteration carrying the final ActionEvent")
    except StopIteration as exc:
        return exc.value


def _fake_query(response_cls, choices):
    """Fake `self.query` returning a canned valid Response. chosen_option MUST be a choice VALUE
    (not a key): extract_and_validate_choice_text (DBHLLM/prompts/utils.py) matches
    response.chosen_option against choices.values(), so a key would raise ValueError and
    collect_single_choice's retry-forever loop would hang."""
    key = next(iter(choices))

    def _query(*args, **kwargs):
        return response_cls(reasons="test reason", chosen_option=choices[key])

    return _query


# --------------------------------------------------------------------------------------
# LLMPlayer.choose (DBHLLM/player.py) -- generator, 2 callback pairs.
# --------------------------------------------------------------------------------------
def test_llm_player_perm_index_threading(monkeypatch):
    _set_balanced_perm_env(monkeypatch)
    agent = LLMPlayer(chapter_summary="chapter", protagonist_summary="protagonist")
    agent.query = _fake_query(PlayerChoosePrompt.Response, CHOICES)

    gen = agent.choose(key="opt_0", context="ctx", choices=CHOICES, info={})
    action_event = _drive_choose_with_callbacks(gen, n_callback_pairs=2)

    assert action_event.kwargs.choice_key in CHOICES
    choices_pair = agent._choices_history["opt_0"][-1]["choices_pair"]
    _assert_choices_pair(choices_pair, lambda text: _extract_block_trailing_marker(text, PLAYER_MARKER))


# --------------------------------------------------------------------------------------
# LLMTextOnlyPlayer.choose (DBHLLM/player.py) -- generator, 1 callback pair.
# --------------------------------------------------------------------------------------
def test_llm_text_only_player_perm_index_threading(monkeypatch):
    _set_balanced_perm_env(monkeypatch)
    agent = LLMTextOnlyPlayer(chapter_summary="chapter", protagonist_summary="protagonist")
    agent.query = _fake_query(PlayerChoosePrompt.Response, CHOICES)

    gen = agent.choose(key="opt_0", context="ctx", choices=CHOICES, info={})
    action_event = _drive_choose_with_callbacks(gen, n_callback_pairs=1)

    assert action_event.kwargs.choice_key in CHOICES
    choices_pair = agent._choices_history["opt_0"][-1]["choices_pair"]
    _assert_choices_pair(choices_pair, lambda text: _extract_block_trailing_marker(text, PLAYER_MARKER))


# --------------------------------------------------------------------------------------
# OmniPlayer.choose (DBHLLM/omni_player.py) -- plain function.
# --------------------------------------------------------------------------------------
def test_omni_player_perm_index_threading(monkeypatch):
    _set_balanced_perm_env(monkeypatch)
    agent = OmniPlayer(chapter_summary="chapter", protagonist_summary="protagonist")
    assert agent._special_model_instance is None  # fake self.query is the only seam used
    agent._combiner.add_image(Image.new("RGB", (10, 10)))  # matches what process_obs does in production
    agent.query = _fake_query(OmniChoosePrompt.Response, CHOICES)

    action_event = agent.choose(key="opt_0", context="ctx", choices=CHOICES, info={})

    assert action_event.kwargs.choice_key in CHOICES
    choices_pair = agent._choices_history["opt_0"][-1]["choices_pair"]
    _assert_choices_pair(choices_pair, lambda text: _extract_block_trailing_marker(text, OMNI_MARKER))


# --------------------------------------------------------------------------------------
# LLMAgent.choose (scenes/other/harp_default.py) -- plain function.
# --------------------------------------------------------------------------------------
def test_harp_default_perm_index_threading(monkeypatch):
    _set_balanced_perm_env(monkeypatch)
    agent = harp_default.LLMAgent()
    agent.query = _fake_query(harp_default.ChoosePrompt.Response, CHOICES)

    action_event = agent.choose(name="scene1", scenario="scenario text", choices=CHOICES)

    assert action_event.kwargs.choice_key in CHOICES
    choices_pair = agent._choices_history["scene1"][-1]["choices_pair"]
    _assert_choices_pair(choices_pair, lambda text: _extract_block_trailing_marker(text, HARP_DEFAULT_STYLE_MARKER))


# --------------------------------------------------------------------------------------
# LLMAgent.choose (scenes/other/harp_agent.py) -- plain function, mirrors harp_default.py.
# --------------------------------------------------------------------------------------
def test_harp_agent_perm_index_threading(monkeypatch):
    _set_balanced_perm_env(monkeypatch)
    agent = harp_agent.LLMAgent()
    agent.query = _fake_query(harp_agent.ChoosePrompt.Response, CHOICES)

    action_event = agent.choose(name="scene1", scenario="scenario text", choices=CHOICES)

    assert action_event.kwargs.choice_key in CHOICES
    choices_pair = agent._choices_history["scene1"][-1]["choices_pair"]
    _assert_choices_pair(choices_pair, lambda text: _extract_block_trailing_marker(text, HARP_DEFAULT_STYLE_MARKER))


# --------------------------------------------------------------------------------------
# LLMAgent.choose (scenes/other/harp_bridge.py) -- plain function, perspective="first" default.
# --------------------------------------------------------------------------------------
def test_harp_bridge_perm_index_threading(monkeypatch):
    _set_balanced_perm_env(monkeypatch)
    agent = harp_bridge.LLMAgent()
    assert agent.perspective == "first"
    agent.query = _fake_query(harp_bridge.ChoosePrompt.Response, CHOICES)

    action_event = agent.choose(name="scene1", scenario="scenario text", choices=CHOICES)

    assert action_event.kwargs.choice_key in CHOICES
    choices_pair = agent._choices_history["scene1"][-1]["choices_pair"]
    _assert_choices_pair(
        choices_pair,
        lambda text: _extract_block_bounded(text, HARP_BRIDGE_STYLE_START, HARP_BRIDGE_STYLE_END),
    )


# --------------------------------------------------------------------------------------
# LLMAgent.choose (scenes/other/harp_bridge_ablation.py) -- plain function, image/dialogue
# default to None (safe to omit).
# --------------------------------------------------------------------------------------
def test_harp_bridge_ablation_perm_index_threading(monkeypatch):
    _set_balanced_perm_env(monkeypatch)
    agent = harp_bridge_ablation.LLMAgent()
    agent.query = _fake_query(harp_bridge_ablation.ChoosePrompt.Response, CHOICES)

    action_event = agent.choose(name="scene1", scenario="scenario text", choices=CHOICES)

    assert action_event.kwargs.choice_key in CHOICES
    choices_pair = agent._choices_history["scene1"][-1]["choices_pair"]
    _assert_choices_pair(
        choices_pair,
        lambda text: _extract_block_bounded(text, HARP_BRIDGE_STYLE_START, HARP_BRIDGE_STYLE_END),
    )


# --------------------------------------------------------------------------------------
# The four deep-think builders (player, omni, harp_default, harp_agent) are never given a
# perm_index, so their get_choices_text call stays on the random branch (perm_index=0).
# think_iterations=0 in the threading tests above means the deep-think branch never runs there;
# these tests call the four builders directly.
# --------------------------------------------------------------------------------------
DEEP_THINK_MARKER = "\n# Choices\n\n"  # {choices} is the last placeholder of all four deep-think templates

DEEP_THINK_CASES = [
    pytest.param(
        DeepThinkPrompt,
        {
            "protagonist_summary": "protagonist",
            "chapter_summary": "chapter",
            "image_descriptions": "img desc",
            "plot_summaries": "plot summary",
            "dialogue": "dialogue",
            "choices": CHOICES,
            "thoughts": "",
            "memory": "memory",
        },
        id="player",
    ),
    pytest.param(
        OmniDeepThinkPrompt,
        {
            "protagonist_summary": "protagonist",
            "chapter_summary": "chapter",
            "choices": CHOICES,
            "thoughts": "",
            "memory": "memory",
            "image": Image.new("RGB", (10, 10)),
            "image_detail": "high",
            "dialogue": "ctx",
        },
        id="omni",
    ),
    pytest.param(
        harp_default.DeepThinkPrompt,
        {"scenario": "scenario text", "choices": CHOICES, "thoughts": ""},
        id="harp_default",
    ),
    pytest.param(
        harp_agent.DeepThinkPrompt,
        {"scenario": "scenario text", "choices": CHOICES, "thoughts": ""},
        id="harp_agent",
    ),
]


@pytest.mark.parametrize("prompt_cls, kwargs", DEEP_THINK_CASES)
def test_deep_think_builder_passes_perm_index_zero(monkeypatch, prompt_cls, kwargs):
    module = sys.modules[prompt_cls.__module__]
    assert module.get_choices_text is get_choices_text  # the builder's own binding is the one perm-aware function
    signature = inspect.signature(get_choices_text)
    received = []

    def spy(*args, **spy_kwargs):
        bound = signature.bind(*args, **spy_kwargs)
        bound.apply_defaults()
        received.append(bound.arguments["perm_index"])
        return get_choices_text(*args, **spy_kwargs)

    monkeypatch.setattr(module, "get_choices_text", spy)
    prompt_cls.get_prompt(**kwargs)
    assert received == [0]


@pytest.mark.parametrize("prompt_cls, kwargs", DEEP_THINK_CASES)
def test_deep_think_builder_renders_the_random_branch_order(monkeypatch, prompt_cls, kwargs):
    # get_choices_text's perm_index=0 branch calls random.shuffle on the key-sorted items; reversing
    # them in place makes that branch deterministic: descending key order.
    monkeypatch.setattr(random, "shuffle", lambda items: items.reverse())
    block = _extract_block_trailing_marker(_prompt_text(prompt_cls.get_prompt(**kwargs)), DEEP_THINK_MARKER)
    assert block == "\n".join(f"- {value}" for _, value in sorted(CHOICES.items(), reverse=True))

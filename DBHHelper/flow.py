from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable


import inspect
import random

import dill as pickle
import networkx as nx
import rich
import yaml
from rich.pretty import pretty_repr
from rich.text import Text

from core.event import EventDispatcher, EventSystem, EventSystemCloseEvent
from core.flow import BaseFlow
from core.log import get_clearml, get_logger, is_enabled_clearml
from core.scenario import ScenarioNotCompletedEvent
from core.transform import auto_yield_class, register_auto_yield
from core.utils import Infix, get_status_manager
from DBHHelper.api import DBHHelperAPI
from DBHHelper.events import ActionEvent
from DBHHelper.utils import (
    FrozenKeysDict,
    GraphProcessor,
    draw_flowgraph,
    generate_combined_id,
)

GP = GraphProcessor()
E = Infix(GP.add_edge)


@auto_yield_class
class DBHFlow(EventDispatcher, BaseFlow):
    chapter_number: int
    dbhh: DBHHelperAPI

    def __init__(
        self,
        dbhh: DBHHelperAPI,
        cfg: dict,
        auto: int = 2,
        ending: int = 0,
        choices: dict | None = None,
    ) -> None:
        self.dbhh = dbhh
        self._logger = get_logger()
        self.cfg = cfg
        # 3: full 2: half2 1: half1 0: none -1: llm
        self.auto = auto
        self.ending = ending
        if choices is None:
            self.choices = {}
        else:
            self.choices = choices
        self.all_choices = {}
        self.stats = {}
        if "STATS" in self.cfg:
            for key in self.cfg["STATS"]:
                self.stats[key] = ""
        self._status = {}

    @property
    def status(self):
        if self._status is None:
            raise AttributeError("settings not initialized yet; assign a dict first.")
        return self._status

    @status.setter
    def status(self, value):
        # Accept plain dicts and wrap them.
        if isinstance(value, dict):
            if self._status is None:
                # First assignment: freeze the key set here
                self._status = FrozenKeysDict(value)
            else:
                # Later assignments just update existing keys (no new keys)
                self._status.update(value)
        else:
            raise TypeError("Assign a dict or FrozenKeysDict.")

    def setup(self):
        self.last_choice = ""
        self.path = []
        self.graph()
        self.G = GP.G
        draw_flowgraph(self.G, self._logger.log_path, logger=self._logger)

    def graph(self):
        raise NotImplementedError

    def check_graph(self):
        for node in self.G.nodes():
            assert self.G.degree(node) > 0, f"Node {node} has no edge"
            assert "func" in self.G.nodes[node], f"Node {node} has no function"

    @EventDispatcher.on(EventSystemCloseEvent)
    def draw_highlighted_flowgraph(self):
        if getattr(self, "path", None) is None:
            return
        draw_flowgraph(self.G, self._logger.log_path, self.path, logger=self._logger)

    @register_auto_yield
    def get_choice(
        self,
        KEY: str = "",
        ENDINGS: dict | None = None,
        CHOICES: dict | None = None,
        BRANCHES: dict | None = None,
        press_button: bool = True,
    ):
        func_name = inspect.stack()[1].function
        if not KEY:
            KEY = func_name
        # Default values
        CONTEXT = ""
        CHOICES_CONTEXT = {}
        STATS = {}

        # Check if KEY exists in self.cfg["CHOICES"]
        if KEY in self.cfg["CHOICES"]:
            choices_cfg = self.cfg["CHOICES"][KEY]
            CONTEXT = choices_cfg.get("CONTEXT", "")
            if CHOICES is None:
                CHOICES = choices_cfg["CHOICES"]
            CHOICES_CONTEXT = choices_cfg.get("CHOICES_CONTEXT", {})
            if BRANCHES is None:
                BRANCHES = choices_cfg.get("BRANCHES", {})
            STATS = choices_cfg.get("STATS", {})
        elif CHOICES is None:
            # KEY not in self.cfg["CHOICES"] and no CHOICES provided
            raise ValueError(
                f"No choices configuration found for '{KEY}' and no CHOICES provided"
            )
        self._logger.info(f"Choices: {CHOICES}")
        self.dbhh.obs(context=CONTEXT, choices=CHOICES, choice_stage="before")
        if self.auto >= 1:
            flag = False
            for cond, choice in ENDINGS.items():
                if cond(self):
                    CHOICE = choice
                    flag = True
                    break
            if not flag:
                if self.ending == 0:
                    CHOICE = self.choices[KEY]
                else:
                    CHOICE = random.choice(list(CHOICES.keys()))
        elif self.auto >= 0:
            CHOICE = self.dbhh.get_choice_from_input(CHOICES.keys())
        else:
            # Use KEY directly without modification
            # Create combined data structure here
            combined_data = {
                "status": self.status,
                "choices": CHOICES,
                "context": CONTEXT if CONTEXT is not None else "",
            }
            hash_id = generate_combined_id(combined_data)
            modified_key = KEY + "_" + hash_id
            action_event: ActionEvent = self.dbhh.act(
                key=modified_key,
                context=CONTEXT,
                choices=CHOICES,
                info=combined_data,
            )
            self._logger.debug(f"Received action event: {pretty_repr(action_event)}")
            CHOICE = action_event.kwargs.choice_key
        if press_button:
            self.dbhh.vg_press_button(button=CHOICE)
            if CHOICES[CHOICE] in CHOICES_CONTEXT:
                self.dbhh.obs(
                    context=CHOICES_CONTEXT[CHOICES[CHOICE]], choice_stage="after"
                )
        self.last_choice = CHOICES[CHOICE]
        if BRANCHES:
            self.next_branch = BRANCHES[CHOICE]
        if STATS and CHOICE in STATS["VALUES"]:
            self.stats[STATS["KEY"]] = STATS["VALUES"][CHOICE]
        self.all_choices[KEY] = CHOICE
        self._logger.info(f"Choosing {self.last_choice}")
        return CHOICE

    def save_stats(self):
        _stats = {
            "chapter": self.cfg["CHAPTER"],
            "stats": self.stats,
            "choices": self.all_choices,
            "ending": self.ending,
            "path": self.path,
        }
        with open(
            f"{self._logger.log_path}/flow_stats.yaml", "w", encoding="utf-8"
        ) as f:
            yaml.safe_dump(_stats, f, default_flow_style=False, allow_unicode=True)
        if is_enabled_clearml():
            task = get_clearml()
            task.upload_artifact(
                name="flow_stats.yaml",
                artifact_object=f"{self._logger.log_path}/flow_stats.yaml",
                metadata={"description": "Flow stats"},
            )

    def START(self):
        # self.dbhh.wait_for_input()
        self.dbhh.activate_win()
        self.dbhh.activate_vg()
        self.dbhh.set_default_game_speed()

    def FLOWCHART(self):
        self.dbhh.wait_for_cutscene("CS_FLOWCHART")
        self.dbhh.vg_press_button(button="A")
        self.dbhh.wait(20, speedup=False)
        self.dbhh.obs()
        self.dbhh.vg_press_button(button="A")
        self.dbhh.wait(5, speedup=False)

    def END(self):
        self.dbhh.exit_to_main_menu()
        self.save_stats()

    @EventDispatcher.on(ScenarioNotCompletedEvent)
    def no_complete_exit(self):
        self._logger.info(
            "Scenario not completed. Wait for 3 seconds and exit to main menu."
        )
        self.dbhh.reset_gamepad()
        self.dbhh.set_default_game_speed()
        self.dbhh.wait(seconds=3, speedup=False)
        try:
            self.dbhh.exit_to_main_menu(timeout=10, ignore_error=True)
        except Exception as e:
            self._logger.error(f"Failed to exit to main menu: {e}")
        except KeyboardInterrupt:
            self._logger.error("KeyboardInterrupt", exc_info=True)

    def run(self):
        cur = "START"
        console = rich.get_console()
        status_manager = get_status_manager()

        while True:
            func = self.G.nodes[cur]["func"]

            # Create managed status that can be paused globally
            status_text = Text(f"Running Node {func.__name__}...", style="bold green")
            with status_manager.create_status(console, status_text) as status:
                self._logger.info(f"Running Node {func.__name__}")
                result = func()
                self._logger.debug(f"Node {func.__name__} returned: {result}")

                self.path.append(cur)
                if inspect.isgenerator(result):
                    # The status will be automatically paused by parallel_execute
                    # when Progress needs to use the console
                    yield from result

            next_nodes = list(self.G.successors(cur))
            if len(next_nodes) == 0:
                break
            if len(next_nodes) == 1:
                cur = next_nodes[0]
            else:
                assert self.next_branch in next_nodes, (
                    f"Branch {self.next_branch} not found in {next_nodes}"
                )
                cur = self.next_branch

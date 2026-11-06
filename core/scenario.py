from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from typing import Generator

    from core.event import EventDispatcher

import gc
import logging

import rich

from core.event import Event, EventSystem
from core.log import close_logger, init_global_logger


class ScenarioNotCompletedEvent(Event):
    name: str = "scenario_not_completed_event"


class ScenarioCompleteEvent(Event):
    name: str = "scenario_complete_event"


class Scenario:
    main_g: Generator[Event, Event, None]
    triggers: List[EventDispatcher]

    def __init__(
        self,
        scen_name: str,
        run_name: str,
        levels=(logging.INFO, logging.INFO, logging.DEBUG),
        tags=None,
    ):
        self.scen_name = scen_name
        self.run_name = run_name
        self._logger = init_global_logger(
            self.scen_name,
            self.run_name,
            levels=levels,
            tags=tags,
        )
        self._is_completed = False

    def setup(self):
        raise NotImplementedError("Scenario setup not implemented")

    def run(self):
        self._logger.info("Running scenario")
        try:
            with rich.get_console().status(
                "[bold blue]Running Scenario Setup..."
            ) as status:
                self.setup()
            assert self.main_g is not None, "Main generator not set"
            assert self.triggers is not None, "Triggers not set"
            self.event_system = EventSystem(self.main_g, self.triggers)
            self.event_system.run()
            self._is_completed = True
        except Exception:
            self._logger.error("Error running scenario", exc_info=True)
        except KeyboardInterrupt:
            self._logger.info("Keyboard interrupt")
        finally:
            self.close()
        return 0 if self._is_completed else 1

    def close(self):
        self._logger.info("Closing scenario")
        try:
            if hasattr(self, "event_system"):
                self.event_system.close_generators()
                with rich.get_console().status(
                    "[bold blue]Closing Event System..."
                ) as status:
                    if self._is_completed:
                        self.event_system.one_event(
                            ScenarioCompleteEvent(), "Scenario"
                        )
                    else:
                        self.event_system.one_event(
                            ScenarioNotCompletedEvent(), "Scenario"
                        )
                    self.event_system.close()
        except Exception:
            self._logger.error("Error closing event system", exc_info=True)
        except KeyboardInterrupt:
            self._logger.info("Keyboard interrupt")
        close_logger()
        gc.collect()

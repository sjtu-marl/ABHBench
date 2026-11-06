import inspect
import os
import re
import time
from typing import override

from PIL import Image, ImageGrab

from core.event import EventSystem
from core.log import get_clearml, is_enabled_clearml, is_enabled_langfuse
from core.transform import register_auto_yield
from core.utils import save_obs_image

from ..api import DBHHelperAPI
from ..events import (
    ActEvent,
    ActionEvent,
    ObsEvent,
    ObsWithActEvent,
    ObsWithContextAndChoicesEvent,
    ObsWithContextEvent,
)


class IOMixin(DBHHelperAPI):
    @override
    def io_setup(self, obs_interval=1, obs_move_interval=3):
        self.obs_interval = obs_interval
        self.obs_move_interval = obs_move_interval
        self.obs_index = 0
        self.cur_obs = None
        self._last_act = None

    @override
    def set_last_act(self, act: str):
        self._last_act = act

    @override
    def wait_for_input(self, delay=3):
        input(f"Press Enter to wait for {delay} seconds...")
        for i in range(delay):
            time.sleep(1)
            self.info(f"Waiting... {delay - i}")
        self.win.activate()
        self.info("CONTINUE")

    @override
    def screenshot(self):
        l, t, r, b = self.win.getClientFrame()
        screenshot = ImageGrab.grab(bbox=(l, t, r, b))
        if (
            is_enabled_clearml()
            and not is_enabled_langfuse()
            and os.getenv("flags.upload_obs", "true").lower() == "true"
        ):
            task = get_clearml()
            task.get_logger().report_image(
                "Raw Screenshot",
                "raw screenshot",
                self.obs_index,
                image=screenshot,
            )

        # Save image locally if enabled
        save_obs_image(screenshot, "Raw Screenshot", "raw screenshot", self.obs_index)
        self.cur_obs = screenshot
        self.obs_index += 1
        return self.cur_obs

    @register_auto_yield
    @override
    def obs(self, context=None, choices=None, choice_stage=None):
        self.pause()

        obs = self.screenshot()
        if context is not None:
            if choices is not None:
                yield ObsWithContextAndChoicesEvent(
                    kwargs={
                        "obs": obs,
                        "context": context,
                        "choices": choices,
                    }
                )
            else:
                yield ObsWithContextEvent(
                    kwargs={
                        "obs": obs,
                        "context": context,
                    }
                )
        elif self._last_act is not None:
            yield ObsWithActEvent(
                kwargs={
                    "obs": obs,
                    "act": self._last_act,
                }
            )
            self._last_act = None
        else:
            yield ObsEvent(kwargs={"obs": obs})
        self.resume()

    @register_auto_yield
    @override
    def act(
        self,
        key: str,
        context: str,
        choices: dict,
        info: dict,
    ):
        self.pause()
        self.debug(f"ACT: key={key}, context={context}, choices={choices}, info={info}")
        yield ActEvent(
            kwargs={
                "key": key,
                "context": context,
                "choices": choices,
                "info": info,
            },
            callback=ActionEvent,
        )
        self.debug("Waiting for action...")
        action_event: ActionEvent = yield from EventSystem.wait_for_callback()
        self.resume()
        return action_event

    @override
    def get_choice_from_input(self, choices=None):
        self.pause()
        self.info("Waiting for choice...")
        if choices is None:
            CHOICE = input()
        else:
            while True:
                CHOICE = input(f"Choose from {choices}: ")
                if CHOICE in choices:
                    break
        self.wait(1)
        self.resume()
        self.activate_win()
        self.wait(0.5)
        return CHOICE

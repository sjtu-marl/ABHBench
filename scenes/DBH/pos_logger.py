import logging
import os
import time

from PIL import Image
from pydantic import BaseModel
from pynput import keyboard

import DBHHelper.gamepad as gp
from core.event import Event, EventDispatcher, EventSystemCloseEvent
from core.scenario import Scenario
from core.transform import auto_yield_class, register_auto_yield
from DBHHelper.events import (
    ObsEvent,
    ObsWithActEvent,
    ObsWithContextAndChoicesEvent,
    ObsWithContextEvent,
)
from DBHHelper.helper import DBHHelper

os.environ["flags.save_obs_local"] = "true"


class EndEvent(Event):
    name: str = "end_event"


class ObsSaver(EventDispatcher):
    def __init__(self, folder: str, start_index: int = 0):
        self._folder = folder
        self._start_index = start_index
        self._index = start_index

    @EventDispatcher.on(
        [ObsEvent, ObsWithContextEvent, ObsWithActEvent, ObsWithContextAndChoicesEvent]
    )
    def save(self, obs: Image.Image):
        filename = f"{self._folder}/obs_{self._index:04d}.jpeg"
        obs.save(filename)
        self._index += 1
        return filename


@auto_yield_class
class Flow(EventDispatcher):
    def __init__(
        self,
        dbhh: DBHHelper,
        gamepad_type=gp.Gamepads.Xbox360,
        trigger_btn="BACK",
        exit_btn="XBOX",
    ):
        self.dbhh = dbhh
        self.gamepad_type = gamepad_type
        self.trigger_btn = trigger_btn
        self.exit_btn = exit_btn
        self.gamepad = None
        self.keyboard_listener = None
        self.running = False
        self.exit_requested = False

    def setup(self):
        self.n = 0

    def log_mem(self):
        output = f"""
--------{self.n}---------
model_pos: {self.dbhh.read_model_pos()}
camera_pos: {self.dbhh.read_camera_pos()[:2]}
camera_pos_z: {self.dbhh.read_camera_pos()[2]}
view: {self.dbhh.read_camera_pos()[3:]}
num_poi: {self.dbhh.read_num_poi()}
--------{self.n}---------"""
        self.dbhh.info(output)
        self.dbhh.screenshot()
        self.n += 1

    def trigger_callback(self):
        """Callback for when the trigger button is pressed"""
        self.log_mem()

    def exit_callback(self):
        """Callback for when exit is requested"""
        self.dbhh.info("Exit requested. Shutting down...")
        self.exit_requested = True

    def keyboard_listen(self):
        """Set up keyboard listener for key press events"""
        try:
            # Set up keyboard listener with callbacks
            self.keyboard_listener = keyboard.Listener(
                on_press=self.on_key_press,
                on_release=None,  # We don't need release events
            )
            self.keyboard_listener.start()
            self.dbhh.info(
                "Keyboard controls enabled: Press 'p' to log memory. Press 'F4' to exit."
            )
            return True
        except Exception as e:
            self.dbhh.info(f"Could not initialize keyboard controls: {e}")
            return False

    def on_key_press(self, key):
        """Handle key press events"""
        try:
            # Check if it's a special key like F4
            if key == keyboard.Key.f4:
                self.exit_callback()

            if key == keyboard.Key.f6:
                time.sleep(1)
                self.dbhh.activate_vg()

            # Check if it's an alphanumeric key
            if hasattr(key, "char"):
                if key.char == "p":
                    self.trigger_callback()

                if key.char == "j":
                    time.sleep(1)
                    self.dbhh.activate_vg()
                    self.dbhh.vg_press_button(button="X")
                if key.char == "i":
                    time.sleep(1)
                    self.dbhh.activate_vg()
                    self.dbhh.vg_press_button(button="Y")
                if key.char == "k":
                    time.sleep(1)
                    self.dbhh.activate_vg()
                    self.dbhh.vg_press_button(button="A")
                if key.char == "l":
                    time.sleep(1)
                    self.dbhh.activate_vg()
                    self.dbhh.vg_press_button(button="B")
        except Exception as e:
            self.dbhh.info(f"Error processing keyboard input: {e}")

    def gamepad_listen(self):
        if not gp.available():
            self.dbhh.info("No gamepad available.")
            return False

        gamepad = self.gamepad_type()
        self.gamepad = gamepad

        if not gamepad.isConnected():
            self.dbhh.info("Gamepad could not connect.")
            return False

        self.dbhh.info(
            f"Gamepad {self.gamepad_type.__name__} connected. "
            f"Press {self.trigger_btn} to log memory. Press {self.exit_btn} to exit."
        )
        self.dbhh.info(f"Images will be saved to {self.dbhh._logger.log_path}")

        # Start background updates
        gamepad.startBackgroundUpdates()

        # Register button handlers
        gamepad.addButtonPressedHandler(self.trigger_btn, self.trigger_callback)
        gamepad.addButtonPressedHandler(self.exit_btn, self.exit_callback)

        return True

    def run(self):
        gamepad_available = self.gamepad_listen()
        keyboard_available = self.keyboard_listen()

        if not gamepad_available and not keyboard_available:
            print("Neither gamepad nor keyboard controls could be initialized.")
            return

        if not gamepad_available:
            print("Gamepad not available. Using keyboard controls only.")
        else:
            if keyboard_available:
                print("Both gamepad and keyboard controls enabled.")
                print(
                    "You can use either gamepad buttons or keyboard keys to control the application."
                )

        self.running = True
        self.exit_requested = False

        # Keep running until exit is requested or all input methods are unavailable
        while self.running and not self.exit_requested:
            if gamepad_available and self.gamepad and not self.gamepad.isConnected():
                self.dbhh.info("Gamepad disconnected.")
                gamepad_available = False
                if not keyboard_available:
                    break

            # Sleep briefly to avoid consuming CPU
            time.sleep(0.1)
        yield EndEvent()

    @EventDispatcher.on(EventSystemCloseEvent)
    def close(self):
        self.running = False

        # Clean up gamepad if available
        if self.gamepad:
            # Stop background updates before disconnecting
            self.gamepad.stopBackgroundUpdates()
            self.gamepad.disconnect()

        # Clean up keyboard listener if available
        if self.keyboard_listener:
            self.keyboard_listener.stop()


class Scen(Scenario):
    def __init__(self):
        super().__init__(
            "DBH_Extra",
            "pos_logger",
            levels=(
                logging.DEBUG
                if os.getenv("flags.console_debug", "false").lower() == "true"
                else logging.INFO,
                logging.INFO,
                logging.DEBUG,
            ),
            tags=["DBH", "pos_logger"],
        )

    def setup(self):
        dbhh = DBHHelper()
        flow = Flow(dbhh)
        flow.setup()
        dbhh.setup(enable_speedhack=False, window_adjust=False)
        # Log initial info about available controls
        dbhh.info("Position logger starting with gamepad and keyboard support")
        dbhh.info("Keyboard controls: 'p' to log memory, 'F4' to exit")
        self.main_g = flow.run
        self.triggers = [dbhh, flow]


if __name__ == "__main__":
    Scen().run()

import json
import time
from typing import override

import numpy as np

from core.utils import dict_config
from DBHHelper.api import DBHHelperAPI


def is_clockwise(sequence):
    # Map directions to numerical values: L -> 0, U -> 1, R -> 2, D -> 3
    direction_map = {"L": 0, "U": 1, "R": 2, "D": 3}

    # Calculate the differences between adjacent directions
    differences = []
    for i in range(len(sequence) - 1):
        current_dir = direction_map[sequence[i]]
        next_dir = direction_map[sequence[i + 1]]
        diff = (next_dir - current_dir) % 4
        differences.append(diff)

    # Determine if the sequence is clockwise or counterclockwise
    if all(diff == 1 for diff in differences):
        return True  # Clockwise
    elif all(diff == 3 for diff in differences):
        return False  # Counterclockwise
    else:
        return None  # Indeterminate (not a simple circular path)


class VGMixin(DBHHelperAPI):
    @override
    def vg_setup(self):
        # gamepad forward y 1.0, right x 1.0
        self.gamepad = self.ppack.VX360Gamepad()
        # Track gamepad state
        self._gamepad_state = {
            "buttons": {
                "A": False,
                "B": False,
                "X": False,
                "Y": False,
                "LEFT_SHOULDER": False,
                "RIGHT_SHOULDER": False,
                "LEFT_THUMB": False,
                "RIGHT_THUMB": False,
                "START": False,
                "BACK": False,
                "GUIDE": False,
                "DPAD_UP": False,
                "DPAD_DOWN": False,
                "DPAD_LEFT": False,
                "DPAD_RIGHT": False,
            },
            "joysticks": {"left": {"x": 0.0, "y": 0.0}, "right": {"x": 0.0, "y": 0.0}},
            "triggers": {"left": 0.0, "right": 0.0},
        }

    @override
    def get_gamepad_state(self):
        """
        Returns the current state of the gamepad for debugging purposes.

        Returns:
            dict: A dictionary containing the current state of all gamepad controls
        """
        self.debug("Getting gamepad state")
        return self._gamepad_state

    @override
    def print_gamepad_state(self):
        """
        Prints the current state of the gamepad in a readable format for debugging.
        """
        state = self.get_gamepad_state()
        formatted_state = json.dumps(state, indent=2)
        self.debug(f"Gamepad State:\n{formatted_state}")
        return formatted_state

    @override
    def activate_vg(self):
        self.gamepad.right_joystick_float(x_value_float=1, y_value_float=1)
        self._gamepad_state["joysticks"]["right"]["x"] = 1.0
        self._gamepad_state["joysticks"]["right"]["y"] = 1.0
        self.gamepad.update()
        time.sleep(0.01)
        self.reset_gamepad()
        time.sleep(0.01)
        # self.debug("Press START")
        # self.vg_press_button("START", after=2)
        # self.debug("Press START")
        # self.vg_press_button("START", after=2)
        # self.debug("Press START")
        # self.vg_press_button("START", after=2)

    @dict_config
    @override
    def interact(self, it: str | list, pause=1, after=None, retry=3):
        if isinstance(it, str):
            assert it in [
                "R_UP",
                "R_DOWN",
                "R_LEFT",
                "R_RIGHT",
                "A",
                "B",
                "X",
                "Y",
                "LEFT_SHOULDER",
                "RIGHT_SHOULDER",
                "LEFT_THUMB",
                "RIGHT_THUMB",
                "LEFT_TRIGGER",
                "RIGHT_TRIGGER",
            ]
        if isinstance(it, list):
            assert all(
                [
                    i
                    in [
                        "A",
                        "B",
                        "X",
                        "Y",
                        "LEFT_SHOULDER",
                        "RIGHT_SHOULDER",
                        "LEFT_THUMB",
                        "RIGHT_THUMB",
                        "LEFT_TRIGGER",
                        "RIGHT_TRIGGER",
                    ]
                    for i in it
                ]
            )
        self.debug(f"Interacting with {it}")
        success = False
        while True:
            if it == "R_UP":
                self.exp_rj_interact(seq=["U"], pause=pause, after=0)
            elif it == "R_DOWN":
                self.exp_rj_interact(seq=["D"], pause=pause, after=0)
            elif it == "R_LEFT":
                self.exp_rj_interact(seq=["L"], pause=pause, after=0)
            elif it == "R_RIGHT":
                self.exp_rj_interact(seq=["R"], pause=pause, after=0)
            elif it == "LEFT_TRIGGER":
                self.vg_trigger(lr="L", duration=pause, after=0)
            elif it == "RIGHT_TRIGGER":
                self.vg_trigger(lr="R", duration=pause, after=0)
            elif isinstance(it, str):
                self.vg_press_button(button=it, after=0)
            elif isinstance(it, list):
                self.vg_press_buttons(buttons=it, after=0)
            success = self.read_num_poi() == 0
            if success or not retry:
                break
            retry -= 1
        if after is not None:
            self.wait(after, speedup=False)

    @dict_config
    @override
    def rj_interact(self, xy, duration=0.2, after=0.2, keep=False):
        self.debug(f"Interacting with right joystick {xy}")
        self.gamepad.right_joystick_float(
            x_value_float=xy[0],
            y_value_float=xy[1],
        )
        # Update state
        self._gamepad_state["joysticks"]["right"]["x"] = xy[0]
        self._gamepad_state["joysticks"]["right"]["y"] = xy[1]
        self.gamepad.update()
        if keep:
            return
        time.sleep(duration)
        self.reset_gamepad()
        # Reset state
        self._gamepad_state["joysticks"]["right"]["x"] = 0.0
        self._gamepad_state["joysticks"]["right"]["y"] = 0.0
        self.gamepad.update()
        time.sleep(duration)
        self.wait(after, speedup=False)

    @dict_config
    @override
    def exp_rj_interact(
        self, seq, duration=0.05, pause=0.0, after=1, smooth=10, keep=False
    ):
        self.debug(f"Interacting with right joystick {seq}")
        clockwise = is_clockwise(seq)
        seq = ["S"] + seq
        coords = []
        for idx in range(len(seq) - 1):
            a = ",".join(seq[idx : idx + 2])
            self.debug(f"Action: {a}")
            if "S" in a:
                x, y = 0.0, 0.0
                if a == "S,L":
                    x = -1.0
                if a == "S,R":
                    x = 1.0
                if a == "S,U":
                    y = 1.0
                if a == "S,D":
                    y = -1.0
                x_coords = np.linspace(0.0, x, num=smooth)
                y_coords = np.linspace(0.0, y, num=smooth)
                if pause > 0:
                    x_coords = np.append(x_coords, [x] * int(pause / duration))
                    y_coords = np.append(y_coords, [y] * int(pause / duration))
            else:
                start_angle = 0
                end_angle = 0
                if a[0] == "L":
                    start_angle = np.pi
                if a[0] == "R":
                    start_angle = 0
                if a[0] == "U":
                    start_angle = np.pi / 2
                if a[0] == "D":
                    start_angle = np.pi * 3 / 2
                if a[-1] == "L":
                    end_angle = np.pi
                if a[-1] == "R":
                    end_angle = 0
                if a[-1] == "U":
                    end_angle = np.pi / 2
                if a[-1] == "D":
                    end_angle = np.pi * 3 / 2
                if clockwise and end_angle > start_angle:
                    end_angle -= 2 * np.pi
                if not clockwise and end_angle < start_angle:
                    end_angle += 2 * np.pi
                angles = np.linspace(start_angle, end_angle, num=smooth)
                x_coords = np.cos(angles)
                y_coords = np.sin(angles)
            coords.extend(list(zip(x_coords, y_coords)))
        for coord in coords:
            self.gamepad.right_joystick_float(
                x_value_float=float(coord[0]),
                y_value_float=float(coord[1]),
            )
            # Update state
            self._gamepad_state["joysticks"]["right"]["x"] = float(coord[0])
            self._gamepad_state["joysticks"]["right"]["y"] = float(coord[1])
            self.gamepad.update()
            time.sleep(duration)
            self.debug(f"Coord: {coord}")
        if keep:
            return
        self.gamepad.right_joystick_float(
            x_value_float=0,
            y_value_float=0,
        )
        # Reset state
        self._gamepad_state["joysticks"]["right"]["x"] = 0.0
        self._gamepad_state["joysticks"]["right"]["y"] = 0.0
        self.gamepad.update()
        time.sleep(duration)
        self.wait(after, speedup=False)

    @dict_config
    @override
    def vg_press_button(self, button, duration=0.1, after=1, keep=False):
        self.debug(f"Pressing button {button}")
        button_name = button
        if isinstance(button, str):
            button = getattr(self.ppack.XUSB_BUTTON, f"XUSB_GAMEPAD_{button}")
            # Update state
            if button_name in self._gamepad_state["buttons"]:
                self._gamepad_state["buttons"][button_name] = True
        self.gamepad.press_button(button=button)
        self.gamepad.update()
        if keep:
            return
        time.sleep(duration)
        self.gamepad.release_button(button=button)
        if (
            isinstance(button_name, str)
            and button_name in self._gamepad_state["buttons"]
        ):
            self._gamepad_state["buttons"][button_name] = False
        self.gamepad.update()
        self.wait(after, speedup=False)

    @dict_config
    @override
    def vg_press_buttons(self, buttons: list, duration=0.1, after=1, keep=False):
        self.debug(f"Pressing buttons {buttons}")
        button_names = []
        if isinstance(buttons[0], str):
            button_names = buttons.copy()
            buttons = [
                getattr(self.ppack.XUSB_BUTTON, f"XUSB_GAMEPAD_{button}")
                for button in buttons
            ]
            # Update state
            for btn in button_names:
                if btn in self._gamepad_state["buttons"]:
                    self._gamepad_state["buttons"][btn] = True

        [self.gamepad.press_button(button=button) for button in buttons]
        self.gamepad.update()
        if keep:
            return
        time.sleep(duration)
        [self.gamepad.release_button(button=button) for button in buttons]
        # Update state for release
        if button_names:
            for btn in button_names:
                if btn in self._gamepad_state["buttons"]:
                    self._gamepad_state["buttons"][btn] = False
        self.gamepad.update()
        self.wait(after, speedup=False)

    @dict_config
    @override
    def vg_release_button(self, button):
        self.debug(f"Releasing button {button}")
        button_name = button
        if isinstance(button, str):
            button = getattr(self.ppack.XUSB_BUTTON, f"XUSB_GAMEPAD_{button}")
            # Update state
            if button_name in self._gamepad_state["buttons"]:
                self._gamepad_state["buttons"][button_name] = False
        self.gamepad.release_button(button=button)
        self.gamepad.update()

    @dict_config
    @override
    def vg_release_buttons(self, buttons: list):
        self.debug(f"Releasing buttons {buttons}")
        button_names = []
        if isinstance(buttons[0], str):
            button_names = buttons.copy()
            buttons = [
                getattr(self.ppack.XUSB_BUTTON, f"XUSB_GAMEPAD_{button}")
                for button in buttons
            ]
            # Update state
            for btn in button_names:
                if btn in self._gamepad_state["buttons"]:
                    self._gamepad_state["buttons"][btn] = False

        [self.gamepad.release_button(button=button) for button in buttons]
        # Update state for release
        if button_names:
            for btn in button_names:
                if btn in self._gamepad_state["buttons"]:
                    self._gamepad_state["buttons"][btn] = False
        self.gamepad.update()

    @dict_config
    @override
    def vg_trigger(self, lr, duration=1, after=1):
        if lr == "L":
            self.gamepad.left_trigger_float(1.0)
            self._gamepad_state["triggers"]["left"] = 1.0
        elif lr == "R":
            self.gamepad.right_trigger_float(1.0)
            self._gamepad_state["triggers"]["right"] = 1.0
        else:
            raise ValueError("lr must be 'L' or 'R'")
        self.gamepad.update()
        time.sleep(duration)
        if lr == "L":
            self.gamepad.left_trigger_float(0.0)
            self._gamepad_state["triggers"]["left"] = 0.0
        elif lr == "R":
            self.gamepad.right_trigger_float(0.0)
            self._gamepad_state["triggers"]["right"] = 0.0
        self.gamepad.update()
        time.sleep(after)

    @dict_config
    @override
    def vg_triggers(self, duration=1, after=1):
        self.gamepad.left_trigger_float(1.0)
        self.gamepad.right_trigger_float(1.0)
        self._gamepad_state["triggers"]["left"] = 1.0
        self._gamepad_state["triggers"]["right"] = 1.0
        self.gamepad.update()
        time.sleep(duration)
        self.gamepad.left_trigger_float(0.0)
        self.gamepad.right_trigger_float(0.0)
        self._gamepad_state["triggers"]["left"] = 0.0
        self._gamepad_state["triggers"]["right"] = 0.0
        self.gamepad.update()
        time.sleep(after)

    @dict_config
    @override
    def vg_trigger_down(self, lr):
        if lr == "L":
            self.gamepad.left_trigger_float(1.0)
            self._gamepad_state["triggers"]["left"] = 1.0
        elif lr == "R":
            self.gamepad.right_trigger_float(1.0)
            self._gamepad_state["triggers"]["right"] = 1.0
        else:
            raise ValueError("lr must be 'L' or 'R'")
        self.debug(f"Trigger {lr} down")
        self.gamepad.update()

    @dict_config
    @override
    def vg_trigger_up(self, lr):
        if lr == "L":
            self.gamepad.left_trigger_float(0.0)
            self._gamepad_state["triggers"]["left"] = 0.0
        elif lr == "R":
            self.gamepad.right_trigger_float(0.0)
            self._gamepad_state["triggers"]["right"] = 0.0
        else:
            raise ValueError("lr must be 'L' or 'R'")
        self.gamepad.update()

    @override
    def reset_gamepad(self):
        self.gamepad.reset()
        self.gamepad.update()
        # Reset all state tracking
        for button in self._gamepad_state["buttons"]:
            self._gamepad_state["buttons"][button] = False
        self._gamepad_state["joysticks"]["left"]["x"] = 0.0
        self._gamepad_state["joysticks"]["left"]["y"] = 0.0
        self._gamepad_state["joysticks"]["right"]["x"] = 0.0
        self._gamepad_state["joysticks"]["right"]["y"] = 0.0
        self._gamepad_state["triggers"]["left"] = 0.0
        self._gamepad_state["triggers"]["right"] = 0.0

    @dict_config
    @override
    def left_joystick_move(self, x_value_float=0, y_value_float=0, after=0):
        """
        Move left joystick to specified position and update gamepad state.

        Args:
            x_value_float: X-axis value (-1.0 to 1.0)
            y_value_float: Y-axis value (-1.0 to 1.0)
            after: Wait time after operation
        """
        self.debug(f"Moving left joystick to ({x_value_float}, {y_value_float})")
        self.gamepad.left_joystick_float(
            x_value_float=x_value_float, y_value_float=y_value_float
        )
        self._gamepad_state["joysticks"]["left"]["x"] = x_value_float
        self._gamepad_state["joysticks"]["left"]["y"] = y_value_float
        self.gamepad.update()
        if after > 0:
            self.wait(after, speedup=False)

    @dict_config
    @override
    def right_joystick_move(self, x_value_float=0, y_value_float=0, after=0):
        """
        Move right joystick to specified position and update gamepad state.

        Args:
            x_value_float: X-axis value (-1.0 to 1.0)
            y_value_float: Y-axis value (-1.0 to 1.0)
            after: Wait time after operation
        """
        self.debug(f"Moving right joystick to ({x_value_float}, {y_value_float})")
        self.gamepad.right_joystick_float(
            x_value_float=x_value_float, y_value_float=y_value_float
        )
        self._gamepad_state["joysticks"]["right"]["x"] = x_value_float
        self._gamepad_state["joysticks"]["right"]["y"] = y_value_float
        self.gamepad.update()
        if after > 0:
            self.wait(after, speedup=False)

    @override
    def vg_close(self):
        if hasattr(self, "gamepad") and self.gamepad:
            self.gamepad.close()
            self.gamepad = None

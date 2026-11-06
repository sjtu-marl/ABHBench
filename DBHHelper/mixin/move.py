import math
import time
from typing import List, Union, override

import numpy as np

from core.transform import register_auto_yield
from core.utils import dict_config
from DBHHelper.api import DBHHelperAPI


class MoveMixin(DBHHelperAPI):
    @override
    def move_setup(self):
        # Pre-allocate numpy arrays for vector calculations
        self._forward_direction = np.zeros(2, dtype=np.float32)
        self._right_direction = np.zeros(2, dtype=np.float32)
        self._model_pos_np = np.zeros(2, dtype=np.float32)
        self._target_pos_np = np.zeros(2, dtype=np.float32)
        self._target_vector = np.zeros(2, dtype=np.float32)

    @register_auto_yield
    @dict_config
    @override
    def to_pos_ui(
        self,
        model_pos: List[float],
        interval=0.01,
        after=0.5,
        num_poi: int | list = None,
        indicator: int = None,
        obs=True,
        finish_obs=False,
        CONTEXT=None,
    ):
        self.debug(f"Moving to {model_pos} until indicator")
        if not obs:
            self.debug("No observation")

        # Calculate actual duration based on game speed and interval
        actual_obs_duration = self.obs_move_interval / self.get_game_speed()
        last_obs_time = time.time()

        while True:
            if self._move(model_pos):
                break
            flag_poi = self.read_num_poi()
            flag_indicator = self.read_indicator()
            self.debug(
                f"flag: {flag_poi} num_poi: {num_poi} indicator: {indicator} flag_indicator: {flag_indicator}"
            )
            if (
                (
                    (num_poi is None and flag_poi > 0)
                    or (isinstance(num_poi, int) and flag_poi == num_poi)
                    or (
                        isinstance(num_poi, list)
                        and any(flag_poi == _num_poi for _num_poi in num_poi)
                    )
                )
                and (indicator is None or flag_indicator == indicator)
                and self._dis_target(model_pos) < 1
            ):
                self.debug("Target reached with indicator")
                self.reset_gamepad()
                break
            time.sleep(interval)

            # Use timestamp difference to determine if observation is needed
            current_time = time.time()
            elapsed_time = current_time - last_obs_time
            if self._debug_level >= 2:
                self.debug(
                    f"Elapsed time: {elapsed_time:.3f}, Required: {actual_obs_duration:.3f}"
                )

            if obs and elapsed_time >= actual_obs_duration:
                self.debug("Capture observation")
                if CONTEXT:
                    yield from self.obs(context=CONTEXT)
                else:
                    yield from self.obs()
                last_obs_time = time.time()  # Record time after obs completes
        self.wait(after)
        if (obs and finish_obs) or CONTEXT:
            if CONTEXT:
                yield from self.obs(context=CONTEXT)
            else:
                yield from self.obs()

    @register_auto_yield
    @dict_config
    @override
    def to_pos_only_ui(
        self,
        model_pos: List[float],
        interval=0.01,
        after=0.5,
        num_poi: int | list = None,
        indicator: int = None,
        obs=True,
        finish_obs=False,
        CONTEXT=None,
    ):
        self.debug(f"Moving to {model_pos} until indicator")
        if not obs:
            self.debug("No observation")

        # Calculate actual duration based on game speed and interval
        actual_obs_duration = self.obs_move_interval / self.get_game_speed()
        last_obs_time = time.time()

        while True:
            self._move(model_pos)
            flag_poi = self.read_num_poi()
            flag_indicator = self.read_indicator()
            self.debug(
                f"flag: {flag_poi} num_poi: {num_poi} indicator: {indicator} flag_indicator: {flag_indicator}"
            )
            if (
                (num_poi is None and flag_poi > 0)
                or (isinstance(num_poi, int) and flag_poi == num_poi)
                or (
                    isinstance(num_poi, list)
                    and any(flag_poi == _num_poi for _num_poi in num_poi)
                )
            ) and (indicator is None or flag_indicator == indicator):
                self.debug("Target reached with indicator")
                self.reset_gamepad()
                break
            time.sleep(interval)

            # Use timestamp difference to determine if observation is needed
            current_time = time.time()
            elapsed_time = current_time - last_obs_time
            if self._debug_level >= 2:
                self.debug(
                    f"Elapsed time: {elapsed_time:.3f}, Required: {actual_obs_duration:.3f}"
                )

            if obs and elapsed_time >= actual_obs_duration:
                self.debug("Capture observation")
                if CONTEXT:
                    yield from self.obs(context=CONTEXT)
                else:
                    yield from self.obs()
                last_obs_time = time.time()  # Record time after obs completes
        self.wait(after)
        if (obs and finish_obs) or CONTEXT:
            if CONTEXT:
                yield from self.obs(context=CONTEXT)
            else:
                yield from self.obs()

    @register_auto_yield
    @dict_config
    @override
    def to_pos(
        self,
        model_pos: List[float],
        threshold=0.3,
        interval=0.01,
        after=0.1,
        obs=True,
        finish_obs=True,
        CONTEXT=None,
    ):
        self.debug(f"Moving to {model_pos}")
        if not obs:
            self.debug("No observation")

        # Calculate actual duration based on game speed and interval
        actual_obs_duration = self.obs_move_interval / self.get_game_speed()
        last_obs_time = time.time()

        while True:
            if self._move(model_pos, threshold):
                break
            time.sleep(interval)

            # Use timestamp difference to determine if observation is needed
            current_time = time.time()
            elapsed_time = current_time - last_obs_time
            if self._debug_level >= 2:
                self.debug(
                    f"Elapsed time: {elapsed_time:.3f}, Required: {actual_obs_duration:.3f}"
                )

            if obs and elapsed_time >= actual_obs_duration:
                self.debug("Capture observation")
                if CONTEXT:
                    yield from self.obs(context=CONTEXT)
                else:
                    yield from self.obs()
                last_obs_time = time.time()  # Record time after obs completes
        self.wait(after)
        if (obs and finish_obs) or CONTEXT:
            if CONTEXT:
                yield from self.obs(context=CONTEXT)
            else:
                yield from self.obs()

    def _move(self, target_pos, threshold=0.3):
        # Read the current model position and camera position
        model_pos = self.read_model_pos()
        camera_pos = self.read_camera_pos()

        # Use pre-allocated arrays, update values in-place
        self._forward_direction[0] = -camera_pos[3]
        self._forward_direction[1] = -camera_pos[4]

        # Calculate the right direction vector by rotating
        # the forward direction vector clockwise 90 degrees
        self._right_direction[0] = self._forward_direction[1]
        self._right_direction[1] = -self._forward_direction[0]

        # Update position arrays in-place
        self._model_pos_np[0] = model_pos[0]
        self._model_pos_np[1] = model_pos[1]
        self._target_pos_np[0] = target_pos[0]
        self._target_pos_np[1] = target_pos[1]

        # Compute the vector pointing from the current position to the target position
        # Using in-place subtraction
        np.subtract(self._target_pos_np, self._model_pos_np, out=self._target_vector)

        if self._debug_level >= 2:
            self.debug(
                f"forward: {self._forward_direction}, right: {self._right_direction}"
            )
            self.debug(
                f"cur: {self._model_pos_np}, tar: {self._target_pos_np}, vec: {self._target_vector}"
            )

        # Calculate vector lengths using numpy's efficient norm function
        len_forward = np.linalg.norm(self._forward_direction)
        len_right = np.linalg.norm(self._right_direction)
        len_target = np.linalg.norm(self._target_vector)

        if len_target < threshold:  # Check if the distance is less than the threshold
            self.debug("Target reached")
            self.reset_gamepad()
            return True

        # Calculate normalized dot products using numpy's dot product function
        dot_product_forward = np.dot(self._forward_direction, self._target_vector) / (
            len_forward * len_target
        )
        dot_product_right = np.dot(self._right_direction, self._target_vector) / (
            len_right * len_target
        )

        if self._debug_level >= 2:
            self.debug(
                f"dot_forward: {dot_product_forward}, dot_right: {dot_product_right}, len: {len_target}"
            )
        self.gamepad.left_joystick_float(
            x_value_float=float(dot_product_right),
            y_value_float=float(dot_product_forward),
        )
        self.gamepad.update()
        return False

    def _dis_target(self, target_pos):
        model_pos = self.read_model_pos()

        # Use pre-allocated arrays, update values in-place
        self._model_pos_np[0] = model_pos[0]
        self._model_pos_np[1] = model_pos[1]
        self._target_pos_np[0] = target_pos[0]
        self._target_pos_np[1] = target_pos[1]

        # Calculate difference vector in-place and compute norm
        np.subtract(self._target_pos_np, self._model_pos_np, out=self._target_vector)
        return float(np.linalg.norm(self._target_vector))

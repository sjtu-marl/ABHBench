import math
import os
import sys
import time
from typing import override

from core.transform import register_auto_yield
from core.utils import dict_config
from DBHHelper.api import DBHHelperAPI


class WaitMixin(DBHHelperAPI):
    @override
    def wait(self, seconds: float, speedup=True):
        self.debug(f"Waiting for {seconds} seconds...")
        if seconds > 3 and speedup:
            _sec = seconds / 5
            self.set_game_speed(5)
        else:
            _sec = seconds
        time.sleep(_sec)
        if seconds > 3 and speedup:
            self.set_default_game_speed()
        self.debug("CONTINUE")

    @override
    def wait_for_main_menu(self, index: int, timeout: float = 10.0):
        """Wait for main menu to reach specific index.

        Args:
            index: Expected menu index
            timeout: Maximum time to wait in seconds (default: 10.0)

        Returns:
            bool: True if menu index was reached, False if timeout occurred
        """
        self.debug(f"Waiting for main menu index {index} (timeout: {timeout}s)...")
        start_time = time.time()
        while True:
            flag = self.read_menu_index()
            self.debug(f"Current menu index: {flag}")
            if flag == index:
                self.debug("Main menu index reached")
                return True

            # Check if timeout has elapsed
            if timeout > 0 and (time.time() - start_time) > timeout:
                self.debug(f"Timeout waiting for menu index {index}")
                return False

            time.sleep(0.1)

    @override
    def wait_for_loading(self, timeout=-1, after=2, ignore_error=False):
        """Wait for game to finish loading.

        Args:
            timeout: Maximum time to wait for loading to complete (-1 = wait indefinitely)
            after: Time to wait after loading finishes
            ignore_error: If True, only show warning on timeout; if False, exit with error (default: False)

        Raises:
            SystemExit: If loading takes longer than timeout seconds and ignore_error is False
        """
        self.debug("Waiting for loading screen to appear...")
        # Wait for loading screen to appear (camera pos[0] == 0)
        loading_start_time = time.time()
        loading_detected = False

        while True:
            flag = self.read_camera_pos()[0]
            if flag == 0:
                self.debug("Loading screen detected")
                loading_detected = True
                break

            # Check if we've been trying to detect loading for too long
            if timeout > 0 and time.time() - loading_start_time > timeout:
                if ignore_error:
                    self.warning(
                        f"Failed to detect loading screen after {timeout}s, continuing anyway"
                    )
                    return
                else:
                    self.error(
                        f"Failed to detect loading screen after {timeout} seconds!"
                    )
                    self.error("Game may not have started loading properly.")
                    self.error(
                        "Please restart the game manually and press Enter to exit..."
                    )
                    input()  # Wait for user to press Enter
                    sys.exit(2)  # Exit with error code

            time.sleep(1)

        if not loading_detected:
            return

        # Now wait for loading to finish
        loading_start_time = time.time()
        while True:
            flag = self.read_camera_pos()[0]
            if flag != 0:
                self.debug("Loading finished")
                break

            # Check if loading is taking too long (stuck)
            if timeout > 0 and time.time() - loading_start_time > timeout:
                if ignore_error:
                    self.warning(
                        f"Loading stuck for {timeout} seconds, but continuing due to ignore_error=True"
                    )
                    break
                else:
                    self.error(f"Loading stuck for {timeout} seconds!")
                    self.error("Game appears to be frozen in loading screen.")
                    self.error(
                        "Please restart the game manually and press Enter to exit..."
                    )
                    input()  # Wait for user to press Enter
                    sys.exit(2)  # Exit with error code

            time.sleep(1)

        self.wait(after, speedup=False)


class CSWaitMixin(DBHHelperAPI):
    @register_auto_yield
    @dict_config
    @override
    def wait_for_cutscene(
        self,
        model_pos,
        camera_pos,
        count=3,
        interval=0.01,
        before=0.0,
        after=1.0,
        threshold=(0.01, 0.1),
        sh_speed=None,
        obs=True,
        obs_interval=None,
        finish_obs=True,
        CONTEXT=None,
    ):
        if sh_speed is None:
            sh_speed = float(os.environ.get("sh_speed", 5))
        self.wait(before)
        self.debug("Waiting for cutscene...")
        if not obs:
            self.debug("No observation")
        if obs_interval is None:
            obs_interval = self.obs_interval

        # Calculate actual duration based on sh_speed
        actual_obs_duration = obs_interval / sh_speed
        last_obs_time = time.time()

        self.set_game_speed(sh_speed)
        c = 0
        while True:
            _model_pos = self.read_model_pos()
            model_dis = math.sqrt(
                (_model_pos[0] - model_pos[0]) ** 2
                + (_model_pos[1] - model_pos[1]) ** 2
            )
            if self._debug_level >= 2:
                self.debug(
                    f"model: tar: {model_pos}, cur: {_model_pos[:2]}, dis: {model_dis}"
                )
            if camera_pos is None:
                camera_dis = 0
            else:
                _camera_pos = self.read_camera_pos()
                camera_dis = math.sqrt(
                    (_camera_pos[0] - camera_pos[0]) ** 2
                    + (_camera_pos[1] - camera_pos[1]) ** 2
                )
                if self._debug_level >= 2:
                    self.debug(
                        f"camera: tar: {camera_pos}, cur: {_camera_pos[:2]}, dis: {camera_dis}"
                    )
            if model_dis < threshold[0] and camera_dis < threshold[1]:
                self.set_default_game_speed()
                c += 1
                if c >= count:
                    break
            else:
                if self.get_game_speed() == self._default_game_speed:
                    self.set_game_speed(sh_speed)
                c = 0
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
    def wait_for_cutscene_ui(
        self,
        model_pos,
        camera_pos,
        count=3,
        interval=0.01,
        before=0.0,
        after=1,
        threshold=(0.01, 0.1),
        num_poi: int | None = None,
        indicator: int | None = None,
        sh_speed=None,
        obs=True,
        obs_interval=None,
        finish_obs=True,
        CONTEXT=None,
    ):
        if sh_speed is None:
            sh_speed = float(os.environ.get("sh_speed", 5))
        self.wait(before)
        self.debug("Waiting for cutscene until indicator...")
        if not obs:
            self.debug("No observation")
        if obs_interval is None:
            obs_interval = self.obs_interval

        # Calculate actual duration based on sh_speed
        actual_obs_duration = obs_interval / sh_speed
        last_obs_time = time.time()

        self.set_game_speed(sh_speed)
        c = 0
        while True:
            _model_pos = self.read_model_pos()
            model_dis = math.sqrt(
                (_model_pos[0] - model_pos[0]) ** 2
                + (_model_pos[1] - model_pos[1]) ** 2
            )
            if self._debug_level >= 2:
                self.debug(
                    f"model: tar: {model_pos}, cur: {_model_pos[:2]}, dis: {model_dis}"
                )
            if camera_pos is None:
                camera_dis = 0
            else:
                _camera_pos = self.read_camera_pos()
                camera_dis = math.sqrt(
                    (_camera_pos[0] - camera_pos[0]) ** 2
                    + (_camera_pos[1] - camera_pos[1]) ** 2
                )
                if self._debug_level >= 2:
                    self.debug(
                        f"camera: tar: {camera_pos}, cur: {_camera_pos[:2]}, dis: {camera_dis}"
                    )
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
                self.set_default_game_speed()
                self.debug("Target reached with indicator")
                break
            if model_dis < threshold[0] and camera_dis < threshold[1]:
                self.set_default_game_speed()
                c += 1
                if c >= count:
                    self.debug("Target reached")
                    break
            else:
                if self.get_game_speed() == self._default_game_speed:
                    self.set_game_speed(sh_speed)
                c = 0
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
    def wait_for_ui(
        self,
        num_poi: int,
        indicator: int | None = None,
        sh_speed=None,
        count=3,
        interval=0.01,
        before=0.0,
        after=0.5,
        obs=True,
        obs_interval=None,
        finish_obs=True,
        CONTEXT=None,
    ):
        if sh_speed is None:
            sh_speed = float(os.environ.get("sh_speed", 5))
        self.wait(before)
        self.debug("Waiting for UI...")
        if not obs:
            self.debug("No observation")
        if obs_interval is None:
            obs_interval = self.obs_interval

        self.set_game_speed(sh_speed)

        # Calculate actual duration based on sh_speed
        actual_obs_duration = obs_interval / sh_speed
        last_obs_time = time.time()
        c = 0
        while True:
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
                self.set_default_game_speed()
                c += 1
                if c >= count:
                    self.debug("Target reached with indicator")
                    break
            else:
                if self.get_game_speed() == self._default_game_speed:
                    self.set_game_speed(sh_speed)
                c = 0
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
    def wait_for_no_ui(
        self,
        num_poi: int | list,
        indicator: int | None = None,
        sh_speed=None,
        count=3,
        interval=0.01,
        before=0.0,
        after=1,
        obs=False,
        obs_interval=None,
        finish_obs=True,
        CONTEXT=None,
    ):
        if sh_speed is None:
            sh_speed = float(os.environ.get("sh_speed", 5))
        self.wait(before)
        self.debug("Waiting for no UI...")
        if not obs:
            self.debug("No observation")
        if obs_interval is None:
            obs_interval = self.obs_interval

        self.set_game_speed(sh_speed)

        # Calculate actual duration based on sh_speed
        actual_obs_duration = obs_interval / sh_speed
        last_obs_time = time.time()
        c = 0
        while True:
            flag_poi = self.read_num_poi()
            flag_indicator = self.read_indicator()
            self.debug(
                f"flag: {flag_poi} num_poi: {num_poi} indicator: {indicator} flag_indicator: {flag_indicator}"
            )
            if not (
                (
                    (num_poi is None and flag_poi > 0)
                    or (isinstance(num_poi, int) and flag_poi == num_poi)
                    or (
                        isinstance(num_poi, list)
                        and any(flag_poi == _num_poi for _num_poi in num_poi)
                    )
                )
                and (indicator is None or flag_indicator == indicator)
            ):
                self.set_default_game_speed()
                c += 1
                if c >= count:
                    self.debug("Target reached with no indicator")
                    break
            else:
                if self.get_game_speed() == self._default_game_speed:
                    self.set_game_speed(sh_speed)
                c = 0
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
    def wait_for_n_obs(
        self,
        n: int,
        sh_speed=None,
        interval=0.01,
        before=0.0,
        after=0.1,
        obs_interval=None,
        CONTEXT=None,
    ):
        if sh_speed is None:
            sh_speed = float(os.environ.get("sh_speed", 5))
        self.wait(before)
        self.debug(f"Waiting for {n} observations...")
        if obs_interval is None:
            obs_interval = self.obs_interval

        self.set_game_speed(sh_speed)

        # Calculate actual duration based on sh_speed
        actual_obs_duration = obs_interval / sh_speed
        last_obs_time = time.time()
        c = 0
        while True:
            time.sleep(interval)

            # Use timestamp difference to determine if observation is needed
            current_time = time.time()
            elapsed_time = current_time - last_obs_time
            if self._debug_level >= 2:
                self.debug(
                    f"Elapsed time: {elapsed_time:.3f}, Required: {actual_obs_duration:.3f}"
                )

            if elapsed_time >= actual_obs_duration:
                self.debug("Capture observation")
                if CONTEXT:
                    yield from self.obs(context=CONTEXT)
                else:
                    yield from self.obs()
                last_obs_time = time.time()  # Record time after obs completes
                c += 1
                if c >= n:
                    break
        self.set_default_game_speed()
        self.wait(after)

    @register_auto_yield
    @dict_config
    @override
    def qte(
        self,
        button,
        num_poi: int,
        indicator: int | None = None,
        duration=0.05,
        after=0.05,
        obs=True,
        obs_interval=None,
        finish_obs=True,
        CONTEXT=None,
    ):
        self.debug("QTE...")
        if not obs:
            self.debug("No observation")
        if obs_interval is None:
            obs_interval = self.obs_interval

        # Calculate actual duration based on game speed and interval
        actual_obs_duration = obs_interval / self.get_game_speed()
        last_obs_time = time.time()
        while True:
            flag_poi = self.read_num_poi()
            flag_indicator = self.read_indicator()
            self.debug(
                f"flag: {flag_poi} num_poi: {num_poi} indicator: {indicator} flag_indicator: {flag_indicator}"
            )
            if ((num_poi is None and flag_poi > 0) or flag_poi == num_poi) and (
                indicator is None or flag_indicator == indicator
            ):
                self.debug("Target reached with indicator")
                break
            time.sleep(0.1)

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
        if obs:
            if CONTEXT:
                yield from self.obs(context=CONTEXT)
            else:
                yield from self.obs()

        # Reset timestamp for second phase
        last_obs_time = time.time()
        # Recalculate actual duration for second phase
        actual_obs_duration = obs_interval / self.get_game_speed()
        while True:
            flag_poi = self.read_num_poi()
            flag_indicator = self.read_indicator()
            self.debug(
                f"flag: {flag_poi} num_poi: {num_poi} indicator: {indicator} flag_indicator: {flag_indicator}"
            )
            if not (
                ((num_poi is None and flag_poi > 0) or flag_poi == num_poi)
                and (indicator is None or flag_indicator == indicator)
            ):
                self.debug("Target reached with no indicator")
                break
            self.vg_press_button(button=button, duration=duration, after=after)

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
        if (obs and finish_obs) or CONTEXT:
            if CONTEXT:
                yield from self.obs(context=CONTEXT)
            else:
                yield from self.obs()

    @register_auto_yield
    @dict_config
    @override
    def qtes(
        self,
        buttons: list,
        num_poi: int,
        indicator: int | None = None,
        duration=0.05,
        after=0.05,
        obs=True,
        obs_interval=None,
        finish_obs=True,
        CONTEXT=None,
    ):
        self.debug("QTE...")
        if not obs:
            self.debug("No observation")
        if obs_interval is None:
            obs_interval = self.obs_interval

        # Calculate actual duration based on game speed and interval
        actual_obs_duration = obs_interval / self.get_game_speed()
        last_obs_time = time.time()
        while True:
            flag_poi = self.read_num_poi()
            flag_indicator = self.read_indicator()
            self.debug(
                f"flag: {flag_poi} num_poi: {num_poi} indicator: {indicator} flag_indicator: {flag_indicator}"
            )
            if ((num_poi is None and flag_poi > 0) or flag_poi == num_poi) and (
                indicator is None or flag_indicator == indicator
            ):
                self.debug("Target reached with indicator")
                break
            time.sleep(0.1)

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
        if obs:
            if CONTEXT:
                yield from self.obs(context=CONTEXT)
            else:
                yield from self.obs()

        # Reset timestamp for second phase
        last_obs_time = time.time()
        # Recalculate actual duration for second phase
        actual_obs_duration = obs_interval / self.get_game_speed()
        while True:
            flag_poi = self.read_num_poi()
            flag_indicator = self.read_indicator()
            self.debug(
                f"flag: {flag_poi} num_poi: {num_poi} indicator: {indicator} flag_indicator: {flag_indicator}"
            )
            if not (
                ((num_poi is None and flag_poi > 0) or flag_poi == num_poi)
                and (indicator is None or flag_indicator == indicator)
            ):
                self.debug("Target reached with no indicator")
                break
            self.vg_press_buttons(buttons=buttons, duration=duration, after=after)

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
        if (obs and finish_obs) or CONTEXT:
            if CONTEXT:
                yield from self.obs(context=CONTEXT)
            else:
                yield from self.obs()

    @register_auto_yield
    @dict_config
    @override
    def qte_until_cutscene(
        self,
        button,
        model_pos,
        camera_pos,
        count=3,
        interval=0.01,
        threshold=(0.01, 0.1),
        duration=0.05,
        after=0.05,
        obs=True,
        obs_interval=None,
        finish_obs=True,
        CONTEXT=None,
    ):
        """Press QTE button until reaching target cutscene position.

        Args:
            button: The button to press continuously
            model_pos: Target model position [x, y]
            camera_pos: Target camera position [x, y] or None
            count: Number of consecutive matches needed (default: 3)
            interval: Sleep interval between checks (default: 0.01)
            threshold: Distance thresholds for model and camera (default: (0.01, 0.1))
            duration: Button press duration (default: 0.05)
            after: Wait time after button press (default: 0.05)
            obs: Whether to capture observations (default: True)
            obs_interval: Observation interval (default: from config)
            finish_obs: Whether to capture final observation (default: True)
            CONTEXT: Context for observations (default: None)
        """
        self.debug("QTE until cutscene...")
        if not obs:
            self.debug("No observation")
        if obs_interval is None:
            obs_interval = self.obs_interval

        # Calculate actual duration based on current game speed
        actual_obs_duration = obs_interval / self.get_game_speed()
        last_obs_time = time.time()

        c = 0
        while True:
            _model_pos = self.read_model_pos()
            model_dis = math.sqrt(
                (_model_pos[0] - model_pos[0]) ** 2
                + (_model_pos[1] - model_pos[1]) ** 2
            )
            if self._debug_level >= 2:
                self.debug(
                    f"model: tar: {model_pos}, cur: {_model_pos[:2]}, dis: {model_dis}"
                )
            if camera_pos is None:
                camera_dis = 0
            else:
                _camera_pos = self.read_camera_pos()
                camera_dis = math.sqrt(
                    (_camera_pos[0] - camera_pos[0]) ** 2
                    + (_camera_pos[1] - camera_pos[1]) ** 2
                )
                if self._debug_level >= 2:
                    self.debug(
                        f"camera: tar: {camera_pos}, cur: {_camera_pos[:2]}, dis: {camera_dis}"
                    )

            if model_dis < threshold[0] and camera_dis < threshold[1]:
                c += 1
                if c >= count:
                    self.debug("Target cutscene reached")
                    break
            else:
                c = 0
                # Press the QTE button continuously
                self.vg_press_button(button=button, duration=duration, after=after)

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

        if (obs and finish_obs) or CONTEXT:
            if CONTEXT:
                yield from self.obs(context=CONTEXT)
            else:
                yield from self.obs()

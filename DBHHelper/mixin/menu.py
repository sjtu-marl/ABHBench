from typing import Tuple, override

from core.utils import dict_config
from DBHHelper.api import DBHHelperAPI
from DBHHelper.mixin.mem import MainMenuIndex, MenuIndex


class MenuMixin(DBHHelperAPI):
    @override
    def menu_setup(self):
        self.in_chapter = False

    @dict_config
    @override
    def enter_chapter(
        self, chapter: int, checkpoint: Tuple[float, float, float] | None = None
    ):
        assert self.read_menu_index() == MainMenuIndex.MAIN_MENU, "Not in main menu"
        self.debug(f"Entering chapter {chapter}")
        self.in_chapter = False
        # Reset to left
        self.info("Reset to left")
        for _ in range(5):
            self.debug("Press DPAD LEFT")
            self.vg_press_button(button="DPAD_LEFT")
        # Enter chapter selection
        self.info("Enter chapter selection")
        for _ in range(2):
            self.debug("Press DPAD RIGHT")
            self.vg_press_button(button="DPAD_RIGHT")
        # Confirm
        self.info("Confirm Enter chapter selection")

        # Add retry logic for button press with maximum 3 retries
        max_retries = 3
        retry_count = 0
        success = False

        while retry_count < max_retries and not success:
            if retry_count > 0:
                self.debug(f"Retry {retry_count}/{max_retries} pressing button A")
            self.debug("Press A")
            self.vg_press_button(button="A", after=2)

            # Check if wait_for_main_menu times out
            success = self.wait_for_main_menu(
                MainMenuIndex.CHAPTER_SELECT, timeout=10.0
            )
            if not success:
                self.debug(
                    "Timeout waiting for chapter selection menu, retrying button press"
                )
                retry_count += 1

        if not success:
            self.error("Failed to enter chapter selection after maximum retries")
            raise RuntimeError(
                "Failed to enter chapter selection after maximum retries"
            )

        assert self.find_chapter_num_addr()
        # Select chapter
        self.info(f"Select chapter {chapter}")
        while True:
            chapter_num = self.read_chapter_num() + 1
            self.debug(f"Current chapter: {chapter_num}")
            if chapter_num == chapter:
                break
            if self.read_chapter_num() < chapter:
                self.debug("Press DPAD RIGHT")
                self.vg_press_button(button="DPAD_RIGHT", after=0.2)
            else:
                self.debug("Press DPAD LEFT")
                self.vg_press_button(button="DPAD_LEFT", after=0.2)
        self.info("Confirm Select chapter")
        self.debug("Press A")

        # Add retry logic for chapter selection confirmation
        max_retries = 3
        retry_count = 0
        success = False

        while retry_count < max_retries and not success:
            if retry_count > 0:
                self.debug(
                    f"Retry {retry_count}/{max_retries} confirming chapter selection"
                )
            self.vg_press_button(button="A", after=3)

            success = self.wait_for_main_menu(
                MainMenuIndex.CHECKPOINT_SELECT, timeout=10.0
            )
            if not success:
                self.debug("Timeout waiting for checkpoint selection menu, retrying")
                retry_count += 1

        if not success:
            self.error("Failed to enter checkpoint selection after maximum retries")
            raise RuntimeError(
                "Failed to enter checkpoint selection after maximum retries"
            )
        if checkpoint is not None:
            self.info(f"Select checkpoint {checkpoint}")
            x, y, duration = checkpoint
            self.gamepad.left_joystick_float(x_value_float=x, y_value_float=y)
            self.gamepad.update()
            self.wait(duration, speedup=False)
            self.gamepad.right_joystick_float(x_value_float=0, y_value_float=0)
            self.gamepad.update()
            self.wait(1, speedup=False)
        self.info("Confirm Select checkpoint")
        self.debug("Press A")

        # Add retry logic for checkpoint selection confirmation
        max_retries = 3
        retry_count = 0
        success = False

        while retry_count < max_retries and not success:
            if retry_count > 0:
                self.debug(f"Retry {retry_count}/{max_retries} confirming checkpoint")
            self.vg_press_button(button="A", after=2)

            success = self.wait_for_main_menu(MainMenuIndex.SAVE, timeout=10.0)
            if not success:
                self.debug("Timeout waiting for save menu, retrying")
                retry_count += 1

        if not success:
            self.error("Failed to reach save screen after maximum retries")
            raise RuntimeError("Failed to reach save screen after maximum retries")
        self.debug("Press DPAD RIGHT")
        self.vg_press_button(button="DPAD_RIGHT")
        # Confirm
        self.debug("Press A")
        self.vg_press_button(button="A")
        self.wait_for_loading()
        self.in_chapter = True

    @override
    def exit_to_main_menu(self, timeout=-1, ignore_error=False):
        if not self.in_chapter:
            self.debug("Not in chapter, skipping exit to main menu")
            return
        self.debug("Exiting to main menu")
        self.reset_gamepad()
        self.wait(0.5)
        self.debug("Press START")
        while True:
            self.vg_press_button(button="START")
            self.wait(1)
            ind = self.read_menu_indicator()
            self.debug(f"Menu indicator: {ind}")
            if ind == MenuIndex.PAUSE_MENU:
                break
        # Reset to left
        self.info("Reset to left")
        for _ in range(4):
            self.debug("Press DPAD LEFT")
            self.vg_press_button(button="DPAD_LEFT")
        self.debug("Press DPAD RIGHT")
        self.vg_press_button(button="DPAD_RIGHT")
        # Confirm
        self.debug("Press A")
        self.vg_press_button(button="A")
        # Confirm
        self.debug("Press A")
        self.vg_press_button(button="A")
        self.wait_for_loading(timeout=timeout, ignore_error=ignore_error)
        assert self.read_menu_indicator() == MenuIndex.MAIN_MENU
        self.in_chapter = False

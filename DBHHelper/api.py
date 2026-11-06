import logging
import os
from typing import List, Tuple

import psutil
from PIL import Image
from pymem import Pymem as cPymem
from vgamepad import VX360Gamepad

from core.transform import register_auto_yield


class DBHHelperAPI:
    cfg: dict
    speedhack: bool
    # ppack: PlatformPack

    def setup(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    # proc.py
    # sh: SpeedHackConnector
    _game_speed: float
    _default_game_speed: float
    _cur_game_speed: float
    _is_paused: bool

    def sh_setup(self, speedhack=True):
        raise NotImplementedError

    def set_game_speed(self, value: float):
        raise NotImplementedError

    def set_default_game_speed(self, value: float | None = None):
        raise NotImplementedError

    def get_game_speed(self):
        raise NotImplementedError

    def activate_speedhack(self):
        raise NotImplementedError

    def pause(self):
        raise NotImplementedError

    def resume(self):
        raise NotImplementedError

    processes: List[psutil.Process]
    proc: psutil.Process
    # win: pwc._main.BaseWindow

    def proc_setup(self, window_adjust=True):
        raise NotImplementedError

    def proc_suspend(self):
        raise NotImplementedError

    def proc_resume(self):
        raise NotImplementedError

    def activate_win(self):
        raise NotImplementedError

    def proc_close(self):
        raise NotImplementedError

    def sh_close(self):
        raise NotImplementedError

    # log.py
    _logger: logging.Logger
    _debug_level: int

    def log_setup(self):
        raise NotImplementedError

    def info(self, msg: str):
        raise NotImplementedError

    def debug(self, msg: str):
        raise NotImplementedError

    def warning(self, msg: str):
        raise NotImplementedError

    def error(self, msg: str):
        raise NotImplementedError

    # wait.py
    def wait(self, seconds: float, speedup=True):
        raise NotImplementedError

    def wait_for_main_menu(self, index: int, timeout: float = 10.0):
        raise NotImplementedError

    def wait_for_loading(self, timeout=-1, after=2, ignore_error=False):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def wait_for_cutscene(
        self,
        model_pos,
        camera_pos,
        count=2,
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
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def wait_for_cutscene_ui(
        self,
        model_pos,
        camera_pos,
        count=2,
        interval=0.01,
        before=0.0,
        after=1,
        threshold=(0.01, 0.1),
        num_poi: int | None = None,
        indicator: int | None = None,
        sh_speed=None,
        obs=True,
        obs_interval=None,
        finish_obs=False,
        CONTEXT=None,
    ):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def wait_for_ui(
        self,
        num_poi,
        indicator: int | None = None,
        sh_speed=None,
        count=3,
        interval=0.01,
        before=0.0,
        after=0.5,
        obs=True,
        obs_interval=None,
        finish_obs=False,
        CONTEXT=None,
    ):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
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
        finish_obs=False,
        CONTEXT=None,
    ):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def wait_for_n_obs(
        self,
        n: int,
        sh_speed=None,
        interval=0.01,
        before=0.0,
        after=0.1,
        obs_interval=None,
    ):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def qte(
        self,
        button,
        num_poi,
        indicator: int | None = None,
        duration=0.05,
        after=0.05,
        obs=True,
        obs_interval=None,
        finish_obs=True,
        CONTEXT=None,
    ):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def qtes(
        self,
        buttons: list,
        num_poi,
        indicator: int | None = None,
        duration=0.05,
        after=0.05,
        obs=True,
        obs_interval=None,
        finish_obs=True,
        CONTEXT=None,
    ):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
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
        raise NotImplementedError

    # io.py
    obs_interval: float
    obs_move_interval: float
    obs_index: int
    last_screenshot: Image.Image
    cur_obs: Image.Image

    def io_setup(self, obs_interval=1, obs_move_interval=3):
        raise NotImplementedError

    def set_last_act(self, act):
        raise NotImplementedError

    def wait_for_input(self, delay=3):
        raise NotImplementedError

    def screenshot(self):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def obs(self, context=None, choices=None, choice_stage=None):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def act(
        self,
        key: str,
        context: str,
        choices: dict,
        info: dict,
    ):
        raise NotImplementedError

    def get_choice_from_input(self, choices=None):
        raise NotImplementedError

    # mem.py
    pm: cPymem
    entrypoint: int

    def mem_setup(self, find_model=True, retry=5):
        raise NotImplementedError

    def read_pointer_chain(self, base_address: int, offsets: List[int]):
        raise NotImplementedError

    def find_chapter_num_addr(self) -> bool:
        raise NotImplementedError

    def read_chapter_num(self) -> int:
        raise NotImplementedError

    def read_model_pos(self) -> List[float]:
        raise NotImplementedError

    def find_model_addr(self) -> bool:
        raise NotImplementedError

    def read_camera_pos(self) -> List[float]:
        raise NotImplementedError

    def read_indicator(self) -> int:
        raise NotImplementedError

    def read_num_poi(self) -> int:
        raise NotImplementedError

    def read_num_ip(self) -> int:
        raise NotImplementedError

    def read_menu_indicator(self) -> int:
        raise NotImplementedError

    def read_menu_index(self) -> int:
        raise NotImplementedError

    def dump_memory(self, address: int, range_bytes: int = 64):
        raise NotImplementedError

    # menu.py
    def menu_setup(self):
        raise NotImplementedError

    def enter_chapter(
        self, chapter: int, checkpoint: Tuple[float, float, float] | None = None
    ):
        raise NotImplementedError

    def exit_to_main_menu(self, timeout=-1, ignore_error=False):
        raise NotImplementedError

    # move.py
    def move_setup(self):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def to_pos_ui(
        self,
        model_pos,
        interval=0.1,
        after=0.5,
        num_poi: int | list | None = None,
        indicator: int | None = None,
        obs=True,
        finish_obs=False,
        CONTEXT=None,
    ):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def to_pos_only_ui(
        self,
        model_pos,
        interval=0.1,
        after=0.5,
        num_poi: int | list | None = None,
        indicator: int | None = None,
        obs=True,
        finish_obs=False,
        CONTEXT=None,
    ):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def to_pos(
        self,
        model_pos,
        threshold=0.3,
        interval=0.01,
        after=0.1,
        obs=True,
        finish_obs=True,
        CONTEXT=None,
    ):
        raise NotImplementedError

    # record.py
    def recorder_setup(self, record=False, change_rec_dir=True):
        raise NotImplementedError

    def start_record(self):
        raise NotImplementedError

    def pause_record(self):
        raise NotImplementedError

    def resume_record(self):
        raise NotImplementedError

    def stop_record(self):
        raise NotImplementedError

    def get_version(self):
        raise NotImplementedError

    # vg.py
    gamepad: VX360Gamepad

    def vg_setup(self):
        raise NotImplementedError

    def get_gamepad_state(self):
        raise NotImplementedError

    def print_gamepad_state(self):
        raise NotImplementedError

    def activate_vg(self):
        raise NotImplementedError

    def interact(self, it: str | list, pause=1, after=None, retry=3):
        raise NotImplementedError

    def rj_interact(self, xy, duration=0.2, after=0.2):
        raise NotImplementedError

    def exp_rj_interact(
        self, seq, duration=0.02, pause=0.0, after=1, smooth=10, keep=False
    ):
        raise NotImplementedError

    def vg_press_button(self, button, duration=0.1, after: float = 1, keep=False):
        raise NotImplementedError

    def vg_press_buttons(
        self, buttons: list, duration=0.1, after: float = 1, keep=False
    ):
        raise NotImplementedError

    def vg_trigger(self, lr, duration=1, after=1):
        raise NotImplementedError

    def vg_triggers(self, duration=1, after=1):
        raise NotImplementedError

    def vg_trigger_down(self, lr):
        raise NotImplementedError

    def vg_trigger_up(self, lr):
        raise NotImplementedError

    def reset_gamepad(self):
        raise NotImplementedError

    def vg_close(self):
        raise NotImplementedError

    def vg_release_button(self, button):
        raise NotImplementedError

    def vg_release_buttons(self, buttons: list):
        raise NotImplementedError

    def left_joystick_move(self, x_value_float=0, y_value_float=0, after=0):
        raise NotImplementedError

    def right_joystick_move(self, x_value_float=0, y_value_float=0, after=0):
        raise NotImplementedError

    # view.py
    @register_auto_yield(allow_override=True)
    def to_ip(self, ip, init_loc, init_view, btn="Y", repeat=5):
        raise NotImplementedError

    def to_view(self, target_view):
        raise NotImplementedError

    @register_auto_yield(allow_override=True)
    def timeline_slide(self, dirs, view=None):
        raise NotImplementedError

import logging

from core.event import Event
from core.transform import register_auto_yield
from DBHHelper.api import DBHHelperAPI


class DummyEvent(Event):
    name: str = "dummy_event"


class DBHHelperDummyAPI(DBHHelperAPI):
    cfg: dict
    speedhack: bool

    def setup(self, *args, **kwargs):
        pass

    def close(self, *args, **kwargs):
        pass

    # proc.py
    def set_game_speed(self, *args, **kwargs):
        pass

    def set_default_game_speed(self, *args, **kwargs):
        pass

    def get_game_speed(self, *args, **kwargs):
        pass

    def activate_speedhack(self, *args, **kwargs):
        pass

    def pause(self, *args, **kwargs):
        pass

    def resume(self, *args, **kwargs):
        pass

    def proc_suspend(self, *args, **kwargs):
        pass

    def proc_resume(self, *args, **kwargs):
        pass

    def activate_win(self, *args, **kwargs):
        pass

    def proc_close(self, *args, **kwargs):
        pass

    def sh_close(self, *args, **kwargs):
        pass

    # log.py
    _logger: logging.Logger

    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    # wait.py
    def wait(self, *args, **kwargs):
        pass

    def wait_for_main_menu(self, *args, **kwargs):
        pass

    def wait_for_loading(self, *args, **kwargs):
        pass

    @register_auto_yield(allow_override=True)
    def wait_for_cutscene(self, *args, **kwargs):
        yield DummyEvent()

    @register_auto_yield(allow_override=True)
    def wait_for_cutscene_ui(self, *args, **kwargs):
        yield DummyEvent()

    @register_auto_yield(allow_override=True)
    def wait_for_ui(self, *args, **kwargs):
        yield DummyEvent()

    @register_auto_yield(allow_override=True)
    def wait_for_no_ui(self, *args, **kwargs):
        yield DummyEvent()

    @register_auto_yield(allow_override=True)
    def wait_for_n_obs(self, *args, **kwargs):
        yield DummyEvent()

    @register_auto_yield(allow_override=True)
    def qte(self, *args, **kwargs):
        yield DummyEvent()

    @register_auto_yield(allow_override=True)
    def qtes(self, *args, **kwargs):
        yield DummyEvent()

    @register_auto_yield(allow_override=True)
    def qte_until_cutscene(self, *args, **kwargs):
        yield DummyEvent()

    # io.py
    def set_last_act(self, *args, **kwargs):
        pass

    def wait_for_input(self, *args, **kwargs):
        pass

    def screenshot(self, *args, **kwargs):
        pass

    @register_auto_yield(allow_override=True)
    def obs(self, *args, **kwargs):
        yield DummyEvent()

    @register_auto_yield(allow_override=True)
    def act(self, *args, **kwargs):
        yield DummyEvent()

    def get_choice_from_input(self, *args, **kwargs):
        pass

    # mem.py
    def read_pointer_chain(self, *args, **kwargs):
        pass

    def find_chapter_num_addr(self, *args, **kwargs):
        pass

    def read_chapter_num(self, *args, **kwargs):
        pass

    def read_model_pos(self, *args, **kwargs):
        pass

    def find_model_addr(self, *args, **kwargs):
        pass

    def read_camera_pos(self, *args, **kwargs):
        pass

    def read_indicator(self, *args, **kwargs):
        pass

    def read_num_poi(self, *args, **kwargs):
        pass

    def read_num_ip(self, *args, **kwargs):
        pass

    def read_menu_indicator(self, *args, **kwargs):
        pass

    def read_menu_index(self, *args, **kwargs):
        pass

    def dump_memory(self, *args, **kwargs):
        pass

    # menu.py
    def menu_setup(self, *args, **kwargs):
        pass

    def enter_chapter(self, *args, **kwargs):
        pass

    def exit_to_main_menu(self, *args, **kwargs):
        pass

    # move.py
    def move_setup(self, *args, **kwargs):
        pass

    @register_auto_yield(allow_override=True)
    def to_pos_ui(self, *args, **kwargs):
        yield DummyEvent()

    @register_auto_yield(allow_override=True)
    def to_pos_only_ui(self, *args, **kwargs):
        yield DummyEvent()

    @register_auto_yield(allow_override=True)
    def to_pos(self, *args, **kwargs):
        yield DummyEvent()

    # record.py
    def recorder_setup(self, *args, **kwargs):
        pass

    def start_record(self, *args, **kwargs):
        pass

    def pause_record(self, *args, **kwargs):
        pass

    def resume_record(self, *args, **kwargs):
        pass

    def stop_record(self, *args, **kwargs):
        pass

    def get_version(self, *args, **kwargs):
        pass

    def vg_setup(self, *args, **kwargs):
        pass

    def get_gamepad_state(self, *args, **kwargs):
        pass

    def print_gamepad_state(self, *args, **kwargs):
        pass

    def activate_vg(self, *args, **kwargs):
        pass

    def interact(self, *args, **kwargs):
        pass

    def rj_interact(self, *args, **kwargs):
        pass

    def exp_rj_interact(self, *args, **kwargs):
        pass

    def vg_press_button(self, *args, **kwargs):
        pass

    def vg_press_buttons(self, *args, **kwargs):
        pass

    def vg_trigger(self, *args, **kwargs):
        pass

    def vg_triggers(self, *args, **kwargs):
        pass

    def vg_trigger_down(self, *args, **kwargs):
        pass

    def vg_trigger_up(self, *args, **kwargs):
        pass

    def reset_gamepad(self, *args, **kwargs):
        pass

    def vg_close(self, *args, **kwargs):
        pass

    def vg_release_button(self, *args, **kwargs):
        pass

    def vg_release_buttons(self, *args, **kwargs):
        pass

    def left_joystick_move(self, *args, **kwargs):
        pass

    def right_joystick_move(self, *args, **kwargs):
        pass

    # view.py
    @register_auto_yield(allow_override=True)
    def to_ip(self, *args, **kwargs):
        yield DummyEvent()

    def to_view(self, *args, **kwargs):
        pass

    @register_auto_yield(allow_override=True)
    def timeline_slide(self, *args, **kwargs):
        yield DummyEvent()

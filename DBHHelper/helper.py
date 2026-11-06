import os
from typing import override

from core.event import EventDispatcher, EventSystemCloseEvent
from core.log import get_logger
from core.utils import DictConfig
from DBHHelper.api import DBHHelperAPI
from DBHHelper.mixin.io import IOMixin
from DBHHelper.mixin.log import LogMixin
from DBHHelper.mixin.mem import MemMixin
from DBHHelper.mixin.menu import MenuMixin
from DBHHelper.mixin.move import MoveMixin
from DBHHelper.mixin.proc import ProcMixin, SHMixin
from DBHHelper.mixin.record import OBSRecorderMixin
from DBHHelper.mixin.vg import VGMixin
from DBHHelper.mixin.view import ViewMixin
from DBHHelper.mixin.wait import CSWaitMixin, WaitMixin
from DBHHelper.platform import create_ppack


class DBHHelper(
    MoveMixin,
    ViewMixin,
    MenuMixin,
    IOMixin,
    WaitMixin,
    CSWaitMixin,
    OBSRecorderMixin,
    VGMixin,
    LogMixin,
    ProcMixin,
    SHMixin,
    MemMixin,
    DictConfig,
    DBHHelperAPI,
    EventDispatcher,
):
    def __init__(self, cfg=None):
        self._logger = get_logger()
        self.set_cfg(cfg)

    @override
    def setup(
        self,
        enable_speedhack=True,
        obs_interval=1,
        obs_move_interval=3,
        record=False,
        change_rec_dir=True,
        find_model=True,
        vgamepad=True,
        window_adjust=True,
    ):
        self.enable_speedhack = enable_speedhack
        self.log_setup()
        self.menu_setup()
        self.ppack = create_ppack()
        self.proc_setup(window_adjust=window_adjust)
        self.sh_setup(enable_speedhack)
        self.move_setup()
        self.io_setup(obs_interval, obs_move_interval)
        if vgamepad:
            self.vg_setup()
        self.mem_setup(find_model)
        self.recorder_setup(
            record or os.getenv("flags.record", "false").lower() == "true",
            change_rec_dir,
        )

    @EventDispatcher.on(EventSystemCloseEvent)
    @override
    def close(self):
        self._logger.debug("Starting DBHHelper close sequence")
        self._logger.debug("Closing virtual gamepad")
        self.vg_close()
        self._logger.debug("Closing process handler")
        self.proc_close()
        self._logger.debug("Closing speedhack")
        self.sh_close()
        self._logger.debug("Closing platform pack")
        self.ppack.close()
        self._logger.debug("Stopping recorder")
        self.stop_record()
        self._logger.debug("DBHHelper close sequence completed")

import os
from typing import override

from core.utils import get_frame, init_logger
from DBHHelper.api import DBHHelperAPI


class LogMixin(DBHHelperAPI):
    @override
    def log_setup(self):
        self._debug_level = int(os.getenv("flags.debug", "1"))

    @override
    def info(self, msg: str):
        self._logger.info(msg, frame=get_frame(2))

    @override
    def debug(self, msg: str):
        self._logger.debug(msg, frame=get_frame(2))

    @override
    def warning(self, msg: str):
        self._logger.warning(msg, frame=get_frame(2))

    @override
    def error(self, msg: str):
        self._logger.error(msg, frame=get_frame(2))

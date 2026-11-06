import pywinctl as pwc
import rpyc
import Xlib
from pywinctl._pywinctl_linux import LinuxWindow
from vgamepad import VX360Gamepad

from ..common.pack import PlatformPack


class LinuxPack(PlatformPack):
    def __init__(self):
        super().__init__()
        self._conn = rpyc.classic.connect("localhost")
        self._conn._config["sync_request_timeout"] = None
        self._conn.execute("import win32api")
        self.win32api = self._conn.modules.win32api
        self._conn.execute("import win32file")
        self.win32file = self._conn.modules.win32file
        self._conn.execute("import win32event")
        self.win32event = self._conn.modules.win32event
        self._conn.execute("import win32process")
        self.win32process = self._conn.modules.win32process
        self.win32lib = {
            "win32api": self.win32api,
            "win32file": self.win32file,
            "win32event": self.win32event,
            "win32process": self.win32process,
        }
        self._conn.execute("import psutil")
        self.pstuil = self._conn.modules.psutil
        self._conn.execute("from pymem import Pymem")
        self.Pymem = self._conn.namespace["Pymem"]
        self._conn.execute("import pymem")
        self.pymem = self._conn.namespace["pymem"]
        self.VX360Gamepad = VX360Gamepad

    def close(self):
        super().close()
        self._conn.close()


def get_window_by_title(title: str):
    wins = pwc.getAllWindows()
    for w in wins:
        if w.title == title:
            return w
    all_titles = pwc.getAllTitles()
    raise ValueError(
        f"Window with title '{title}' not found. Available titles: {all_titles}"
    )


def resize_window(win: LinuxWindow, width: int, height: int):
    win.resizeTo(width, height, True)


def create_ppack():
    return LinuxPack()


__all__ = ["create_ppack", "get_window_by_title", "resize_window"]

import psutil
import pymem
import pywinctl as pwc
import win32api
import win32event
import win32file
import win32process
from pymem import Pymem
from pywinctl._pywinctl_win import Win32Window

from ..common.pack import PlatformPack


class WinPack(PlatformPack):
    def __init__(self):
        super().__init__()
        self.win32api = win32api
        self.win32file = win32file
        self.win32event = win32event
        self.win32process = win32process
        self.win32lib = {
            "win32api": self.win32api,
            "win32file": self.win32file,
            "win32event": self.win32event,
            "win32process": self.win32process,
        }
        self.pstuil = psutil
        self.Pymem = Pymem
        self.pymem = pymem


def get_window_by_title(title: str):
    wins = pwc.getAllWindows()
    for w in wins:
        if w.title == title:
            return w


def resize_window(win: Win32Window, width: int, height: int):
    l, t, r, b = win.getClientFrame()
    x, y, w, h = l, t, r - l, b - t
    delta_w = win.width - w
    delta_h = win.height - h
    win.resizeTo(width + delta_w, height + delta_h, True)


def create_ppack():
    return WinPack()


__all__ = ["create_ppack", "get_window_by_title", "resize_window"]

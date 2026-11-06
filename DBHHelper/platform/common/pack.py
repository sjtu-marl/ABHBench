from typing import Type

from pymem import Pymem as cPymem
from vgamepad import XUSB_BUTTON, VX360Gamepad

from .proch import find_process_by_cmdline, read_pointer_chain
from .speedhack import SpeedHackConnector


class PlatformPack:
    Pymem: Type[cPymem]
    pm: cPymem
    _speedhack: SpeedHackConnector

    def __init__(self) -> None:
        self.XUSB_BUTTON = XUSB_BUTTON
        self.VX360Gamepad = VX360Gamepad

    def find_process_by_cmdline(self, substrings):
        return find_process_by_cmdline(substrings, self.pstuil)

    def load_pymem(self, pid):
        self.pm = self.Pymem(pid)
        return self.pm

    def read_pointer_chain(self, base_address, offsets):
        """Read a value from a pointer chain."""
        return read_pointer_chain(self.pm, base_address, offsets)

    def activate_speedhack(self, pid) -> SpeedHackConnector:
        self._speedhack = SpeedHackConnector(pid, self.win32lib)
        return self._speedhack

    def close(self):
        if hasattr(self, "_speedhack") and self._speedhack:
            self._speedhack.close()
            self._speedhack = None

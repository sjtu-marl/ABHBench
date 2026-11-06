from typing import override

from DBHHelper.api import DBHHelperAPI
from DBHHelper.platform import get_window_by_title, resize_window


class SHMixin(DBHHelperAPI):
    @override
    def sh_setup(self, speedhack=True):
        self._game_speed = self._default_game_speed = self._cur_game_speed = 1
        if speedhack:
            self.activate_speedhack()
            self.set_default_game_speed()
        else:
            self.sh = None
        self._is_paused = False

    @override
    def set_game_speed(self, value: float):
        if self.sh is None:
            return
        if self._game_speed == value:
            return
        self.debug(f"Set game speed to {value}")
        self._game_speed = value
        self.sh.set_game_speed(value)

    @override
    def set_default_game_speed(self, value: float = None):
        if value:
            self._default_game_speed = value
        self.set_game_speed(self._default_game_speed)

    @override
    def get_game_speed(self):
        return self._game_speed

    @override
    def activate_speedhack(self):
        self.sh = self.ppack.activate_speedhack(self.proc.pid)

    @override
    def pause(self):
        if self._is_paused:
            return
        self._cur_game_speed = self.get_game_speed()
        self.set_game_speed(0)
        self.pause_record()
        self._is_paused = True

    @override
    def resume(self):
        if not self._is_paused:
            return
        self.set_game_speed(self._cur_game_speed)
        self.resume_record()
        self._is_paused = False
        self.wait(0.01)

    def sh_close(self):
        if self.sh:
            self.set_default_game_speed(1.0)
            self.sh.close()
            self.sh = None


class ProcMixin(DBHHelperAPI):
    @override
    def proc_setup(self, window_adjust=True):
        self.processes = self.ppack.find_process_by_cmdline(["DetroitBecomeHuman.exe"])
        self.debug(f"Found {len(self.processes)} processes")
        self.proc = self.processes[0]
        self.debug(f"Pid: {self.proc.pid}, Cmdline: {self.proc.info['cmdline'][0]}")
        self.win = get_window_by_title("Detroit: Become Human")
        if not window_adjust:
            self.debug("Window adjust disabled")
            return
        resize_window(self.win, 1072, 603)
        self.win.moveTo(100, 100, True)
        self.wait(2, False)
        self.debug(f"Window resize to {self.win.width}x{self.win.height}")
        l, t, r, b = self.win.getClientFrame()
        self.debug(f"Image: {self.win.getClientFrame()}  {b - t},{r - l}")
        self.win.alwaysOnTop(True)
        self.win.alwaysOnTop(True)
        self.win.activate()

    @override
    def proc_suspend(self):
        self.proc.suspend()
        self.debug("Process suspended")

    @override
    def proc_resume(self):
        self.proc.resume()
        self.wait(0.3)
        self.activate_win()
        self.debug("Process resumed")

    @override
    def activate_win(self):
        self.win.activate()
        self.debug("Window activated")

    @override
    def proc_close(self):
        try:
            self.win.alwaysOnTop(False)
        except Exception:
            pass

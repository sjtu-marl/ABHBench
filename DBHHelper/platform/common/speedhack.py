"""This code is adapted from [SoulsGym](https://github.com/amacati/SoulsGym). Thanks for this implementation."""

import struct
import time
from pathlib import Path
from threading import Lock
from typing import Any
from weakref import WeakValueDictionary

PROCESS_ALL_ACCESS = 0x000F0000 | 0x00100000 | 0x00000FFF
MEM_CREATE = 0x00001000 | 0x00002000
MEM_RELEASE = 0x00008000
MAX_PATH = 260
PAGE_READWRITE = 0x04


class Singleton(type):
    """Metaclass for singletons."""

    # Enables automatic __del__ call after all instances have gone out of scope
    # See https://stackoverflow.com/questions/43619748/destroying-a-singleton-object-in-python
    _instances = WeakValueDictionary()
    _lock = Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Create the class if no object is already instantiated, otherwise return the instance."""
        with cls._lock:
            if cls not in cls._instances:
                # This variable declaration is required to force a strong reference on the instance
                instance = super(Singleton, cls).__call__(*args, **kwargs)
                cls._instances[cls] = instance
            else:
                # Check if existing instance is closed, if so create a new one
                existing_instance = cls._instances[cls]
                if (
                    hasattr(existing_instance, "_is_closed")
                    and existing_instance._is_closed
                ):
                    instance = super(Singleton, cls).__call__(*args, **kwargs)
                    cls._instances[cls] = instance
            return cls._instances[cls]


class SpeedHackConnector(metaclass=Singleton):
    """Inject the speed hack and connect to the speed command pipe."""

    dll_path = Path(__file__).parent / "SpeedHackDLL.dll"
    _lock = Lock()

    def __init__(self, pid: int, win32lib: dict):
        """Connect to the SpeedHack pipe.

        If the pipe is not yet open, inject the DLL into the game.

        Args:
            process_name: Name of the process to connect to.
        """
        assert self.dll_path.exists()
        self.pipe = None
        self.pid = pid
        self.win32api = win32lib["win32api"]
        self.win32file = win32lib["win32file"]
        self.win32event = win32lib["win32event"]
        self.win32process = win32lib["win32process"]
        self.pipe_name = r"\\.\pipe\GeneralGameSpeedHackPipe" + f"_{pid}"
        self.actived = False
        self._is_closed = False  # Track if instance has been closed
        try:
            self.pipe = self._connect_pipe()
            self.actived = True
        except Exception as e:
            if not e.args[0] == 2 and e.args[1] == "CreateFile":
                raise e  # Not the anticipated error on missing pipe, so we re-raise
            self._inject_dll(self.pid, self.dll_path)
            # Give the pipe time to come up after the injection (very conservative)
            time.sleep(0.1)
            self.pipe = self._connect_pipe()
            self.actived = True

    def set_game_speed(self, value: float):
        """Set the game speed to a new value.

        Args:
            value: The new game speed. Can't be lower than 0.
        """
        if not self.actived:
            return
        assert value >= 0
        self.win32file.WriteFile(self.pipe, struct.pack("f", value))

    def _connect_pipe(self) -> int:
        return self.win32file.CreateFile(
            self.pipe_name,
            self.win32file.GENERIC_WRITE,
            0,
            None,
            self.win32file.OPEN_EXISTING,
            0,
            None,
        )

    def _inject_dll(self, pid: int, dll_path: Path):
        """Inject a DLL into the target process.

        Injection opens a process handle of the target process, allocates virtual memory in its address
        space, writes the DLL path to this address and forces the process to open the DLL by creating a remote thread.

        Args:
            process_name: Target process name.
            dll_path: Path to the DLL file.
        """
        p_handle = self.win32api.OpenProcess(PROCESS_ALL_ACCESS, 0, pid)
        mem_addr = self._write_dll_to_process(p_handle, dll_path)
        if mem_addr is None:
            return
        t_handle = self._create_remote_thread(p_handle, mem_addr)
        self.win32event.WaitForSingleObject(t_handle, 5_000)
        self._injection_cleanup(p_handle, t_handle, mem_addr)

    def _write_dll_to_process(self, p_handle: int, dll_path: Path) -> int:
        """Write the DLL path to the external process memory.

        Args:
            p_handle: Target process handle.
            dll_path: Path to the injection DLL.

        Returns:
            The memory address of the allocated memory.

        Raises:
            InjectionFailure: The requested memory could not be allocated or written to.
        """
        mem_addr = self.win32process.VirtualAllocEx(
            p_handle, 0, MAX_PATH, MEM_CREATE, PAGE_READWRITE
        )
        if not mem_addr:
            self.win32api.CloseHandle(p_handle)
            return
        if not self.win32process.WriteProcessMemory(
            p_handle, mem_addr, str(dll_path).encode("ascii")
        ):
            self.win32api.CloseHandle(p_handle)
            return
        return mem_addr

    def _create_remote_thread(self, p_handle: int, mem_addr: int) -> int:
        """Create a remote thread and load the injected DLL.

        Args:
            p_handle: Target process handle.
            mem_addr: Address of the DLL path memory.

        Returns:
            The handle of the created thread.
        """
        module_addr = self.win32api.GetModuleHandle("kernel32.dll")
        load_library_fn = self.win32api.GetProcAddress(module_addr, "LoadLibraryA")
        t_handle, _ = self.win32process.CreateRemoteThread(
            p_handle, None, 0, load_library_fn, mem_addr, 0
        )
        return t_handle

    def _injection_cleanup(self, p_handle: int, t_handle: int, mem_addr: int):
        """Clean up the injection by freeing the allocated memory and closing the handles.

        Args:
            p_handle: Target process handle.
            t_handle: Injection thread handle.
            mem_addr: Address of the DLL path memory.
        """
        self.win32process.VirtualFreeEx(p_handle, mem_addr, 0, MEM_RELEASE)
        self.win32api.CloseHandle(p_handle)
        self.win32api.CloseHandle(t_handle)

    def close(self):
        if self.pipe is not None:
            try:
                self.win32file.CloseHandle(self.pipe)
            except (
                TypeError
            ):  # Throws NoneType object not callable error for some reason
                ...
            except EOFError:
                ...
            self.pipe = None
        self.actived = False
        self._is_closed = True  # Mark instance as closed

    def __del__(self):
        """Close the pipe handle on deletion."""
        self.close()

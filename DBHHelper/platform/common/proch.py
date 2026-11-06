from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymem import Pymem


def find_process_by_cmdline(substrings, psutil):
    """Return a list of processes where 'substring' is in the command line."""
    matched_processes = []
    for process in psutil.process_iter(["cmdline"]):
        try:
            if not process.info["cmdline"]:
                continue
            if len(process.info["cmdline"]) > 1:
                continue
            cmdline = process.info["cmdline"][0] if process.info["cmdline"][0] else ""
            if all(substring in cmdline for substring in substrings):
                matched_processes.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # The process may have ended or access is denied.
            continue
    return matched_processes


def read_pointer_chain(pm: Pymem, base_address, offsets):
    """Read a value from a pointer chain."""
    address = base_address
    for offset in offsets:
        address = pm.read_uint(address) + offset
    return pm.read_uint(address)

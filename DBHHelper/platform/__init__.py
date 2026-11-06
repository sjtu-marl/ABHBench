import platform

if platform.system() == "Windows":
    from .win import create_ppack, get_window_by_title, resize_window
elif platform.system() == "Linux":  # Linux
    from .linux import create_ppack, get_window_by_title, resize_window
else:
    raise NotImplementedError(f"Unsupported platform: {platform.system()}")

import copy
import functools
import inspect
import logging
import os
import random
import string
import threading
from enum import Enum, auto
from typing import Callable, Optional


class InfixOpType(Enum):
    LEFT = auto()
    RIGHT = auto()
    D_HEAD = auto()
    D_TAIL = auto()


class Infix:
    def __init__(
        self,
        function: Callable[[InfixOpType, any, any], any],
        op: str = None,
        value: any = None,
    ):
        self.function = function
        self.op = op
        self.value = value

    def __process_ops(self, op: str, other: any):
        if self.op:
            _ops = [self.op, op]
            _values = [self.value, other]
            if _ops == ["ror", "or"]:
                itype = InfixOpType.D_TAIL
            elif _ops == ["rlshift", "rshift"]:
                itype = InfixOpType.D_HEAD
            elif _ops == ["rlshift", "or"]:
                itype = InfixOpType.LEFT
            elif _ops == ["rshift", "ror"]:
                itype = InfixOpType.RIGHT
                _values = _values[::-1]
            else:
                raise RuntimeError("Invalid operation")
            res = self.function(itype, *_values)
            self.op = None
            self.value = None
            return res
        return Infix(self.function, op, other)

    def __ror__(self, other: any):
        return self.__process_ops("ror", other)

    def __or__(self, other: any):
        return self.__process_ops("or", other)

    def __rlshift__(self, other: any):
        return self.__process_ops("rlshift", other)

    def __rshift__(self, other: any):
        return self.__process_ops("rshift", other)


def dict_config(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # If the function is called with keyword arguments, ensure that only keyword arguments are provided
        if kwargs:
            if args:
                raise TypeError(
                    "This function only accepts parameters in dictionary form or a single string argument"
                )
            return func(self, **kwargs)
        # If the function is called with positional arguments, allow only a single string argument.
        # Use the string as a key to fetch the configuration from self.cfg.
        elif len(args) == 1 and isinstance(args[0], str):
            key = args[0]
            if not hasattr(self, "cfg"):
                raise AttributeError("The object does not have a 'cfg' attribute")
            if key not in self.cfg:
                raise KeyError(f"The key '{key}' does not exist in the configuration")
            config = self.cfg[key]
            if not isinstance(config, dict):
                raise ValueError("The configuration value must be a dictionary")
            return func(self, **config)
        # All other cases are considered illegal calls
        else:
            raise TypeError(
                "This function only accepts parameters in dictionary form or a single string argument"
            )

    return wrapper


class DictConfig:
    def set_cfg(self, cfg):
        self.cfg = cfg


def get_path(name="logs", abspath=None, relative_path=None, _file=None, parent=False):
    """Create path if path don't exist
    Args:
        name: folder name
        abspath: absolute path to be prefix
        relative_path: relative path that can be convert into absolute path
        _file: use directory based on _file
        parent: whether the path is in the parent folder
    Returns: Path of the folder
    """
    import os

    if abspath:
        directory = os.path.abspath(os.path.join(abspath, name))
    elif relative_path:
        directory = os.path.abspath(os.path.join(os.path.abspath(relative_path), name))
    else:
        import sys

        if getattr(sys, "frozen", False):
            application_path = os.path.dirname(sys.executable)
            directory = os.path.abspath(os.path.join(application_path, name))
        elif _file:
            if parent:
                directory = os.path.abspath(
                    os.path.join(os.path.dirname(_file), *([os.pardir] * parent), name)
                )
            else:
                directory = os.path.abspath(os.path.join(os.path.dirname(_file), name))
        else:
            if parent:
                directory = os.path.abspath(
                    os.path.join(
                        os.path.dirname(__file__), *([os.pardir] * parent), name
                    )
                )
            else:
                directory = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), name)
                )
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory


def _find_caller(f):
    from logging import _srcfile, os

    rv = "(unknown file)", 0, "(unknown function)", None
    while hasattr(f, "f_code"):
        co = f.f_code
        filename = os.path.normcase(co.co_filename)
        if filename == _srcfile:
            f = f.f_back
            continue
        sinfo = None
        rv = (co.co_filename, f.f_lineno, co.co_name, sinfo)
        break
    return rv


def sprint(*args, **kwargs):
    """Print with stack"""
    import datetime
    import sys

    frame = sys._getframe(kwargs.pop("limit", 1))
    rv = _find_caller(frame)
    rv0 = str(rv[0])
    if len(rv0) > 10:
        rv0 = "..." + rv0[-10:]
    rv2 = str(rv[2])
    if len(rv2) > 10:
        rv2 = "..." + rv2[-10:]
    print(f"[{datetime.datetime.now()}][{rv0}:{rv2}:{rv[1]}] ", *args, **kwargs)


BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"
COLORS = {
    "WARNING": YELLOW,
    "INFO": WHITE,
    "DEBUG": BLUE,
    "CRITICAL": YELLOW,
    "ERROR": RED,
    "RED": RED,
    "GREEN": GREEN,
    "YELLOW": YELLOW,
    "BLUE": BLUE,
    "MAGENTA": MAGENTA,
    "CYAN": CYAN,
    "WHITE": WHITE,
}


class ColoredFormatter(logging.Formatter):
    def __init__(self, msg):
        logging.Formatter.__init__(self, msg)

    def format(self, record):
        record = copy.deepcopy(record)
        levelname = record.levelname
        if levelname in COLORS:
            levelname_color = (
                COLOR_SEQ % (30 + COLORS[levelname]) + levelname + RESET_SEQ
            )
            record.levelname = levelname_color
        message = logging.Formatter.format(self, record)
        message = message.replace("$RESET", RESET_SEQ).replace("$BOLD", BOLD_SEQ)
        for k, v in COLORS.items():
            message = (
                message.replace("$" + k, COLOR_SEQ % (v + 30))
                .replace("$BG" + k, COLOR_SEQ % (v + 40))
                .replace("$BG-" + k, COLOR_SEQ % (v + 40))
            )
        return message + RESET_SEQ


def get_frame(depth=1):
    import sys

    return sys._getframe(depth)


# Global variable to store the names of registered modules.
registered_debug_modules = set()


def register_debug_module():
    """
    Registers the current module by its full file path.
    Retrieves the caller's __file__ attribute, converts it to an absolute path,
    and adds it to the registered_debug_modules set.
    """
    # Get the frame of the caller.
    frame = inspect.currentframe().f_back
    file_path = frame.f_globals.get("__file__")
    if file_path:
        full_path = os.path.abspath(file_path)
        registered_debug_modules.add(full_path)
        return full_path
    else:
        raise ValueError("Current module has no __file__ attribute.")


def get_registered_debug_modules():
    return registered_debug_modules


def parallel_execute(
    func,
    n_times,
    max_workers=None,
    args_list=None,
    show_progress=True,
    description="Executing tasks",
):
    """
    Executes a function in parallel multiple times and returns the results.
    Handles KeyboardInterrupt by canceling pending futures.

    Args:
        func: The function to execute.
        n_times: Number of times to execute the function.
        max_workers: Maximum number of worker threads (defaults to n_times).
        args_list: Optional list of argument tuples to pass to each function call.
                  Each tuple in the list is unpacked and passed to one function call.
                  If provided, must have the same length as n_times.
        show_progress: Whether to show a progress bar (default: True).
        description: Description text for the progress bar (default: "Executing tasks").

    Returns:
        List of results from the function calls completed before any interruption.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from rich.progress import Progress, TaskID

    max_workers = max_workers or int(os.getenv("optimize.max_workers", n_times))
    results = []

    if args_list and len(args_list) != n_times:
        raise ValueError(
            f"args_list length ({len(args_list)}) must match n_times ({n_times})"
        )

    futures = []
    executor = None
    progress = None
    task_id = None

    try:
        executor = ThreadPoolExecutor(max_workers=max_workers)

        # Initialize progress bar if requested
        if show_progress:
            # Pause any active status displays to avoid conflicts
            pause_status()
            # Create progress with faster speed estimation updates
            progress = Progress()
            progress.start()
            task_id = progress.add_task(f"{description} (0/{n_times})", total=n_times)

        # Submit tasks to executor
        if args_list:
            futures = [executor.submit(func, *args) for args in args_list]
        else:
            futures = [executor.submit(func) for _ in range(n_times)]

        # Process results as they complete
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1

            # Update progress bar
            if show_progress and progress and task_id is not None:
                progress.update(
                    task_id,
                    advance=1,
                    description=f"{description} ({completed}/{n_times})",
                )

    except KeyboardInterrupt:
        # Cancel any pending futures when interrupted
        for future in futures:
            if not future.done():
                future.cancel()
        raise
    finally:
        # Stop progress bar and resume status displays
        if progress:
            progress.stop()
            # Resume any paused status displays
            resume_status()

        # Ensure the executor is shut down properly
        if executor:
            executor.shutdown(wait=False)

    return results


def generate_short_hash(length=6):
    """
    Generates a single short hash consisting of lowercase letters and digits.
    """
    return "".join(
        random.Random().choices(string.ascii_lowercase + string.digits, k=length)
    )


def init_logger(
    name,
    path=None,
    filename=None,
    levels=(logging.INFO, logging.INFO, logging.DEBUG),
    enables=(True, True, False),
    tags: list[str] = None,
):
    """Initialize a logger with certain name
    Args:
        name (str): Logger name
        path (str): Optional, specify which folder path
            the log file will be stored, for example
            '/tmp/log'
        level (tuple): Optional, consist of three logging levels.
            The first stands for logging level of console handler,
            the second and third stand for logging levels of file handlers.
        enable (tuple): Optional, define whether each handler is enabled.
            The first enables console handler,
            the second enables file handlers,
            and the third enables Langfuse handler.
    Returns:
        logging.Logger: logger instance
    """
    import logging.handlers
    import os
    import types

    # Import Rich components
    import rich
    from langfuse import Langfuse
    from rich.text import Text
    from rich.traceback import Traceback

    # Create a fully custom handler using Rich's Console directly
    class CustomRichLogHandler(logging.Handler):
        LEVEL_COLORS = {
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }

        def __init__(self, level=logging.NOTSET):
            super().__init__(level)
            self.console = rich.get_console()

        def emit(self, record):
            try:
                # Create timestamp text with bright black style
                timestamp = Text(f"[{self.formatTime(record)}]", style="bright_black")

                # Create level text with its associated color and fixed width
                level_text = Text(
                    f" {record.levelname:<8}",
                    style=self.LEVEL_COLORS.get(record.levelname, "white"),
                )

                # Process filename and function name, then truncate if too long
                filename = record.filename
                funcname = record.funcName
                if len(filename) > 15:
                    filename = "..." + filename[-12:]
                if len(funcname) > 10:
                    funcname = "..." + funcname[-7:]

                # Prepare file info text with bright blue style
                file_info = Text(
                    f"[{record.name}][{filename:15s}:{funcname:10s}:{record.lineno:4d}]",
                    style="bright_blue",
                )

                # Create message text from markup
                message = Text.from_markup(f" {record.getMessage()}")

                # Combine timestamp, level, and message as the left-side text
                left_text = Text.assemble(timestamp, level_text, message)

                # Get the console's total width and calculate the width for file_info
                total_width = self.console.width
                file_info_width = file_info.cell_len

                # Define available width for left_text (total width minus file_info width)
                available_width = total_width - file_info_width

                # Wrap left_text within the available width
                wrapped_lines = left_text.wrap(self.console, available_width)

                output_lines = []
                # Process all wrapped lines except the last one
                for line in wrapped_lines[:-1]:
                    output_lines.append(line)

                if wrapped_lines:
                    # For the last line, compute the padding needed
                    last_line = wrapped_lines[-1]
                    padding_length = available_width - last_line.cell_len
                    if padding_length > 0:
                        # Append spaces so that file_info can be added at the far right
                        padding = Text(" " * padding_length)
                        last_line = Text.assemble(last_line, padding, file_info)
                    else:
                        # If the last line already fills the available space, print file_info on a new line
                        new_line = (
                            Text(" " * (total_width - file_info_width)) + file_info
                        )
                        output_lines.append(new_line)
                    output_lines.append(last_line)
                else:
                    # In case left_text is empty, simply output file_info right-aligned
                    output_lines.append(
                        Text(" " * (total_width - file_info_width)) + file_info
                    )

                # Print all the assembled output lines
                for line in output_lines:
                    self.console.print(line)

                # If an exception occurred, print the traceback using Rich's formatting
                if record.exc_info:
                    exc_type, exc_value, exc_traceback = record.exc_info
                    tb = Traceback.from_exception(
                        exc_type, exc_value, exc_traceback, show_locals=True
                    )
                    self.console.print(tb)
            except Exception:
                self.handleError(record)

        def formatTime(self, record):
            """Format the time using a specified format."""
            import time

            formatter = logging.Formatter(datefmt="[%Y-%m-%d %H:%M:%S]")
            formatter.converter = time.localtime
            return formatter.formatTime(record)

    class CustomFileFormatter(logging.Formatter):
        def format(self, record):
            # Create a copy of the record to avoid modifying the original
            record = copy.copy(record)
            # Truncate filename if it is longer than 15 characters: keep the last 12 characters with "..." prefix
            if len(record.filename) > 15:
                record.filename = "..." + record.filename[-12:]
            # Truncate funcName if it is longer than 10 characters: keep the last 7 characters with "..." prefix
            if len(record.funcName) > 10:
                record.funcName = "..." + record.funcName[-7:]
            return super().format(record)

    # Create handler for langfuse
    class LangfuseHandler(logging.Handler):
        def __init__(self, langfuse: Langfuse, level=logging.NOTSET):
            super().__init__(level)
            self.langfuse = langfuse
            # Single trace for the entire logger
            self._trace = None
            # Dictionary to store spans by function call stack
            self._spans = {}
            # Logger name to associate with this handler
            self.logger_name = None

        def _get_function_stack(self, frame):
            """Build a complete stack of function calls from the current frame up to the root.
            Returns the entire stack for span creation decisions based on stack level.
            Filters only frames containing the current working directory in the filename."""
            import os

            # Get the current working directory to check against filenames
            cwd = os.getcwd()

            # Collect frames in a stack
            stack = []
            current_frame = frame

            while current_frame:
                # Skip frames that are part of the logging infrastructure
                if (
                    current_frame.f_code.co_filename == __file__
                    or current_frame.f_code.co_name
                    in ["handle", "callHandlers", "_log", "emit"]
                    or cwd not in current_frame.f_code.co_filename
                ):
                    current_frame = current_frame.f_back
                    continue

                # Create a frame info tuple with filename, function name, and line number
                frame_info = (
                    current_frame.f_code.co_filename,
                    current_frame.f_code.co_name,
                )
                # Add to stack if the filename contains the cwd
                stack.append(frame_info)
                current_frame = current_frame.f_back

            stack.append(("root", "trace"))
            stack.reverse()
            return tuple(stack)

        def _get_or_create_trace(self, logger_name):
            """Get or create a single trace for the logger."""
            if self._trace is None:
                self._trace = self.langfuse.trace(
                    name=logger_name, metadata={"logger": logger_name}
                )
            return self._trace

        def _get_span(self, function_stack):
            """Get an existing span or create a nested structure of spans based on the function stack."""
            if not function_stack:
                return self._trace  # If no stack, use the trace directly

            # Generate a stack key for lookup
            stack_key = tuple(function_stack)

            # Return existing span if we have one for this exact stack
            if stack_key in self._spans:
                return self._spans[stack_key]

            # For nested functions, find the parent span and create a child span
            parent_stack_key = tuple(function_stack[:-1])

            # Ensure the parent span exists
            if parent_stack_key not in self._spans:
                self._get_span(function_stack[:-1])

            # Now get the parent span
            parent_span = self._spans[parent_stack_key]

            # Create a child span
            filename, funcname = function_stack[-1]
            span = parent_span.span(
                name=funcname,
                metadata={
                    "filename": filename,
                },
            )
            self._spans[stack_key] = span
            return span

        def _end_spans(self, function_stack):
            """End spans that are no longer in the function stack."""
            end_spans = []
            for stack_key in self._spans:
                for i in range(len(stack_key)):
                    if i < len(function_stack) and stack_key[i] == function_stack[i]:
                        continue
                    self._spans[stack_key].end()
                    end_spans.append(stack_key)
                    break
            for stack_key in end_spans:
                del self._spans[stack_key]

        def emit(self, record):
            try:
                import inspect

                # Initialize trace on first use
                if self._trace is None:
                    self.logger_name = record.name
                    self._trace = self.langfuse.trace(
                        name=record.name, metadata={"logger": record.name}, tags=tags
                    )
                    self._spans[(("root", "trace"),)] = self._trace

                # Get the current execution frame
                frame = inspect.currentframe()

                # Skip handler frames to get to the actual logging code
                while frame:
                    if (
                        frame.f_code.co_filename != __file__
                        and frame.f_code.co_name != "emit"
                    ):
                        break
                    frame = frame.f_back

                # Find the appropriate span for this log event
                if frame:
                    # Get the function call stack
                    function_stack = self._get_function_stack(frame)
                    self._end_spans(function_stack)
                    # Get or create the span for this function stack
                    span = self._get_span(function_stack)
                else:
                    # If we can't determine the frame, log at the trace level
                    span = self._trace

                # Prepare metadata with standard fields
                metadata = {
                    "filename": record.filename,
                    "funcName": record.funcName,
                    "lineno": record.lineno,
                }

                # Add exception info to metadata if available
                if record.exc_info:
                    exc_type, exc_value, exc_tb = record.exc_info
                    metadata["exception"] = {
                        "type": exc_type.__name__,
                        "message": str(exc_value),
                    }

                    # Add traceback information
                    import traceback

                    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
                    metadata["traceback"] = "".join(tb_lines)

                # Map Python's logging levels to Langfuse's accepted levels
                langfuse_level_map = {
                    "DEBUG": "DEBUG",
                    "INFO": "DEFAULT",
                    "WARNING": "WARNING",
                    "ERROR": "ERROR",
                    "CRITICAL": "ERROR",
                }

                # Use the mapped level or default to 'DEFAULT' if not found
                langfuse_level = langfuse_level_map.get(record.levelname, "DEFAULT")

                # Determine the log method name (info, debug, etc.)
                log_method = (
                    record.levelname.lower()
                )  # Convert INFO to info, DEBUG to debug, etc.

                # Log the event with the appropriate span
                span.event(
                    name=log_method,  # Use the logging level (info, debug, etc.) as event name
                    level=langfuse_level,
                    status_message=record.getMessage(),
                    metadata=metadata,
                )

            except Exception:
                self.handleError(record)

        def close(self):
            # End all spans
            for span in self._spans.values():
                if span is not self._trace:
                    span.end()
            super().close()

    class DebugModuleFilter(logging.Filter):
        """
        Custom logging filter:
        When the log level is DEBUG, only logs originating from files whose full paths
        are listed in debug_modules will be output.
        """

        def __init__(self, handler=None):
            super().__init__()
            self.handler = handler

        def filter(self, record):
            if record.levelno == logging.DEBUG:
                # Check if the handler's level is higher than DEBUG
                # If so, filter out the log regardless of the module
                if self.handler and self.handler.level > logging.DEBUG:
                    return False

                # Convert record.pathname to an absolute path for consistency.
                record_path = os.path.abspath(record.pathname)
                if not registered_debug_modules:
                    # If no modules are registered, allow all DEBUG logs.
                    return True
                elif record_path not in registered_debug_modules:
                    return False
            return True

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = 0
    if filename is None:
        filename = name
    if path:
        folderpath = path
    else:
        folderpath = get_path("../logs")
    filepath = os.path.join(folderpath, filename)
    setattr(logger, "log_path", folderpath)
    setattr(logger, "base_filename", filename)  # Store the base filename for later use

    if enables[0]:
        # Use our fully custom Rich handler for console output
        rich_handler = CustomRichLogHandler(
            level=levels[0],
        )
        rich_handler.addFilter(DebugModuleFilter(handler=rich_handler))
        logger.addHandler(rich_handler)
        # print(f"669 handlers: {logger.handlers}, {len(logger.handlers)}")

    if enables[1]:
        # Import necessary components for async logging
        import atexit
        import queue
        from logging.handlers import QueueHandler, QueueListener

        # Create a queue for log records
        log_queue = queue.Queue(-1)  # Unlimited size queue

        # Keep the regular file handlers with standard formatting
        _nf = "[%(asctime)s] %(levelname)-8s [%(name)s][%(filename)15s:%(funcName)10s:%(lineno)4d] %(message)s"
        nformatter = CustomFileFormatter(_nf)

        # Create the actual RotatingFileHandlers - these won't be added directly to the logger
        # but will be managed by the QueueListener
        handler1 = logging.handlers.RotatingFileHandler(
            filepath + f"_{logging.getLevelName(levels[1])}.log",
            maxBytes=50 * 1024 * 1024,
            backupCount=5,
        )
        handler1.setLevel(levels[1])
        handler1.setFormatter(nformatter)
        handler1.addFilter(DebugModuleFilter(handler=handler1))

        handler2 = logging.handlers.RotatingFileHandler(
            filepath + f"_{logging.getLevelName(levels[2])}.log",
            maxBytes=50 * 1024 * 1024,
            backupCount=5,
        )
        handler2.setLevel(levels[2])
        handler2.setFormatter(nformatter)
        handler2.addFilter(DebugModuleFilter(handler=handler2))

        # Create and start a queue listener that will handle the actual file writing
        # in a separate thread
        listener = QueueListener(
            log_queue, handler1, handler2, respect_handler_level=True
        )
        listener.start()

        # Define shutdown function to ensure proper cleanup on program exit
        def shutdown():
            # First stop the listener (processes any remaining records in the queue)
            listener.stop()
            # Then explicitly flush and close each handler
            handler1.flush()
            handler2.flush()
            handler1.close()
            handler2.close()

        # Register the shutdown function to run on program exit
        atexit.register(shutdown)

        # Create a QueueHandler that will send log records to the queue
        queue_handler = QueueHandler(log_queue)
        logger.addHandler(queue_handler)

        # Store listener reference on the logger so it can be accessed if needed
        setattr(logger, "queue_listener", listener)

    # Add Langfuse handler if enabled
    if enables[2]:
        from core.log import get_langfuse

        # Get Langfuse instance
        langfuse = get_langfuse()
        if langfuse:
            # Create and add Langfuse handler
            langfuse_handler = LangfuseHandler(langfuse)
            langfuse_handler.addFilter(DebugModuleFilter())
            logger.addHandler(langfuse_handler)
            # print(f"711 handlers: {logger.handlers}, {len(logger.handlers)}")

    def findCaller(self, stack_info=False, frame=None):
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.
        """
        from logging import _srcfile, currentframe, io, os, traceback

        if frame:
            f = frame
        else:
            f = get_frame(3)
            # On some versions of IronPython, currentframe() returns None if
            # IronPython isn't run with -X:Frames.
            if f is not None:
                f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)", None
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile:
                f = f.f_back
                continue
            sinfo = None
            if stack_info:
                sio = io.StringIO()
                sio.write("Stack (most recent call last):\n")
                traceback.print_stack(f, file=sio)
                sinfo = sio.getvalue()
                if sinfo[-1] == "\n":
                    sinfo = sinfo[:-1]
                sio.close()
            rv = (co.co_filename, f.f_lineno, co.co_name, sinfo)
            break
        return rv

    def _log(
        self, level, msg, args, exc_info=None, extra=None, stack_info=False, frame=None
    ):
        """
        Low-level logging routine which creates a LogRecord and then calls
        all the handlers of this logger to handle the record.
        """
        from logging import _srcfile, sys

        sinfo = None
        if _srcfile:
            # IronPython doesn't track Python frames, so findCaller raises an
            # exception on some versions of IronPython. We trap it here so that
            # IronPython can use logging.
            try:
                fn, lno, func, sinfo = self.findCaller(stack_info, frame)
            except ValueError:  # pragma: no cover
                fn, lno, func = "(unknown file)", 0, "(unknown function)"
        else:  # pragma: no cover
            fn, lno, func = "(unknown file)", 0, "(unknown function)"
        if exc_info:
            if isinstance(exc_info, BaseException):
                exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
            elif not isinstance(exc_info, tuple):
                exc_info = sys.exc_info()
        record = self.makeRecord(
            self.name, level, fn, lno, msg, args, exc_info, func, extra, sinfo
        )
        self.handle(record)

    func_type = types.MethodType
    logger.findCaller = func_type(findCaller, logger)
    logger._log = func_type(_log, logger)
    return logger


def get_run_timestamp():
    import datetime

    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


RUN_TIMESTAMP = get_run_timestamp()


class DummyLogger(object):
    """Dummy logger, replace all method with pass"""

    def __init__(self):
        pass

    def setLevel(self, level):
        pass

    def debug(self, msg, *args, **kwargs):
        pass

    def info(self, msg, *args, **kwargs):
        pass

    def warning(self, msg, *args, **kwargs):
        pass

    def warn(self, msg, *args, **kwargs):
        pass

    def error(self, msg, *args, **kwargs):
        pass

    def exception(self, msg, *args, exc_info=True, **kwargs):
        pass

    def critical(self, msg, *args, **kwargs):
        pass

    fatal = critical

    def log(self, level, msg, *args, **kwargs):
        pass

    def findCaller(self, stack_info=False, frame=None):
        pass

    def makeRecord(
        self,
        name,
        level,
        fn,
        lno,
        msg,
        args,
        exc_info,
        func=None,
        extra=None,
        sinfo=None,
    ):
        pass

    def _log(
        self, level, msg, args, exc_info=None, extra=None, stack_info=False, frame=None
    ):
        pass

    def handle(self, record):
        pass

    def addHandler(self, hdlr):
        pass

    def removeHandler(self, hdlr):
        pass

    def hasHandlers(self):
        pass

    def callHandlers(self, record):
        pass

    def getEffectiveLevel(self):
        pass

    def isEnabledFor(self, level):
        pass

    def getChild(self, suffix):
        pass


class Dummytqdm(object):
    def update(self, n=1):
        pass

    def close(self):
        pass

    def unpause(self):
        pass

    def set_description(self, desc=None, refresh=True):
        pass

    def set_description_str(self, desc=None, refresh=True):
        pass

    def set_postfix(self, ordered_dict=None, refresh=True, **kwargs):
        pass

    def set_postfix_str(self, s="", refresh=True):
        pass

    def moveto(self, n):
        pass

    def clear(self, nolock=False):
        pass

    def refresh(self, nolock=False):
        pass


def save_obs_image(image, category: str, name: str, index: int) -> None:
    """Save observation image locally if save_obs_local is enabled.

    Args:
        image: PIL.Image to save
        category: Category name (e.g., "Raw Screenshot", "Combined Obs")
        name: Name of the image (e.g., "raw screenshot", "combined obs")
        index: Index number for the image
    """
    import os

    from core.log import get_logger

    # Check if local saving is enabled
    if os.getenv("flags.save_obs_local", "false").lower() != "true":
        return

    # Get logger to access log_path
    logger = get_logger()
    if not hasattr(logger, "log_path"):
        return

    # Create directory if it doesn't exist
    save_dir = os.path.join(logger.log_path, category.replace(" ", "_"))
    os.makedirs(save_dir, exist_ok=True)

    # Save image
    filename = f"{name.replace(' ', '_')}_{index:08d}.jpeg"
    filepath = os.path.join(save_dir, filename)
    image.save(filepath)


class GlobalStatusManager:
    """
    Global manager for Rich status displays that can be paused when needed.

    This allows coordination between different parts of the application
    that need to use Rich's live display functionality.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._active_status: Optional["ManagedStatus"] = None
        self._paused = False

    def create_status(self, console, text) -> "ManagedStatus":
        """Create a managed status that can be paused globally."""
        return ManagedStatus(self, console, text)

    def pause_all(self):
        """Pause all active status displays."""
        with self._lock:
            if self._active_status and not self._paused:
                self._active_status._pause_internal()
                self._paused = True

    def resume_all(self):
        """Resume all paused status displays."""
        with self._lock:
            if self._active_status and self._paused:
                self._active_status._resume_internal()
                self._paused = False

    def _register_status(self, status: "ManagedStatus"):
        """Register a status as active."""
        with self._lock:
            if self._active_status:
                self._active_status._stop_internal()
            self._active_status = status

    def _unregister_status(self, status: "ManagedStatus"):
        """Unregister a status."""
        with self._lock:
            if self._active_status is status:
                self._active_status = None
                self._paused = False


class ManagedStatus:
    """A status display that can be managed globally."""

    def __init__(self, manager: GlobalStatusManager, console, text):
        self.manager = manager
        self.console = console
        self.text = text
        self.status = None
        self.is_active = False
        self._locally_paused = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        """Start the status display."""
        if not self.is_active:
            self.manager._register_status(self)
            self._start_status()

    def stop(self):
        """Stop the status display."""
        if self.is_active:
            self._stop_internal()
            self.manager._unregister_status(self)

    def _start_status(self):
        """Internal method to start the status display."""
        if not self.is_active and not self._locally_paused:
            try:
                from rich.status import Status

                self.status = Status(self.text, console=self.console, spinner="dots")
                self.status.start()
                self.is_active = True
            except Exception:
                # If there's a conflict, just skip the status
                pass

    def _stop_internal(self):
        """Internal method to stop the status display."""
        if self.is_active and self.status:
            try:
                self.status.stop()
            except Exception:
                pass
            self.status = None
            self.is_active = False

    def _pause_internal(self):
        """Internal method called by manager to pause."""
        if self.is_active:
            self._stop_internal()

    def _resume_internal(self):
        """Internal method called by manager to resume."""
        if not self.is_active and not self._locally_paused:
            self._start_status()

    def update_text(self, text):
        """Update the status text."""
        self.text = text
        if self.is_active and self.status:
            self.status.update(text)


# Global instance
_global_status_manager = GlobalStatusManager()


def get_status_manager() -> GlobalStatusManager:
    """Get the global status manager instance."""
    return _global_status_manager


def pause_status():
    """Convenience function to pause all status displays."""
    _global_status_manager.pause_all()


def resume_status():
    """Convenience function to resume all status displays."""
    _global_status_manager.resume_all()

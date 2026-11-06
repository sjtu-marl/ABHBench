import logging
import os

from clearml import Task
from dotenv import dotenv_values

from core import extra_config
from core.utils import (
    DummyLogger,
    get_path,
    get_run_timestamp,
    init_logger,
    register_debug_module,
)

_global_logger = None
_global_langfuse = None
_global_clearml = None


def init_global_logger(
    logger_name: str,
    filename: str,
    enables=(True, True, False),
    levels=(logging.INFO, logging.INFO, logging.DEBUG),
    tags=None,
):
    global _global_logger

    clearml_enabled = os.getenv("flags.clearml", "false").lower() == "true"
    if clearml_enabled:
        init_clearml(logger_name, filename, tags)

    log_path = get_path(f"logs/{get_run_timestamp()}", parent=True)
    _levels = (os.getenv("flags.console_level", levels[0]), levels[1], levels[2])
    _global_logger = init_logger(
        logger_name,
        path=log_path,
        filename=filename,
        enables=enables,
        levels=_levels,
        tags=tags,
    )
    _global_logger.info(f"Logger initialized at path: {log_path}")

    # Print .env and config information to debug log
    config = dotenv_values()
    _global_logger.debug("Environment variables from .env file:")
    for key, value in config.items():
        _global_logger.debug(f"  {key}: {value}")

    _global_logger.debug("Extra configuration:")
    for key, value in extra_config.items():
        _global_logger.debug(f"  {key}: {value}")
    # _global_logger.info(
    #     f"Logger handlers: {_global_logger.handlers}, {len(_global_logger.handlers)}"
    # )
    return _global_logger


def get_logger():
    global _global_logger
    if _global_logger is None:
        if os.getenv("flags.rich", "false").lower() == "true":
            from rich.logging import RichHandler

            FORMAT = "%(message)s"
            logging.basicConfig(
                level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
            )

            _global_logger = logging.getLogger("rich")
            return _global_logger
        print("Global logger not initialized. Returning a dummy logger.")
        return DummyLogger()
    return _global_logger


def close_logger():
    global _global_logger

    # Upload log files to ClearML if enabled
    if is_enabled_clearml() and _global_logger:
        task = get_clearml()

        # Only upload specific log files based on the logger's handlers
        if hasattr(_global_logger, "log_path") and hasattr(_global_logger, "handlers"):
            log_path = _global_logger.log_path

            # Using the base_filename attribute that we set during logger initialization
            if hasattr(_global_logger, "base_filename"):
                filename = _global_logger.base_filename

                # Upload INFO and DEBUG log files
                for level in ["INFO", "DEBUG"]:
                    log_filename = f"{filename}_{level}.log"
                    log_filepath = os.path.join(log_path, log_filename)

                    if os.path.isfile(log_filepath):
                        try:
                            task.upload_artifact(
                                name=log_filename,
                                artifact_object=log_filepath,
                                metadata={"description": f"{level} log file"},
                            )
                        except Exception:
                            pass

                    # Also check for rotated log files (e.g., filename_INFO.log.1, filename_INFO.log.2, etc.)
                    for i in range(1, 6):  # Check for up to 5 rotated files
                        rotated_filename = f"{log_filename}.{i}"
                        rotated_filepath = os.path.join(log_path, rotated_filename)

                        if os.path.isfile(rotated_filepath):
                            try:
                                task.upload_artifact(
                                    name=rotated_filename,
                                    artifact_object=rotated_filepath,
                                    metadata={
                                        "description": f"Rotated {level} log file #{i}"
                                    },
                                )
                            except Exception:
                                pass
            else:
                # Fall back to scanning the directory for log files
                logger_name = _global_logger.name

                # List all files in the log directory and look for ones matching the logger name
                log_files = os.listdir(log_path)
                matching_files = [
                    f
                    for f in log_files
                    if f.startswith(logger_name) and f.endswith(".log")
                ]

                for log_file in matching_files:
                    log_filepath = os.path.join(log_path, log_file)
                    try:
                        task.upload_artifact(
                            name=log_file,
                            artifact_object=log_filepath,
                            metadata={"description": "Log file"},
                        )
                    except Exception:
                        pass

    close_clearml()
    if not _global_logger:
        return
    handlers = _global_logger.handlers[:]
    for handler in handlers:
        handler.close()
        _global_logger.removeHandler(handler)
        assert handler not in _global_logger.handlers
    _global_logger = None


def set_tags_with_verification(task: Task, tags, max_retries=5):
    """
    Set tags on the ClearML task and verify they are properly set on the remote server.
    Will keep retrying until all tags are successfully set or max_retries is reached.

    Args:
        task: ClearML Task object
        tags: Tags to set (string, list, or set)
        max_retries: Maximum number of retry attempts (default: 5)

    Returns:
        bool: True if all tags successfully set, False otherwise
    """
    if not tags:
        return True

    # Convert tags to set for easier comparison
    if isinstance(tags, list):
        expected_tags = set(tags)
    elif not isinstance(tags, set):
        expected_tags = {tags}
    else:
        expected_tags = tags

    retry_count = 0

    try:
        while retry_count < max_retries:
            # Set tags with the full list
            task.set_tags(list(expected_tags))

            # Force task data update from server
            task.reload()
            remote_tags = set(task.get_tags())

            # Check if all expected tags are present
            missing_tags = expected_tags - remote_tags
            if not missing_tags:
                # All tags set successfully
                return True

            # Increment retry counter
            retry_count += 1

            # Small delay before next retry (can be removed if causing issues)
            import time

            time.sleep(0.5)

        # If we've reached max retries and still have missing tags, return False
        return False

    except Exception:
        # Silently handle exceptions - we don't want to break initialization
        return False


def process_tags(tags):
    """
    Process and combine tags from different sources.
    Handles tags from function arguments and from config flags.clearml_tag.

    Args:
        tags: Tags provided directly to the function (string, list, or set)

    Returns:
        list: Combined list of tags from all sources
    """
    # Process the direct tags argument
    if tags is None:
        all_tags = []
    elif isinstance(tags, str):
        all_tags = [tags]
    elif isinstance(tags, (list, set)):
        all_tags = list(tags)
    else:
        all_tags = [str(tags)]

    # Process additional tags from config
    clearml_tag_str = os.getenv("flags.clearml_tag", "")
    if clearml_tag_str:
        # Split the comma-separated string and strip whitespace
        config_tags = [tag.strip() for tag in clearml_tag_str.split(",") if tag.strip()]
        all_tags.extend(config_tags)

    # Return unique tags
    return list(set(all_tags))


def init_clearml(project_name: str, task_name: str, tags) -> Task:
    global _global_clearml
    if os.getenv("flags.random", "true").lower() == "true":
        Task.set_random_seed(None)
    _global_clearml = Task.init(
        project_name=project_name,
        task_name=task_name,
        task_type=Task.TaskTypes.inference,
        reuse_last_task_id=False,
        auto_connect_frameworks={"matplotlib": False},
        auto_resource_monitoring=False,
    )
    config = dotenv_values()
    _global_clearml.set_user_properties(**config)
    _global_clearml.set_user_properties(**extra_config)

    # Process and combine tags from all sources
    combined_tags = process_tags(tags)

    # Set tags and verify they are properly set on the remote server
    set_tags_with_verification(_global_clearml, combined_tags)

    return _global_clearml


def get_clearml() -> Task:
    global _global_clearml
    return _global_clearml


def close_clearml():
    global _global_clearml
    if not _global_clearml:
        return
    _global_clearml.close()
    _global_clearml = None


def is_enabled_clearml() -> bool:
    return _global_clearml is not None


def is_enabled_langfuse() -> bool:
    return _global_langfuse is not None


__all__ = [
    "init_global_logger",
    "get_logger",
    "close_logger",
    "get_clearml",
    "is_enabled_clearml",
    "register_debug_module",
    "set_tags_with_verification",
    "process_tags",
]

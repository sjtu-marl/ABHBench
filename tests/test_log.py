import shutil
import tempfile
from unittest.mock import patch

import pytest

from core.log import close_logger, init_global_logger


@pytest.fixture
def temp_log_dir():
    # Create a temporary directory for log files
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Clean up after the test
    shutil.rmtree(temp_dir)


def test_init_logger_without_langfuse(temp_log_dir):
    """Test initializing the logger without Langfuse enabled"""
    with patch("core.utils.get_path") as mock_get_path:
        mock_get_path.return_value = temp_log_dir

        # Initialize logger with Langfuse disabled
        logger = init_global_logger(
            "test_logger", "test_log", enables=(True, True, False)
        )

        # Check if logger is correctly initialized
        assert logger is not None
        assert logger.name == "test_logger"

        # Check handlers (should have console and file handlers but no Langfuse)
        handler_types = [type(h) for h in logger.handlers]
        assert len(logger.handlers) == 3  # Console handler + 2 file handlers

        # Check if any handler is a Langfuse handler
        has_langfuse_handler = any(
            hasattr(h, "_trace") and hasattr(h, "_spans") for h in logger.handlers
        )
        assert not has_langfuse_handler

        # Clean up
        close_logger()


def test_init_logger_with_langfuse(temp_log_dir):
    """Test initializing the logger with Langfuse enabled using real Langfuse"""
    with patch("core.utils.get_path") as mock_get_path:
        mock_get_path.return_value = temp_log_dir

        # Initialize logger with Langfuse enabled
        logger = init_global_logger(
            "test_logger", "test_log", enables=(True, True, True)
        )

        # Check if logger is correctly initialized
        assert logger is not None
        assert logger.name == "test_logger"

        # Check if Langfuse handler is added
        has_langfuse_handler = any(
            hasattr(h, "_trace") and hasattr(h, "_spans") for h in logger.handlers
        )
        assert has_langfuse_handler

        # Log a test message to ensure it works
        logger.info("Testing Langfuse integration")

        # Clean up
        close_logger()


def test_exception_logging_with_langfuse(temp_log_dir):
    """Test that exception info is included in Langfuse events using real Langfuse"""
    with patch("core.utils.get_path") as mock_get_path:
        mock_get_path.return_value = temp_log_dir

        # Initialize Langfuse and logger
        logger = init_global_logger(
            "test_logger", "test_log", enables=(True, True, True)
        )

        # Find the Langfuse handler
        langfuse_handler = next(
            (
                h
                for h in logger.handlers
                if hasattr(h, "_trace") and hasattr(h, "_spans")
            ),
            None,
        )
        assert langfuse_handler is not None

        # Create a spy on the handler's emit method
        with patch.object(
            langfuse_handler, "emit", wraps=langfuse_handler.emit
        ) as spy_emit:
            # Log an exception
            try:
                raise ValueError("Test exception")
            except ValueError:
                logger.exception("An error occurred")

            # Verify emit was called
            assert spy_emit.call_count >= 1

            # Give Langfuse a moment to process
            logger.info("Exception test completed")

        # Clean up
        close_logger()


def outer_function(logger):
    """Parent function to demonstrate span hierarchy"""
    logger.info("This is the outer function")
    inner_function(logger)
    return "Outer function completed"


def inner_function(logger):
    """Child function to demonstrate span hierarchy"""
    logger.info("This is the inner function")
    innermost_function(logger)
    return "Inner function completed"


def innermost_function(logger):
    """Innermost function to demonstrate span hierarchy"""
    logger.info("This is the innermost function")
    # Log an error to test exception handling
    try:
        raise ValueError("Test exception in innermost function")
    except ValueError:
        logger.exception("An error occurred in innermost function")
    return "Innermost function completed with error"


def test_langfuse_spans_and_hierarchy(temp_log_dir):
    """Test that Langfuse spans are created with proper hierarchy using real functions"""
    with patch("core.utils.get_path") as mock_get_path:
        mock_get_path.return_value = temp_log_dir

        # Initialize logger with Langfuse enabled but file logging disabled for simplicity
        logger = init_global_logger(
            "test_hierarchy", "test_hierarchy", enables=(True, False, True)
        )

        # Find the Langfuse handler
        langfuse_handler = next(
            (
                h
                for h in logger.handlers
                if hasattr(h, "_trace") and hasattr(h, "_spans")
            ),
            None,
        )
        assert langfuse_handler is not None, "Langfuse handler should be present"

        # Spy on the emit method to track calls
        with patch.object(
            langfuse_handler, "emit", wraps=langfuse_handler.emit
        ) as spy_emit:
            # Call the outer function which calls inner functions
            # This creates a real call stack for the span hierarchy
            result = outer_function(logger)

            # Verify that the emit method was called multiple times
            assert spy_emit.call_count >= 4  # At least 4 calls (3 info + 1 exception)

            # Give some meaningful output
            logger.info(f"Test completed with result: {result}")

        # Clean up
        close_logger()

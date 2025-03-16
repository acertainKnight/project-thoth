"""
Logging utilities for Thoth.
"""
import logging
import sys
from pathlib import Path


def setup_logging(log_level: str, log_file: Path) -> None:
    """
    Set up logging for Thoth.

    Args:
        log_level (str): The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file (Path): Path to the log file.
    """
    # Create logger
    logger = logging.getLogger("thoth")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler(log_file)

    # Create formatters
    console_format = logging.Formatter("%(levelname)s - %(message)s")
    file_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Set formatters
    console_handler.setFormatter(console_format)
    file_handler.setFormatter(file_format)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # Log startup message
    logger.info("Logging initialized")

"""
File utilities for Thoth.
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def ensure_directory(directory: Path) -> Path:
    """
    Ensure that a directory exists, creating it if necessary.

    Args:
        directory (Path): The directory path to ensure.

    Returns:
        Path: The directory path.
    """
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def copy_file(source: Path, destination: Path) -> Path:
    """
    Copy a file from source to destination.

    Args:
        source (Path): The source file path.
        destination (Path): The destination file path.

    Returns:
        Path: The destination file path.
    """
    ensure_directory(destination.parent)
    return Path(shutil.copy2(source, destination))


def list_files(directory: Path, pattern: str = "*") -> list[Path]:
    """
    List files in a directory matching a pattern.

    Args:
        directory (Path): The directory to list files from.
        pattern (str): The glob pattern to match files against.

    Returns:
        List[Path]: A list of file paths.
    """
    return list(directory.glob(pattern))


def get_file_stem(file_path: Path) -> str:
    """
    Get the stem (filename without extension) of a file.

    Args:
        file_path (Path): The file path.

    Returns:
        str: The file stem.
    """
    return file_path.stem


def get_relative_path(file_path: Path, base_path: Path) -> Path:
    """
    Get the relative path of a file from a base path.

    Args:
        file_path (Path): The file path.
        base_path (Path): The base path.

    Returns:
        Path: The relative path.
    """
    return file_path.relative_to(base_path)

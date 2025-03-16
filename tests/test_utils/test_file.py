"""
Tests for the file utility module.
"""
import os
import tempfile
from pathlib import Path

import pytest

from thoth.utils.file import (
    ensure_directory,
    copy_file,
    list_files,
    get_file_stem,
    get_relative_path,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


def test_ensure_directory(temp_dir):
    """Test ensure_directory function."""
    # Test with existing directory
    result = ensure_directory(temp_dir)
    assert result == temp_dir
    assert result.exists()
    assert result.is_dir()

    # Test with new directory
    new_dir = temp_dir / "new_dir"
    result = ensure_directory(new_dir)
    assert result == new_dir
    assert result.exists()
    assert result.is_dir()

    # Test with nested directory
    nested_dir = temp_dir / "nested" / "dir"
    result = ensure_directory(nested_dir)
    assert result == nested_dir
    assert result.exists()
    assert result.is_dir()


def test_copy_file(temp_dir):
    """Test copy_file function."""
    # Create a source file
    source_file = temp_dir / "source.txt"
    with open(source_file, "w") as f:
        f.write("Test content")

    # Test copying to existing directory
    dest_file = temp_dir / "dest.txt"
    result = copy_file(source_file, dest_file)
    assert result == dest_file
    assert result.exists()
    assert result.read_text() == "Test content"

    # Test copying to new directory
    new_dest_file = temp_dir / "new_dir" / "dest.txt"
    result = copy_file(source_file, new_dest_file)
    assert result == new_dest_file
    assert result.exists()
    assert result.read_text() == "Test content"
    assert new_dest_file.parent.exists()
    assert new_dest_file.parent.is_dir()


def test_list_files(temp_dir):
    """Test list_files function."""
    # Create some files
    (temp_dir / "file1.txt").touch()
    (temp_dir / "file2.txt").touch()
    (temp_dir / "file3.md").touch()
    (temp_dir / "subdir").mkdir()
    (temp_dir / "subdir" / "file4.txt").touch()

    # Test listing all files
    files = list_files(temp_dir)
    assert len(files) == 4
    assert temp_dir / "file1.txt" in files
    assert temp_dir / "file2.txt" in files
    assert temp_dir / "file3.md" in files
    assert temp_dir / "subdir" in files

    # Test listing files with pattern
    txt_files = list_files(temp_dir, "*.txt")
    assert len(txt_files) == 2
    assert temp_dir / "file1.txt" in txt_files
    assert temp_dir / "file2.txt" in txt_files
    assert temp_dir / "file3.md" not in txt_files

    # Test listing files recursively
    all_txt_files = list_files(temp_dir, "**/*.txt")
    assert len(all_txt_files) == 3
    assert temp_dir / "file1.txt" in all_txt_files
    assert temp_dir / "file2.txt" in all_txt_files
    assert temp_dir / "subdir" / "file4.txt" in all_txt_files


def test_get_file_stem():
    """Test get_file_stem function."""
    assert get_file_stem(Path("file.txt")) == "file"
    assert get_file_stem(Path("path/to/file.txt")) == "file"
    assert get_file_stem(Path("file")) == "file"
    assert get_file_stem(Path("file.tar.gz")) == "file.tar"


def test_get_relative_path():
    """Test get_relative_path function."""
    base_path = Path("/base/path")
    file_path = Path("/base/path/to/file.txt")
    assert get_relative_path(file_path, base_path) == Path("to/file.txt")

    base_path = Path("/base/path")
    file_path = Path("/base/path/file.txt")
    assert get_relative_path(file_path, base_path) == Path("file.txt")

    with pytest.raises(ValueError):
        # File path is not relative to base path
        get_relative_path(Path("/other/path/file.txt"), Path("/base/path"))

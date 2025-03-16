"""
Tests for utility functions in the Thoth AI Research Agent.
"""

import os
import tempfile
import unittest
from pathlib import Path

from src.thoth.utils.file_utils import (
    ensure_directory,
    get_filename_without_extension,
    write_text_file,
    read_text_file
)
from src.thoth.utils.text_utils import (
    normalize_text,
    create_slug,
    truncate_text,
    extract_doi
)


class TestFileUtils(unittest.TestCase):
    """
    Tests for file utility functions.
    """

    def test_ensure_directory(self):
        """Test that ensure_directory creates a directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = os.path.join(temp_dir, "test_dir")
            result = ensure_directory(test_dir)
            self.assertTrue(os.path.exists(test_dir))
            self.assertTrue(os.path.isdir(test_dir))
            self.assertEqual(result, str(Path(test_dir).absolute()))

    def test_get_filename_without_extension(self):
        """Test that get_filename_without_extension returns the correct filename."""
        self.assertEqual(get_filename_without_extension("/path/to/file.txt"), "file")
        self.assertEqual(get_filename_without_extension("file.pdf"), "file")
        self.assertEqual(get_filename_without_extension("file"), "file")

    def test_write_and_read_text_file(self):
        """Test that write_text_file and read_text_file work correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = os.path.join(temp_dir, "test.txt")
            test_content = "Hello, world!"

            # Test writing
            result = write_text_file(test_file, test_content)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(test_file))

            # Test reading
            read_content = read_text_file(test_file)
            self.assertEqual(read_content, test_content)


class TestTextUtils(unittest.TestCase):
    """
    Tests for text utility functions.
    """

    def test_normalize_text(self):
        """Test that normalize_text removes extra whitespace."""
        self.assertEqual(normalize_text("  Hello,  world!  "), "Hello, world!")
        self.assertEqual(normalize_text("\n\nHello,\n\nworld!\n\n"), "Hello, world!")

    def test_create_slug(self):
        """Test that create_slug creates a valid slug."""
        self.assertEqual(create_slug("Hello, World!"), "hello-world")
        self.assertEqual(create_slug("Title: With Punctuation!"), "title-with-punctuation")
        self.assertEqual(create_slug("Multiple   Spaces"), "multiple-spaces")

    def test_truncate_text(self):
        """Test that truncate_text truncates text correctly."""
        text = "This is a long text that needs to be truncated."
        self.assertEqual(truncate_text(text, 10), "This is...")
        self.assertEqual(truncate_text(text, 10, add_ellipsis=False), "This is a")
        self.assertEqual(truncate_text("Short", 10), "Short")

    def test_extract_doi(self):
        """Test that extract_doi extracts DOIs correctly."""
        self.assertEqual(extract_doi("DOI: 10.1234/abcd.5678"), "10.1234/abcd.5678")
        self.assertEqual(extract_doi("https://doi.org/10.1234/abcd.5678"), "10.1234/abcd.5678")
        self.assertEqual(extract_doi("No DOI here"), None)


if __name__ == "__main__":
    unittest.main()

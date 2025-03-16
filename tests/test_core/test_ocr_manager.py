"""
Tests for the OCR Manager.
"""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from thoth.core.ocr_manager import OCRError, OCRManager


class TestOCRManager(unittest.TestCase):
    """Tests for the OCR Manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.ocr_manager = OCRManager(api_key=self.api_key)
        self.test_pdf_path = Path("tests/fixtures/test.pdf")
        self.test_output_dir = Path("tests/fixtures/output")

        # Create test directories if they don't exist
        os.makedirs(self.test_output_dir, exist_ok=True)

        # Ensure the test PDF file exists
        if not self.test_pdf_path.exists():
            self.test_pdf_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.test_pdf_path, "wb") as f:
                f.write(b"%PDF-1.5\n%Test PDF file for OCR Manager tests")

    def tearDown(self):
        """Clean up after tests."""
        # Remove test output files
        for file in self.test_output_dir.glob("*.md"):
            file.unlink(missing_ok=True)

    @patch("requests.post")
    def test_convert_pdf_to_markdown_success(self, mock_post):
        """Test successful PDF to Markdown conversion."""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Test Markdown\n\nThis is a test."
        mock_post.return_value = mock_response

        # Call the method
        result = self.ocr_manager.convert_pdf_to_markdown(
            self.test_pdf_path, self.test_output_dir
        )

        # Check that the API was called with the correct parameters
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(
            call_args[1]["headers"]["Authorization"], f"Bearer {self.api_key}"
        )
        self.assertEqual(call_args[1]["headers"]["Accept"], "text/markdown")
        self.assertIn("files", call_args[1])
        self.assertIn("file", call_args[1]["files"])

        # Check that the result is correct
        self.assertEqual(result, self.test_output_dir / f"{self.test_pdf_path.stem}.md")
        self.assertTrue(result.exists())

        # Check the content of the output file
        with open(result, encoding="utf-8") as f:
            content = f.read()
            self.assertEqual(content, "# Test Markdown\n\nThis is a test.")

    @patch("requests.post")
    def test_convert_pdf_to_markdown_api_error(self, mock_post):
        """Test handling of API errors."""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        # Call the method and check that it raises an OCRError
        with self.assertRaises(OCRError):
            self.ocr_manager.convert_pdf_to_markdown(
                self.test_pdf_path, self.test_output_dir
            )

    @patch("requests.post")
    def test_convert_pdf_to_markdown_request_exception(self, mock_post):
        """Test handling of request exceptions."""
        # Mock the API response to raise an exception
        mock_post.side_effect = requests.exceptions.RequestException("Connection error")

        # Call the method and check that it raises an OCRError
        with self.assertRaises(OCRError):
            self.ocr_manager.convert_pdf_to_markdown(
                self.test_pdf_path, self.test_output_dir
            )

    def test_convert_pdf_to_markdown_file_not_found(self):
        """Test handling of file not found errors."""
        # Call the method with a non-existent file and check that it raises
        # a FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            self.ocr_manager.convert_pdf_to_markdown(
                Path("non_existent.pdf"), self.test_output_dir
            )

    @patch("requests.post")
    def test_convert_pdf_to_markdown_default_output(self, mock_post):
        """Test conversion with default output directory."""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Test Markdown\n\nThis is a test."
        mock_post.return_value = mock_response

        # Call the method with no output directory
        result = self.ocr_manager.convert_pdf_to_markdown(self.test_pdf_path)

        # Check that the result is correct
        expected_path = self.test_pdf_path.with_suffix(".md")
        self.assertEqual(result, expected_path)
        self.assertTrue(result.exists())

        # Clean up
        result.unlink(missing_ok=True)

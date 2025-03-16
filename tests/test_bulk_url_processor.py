"""
Tests for the Bulk URL Processor module.
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.thoth.uri.bulk_url_processor import BulkURLProcessor


class TestBulkURLProcessor(unittest.TestCase):
    """
    Test cases for the BulkURLProcessor class.
    """

    def setUp(self):
        """
        Set up test environment.
        """
        # Create a temporary directory for test PDFs
        self.temp_dir = tempfile.mkdtemp()
        self.processor = BulkURLProcessor(pdf_dir=self.temp_dir)

    def tearDown(self):
        """
        Clean up test environment.
        """
        # Remove temporary directory and its contents
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_generate_filename_from_url(self):
        """
        Test generating filenames from URLs.
        """
        # Test with PDF URL
        url1 = "https://example.com/papers/test-paper.pdf"
        filename1 = self.processor._generate_filename_from_url(url1)
        self.assertEqual(filename1, "test-paper.pdf")

        # Test with non-PDF URL
        url2 = "https://example.com/papers/view?id=123"
        filename2 = self.processor._generate_filename_from_url(url2)
        self.assertEqual(filename2, "example_com_papers-view-id-123.pdf")

    def test_process_url_file(self):
        """
        Test processing a URL file.
        """
        # Create a temporary URL file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("https://example.com/paper1.pdf\n")
            f.write("https://example.com/paper2.pdf\n")
            f.write("\n")  # Empty line
            f.write("# Comment line\n")
            f.write("https://example.com/paper3.pdf\n")
            url_file_path = f.name

        try:
            # Mock the download_pdfs method
            with patch.object(self.processor, 'download_pdfs') as mock_download:
                mock_download.return_value = (["path1", "path2", "path3"], [])

                # Call the method
                successful, failed = self.processor.process_url_file(url_file_path)

                # Check that download_pdfs was called with the correct URLs
                mock_download.assert_called_once()
                called_urls = mock_download.call_args[0][0]
                self.assertEqual(len(called_urls), 3)
                self.assertEqual(called_urls[0], "https://example.com/paper1.pdf")
                self.assertEqual(called_urls[1], "https://example.com/paper2.pdf")
                self.assertEqual(called_urls[2], "https://example.com/paper3.pdf")

                # Check the return values
                self.assertEqual(successful, ["path1", "path2", "path3"])
                self.assertEqual(failed, [])
        finally:
            # Clean up the temporary file
            os.unlink(url_file_path)

    @patch('requests.get')
    def test_download_pdf(self, mock_get):
        """
        Test downloading a PDF.
        """
        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/pdf'}
        mock_response.iter_content.return_value = [b'PDF content']
        mock_get.return_value = mock_response

        # Call the method
        url = "https://example.com/test.pdf"
        result = self.processor._download_pdf(url)

        # Check that requests.get was called with the correct URL
        mock_get.assert_called_once_with(url, timeout=60, stream=True)

        # Check that the file was created
        self.assertIsNotNone(result)
        self.assertTrue(os.path.exists(result))

        # Check the file content
        with open(result, 'rb') as f:
            content = f.read()
            self.assertEqual(content, b'PDF content')


if __name__ == '__main__':
    unittest.main()

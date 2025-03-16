"""
Tests for the URI handler module.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thoth.config import ThothConfig
from thoth.uri.handler import URIHandler, process_uri


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = MagicMock(spec=ThothConfig)
    config.pdf_dir = Path("/tmp/thoth/pdfs")
    return config


class TestURIHandler:
    """Tests for the URIHandler class."""

    def test_init(self, mock_config):
        """Test initialization of URIHandler."""
        handler = URIHandler(mock_config)
        assert handler.config == mock_config
        assert handler.pdf_dir == mock_config.pdf_dir

    def test_process_uri_not_thoth(self, mock_config):
        """Test processing a non-Thoth URI."""
        handler = URIHandler(mock_config)
        result = handler.process_uri("http://example.com")
        assert result is False

    @patch("thoth.uri.handler.download_citation")
    def test_process_uri_doi(self, mock_download, mock_config):
        """Test processing a DOI URI."""
        # Set up the mock to return a Path
        mock_download.return_value = Path("/tmp/thoth/pdfs/paper.pdf")

        # Create the handler and process a DOI URI
        handler = URIHandler(mock_config)
        result = handler.process_uri("thoth://doi:10.1234/5678")

        # Check that the result is True and download_citation was called
        assert result is True
        mock_download.assert_called_once()

        # Check that the DOI was extracted correctly
        args, kwargs = mock_download.call_args
        citation = args[0]
        assert citation.doi == "10.1234/5678"

    @patch("thoth.uri.handler.download_citation")
    def test_process_uri_url(self, mock_download, mock_config):
        """Test processing a URL URI."""
        # Set up the mock to return a Path
        mock_download.return_value = Path("/tmp/thoth/pdfs/paper.pdf")

        # Create the handler and process a URL URI
        handler = URIHandler(mock_config)
        result = handler.process_uri("thoth://url:https://example.com/paper.pdf")

        # Check that the result is True and download_citation was called
        assert result is True
        mock_download.assert_called_once()

        # Check that the URL was extracted correctly
        args, kwargs = mock_download.call_args
        citation = args[0]
        assert citation.url == "https://example.com/paper.pdf"

    @patch("thoth.uri.handler.download_citation")
    def test_process_uri_invalid_format(self, mock_download, mock_config):
        """Test processing a URI with an invalid format."""
        handler = URIHandler(mock_config)
        result = handler.process_uri("thoth://invalid")

        # Check that the result is False and download_citation was not called
        assert result is False
        mock_download.assert_not_called()

    @patch("thoth.uri.handler.download_citation")
    def test_process_uri_download_failure(self, mock_download, mock_config):
        """Test processing a URI when download fails."""
        # Set up the mock to return None (download failure)
        mock_download.return_value = None

        # Create the handler and process a DOI URI
        handler = URIHandler(mock_config)
        result = handler.process_uri("thoth://doi:10.1234/5678")

        # Check that the result is False
        assert result is False
        mock_download.assert_called_once()

    @patch("thoth.uri.handler.download_citation")
    def test_process_uri_exception(self, mock_download, mock_config):
        """Test processing a URI when an exception occurs."""
        # Set up the mock to raise an exception
        mock_download.side_effect = Exception("Test exception")

        # Create the handler and process a DOI URI
        handler = URIHandler(mock_config)
        result = handler.process_uri("thoth://doi:10.1234/5678")

        # Check that the result is False
        assert result is False
        mock_download.assert_called_once()


@patch("thoth.uri.handler.URIHandler")
def test_process_uri_function(mock_handler_class, mock_config):
    """Test the process_uri function."""
    # Set up the mock
    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler
    mock_handler.process_uri.return_value = True

    # Call the function
    result = process_uri("thoth://doi:10.1234/5678", mock_config)

    # Check that the result is True and the handler was created and used
    assert result is True
    mock_handler_class.assert_called_once_with(mock_config)
    mock_handler.process_uri.assert_called_once_with("thoth://doi:10.1234/5678")

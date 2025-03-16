"""
Tests for the Citation Downloader module.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from thoth.citation.citation import Citation
from thoth.citation.downloader import (
    CitationDownloader,
    CitationDownloadError,
    download_citation,
)


class TestCitationDownloader:
    """Tests for the CitationDownloader class."""

    @pytest.fixture
    def downloader(self, tmp_path):
        """Create a CitationDownloader instance for testing."""
        return CitationDownloader(tmp_path)

    @pytest.fixture
    def sample_citation(self):
        """Create a sample citation for testing."""
        return Citation(
            title="Sample Paper",
            authors=["J. Smith", "A. Jones"],
            year=2023,
            doi="10.1234/5678",
            url="https://example.com/paper",
        )

    @pytest.fixture
    def doi_citation(self):
        """Create a citation with only DOI for testing."""
        return Citation(
            title="DOI Paper",
            authors=["J. Smith"],
            year=2023,
            doi="10.1234/5678",
        )

    @pytest.fixture
    def url_citation(self):
        """Create a citation with only URL for testing."""
        return Citation(
            title="URL Paper",
            authors=["A. Jones"],
            year=2023,
            url="https://example.com/paper",
        )

    @pytest.fixture
    def minimal_citation(self):
        """Create a minimal citation for testing."""
        return Citation(
            title="Minimal Paper",
            authors=["J. Smith"],
        )

    def test_init(self, downloader, tmp_path):
        """Test initialization of CitationDownloader."""
        assert downloader.output_dir == tmp_path
        assert tmp_path.exists()

    @patch("thoth.citation.downloader.CitationDownloader._download_from_doi")
    def test_download_citation_with_doi(
        self, mock_download_doi, downloader, doi_citation
    ):
        """Test downloading a citation with DOI."""
        # Mock the _download_from_doi method
        expected_path = Path("/path/to/pdf.pdf")
        mock_download_doi.return_value = expected_path

        # Call the method
        result = downloader.download_citation(doi_citation)

        # Check that _download_from_doi was called with the correct arguments
        mock_download_doi.assert_called_once_with(doi_citation.doi, doi_citation.title)
        assert result == expected_path

    @patch("thoth.citation.downloader.CitationDownloader._download_from_url")
    def test_download_citation_with_url(
        self, mock_download_url, downloader, url_citation
    ):
        """Test downloading a citation with URL."""
        # Mock the _download_from_url method
        expected_path = Path("/path/to/pdf.pdf")
        mock_download_url.return_value = expected_path

        # Call the method
        result = downloader.download_citation(url_citation)

        # Check that _download_from_url was called with the correct arguments
        mock_download_url.assert_called_once_with(url_citation.url, url_citation.title)
        assert result == expected_path

    @patch("thoth.citation.downloader.CitationDownloader._search_and_download")
    def test_download_citation_with_search(
        self, mock_search, downloader, minimal_citation
    ):
        """Test downloading a citation with search."""
        # Mock the _search_and_download method
        expected_path = Path("/path/to/pdf.pdf")
        mock_search.return_value = expected_path

        # Call the method
        result = downloader.download_citation(minimal_citation)

        # Check that _search_and_download was called with the correct arguments
        mock_search.assert_called_once_with(minimal_citation)
        assert result == expected_path

    @patch("thoth.citation.downloader.CitationDownloader._download_from_doi")
    @patch("thoth.citation.downloader.CitationDownloader._download_from_url")
    def test_download_citation_fallback(
        self, mock_download_url, mock_download_doi, downloader, sample_citation
    ):
        """Test fallback from DOI to URL if DOI download fails."""
        # Mock the _download_from_doi method to return None (failure)
        mock_download_doi.return_value = None

        # Mock the _download_from_url method
        expected_path = Path("/path/to/pdf.pdf")
        mock_download_url.return_value = expected_path

        # Call the method
        result = downloader.download_citation(sample_citation)

        # Check that both methods were called with the correct arguments
        mock_download_doi.assert_called_once_with(
            sample_citation.doi, sample_citation.title
        )
        mock_download_url.assert_called_once_with(
            sample_citation.url, sample_citation.title
        )
        assert result == expected_path

    @patch("thoth.citation.downloader.requests.head")
    @patch("thoth.citation.downloader.requests.get")
    @patch("thoth.citation.downloader.CitationDownloader._download_pdf")
    def test_download_from_doi_direct_pdf(
        self, mock_download_pdf, mock_get, mock_head, downloader
    ):
        """Test downloading from DOI when the DOI resolves to a direct PDF."""
        # Mock the requests.head response
        mock_head_response = MagicMock()
        mock_head_response.url = "https://example.com/paper.pdf"
        mock_head.return_value = mock_head_response

        # Mock the _download_pdf method
        expected_path = Path("/path/to/pdf.pdf")
        mock_download_pdf.return_value = expected_path

        # Call the method
        result = downloader._download_from_doi("10.1234/5678", "Sample Paper")

        # Check that the correct methods were called
        mock_head.assert_called_once()
        mock_download_pdf.assert_called_once_with(
            "https://example.com/paper.pdf", "Sample Paper"
        )
        mock_get.assert_not_called()  # Should not be called for direct PDF
        assert result == expected_path

    @patch("thoth.citation.downloader.requests.head")
    @patch("thoth.citation.downloader.requests.get")
    @patch("thoth.citation.downloader.CitationDownloader._download_pdf")
    def test_download_from_doi_landing_page(
        self, mock_download_pdf, mock_get, mock_head, downloader
    ):
        """Test downloading from DOI when the DOI resolves to a landing page."""
        # Mock the requests.head response
        mock_head_response = MagicMock()
        mock_head_response.url = "https://example.com/paper"
        mock_head.return_value = mock_head_response

        # Mock the requests.get response
        mock_get_response = MagicMock()
        mock_get_response.text = '<a href="paper.pdf">PDF</a>'
        mock_get.return_value = mock_get_response

        # Mock the _download_pdf method
        expected_path = Path("/path/to/pdf.pdf")
        mock_download_pdf.return_value = expected_path

        # Call the method
        result = downloader._download_from_doi("10.1234/5678", "Sample Paper")

        # Check that the correct methods were called
        mock_head.assert_called_once()
        mock_get.assert_called_once()
        mock_download_pdf.assert_called_once_with(
            "https://example.com/paper.pdf", "Sample Paper"
        )
        assert result == expected_path

    @patch("thoth.citation.downloader.requests.head")
    def test_download_from_doi_error(self, mock_head, downloader):
        """Test handling of errors when downloading from DOI."""
        # Mock the requests.head method to raise an exception
        mock_head.side_effect = requests.exceptions.RequestException("Connection error")

        # Call the method
        result = downloader._download_from_doi("10.1234/5678", "Sample Paper")

        # Check that the result is None
        assert result is None

    @patch("thoth.citation.downloader.requests.get")
    @patch("thoth.citation.downloader.CitationDownloader._download_pdf")
    def test_download_from_url_direct_pdf(
        self, mock_download_pdf, mock_get, downloader
    ):
        """Test downloading from URL when the URL is a direct PDF."""
        # Mock the _download_pdf method
        expected_path = Path("/path/to/pdf.pdf")
        mock_download_pdf.return_value = expected_path

        # Call the method
        result = downloader._download_from_url(
            "https://example.com/paper.pdf", "Sample Paper"
        )

        # Check that the correct methods were called
        mock_download_pdf.assert_called_once_with(
            "https://example.com/paper.pdf", "Sample Paper"
        )
        mock_get.assert_not_called()  # Should not be called for direct PDF
        assert result == expected_path

    @patch("thoth.citation.downloader.requests.get")
    @patch("thoth.citation.downloader.CitationDownloader._download_pdf")
    def test_download_from_url_landing_page(
        self, mock_download_pdf, mock_get, downloader
    ):
        """Test downloading from URL when the URL is a landing page."""
        # Mock the requests.get response
        mock_get_response = MagicMock()
        mock_get_response.text = '<a href="paper.pdf">PDF</a>'
        mock_get.return_value = mock_get_response

        # Mock the _download_pdf method
        expected_path = Path("/path/to/pdf.pdf")
        mock_download_pdf.return_value = expected_path

        # Call the method
        result = downloader._download_from_url(
            "https://example.com/paper", "Sample Paper"
        )

        # Check that the correct methods were called
        mock_get.assert_called_once()
        mock_download_pdf.assert_called_once_with(
            "https://example.com/paper.pdf", "Sample Paper"
        )
        assert result == expected_path

    @patch("thoth.citation.downloader.requests.get")
    def test_download_from_url_error(self, mock_get, downloader):
        """Test handling of errors when downloading from URL."""
        # Mock the requests.get method to raise an exception
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        # Call the method
        result = downloader._download_from_url(
            "https://example.com/paper", "Sample Paper"
        )

        # Check that the result is None
        assert result is None

    @patch("thoth.citation.downloader.requests.get")
    @patch("thoth.citation.downloader.CitationDownloader._download_pdf")
    def test_search_and_download(
        self, mock_download_pdf, mock_get, downloader, minimal_citation
    ):
        """Test searching for and downloading a paper."""
        # Mock the first requests.get response (search)
        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = {"data": [{"paperId": "abcd1234"}]}

        # Mock the second requests.get response (paper details)
        mock_paper_response = MagicMock()
        mock_paper_response.status_code = 200
        mock_paper_response.json.return_value = {
            "openAccessPdf": {"url": "https://example.com/paper.pdf"}
        }

        # Set up the side effect to return different responses for different calls
        mock_get.side_effect = [mock_search_response, mock_paper_response]

        # Mock the _download_pdf method
        expected_path = Path("/path/to/pdf.pdf")
        mock_download_pdf.return_value = expected_path

        # Call the method
        result = downloader._search_and_download(minimal_citation)

        # Check that the correct methods were called
        assert mock_get.call_count == 2
        mock_download_pdf.assert_called_once_with(
            "https://example.com/paper.pdf", minimal_citation.title
        )
        assert result == expected_path

    @patch("thoth.citation.downloader.requests.get")
    def test_search_and_download_no_results(
        self, mock_get, downloader, minimal_citation
    ):
        """Test searching for a paper with no results."""
        # Mock the requests.get response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        # Call the method
        result = downloader._search_and_download(minimal_citation)

        # Check that the result is None
        assert result is None

    @patch("thoth.citation.downloader.requests.get")
    def test_download_pdf(self, mock_get, downloader, tmp_path):
        """Test downloading a PDF."""
        # Mock the requests.get response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.iter_content.return_value = [b"PDF content"]
        mock_get.return_value = mock_response

        # Call the method
        result = downloader._download_pdf(
            "https://example.com/paper.pdf", "Sample Paper"
        )

        # Check that the correct methods were called
        mock_get.assert_called_once()
        assert result.exists()
        assert result.suffix == ".pdf"
        assert result.parent == tmp_path

        # Check the content of the file
        with open(result, "rb") as f:
            content = f.read()
            assert content == b"PDF content"

    @patch("thoth.citation.downloader.requests.get")
    def test_download_pdf_error(self, mock_get, downloader):
        """Test handling of errors when downloading a PDF."""
        # Mock the requests.get method to return an error
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        # Call the method and check that it raises a CitationDownloadError
        with pytest.raises(CitationDownloadError):
            downloader._download_pdf("https://example.com/paper.pdf", "Sample Paper")

    @patch("thoth.citation.downloader.requests.get")
    def test_download_pdf_not_pdf(self, mock_get, downloader):
        """Test handling of non-PDF content."""
        # Mock the requests.get method to return non-PDF content
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_get.return_value = mock_response

        # Call the method and check that it raises a CitationDownloadError
        with pytest.raises(CitationDownloadError):
            downloader._download_pdf("https://example.com/paper", "Sample Paper")

    @patch("thoth.citation.downloader.CitationDownloader")
    def test_convenience_function(
        self, mock_downloader_class, sample_citation, tmp_path
    ):
        """Test the convenience function."""
        # Mock the CitationDownloader class
        mock_downloader = MagicMock()
        mock_downloader.download_citation.return_value = Path("/path/to/pdf.pdf")
        mock_downloader_class.return_value = mock_downloader

        # Call the function
        result = download_citation(sample_citation, tmp_path)

        # Check that the correct methods were called
        mock_downloader_class.assert_called_once_with(tmp_path)
        mock_downloader.download_citation.assert_called_once_with(sample_citation)
        assert result == Path("/path/to/pdf.pdf")

"""
Tests for the PDF locator service.
"""

from unittest.mock import Mock, patch

import pytest

from thoth.services.pdf_locator_service import PdfLocation, PdfLocatorService
from thoth.utilities.config import ThothConfig


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = Mock(spec=ThothConfig)
    config.api_keys = Mock()
    config.api_keys.unpaywall_email = 'test@example.com'
    config.api_keys.semanticscholar_api_key = 'test-key'
    return config


@pytest.fixture
def pdf_locator(mock_config):
    """Create a PdfLocatorService instance."""
    return PdfLocatorService(config=mock_config)


class TestPdfLocatorService:
    """Test cases for PdfLocatorService."""

    def test_initialization(self, pdf_locator, mock_config):  # noqa: ARG002
        """Test service initialization."""
        assert pdf_locator.email == 'test@example.com'
        assert pdf_locator.user_agent == 'Thoth/0.3 (+mailto:test@example.com)'

    def test_initialization_without_email(self, mock_config):
        """Test service initialization without email."""
        mock_config.api_keys.unpaywall_email = None
        service = PdfLocatorService(config=mock_config)
        assert service.email is None
        assert service.user_agent == 'Thoth/0.3'

    @patch('requests.Session.get')
    def test_from_crossref_success(self, mock_get, pdf_locator):
        """Test successful PDF location from Crossref."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'link': [
                    {
                        'URL': 'https://example.com/paper.pdf',
                        'content-type': 'application/pdf',
                    }
                ],
                'license': [{'URL': 'https://creativecommons.org/licenses/by/4.0/'}],
            }
        }
        mock_get.return_value = mock_response

        result = pdf_locator._from_crossref('10.1234/test')

        assert result is not None
        assert result.url == 'https://example.com/paper.pdf'
        assert result.source == 'crossref'
        assert result.licence == 'cc-by'
        assert result.is_oa is True

    @patch('requests.Session.get')
    def test_from_crossref_no_pdf(self, mock_get, pdf_locator):
        """Test Crossref response with no PDF link."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'link': [
                    {
                        'URL': 'https://example.com/abstract',
                        'content-type': 'text/html',
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        result = pdf_locator._from_crossref('10.1234/test')
        assert result is None

    @patch('requests.Session.get')
    def test_from_unpaywall_success(self, mock_get, pdf_locator):
        """Test successful PDF location from Unpaywall."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'is_oa': True,
            'best_oa_location': {
                'url_for_pdf': 'https://repository.edu/paper.pdf',
                'license': 'cc-by-nc',
            },
        }
        mock_get.return_value = mock_response

        result = pdf_locator._from_unpaywall('10.1234/test')

        assert result is not None
        assert result.url == 'https://repository.edu/paper.pdf'
        assert result.source == 'unpaywall'
        assert result.licence == 'cc-by-nc'
        assert result.is_oa is True

    @patch('requests.Session.get')
    def test_from_unpaywall_not_oa(self, mock_get, pdf_locator):
        """Test Unpaywall response for non-OA article."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'is_oa': False}
        mock_get.return_value = mock_response

        result = pdf_locator._from_unpaywall('10.1234/test')
        assert result is None

    def test_from_arxiv_with_arxiv_id(self, pdf_locator):
        """Test arXiv PDF location with arXiv ID."""
        result = pdf_locator._from_arxiv(None, '1706.03762')

        assert result is not None
        assert result.url == 'https://arxiv.org/pdf/1706.03762.pdf'
        assert result.source == 'arxiv'
        assert result.licence == 'arXiv'
        assert result.is_oa is True

    def test_from_arxiv_with_doi(self, pdf_locator):
        """Test arXiv PDF location with DOI."""
        result = pdf_locator._from_arxiv('10.48550/arXiv.1706.03762', None)

        assert result is not None
        assert result.url == 'https://arxiv.org/pdf/1706.03762.pdf'
        assert result.source == 'arxiv'

    def test_from_arxiv_no_id(self, pdf_locator):
        """Test arXiv with no valid ID."""
        result = pdf_locator._from_arxiv('10.1234/other', None)
        assert result is None

    @patch('requests.Session.get')
    def test_from_semanticscholar_success(self, mock_get, pdf_locator):
        """Test successful PDF location from Semantic Scholar."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'openAccessPdf': {'url': 'https://pdfs.semanticscholar.org/paper.pdf'}
        }
        mock_get.return_value = mock_response

        result = pdf_locator._from_semanticscholar('10.1234/test')

        assert result is not None
        assert result.url == 'https://pdfs.semanticscholar.org/paper.pdf'
        assert result.source == 's2'
        assert result.is_oa is True

    @patch('requests.head')
    def test_from_doi_head_success(self, mock_head, pdf_locator):
        """Test successful PDF location via DOI HEAD."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_response.url = 'https://publisher.com/paper.pdf'
        mock_head.return_value = mock_response

        result = pdf_locator._from_doi_head('10.1234/test')

        assert result is not None
        assert result.url == 'https://publisher.com/paper.pdf'
        assert result.source == 'doi-head'
        assert result.is_oa is False  # Might be paywalled

    @patch('requests.head')
    def test_from_doi_head_not_pdf(self, mock_head, pdf_locator):
        """Test DOI HEAD when response is not PDF."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/html'}
        mock_head.return_value = mock_response

        result = pdf_locator._from_doi_head('10.1234/test')
        assert result is None

    def test_doi_to_arxiv_valid(self, pdf_locator):
        """Test DOI to arXiv ID extraction."""
        doi = '10.48550/arXiv.1706.03762'
        result = pdf_locator._doi_to_arxiv(doi)
        assert result == '1706.03762'

    def test_doi_to_arxiv_invalid(self, pdf_locator):
        """Test DOI to arXiv ID extraction with non-arXiv DOI."""
        doi = '10.1038/nature12373'
        result = pdf_locator._doi_to_arxiv(doi)
        assert result is None

    def test_extract_license_cc_by(self, pdf_locator):
        """Test license extraction for CC-BY."""
        message = {'license': [{'URL': 'https://creativecommons.org/licenses/by/4.0/'}]}
        result = pdf_locator._extract_license(message)
        assert result == 'cc-by'

    def test_extract_license_cc_by_nc(self, pdf_locator):
        """Test license extraction for CC-BY-NC."""
        message = {
            'license': [{'URL': 'https://creativecommons.org/licenses/by-nc/4.0/'}]
        }
        result = pdf_locator._extract_license(message)
        assert result == 'cc-by-nc'

    def test_extract_license_none(self, pdf_locator):
        """Test license extraction with no license."""
        message = {}
        result = pdf_locator._extract_license(message)
        assert result is None

    @patch.object(PdfLocatorService, '_from_crossref')
    @patch.object(PdfLocatorService, '_from_unpaywall')
    @patch.object(PdfLocatorService, '_from_arxiv')
    @patch.object(PdfLocatorService, '_from_semanticscholar')
    @patch.object(PdfLocatorService, '_from_doi_head')
    def test_locate_chain_first_success(
        self,
        mock_doi_head,
        mock_s2,
        mock_arxiv,
        mock_unpaywall,
        mock_crossref,
        pdf_locator,
    ):
        """Test locate method returns first successful result."""
        # Mock crossref to return a result
        expected_result = PdfLocation(
            url='https://example.com/paper.pdf',
            source='crossref',
            licence='cc-by',
            is_oa=True,
        )
        mock_crossref.return_value = expected_result

        # Others should not be called
        mock_unpaywall.return_value = None
        mock_arxiv.return_value = None
        mock_s2.return_value = None
        mock_doi_head.return_value = None

        result = pdf_locator.locate(doi='10.1234/test')

        assert result == expected_result
        mock_crossref.assert_called_once_with('10.1234/test')
        # Since crossref returned a result, others shouldn't be called
        mock_unpaywall.assert_not_called()
        mock_arxiv.assert_not_called()
        mock_s2.assert_not_called()
        mock_doi_head.assert_not_called()

    @patch.object(PdfLocatorService, '_from_crossref')
    @patch.object(PdfLocatorService, '_from_unpaywall')
    def test_locate_chain_fallback(self, mock_unpaywall, mock_crossref, pdf_locator):
        """Test locate method falls back to next source."""
        # Mock crossref to return None
        mock_crossref.return_value = None

        # Mock unpaywall to return a result
        expected_result = PdfLocation(
            url='https://repository.edu/paper.pdf',
            source='unpaywall',
            licence='cc-by',
            is_oa=True,
        )
        mock_unpaywall.return_value = expected_result

        result = pdf_locator.locate(doi='10.1234/test')

        assert result == expected_result
        mock_crossref.assert_called_once_with('10.1234/test')
        mock_unpaywall.assert_called_once_with('10.1234/test')

    def test_locate_no_identifiers(self, pdf_locator):
        """Test locate method with no identifiers raises error."""
        with pytest.raises(Exception) as exc_info:
            pdf_locator.locate()
        assert 'Either DOI or arXiv ID must be provided' in str(exc_info.value)

    @patch('requests.Session.get')
    def test_get_json_retry_logic(self, mock_get, pdf_locator):
        """Test _get_json retry logic."""
        # First three attempts fail, fourth succeeds
        mock_get.side_effect = [
            Mock(status_code=500),
            Mock(status_code=502),
            Mock(status_code=503),
            Mock(status_code=200),
        ]

        result = pdf_locator._get_json('https://example.com/test')

        assert result is not None
        assert result.status_code == 200
        assert mock_get.call_count == 4

    @patch('requests.Session.get')
    @patch('time.sleep')
    def test_get_json_all_attempts_fail(self, mock_sleep, mock_get, pdf_locator):
        """Test _get_json when all attempts fail."""
        mock_get.return_value = Mock(status_code=500)

        result = pdf_locator._get_json('https://example.com/test')

        assert result is None
        assert mock_get.call_count == 4
        # Check that sleep was called with correct delays
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(3)
        mock_sleep.assert_any_call(7)

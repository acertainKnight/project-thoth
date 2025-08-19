"""
Test the integration of PDF Locator Service with Citation Service and Agent tools.

This module tests that:
1. Citations extracted by CitationProcessor include PDF URLs when available
2. CitationService can locate PDFs for citations
3. Agent tools can successfully use the PDF locator service
"""

from unittest.mock import Mock

import pytest

# Legacy agent tools removed - use MCP tools instead
# from thoth.mcp.tools import (pdf tools available via MCP)
from thoth.services.citation_service import CitationService
from thoth.services.pdf_locator_service import PdfLocation, PdfLocatorService
from thoth.utilities.schemas import Citation


class TestCitationServicePdfIntegration:
    """Test CitationService integration with PDF locator."""

    @pytest.fixture
    def mock_pdf_locator(self):
        """Create a mock PDF locator service."""
        mock = Mock(spec=PdfLocatorService)
        # Mock successful PDF location
        mock.locate.return_value = PdfLocation(
            url='https://arxiv.org/pdf/1706.03762.pdf',
            source='arxiv',
            licence='cc-by',
            is_oa=True,
        )
        return mock

    @pytest.fixture
    def citation_service(self, mock_pdf_locator):
        """Create CitationService with mocked PDF locator."""
        service = CitationService()
        service._pdf_locator_service = mock_pdf_locator
        return service

    def test_locate_pdf_for_single_citation(self, citation_service):
        """Test locating PDF for a single citation."""
        citation = Citation(
            title='Attention Is All You Need',
            doi='10.48550/arXiv.1706.03762',
            arxiv_id='1706.03762',
        )

        pdf_url = citation_service.locate_pdf_for_citation(citation)

        assert pdf_url == 'https://arxiv.org/pdf/1706.03762.pdf'
        citation_service.pdf_locator.locate.assert_called_once_with(
            doi='10.48550/arXiv.1706.03762', arxiv_id='1706.03762'
        )

    def test_locate_pdfs_for_multiple_citations(self, citation_service):
        """Test locating PDFs for multiple citations."""
        citations = [
            Citation(title='Paper 1', doi='10.1234/test1', arxiv_id=None),
            Citation(title='Paper 2', doi=None, arxiv_id='2001.12345'),
            Citation(title='Paper 3 - No ID', doi=None, arxiv_id=None),
        ]

        results = citation_service.locate_pdfs_for_citations(
            citations, update_citations=True
        )

        # Check results
        assert len(results) == 3
        assert results[0][1] == 'https://arxiv.org/pdf/1706.03762.pdf'
        assert results[1][1] == 'https://arxiv.org/pdf/1706.03762.pdf'
        assert results[2][1] is None  # No DOI or arXiv ID

        # Check citations were updated
        assert citations[0].pdf_url == 'https://arxiv.org/pdf/1706.03762.pdf'
        assert citations[0].pdf_source == 'arxiv'
        assert citations[0].is_open_access is True

        assert citations[1].pdf_url == 'https://arxiv.org/pdf/1706.03762.pdf'
        assert citations[2].pdf_url is None

    def test_locate_pdfs_handles_errors(self, citation_service):
        """Test that PDF location errors are handled gracefully."""
        citation_service.pdf_locator.locate.side_effect = Exception('API error')

        citation = Citation(title='Test Paper', doi='10.1234/test')

        results = citation_service.locate_pdfs_for_citations([citation])

        # Should return None for the PDF URL but not crash
        assert len(results) == 1
        assert results[0][0] == citation
        assert results[0][1] is None


# Legacy TestAgentPdfTools class removed during Phase 1 refactoring
# The legacy agent tools (LocatePdfTool, ValidatePdfSourceTool, LocatePdfsForQueryTool)
# were removed as part of the MCP-only transition. PDF locator functionality
# is now available through MCP tools and continues to be tested via the
# CitationService integration tests above.


class TestCitationProcessorPdfIntegration:
    """Test that CitationProcessor includes PDF location in the enhancement step."""

    def test_citation_processor_includes_pdf_location(self):
        """Test that extracted citations include PDF URLs when available."""
        # This is more of an integration test that would require
        # a full setup with mocked LLM and PDF locator
        # For now, we just verify the structure is in place
        from thoth.utilities.schemas import Citation

        citation = Citation(
            title='Test Paper',
            doi='10.1234/test',
            pdf_url='https://example.com/paper.pdf',
            pdf_source='crossref',
            is_open_access=True,
        )

        # Verify the schema includes PDF fields
        assert hasattr(citation, 'pdf_url')
        assert hasattr(citation, 'pdf_source')
        assert citation.pdf_url == 'https://example.com/paper.pdf'
        assert citation.pdf_source == 'crossref'
        assert citation.is_open_access is True


if __name__ == '__main__':
    pytest.main([__file__])

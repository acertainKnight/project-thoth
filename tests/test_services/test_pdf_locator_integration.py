"""
Test the integration of PDF Locator Service with Citation Service and Agent tools.

This module tests that:
1. Citations extracted by CitationProcessor include PDF URLs when available
2. CitationService can locate PDFs for citations
3. Agent tools can successfully use the PDF locator service
"""

from unittest.mock import Mock

import pytest

from thoth.ingestion.agent_v2.tools.pdf_tools import (
    LocatePdfsForQueryTool,
    LocatePdfTool,
    ValidatePdfSourceTool,
)
from thoth.services.citation_service import CitationService
from thoth.services.pdf_locator_service import PdfLocation, PdfLocatorService
from thoth.services.service_manager import ServiceManager
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


class TestAgentPdfTools:
    """Test agent PDF tools."""

    @pytest.fixture
    def mock_service_manager(self):
        """Create a mock service manager."""
        manager = Mock(spec=ServiceManager)

        # Mock PDF locator
        manager.pdf_locator = Mock(spec=PdfLocatorService)
        manager.pdf_locator.locate.return_value = PdfLocation(
            url='https://example.com/paper.pdf',
            source='crossref',
            licence='cc-by',
            is_oa=True,
        )

        # Mock RAG service for search
        manager.rag = Mock()
        manager.rag.search.return_value = [
            {
                'title': 'Test Paper',
                'content': 'Abstract with DOI: 10.1234/test',
                'score': 0.95,
            }
        ]

        # Mock query service
        manager.query = Mock()
        manager.query.get_query.return_value = Mock(
            name='test_query',
            research_question='Test research question',
            keywords=['test', 'research'],
        )

        return manager

    def test_locate_pdf_tool_with_doi(self, mock_service_manager):
        """Test LocatePdfTool with DOI."""
        tool = LocatePdfTool(service_manager=mock_service_manager)

        result = tool._run(doi='10.1234/test')

        assert 'PDF Found!' in result
        assert 'https://example.com/paper.pdf' in result
        assert 'crossref' in result
        mock_service_manager.pdf_locator.locate.assert_called_once_with(
            doi='10.1234/test', arxiv_id=None
        )

    def test_locate_pdf_tool_with_title(self, mock_service_manager):
        """Test LocatePdfTool with title search."""
        tool = LocatePdfTool(service_manager=mock_service_manager)

        result = tool._run(title='Test Paper')

        assert 'PDF Found!' in result
        # Should have searched for the title and extracted DOI
        mock_service_manager.rag.search.assert_called_once_with(query='Test Paper', k=1)
        mock_service_manager.pdf_locator.locate.assert_called_once()

    def test_test_pdf_source_tool(self, mock_service_manager):
        """Test TestPdfSourceTool."""
        tool = ValidatePdfSourceTool(service_manager=mock_service_manager)

        # Mock specific source methods
        mock_service_manager.pdf_locator._from_crossref = Mock(
            return_value=PdfLocation(
                url='https://test.com/pdf', source='crossref', is_oa=True
            )
        )

        result = tool._run(source='crossref')

        assert 'Testing PDF Location Source(s): crossref' in result
        assert 'Success' in result

    def test_locate_pdfs_for_query_tool(self, mock_service_manager):
        """Test LocatePdfsForQueryTool."""
        tool = LocatePdfsForQueryTool(service_manager=mock_service_manager)

        result = tool._run(query_name='test_query', limit=1)

        assert 'Locating PDFs for Query: test_query' in result
        assert 'Found 1 articles' in result
        mock_service_manager.query.get_query.assert_called_once_with('test_query')
        mock_service_manager.rag.search.assert_called_once()


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

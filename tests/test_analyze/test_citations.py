"""
Tests for citation processing and analysis.

Tests the CitationProcessor and other citation-related components.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thoth.analyze.citations.citations import CitationProcessor
from thoth.analyze.citations.extractor import ReferenceExtractor
from thoth.utilities.config import ThothConfig
from thoth.utilities.schemas import Citation


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service for testing."""
    llm_service = MagicMock()
    mock_client = MagicMock()

    # Mock the with_structured_output method to return a mock that can be invoked
    structured_output_mock = MagicMock()
    structured_output_mock.invoke.return_value = {}  # Default empty response
    mock_client.with_structured_output.return_value = structured_output_mock

    # Make with_options chainable and return the client
    mock_client.with_options.return_value = mock_client
    llm_service.get_client.return_value = mock_client
    return llm_service


@pytest.fixture
def mock_prompt_template():
    """Create a mock prompt template."""
    return MagicMock()


def test_single_mode_processing(thoth_config: ThothConfig, mock_llm_service):
    """Test that single processing mode calls the correct method."""
    thoth_config.citation_config.citation_batch_size = 1
    processor = CitationProcessor(mock_llm_service, thoth_config)

    with (
        patch.object(
            processor, '_extract_structured_citations_single', return_value=[]
        ) as mock_single,
        patch.object(
            processor, '_extract_structured_citations_batch', return_value=[]
        ) as mock_batch,
    ):
        mock_path = MagicMock(spec=Path)
        mock_path.read_text.return_value = 'some content'
        processor.extract_citations(mock_path)
        mock_single.assert_called_once()
        mock_batch.assert_not_called()


def test_batch_mode_processing(thoth_config: ThothConfig, mock_llm_service):
    """Test that batch processing mode calls the correct method."""
    thoth_config.citation_config.citation_batch_size = 10
    processor = CitationProcessor(mock_llm_service, thoth_config)

    with (
        patch.object(
            processor, '_extract_structured_citations_single', return_value=[]
        ) as mock_single,
        patch.object(
            processor, '_extract_structured_citations_batch', return_value=[]
        ) as mock_batch,
    ):
        mock_path = MagicMock(spec=Path)
        mock_path.read_text.return_value = 'some content'
        processor.extract_citations(mock_path)
        mock_single.assert_not_called()
        mock_batch.assert_called_once()


def test_full_citation_extraction_flow(thoth_config: ThothConfig, monkeypatch):
    """Test the full citation extraction workflow, mocking the LLM at each step."""
    # 1. Setup Mocks
    mock_llm_service = MagicMock()
    mock_llm_client = MagicMock()
    mock_llm_service.get_client.return_value = mock_llm_client

    # Mock responses for each chain
    mock_doc_citation = Citation(title='Main Paper', is_document_citation=True)
    mock_structured_citation = Citation(
        title='Paper A', authors=['Author A'], year=2023
    )

    monkeypatch.setattr(
        'thoth.analyze.citations.citations.CitationEnhancer.enhance',
        lambda _self, citations: citations,
    )

    # 2. Create Processor and patch its internal methods
    with (
        patch.object(
            CitationProcessor,
            '_extract_document_citation',
            return_value=mock_doc_citation,
        ),
        patch.object(
            CitationProcessor,
            '_extract_structured_citations_single',
            return_value=[mock_structured_citation],
        ),
    ):
        processor = CitationProcessor(mock_llm_service, thoth_config)
        thoth_config.citation_config.citation_batch_size = 1
        processor.citation_batch_size = 1

        # 3. Run extraction with dummy content
        with (
            patch.object(
                processor, '_extract_references_section', return_value='## References'
            ),
            patch.object(
                processor,
                '_clean_references_section',
                return_value='[1] Author A, Paper A (2023)',
            ),
            patch.object(
                processor,
                '_split_references_to_raw_citations',
                return_value=['[1] Author A, Paper A (2023)'],
            ),
        ):
            citations = processor.extract_citations(MagicMock(spec=Path))

    # 4. Assertions
    assert len(citations) == 2
    assert any(c.title == 'Main Paper' for c in citations)
    assert any(c.title == 'Paper A' for c in citations)


@pytest.fixture
def mock_extractor_llm():
    """Create a mock LLM for the ReferenceExtractor."""
    llm = MagicMock()
    # Mock the with_structured_output method to return a mock that can be invoked
    structured_output_mock = MagicMock()
    structured_output_mock.invoke.return_value = MagicMock(heading='References')
    llm.with_structured_output.return_value = structured_output_mock
    return llm


@pytest.mark.parametrize(
    'markdown_content, expected_headings',
    [
        ('# Heading 1\n\n## Heading 2', ['Heading 1', 'Heading 2']),
        (
            'Title\n=====\n\nSubtitle\n--------',
            ['Title', 'Subtitle'],
        ),
        (
            '# ATX and Setext\n\nAnother heading\n---',
            ['ATX and Setext', 'Another heading'],
        ),
        ('  # Leading and trailing spaces  ', ['Leading and trailing spaces']),
        ('No headings here', []),
    ],
)
def test_heading_extraction(
    markdown_content, expected_headings, mock_extractor_llm, mock_prompt_template
):
    """Test that the ReferenceExtractor correctly extracts headings from markdown."""
    extractor = ReferenceExtractor(mock_extractor_llm, mock_prompt_template)
    headings = extractor._get_section_headings(markdown_content)
    assert headings == expected_headings


def test_references_section_extraction(mock_extractor_llm, mock_prompt_template):
    """Test that the references section is correctly extracted."""
    content = """
# Introduction
Some intro text.

## Methods
Some methods text.

# References
[1] A. Author, "A great paper," 2023.
[2] B. Author, "Another great paper," 2024.

# Conclusion
Some conclusion text.
"""
    extractor = ReferenceExtractor(mock_extractor_llm, mock_prompt_template)
    references_text = extractor.extract(content)
    assert '[1] A. Author' in references_text
    assert '[2] B. Author' in references_text
    assert 'Introduction' not in references_text
    assert 'Conclusion' not in references_text

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pypdf import PdfWriter

from thoth.utilities.config import (
    APIGatewayConfig,
    APIKeys,
    CitationConfig,
    CitationLLMConfig,
    CoreConfig,
    EndpointConfig,
    FeatureConfig,
    LLMConfig,
    LoggingConfig,
    ModelConfig,
    RAGConfig,
    TagConsolidatorLLMConfig,
    ThothConfig,
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        # Create standard subdirectories if needed by tests
        (workspace / 'data' / 'pdf').mkdir(parents=True, exist_ok=True)
        (workspace / 'data' / 'notes').mkdir(parents=True, exist_ok=True)
        (workspace / 'knowledge').mkdir(parents=True, exist_ok=True)
        (workspace / 'logs').mkdir(parents=True, exist_ok=True)
        yield workspace


@pytest.fixture
def thoth_config(temp_workspace):
    """
    Create a ThothConfig object with mocked values for testing.
    This fixture now programmatically builds the config to avoid
    issues with environment variable conflicts and validation errors.
    """
    with tempfile.TemporaryDirectory():
        config = ThothConfig(
            core=CoreConfig(
                workspace_dir=temp_workspace,
                prompts_dir=Path(__file__).parent.parent / 'templates' / 'prompts',
                api_keys=APIKeys(
                    mistral_key='test_mistral_key',
                    openrouter_key='test_openrouter_key',
                    openai_key='test_openai_key',
                    anthropic_key='test_anthropic_key',
                    opencitations_key='test_opencitations_key',
                    semanticscholar_api_key='test_semanticscholar_key',
                ),
                llm_config=LLMConfig(
                    model='openai/gpt-4o-mini',
                ),
            ),
            features=FeatureConfig(
                api_server=EndpointConfig(
                    host='localhost',
                    port=8000,
                    base_url='http://localhost:8000',
                    auto_start=False,
                ),
                rag=RAGConfig(
                    collection_name='test_collection',
                    embedding_model='all-MiniLM-L6-v2',
                ),
            ),
            logging_config=LoggingConfig(
                level='INFO',
                logformat='<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>',
            ),
            api_gateway_config=APIGatewayConfig(
                endpoints={
                    'test_service': 'https://httpbin.org',
                    'mock_api': 'https://jsonplaceholder.typicode.com',
                },
                rate_limit=10.0,
                cache_expiry=300,
            ),
            citation_llm_config=CitationLLMConfig(model='test/model'),
            tag_consolidator_llm_config=TagConsolidatorLLMConfig(
                consolidate_model='test/model',
                suggest_model='test/model',
                map_model='test/model',
                model_settings=ModelConfig(),
            ),
            citation_config=CitationConfig(opencitations_key='dummy-key'),
        )
        yield config


@pytest.fixture
def mock_config(temp_workspace):
    """Create a mock configuration for testing."""
    config = MagicMock(spec=ThothConfig)
    config.workspace_dir = temp_workspace
    config.pdf_dir = temp_workspace / 'data' / 'pdf'
    config.notes_dir = temp_workspace / 'data' / 'notes'
    config.knowledge_base_dir = temp_workspace / 'knowledge'
    config.api_keys.openrouter_key = 'test-openrouter-key'
    config.api_keys.mistral_key = 'test-mistral-key'
    return config


@pytest.fixture
def sample_pdf_path(temp_workspace):
    """Create a dummy PDF file for testing."""
    pdf_path = temp_workspace / 'sample.pdf'
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)  # Create a small blank page
    with open(pdf_path, 'wb') as f:
        writer.write(f)
    return pdf_path


@pytest.fixture
def sample_markdown_path(temp_workspace):
    """Create a dummy Markdown file for testing."""
    md_path = temp_workspace / 'sample.md'
    md_path.write_text('# Sample Markdown\n\nThis is a test.')
    return md_path


@pytest.fixture
def sample_analysis_response():
    """Return a sample AnalysisResponse object."""
    from thoth.utilities.schemas import AnalysisResponse

    return AnalysisResponse(
        abstract='Test abstract.',
        summary='Test summary.',
        key_points='- Point 1\n- Point 2',
    )


@pytest.fixture
def sample_citations():
    """Return a sample list of Citation objects."""
    from thoth.utilities.schemas import Citation

    return [
        Citation(
            title='Test Paper 1',
            text='Raw text 1',
            doi='10.1234/test1',
            is_document_citation=True,
        ),
        Citation(
            title='Test Paper 2',
            text='Raw text 2',
            arxiv_id='1234.56789',
        ),
    ]


@pytest.fixture
def sample_research_query():
    """Return a sample ResearchQuery object."""
    from thoth.utilities.schemas import ResearchQuery

    return ResearchQuery(
        name='test_query',
        description='A query for testing purposes',
        research_question='What is the meaning of life?',
        keywords=['life', 'meaning', 'philosophy'],
        required_topics=['philosophy'],
        preferred_topics=['existentialism'],
        excluded_topics=['mathematics'],
        minimum_relevance_score=0.6,
    )

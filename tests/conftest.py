import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pypdf import PdfWriter

from thoth.utilities.config import (
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
    Create a ThothConfig object with test values using hybrid loader.
    """
    import json
    import tempfile
    from pathlib import Path

    # Create a temporary settings file for testing
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        test_settings = {
            'apiKeys': {
                'mistralKey': 'test_mistral_key',
                'openrouterKey': 'test_openrouter_key',
                'openaiKey': 'test_openai_key',
                'anthropicKey': 'test_anthropic_key',
                'opencitationsKey': 'test_opencitations_key',
                'semanticScholarKey': 'test_semanticscholar_key',
            },
            'llm': {
                'default': {'model': 'openai/gpt-4o-mini'},
                'citation': {'model': 'openai/gpt-4o-mini'},
                'researchAgent': {'model': 'test/research-model'},
                'tagConsolidator': {
                    'consolidateModel': 'test/model',
                    'suggestModel': 'test/model',
                    'mapModel': 'test/model',
                },
            },
            'paths': {
                'workspace': str(temp_workspace),
                'pdf': 'data/pdf',
                'notes': 'data/notes',
            },
            'servers': {
                'api': {
                    'host': 'localhost',
                    'port': 8000,
                    'baseUrl': 'http://localhost:8000',
                }
            },
            'rag': {
                'collectionName': 'test_collection',
                'embeddingModel': 'all-MiniLM-L6-v2',
            },
            'logging': {'level': 'INFO', 'format': '{time} | {level} | {message}'},
        }
        json.dump(test_settings, f)
        temp_settings_path = f.name

    try:
        # Create config using hybrid loader with temporary settings file
        from thoth.utilities.config.hybrid_loader import (
            HybridConfigLoader,
            create_hybrid_settings,
        )

        # Temporarily replace the settings file path
        original_init = HybridConfigLoader.__init__

        def mock_init(self, env_file='.env', settings_file='.thoth.settings.json'):  # noqa: ARG001
            original_init(self, env_file, temp_settings_path)

        HybridConfigLoader.__init__ = mock_init

        try:
            config = create_hybrid_settings(ThothConfig)
            yield config
        finally:
            HybridConfigLoader.__init__ = original_init
    finally:
        Path(temp_settings_path).unlink(missing_ok=True)


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
    config.api_keys.openai_key = 'test-openai-key'
    config.api_keys.anthropic_key = 'test-anthropic-key'
    config.api_keys.opencitations_key = 'test-opencitations-key'

    # Add nested config objects explicitly
    config.citation_llm_config = MagicMock()
    config.citation_llm_config.model = 'openai/gpt-4o-mini'

    config.citation_config = MagicMock()
    config.citation_config.use_semanticscholar = True
    config.citation_config.use_opencitations = True
    config.citation_config.use_scholarly = False
    config.citation_config.use_arxiv = False

    config.rag_config = MagicMock()
    config.rag_config.collection_name = 'test_collection'
    config.rag_config.embedding_model = 'all-MiniLM-L6-v2'
    config.rag_config.vector_db_path = temp_workspace / 'vector_db'
    config.rag_config.chunk_size = 4000
    config.rag_config.chunk_overlap = 200

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

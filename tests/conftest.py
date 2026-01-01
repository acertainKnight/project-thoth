"""
Pytest configuration and shared fixtures for Thoth test suite.

This module provides:
- Database fixtures with transaction rollback
- Mock service fixtures (LLM, web search, API clients)
- Sample data fixtures (citations, papers, ground truth)
- Test configuration overrides
- Async test support configuration
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from loguru import logger

from thoth.config import Config
from thoth.services.postgres_service import PostgresService
from thoth.utilities.schemas.citations import Citation

# Import all fixture modules to make fixtures available
pytest_plugins = [
    'tests.fixtures.citation_fixtures',
    'tests.fixtures.config_fixtures',  # Added: temp_vault and config fixtures
    'tests.fixtures.database_fixtures',
    'tests.fixtures.evaluation_fixtures',
    'tests.fixtures.mcp_fixtures',
    'tests.fixtures.mcp_server_fixtures',  # Added: MCP server fixtures
    'tests.fixtures.performance_fixtures',
    'tests.fixtures.service_fixtures',
    'tests.fixtures.workflow_fixtures',
]


# ============================================================================
# Test Configuration
# ============================================================================

@pytest.fixture(scope='session')
def event_loop_policy():
    """Set event loop policy for async tests."""
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope='session')
def test_config() -> Config:
    """
    Create test configuration with overrides.

    Uses in-memory test database and mock API keys.
    """
    # Create temporary test vault
    temp_dir = tempfile.mkdtemp(prefix='thoth_test_')
    test_vault = Path(temp_dir) / 'test_vault'
    test_vault.mkdir(parents=True)
    (test_vault / '_thoth').mkdir()

    # Mock environment variables
    with patch.dict('os.environ', {
        'OBSIDIAN_VAULT_PATH': str(test_vault),
        'POSTGRES_DB': 'thoth_test',
        'POSTGRES_HOST': 'localhost',
        'POSTGRES_PORT': '5432',
        'POSTGRES_USER': 'test_user',
        'POSTGRES_PASSWORD': 'test_password',
    }):
        config = Config()
        config.vault_root = test_vault
        return config


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def postgres_service(test_config: Config) -> AsyncGenerator[PostgresService, None]:
    """
    Create PostgreSQL service with test database.

    Uses transaction rollback to ensure test isolation.
    Each test gets a clean database state.
    """
    service = PostgresService(test_config)
    await service.initialize()

    try:
        # Start transaction for test isolation
        async with service.pool.acquire() as conn:
            async with conn.transaction():
                yield service
                # Transaction automatically rolls back after test
    finally:
        await service.close()


@pytest_asyncio.fixture
async def empty_database(postgres_service: PostgresService):
    """
    Ensure database is empty before test.

    Truncates all tables to provide clean slate.
    """
    async with postgres_service.pool.acquire() as conn:
        await conn.execute('TRUNCATE TABLE citations CASCADE')
        await conn.execute('TRUNCATE TABLE papers CASCADE')
        await conn.execute('TRUNCATE TABLE articles CASCADE')
        await conn.execute('TRUNCATE TABLE research_questions CASCADE')


# ============================================================================
# Mock Service Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_service():
    """
    Mock LLM service for testing without API calls.

    Returns structured responses matching expected schemas.
    """
    mock = MagicMock()
    mock.generate_completion = AsyncMock(return_value='Mocked LLM response')
    mock.analyze_content = AsyncMock(return_value={
        'summary': 'Test paper summary',
        'key_points': ['Point 1', 'Point 2', 'Point 3'],
        'methodology': 'Test methodology',
        'tags': ['machine-learning', 'nlp'],
    })
    return mock


@pytest.fixture
def mock_web_search():
    """
    Mock web search service to avoid external API calls.

    Returns realistic search results for testing.
    """
    mock = MagicMock()
    mock.search = AsyncMock(return_value=[
        {
            'title': 'Test Paper Title',
            'url': 'https://example.com/paper.pdf',
            'snippet': 'Test paper abstract snippet',
        }
    ])
    return mock


@pytest.fixture
def mock_crossref_client():
    """Mock CrossRef API client."""
    mock = MagicMock()
    mock.search = AsyncMock(return_value={
        'status': 'ok',
        'message': {
            'items': [
                {
                    'DOI': '10.1234/test.doi',
                    'title': ['Test Paper Title'],
                    'author': [
                        {'given': 'John', 'family': 'Doe'},
                        {'given': 'Jane', 'family': 'Smith'},
                    ],
                    'published': {'date-parts': [[2023, 5, 15]]},
                    'container-title': ['Test Journal'],
                }
            ]
        }
    })
    return mock


@pytest.fixture
def mock_openalex_client():
    """Mock OpenAlex API client."""
    mock = MagicMock()
    mock.search = AsyncMock(return_value={
        'results': [
            {
                'id': 'https://openalex.org/W1234567890',
                'doi': 'https://doi.org/10.1234/test.doi',
                'title': 'Test Paper Title',
                'authorships': [
                    {'author': {'display_name': 'John Doe'}},
                    {'author': {'display_name': 'Jane Smith'}},
                ],
                'publication_year': 2023,
                'primary_location': {
                    'source': {'display_name': 'Test Journal'}
                },
            }
        ]
    })
    return mock


@pytest.fixture
def mock_semanticscholar_client():
    """Mock Semantic Scholar API client."""
    mock = MagicMock()
    mock.search = AsyncMock(return_value={
        'data': [
            {
                'paperId': 'abcd1234',
                'externalIds': {'DOI': '10.1234/test.doi'},
                'title': 'Test Paper Title',
                'authors': [
                    {'name': 'John Doe'},
                    {'name': 'Jane Smith'},
                ],
                'year': 2023,
                'venue': 'Test Journal',
                'citationCount': 42,
            }
        ]
    })
    return mock


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_citation() -> Citation:
    """
    Create sample citation for testing.

    Represents typical academic citation with all fields populated.
    """
    return Citation(
        text='Doe, J., & Smith, J. (2023). Test Paper Title. Test Journal, 10(2), 123-145.',
        title='Test Paper Title',
        authors=['John Doe', 'Jane Smith'],
        year=2023,
        journal='Test Journal',
        volume='10',
        issue='2',
        pages='123-145',
    )


@pytest.fixture
def sample_citations() -> list[Citation]:
    """
    Create list of sample citations for batch testing.

    Includes various citation formats and completeness levels.
    """
    return [
        Citation(
            text='Doe, J. (2023). First Paper. Journal A.',
            title='First Paper',
            authors=['John Doe'],
            year=2023,
            journal='Journal A',
        ),
        Citation(
            text='Smith, J., & Jones, B. (2022). Second Paper. Journal B, 5(1), 10-20.',
            title='Second Paper',
            authors=['Jane Smith', 'Bob Jones'],
            year=2022,
            journal='Journal B',
            volume='5',
            issue='1',
            pages='10-20',
        ),
        Citation(
            text='Brown et al. (2021). Third Paper. arXiv:2101.12345.',
            title='Third Paper',
            authors=['Alice Brown', 'Charlie White'],
            year=2021,
            arxiv_id='2101.12345',
        ),
    ]


@pytest.fixture
def sample_paper_content() -> str:
    """
    Create sample paper content for analysis testing.

    Includes typical paper sections: abstract, intro, methods, results, conclusion.
    """
    return '''
# Test Paper Title

## Abstract
This is a test paper abstract that summarizes the key contributions.
We present a novel approach to test-driven development in research software.

## Introduction
Academic research requires rigorous testing methodologies.
This paper explores property-based testing for citation resolution.

## Methods
We employ hypothesis testing framework for property-based tests.
Our approach validates symmetry, monotonicity, and boundary conditions.

## Results
Property-based tests discovered 3 edge cases in citation parser.
Performance benchmarks show 2.5x speedup with batch processing.

## Conclusion
Property-based testing provides robust validation for research software.
Future work will extend to LLM-based content analysis pipelines.

## References
1. Test Citation One (2023)
2. Test Citation Two (2022)
'''


@pytest.fixture
def sample_ground_truth():
    """
    Create sample ground truth data for evaluation testing.

    Includes annotated citation resolutions with confidence scores.
    """
    return {
        'citations': [
            {
                'input': 'Doe, J. (2023). Test Paper.',
                'expected_doi': '10.1234/test.doi',
                'expected_title': 'Test Paper Title',
                'expected_confidence': 0.95,
            }
        ],
        'analyses': [
            {
                'paper_id': 'test_paper_1',
                'expected_summary': 'Expected summary text...',
                'expected_tags': ['test', 'evaluation'],
                'expected_strategy': 'direct',
            }
        ]
    }


# ============================================================================
# Performance Testing Fixtures
# ============================================================================

@pytest.fixture
def benchmark_data_small() -> list[Citation]:
    """Generate small dataset (10 citations) for benchmarking."""
    return [
        Citation(
            title=f'Test Paper {i}',
            authors=[f'Author {i}'],
            year=2020 + (i % 4),
            journal=f'Journal {i % 3}',
        )
        for i in range(10)
    ]


@pytest.fixture
def benchmark_data_medium() -> list[Citation]:
    """Generate medium dataset (100 citations) for benchmarking."""
    return [
        Citation(
            title=f'Test Paper {i}',
            authors=[f'Author {i}', f'CoAuthor {i}'],
            year=2020 + (i % 4),
            journal=f'Journal {i % 10}',
        )
        for i in range(100)
    ]


@pytest.fixture
def benchmark_data_large() -> list[Citation]:
    """Generate large dataset (1000 citations) for benchmarking."""
    return [
        Citation(
            title=f'Test Paper {i}',
            authors=[f'Author {j}' for j in range(i % 5 + 1)],
            year=2020 + (i % 4),
            journal=f'Journal {i % 20}',
            volume=str(i % 50),
        )
        for i in range(1000)
    ]


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """
    Create temporary directory for test file operations.

    Automatically cleaned up after test completion.
    """
    with tempfile.TemporaryDirectory(prefix='thoth_test_') as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def capture_logs(caplog):
    """
    Capture log output during tests.

    Useful for verifying logging behavior.
    """
    caplog.set_level('DEBUG')
    return caplog


# ============================================================================
# Markers and Test Configuration
# ============================================================================

def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        'markers', 'e2e: End-to-end integration tests (may be slow)'
    )
    config.addinivalue_line(
        'markers', 'property: Property-based tests using hypothesis'
    )
    config.addinivalue_line(
        'markers', 'benchmark: Performance benchmark tests'
    )
    config.addinivalue_line(
        'markers', 'slow: Tests that take significant time to run'
    )
    config.addinivalue_line(
        'markers', 'requires_db: Tests that require PostgreSQL database'
    )
    config.addinivalue_line(
        'markers', 'requires_api: Tests that require external API access'
    )


# ============================================================================
# Async Test Helpers
# ============================================================================

@pytest.fixture
def anyio_backend():
    """Configure anyio backend for async tests."""
    return 'asyncio'

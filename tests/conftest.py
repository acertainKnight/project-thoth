# This file can be empty. Its presence helps pytest discovery.

"""
Pytest configuration and fixtures for Thoth test suite.

This module provides common fixtures and configuration for all tests.
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dotenv import load_dotenv

from thoth.utilities.schemas import AnalysisResponse, Citation, ResearchQuery

# Load test environment
load_dotenv('.env.test', override=True)


@pytest.fixture(scope='session')
def test_data_dir():
    """
    Create a temporary directory for test data that persists for the entire test
    session.

    Returns:
        Path: Path to the test data directory.
    """
    temp_dir = tempfile.mkdtemp(prefix='thoth_test_')
    yield Path(temp_dir)
    # Cleanup after all tests
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_workspace(test_data_dir):
    """
    Create a temporary workspace directory for each test.

    Args:
        test_data_dir: Session-scoped test data directory.

    Returns:
        Path: Path to the temporary workspace.
    """
    workspace = test_data_dir / f'workspace_{os.getpid()}'
    workspace.mkdir(exist_ok=True)

    # Create standard subdirectories
    (workspace / 'pdf').mkdir(exist_ok=True)
    (workspace / 'markdown').mkdir(exist_ok=True)
    (workspace / 'notes').mkdir(exist_ok=True)
    (workspace / 'output').mkdir(exist_ok=True)
    (workspace / 'knowledge').mkdir(exist_ok=True)
    (workspace / 'discovery').mkdir(exist_ok=True)

    yield workspace

    # Cleanup
    if workspace.exists():
        shutil.rmtree(workspace)


@pytest.fixture
def mock_config(temp_workspace):
    """
    Create a mock configuration for testing.

    Args:
        temp_workspace: Temporary workspace directory.

    Returns:
        dict: Mock configuration dictionary.
    """
    return {
        'pdf_dir': str(temp_workspace / 'pdf'),
        'markdown_dir': str(temp_workspace / 'markdown'),
        'notes_dir': str(temp_workspace / 'notes'),
        'output_dir': str(temp_workspace / 'output'),
        'knowledge_dir': str(temp_workspace / 'knowledge'),
        'discovery_dir': str(temp_workspace / 'discovery'),
        'templates_dir': 'templates',
        'prompts_dir': 'templates/prompts',
        'api_keys': {
            'mistral_key': 'test_mistral_key',
            'openrouter_key': 'test_openrouter_key',
            'openai_key': 'test_openai_key',
            'anthropic_key': 'test_anthropic_key',
            'opencitations_key': 'test_opencitations_key',
            'semanticscholar_key': 'test_semanticscholar_key',
        },
        'llm_config': {
            'model': 'openai/gpt-4o-mini',
            'temperature': 0.7,
            'max_tokens': 4000,
        },
        'api_server_config': {
            'host': 'localhost',
            'port': 8000,
            'base_url': 'http://localhost:8000',
            'auto_start': False,
        },
        'mcp_server_config': {
            'host': 'localhost',
            'port': 8001,
            'base_url': 'http://localhost:8001',
            'auto_start': False,
        },
    }


@pytest.fixture
def thoth_config(mock_config, monkeypatch):
    """
    Create a ThothConfig object with mocked values for testing.
    """
    from thoth.utilities.config import ThothConfig

    # Use monkeypatch to set environment variables from mock_config
    # This is more robust for testing the real config loading
    monkeypatch.setenv('API_MISTRAL_KEY', mock_config['api_keys']['mistral_key'])
    monkeypatch.setenv('API_OPENROUTER_KEY', mock_config['api_keys']['openrouter_key'])
    # ... set other env vars as needed ...

    config = ThothConfig()

    # Override any complex objects that need mocking
    config.core.pdf_dir = Path(mock_config['pdf_dir'])
    config.core.markdown_dir = Path(mock_config['markdown_dir'])
    config.core.notes_dir = Path(mock_config['notes_dir'])
    config.core.output_dir = Path(mock_config['output_dir'])
    config.core.knowledge_base_dir = Path(mock_config['knowledge_dir'])
    # ... and so on for other paths

    return config


@pytest.fixture
def mock_llm_client():
    """
    Create a mock LLM client for testing.

    Returns:
        MagicMock: Mock LLM client.
    """
    client = MagicMock()

    # Default response for analysis
    client.analyze.return_value = {
        'title': 'Test Paper',
        'authors': ['Author 1', 'Author 2'],
        'abstract': 'Test abstract',
        'key_findings': ['Finding 1', 'Finding 2'],
        'methodology': 'Test methodology',
        'results': 'Test results',
        'significance': 'Test significance',
        'limitations': ['Limitation 1'],
        'future_work': ['Future work 1'],
        'tags': ['test', 'paper'],
    }

    return client


@pytest.fixture
def sample_pdf_path(temp_workspace):
    """
    Create a sample PDF file for testing.

    Args:
        temp_workspace: Temporary workspace directory.

    Returns:
        Path: Path to the sample PDF file.
    """
    pdf_path = temp_workspace / 'pdf' / 'sample.pdf'

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(pdf_path, 'wb') as f:
        writer.write(f)

    return pdf_path


@pytest.fixture
def sample_markdown_path(temp_workspace):
    """
    Create a sample markdown file for testing.

    Args:
        temp_workspace: Temporary workspace directory.

    Returns:
        Path: Path to the sample markdown file.
    """
    md_path = temp_workspace / 'markdown' / 'sample.md'
    md_content = """# Sample Paper

## Abstract
This is a test abstract for the sample paper.

## Introduction
This is the introduction section.

## Methods
This describes the methodology.

## Results
These are the results.

## References
1. Reference One (2023)
2. Reference Two (2023)
"""
    md_path.write_text(md_content)
    return md_path


@pytest.fixture
def sample_analysis_response():
    """
    Create a sample analysis response for testing.

    Returns:
        dict: Sample analysis response.
    """
    return AnalysisResponse(
        title='Sample Paper Title',
        authors=['Author One', 'Author Two'],
        abstract='This is a sample abstract.',
        summary='This is a sample summary of the paper.',
        key_points='- Finding 1\n- Finding 2',
        key_findings=['Finding 1', 'Finding 2'],
        methodology='Sample methodology',
        results='Sample results',
        significance='Sample significance',
        limitations='Limitation 1',
        future_work='Future work 1',
        tags=['machine-learning', 'deep-learning'],
        arxiv_id='2301.00001',
        doi='10.1234/sample',
        publication_date='2023-01-01',
        venue='Sample Conference 2023',
    )


@pytest.fixture
def sample_research_query():
    """
    Create a sample research query for testing.

    Returns:
        ResearchQuery: Sample research query.
    """
    return ResearchQuery(
        name='test_query',
        description='Test research query',
        research_question='What are the latest advances in machine learning?',
        keywords=['machine learning', 'deep learning', 'neural networks'],
        required_topics=['machine learning'],
        preferred_topics=['deep learning'],
        excluded_topics=['hardware'],
    )


@pytest.fixture
def sample_citations():
    """
    Create sample citations for testing.

    Returns:
        list: List of sample citations.
    """
    return [
        Citation(
            title='Citation One',
            authors=['Author A', 'Author B'],
            year='2023',
            venue='Conference A',
            url='https://example.com/paper1',
            doi='10.1234/citation1',
        ),
        Citation(
            title='Citation Two',
            authors=['Author C', 'Author D'],
            year='2023',
            venue='Journal B',
            url='https://example.com/paper2',
            doi='10.1234/citation2',
        ),
    ]


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """
    Set up mock environment variables for all tests.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setenv('API_MISTRAL_KEY', 'test_mistral_key')
    monkeypatch.setenv('API_OPENROUTER_KEY', 'test_openrouter_key')
    monkeypatch.setenv('API_OPENAI_KEY', 'test_openai_key')
    monkeypatch.setenv('API_ANTHROPIC_KEY', 'test_anthropic_key')
    monkeypatch.setenv('LLM_MODEL', 'openai/gpt-4o-mini')
    monkeypatch.setenv('ENDPOINT_HOST', 'localhost')
    monkeypatch.setenv('ENDPOINT_PORT', '8000')
    monkeypatch.setenv('ENDPOINT_BASE_URL', 'http://localhost:8000')


@pytest.fixture
def mock_service_manager(mock_config):
    """
    Create a mock service manager for testing.

    Args:
        mock_config: Mock configuration.

    Returns:
        ServiceManager: Mock service manager.
    """
    from thoth.services.service_manager import ServiceManager

    # Create a real service manager with test configuration
    manager = ServiceManager(
        ocr_api_key=mock_config['api_keys']['mistral_key'],
        llm_api_key=mock_config['api_keys']['openrouter_key'],
        templates_dir=Path(mock_config['templates_dir']),
        prompts_dir=Path(mock_config['prompts_dir']),
        output_dir=Path(mock_config['output_dir']),
        notes_dir=Path(mock_config['notes_dir']),
        api_base_url=mock_config['api_server_config']['base_url'],
        knowledge_dir=Path(mock_config['knowledge_dir']),
    )

    return manager

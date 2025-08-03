"""
Pytest configuration for agent v2 tests.

Provides fixtures and configuration specific to agent v2 testing.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from thoth.ingestion.agent_v2 import create_research_assistant
from thoth.pipeline import ThothPipeline
from thoth.services.service_manager import ServiceManager
from thoth.utilities.config import (
    APIGatewayConfig,
    APIKeys,
    CoreConfig,
    EndpointConfig,
    FeatureConfig,
    LLMConfig,
    LoggingConfig,
    RAGConfig,
    ThothConfig,
)


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_pipeline(thoth_config, monkeypatch):
    """
    Create a ThothPipeline for agent testing.

    Uses the thoth_config fixture from the main conftest.py.
    """

    # Mock the get_config function to return our test config
    def mock_get_config():
        return thoth_config

    monkeypatch.setattr('thoth.pipeline.get_config', mock_get_config)

    # ThothPipeline loads config internally, doesn't accept config parameter
    pipeline = ThothPipeline()
    return pipeline


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
    """Create a ThothConfig object with mocked values for testing."""
    with tempfile.TemporaryDirectory():
        config = ThothConfig(
            core=CoreConfig(
                workspace_dir=temp_workspace,
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
                enabled=True,
            ),
        )
        yield config


@pytest.fixture
def mock_service_manager():
    """Create a mock service manager for unit testing."""
    service_manager = MagicMock(spec=ServiceManager)
    service_manager.config = MagicMock()
    service_manager.llm = MagicMock()
    service_manager.query = MagicMock()
    service_manager.discovery = MagicMock()
    service_manager.rag = MagicMock()
    service_manager.article = MagicMock()
    yield service_manager


@pytest.fixture
def legacy_test_agent(test_pipeline):
    """Create a legacy agent for testing."""
    import asyncio

    agent = create_research_assistant(
        service_manager=test_pipeline.services, enable_memory=False, use_mcp_tools=False
    )
    # Initialize the agent to load tools synchronously
    asyncio.run(agent.async_initialize())
    return agent


@pytest.fixture
def mcp_test_agent(test_pipeline):
    """Create an MCP agent for testing (may skip if not available)."""
    import asyncio

    try:
        agent = create_research_assistant(
            service_manager=test_pipeline.services,
            enable_memory=False,
            use_mcp_tools=True,
        )
        # Initialize the agent to load tools synchronously
        asyncio.run(agent.async_initialize())
        return agent
    except Exception:
        pytest.skip('MCP agent not available')


# Pytest markers for categorizing tests
def pytest_configure(config):
    """Register custom markers for pytest."""
    config.addinivalue_line('markers', 'mcp: Tests for MCP tools')
    config.addinivalue_line('markers', 'legacy: Tests for legacy tools')
    config.addinivalue_line(
        'markers', 'async_execution: Tests for async execution fixes'
    )
    config.addinivalue_line('markers', 'slow: Slow tests that may take longer to run')
    config.addinivalue_line('markers', 'integration: Integration tests')


def pytest_addoption(parser):
    """Add command line options for pytest."""
    parser.addoption(
        '--integration',
        action='store_true',
        default=False,
        help='run integration tests',
    )


def pytest_collection_modifyitems(items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add markers based on test/module names
        if 'mcp' in item.nodeid.lower():
            item.add_marker(pytest.mark.mcp)
        if 'legacy' in item.nodeid.lower():
            item.add_marker(pytest.mark.legacy)
        if 'async' in item.nodeid.lower():
            item.add_marker(pytest.mark.async_execution)

        # Add integration/unit markers
        if 'integration' in item.nodeid.lower():
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)


def pytest_runtest_setup(item):
    """Skip integration tests if not specified."""
    if 'integration' in item.keywords and not item.config.getoption('--integration'):
        pytest.skip('skipping integration test')

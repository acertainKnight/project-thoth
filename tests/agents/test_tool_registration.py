"""
Tests for Letta tool registration system.
"""

from unittest.mock import Mock, patch

import pytest

from thoth.agents.orchestrator import ThothOrchestrator
from thoth.services.service_manager import ServiceManager
from thoth.tools.letta_registration import LettaToolRegistry, register_all_letta_tools


class TestLettaToolRegistry:
    """Test the LettaToolRegistry class."""

    @pytest.fixture
    def service_manager(self):
        """Mock service manager."""
        return Mock(spec=ServiceManager)

    @pytest.fixture
    def mock_letta_client(self):
        """Mock Letta client."""
        client = Mock()
        client.tools = Mock()
        client.tools.create = Mock()
        return client

    def test_init_without_letta(self, service_manager):
        """Test registry initialization without Letta client."""
        registry = LettaToolRegistry(service_manager)

        assert registry.service_manager == service_manager
        assert registry.letta_client is None
        assert isinstance(registry._registered_tools, dict)
        assert len(registry._registered_tools) == 0

    def test_init_with_letta(self, service_manager, mock_letta_client):
        """Test registry initialization with Letta client."""
        registry = LettaToolRegistry(service_manager, mock_letta_client)

        assert registry.service_manager == service_manager
        assert registry.letta_client == mock_letta_client
        assert isinstance(registry._registered_tools, dict)

    def test_tool_categorization(self, service_manager):
        """Test tool categorization logic."""
        registry = LettaToolRegistry(service_manager)

        # Test research tools
        assert registry._categorize_tool('search_articles') == 'research'
        assert registry._categorize_tool('analyze_topic') == 'research'

        # Test citation tools
        assert registry._categorize_tool('extract_citations') == 'citation'
        assert registry._categorize_tool('format_citations') == 'citation'

        # Test processing tools
        assert registry._categorize_tool('process_pdf') == 'processing'
        assert registry._categorize_tool('batch_process_pdfs') == 'processing'

        # Test memory tools
        assert registry._categorize_tool('core_memory_append') == 'memory'
        assert registry._categorize_tool('archival_memory_search') == 'memory'

        # Test unknown tools default to general
        assert registry._categorize_tool('unknown_tool') == 'general'

    def test_get_tools_for_agent_type(self, service_manager):
        """Test getting tools for specific agent types."""
        registry = LettaToolRegistry(service_manager)

        # Mock some registered tools
        registry._registered_tools = {
            'search_articles': {'category': 'research'},
            'extract_citations': {'category': 'citation'},
            'process_pdf': {'category': 'processing'},
            'core_memory_append': {'category': 'memory'},
            'backup_collection': {'category': 'management'},
        }

        # Test research agent gets research, citation, and processing tools
        research_tools = registry.get_tools_for_agent_type('research')
        assert 'search_articles' in research_tools
        assert 'extract_citations' in research_tools
        assert 'process_pdf' in research_tools
        assert 'core_memory_append' not in research_tools  # memory not included

        # Test analysis agent gets research, citation, and memory tools
        analysis_tools = registry.get_tools_for_agent_type('analysis')
        assert 'search_articles' in analysis_tools
        assert 'extract_citations' in analysis_tools
        assert 'core_memory_append' in analysis_tools
        assert 'process_pdf' not in analysis_tools  # processing not included

        # Test custom agent gets all basic categories
        custom_tools = registry.get_tools_for_agent_type('custom')
        assert 'search_articles' in custom_tools
        assert 'process_pdf' in custom_tools
        assert 'core_memory_append' in custom_tools

    @pytest.mark.asyncio
    async def test_register_all_tools_without_letta(self, service_manager):
        """Test registering tools when Letta is not available."""
        registry = LettaToolRegistry(service_manager)  # No Letta client

        # Should not raise exception
        await registry.register_all_tools()

        # No tools should be registered with Letta
        assert len(registry._registered_tools) == 0

    @pytest.mark.asyncio
    @patch('thoth.tools.letta_registration.LETTA_AVAILABLE', True)
    async def test_register_all_tools_with_letta(
        self, service_manager, mock_letta_client
    ):
        """Test registering tools when Letta is available."""
        registry = LettaToolRegistry(service_manager, mock_letta_client)

        # Mock the tool creation
        mock_letta_client.tools.create.return_value = Mock(id='test_tool_id')

        with (
            patch.object(registry, '_register_mcp_tools') as mock_mcp,
            patch.object(registry, '_register_pipeline_tools') as mock_pipeline,
            patch.object(registry, '_register_utility_tools') as mock_utility,
        ):
            await registry.register_all_tools()

            # Verify all registration methods were called
            mock_mcp.assert_called_once()
            mock_pipeline.assert_called_once()
            mock_utility.assert_called_once()

    def test_generate_tool_source_code_mcp(self, service_manager):
        """Test MCP tool source code generation."""
        registry = LettaToolRegistry(service_manager)

        # Mock tool schema
        mock_schema = Mock()
        mock_schema.description = 'Test MCP tool'
        mock_schema.inputSchema = {
            'properties': {'query': {'type': 'string'}, 'limit': {'type': 'integer'}}
        }

        source_code = registry._generate_tool_source_code(
            'test_tool', mock_schema, 'mcp'
        )

        assert 'async def test_tool' in source_code
        assert 'query: str, limit: int' in source_code
        assert 'Test MCP tool' in source_code
        assert 'registry.execute_tool' in source_code

    def test_generate_tool_source_code_pipeline(self, service_manager):
        """Test pipeline tool source code generation."""
        registry = LettaToolRegistry(service_manager)

        tool_def = {
            'name': 'run_document_pipeline',
            'description': 'Process documents through pipeline',
            'category': 'processing',
        }

        source_code = registry._generate_tool_source_code(
            'run_document_pipeline', tool_def, 'pipeline'
        )

        assert 'async def run_document_pipeline' in source_code
        assert 'document_path: str' in source_code
        assert 'Process documents through pipeline' in source_code
        assert 'DocumentPipeline' in source_code

    def test_generate_tool_source_code_utility(self, service_manager):
        """Test utility tool source code generation."""
        registry = LettaToolRegistry(service_manager)

        tool_def = {
            'name': 'get_system_status',
            'description': 'Check system health',
            'category': 'management',
        }

        source_code = registry._generate_tool_source_code(
            'get_system_status', tool_def, 'utility'
        )

        assert 'def get_system_status' in source_code
        assert 'Check system health' in source_code
        assert 'System status:' in source_code


class TestToolRegistrationIntegration:
    """Integration tests for tool registration with orchestrator."""

    @pytest.fixture
    def service_manager(self):
        """Mock service manager."""
        return Mock(spec=ServiceManager)

    @pytest.mark.asyncio
    @patch('thoth.tools.letta_registration.LETTA_AVAILABLE', False)
    async def test_register_all_letta_tools_fallback(self, service_manager):
        """Test fallback behavior when Letta is not available."""
        registry = await register_all_letta_tools(service_manager)

        assert isinstance(registry, LettaToolRegistry)
        assert registry.service_manager == service_manager
        assert registry.letta_client is None

    @pytest.mark.asyncio
    @patch('thoth.tools.letta_registration.LETTA_AVAILABLE', True)
    async def test_register_all_letta_tools_with_client(self, service_manager):
        """Test tool registration with Letta client."""
        mock_client = Mock()
        mock_client.tools = Mock()
        mock_client.tools.create = Mock(return_value=Mock(id='test_tool'))

        with patch.object(LettaToolRegistry, 'register_all_tools') as mock_register:
            registry = await register_all_letta_tools(service_manager, mock_client)

            assert isinstance(registry, LettaToolRegistry)
            assert registry.service_manager == service_manager
            assert registry.letta_client == mock_client
            mock_register.assert_called_once()

    @pytest.mark.asyncio
    @patch('thoth.agents.orchestrator.LETTA_AVAILABLE', False)
    async def test_orchestrator_setup_without_letta(self, service_manager):
        """Test orchestrator setup without Letta."""
        orchestrator = ThothOrchestrator(service_manager=service_manager)

        # Should use fallback mode
        assert orchestrator._use_fallback is True

        # Setup should complete without error
        await orchestrator.setup()

    def test_get_registered_tools(self, service_manager):
        """Test getting the registered tools dictionary."""
        registry = LettaToolRegistry(service_manager)

        # Initially empty
        tools = registry.get_registered_tools()
        assert isinstance(tools, dict)
        assert len(tools) == 0

        # Add mock tool
        registry._registered_tools['test_tool'] = {
            'type': 'mcp',
            'category': 'research',
        }

        tools = registry.get_registered_tools()
        assert len(tools) == 1
        assert 'test_tool' in tools
        assert tools['test_tool']['type'] == 'mcp'

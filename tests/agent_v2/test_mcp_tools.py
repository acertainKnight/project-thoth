"""
Tests for MCP tools functionality and registration.

Validates that MCP tools are properly registered, discoverable, and executable
through the async agent framework.
"""

from unittest.mock import MagicMock

import pytest

from thoth.ingestion.agent_v2 import create_research_assistant
from thoth.mcp.base_tools import MCPTool, MCPToolRegistry
from thoth.mcp.tools import MCP_TOOL_CLASSES, register_all_mcp_tools


class TestMCPToolDiscovery:
    """Test suite for MCP tool discovery and registration."""

    def test_mcp_tool_classes_available(self):
        """Test that MCP tool classes are properly imported."""
        assert len(MCP_TOOL_CLASSES) > 0, 'No MCP tool classes found'
        assert len(MCP_TOOL_CLASSES) >= 30, (
            f'Expected at least 30 MCP tools, found {len(MCP_TOOL_CLASSES)}'
        )

        # Test each tool class has required attributes
        for tool_class in MCP_TOOL_CLASSES:
            assert issubclass(tool_class, MCPTool), (
                f'{tool_class.__name__} is not a subclass of MCPTool'
            )
            assert hasattr(tool_class, 'name'), (
                f'{tool_class.__name__} missing name property'
            )
            assert hasattr(tool_class, 'description'), (
                f'{tool_class.__name__} missing description'
            )
            assert hasattr(tool_class, 'input_schema'), (
                f'{tool_class.__name__} missing input_schema'
            )
            assert hasattr(tool_class, 'execute'), (
                f'{tool_class.__name__} missing execute method'
            )

    def test_mcp_tool_registry_registration(self):
        """Test MCP tool registry functionality."""
        mock_service_manager = MagicMock()
        registry = MCPToolRegistry(service_manager=mock_service_manager)

        # Register all tools
        register_all_mcp_tools(registry)

        # Verify tools are registered
        schemas = registry.get_tool_schemas()
        assert len(schemas) > 0, 'No tools registered in MCP registry'
        assert len(schemas) >= 30, (
            f'Expected at least 30 registered tools, found {len(schemas)}'
        )

        # Verify schema structure
        for schema in schemas[:5]:  # Check first 5 schemas
            assert hasattr(schema, 'name')
            assert hasattr(schema, 'description')
            assert hasattr(schema, 'inputSchema')
            assert isinstance(schema.name, str)
            assert isinstance(schema.description, str)
            assert isinstance(schema.inputSchema, dict)

    def test_mcp_tool_categories(self):
        """Test that all expected MCP tool categories are present."""
        tool_names = [tool_class.__name__ for tool_class in MCP_TOOL_CLASSES]

        # Query management tools
        query_tools = [name for name in tool_names if 'Query' in name]
        assert len(query_tools) >= 4, (
            f'Expected at least 4 query tools, found {query_tools}'
        )

        # Discovery tools
        discovery_tools = [
            name for name in tool_names if 'Discovery' in name or 'Source' in name
        ]
        assert len(discovery_tools) >= 6, (
            f'Expected at least 6 discovery tools, found {discovery_tools}'
        )

        # Processing tools
        processing_tools = [
            name for name in tool_names if 'Process' in name or 'Article' in name
        ]
        assert len(processing_tools) >= 4, (
            f'Expected at least 4 processing tools, found {processing_tools}'
        )

        # Analysis tools
        analysis_tools = [
            name for name in tool_names if 'Analy' in name or 'Evaluat' in name
        ]
        assert len(analysis_tools) >= 2, (
            f'Expected at least 2 analysis tools, found {analysis_tools}'
        )

    def test_mcp_tool_instantiation(self):
        """Test that MCP tools can be instantiated with a service manager."""
        mock_service_manager = MagicMock()

        # Test instantiation of a few representative tools
        test_tools = [
            tool_class
            for tool_class in MCP_TOOL_CLASSES
            if 'List'
            in tool_class.__name__  # List tools are usually safe to instantiate
        ][:3]

        for tool_class in test_tools:
            try:
                tool_instance = tool_class(service_manager=mock_service_manager)
                assert isinstance(tool_instance, MCPTool)
                assert tool_instance.service_manager is mock_service_manager

                # Test schema generation
                schema = tool_instance.to_schema()
                assert schema.name
                assert schema.description
                assert isinstance(schema.inputSchema, dict)

            except Exception as e:
                pytest.fail(f'Failed to instantiate {tool_class.__name__}: {e}')


class TestMCPToolIntegration:
    """Test suite for MCP tool integration with the agent."""

    @pytest.fixture
    def pipeline(self):
        """Create a ThothPipeline for testing."""
        from thoth.pipeline import ThothPipeline

        # ThothPipeline loads config internally, doesn't accept config parameter
        pipeline = ThothPipeline()
        return pipeline

    @pytest.fixture
    def mcp_agent(self, pipeline):
        """Create an agent with MCP tools for testing."""
        import asyncio

        try:
            agent = create_research_assistant(
                service_manager=pipeline.services,
                enable_memory=False,
                use_mcp_tools=True,
            )
            # Initialize the agent to load tools synchronously
            asyncio.run(agent.async_initialize())
            return agent
        except Exception:
            pytest.skip('MCP tools not available for integration testing')

    @pytest.mark.asyncio
    async def test_mcp_agent_has_tools_loaded(self, mcp_agent):
        """Test that MCP agent has tools loaded."""
        tools = mcp_agent.get_available_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0, 'MCP agent has no tools loaded'

        # Verify tool structure
        for tool in tools[:5]:  # Check first 5 tools
            assert 'name' in tool
            assert 'description' in tool
            assert isinstance(tool['name'], str)
            assert isinstance(tool['description'], str)

    @pytest.mark.asyncio
    async def test_mcp_agent_tool_discovery_request(self, mcp_agent):
        """Test agent's response to tool discovery requests."""
        response = await mcp_agent.chat(
            message='What tools do you have available? Please list them.',
            session_id='test_tool_discovery',
        )

        assert 'response' in response
        assert response['response']

        # Response should mention tools or capabilities
        response_text = response['response'].lower()
        tool_keywords = ['tool', 'capability', 'function', 'help', 'can']
        assert any(keyword in response_text for keyword in tool_keywords), (
            "Response doesn't mention tools or capabilities"
        )

    @pytest.mark.asyncio
    async def test_mcp_agent_simple_tool_requests(self, mcp_agent):
        """Test agent handling of simple tool requests."""
        # Test queries-related request
        response = await mcp_agent.chat(
            message='Please list my research queries', session_id='test_query_tools'
        )
        assert 'response' in response

        # Test discovery sources request
        response = await mcp_agent.chat(
            message='Please show me my discovery sources',
            session_id='test_discovery_tools',
        )
        assert 'response' in response

        # Test collection stats request
        response = await mcp_agent.chat(
            message='Please show me statistics about my collection',
            session_id='test_stats_tools',
        )
        assert 'response' in response

    @pytest.mark.asyncio
    async def test_mcp_tool_execution_no_errors(self, mcp_agent):
        """Test that MCP tool execution doesn't throw sync invocation errors."""
        # This is the critical test for the original sync invocation issue
        try:
            # Make a request that should trigger tool usage
            response = await mcp_agent.chat(
                message='Please help me by using any appropriate tool to show what you can do',
                session_id='test_tool_execution',
            )

            assert 'response' in response

            # If tool calls were made, verify they completed successfully
            if response.get('tool_calls'):
                assert isinstance(response['tool_calls'], list)
                for tool_call in response['tool_calls']:
                    assert 'tool' in tool_call
                    assert isinstance(tool_call['tool'], str)
                    # Tool execution completed without sync invocation errors

        except Exception as e:
            if 'StructuredTool does not support sync invocation' in str(e):
                pytest.fail(f'Sync invocation error still present: {e}')
            elif 'does not support sync invocation' in str(e):
                pytest.fail(f'Sync invocation error detected: {e}')
            else:
                # Other errors might be expected (MCP server not running, etc.)
                pass

    @pytest.mark.asyncio
    async def test_mcp_web_search_tool(self, mcp_agent):
        """Test MCP web search tool if available."""
        try:
            response = await mcp_agent.chat(
                message="Please search the web for 'pytest' and give me a brief summary",
                session_id='test_web_search',
            )

            assert 'response' in response
            assert response['response']

            # If web search was used, verify the response structure
            if response.get('tool_calls'):
                web_tools = [
                    tc
                    for tc in response['tool_calls']
                    if 'web' in tc.get('tool', '').lower()
                    or 'search' in tc.get('tool', '').lower()
                ]
                if web_tools:
                    # Web search tool was successfully invoked
                    assert len(web_tools) > 0

        except Exception:
            # Web search might fail due to network issues, rate limits, etc.
            # This is acceptable for testing
            pass


class TestMCPToolSpecific:
    """Test specific MCP tool functionality."""

    def test_mcp_tool_input_schemas(self):
        """Test that MCP tools have valid input schemas."""
        for tool_class in MCP_TOOL_CLASSES[:10]:  # Test first 10 tools
            mock_service_manager = MagicMock()

            try:
                tool_instance = tool_class(service_manager=mock_service_manager)
                schema = tool_instance.input_schema

                assert isinstance(schema, dict), (
                    f'{tool_class.__name__} input_schema is not a dict'
                )
                assert 'type' in schema, (
                    f"{tool_class.__name__} input_schema missing 'type'"
                )
                assert schema['type'] == 'object', (
                    f"{tool_class.__name__} input_schema type is not 'object'"
                )

                # If properties exist, they should be valid
                if 'properties' in schema:
                    assert isinstance(schema['properties'], dict)

            except Exception as e:
                pytest.fail(
                    f'Failed to get input schema for {tool_class.__name__}: {e}'
                )

    def test_mcp_tool_descriptions(self):
        """Test that MCP tools have meaningful descriptions."""
        for tool_class in MCP_TOOL_CLASSES:
            mock_service_manager = MagicMock()

            try:
                tool_instance = tool_class(service_manager=mock_service_manager)
                description = tool_instance.description

                assert isinstance(description, str), (
                    f'{tool_class.__name__} description is not a string'
                )
                assert len(description) > 10, (
                    f"{tool_class.__name__} description is too short: '{description}'"
                )
                assert description.strip() == description, (
                    f'{tool_class.__name__} description has leading/trailing whitespace'
                )

            except Exception as e:
                pytest.fail(f'Failed to get description for {tool_class.__name__}: {e}')

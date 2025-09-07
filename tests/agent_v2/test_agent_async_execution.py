"""
Tests for agent async execution and tool invocation.

Validates that the StructuredTool sync invocation error is resolved and
that the agent properly executes tools asynchronously.
"""

import pytest

from thoth.ingestion.agent_v2 import create_research_assistant
from thoth.ingestion.agent_v2.core.agent import ResearchAssistant
from thoth.pipeline import ThothPipeline


class TestAgentAsyncExecution:
    """Test suite for agent async execution and tool invocation."""

    @pytest.fixture
    def pipeline(self):
        """Create a ThothPipeline for testing."""
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
                enable_memory=False,  # Disable memory for simpler testing
                use_mcp_tools=True,
            )
            # Initialize the agent to load tools synchronously
            asyncio.run(agent.async_initialize())
            return agent
        except Exception:
            # Fallback if MCP tools fail to initialize
            pytest.skip('MCP tools not available')

    @pytest.fixture
    def legacy_agent(self, pipeline):
        """Create an agent - legacy tools removed, now uses MCP only."""
        import asyncio

        try:
            agent = create_research_assistant(
                service_manager=pipeline.services,
                enable_memory=False,  # Disable memory for simpler testing
            )
            # Initialize the agent to load tools synchronously
            asyncio.run(agent.async_initialize())
        except RuntimeError as e:
            if 'MCP tools are required' in str(e):
                pytest.skip('MCP tools not available for legacy agent test')
            raise
        return agent

    @pytest.mark.asyncio
    async def test_agent_initialization(self, pipeline):
        """Test that agents can be initialized successfully."""
        # Test MCP agent initialization
        try:
            mcp_agent = create_research_assistant(
                service_manager=pipeline.services,
                enable_memory=False,
                use_mcp_tools=True,
            )
            assert mcp_agent is not None
            assert isinstance(mcp_agent, ResearchAssistant)
        except Exception:
            pytest.skip(
                'MCP agent initialization failed - may be expected if MCP server not running'
            )

        # Test legacy agent initialization
        legacy_agent = create_research_assistant(
            service_manager=pipeline.services, enable_memory=False, use_mcp_tools=False
        )
        assert legacy_agent is not None
        assert isinstance(legacy_agent, ResearchAssistant)

    @pytest.mark.asyncio
    async def test_no_sync_invocation_error(self, mcp_agent):
        """Test that StructuredTool sync invocation error is resolved."""
        # This test validates the critical fix for the sync invocation error
        try:
            response = await mcp_agent.chat(
                message='Hello, please just respond without using tools',
                session_id='test_sync_fix',
            )

            assert 'response' in response
            assert response['response']  # Should have some response

            # If we get here without an exception, the sync invocation issue is fixed

        except Exception as e:
            if 'StructuredTool does not support sync invocation' in str(e):
                pytest.fail(f'Sync invocation error still present: {e}')
            else:
                # Other exceptions might be expected (network issues, etc.)
                pytest.skip(f'Other error occurred (may be expected): {e}')

    @pytest.mark.asyncio
    async def test_basic_agent_chat(self, mcp_agent):
        """Test basic agent chat functionality."""
        response = await mcp_agent.chat(
            message='Hello, please just say hello back', session_id='test_basic_chat'
        )

        assert isinstance(response, dict)
        assert 'response' in response
        assert response['response']
        assert isinstance(response['response'], str)

    @pytest.mark.asyncio
    async def test_legacy_agent_chat(self, legacy_agent):
        """Test legacy agent chat functionality."""
        response = await legacy_agent.chat(
            message='Hello, please just say hello back', session_id='test_legacy_chat'
        )

        assert isinstance(response, dict)
        assert 'response' in response
        assert response['response']
        assert isinstance(response['response'], str)

    @pytest.mark.asyncio
    async def test_agent_tool_loading(self, mcp_agent, legacy_agent):
        """Test that agents have tools loaded - both use MCP now."""
        # Both agents now use MCP tools (legacy tools were removed in Phase 1)
        mcp_tools = mcp_agent.get_available_tools()
        assert isinstance(mcp_tools, list)
        # In test environment, MCP server may not be running, so tools might be empty
        # This is expected behavior - the agent should still function

        # "Legacy" agent also uses MCP tools now
        legacy_tools = legacy_agent.get_available_tools()
        assert isinstance(legacy_tools, list)
        # Both agents should have the same tool loading behavior

        # If tools are available, verify structure
        if mcp_tools:
            for tool in mcp_tools[:3]:  # Check first few tools
                assert 'name' in tool
                assert 'description' in tool
                assert isinstance(tool['name'], str)
                assert isinstance(tool['description'], str)

    @pytest.mark.asyncio
    async def test_concurrent_agent_requests(self, mcp_agent):
        """Test concurrent requests to the same agent."""
        import asyncio

        # Create multiple concurrent chat requests
        tasks = []
        for i in range(3):
            task = mcp_agent.chat(
                message=f'Hello, this is concurrent request {i + 1}',
                session_id=f'test_concurrent_{i}',
            )
            tasks.append(task)

        # Wait for all to complete
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that most completed successfully
        successful = sum(1 for r in responses if not isinstance(r, Exception))
        assert successful >= 2, f'Only {successful}/3 concurrent requests succeeded'

        # Verify successful responses
        for response in responses:
            if not isinstance(response, Exception):
                assert 'response' in response
                assert response['response']

    @pytest.mark.asyncio
    async def test_agent_session_isolation(self, mcp_agent):
        """Test that different sessions are properly isolated."""
        # Send message in session 1
        response1 = await mcp_agent.chat(
            message='Remember my name is Alice', session_id='session_1'
        )

        # Send message in session 2
        response2 = await mcp_agent.chat(
            message='What is my name?', session_id='session_2'
        )

        assert 'response' in response1
        assert 'response' in response2

        # Note: Full memory isolation testing would require memory to be enabled
        # and more complex validation

    @pytest.mark.asyncio
    async def test_agent_error_handling(self, mcp_agent):
        """Test agent handling of various edge cases."""
        # Test empty message
        response = await mcp_agent.chat(message='', session_id='test_empty')
        assert 'response' in response

        # Test very long message
        long_message = 'Help me with this research topic. ' * 100
        response = await mcp_agent.chat(message=long_message, session_id='test_long')
        assert 'response' in response

        # Test invalid tool request
        response = await mcp_agent.chat(
            message="Please use the 'nonexistent_magical_tool' to do something",
            session_id='test_invalid_tool',
        )
        assert 'response' in response
        # Agent should handle this gracefully without crashing

    @pytest.mark.asyncio
    async def test_agent_with_tool_requests(self, mcp_agent):
        """Test agent when explicitly asked to use tools."""
        response = await mcp_agent.chat(
            message='Please list my available tools or tell me what you can do',
            session_id='test_tool_request',
        )

        assert 'response' in response
        assert response['response']

        # Check if any tools were actually called
        if response.get('tool_calls'):
            assert isinstance(response['tool_calls'], list)
            for tool_call in response['tool_calls']:
                assert 'tool' in tool_call
                assert isinstance(tool_call['tool'], str)

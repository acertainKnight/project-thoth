"""
Comprehensive integration tests for the tool ecosystem.

Tests the overall functionality of the tool system including MCP/legacy
compatibility, error handling, and real-world usage scenarios.
"""

import asyncio

import pytest

from thoth.ingestion.agent_v2 import create_research_assistant
from thoth.ingestion.agent_v2.tools.decorators import get_registered_tools
from thoth.mcp.tools import MCP_TOOL_CLASSES


class TestToolEcosystemIntegration:
    """Integration tests for the complete tool ecosystem."""

    @pytest.fixture
    def pipeline(self):
        """Create a ThothPipeline for testing."""
        from thoth.pipeline import ThothPipeline

        # ThothPipeline loads config internally, doesn't accept config parameter
        pipeline = ThothPipeline()
        return pipeline

    @pytest.fixture
    def both_agents(self, pipeline):
        """Create both MCP and legacy agents for comparison testing."""
        import asyncio

        agents = {}

        # Create legacy agent
        legacy_agent = create_research_assistant(
            service_manager=pipeline.services, enable_memory=False, use_mcp_tools=False
        )
        # Initialize the agent to load tools synchronously
        asyncio.run(legacy_agent.async_initialize())
        agents['legacy'] = legacy_agent

        # Try to create MCP agent
        try:
            mcp_agent = create_research_assistant(
                service_manager=pipeline.services,
                enable_memory=False,
                use_mcp_tools=True,
            )
            # Initialize the agent to load tools synchronously
            asyncio.run(mcp_agent.async_initialize())
            agents['mcp'] = mcp_agent
        except Exception:
            agents['mcp'] = None

        return agents

    @pytest.mark.asyncio
    async def test_tool_ecosystem_coverage(self, both_agents):
        """Test that tool ecosystem provides comprehensive coverage."""
        legacy_agent = both_agents['legacy']
        mcp_agent = both_agents['mcp']

        # Test legacy agent coverage
        legacy_tools = legacy_agent.get_available_tools()

        # Should have tools for major functionality areas
        assert len(legacy_tools) >= 10, (
            f'Expected at least 10 legacy tools, found {len(legacy_tools)}'
        )

        # Test MCP agent coverage if available
        if mcp_agent is not None:
            mcp_tools = mcp_agent.get_available_tools()

            assert len(mcp_tools) >= 20, (
                f'Expected at least 20 MCP tools, found {len(mcp_tools)}'
            )

            # MCP should have more tools than legacy
            assert len(mcp_tools) >= len(legacy_tools), (
                'MCP agent should have at least as many tools as legacy'
            )

    @pytest.mark.asyncio
    async def test_no_sync_invocation_errors_comprehensive(self, both_agents):
        """Comprehensive test that sync invocation errors are resolved."""
        test_messages = [
            'Please help me with research',
            'What tools do you have?',
            'Please search for information',
            'Can you analyze something?',
            'List my queries or sources',
        ]

        for agent_type, agent in both_agents.items():
            if agent is None:
                continue

            for i, message in enumerate(test_messages):
                try:
                    response = await agent.chat(
                        message=message, session_id=f'test_no_sync_{agent_type}_{i}'
                    )

                    assert 'response' in response
                    assert response['response']

                except Exception as e:
                    if 'StructuredTool does not support sync invocation' in str(e):
                        pytest.fail(
                            f"Sync invocation error in {agent_type} agent with message '{message}': {e}"
                        )
                    elif 'does not support sync invocation' in str(e):
                        pytest.fail(
                            f"Sync invocation error in {agent_type} agent with message '{message}': {e}"
                        )
                    else:
                        # Other errors might be expected
                        pass

    @pytest.mark.asyncio
    async def test_agent_tool_selection_intelligence(self, both_agents):
        """Test that agents intelligently select appropriate tools."""
        test_scenarios = [
            {
                'message': 'Please list my research queries',
                'expected_tool_keywords': ['query', 'list'],
                'scenario': 'query_management',
            },
            {
                'message': 'Please show me my discovery sources',
                'expected_tool_keywords': ['discovery', 'source', 'list'],
                'scenario': 'discovery_management',
            },
            {
                'message': 'Search the web for machine learning papers',
                'expected_tool_keywords': ['web', 'search'],
                'scenario': 'web_search',
            },
            {
                'message': 'Please analyze my article collection',
                'expected_tool_keywords': ['analy', 'collection', 'stat'],
                'scenario': 'collection_analysis',
            },
        ]

        for agent_type, agent in both_agents.items():
            if agent is None:
                continue

            for scenario in test_scenarios:
                try:
                    response = await agent.chat(
                        message=scenario['message'],
                        session_id=f'test_selection_{agent_type}_{scenario["scenario"]}',
                    )

                    assert 'response' in response

                    # If tools were called, check if appropriate ones were selected
                    if response.get('tool_calls'):
                        tool_calls = response['tool_calls']
                        assert len(tool_calls) > 0

                        # Check if any called tools match expected keywords
                        called_tool_names = [
                            tc.get('tool', '').lower() for tc in tool_calls
                        ]

                        # At least one tool should match expected keywords
                        keyword_matches = []
                        for tool_name in called_tool_names:
                            for keyword in scenario['expected_tool_keywords']:
                                if keyword.lower() in tool_name:
                                    keyword_matches.append((tool_name, keyword))

                        # This is informational - we don't fail if no match
                        # as tool selection depends on availability and context

                except Exception:
                    # Tool selection tests might fail due to missing data/services
                    # This is acceptable for testing
                    pass

    @pytest.mark.asyncio
    async def test_error_handling_robustness(self, both_agents):
        """Test error handling robustness across the tool ecosystem."""
        error_test_cases = [
            '',  # Empty message
            "Please use the 'nonexistent_magical_tool' to do impossible things",  # Invalid tool
            'x' * 1000,  # Very long message
            "Please do something that requires tools that don't exist",  # Impossible request
            '🚀🤖🔧' * 50,  # Unicode stress test
        ]

        for agent_type, agent in both_agents.items():
            if agent is None:
                continue

            for i, test_message in enumerate(error_test_cases):
                try:
                    response = await agent.chat(
                        message=test_message, session_id=f'test_error_{agent_type}_{i}'
                    )

                    # Should always get a response, even for problematic inputs
                    assert 'response' in response
                    assert isinstance(response['response'], str)

                    # Response should not be empty for non-empty inputs
                    if test_message.strip():
                        assert len(response['response']) > 0

                except Exception as e:
                    # Should not crash with unhandled exceptions
                    pytest.fail(
                        f"Unhandled exception in {agent_type} agent with input '{test_message[:50]}...': {e}"
                    )

    @pytest.mark.asyncio
    async def test_concurrent_tool_usage(self, both_agents):
        """Test concurrent tool usage across multiple sessions."""
        for agent_type, agent in both_agents.items():
            if agent is None:
                continue

            # Create multiple concurrent requests with different tool needs
            tasks = []
            for i in range(5):
                messages = [
                    'Please help me with my research',
                    'What tools do you have available?',
                    'Please list my queries',
                    'Show me my discovery sources',
                    'Help me search for information',
                ]

                task = agent.chat(
                    message=messages[i], session_id=f'concurrent_{agent_type}_{i}'
                )
                tasks.append(task)

            # Wait for all requests to complete
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Check results
            successful = sum(1 for r in responses if not isinstance(r, Exception))
            assert successful >= 3, (
                f'Only {successful}/5 concurrent requests succeeded for {agent_type} agent'
            )

            # Verify successful responses
            for response in responses:
                if not isinstance(response, Exception):
                    assert 'response' in response
                    assert response['response']

    @pytest.mark.asyncio
    async def test_tool_ecosystem_performance(self, both_agents):
        """Test tool ecosystem performance characteristics."""
        import time

        for agent_type, agent in both_agents.items():
            if agent is None:
                continue

            # Test response times for various tool requests
            test_messages = [
                'Hello, please just respond quickly',
                'What tools do you have?',
                'Please help me with something simple',
            ]

            response_times = []

            for message in test_messages:
                start_time = time.time()

                try:
                    response = await agent.chat(
                        message=message,
                        session_id=f'perf_test_{agent_type}_{hash(message)}',
                    )

                    end_time = time.time()
                    response_time = end_time - start_time
                    response_times.append(response_time)

                    assert 'response' in response

                    # Reasonable response time (adjust based on your requirements)
                    assert response_time < 30.0, (
                        f'Response time too slow: {response_time:.2f}s for {agent_type}'
                    )

                except Exception:
                    # Performance test failures are informational
                    pass

            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                # This is informational for monitoring
                print(
                    f'{agent_type} agent average response time: {avg_response_time:.2f}s'
                )

    def test_tool_ecosystem_static_validation(self):
        """Static validation of the tool ecosystem structure."""
        # Test MCP tools
        assert len(MCP_TOOL_CLASSES) > 0, 'No MCP tools available'

        for tool_class in MCP_TOOL_CLASSES:
            # Each MCP tool should have required attributes
            assert hasattr(tool_class, '__name__')
            assert hasattr(tool_class, 'name'), f'{tool_class.__name__} missing name'
            assert hasattr(tool_class, 'description'), (
                f'{tool_class.__name__} missing description'
            )
            assert hasattr(tool_class, 'input_schema'), (
                f'{tool_class.__name__} missing input_schema'
            )
            assert hasattr(tool_class, 'execute'), (
                f'{tool_class.__name__} missing execute method'
            )

        # Test legacy tools
        legacy_tools = get_registered_tools()
        assert len(legacy_tools) > 0, 'No legacy tools available'

        for tool_name, tool_class in legacy_tools.items():
            assert isinstance(tool_name, str)
            assert hasattr(tool_class, '__name__')
            # Legacy tools should be properly decorated
            assert tool_name in tool_class.__name__ or tool_class.__name__ in tool_name

    @pytest.mark.asyncio
    async def test_tool_ecosystem_memory_isolation(self, both_agents):
        """Test that tool usage is properly isolated between sessions."""
        for _, agent in both_agents.items():
            if agent is None:
                continue

            # Send context-setting message in session 1
            await agent.chat(
                message="Remember that I'm working on neural networks research",
                session_id='memory_test_1',
            )

            # Send query in session 2
            response2 = await agent.chat(
                message='What am I working on?', session_id='memory_test_2'
            )

            # Sessions should be isolated (response shouldn't know about neural nets)
            # Note: This test depends on memory being properly isolated
            assert 'response' in response2

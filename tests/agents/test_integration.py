"""
Integration tests for the complete agent system.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from thoth.agents.orchestrator import ThothOrchestrator
from thoth.agents.subagent_factory import SubagentFactory
from thoth.services.service_manager import ServiceManager
from thoth.tools.letta_registration import LettaToolRegistry


class TestAgentSystemIntegration:
    """Integration tests for the complete agent system."""

    @pytest.fixture
    def service_manager(self):
        """Mock service manager with realistic services."""
        manager = Mock(spec=ServiceManager)

        # Mock LLM service
        manager.llm_service = Mock()
        manager.llm_service.chat = AsyncMock(return_value='Mock LLM response')

        # Mock RAG service
        manager.rag_service = Mock()
        manager.rag_service.search = AsyncMock(return_value=[])

        # Mock discovery service
        manager.discovery_service = Mock()
        manager.discovery_service.discover_papers = AsyncMock(return_value=[])

        # Mock Letta service
        manager.letta_service = Mock()
        manager.letta_service.initialize = AsyncMock()

        # Mock get_service method to return the mocked services
        def mock_get_service(service_name):
            if service_name == 'letta':
                return manager.letta_service
            elif service_name == 'llm':
                return manager.llm_service
            elif service_name == 'rag':
                return manager.rag_service
            elif service_name == 'discovery':
                return manager.discovery_service
            return Mock()

        manager.get_service = Mock(side_effect=mock_get_service)

        return manager

    @pytest.fixture
    def workspace_dir(self, tmp_path):
        """Create temporary workspace directory."""
        workspace = tmp_path / 'workspace'
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    @pytest.fixture
    def mock_letta_client(self):
        """Mock Letta client with realistic API."""
        client = Mock()

        # Mock agents API
        client.agents = Mock()
        client.agents.list = Mock(return_value=[])
        client.agents.create = Mock(
            return_value=Mock(id='agent_123', name='test-agent')
        )
        client.agents.get = Mock(return_value=Mock(id='agent_123'))

        # Mock tools API
        client.tools = Mock()
        client.tools.create = Mock(return_value=Mock(id='tool_123'))

        return client

    @pytest.mark.asyncio
    @patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True)
    @patch('thoth.agents.subagent_factory.LETTA_AVAILABLE', True)
    @patch('thoth.tools.letta_registration.LETTA_AVAILABLE', True)
    async def test_complete_agent_creation_workflow(
        self, service_manager, workspace_dir, mock_letta_client
    ):
        """Test the complete workflow from orchestrator setup to agent creation."""

        with (
            patch(
                'thoth.agents.orchestrator.LettaClient', return_value=mock_letta_client
            ),
            patch(
                'thoth.tools.letta_registration.register_all_letta_tools'
            ) as mock_register_tools,
        ):
            # Mock tool registry
            mock_tool_registry = Mock(spec=LettaToolRegistry)
            mock_tool_registry.get_tools_for_agent_type = Mock(
                return_value=[
                    'search_articles',
                    'extract_citations',
                    'analyze_document',
                ]
            )
            mock_register_tools.return_value = mock_tool_registry

            # Initialize orchestrator
            orchestrator = ThothOrchestrator(
                service_manager=service_manager, workspace_dir=workspace_dir
            )

            # Mock the setup process
            with (
                patch.object(orchestrator, '_init_main_agent') as mock_init_main,
                patch.object(orchestrator, '_load_system_agents') as mock_load_system,
            ):
                # Mock _init_main_agent to set main_agent_id
                async def mock_init_main_agent():
                    orchestrator.main_agent_id = 'main_agent_123'
                    return 'main_agent_123'

                mock_init_main.side_effect = mock_init_main_agent
                mock_load_system.return_value = None

                # Setup should create tool registry and agent factory
                await orchestrator.setup()

                assert orchestrator.unified_registry is not None
                assert orchestrator.agent_factory is not None
                assert orchestrator.main_agent_id is not None

                # Test agent creation through message handling
                with patch.object(
                    orchestrator.agent_factory, 'create_from_chat'
                ) as mock_create:
                    mock_create.return_value = (
                        '✅ **Created @test-agent**\n\n**Description:** Test agent'
                    )

                    response = await orchestrator.handle_message(
                        message='create an agent that analyzes citations',
                        user_id='test_user',
                    )

                    assert '**Created @test-agent**' in response
                    mock_create.assert_called_once_with(
                        'create an agent that analyzes citations', 'test_user'
                    )

    @pytest.mark.asyncio
    @patch('thoth.tools.letta_registration.LETTA_AVAILABLE', True)
    async def test_tool_registration_integration(
        self, service_manager, mock_letta_client
    ):
        """Test tool registration system integration."""

        with patch(
            'thoth.tools.letta_registration.MCP_TOOL_CLASSES', []
        ):  # Empty for test
            # Create tool registry
            from thoth.tools.letta_registration import register_all_letta_tools

            tool_registry = await register_all_letta_tools(
                service_manager=service_manager, letta_client=mock_letta_client
            )

            assert isinstance(tool_registry, LettaToolRegistry)
            assert tool_registry.service_manager == service_manager
            assert tool_registry.letta_client == mock_letta_client

            # Test tool categorization
            assert tool_registry._categorize_tool('search_articles') == 'research'
            assert tool_registry._categorize_tool('extract_citations') == 'citation'

            # Test agent type tool selection
            research_tools = tool_registry.get_tools_for_agent_type('research')
            analysis_tools = tool_registry.get_tools_for_agent_type('analysis')

            # Should return appropriate tools for each type
            assert isinstance(research_tools, list)
            assert isinstance(analysis_tools, list)

    @pytest.mark.asyncio
    @patch('thoth.agents.subagent_factory.LETTA_AVAILABLE', True)
    async def test_subagent_factory_integration(
        self, service_manager, workspace_dir, mock_letta_client
    ):
        """Test subagent factory integration with tool registry."""

        # Create tool registry
        tool_registry = Mock(spec=LettaToolRegistry)
        tool_registry.get_tools_for_agent = Mock(
            return_value=['search_articles', 'extract_citations', 'format_citations']
        )

        # Create factory
        factory = SubagentFactory(
            letta_client=mock_letta_client,
            workspace_dir=workspace_dir,
            service_manager=service_manager,
            tool_registry=tool_registry,
        )

        # Mock agent creation in Letta
        mock_letta_agent = Mock(id='agent_456')
        mock_letta_client.agents.create.return_value = mock_letta_agent

        with patch.object(factory, '_agent_exists', return_value=False):
            response = await factory.create_from_chat(
                'create a citation analysis agent for medical research',
                'researcher_789',
            )

            # Should successfully create agent
            assert 'Created @' in response
            assert 'citation' in response.lower()

            # Should have created Letta agent
            mock_letta_client.agents.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_integration(self, service_manager, workspace_dir):
        """Test that the system works gracefully without Letta."""

        with (
            patch('thoth.agents.orchestrator.LETTA_AVAILABLE', False),
            patch('thoth.agents.subagent_factory.LETTA_AVAILABLE', False),
            patch('thoth.tools.letta_registration.LETTA_AVAILABLE', False),
        ):
            # Initialize orchestrator without Letta
            orchestrator = ThothOrchestrator(
                service_manager=service_manager, workspace_dir=workspace_dir
            )

            # Should initialize in fallback mode
            assert orchestrator._use_fallback is True

            # Setup should complete without error
            await orchestrator.setup()

            # Should remain in fallback mode after setup
            assert orchestrator._use_fallback is True

            # Message handling should work with fallback responses
            response = await orchestrator.handle_message(
                message='create an agent', user_id='test_user'
            )

            assert 'Letta agent system is not available' in response

            # Should handle all message types gracefully
            messages = [
                'create an agent that analyzes papers',
                '@test-agent help me',
                'list my agents',
                'general research question',
            ]

            for message in messages:
                response = await orchestrator.handle_message(message, 'test_user')
                assert isinstance(response, str)
                assert len(response) > 0

    @pytest.mark.asyncio
    async def test_error_resilience(self, service_manager, workspace_dir):  # noqa: ARG002
        """Test system resilience to errors."""

        with patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True):
            # Mock service manager to fail when getting Letta service
            failing_service_manager = Mock(spec=ServiceManager)
            failing_service_manager.get_service = Mock(
                side_effect=Exception('Service unavailable')
            )

            orchestrator = ThothOrchestrator(
                service_manager=failing_service_manager, workspace_dir=workspace_dir
            )

            # Setup should handle errors gracefully and fall back
            await orchestrator.setup()

            # Should fall back to basic mode
            assert orchestrator._use_fallback is True

            # Should still handle messages
            response = await orchestrator.handle_message('test', 'user')
            assert isinstance(response, str)

    @pytest.mark.asyncio
    @patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True)
    async def test_agent_mention_routing(
        self, service_manager, workspace_dir, mock_letta_client
    ):
        """Test that @agent mentions are properly routed."""

        with patch(
            'thoth.agents.orchestrator.LettaClient', return_value=mock_letta_client
        ):
            orchestrator = ThothOrchestrator(
                service_manager=service_manager, workspace_dir=workspace_dir
            )
            orchestrator._use_fallback = False
            orchestrator.letta_client = mock_letta_client

            # Mock the agents list call
            mock_agent = Mock()
            mock_agent.name = 'citation-agent'
            mock_agent.id = 'agent_123'
            mock_letta_client.agents.list.return_value = [mock_agent]

            # Mock the messages.create call
            mock_response = Mock()
            mock_message = Mock()
            mock_message.role = 'assistant'
            mock_message.content = 'Analysis complete'
            mock_response.messages = [mock_message]
            mock_letta_client.agents.messages.create.return_value = mock_response

            response = await orchestrator.handle_message(
                message="@citation-agent analyze this paper's references",
                user_id='researcher',
            )

            assert '[@citation-agent]:' in response
            assert 'Analysis complete' in response
            mock_letta_client.agents.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_performance_with_multiple_agents(
        self, service_manager, workspace_dir
    ):
        """Test system performance with multiple agents."""

        with patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True):
            mock_letta_client = Mock()
            mock_letta_client.agents = Mock()
            mock_letta_client.agents.create = Mock()

            with patch(
                'thoth.agents.orchestrator.LettaClient', return_value=mock_letta_client
            ):
                orchestrator = ThothOrchestrator(
                    service_manager=service_manager, workspace_dir=workspace_dir
                )

                # Mock setup
                with (
                    patch.object(orchestrator, '_init_main_agent') as mock_init_main,
                    patch.object(
                        orchestrator, '_load_system_agents'
                    ) as mock_load_system,
                    patch(
                        'thoth.tools.unified_registry.initialize_unified_registry'
                    ) as mock_registry,
                ):
                    # Mock _init_main_agent to set main_agent_id
                    async def mock_init_main_agent():
                        orchestrator.main_agent_id = 'main_agent_123'
                        return 'main_agent_123'

                    mock_init_main.side_effect = mock_init_main_agent
                    mock_load_system.return_value = None
                    mock_registry.return_value = Mock()

                    await orchestrator.setup()

                    # Simulate creating multiple agents quickly
                    agent_descriptions = [
                        'create a citation analysis agent',
                        'create a paper discovery agent',
                        'create a research synthesis agent',
                        'create a reference formatting agent',
                    ]

                    # Mock agent factory
                    orchestrator.agent_factory = Mock()
                    orchestrator.agent_factory.create_from_chat = AsyncMock(
                        return_value='✅ Created agent successfully'
                    )

                    # Create agents concurrently
                    import asyncio

                    tasks = [
                        orchestrator.handle_message(desc, f'user_{i}')
                        for i, desc in enumerate(agent_descriptions)
                    ]

                    responses = await asyncio.gather(*tasks)

                    # All should complete successfully
                    assert len(responses) == 4
                    for response in responses:
                        assert isinstance(response, str)
                        assert '✅' in response

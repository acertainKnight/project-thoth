"""
Tests for ThothOrchestrator class.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from thoth.agents.orchestrator import ThothOrchestrator
from thoth.services.service_manager import ServiceManager


class TestThothOrchestrator:
    """Test the ThothOrchestrator class."""

    @pytest.fixture
    def service_manager(self):
        """Mock service manager."""
        return Mock(spec=ServiceManager)

    @pytest.fixture
    def workspace_dir(self, tmp_path):
        """Create a temporary workspace directory."""
        return tmp_path / 'workspace'

    @pytest.fixture
    def mock_letta_client(self):
        """Mock Letta client."""
        client = Mock()
        client.agents = Mock()
        client.agents.list = Mock(return_value=[])
        client.agents.create = Mock()
        client.agents.get = Mock()
        return client

    def test_init_without_letta(self, service_manager, workspace_dir):
        """Test orchestrator initialization without Letta."""
        with patch('thoth.agents.orchestrator.LETTA_AVAILABLE', False):
            orchestrator = ThothOrchestrator(
                service_manager=service_manager, workspace_dir=workspace_dir
            )

            assert orchestrator._use_fallback is True
            assert orchestrator.letta_client is None
            assert orchestrator.main_agent_id is None

    @pytest.mark.asyncio
    @patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True)
    async def test_init_with_letta(
        self, service_manager, workspace_dir, mock_letta_client
    ):
        """Test orchestrator initialization with Letta."""
        with patch(
            'thoth.agents.orchestrator.LettaClient', return_value=mock_letta_client
        ):
            orchestrator = ThothOrchestrator(
                service_manager=service_manager,
                workspace_dir=workspace_dir,
            )

            assert orchestrator._use_fallback is False
            assert orchestrator.letta_client is None  # Not set until setup()
            assert orchestrator.service_manager == service_manager

    @pytest.mark.asyncio
    async def test_setup_fallback_mode(self, service_manager, workspace_dir):
        """Test setup in fallback mode."""
        orchestrator = ThothOrchestrator(
            service_manager=service_manager, workspace_dir=workspace_dir
        )
        orchestrator._use_fallback = True

        # Should complete without error
        await orchestrator.setup()

    @pytest.mark.asyncio
    @patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True)
    async def test_setup_with_letta(
        self, service_manager, workspace_dir, mock_letta_client
    ):
        """Test setup with Letta client."""
        with (
            patch(
                'thoth.agents.orchestrator.LettaClient', return_value=mock_letta_client
            ),
            patch(
                'thoth.tools.letta_registration.register_all_letta_tools',
                new_callable=AsyncMock,
            ) as mock_register,
        ):
            # Mock the registration to return a tool registry
            mock_tool_registry = Mock()
            mock_register.return_value = mock_tool_registry

            # Mock the letta service returned by service manager
            mock_letta_service = Mock()
            mock_letta_service.initialize = AsyncMock()
            mock_letta_service.get_client.return_value = mock_letta_client
            service_manager.get_service.return_value = mock_letta_service

            orchestrator = ThothOrchestrator(
                service_manager=service_manager, workspace_dir=workspace_dir
            )
            orchestrator._use_fallback = False

            with (
                patch.object(orchestrator, '_init_main_agent') as mock_init_main,
                patch.object(orchestrator, '_load_system_agents') as mock_load_system,
                patch.object(
                    orchestrator, '_setup_memory_management'
                ) as mock_memory_setup,
                patch.object(orchestrator.agent_factory, 'setup') as mock_factory_setup,
                patch(
                    'thoth.agents.orchestrator.initialize_unified_registry'
                ) as mock_unified_registry,
            ):
                mock_init_main.return_value = AsyncMock()
                mock_load_system.return_value = AsyncMock()
                mock_memory_setup.return_value = AsyncMock()
                mock_factory_setup.return_value = AsyncMock()
                mock_unified_registry.return_value = AsyncMock(
                    return_value=mock_tool_registry
                )

                await orchestrator.setup()

                # Verify setup steps were called
                mock_unified_registry.assert_called_once_with(
                    service_manager, mock_letta_client
                )
                mock_init_main.assert_called_once()
                mock_load_system.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_fallback(self, service_manager, workspace_dir):
        """Test message handling in fallback mode."""
        orchestrator = ThothOrchestrator(
            service_manager=service_manager, workspace_dir=workspace_dir
        )
        orchestrator._use_fallback = True

        response = await orchestrator.handle_message(
            message='test message', user_id='test_user'
        )

        assert 'Letta agent system is not available' in response

    @pytest.mark.asyncio
    @patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True)
    async def test_handle_agent_creation_message(
        self, service_manager, workspace_dir, mock_letta_client
    ):
        """Test handling agent creation messages."""
        orchestrator = ThothOrchestrator(
            service_manager=service_manager, workspace_dir=workspace_dir
        )
        orchestrator._use_fallback = False
        orchestrator.client = mock_letta_client

        # Mock agent factory
        mock_agent_factory = Mock()
        mock_agent_factory.create_from_chat = AsyncMock(
            return_value='✅ Created @test-agent'
        )
        orchestrator.agent_factory = mock_agent_factory

        response = await orchestrator.handle_message(
            message='create an agent that analyzes citations', user_id='test_user'
        )

        assert '✅ Created @test-agent' in response
        mock_agent_factory.create_from_chat.assert_called_once()

    @pytest.mark.asyncio
    @patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True)
    async def test_handle_agent_mention_message(
        self, service_manager, workspace_dir, mock_letta_client
    ):
        """Test handling @agent mention messages."""
        orchestrator = ThothOrchestrator(
            service_manager=service_manager, workspace_dir=workspace_dir
        )
        orchestrator._use_fallback = False
        orchestrator.letta_client = mock_letta_client

        # Mock routing to agent
        with patch.object(orchestrator, '_route_to_agent') as mock_route:
            mock_route.return_value = '[@test-agent]: Agent response'

            response = await orchestrator.handle_message(
                message='@test-agent analyze this paper', user_id='test_user'
            )

            assert '[@test-agent]: Agent response' in response
            mock_route.assert_called_once_with(
                '@test-agent analyze this paper', 'test-agent', 'test_user'
            )

    @pytest.mark.asyncio
    @patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True)
    async def test_handle_list_agents_message(
        self, service_manager, workspace_dir, mock_letta_client
    ):
        """Test handling list agents messages."""
        orchestrator = ThothOrchestrator(
            service_manager=service_manager, workspace_dir=workspace_dir
        )
        orchestrator._use_fallback = False
        orchestrator.client = mock_letta_client

        with patch.object(orchestrator, '_list_available_agents') as mock_list:
            mock_list.return_value = (
                '🤖 **Available Agents**\n\n**System Agents:**\n...'
            )

            response = await orchestrator.handle_message(
                message='list agents', user_id='test_user'
            )

            assert '🤖 **Available Agents**' in response
            mock_list.assert_called_once_with('test_user')

    @pytest.mark.asyncio
    @patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True)
    async def test_handle_main_agent_message(
        self, service_manager, workspace_dir, mock_letta_client
    ):
        """Test routing to main agent for general messages."""
        orchestrator = ThothOrchestrator(
            service_manager=service_manager, workspace_dir=workspace_dir
        )
        orchestrator._use_fallback = False
        orchestrator.letta_client = mock_letta_client

        # Mock main agent
        orchestrator.main_agent_id = 'main_agent_123'

        # Mock the letta client messages.create call
        mock_response = Mock()
        mock_message = Mock()
        mock_message.role = 'assistant'
        mock_message.content = 'Main agent response'
        mock_response.messages = [mock_message]
        mock_letta_client.agents.messages.create.return_value = mock_response

        with patch.object(orchestrator, '_auto_select_agent') as mock_auto:
            mock_auto.return_value = None  # No auto-selection

            response = await orchestrator.handle_message(
                message='general research question', user_id='test_user'
            )

            assert response == 'Main agent response'
            mock_letta_client.agents.messages.create.assert_called_once_with(
                agent_id='main_agent_123',
                messages=[{'role': 'user', 'content': 'general research question'}],
            )

    def test_is_agent_creation(self, service_manager, workspace_dir):
        """Test agent creation pattern detection."""
        orchestrator = ThothOrchestrator(
            service_manager=service_manager, workspace_dir=workspace_dir
        )

        # Test positive cases
        assert orchestrator._is_agent_creation('create an agent that does X')
        assert orchestrator._is_agent_creation('make a new agent for citations')
        assert orchestrator._is_agent_creation('build an agent to analyze papers')
        assert orchestrator._is_agent_creation('I need a new agent that can help')
        assert orchestrator._is_agent_creation('add an agent for discovery')

        # Test negative cases
        assert not orchestrator._is_agent_creation('analyze this paper')
        assert not orchestrator._is_agent_creation('search for papers')
        assert not orchestrator._is_agent_creation('what agents are available')

    def test_extract_agent_mentions(self, service_manager, workspace_dir):
        """Test @agent mention extraction."""
        orchestrator = ThothOrchestrator(
            service_manager=service_manager, workspace_dir=workspace_dir
        )

        # Test valid mentions
        assert orchestrator._extract_agent_mentions('@citation-analyzer help me') == [
            'citation-analyzer'
        ]
        assert orchestrator._extract_agent_mentions('@discovery find papers') == [
            'discovery'
        ]
        assert orchestrator._extract_agent_mentions(
            'use @research-assistant and @citation-helper'
        ) == ['research-assistant', 'citation-helper']

        # Test invalid mentions
        assert (
            orchestrator._extract_agent_mentions('@agent generic mention') == []
        )  # Filters out generic @agent
        assert orchestrator._extract_agent_mentions('analyze papers') == []
        assert (
            orchestrator._extract_agent_mentions('email@domain.com') == []
        )  # Not a valid agent mention

    def test_is_list_agents(self, service_manager, workspace_dir):
        """Test list agents pattern detection."""
        orchestrator = ThothOrchestrator(
            service_manager=service_manager, workspace_dir=workspace_dir
        )

        # Test positive cases
        assert orchestrator._is_list_agents('list agents')
        assert orchestrator._is_list_agents('show available agents')
        assert orchestrator._is_list_agents('what agents do I have')
        assert orchestrator._is_list_agents('my agents')

        # Test negative cases
        assert not orchestrator._is_list_agents('create an agent')
        assert not orchestrator._is_list_agents('@agent help me')
        assert not orchestrator._is_list_agents('analyze papers')

    @pytest.mark.asyncio
    @patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True)
    async def test_error_handling(
        self, service_manager, workspace_dir, mock_letta_client
    ):
        """Test error handling in message processing."""
        orchestrator = ThothOrchestrator(
            service_manager=service_manager, workspace_dir=workspace_dir
        )
        orchestrator._use_fallback = False
        orchestrator.letta_client = mock_letta_client

        # Mock agent factory to raise an exception
        mock_agent_factory = Mock()
        mock_agent_factory.create_from_chat = AsyncMock(
            side_effect=Exception('Test error')
        )
        orchestrator.agent_factory = mock_agent_factory

        response = await orchestrator.handle_message(
            message='create an agent', user_id='test_user'
        )

        assert 'Error processing your request' in response
        assert 'Test error' in response


class TestOrchestrationIntegration:
    """Integration tests for orchestration with other components."""

    @pytest.mark.asyncio
    @patch('thoth.agents.orchestrator.LETTA_AVAILABLE', True)
    async def test_full_setup_integration(self):
        """Test full setup with mocked dependencies."""
        service_manager = Mock(spec=ServiceManager)
        workspace_dir = Path('/tmp/test_workspace')

        with (
            patch('thoth.agents.orchestrator.LettaClient') as mock_letta_class,
            patch(
                'thoth.tools.letta_registration.register_all_letta_tools',
                new_callable=AsyncMock,
            ) as mock_register,
        ):
            mock_letta_client = Mock()
            mock_letta_class.return_value = mock_letta_client

            mock_tool_registry = Mock()
            mock_register.return_value = mock_tool_registry

            # Mock the letta service returned by service manager
            mock_letta_service = Mock()
            mock_letta_service.initialize = AsyncMock()
            mock_letta_service.get_client.return_value = mock_letta_client
            service_manager.get_service.return_value = mock_letta_service

            orchestrator = ThothOrchestrator(
                service_manager=service_manager, workspace_dir=workspace_dir
            )
            orchestrator._use_fallback = False

            with (
                patch.object(orchestrator, '_init_main_agent') as mock_init_main,
                patch.object(orchestrator, '_load_system_agents') as mock_load_system,
                patch.object(
                    orchestrator, '_setup_memory_management'
                ) as mock_memory_setup,
                patch.object(orchestrator.agent_factory, 'setup') as mock_factory_setup,
                patch(
                    'thoth.agents.orchestrator.initialize_unified_registry'
                ) as mock_unified_registry,
            ):
                mock_init_main.return_value = AsyncMock()
                mock_load_system.return_value = AsyncMock()
                mock_memory_setup.return_value = AsyncMock()
                mock_factory_setup.return_value = AsyncMock()
                mock_unified_registry.return_value = mock_tool_registry

                await orchestrator.setup()

                # Verify integration setup
                assert orchestrator.unified_registry == mock_tool_registry
                assert orchestrator.agent_factory is not None
                mock_unified_registry.assert_called_once_with(
                    service_manager, mock_letta_client
                )

    @pytest.mark.asyncio
    async def test_fallback_graceful_degradation(self):
        """Test graceful degradation when Letta is not available."""
        service_manager = Mock(spec=ServiceManager)
        workspace_dir = Path('/tmp/test_workspace')

        with patch('thoth.agents.orchestrator.LETTA_AVAILABLE', False):
            orchestrator = ThothOrchestrator(
                service_manager=service_manager, workspace_dir=workspace_dir
            )

            await orchestrator.setup()

            # All operations should work in fallback mode
            response = await orchestrator.handle_message('test', 'user')
            assert 'Letta agent system is not available' in response

            # Should handle all types of messages gracefully
            messages = [
                'create an agent',
                '@test-agent help',
                'list agents',
                'general research question',
            ]

            for message in messages:
                response = await orchestrator.handle_message(message, 'user')
                assert isinstance(response, str)
                assert len(response) > 0

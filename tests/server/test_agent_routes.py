"""
Tests for agent router endpoints.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from thoth.agents.orchestrator import ThothOrchestrator
from thoth.server.app import create_app
from thoth.server.routers import agent


class TestAgentRoutes:
    """Test agent-related API endpoints."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Mock ThothOrchestrator."""
        orchestrator = Mock(spec=ThothOrchestrator)
        orchestrator.handle_message = AsyncMock()
        orchestrator._get_system_agents = AsyncMock(return_value=[])
        orchestrator._get_user_agents = AsyncMock(return_value=[])
        return orchestrator

    @pytest.fixture
    def mock_research_agent(self):
        """Mock research agent."""
        agent = Mock()
        agent.astream_events = AsyncMock()
        return agent

    @pytest.fixture
    def client(self, mock_orchestrator, mock_research_agent):
        """Create test client with mocked dependencies."""
        app = create_app()

        # Set up router dependencies
        agent.set_dependencies(
            agent=mock_research_agent,
            config={'test': 'config'},
            thoth_orchestrator=mock_orchestrator,
        )

        return TestClient(app)

    def test_agent_status_not_initialized(self, client):
        """Test agent status when agent is not initialized."""
        # Clear the global agent
        agent.research_agent = None

        response = client.get('/agents/status')

        assert response.status_code == 503
        data = response.json()
        assert data['status'] == 'not_initialized'
        assert data['agent_initialized'] is False

    def test_agent_status_running(self, client, mock_research_agent):
        """Test agent status when agent is running."""
        # Set up mock agent with tools
        mock_research_agent.get_available_tools = Mock(return_value=['tool1', 'tool2'])
        agent.research_agent = mock_research_agent

        response = client.get('/agents/status')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'running'
        assert data['agent_initialized'] is True
        assert data['tools_count'] == 2

    def test_agent_status_error(self, client, mock_research_agent):
        """Test agent status when agent encounters error."""
        # Mock agent to raise exception
        mock_research_agent.get_available_tools = Mock(
            side_effect=Exception('Test error')
        )
        agent.research_agent = mock_research_agent

        response = client.get('/agents/status')

        assert response.status_code == 500
        data = response.json()
        assert data['status'] == 'error'
        assert data['agent_initialized'] is False
        assert 'Test error' in data['error']

    def test_list_agent_tools(self, client, mock_research_agent):
        """Test listing agent tools."""
        # Mock available tools
        mock_research_agent.get_available_tools = Mock(
            return_value=['search_articles', 'extract_citations', 'analyze_document']
        )
        agent.research_agent = mock_research_agent

        response = client.get('/agents/tools')

        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 3
        assert 'search_articles' in data['tools']
        assert 'extract_citations' in data['tools']
        assert 'analyze_document' in data['tools']

    def test_list_agent_tools_not_initialized(self, client):
        """Test listing tools when agent is not initialized."""
        agent.research_agent = None

        response = client.get('/agents/tools')

        assert response.status_code == 503
        assert 'Research agent not initialized' in response.json()['detail']

    @pytest.mark.asyncio
    async def test_agent_chat_with_orchestrator(self, client, mock_orchestrator):
        """Test agent chat with orchestrator available."""
        # Mock orchestrator response
        mock_orchestrator.handle_message.return_value = (
            'Agent response from orchestrator'
        )
        agent.orchestrator = mock_orchestrator

        response = client.post(
            '/agents/chat',
            json={
                'message': 'create a citation agent',
                'user_id': 'test_user',
                'conversation_id': 'conv_123',
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['response'] == 'Agent response from orchestrator'
        assert data['agent_type'] == 'letta_orchestrated'
        assert data['conversation_id'] == 'conv_123'
        assert data['user_id'] == 'test_user'

    @pytest.mark.asyncio
    async def test_agent_chat_fallback_to_research_agent(
        self, client, mock_research_agent
    ):
        """Test agent chat fallback when orchestrator not available."""
        agent.orchestrator = None
        agent.research_agent = mock_research_agent

        # Mock stream events for research agent
        async def mock_stream_events(*_args, **_kwargs):
            yield {
                'event': 'on_chain_end',
                'data': {
                    'output': {'messages': [{'content': 'Research agent response'}]}
                },
            }

        mock_research_agent.astream_events = mock_stream_events

        response = client.post(
            '/agents/chat',
            json={'message': 'analyze this paper', 'conversation_id': 'conv_456'},
        )

        assert response.status_code == 200
        data = response.json()
        assert data['response'] == 'Research agent response'
        assert data['agent_type'] == 'research'

    def test_agent_chat_no_agents_available(self, client):
        """Test agent chat when no agents are available."""
        agent.orchestrator = None
        agent.research_agent = None

        response = client.post('/agents/chat', json={'message': 'test message'})

        assert response.status_code == 503
        assert (
            'Neither orchestrator nor research agent is available'
            in response.json()['detail']
        )

    @pytest.mark.asyncio
    async def test_list_available_agents_with_orchestrator(
        self, client, mock_orchestrator
    ):
        """Test listing available agents with orchestrator."""
        # Mock system and user agents
        system_agent = Mock()
        system_agent.name = 'citation-analyzer'
        system_agent.description = 'Analyzes citations'
        system_agent.capabilities = ['Citation analysis']

        user_agent = Mock()
        user_agent.name = 'my-research-agent'
        user_agent.description = 'Custom research agent'
        user_agent.capabilities = ['Research', 'Analysis']

        mock_orchestrator._get_system_agents.return_value = [system_agent]
        mock_orchestrator._get_user_agents.return_value = [user_agent]
        agent.orchestrator = mock_orchestrator

        response = client.get('/agents/list')

        assert response.status_code == 200
        data = response.json()
        assert data['total_count'] == 2
        assert data['system_count'] == 1
        assert data['user_count'] == 1

        # Check agent details
        agents = data['agents']
        system_agents = [a for a in agents if a['type'] == 'system']
        user_agents = [a for a in agents if a['type'] == 'user']

        assert len(system_agents) == 1
        assert system_agents[0]['name'] == 'citation-analyzer'
        assert system_agents[0]['description'] == 'Analyzes citations'

        assert len(user_agents) == 1
        assert user_agents[0]['name'] == 'my-research-agent'
        assert user_agents[0]['description'] == 'Custom research agent'

    def test_list_available_agents_no_orchestrator(self, client):
        """Test listing agents when orchestrator is not available."""
        agent.orchestrator = None

        response = client.get('/agents/list')

        assert response.status_code == 200
        data = response.json()
        assert data['agents'] == []
        assert 'Orchestrator not available' in data['message']

    @pytest.mark.asyncio
    async def test_list_agents_error_handling(self, client, mock_orchestrator):
        """Test error handling in agent listing."""
        # Mock orchestrator methods to raise exceptions
        mock_orchestrator._get_system_agents.side_effect = Exception(
            'System agent error'
        )
        mock_orchestrator._get_user_agents.side_effect = Exception('User agent error')
        agent.orchestrator = mock_orchestrator

        response = client.get('/agents/list')

        assert response.status_code == 200  # Should still return 200 with error message
        data = response.json()
        assert data['agents'] == []
        assert 'Error retrieving agents' in data['message']

    def test_agent_config_endpoint(self, client):
        """Test getting agent configuration."""
        with patch('thoth.server.routers.agent.get_config') as mock_get_config:
            # Mock configuration
            mock_config = Mock()
            mock_config.workspace_dir = '/test/workspace'
            mock_config.pdf_dir = '/test/pdfs'
            mock_config.notes_dir = '/test/notes'
            mock_config.queries_dir = '/test/queries'
            mock_config.agent_storage_dir = '/test/agents'

            mock_config.api_server_config = Mock()
            mock_config.api_server_config.host = 'localhost'
            mock_config.api_server_config.port = 8000
            mock_config.api_server_config.base_url = 'http://localhost:8000'

            mock_config.llm_config = Mock()
            mock_config.llm_config.model = 'gpt-4'
            mock_config.research_agent_llm_config = Mock()
            mock_config.research_agent_llm_config.model = 'gpt-4'

            mock_config.discovery_config = Mock()
            mock_config.discovery_config.auto_start_scheduler = True
            mock_config.discovery_config.default_max_articles = 10

            mock_config.api_keys = Mock()
            mock_config.api_keys.mistral_key = 'test_key'
            mock_config.api_keys.openrouter_key = None

            mock_get_config.return_value = mock_config

            response = client.get('/agents/config')

            assert response.status_code == 200
            data = response.json()

            assert data['directories']['workspace_dir'] == '/test/workspace'
            assert data['api_server']['host'] == 'localhost'
            assert data['api_server']['port'] == 8000
            assert data['llm_models']['llm_model'] == 'gpt-4'
            assert data['discovery']['auto_start_scheduler'] is True
            assert data['has_api_keys']['mistral'] is True
            assert data['has_api_keys']['openrouter'] is False

    def test_update_agent_config(self, client):
        """Test updating agent configuration."""
        response = client.post(
            '/agents/config',
            json={
                'api_keys': {'openai': 'new_api_key', 'anthropic': 'another_key'},
                'directories': {'workspace': '/new/workspace'},
                'settings': {'auto_discovery': True, 'max_articles': 20},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['message'] == 'Configuration updated successfully'
        assert 'updated_keys' in data

    def test_sync_obsidian_settings(self, client):
        """Test syncing settings from Obsidian plugin."""
        response = client.post(
            '/agents/sync-settings',
            json={
                'mistralApiKey': 'test_mistral_key',
                'openaiApiKey': 'test_openai_key',
                'thothWorkspaceDir': '/obsidian/workspace',
                'enableAutoDiscovery': True,
                'defaultMaxArticles': 25,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['message'] == 'Settings synchronized successfully'
        assert data['synced_settings_count'] > 0


class TestAgentChatIntegration:
    """Integration tests for agent chat functionality."""

    @pytest.mark.asyncio
    async def test_agent_creation_flow(self):
        """Test complete agent creation flow through API."""
        # Mock orchestrator
        mock_orchestrator = Mock(spec=ThothOrchestrator)
        mock_orchestrator.handle_message = AsyncMock(
            return_value='✅ **Created @citation-analyzer**\n\n**Description:** Analyzes citation patterns'
        )

        # Set up test client
        app = create_app()
        agent.set_dependencies(None, {}, mock_orchestrator)
        client = TestClient(app)

        response = client.post(
            '/agents/chat',
            json={
                'message': 'create a citation analysis agent',
                'user_id': 'researcher_123',
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert 'Created @citation-analyzer' in data['response']

        # Verify orchestrator was called with correct parameters
        mock_orchestrator.handle_message.assert_called_once_with(
            message='create a citation analysis agent',
            user_id='researcher_123',
            thread_id=None,
        )

    @pytest.mark.asyncio
    async def test_agent_interaction_flow(self):
        """Test interacting with created agent through API."""
        # Mock orchestrator
        mock_orchestrator = Mock(spec=ThothOrchestrator)
        mock_orchestrator.handle_message = AsyncMock(
            return_value='[@citation-analyzer]: I found 15 citations in this paper...'
        )

        # Set up test client
        app = create_app()
        agent.set_dependencies(None, {}, mock_orchestrator)
        client = TestClient(app)

        response = client.post(
            '/agents/chat',
            json={
                'message': '@citation-analyzer analyze the references in this paper',
                'user_id': 'researcher_123',
                'conversation_id': 'conv_789',
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert '[@citation-analyzer]:' in data['response']
        assert 'citations' in data['response']

        # Verify orchestrator was called with agent mention
        mock_orchestrator.handle_message.assert_called_once_with(
            message='@citation-analyzer analyze the references in this paper',
            user_id='researcher_123',
            thread_id='conv_789',
        )

    @pytest.mark.asyncio
    async def test_error_handling_in_chat(self):
        """Test error handling in agent chat."""
        # Mock orchestrator to raise exception
        mock_orchestrator = Mock(spec=ThothOrchestrator)
        mock_orchestrator.handle_message = AsyncMock(
            side_effect=Exception('Orchestrator error')
        )

        # Set up test client
        app = create_app()
        agent.set_dependencies(None, {}, mock_orchestrator)
        client = TestClient(app)

        response = client.post('/agents/chat', json={'message': 'test message'})

        assert response.status_code == 500
        assert 'Failed to process agent chat' in response.json()['detail']
        assert 'Orchestrator error' in response.json()['detail']

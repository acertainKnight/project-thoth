import pytest
from fastapi.testclient import TestClient

from thoth.server import app as server_app
from thoth.server import create_app


class DummyAgent:
    async def chat(self, message, session_id=None, model_override=None):  # noqa: ARG002
        return {'response': f'echo:{message}'}

    def get_available_tools(self):
        return ['t1']


class DummyRouter:
    def __init__(self, _config: object):
        """Dummy router."""
        pass

    def select_model(self, _message: str) -> str:
        return 'dummy'


@pytest.fixture
def client(monkeypatch):
    # Create a test app with mocked dependencies
    from thoth.utilities.config import ThothConfig
    from thoth.server.app import app
    
    # Mock the initialization of research agent and other dependencies
    monkeypatch.setattr('thoth.ingestion.agent_v2.core.agent.create_research_assistant_async', 
                       lambda **kwargs: DummyAgent())
    monkeypatch.setattr('thoth.services.llm_router.LLMRouter', lambda config: DummyRouter(config))
    
    # Initialize app state with mocked objects
    app.state.research_agent = DummyAgent()
    app.state.service_manager = None  # Mock service manager if needed
    
    # Initialize chat manager to avoid 503 errors
    from thoth.server.chat_models import ChatPersistenceManager
    from pathlib import Path
    import tempfile
    temp_dir = Path(tempfile.mkdtemp())
    app.state.chat_manager = ChatPersistenceManager(storage_path=temp_dir)
    
    return TestClient(app)


def test_websocket_chat(client):
    with client.websocket_connect('/ws/chat') as ws:
        ws.send_json({'message': 'hi', 'id': 'msg1'})
        data = ws.receive_json()
        assert data['response'] == 'echo:hi'
        assert data['id'] == 'msg1'


def test_websocket_reconnect(client):
    with client.websocket_connect('/ws/chat') as ws:
        ws.send_json({'message': 'one', 'id': 'one'})
        ws.receive_json()
    with client.websocket_connect('/ws/chat') as ws2:
        ws2.send_json({'message': 'two', 'id': 'two'})
        data = ws2.receive_json()
        assert data['response'] == 'echo:two'
        assert data['id'] == 'two'


def test_websocket_status(client):
    with client.websocket_connect('/ws/status') as ws:
        data = ws.receive_json()
        assert data['status'] == 'running'


def test_http_fallback(client):
    resp = client.post('/research/chat', json={'message': 'hi', 'id': 'http'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['response'] == 'echo:hi'
    assert data['id'] == 'http'


def test_websocket_id_echo(client):
    with client.websocket_connect('/ws/chat') as ws:
        ws.send_json({'message': 'idtest', 'id': '123'})
        data = ws.receive_json()
        assert data['response'] == 'echo:idtest'
        assert data['id'] == '123'

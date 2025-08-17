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
    
    # Mock the global objects that the app uses
    monkeypatch.setattr('thoth.server.app.research_agent', DummyAgent())
    monkeypatch.setattr('thoth.server.app.LLMRouter', lambda config: DummyRouter(config))
    monkeypatch.setattr('thoth.server.app.get_config', lambda: ThothConfig())
    
    # Create the app
    test_app = create_app()
    return TestClient(test_app)


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

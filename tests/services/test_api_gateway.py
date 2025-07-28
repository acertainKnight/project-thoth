from thoth.services.api_gateway import ExternalAPIGateway, ServiceError
from thoth.utilities.config import ThothConfig


class DummyResponse:
    def __init__(self, status_code: int, data: dict, reason: str = ''):
        self.status_code = status_code
        self._data = data
        self.reason = reason

    def json(self):
        return self._data

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise ServiceError(f'{self.status_code} Client Error: {self.reason}')


def create_gateway(config: ThothConfig) -> ExternalAPIGateway:
    """Helper to create an API gateway instance for tests."""
    gateway = ExternalAPIGateway(config=config)
    # Ensure a test endpoint exists
    if 'test' not in gateway.endpoints:
        gateway.endpoints['test'] = 'https://example.com'
    return gateway


def test_rate_limiting(monkeypatch, thoth_config: ThothConfig):
    gateway = create_gateway(thoth_config)
    calls = []

    def mock_acquire():
        calls.append(1)

    monkeypatch.setattr(gateway.rate_limiter, 'acquire', mock_acquire)
    monkeypatch.setattr(
        gateway.session,
        'request',
        lambda *_args, **_kwargs: DummyResponse(200, {'ok': True}),
    )

    gateway.get('test', path='one')
    gateway.get('test', path='two')

    assert len(calls) == 2


def test_caching(monkeypatch, thoth_config: ThothConfig):
    gateway = create_gateway(thoth_config)
    responses = [DummyResponse(200, {'num': 1}), DummyResponse(200, {'num': 2})]

    monkeypatch.setattr(gateway.rate_limiter, 'acquire', lambda: None)

    def side_effect(*_a, **_k):
        return responses.pop(0)

    monkeypatch.setattr(gateway.session, 'request', side_effect)

    first = gateway.get('test', path='cache')
    second = gateway.get('test', path='cache')

    assert first == {'num': 1}
    assert second == {'num': 1}
    assert len(responses) == 1


def test_retry_logic(monkeypatch, thoth_config: ThothConfig):
    gateway = create_gateway(thoth_config)
    attempts = []
    monkeypatch.setattr(gateway.rate_limiter, 'acquire', lambda: None)

    def side_effect(*_a, **_k):
        attempts.append(1)
        if len(attempts) < 3:  # Fail first two times
            return DummyResponse(500, {}, reason='Server Error')
        return DummyResponse(200, {'ok': True})

    monkeypatch.setattr(gateway.session, 'request', side_effect)
    monkeypatch.setattr('time.sleep', lambda *_a, **_k: None)

    result = gateway.get('test', path='retry')

    assert result == {'ok': True}
    assert len(attempts) == 3

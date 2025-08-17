"""Tests for service health monitoring."""

import json

from thoth.monitoring import HealthMonitor
from thoth.server.routers.health import health_check
from thoth.services.service_manager import ServiceManager
from thoth.utilities.config import ThothConfig


def _create_manager(config: ThothConfig) -> ServiceManager:
    manager = ServiceManager(config=config)
    manager.initialize()
    return manager


def test_individual_service_health(thoth_config: ThothConfig):
    manager = _create_manager(thoth_config)
    for service in manager.get_all_services().values():
        status = service.health_check()
        assert status['status'] == 'healthy'


def test_health_monitor_overall(thoth_config: ThothConfig):
    manager = _create_manager(thoth_config)
    monitor = HealthMonitor(manager)
    result = monitor.overall_status()
    assert result['healthy'] is True
    assert set(result['services'].keys()) == set(manager.get_all_services().keys())


def test_health_endpoint(monkeypatch, thoth_config: ThothConfig):
    manager = _create_manager(thoth_config)
    # Call health_check directly with the service manager
    response = health_check(service_manager=manager)
    # The response is a JSONResponse object, get the content
    if hasattr(response, 'body'):
        data = json.loads(response.body.decode())
    else:
        # FastAPI JSONResponse stores content differently
        import json as json_module
        data = json_module.loads(response.body) if hasattr(response, 'body') else response.content
    assert data.get('healthy') is True or data.get('status') == 'healthy'
    assert 'services' in data or 'status' in data


def test_health_monitor_failure(monkeypatch, thoth_config: ThothConfig):
    manager = _create_manager(thoth_config)
    svc_name, svc = next(iter(manager.get_all_services().items()))

    def boom():
        raise RuntimeError('fail')

    monkeypatch.setattr(svc, 'health_check', boom)
    monitor = HealthMonitor(manager)
    result = monitor.overall_status()
    assert result['healthy'] is False
    assert result['services'][svc_name]['status'] == 'unhealthy'

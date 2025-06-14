"""Tests for service health monitoring."""

import json

from thoth.monitoring import HealthMonitor
from thoth.services.service_manager import ServiceManager
from thoth.server.api_server import health_check


def _create_manager() -> ServiceManager:
    manager = ServiceManager()
    manager.initialize()
    return manager


def test_individual_service_health():
    manager = _create_manager()
    for service in manager.get_all_services().values():
        status = service.health_check()
        assert status["status"] == "healthy"


def test_health_monitor_overall():
    manager = _create_manager()
    monitor = HealthMonitor(manager)
    result = monitor.overall_status()
    assert result["healthy"] is True
    assert set(result["services"].keys()) == set(manager.get_all_services().keys())


def test_health_endpoint(monkeypatch):
    manager = _create_manager()
    monkeypatch.setattr('thoth.server.api_server.service_manager', manager, raising=False)
    response = health_check()
    data = json.loads(response.body.decode())
    assert data["healthy"] is True
    assert "services" in data


def test_health_monitor_failure(monkeypatch):
    manager = _create_manager()
    svc_name, svc = next(iter(manager.get_all_services().items()))
    def boom():
        raise RuntimeError('fail')
    monkeypatch.setattr(svc, 'health_check', boom)
    monitor = HealthMonitor(manager)
    result = monitor.overall_status()
    assert result["healthy"] is False
    assert result["services"][svc_name]["status"] == "unhealthy"

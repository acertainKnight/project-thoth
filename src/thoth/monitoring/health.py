from __future__ import annotations

from typing import Any

from thoth.services.service_manager import ServiceManager

"""Simple health monitoring utilities."""


class HealthMonitor:
    """Collect health information for all services."""

    def __init__(self, service_manager: ServiceManager) -> None:
        self.service_manager = service_manager

    def check_services(self) -> dict[str, dict[str, Any]]:
        """Run ``health_check`` on all managed services."""
        statuses: dict[str, dict[str, Any]] = {}
        for name, service in self.service_manager.get_all_services().items():
            try:
                statuses[name] = service.health_check()
            except Exception as exc:  # pragma: no cover - defensive
                statuses[name] = {
                    'service': service.__class__.__name__,
                    'status': 'unhealthy',
                    'error': str(exc),
                }
        return statuses

    def overall_status(self) -> dict[str, Any]:
        """Return aggregated health information."""
        services = self.check_services()
        healthy = all(info.get('status') == 'healthy' for info in services.values())
        return {'healthy': healthy, 'services': services}

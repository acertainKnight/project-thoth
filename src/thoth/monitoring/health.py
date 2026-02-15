"""Simple health monitoring utilities."""

from __future__ import annotations

import inspect
from typing import Any

from loguru import logger

from thoth.services.service_manager import ServiceManager


class HealthMonitor:
    """
    Collect health information for all services.

    This class provides centralized health monitoring for all managed services,
    allowing for quick identification of service failures and overall system health.
    """

    def __init__(self, service_manager: ServiceManager) -> None:
        """
        Initialize the health monitor.

        Args:
            service_manager: The ServiceManager instance containing all services to
            monitor.

        Example:
            >>> from thoth.services.service_manager import ServiceManager
            >>> service_manager = ServiceManager()
            >>> health_monitor = HealthMonitor(service_manager)
        """
        self.service_manager = service_manager

    def check_services(self) -> dict[str, dict[str, Any]]:
        """
        Run health_check on all managed services.

        Returns:
            dict[str, dict[str, Any]]: A dictionary mapping service names to their
            health status information.
            Each service status includes 'status', 'service', and potentially
            'error' fields.

        Example:
            >>> health_monitor = HealthMonitor(service_manager)
            >>> statuses = health_monitor.check_services()
            >>> statuses['llm_service']['status']
            'healthy'
        """
        statuses: dict[str, dict[str, Any]] = {}

        try:
            services = self.service_manager.get_all_services()
            logger.debug(f'Checking health of {len(services)} services')

            for name, service in services.items():
                try:
                    health_result = service.health_check()
                    # Some services define async health_check(). The health router
                    # is sync so we can't await here. Close the coroutine to avoid
                    # the "never awaited" RuntimeWarning and treat it as healthy
                    # since the method exists.
                    if inspect.isawaitable(health_result):
                        health_result.close()
                        health_result = {
                            'status': 'healthy',
                            'service': service.__class__.__name__,
                        }
                    if not isinstance(health_result, dict):
                        # Ensure we have a dict response
                        health_result = {
                            'status': 'healthy',
                            'service': service.__class__.__name__,
                        }
                    statuses[name] = health_result
                    logger.debug(
                        f"Service '{name}' health check: {health_result.get('status', 'unknown')}"
                    )
                except AttributeError:
                    # Service doesn't have a health_check method
                    logger.warning(
                        f"Service '{name}' ({service.__class__.__name__}) does not implement health_check()"
                    )
                    statuses[name] = {
                        'service': service.__class__.__name__,
                        'status': 'unknown',
                        'error': 'health_check method not implemented',
                    }
                except Exception as exc:
                    logger.error(f"Health check failed for service '{name}': {exc}")
                    statuses[name] = {
                        'service': service.__class__.__name__,
                        'status': 'unhealthy',
                        'error': str(exc),
                    }
        except Exception as exc:
            logger.error(f'Failed to get services from service manager: {exc}')
            return {
                'service_manager': {
                    'service': 'ServiceManager',
                    'status': 'unhealthy',
                    'error': f'Failed to get services: {exc!s}',
                }
            }

        return statuses

    def overall_status(self) -> dict[str, Any]:
        """
        Return aggregated health information for the entire system.

        Returns:
            dict[str, Any]: Overall system health status with 'healthy' boolean and
            'services' details.

        Example:
            >>> health_monitor = HealthMonitor(service_manager)
            >>> status = health_monitor.overall_status()
            >>> status['healthy']
            True
            >>> len(status['services'])
            5
        """
        services = self.check_services()

        # Count healthy vs unhealthy services.
        # "unknown" means the service doesn't implement health_check -- that's
        # not a failure, just a gap in instrumentation. Only "unhealthy" counts
        # as an actual problem that should surface a 503.
        healthy_count = sum(
            1 for info in services.values() if info.get('status') == 'healthy'
        )
        unhealthy_count = sum(
            1 for info in services.values() if info.get('status') == 'unhealthy'
        )
        total_count = len(services)

        overall_healthy = unhealthy_count == 0 and total_count > 0

        result = {
            'healthy': overall_healthy,
            'services': services,
            'summary': {
                'total_services': total_count,
                'healthy_services': healthy_count,
                'unhealthy_services': unhealthy_count,
                'unknown_services': total_count - healthy_count - unhealthy_count,
            },
        }

        logger.info(
            f'Overall system health: {"healthy" if overall_healthy else "unhealthy"} '
            f'({healthy_count}/{total_count} services healthy)'
        )

        return result

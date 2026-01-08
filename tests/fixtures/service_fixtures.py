"""Fixtures for testing services with various health states."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest


class HealthyService:
    """Mock service that always reports healthy status."""

    def __init__(self, name: str = 'HealthyService') -> None:
        """Initialize healthy service."""
        self.name = name
        self._initialized = True

    def health_check(self) -> dict[str, Any]:
        """Return healthy status."""
        return {
            'status': 'healthy',
            'service': self.__class__.__name__,
            'details': 'Service is operating normally',
        }


class UnhealthyService:
    """Mock service that reports unhealthy status."""

    def __init__(
        self, name: str = 'UnhealthyService', error_msg: str = 'Service degraded'
    ) -> None:
        """Initialize unhealthy service."""
        self.name = name
        self.error_msg = error_msg
        self._initialized = True

    def health_check(self) -> dict[str, Any]:
        """Return unhealthy status."""
        return {
            'status': 'unhealthy',
            'service': self.__class__.__name__,
            'error': self.error_msg,
        }


class ServiceWithoutHealthCheck:
    """Mock service that doesn't implement health_check method."""

    def __init__(self, name: str = 'ServiceWithoutHealthCheck') -> None:
        """Initialize service without health check."""
        self.name = name
        self._initialized = True

    def some_other_method(self) -> str:
        """Placeholder method."""
        return 'Service running'


class ServiceRaisingException:
    """Mock service that raises an exception during health check."""

    def __init__(
        self,
        name: str = 'ServiceRaisingException',
        exception_type: type[Exception] = RuntimeError,
        exception_msg: str = 'Health check failed',
    ) -> None:
        """Initialize service that raises exceptions."""
        self.name = name
        self.exception_type = exception_type
        self.exception_msg = exception_msg
        self._initialized = True

    def health_check(self) -> dict[str, Any]:
        """Raise an exception when called."""
        raise self.exception_type(self.exception_msg)


class ServiceWithNonDictResponse:
    """Mock service that returns non-dict response from health_check."""

    def __init__(
        self, name: str = 'ServiceWithNonDictResponse', response: Any = True
    ) -> None:
        """Initialize service with non-dict response."""
        self.name = name
        self.response = response
        self._initialized = True

    def health_check(self) -> Any:
        """Return non-dict response."""
        return self.response


class ServiceWithPartialHealthCheck:
    """Mock service that returns incomplete health status dict."""

    def __init__(self, name: str = 'ServiceWithPartialHealthCheck') -> None:
        """Initialize service with partial response."""
        self.name = name
        self._initialized = True

    def health_check(self) -> dict[str, Any]:
        """Return partial health status without all expected fields."""
        return {
            'status': 'healthy',
            # Missing 'service' field
        }


class ServiceWithUnknownStatus:
    """Mock service that returns unknown status."""

    def __init__(self, name: str = 'ServiceWithUnknownStatus') -> None:
        """Initialize service with unknown status."""
        self.name = name
        self._initialized = True

    def health_check(self) -> dict[str, Any]:
        """Return unknown status."""
        return {
            'status': 'unknown',
            'service': self.__class__.__name__,
            'details': 'Status cannot be determined',
        }


class DegradedService:
    """Mock service in degraded state (partially working)."""

    def __init__(self, name: str = 'DegradedService') -> None:
        """Initialize degraded service."""
        self.name = name
        self._initialized = True

    def health_check(self) -> dict[str, Any]:
        """Return degraded status."""
        return {
            'status': 'degraded',
            'service': self.__class__.__name__,
            'details': 'Service functioning with reduced capacity',
            'warnings': ['High latency detected', 'Connection pool at 80%'],
        }


class IntermittentService:
    """Mock service that alternates between healthy and unhealthy."""

    def __init__(
        self, name: str = 'IntermittentService', initial_state: bool = True
    ) -> None:
        """Initialize intermittent service."""
        self.name = name
        self._is_healthy = initial_state
        self._call_count = 0
        self._initialized = True

    def health_check(self) -> dict[str, Any]:
        """Alternate between healthy and unhealthy states."""
        self._call_count += 1
        self._is_healthy = not self._is_healthy

        if self._is_healthy:
            return {
                'status': 'healthy',
                'service': self.__class__.__name__,
                'call_count': self._call_count,
            }
        else:
            return {
                'status': 'unhealthy',
                'service': self.__class__.__name__,
                'error': 'Intermittent failure',
                'call_count': self._call_count,
            }


class SlowService:
    """Mock service that simulates slow health checks."""

    def __init__(self, name: str = 'SlowService', delay: float = 1.0) -> None:
        """Initialize slow service."""
        self.name = name
        self.delay = delay
        self._initialized = True

    def health_check(self) -> dict[str, Any]:
        """Return health status after simulated delay."""
        import time

        time.sleep(self.delay)
        return {
            'status': 'healthy',
            'service': self.__class__.__name__,
            'response_time': self.delay,
        }


class ServiceWithDetailedMetrics:
    """Mock service that returns detailed health metrics."""

    def __init__(self, name: str = 'ServiceWithDetailedMetrics') -> None:
        """Initialize service with detailed metrics."""
        self.name = name
        self._initialized = True

    def health_check(self) -> dict[str, Any]:
        """Return detailed health metrics."""
        return {
            'status': 'healthy',
            'service': self.__class__.__name__,
            'metrics': {
                'uptime': 3600,
                'request_count': 1000,
                'error_rate': 0.01,
                'memory_usage_mb': 512,
                'cpu_usage_percent': 25.5,
            },
            'dependencies': {
                'database': 'healthy',
                'cache': 'healthy',
                'queue': 'degraded',
            },
        }


# Pytest Fixtures


@pytest.fixture
def healthy_service() -> HealthyService:
    """Fixture providing a healthy service instance."""
    return HealthyService()


@pytest.fixture
def unhealthy_service() -> UnhealthyService:
    """Fixture providing an unhealthy service instance."""
    return UnhealthyService()


@pytest.fixture
def service_without_health_check() -> ServiceWithoutHealthCheck:
    """Fixture providing a service without health_check method."""
    return ServiceWithoutHealthCheck()


@pytest.fixture
def service_raising_exception() -> ServiceRaisingException:
    """Fixture providing a service that raises exceptions."""
    return ServiceRaisingException()


@pytest.fixture
def service_with_non_dict_response() -> ServiceWithNonDictResponse:
    """Fixture providing a service with non-dict response."""
    return ServiceWithNonDictResponse()


@pytest.fixture
def service_with_partial_health_check() -> ServiceWithPartialHealthCheck:
    """Fixture providing a service with partial health check."""
    return ServiceWithPartialHealthCheck()


@pytest.fixture
def service_with_unknown_status() -> ServiceWithUnknownStatus:
    """Fixture providing a service with unknown status."""
    return ServiceWithUnknownStatus()


@pytest.fixture
def degraded_service() -> DegradedService:
    """Fixture providing a degraded service."""
    return DegradedService()


@pytest.fixture
def intermittent_service() -> IntermittentService:
    """Fixture providing an intermittent service."""
    return IntermittentService()


@pytest.fixture
def service_with_detailed_metrics() -> ServiceWithDetailedMetrics:
    """Fixture providing a service with detailed metrics."""
    return ServiceWithDetailedMetrics()


@pytest.fixture
def mock_service_manager_empty() -> Mock:
    """Fixture providing an empty service manager."""
    manager = Mock()
    manager.get_all_services.return_value = {}
    return manager


@pytest.fixture
def mock_service_manager_single_healthy() -> Mock:
    """Fixture providing service manager with single healthy service."""
    manager = Mock()
    manager.get_all_services.return_value = {
        'service1': HealthyService('service1'),
    }
    return manager


@pytest.fixture
def mock_service_manager_multiple_healthy() -> Mock:
    """Fixture providing service manager with multiple healthy services."""
    manager = Mock()
    manager.get_all_services.return_value = {
        'service1': HealthyService('service1'),
        'service2': HealthyService('service2'),
        'service3': HealthyService('service3'),
    }
    return manager


@pytest.fixture
def mock_service_manager_mixed_status() -> Mock:
    """Fixture providing service manager with mixed service statuses."""
    manager = Mock()
    manager.get_all_services.return_value = {
        'healthy1': HealthyService('healthy1'),
        'healthy2': HealthyService('healthy2'),
        'unhealthy1': UnhealthyService('unhealthy1', 'Database connection failed'),
        'unhealthy2': UnhealthyService('unhealthy2', 'API timeout'),
        'no_check': ServiceWithoutHealthCheck('no_check'),
        'exception': ServiceRaisingException(
            'exception', RuntimeError, 'Critical error'
        ),
    }
    return manager


@pytest.fixture
def mock_service_manager_all_unhealthy() -> Mock:
    """Fixture providing service manager with all unhealthy services."""
    manager = Mock()
    manager.get_all_services.return_value = {
        'unhealthy1': UnhealthyService('unhealthy1', 'Service down'),
        'unhealthy2': UnhealthyService('unhealthy2', 'Connection refused'),
        'exception': ServiceRaisingException(
            'exception', ConnectionError, 'Cannot connect'
        ),
    }
    return manager


@pytest.fixture
def mock_service_manager_with_non_dict_responses() -> Mock:
    """Fixture providing service manager with services returning non-dict responses."""
    manager = Mock()
    manager.get_all_services.return_value = {
        'bool_service': ServiceWithNonDictResponse('bool_service', True),
        'str_service': ServiceWithNonDictResponse('str_service', 'healthy'),
        'none_service': ServiceWithNonDictResponse('none_service', None),
    }
    return manager


@pytest.fixture
def mock_service_manager_failing() -> Mock:
    """Fixture providing service manager that fails on get_all_services."""
    manager = Mock()
    manager.get_all_services.side_effect = RuntimeError(
        'Service manager initialization failed'
    )
    return manager


@pytest.fixture
def mock_service_manager_complex() -> Mock:
    """Fixture providing service manager with complex service hierarchy."""
    manager = Mock()
    manager.get_all_services.return_value = {
        'core_service': HealthyService('core_service'),
        'metrics_service': ServiceWithDetailedMetrics('metrics_service'),
        'degraded_service': DegradedService('degraded_service'),
        'intermittent_service': IntermittentService('intermittent_service', True),
        'unknown_service': ServiceWithUnknownStatus('unknown_service'),
        'partial_service': ServiceWithPartialHealthCheck('partial_service'),
    }
    return manager

"""Comprehensive tests for the health monitoring system."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

import pytest

from thoth.monitoring.health import HealthMonitor

# Import fixtures from our service fixtures module
from tests.fixtures.service_fixtures import (
    DegradedService,
    HealthyService,
    IntermittentService,
    ServiceRaisingException,
    ServiceWithDetailedMetrics,
    ServiceWithNonDictResponse,
    ServiceWithoutHealthCheck,
    ServiceWithPartialHealthCheck,
    ServiceWithUnknownStatus,
    UnhealthyService,
)


class TestHealthMonitorInit:
    """Test HealthMonitor initialization."""

    def test_init_with_service_manager(self, mock_service_manager_empty: Mock) -> None:
        """Test HealthMonitor initialization with service manager."""
        monitor = HealthMonitor(mock_service_manager_empty)
        assert monitor.service_manager is mock_service_manager_empty

    def test_init_stores_service_manager_reference(
        self, mock_service_manager_single_healthy: Mock
    ) -> None:
        """Test that service manager reference is correctly stored."""
        monitor = HealthMonitor(mock_service_manager_single_healthy)
        assert hasattr(monitor, "service_manager")
        assert monitor.service_manager is mock_service_manager_single_healthy


class TestHealthMonitorCheckServices:
    """Test HealthMonitor.check_services() method."""

    def test_check_services_empty_manager(self, mock_service_manager_empty: Mock) -> None:
        """Test check_services with no services registered."""
        monitor = HealthMonitor(mock_service_manager_empty)
        statuses = monitor.check_services()

        assert isinstance(statuses, dict)
        assert len(statuses) == 0
        mock_service_manager_empty.get_all_services.assert_called_once()

    def test_check_services_single_healthy(
        self, mock_service_manager_single_healthy: Mock
    ) -> None:
        """Test check_services with single healthy service."""
        monitor = HealthMonitor(mock_service_manager_single_healthy)
        statuses = monitor.check_services()

        assert len(statuses) == 1
        assert "service1" in statuses
        assert statuses["service1"]["status"] == "healthy"
        assert "service" in statuses["service1"]

    def test_check_services_multiple_healthy(
        self, mock_service_manager_multiple_healthy: Mock
    ) -> None:
        """Test check_services with multiple healthy services."""
        monitor = HealthMonitor(mock_service_manager_multiple_healthy)
        statuses = monitor.check_services()

        assert len(statuses) == 3
        for name in ["service1", "service2", "service3"]:
            assert name in statuses
            assert statuses[name]["status"] == "healthy"

    def test_check_services_mixed_status(self, mock_service_manager_mixed_status: Mock) -> None:
        """Test check_services with mixed service health statuses."""
        monitor = HealthMonitor(mock_service_manager_mixed_status)
        statuses = monitor.check_services()

        # Should have status for all 6 services
        assert len(statuses) == 6

        # Check healthy services
        assert statuses["healthy1"]["status"] == "healthy"
        assert statuses["healthy2"]["status"] == "healthy"

        # Check unhealthy services
        assert statuses["unhealthy1"]["status"] == "unhealthy"
        assert "Database connection failed" in statuses["unhealthy1"]["error"]

        assert statuses["unhealthy2"]["status"] == "unhealthy"
        assert "API timeout" in statuses["unhealthy2"]["error"]

        # Check service without health_check method
        assert statuses["no_check"]["status"] == "unknown"
        assert "health_check method not implemented" in statuses["no_check"]["error"]

        # Check service that raises exception
        assert statuses["exception"]["status"] == "unhealthy"
        assert "Critical error" in statuses["exception"]["error"]

    def test_check_services_all_unhealthy(
        self, mock_service_manager_all_unhealthy: Mock
    ) -> None:
        """Test check_services when all services are unhealthy."""
        monitor = HealthMonitor(mock_service_manager_all_unhealthy)
        statuses = monitor.check_services()

        assert len(statuses) == 3
        for status_info in statuses.values():
            assert status_info["status"] == "unhealthy"
            assert "error" in status_info

    def test_check_services_without_health_check_method(self) -> None:
        """Test check_services with service missing health_check method."""
        manager = Mock()
        manager.get_all_services.return_value = {
            "no_health": ServiceWithoutHealthCheck("no_health"),
        }

        monitor = HealthMonitor(manager)
        statuses = monitor.check_services()

        assert len(statuses) == 1
        assert statuses["no_health"]["status"] == "unknown"
        assert "health_check method not implemented" in statuses["no_health"]["error"]
        assert statuses["no_health"]["service"] == "ServiceWithoutHealthCheck"

    def test_check_services_exception_during_health_check(self) -> None:
        """Test check_services when health_check raises exception."""
        manager = Mock()
        manager.get_all_services.return_value = {
            "failing": ServiceRaisingException(
                "failing", RuntimeError, "Unexpected failure"
            ),
        }

        monitor = HealthMonitor(manager)
        statuses = monitor.check_services()

        assert len(statuses) == 1
        assert statuses["failing"]["status"] == "unhealthy"
        assert "Unexpected failure" in statuses["failing"]["error"]
        assert statuses["failing"]["service"] == "ServiceRaisingException"

    def test_check_services_various_exceptions(self) -> None:
        """Test check_services with different exception types."""
        manager = Mock()
        manager.get_all_services.return_value = {
            "runtime_error": ServiceRaisingException(
                "runtime_error", RuntimeError, "Runtime failure"
            ),
            "value_error": ServiceRaisingException(
                "value_error", ValueError, "Invalid value"
            ),
            "connection_error": ServiceRaisingException(
                "connection_error", ConnectionError, "Connection lost"
            ),
        }

        monitor = HealthMonitor(manager)
        statuses = monitor.check_services()

        assert len(statuses) == 3
        assert all(s["status"] == "unhealthy" for s in statuses.values())
        assert "Runtime failure" in statuses["runtime_error"]["error"]
        assert "Invalid value" in statuses["value_error"]["error"]
        assert "Connection lost" in statuses["connection_error"]["error"]

    def test_check_services_non_dict_response(
        self, mock_service_manager_with_non_dict_responses: Mock
    ) -> None:
        """Test check_services with services returning non-dict responses."""
        monitor = HealthMonitor(mock_service_manager_with_non_dict_responses)
        statuses = monitor.check_services()

        assert len(statuses) == 3

        # All should be converted to dict format with healthy status
        for service_name, status_info in statuses.items():
            assert isinstance(status_info, dict)
            assert status_info["status"] == "healthy"
            assert "service" in status_info
            assert status_info["service"] == "ServiceWithNonDictResponse"

    def test_check_services_service_manager_failure(
        self, mock_service_manager_failing: Mock
    ) -> None:
        """Test check_services when service manager fails."""
        monitor = HealthMonitor(mock_service_manager_failing)
        statuses = monitor.check_services()

        # Should return error status for service manager itself
        assert len(statuses) == 1
        assert "service_manager" in statuses
        assert statuses["service_manager"]["status"] == "unhealthy"
        assert "Failed to get services" in statuses["service_manager"]["error"]
        assert "Service manager initialization failed" in statuses["service_manager"]["error"]

    def test_check_services_isolation(self) -> None:
        """Test that one service failure doesn't crash other health checks."""
        manager = Mock()
        manager.get_all_services.return_value = {
            "healthy": HealthyService("healthy"),
            "failing": ServiceRaisingException("failing", RuntimeError, "Crash"),
            "also_healthy": HealthyService("also_healthy"),
        }

        monitor = HealthMonitor(manager)
        statuses = monitor.check_services()

        # All three services should have status entries
        assert len(statuses) == 3
        assert statuses["healthy"]["status"] == "healthy"
        assert statuses["failing"]["status"] == "unhealthy"
        assert statuses["also_healthy"]["status"] == "healthy"

    def test_check_services_preserves_service_details(self) -> None:
        """Test that detailed health information is preserved."""
        manager = Mock()
        manager.get_all_services.return_value = {
            "detailed": ServiceWithDetailedMetrics("detailed"),
        }

        monitor = HealthMonitor(manager)
        statuses = monitor.check_services()

        assert "detailed" in statuses
        assert statuses["detailed"]["status"] == "healthy"
        assert "metrics" in statuses["detailed"]
        assert "dependencies" in statuses["detailed"]
        assert statuses["detailed"]["metrics"]["uptime"] == 3600
        assert statuses["detailed"]["dependencies"]["database"] == "healthy"


class TestHealthMonitorOverallStatus:
    """Test HealthMonitor.overall_status() method."""

    def test_overall_status_empty_manager(self, mock_service_manager_empty: Mock) -> None:
        """Test overall_status with no services."""
        monitor = HealthMonitor(mock_service_manager_empty)
        status = monitor.overall_status()

        assert isinstance(status, dict)
        assert "healthy" in status
        assert status["healthy"] is False  # No services means unhealthy
        assert status["summary"]["total_services"] == 0
        assert status["summary"]["healthy_services"] == 0
        assert status["summary"]["unhealthy_services"] == 0

    def test_overall_status_all_healthy(
        self, mock_service_manager_multiple_healthy: Mock
    ) -> None:
        """Test overall_status when all services are healthy."""
        monitor = HealthMonitor(mock_service_manager_multiple_healthy)
        status = monitor.overall_status()

        assert status["healthy"] is True
        assert status["summary"]["total_services"] == 3
        assert status["summary"]["healthy_services"] == 3
        assert status["summary"]["unhealthy_services"] == 0
        assert len(status["services"]) == 3

    def test_overall_status_mixed_health(
        self, mock_service_manager_mixed_status: Mock
    ) -> None:
        """Test overall_status with mixed service health."""
        monitor = HealthMonitor(mock_service_manager_mixed_status)
        status = monitor.overall_status()

        assert status["healthy"] is False  # Not all services healthy
        assert status["summary"]["total_services"] == 6
        assert status["summary"]["healthy_services"] == 2  # Only the two HealthyService instances
        assert status["summary"]["unhealthy_services"] == 4

    def test_overall_status_all_unhealthy(
        self, mock_service_manager_all_unhealthy: Mock
    ) -> None:
        """Test overall_status when all services are unhealthy."""
        monitor = HealthMonitor(mock_service_manager_all_unhealthy)
        status = monitor.overall_status()

        assert status["healthy"] is False
        assert status["summary"]["total_services"] == 3
        assert status["summary"]["healthy_services"] == 0
        assert status["summary"]["unhealthy_services"] == 3

    def test_overall_status_includes_service_details(
        self, mock_service_manager_single_healthy: Mock
    ) -> None:
        """Test that overall_status includes detailed service information."""
        monitor = HealthMonitor(mock_service_manager_single_healthy)
        status = monitor.overall_status()

        assert "services" in status
        assert "service1" in status["services"]
        assert status["services"]["service1"]["status"] == "healthy"

    def test_overall_status_summary_statistics(
        self, mock_service_manager_mixed_status: Mock
    ) -> None:
        """Test summary statistics calculation."""
        monitor = HealthMonitor(mock_service_manager_mixed_status)
        status = monitor.overall_status()

        summary = status["summary"]
        assert summary["total_services"] == 6
        assert summary["healthy_services"] == 2
        assert summary["unhealthy_services"] == 4
        assert (
            summary["healthy_services"] + summary["unhealthy_services"]
            == summary["total_services"]
        )

    def test_overall_status_aggregation_logic(self) -> None:
        """Test that overall health is correctly aggregated."""
        # Test case 1: All healthy
        manager1 = Mock()
        manager1.get_all_services.return_value = {
            "s1": HealthyService("s1"),
            "s2": HealthyService("s2"),
        }
        monitor1 = HealthMonitor(manager1)
        status1 = monitor1.overall_status()
        assert status1["healthy"] is True

        # Test case 2: One unhealthy
        manager2 = Mock()
        manager2.get_all_services.return_value = {
            "s1": HealthyService("s1"),
            "s2": UnhealthyService("s2"),
        }
        monitor2 = HealthMonitor(manager2)
        status2 = monitor2.overall_status()
        assert status2["healthy"] is False

        # Test case 3: Unknown status treated as not healthy
        manager3 = Mock()
        manager3.get_all_services.return_value = {
            "s1": HealthyService("s1"),
            "s2": ServiceWithUnknownStatus("s2"),
        }
        monitor3 = HealthMonitor(manager3)
        status3 = monitor3.overall_status()
        assert status3["healthy"] is False

    def test_overall_status_with_service_manager_failure(
        self, mock_service_manager_failing: Mock
    ) -> None:
        """Test overall_status when service manager fails."""
        monitor = HealthMonitor(mock_service_manager_failing)
        status = monitor.overall_status()

        assert status["healthy"] is False
        assert "service_manager" in status["services"]
        assert status["services"]["service_manager"]["status"] == "unhealthy"

    def test_overall_status_calls_check_services(
        self, mock_service_manager_single_healthy: Mock
    ) -> None:
        """Test that overall_status calls check_services internally."""
        monitor = HealthMonitor(mock_service_manager_single_healthy)

        with patch.object(monitor, "check_services", wraps=monitor.check_services) as mock_check:
            status = monitor.overall_status()
            mock_check.assert_called_once()
            assert "services" in status


class TestHealthMonitorLogging:
    """Test logging behavior of HealthMonitor."""

    def test_check_services_logs_service_count(
        self, mock_service_manager_multiple_healthy: Mock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that check_services logs the number of services being checked."""
        import logging

        caplog.set_level(logging.DEBUG)

        monitor = HealthMonitor(mock_service_manager_multiple_healthy)
        monitor.check_services()

        # Should have debug log about checking services
        assert any("Checking health of 3 services" in record.message for record in caplog.records)

    def test_check_services_logs_individual_results(
        self, mock_service_manager_mixed_status: Mock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that individual service health checks are logged."""
        import logging

        caplog.set_level(logging.DEBUG)

        monitor = HealthMonitor(mock_service_manager_mixed_status)
        monitor.check_services()

        # Should have debug logs for each service
        log_messages = [record.message for record in caplog.records if record.levelname == "DEBUG"]
        assert any("healthy1" in msg for msg in log_messages)
        assert any("healthy2" in msg for msg in log_messages)

    def test_check_services_logs_missing_health_check(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test warning log when service doesn't have health_check method."""
        import logging

        caplog.set_level(logging.WARNING)

        manager = Mock()
        manager.get_all_services.return_value = {
            "no_check": ServiceWithoutHealthCheck("no_check"),
        }

        monitor = HealthMonitor(manager)
        monitor.check_services()

        # Should have warning about missing health_check
        warning_messages = [
            record.message for record in caplog.records if record.levelname == "WARNING"
        ]
        assert any("does not implement health_check()" in msg for msg in warning_messages)
        assert any("no_check" in msg for msg in warning_messages)

    def test_check_services_logs_exceptions(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test error logging when health check raises exception."""
        import logging

        caplog.set_level(logging.ERROR)

        manager = Mock()
        manager.get_all_services.return_value = {
            "failing": ServiceRaisingException("failing", RuntimeError, "Test error"),
        }

        monitor = HealthMonitor(manager)
        monitor.check_services()

        # Should have error log about health check failure
        error_messages = [
            record.message for record in caplog.records if record.levelname == "ERROR"
        ]
        assert any("Health check failed" in msg for msg in error_messages)
        assert any("failing" in msg for msg in error_messages)

    def test_check_services_logs_service_manager_failure(
        self, mock_service_manager_failing: Mock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test error logging when service manager fails."""
        import logging

        caplog.set_level(logging.ERROR)

        monitor = HealthMonitor(mock_service_manager_failing)
        monitor.check_services()

        # Should have error log about service manager failure
        error_messages = [
            record.message for record in caplog.records if record.levelname == "ERROR"
        ]
        assert any("Failed to get services from service manager" in msg for msg in error_messages)

    def test_overall_status_logs_summary(
        self, mock_service_manager_multiple_healthy: Mock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that overall_status logs summary information."""
        import logging

        caplog.set_level(logging.INFO)

        monitor = HealthMonitor(mock_service_manager_multiple_healthy)
        monitor.overall_status()

        # Should have info log about overall status
        info_messages = [
            record.message for record in caplog.records if record.levelname == "INFO"
        ]
        assert any("Overall system health" in msg for msg in info_messages)
        assert any("healthy" in msg for msg in info_messages)
        assert any("3/3" in msg for msg in info_messages)

    def test_overall_status_logs_unhealthy_system(
        self, mock_service_manager_mixed_status: Mock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test logging when overall system is unhealthy."""
        import logging

        caplog.set_level(logging.INFO)

        monitor = HealthMonitor(mock_service_manager_mixed_status)
        monitor.overall_status()

        # Should log unhealthy status
        info_messages = [
            record.message for record in caplog.records if record.levelname == "INFO"
        ]
        assert any("unhealthy" in msg for msg in info_messages)
        assert any("2/6" in msg for msg in info_messages)


class TestHealthMonitorEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_service_with_partial_health_response(self) -> None:
        """Test handling of incomplete health check response."""
        manager = Mock()
        manager.get_all_services.return_value = {
            "partial": ServiceWithPartialHealthCheck("partial"),
        }

        monitor = HealthMonitor(manager)
        statuses = monitor.check_services()

        # Should still work with partial response
        assert "partial" in statuses
        assert statuses["partial"]["status"] == "healthy"

    def test_service_with_unknown_status(self) -> None:
        """Test handling of unknown status value."""
        manager = Mock()
        manager.get_all_services.return_value = {
            "unknown": ServiceWithUnknownStatus("unknown"),
        }

        monitor = HealthMonitor(manager)
        status = monitor.overall_status()

        # Unknown status should make system unhealthy
        assert status["healthy"] is False
        assert status["services"]["unknown"]["status"] == "unknown"

    def test_service_with_degraded_status(self) -> None:
        """Test handling of degraded service status."""
        manager = Mock()
        manager.get_all_services.return_value = {
            "degraded": DegradedService("degraded"),
        }

        monitor = HealthMonitor(manager)
        status = monitor.overall_status()

        # Degraded status should make system unhealthy
        assert status["healthy"] is False
        assert status["services"]["degraded"]["status"] == "degraded"

    def test_intermittent_service_state_changes(self) -> None:
        """Test service that changes state between calls."""
        manager = Mock()
        intermittent = IntermittentService("intermittent", initial_state=True)
        manager.get_all_services.return_value = {"intermittent": intermittent}

        monitor = HealthMonitor(manager)

        # First check - should be unhealthy (toggled from initial True)
        status1 = monitor.check_services()
        assert status1["intermittent"]["status"] == "unhealthy"

        # Second check - should be healthy (toggled again)
        status2 = monitor.check_services()
        assert status2["intermittent"]["status"] == "healthy"

    def test_multiple_calls_to_check_services(
        self, mock_service_manager_single_healthy: Mock
    ) -> None:
        """Test that multiple calls work correctly."""
        monitor = HealthMonitor(mock_service_manager_single_healthy)

        status1 = monitor.check_services()
        status2 = monitor.check_services()
        status3 = monitor.check_services()

        # All should return consistent results
        assert status1 == status2 == status3
        assert mock_service_manager_single_healthy.get_all_services.call_count == 3

    def test_overall_status_structure_completeness(
        self, mock_service_manager_multiple_healthy: Mock
    ) -> None:
        """Test that overall_status returns complete structure."""
        monitor = HealthMonitor(mock_service_manager_multiple_healthy)
        status = monitor.overall_status()

        # Verify all required keys are present
        assert "healthy" in status
        assert "services" in status
        assert "summary" in status

        # Verify summary structure
        summary = status["summary"]
        assert "total_services" in summary
        assert "healthy_services" in summary
        assert "unhealthy_services" in summary

    def test_service_class_name_in_status(self) -> None:
        """Test that service class name is included in status."""
        manager = Mock()
        manager.get_all_services.return_value = {
            "test_service": HealthyService("test_service"),
        }

        monitor = HealthMonitor(manager)
        statuses = monitor.check_services()

        assert statuses["test_service"]["service"] == "HealthyService"

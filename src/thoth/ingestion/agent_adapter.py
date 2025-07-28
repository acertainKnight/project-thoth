"""
Agent adapter for bridging pipeline services with the modern agent system.

This module provides compatibility between the legacy pipeline interface
and the new agent-based architecture.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from thoth.services.service_manager import ServiceManager


class AgentAdapter:
    """
    Adapter class that bridges pipeline services with the agent system.

    This adapter provides a compatibility layer between the legacy pipeline
    interface and the modern agent architecture, allowing existing code
    to work with the new agent system.
    """

    def __init__(self, service_manager: 'ServiceManager'):
        """
        Initialize the agent adapter.

        Args:
            service_manager: ServiceManager instance from pipeline.services
        """
        self.service_manager = service_manager

    @property
    def services(self) -> 'ServiceManager':
        """
        Get the service manager instance.

        Returns:
            ServiceManager: The service manager for accessing all services
        """
        return self.service_manager

    def get_service_manager(self) -> 'ServiceManager':
        """
        Get the service manager instance.

        Returns:
            ServiceManager: The service manager for accessing all services
        """
        return self.service_manager

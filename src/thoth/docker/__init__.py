"""
Docker integration module for Thoth.

This module provides Docker-aware functionality including:
- Container environment detection
- Volume management for persistence
- Container-optimized file operations
- Service management in container environments
"""

from .container_utils import (
    ContainerInfo,
    DockerEnvironmentDetector,
    VolumeInfo,
    detect_container_environment,
    get_container_info,
    get_volume_mounts,
    is_running_in_docker,
)
from .volume_manager import (
    PersistenceResult,
    VolumeHealthStatus,
    VolumeManager,
)

__all__ = [
    # Container utilities
    'ContainerInfo',
    'DockerEnvironmentDetector',
    'PersistenceResult',
    'VolumeHealthStatus',
    'VolumeInfo',
    # Volume management
    'VolumeManager',
    'detect_container_environment',
    'get_container_info',
    'get_volume_mounts',
    'is_running_in_docker',
]

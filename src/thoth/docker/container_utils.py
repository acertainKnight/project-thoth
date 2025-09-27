"""
Container environment utilities for Docker-aware operations.

This module provides utilities for detecting container environments,
managing Docker-specific operations, and optimizing for containerized deployments.
"""

import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class ContainerInfo:
    """Information about the current container environment."""

    is_container: bool
    container_id: str | None = None
    container_runtime: str | None = None  # docker, podman, etc.
    image_name: str | None = None
    hostname: str | None = None
    cgroup_version: str | None = None
    init_system: str | None = None


@dataclass
class VolumeInfo:
    """Information about a Docker volume mount."""

    host_path: str
    container_path: str
    volume_type: str  # bind, volume, tmpfs
    read_only: bool = False
    volume_name: str | None = None
    driver: str | None = None


class DockerEnvironmentDetector:
    """Detects and analyzes Docker container environments."""

    def __init__(self):
        """Initialize the Docker environment detector."""
        self._cached_info: ContainerInfo | None = None
        self._volume_cache: list[VolumeInfo] | None = None

    def detect_container_environment(self) -> ContainerInfo:
        """
        Detect if running in a container and gather environment information.

        Returns:
            ContainerInfo with detected container details
        """
        if self._cached_info is not None:
            return self._cached_info

        is_container = False
        container_id = None
        container_runtime = None
        image_name = None
        hostname = socket.gethostname()
        cgroup_version = None
        init_system = None

        # Method 1: Check for .dockerenv file
        if Path('/.dockerenv').exists():
            is_container = True
            container_runtime = 'docker'
            logger.debug('Detected Docker container via .dockerenv file')

        # Method 2: Check cgroup information
        if not is_container:
            cgroup_info = self._check_cgroup_info()
            if cgroup_info['is_container']:
                is_container = True
                container_runtime = cgroup_info.get('runtime', 'unknown')
                container_id = cgroup_info.get('container_id')
                cgroup_version = cgroup_info.get('version')
                logger.debug(f'Detected container via cgroup: {container_runtime}')

        # Method 3: Check environment variables
        if not is_container:
            env_detection = self._check_environment_variables()
            if env_detection['is_container']:
                is_container = True
                container_runtime = env_detection.get('runtime', 'unknown')
                logger.debug('Detected container via environment variables')

        # Method 4: Check init system (PID 1)
        init_info = self._check_init_system()
        init_system = init_info.get('init_system')
        if not is_container and init_info.get('suggests_container', False):
            is_container = True
            logger.debug('Detected container via init system analysis')

        # Get additional container information
        if is_container:
            container_id = container_id or self._get_container_id()
            image_name = self._get_image_name()

        self._cached_info = ContainerInfo(
            is_container=is_container,
            container_id=container_id,
            container_runtime=container_runtime,
            image_name=image_name,
            hostname=hostname,
            cgroup_version=cgroup_version,
            init_system=init_system,
        )

        logger.info(f'Container detection result: {self._cached_info}')
        return self._cached_info

    def _check_cgroup_info(self) -> dict[str, Any]:
        """Check cgroup information for container indicators."""
        result = {'is_container': False}

        try:
            # Check /proc/1/cgroup
            cgroup_path = Path('/proc/1/cgroup')
            if cgroup_path.exists():
                content = cgroup_path.read_text()

                # Look for container indicators
                if 'docker' in content:
                    result.update(
                        {
                            'is_container': True,
                            'runtime': 'docker',
                            'container_id': self._extract_docker_id_from_cgroup(
                                content
                            ),
                        }
                    )
                elif 'containerd' in content:
                    result.update({'is_container': True, 'runtime': 'containerd'})
                elif 'lxc' in content:
                    result.update({'is_container': True, 'runtime': 'lxc'})

                # Determine cgroup version
                if (
                    'cgroup2' in content
                    or Path('/sys/fs/cgroup/cgroup.controllers').exists()
                ):
                    result['version'] = 'v2'
                else:
                    result['version'] = 'v1'

            # Also check /proc/self/mountinfo for additional clues
            mountinfo_path = Path('/proc/self/mountinfo')
            if mountinfo_path.exists():
                mountinfo = mountinfo_path.read_text()
                if 'docker' in mountinfo or 'overlay' in mountinfo:
                    result['is_container'] = True

        except Exception as e:
            logger.debug(f'Error checking cgroup info: {e}')

        return result

    def _extract_docker_id_from_cgroup(self, cgroup_content: str) -> str | None:
        """Extract Docker container ID from cgroup content."""
        try:
            for line in cgroup_content.split('\n'):
                if 'docker' in line and '/' in line:
                    # Extract the container ID (last part after /)
                    parts = line.split('/')
                    for part in reversed(parts):
                        if len(part) == 64 and part.isalnum():  # Docker container ID
                            return part[:12]  # Return short ID
            return None
        except Exception:
            return None

    def _check_environment_variables(self) -> dict[str, Any]:
        """Check environment variables for container indicators."""
        result = {'is_container': False}

        # Check common container environment variables
        container_vars = [
            'DOCKER_CONTAINER',
            'KUBERNETES_SERVICE_HOST',
            'KUBERNETES_PORT',
            'container',
            'PODMAN_VERSION',
            'SINGULARITY_CONTAINER',
        ]

        for var in container_vars:
            if os.getenv(var):
                result['is_container'] = True
                if 'DOCKER' in var:
                    result['runtime'] = 'docker'
                elif 'KUBERNETES' in var:
                    result['runtime'] = 'kubernetes'
                elif 'PODMAN' in var:
                    result['runtime'] = 'podman'
                elif 'SINGULARITY' in var:
                    result['runtime'] = 'singularity'
                break

        return result

    def _check_init_system(self) -> dict[str, Any]:
        """Check the init system (PID 1) for container indicators."""
        result = {'suggests_container': False}

        try:
            # Check what's running as PID 1
            with open('/proc/1/comm') as f:
                init_name = f.read().strip()
                result['init_system'] = init_name

                # In containers, PID 1 is often not a traditional init
                if init_name in ['python', 'python3', 'node', 'java', 'sh', 'bash']:
                    result['suggests_container'] = True

        except Exception as e:
            logger.debug(f'Error checking init system: {e}')

        return result

    def _get_container_id(self) -> str | None:
        """Get container ID from various sources."""
        try:
            # Try to get from hostname (Docker often sets hostname to container ID)
            hostname = socket.gethostname()
            if len(hostname) == 12 and hostname.isalnum():
                return hostname

            # Try to get from /proc/self/cgroup
            try:
                with open('/proc/self/cgroup') as f:
                    content = f.read()
                    return self._extract_docker_id_from_cgroup(content)
            except Exception:
                pass

            return None
        except Exception:
            return None

    def _get_image_name(self) -> str | None:
        """Get container image name from environment or labels."""
        try:
            # Check common environment variables
            image_vars = [
                'DOCKER_IMAGE',
                'IMAGE_NAME',
                'CONTAINER_IMAGE',
            ]

            for var in image_vars:
                image = os.getenv(var)
                if image:
                    return image

            return None
        except Exception:
            return None

    def get_volume_mount_info(self, path: str) -> VolumeInfo | None:
        """
        Get volume mount information for a specific path.

        Args:
            path: Path to check for volume mount information

        Returns:
            VolumeInfo if path is on a volume mount, None otherwise
        """
        try:
            path_obj = Path(path).resolve()

            # Read /proc/self/mountinfo to get mount information
            with open('/proc/self/mountinfo') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 10:
                        mount_point = parts[4]
                        mount_source = parts[3] if len(parts) > 9 else parts[9]
                        fs_type = parts[8] if len(parts) > 8 else 'unknown'
                        mount_options = parts[5] if len(parts) > 5 else ''

                        # Check if our path is under this mount point
                        if str(path_obj).startswith(mount_point):
                            # Determine volume type
                            volume_type = 'volume'
                            if 'bind' in mount_options:
                                volume_type = 'bind'
                            elif fs_type == 'tmpfs':
                                volume_type = 'tmpfs'

                            return VolumeInfo(
                                host_path=mount_source,
                                container_path=mount_point,
                                volume_type=volume_type,
                                read_only='ro' in mount_options,
                            )

            return None
        except Exception as e:
            logger.debug(f'Error getting volume mount info for {path}: {e}')
            return None

    def get_all_volume_mounts(self) -> list[VolumeInfo]:
        """
        Get information about all volume mounts in the container.

        Returns:
            List of VolumeInfo objects for all detected mounts
        """
        if self._volume_cache is not None:
            return self._volume_cache

        volumes = []

        try:
            with open('/proc/self/mountinfo') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 10:
                        mount_point = parts[4]
                        mount_source = parts[3] if len(parts) > 9 else parts[9]
                        fs_type = parts[8] if len(parts) > 8 else 'unknown'
                        mount_options = parts[5] if len(parts) > 5 else ''

                        # Skip system mounts
                        if mount_point.startswith(('/proc', '/sys', '/dev')):
                            continue

                        # Determine volume type
                        volume_type = 'volume'
                        if 'bind' in mount_options:
                            volume_type = 'bind'
                        elif fs_type == 'tmpfs':
                            volume_type = 'tmpfs'
                        elif fs_type in ['overlay', 'aufs']:
                            continue  # Skip overlay filesystems

                        volumes.append(
                            VolumeInfo(
                                host_path=mount_source,
                                container_path=mount_point,
                                volume_type=volume_type,
                                read_only='ro' in mount_options,
                            )
                        )

            self._volume_cache = volumes

        except Exception as e:
            logger.error(f'Error reading mount information: {e}')

        return volumes

    def optimize_for_container_performance(self) -> dict[str, Any]:
        """
        Get container-specific performance optimizations.

        Returns:
            Dictionary of optimization recommendations
        """
        optimizations = {'file_watching': {}, 'memory': {}, 'cpu': {}, 'io': {}}

        container_info = self.detect_container_environment()

        if container_info.is_container:
            # File watching optimizations for containers
            optimizations['file_watching'] = {
                'use_polling': True,  # inotify can be unreliable in containers
                'poll_interval': 2.0,  # Longer intervals in containers
                'recursive_limit': 3,  # Limit recursion depth
                'debounce_time': 1.0,  # Longer debounce for container FS
            }

            # Memory optimizations
            optimizations['memory'] = {
                'enable_gc_tuning': True,
                'cache_size_factor': 0.5,  # Smaller caches in containers
                'use_memory_mapping': False,  # Can be problematic in containers
            }

            # CPU optimizations
            try:
                cpu_count = os.cpu_count() or 1
                optimizations['cpu'] = {
                    'worker_count': min(cpu_count, 4),  # Limit workers in containers
                    'enable_threading': cpu_count > 1,
                    'batch_size_factor': 0.75,  # Smaller batches
                }
            except Exception:
                optimizations['cpu'] = {
                    'worker_count': 2,
                    'enable_threading': True,
                    'batch_size_factor': 0.75,
                }

            # I/O optimizations
            optimizations['io'] = {
                'sync_frequency': 30,  # Sync less frequently
                'buffer_size': 8192,  # Smaller buffers
                'use_async_io': True,  # Async I/O works well in containers
            }

        return optimizations


# Convenience functions for common operations
def detect_container_environment() -> ContainerInfo:
    """Detect container environment (convenience function)."""
    detector = DockerEnvironmentDetector()
    return detector.detect_container_environment()


def is_running_in_docker() -> bool:
    """Check if currently running in a Docker container."""
    return detect_container_environment().is_container


def get_container_info() -> ContainerInfo:
    """Get detailed container information."""
    return detect_container_environment()


def get_volume_mounts() -> list[VolumeInfo]:
    """Get all volume mount information."""
    detector = DockerEnvironmentDetector()
    return detector.get_all_volume_mounts()

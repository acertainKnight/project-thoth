"""
Docker detection and validation.

Detects Docker installation, daemon status, and Docker Compose availability.
"""

import platform
import subprocess
from dataclasses import dataclass
from typing import Optional

from loguru import logger


@dataclass
class DockerStatus:
    """Docker installation and runtime status."""

    installed: bool
    version: Optional[str]
    daemon_running: bool
    compose_available: bool
    compose_version: Optional[str]
    platform: str
    error_message: Optional[str] = None


class DockerDetector:
    """Detects Docker installation and status."""

    @staticmethod
    def get_platform() -> str:
        """
        Get current platform.

        Returns:
            Platform string: 'linux', 'darwin' (macOS), or 'windows'
        """
        return platform.system().lower()

    @staticmethod
    def check_docker_installed() -> tuple[bool, Optional[str]]:
        """
        Check if Docker is installed.

        Returns:
            Tuple of (installed, version)
        """
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode == 0:
                # Parse version from output like "Docker version 24.0.7, build afdd53b"
                version_line = result.stdout.strip()
                if 'version' in version_line.lower():
                    version = version_line.split()[2].rstrip(',')
                    logger.info(f'Docker detected: {version}')
                    return True, version

            return False, None

        except FileNotFoundError:
            logger.warning('Docker command not found')
            return False, None
        except Exception as e:
            logger.error(f'Error checking Docker: {e}')
            return False, None

    @staticmethod
    def check_daemon_running() -> bool:
        """
        Check if Docker daemon is running.

        Returns:
            True if daemon is running
        """
        try:
            result = subprocess.run(
                ['docker', 'info'],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode == 0:
                logger.info('Docker daemon is running')
                return True

            logger.warning(f'Docker daemon not running: {result.stderr}')
            return False

        except Exception as e:
            logger.error(f'Error checking Docker daemon: {e}')
            return False

    @staticmethod
    def check_compose_available() -> tuple[bool, Optional[str]]:
        """
        Check if Docker Compose is available.

        Returns:
            Tuple of (available, version)
        """
        try:
            # Try new 'docker compose' command first
            result = subprocess.run(
                ['docker', 'compose', 'version'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode == 0:
                # Parse version from output like "Docker Compose version v2.23.3"
                version_line = result.stdout.strip()
                if 'version' in version_line.lower():
                    parts = version_line.split()
                    version = parts[-1].lstrip('v')
                    logger.info(f'Docker Compose detected: {version}')
                    return True, version

            # Try legacy 'docker-compose' command
            result = subprocess.run(
                ['docker-compose', '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode == 0:
                version_line = result.stdout.strip()
                if 'version' in version_line.lower():
                    parts = version_line.split()
                    version = parts[2].rstrip(',')
                    logger.info(f'Docker Compose (legacy) detected: {version}')
                    return True, version

            return False, None

        except FileNotFoundError:
            logger.warning('Docker Compose not found')
            return False, None
        except Exception as e:
            logger.error(f'Error checking Docker Compose: {e}')
            return False, None

    @classmethod
    def get_status(cls) -> DockerStatus:
        """
        Get comprehensive Docker status.

        Returns:
            DockerStatus object with all detection results
        """
        platform_name = cls.get_platform()
        installed, version = cls.check_docker_installed()

        if not installed:
            return DockerStatus(
                installed=False,
                version=None,
                daemon_running=False,
                compose_available=False,
                compose_version=None,
                platform=platform_name,
                error_message='Docker is not installed',
            )

        daemon_running = cls.check_daemon_running()
        compose_available, compose_version = cls.check_compose_available()

        error_message = None
        if not daemon_running:
            error_message = 'Docker daemon is not running'
        elif not compose_available:
            error_message = 'Docker Compose is not available'

        return DockerStatus(
            installed=installed,
            version=version,
            daemon_running=daemon_running,
            compose_available=compose_available,
            compose_version=compose_version,
            platform=platform_name,
            error_message=error_message,
        )

    @staticmethod
    def get_start_daemon_command() -> str:
        """
        Get platform-specific command to start Docker daemon.

        Returns:
            Command string to start daemon
        """
        platform_name = DockerDetector.get_platform()

        commands = {
            'linux': 'sudo systemctl start docker',
            'darwin': 'open -a Docker',  # macOS
            'windows': 'Start-Service docker',  # PowerShell
        }

        return commands.get(platform_name, 'Please start Docker manually')

    @staticmethod
    def list_running_containers() -> list[dict]:
        """
        List running Docker containers.

        Returns:
            List of container dictionaries with id, name, image, status
        """
        try:
            result = subprocess.run(
                [
                    'docker',
                    'ps',
                    '--format',
                    '{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}',
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode != 0:
                return []

            containers = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) == 4:
                    containers.append({
                        'id': parts[0],
                        'name': parts[1],
                        'image': parts[2],
                        'status': parts[3],
                    })

            return containers

        except Exception as e:
            logger.error(f'Error listing containers: {e}')
            return []

    @staticmethod
    def is_container_running(name_or_id: str) -> bool:
        """
        Check if a specific container is running.

        Args:
            name_or_id: Container name or ID

        Returns:
            True if container is running
        """
        containers = DockerDetector.list_running_containers()
        return any(
            c['name'] == name_or_id or c['id'].startswith(name_or_id)
            for c in containers
        )

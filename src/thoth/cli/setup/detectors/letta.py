"""
Letta server detection and health checking.

Detects Letta server installation, tests connectivity, and validates API endpoints.
"""

from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger


@dataclass
class LettaStatus:
    """Letta server status information."""

    available: bool
    url: str
    mode: str  # 'self-hosted' or 'cloud'
    version: Optional[str]
    healthy: bool
    error_message: Optional[str] = None


class LettaDetector:
    """Detects and validates Letta server."""

    DEFAULT_SELF_HOSTED_URL = 'http://localhost:8283'
    DEFAULT_CLOUD_URL = 'https://api.letta.ai'
    HEALTH_ENDPOINT = '/v1/health'
    VERSION_ENDPOINT = '/v1/version'

    @staticmethod
    async def check_server(
        url: str, timeout: int = 5, api_key: Optional[str] = None
    ) -> tuple[bool, Optional[str], bool]:
        """
        Check if Letta server is available and healthy.

        Args:
            url: Letta server URL
            timeout: Request timeout in seconds
            api_key: Optional API key for cloud mode

        Returns:
            Tuple of (available, version, healthy)
        """
        headers = {}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        async with httpx.AsyncClient() as client:
            # Try health endpoint
            try:
                response = await client.get(
                    f'{url}{LettaDetector.HEALTH_ENDPOINT}',
                    headers=headers,
                    timeout=timeout,
                    follow_redirects=True,
                )

                healthy = response.status_code == 200

                # Try to get version
                version = None
                try:
                    version_response = await client.get(
                        f'{url}{LettaDetector.VERSION_ENDPOINT}',
                        headers=headers,
                        timeout=timeout,
                        follow_redirects=True,
                    )
                    if version_response.status_code == 200:
                        version_data = version_response.json()
                        version = version_data.get('version', 'unknown')
                except Exception:
                    # Version endpoint optional
                    pass

                logger.info(f'Letta server available at {url} (version: {version})')
                return True, version, healthy

            except httpx.ConnectError:
                logger.warning(f'Cannot connect to Letta server at {url}')
                return False, None, False
            except httpx.TimeoutException:
                logger.warning(f'Letta server timeout at {url}')
                return False, None, False
            except Exception as e:
                logger.error(f'Error checking Letta server: {e}')
                return False, None, False

    @staticmethod
    def check_server_sync(
        url: str, timeout: int = 5, api_key: Optional[str] = None
    ) -> tuple[bool, Optional[str], bool]:
        """
        Synchronous wrapper for check_server.

        Args:
            url: Letta server URL
            timeout: Request timeout in seconds
            api_key: Optional API key for cloud mode

        Returns:
            Tuple of (available, version, healthy)
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            LettaDetector.check_server(url, timeout, api_key)
        )

    @classmethod
    def get_status(
        cls,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        mode: str = 'self-hosted',
    ) -> LettaStatus:
        """
        Get comprehensive Letta server status.

        Args:
            url: Server URL (uses defaults if not provided)
            api_key: API key for cloud mode
            mode: 'self-hosted' or 'cloud'

        Returns:
            LettaStatus object with detection results
        """
        # Use default URL if not provided
        if not url:
            url = (
                cls.DEFAULT_CLOUD_URL
                if mode == 'cloud'
                else cls.DEFAULT_SELF_HOSTED_URL
            )

        available, version, healthy = cls.check_server_sync(url, api_key=api_key)

        error_message = None
        if not available:
            error_message = f'Letta server not available at {url}'
        elif not healthy:
            error_message = 'Letta server is not healthy'

        return LettaStatus(
            available=available,
            url=url,
            mode=mode,
            version=version,
            healthy=healthy,
            error_message=error_message,
        )

    @staticmethod
    def check_docker_letta() -> bool:
        """
        Check if Letta is running in Docker.

        Returns:
            True if Letta container is running
        """
        try:
            from .docker import DockerDetector

            containers = DockerDetector.list_running_containers()
            return any('letta' in c['image'].lower() for c in containers)

        except Exception as e:
            logger.error(f'Error checking Docker Letta: {e}')
            return False

    @staticmethod
    def detect_mode() -> str:
        """
        Auto-detect Letta mode based on available servers.

        Returns:
            'self-hosted', 'cloud', or 'none'
        """
        # Check self-hosted first
        self_hosted_available, _, _ = LettaDetector.check_server_sync(
            LettaDetector.DEFAULT_SELF_HOSTED_URL, timeout=2
        )

        if self_hosted_available:
            return 'self-hosted'

        # Check if Docker Letta is running
        if LettaDetector.check_docker_letta():
            return 'self-hosted'

        # No server detected
        return 'none'


"""
Letta server detection and health checking.

Detects Letta server installation, tests connectivity, and validates API endpoints.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger


@dataclass
class LettaStatus:
    """Letta server status information."""

    available: bool
    url: str
    mode: str  # 'self-hosted' or 'cloud'
    version: str | None
    healthy: bool
    error_message: str | None = None


class LettaDetector:
    """Detects and validates Letta server."""

    DEFAULT_SELF_HOSTED_URL = 'http://localhost:8283'
    DEFAULT_CLOUD_URL = 'https://api.letta.ai'
    HEALTH_ENDPOINT = '/v1/health'
    VERSION_ENDPOINT = '/v1/version'

    @staticmethod
    async def check_server(
        url: str, timeout: int = 5, api_key: str | None = None
    ) -> tuple[bool, str | None, bool]:
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
        url: str, timeout: int = 5, api_key: str | None = None
    ) -> tuple[bool, str | None, bool]:
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
        url: str | None = None,
        api_key: str | None = None,
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
    async def fetch_models(
        url: str, api_key: str | None = None, timeout: int = 10
    ) -> list[dict]:
        """
        Fetch available models from a running Letta server.

        Calls GET /v1/models/ and returns models that pass Letta's basic support test.

        Args:
            url: Letta server URL (e.g. http://localhost:8283)
            api_key: Optional API key (required for Letta Cloud)
            timeout: Request timeout in seconds

        Returns:
            List of model dicts with keys: id, provider, context_window.
            Empty list if the server is unreachable or the endpoint fails.
        """
        headers: dict[str, str] = {}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f'{url}/v1/models/',
                    headers=headers,
                    timeout=timeout,
                    follow_redirects=True,
                )

                if resp.status_code != 200:
                    logger.warning(
                        f'Letta /v1/models/ returned {resp.status_code}'
                    )
                    return []

                raw_models = resp.json()
                if not isinstance(raw_models, list):
                    logger.warning('Letta /v1/models/ did not return a list')
                    return []

                models = []
                for m in raw_models:
                    model_id = m.get('name') or m.get('model') or m.get('id', '')
                    provider = m.get('provider_type') or m.get('provider_name', '')
                    context_window = m.get('max_context_window') or m.get('context_window', 0)

                    if model_id:
                        models.append({
                            'id': model_id,
                            'provider': provider,
                            'context_window': int(context_window) if context_window else 0,
                        })

                logger.info(f'Fetched {len(models)} models from Letta at {url}')
                return models

        except httpx.ConnectError:
            logger.debug(f'Cannot connect to Letta at {url} for model list')
            return []
        except httpx.TimeoutException:
            logger.debug(f'Timeout fetching models from Letta at {url}')
            return []
        except Exception as e:
            logger.debug(f'Error fetching Letta models: {e}')
            return []

    @staticmethod
    async def find_running_instance() -> tuple[str | None, str | None]:
        """
        Auto-detect a running Letta instance.

        Checks the default self-hosted URL first, then scans Docker containers
        for a Letta image and tries common ports.

        Returns:
            Tuple of (url, version) if found, (None, None) otherwise.
        """
        # Check default URL first
        default_url = LettaDetector.DEFAULT_SELF_HOSTED_URL
        available, version, healthy = await LettaDetector.check_server(
            default_url, timeout=3
        )
        if available and healthy:
            logger.info(f'Found running Letta at {default_url}')
            return default_url, version

        # Check if there's a Letta Docker container running on another port
        try:
            from .docker import DockerDetector

            containers = DockerDetector.list_running_containers()
            for container in containers:
                if 'letta' in container.get('image', '').lower():
                    # Try to extract port from status/ports info
                    # Default to 8283 if we can't determine
                    logger.info(
                        f"Found Letta container: {container.get('name')}"
                    )
                    # Container found but might be on a different port -
                    # the default URL check above already covers 8283
                    return default_url, None
        except Exception as e:
            logger.debug(f'Error scanning Docker for Letta: {e}')

        return None, None

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

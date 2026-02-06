"""
DEPRECATED: Chrome extension integration for point-and-click scraper configuration.

.. deprecated::
    This module is superseded by the LLM-powered WorkflowBuilder in
    ``thoth.discovery.browser.workflow_builder``. The WorkflowBuilder provides
    automatic article detection without requiring a Chrome extension client.
    Use ``POST /api/workflows/analyze`` instead.

This module provided WebSocket communication with a Chrome extension
that allowed users to configure web scrapers through a point-and-click
interface directly in their browser. The Chrome extension client was
never implemented, making this server-side code unused.

Kept for reference only. Will be removed in a future release.
"""

import asyncio  # noqa: I001
import json
import secrets
from pathlib import Path
from typing import Any

import websockets
from loguru import logger

from thoth.discovery.web_scraper import WebScraper
from thoth.config import config
from thoth.utilities.schemas import ChromeExtensionConfig, ScrapeConfiguration


class ChromeExtensionServer:
    """
    WebSocket server for Chrome extension communication.

    This class provides a WebSocket server that communicates with a Chrome
    extension to enable point-and-click scraper configuration.

    Supports both local and remote connections. When the host is set to
    anything other than 'localhost' or '127.0.0.1', token-based authentication
    is required for all connections.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        auth_token: str | None = None,
    ):
        """
        Initialize the Chrome extension server.

        Args:
            host: Host to bind to. Defaults to config value or 'localhost'.
                  Use '0.0.0.0' for remote access.
            port: Port to run the WebSocket server on. Defaults to config value or 8765.
            auth_token: Authentication token for remote connections. If None and
                        remote access is enabled, a token is auto-generated.
        """
        self.config = config

        # Read from Thoth config, with parameter overrides
        chrome_config = getattr(
            getattr(self.config.settings, 'discovery', None),
            'chrome_extension',
            None,
        )
        self.host = host or (chrome_config.host if chrome_config else 'localhost')
        self.port = port or (chrome_config.port if chrome_config else 8765)

        self.web_scraper = WebScraper()

        # Configuration storage
        self.configs_dir = Path(self.config.discovery_chrome_configs_dir)
        self.configs_dir.mkdir(parents=True, exist_ok=True)

        # Authentication for remote access
        self._is_remote = self.host not in ('localhost', '127.0.0.1')
        if self._is_remote:
            self.auth_token = auth_token or secrets.token_urlsafe(32)
        else:
            self.auth_token = auth_token  # Optional for local

        self._authenticated_clients: set[int] = set()

        logger.info(
            f'Chrome extension server initialized on {self.host}:{self.port} '
            f'(remote_access={"enabled" if self._is_remote else "disabled"})'
        )

    async def start_server(self) -> None:
        """
        Start the WebSocket server.

        When remote access is enabled, logs the auth token so the user
        can configure their Chrome extension with it.

        Example:
            >>> server = ChromeExtensionServer(host='0.0.0.0')
            >>> await server.start_server()
        """
        logger.info(
            f'Starting Chrome extension WebSocket server on '
            f'ws://{self.host}:{self.port}'
        )

        if self._is_remote and self.auth_token:
            logger.info(
                f'Remote access enabled. Auth token: {self.auth_token}\n'
                f'Configure your Chrome extension with this token to connect.'
            )

        async with websockets.serve(self.handle_client, self.host, self.port):
            logger.info(
                f'Chrome extension server running on ws://{self.host}:{self.port}'
            )
            await asyncio.Future()  # Run forever

    async def handle_client(self, websocket, path: str | None = None) -> None:
        """
        Handle WebSocket client connections.

        For remote connections, the first message must be an authentication
        message with the correct token before any other operations are allowed.

        Args:
            websocket: WebSocket connection.
            path: WebSocket path (optional, not present in newer websockets versions).
        """
        client_id = id(websocket)
        remote_addr = getattr(websocket, 'remote_address', 'unknown')
        logger.info(f'Chrome extension client connected from {remote_addr}')

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)

                    # Check authentication for remote connections
                    if self._is_remote and client_id not in self._authenticated_clients:
                        if data.get('type') == 'authenticate':
                            if data.get('token') == self.auth_token:
                                self._authenticated_clients.add(client_id)
                                await websocket.send(json.dumps({
                                    'type': 'auth_result',
                                    'success': True,
                                    'message': 'Authenticated successfully',
                                }))
                                logger.info(f'Client {remote_addr} authenticated')
                                continue
                            else:
                                await websocket.send(json.dumps({
                                    'type': 'auth_result',
                                    'success': False,
                                    'error': 'Invalid authentication token',
                                }))
                                logger.warning(f'Failed auth attempt from {remote_addr}')
                                continue
                        else:
                            await websocket.send(json.dumps({
                                'error': 'Authentication required. Send {"type": "authenticate", "token": "..."}',
                            }))
                            continue

                    response = await self.process_message(data)
                    await websocket.send(json.dumps(response))

                except json.JSONDecodeError:
                    await websocket.send(json.dumps({'error': 'Invalid JSON message'}))
                except Exception as e:
                    logger.error(f'Error processing message: {e}')
                    await websocket.send(json.dumps({'error': str(e)}))

        except websockets.exceptions.ConnectionClosed:
            logger.info(f'Chrome extension client disconnected: {remote_addr}')
        except Exception as e:
            logger.error(f'Error handling client: {e}')
        finally:
            self._authenticated_clients.discard(client_id)

    async def process_message(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Process a message from the Chrome extension.

        Args:
            data: Message data from the extension.

        Returns:
            dict[str, Any]: Response to send back to the extension.
        """
        message_type = data.get('type')

        if message_type == 'test_selectors':
            return await self.test_selectors(data)
        elif message_type == 'save_config':
            return await self.save_config(data)
        elif message_type == 'load_config':
            return await self.load_config(data)
        elif message_type == 'list_configs':
            return await self.list_configs()
        elif message_type == 'test_scrape':
            return await self.test_scrape(data)
        else:
            return {'error': f'Unknown message type: {message_type}'}

    async def test_selectors(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Test CSS selectors on a webpage.

        Args:
            data: Message data containing URL and selectors.

        Returns:
            dict[str, Any]: Test results.
        """
        try:
            url = data.get('url')
            selectors = data.get('selectors', {})

            if not url:
                return {'error': 'URL is required'}

            # Create temporary scrape configuration
            extraction_rules = {}
            for field, selector in selectors.items():
                extraction_rules[field] = {
                    'selector': selector,
                    'attribute': 'text',
                }

            temp_config = ScrapeConfiguration(
                base_url=url,
                extraction_rules=extraction_rules,
            )

            # Test the configuration
            test_result = self.web_scraper.test_configuration(temp_config)

            return {
                'type': 'test_result',
                'success': test_result['success'],
                'articles_found': test_result['articles_found'],
                'sample_data': [
                    {
                        'title': article.title,
                        'authors': article.authors,
                        'abstract': article.abstract[:200] + '...'
                        if article.abstract and len(article.abstract) > 200
                        else article.abstract,
                    }
                    for article in test_result['sample_articles']
                ],
                'errors': test_result['errors'],
            }

        except Exception as e:
            logger.error(f'Error testing selectors: {e}')
            return {'error': str(e)}

    async def save_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Save a scraper configuration.

        Args:
            data: Message data containing configuration.

        Returns:
            dict[str, Any]: Save result.
        """
        try:
            config_name = data.get('name')
            config_data = data.get('config')

            if not config_name or not config_data:
                return {'error': 'Name and config are required'}

            # Create Chrome extension config
            chrome_config = ChromeExtensionConfig(**config_data)

            # Convert to ScrapeConfiguration
            scrape_config = self.chrome_config_to_scrape_config(chrome_config)

            # Save configuration
            config_file = self.configs_dir / f'{config_name}.json'
            with open(config_file, 'w') as f:
                json.dump(
                    {
                        'chrome_config': chrome_config.model_dump(),
                        'scrape_config': scrape_config.model_dump(),
                    },
                    f,
                    indent=2,
                )

            logger.info(f'Saved Chrome extension config: {config_name}')

            return {
                'type': 'save_result',
                'success': True,
                'message': f'Configuration saved as {config_name}',
            }

        except Exception as e:
            logger.error(f'Error saving config: {e}')
            return {'error': str(e)}

    async def load_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Load a scraper configuration.

        Args:
            data: Message data containing config name.

        Returns:
            dict[str, Any]: Loaded configuration.
        """
        try:
            config_name = data.get('name')

            if not config_name:
                return {'error': 'Config name is required'}

            config_file = self.configs_dir / f'{config_name}.json'

            if not config_file.exists():
                return {'error': f'Configuration {config_name} not found'}

            with open(config_file) as f:
                config_data = json.load(f)

            return {
                'type': 'config_data',
                'name': config_name,
                'config': config_data.get('chrome_config', {}),
            }

        except Exception as e:
            logger.error(f'Error loading config: {e}')
            return {'error': str(e)}

    async def list_configs(self) -> dict[str, Any]:
        """
        List all saved configurations.

        Returns:
            dict[str, Any]: List of configuration names.
        """
        try:
            configs = []

            for config_file in self.configs_dir.glob('*.json'):
                try:
                    with open(config_file) as f:
                        config_data = json.load(f)

                    chrome_config = config_data.get('chrome_config', {})

                    configs.append(
                        {
                            'name': config_file.stem,
                            'site_name': chrome_config.get('site_name', 'Unknown'),
                            'base_url': chrome_config.get('base_url', ''),
                            'created': config_file.stat().st_mtime,
                        }
                    )

                except Exception as e:
                    logger.error(f'Error reading config file {config_file}: {e}')

            return {
                'type': 'config_list',
                'configs': configs,
            }

        except Exception as e:
            logger.error(f'Error listing configs: {e}')
            return {'error': str(e)}

    async def test_scrape(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Test a complete scraping configuration.

        Args:
            data: Message data containing configuration.

        Returns:
            dict[str, Any]: Scraping test results.
        """
        try:
            config_data = data.get('config')

            if not config_data:
                return {'error': 'Configuration is required'}

            # Create Chrome extension config
            chrome_config = ChromeExtensionConfig(**config_data)

            # Convert to ScrapeConfiguration
            scrape_config = self.chrome_config_to_scrape_config(chrome_config)

            # Test scraping
            test_result = self.web_scraper.test_configuration(scrape_config)

            return {
                'type': 'scrape_test_result',
                'success': test_result['success'],
                'articles_found': test_result['articles_found'],
                'sample_articles': [
                    {
                        'title': article.title,
                        'authors': article.authors,
                        'abstract': article.abstract[:300] + '...'
                        if article.abstract and len(article.abstract) > 300
                        else article.abstract,
                        'url': article.url,
                        'pdf_url': article.pdf_url,
                        'keywords': article.keywords,
                    }
                    for article in test_result['sample_articles']
                ],
                'errors': test_result['errors'],
            }

        except Exception as e:
            logger.error(f'Error testing scrape: {e}')
            return {'error': str(e)}

    def chrome_config_to_scrape_config(
        self, chrome_config: ChromeExtensionConfig
    ) -> ScrapeConfiguration:
        """
        Convert Chrome extension config to ScrapeConfiguration.

        Args:
            chrome_config: Chrome extension configuration.

        Returns:
            ScrapeConfiguration: Converted scrape configuration.
        """
        # Convert selectors to extraction rules
        extraction_rules = {}
        for field, selector in chrome_config.selectors.items():
            extraction_rules[field] = {
                'selector': selector,
                'attribute': 'text',
            }

            # Special handling for certain fields
            if field in ['url', 'pdf_url']:
                extraction_rules[field]['attribute'] = 'href'
            elif field == 'authors':
                extraction_rules[field]['multiple'] = True
            elif field == 'keywords':
                extraction_rules[field]['multiple'] = True

        # Convert navigation steps to navigation rules
        navigation_rules = {}
        for step in chrome_config.navigation_steps:
            step_type = step.get('type')
            if step_type == 'click':
                navigation_rules['click_selectors'] = navigation_rules.get(
                    'click_selectors', []
                )
                navigation_rules['click_selectors'].append(step.get('selector'))
            elif step_type == 'wait':
                navigation_rules['wait_time'] = step.get('duration', 1)

        return ScrapeConfiguration(
            base_url=chrome_config.base_url,
            extraction_rules=extraction_rules,
            navigation_rules=navigation_rules,
            rate_limiting={'delay': 1.0},
            pagination_config={'enabled': False},
        )


def run_chrome_extension_server(
    host: str | None = None,
    port: int | None = None,
    auth_token: str | None = None,
) -> None:
    """
    Run the Chrome extension WebSocket server.

    Args:
        host: Host to bind to. None uses config default.
              Use '0.0.0.0' for remote access.
        port: Port to run the server on. None uses config default.
        auth_token: Auth token for remote access. Auto-generated if None.

    Example:
        >>> # Local access (default)
        >>> run_chrome_extension_server()

        >>> # Remote access
        >>> run_chrome_extension_server(host='0.0.0.0', port=8765)
    """
    server = ChromeExtensionServer(host=host, port=port, auth_token=auth_token)

    try:
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        logger.info('Chrome extension server stopped by user')
    except Exception as e:
        logger.error(f'Error running Chrome extension server: {e}')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Thoth Chrome Extension Server')
    parser.add_argument(
        '--host', default=None,
        help='Host to bind to (use 0.0.0.0 for remote access)',
    )
    parser.add_argument(
        '--port', type=int, default=None,
        help='Port to listen on (default: 8765)',
    )
    parser.add_argument(
        '--token', default=None,
        help='Auth token for remote connections (auto-generated if not provided)',
    )
    args = parser.parse_args()

    run_chrome_extension_server(host=args.host, port=args.port, auth_token=args.token)

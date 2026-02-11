"""Deployment mode selection screen for setup wizard.

Allows users to choose between local (Docker on this machine) or remote
(Thoth already running on another server).
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from .base import BaseScreen


class DeploymentModeScreen(BaseScreen):
    """Screen for selecting deployment mode: local or remote."""

    def __init__(self) -> None:
        """Initialize deployment mode selection screen."""
        super().__init__(
            title='Select Deployment Mode',
            subtitle='Choose where Thoth will run',
        )
        self.selected_mode: str = ''  # 'local' or 'remote'
        self.thoth_api_url: str = 'http://localhost:8000'
        self.detected_version: str | None = None

    def compose_content(self) -> ComposeResult:
        """
        Compose deployment mode selection content.

        Returns:
            Content widgets
        """
        yield Static(
            "Choose whether you're setting up Thoth locally or "
            'connecting to an existing remote installation.',
            classes='help-text',
        )

        # Mode selection with RadioSet
        # Use Tab / arrow keys to switch between options
        with RadioSet(id='mode-selection'):
            yield RadioButton(
                'Local (This Machine) - Recommended',
                id='mode-local',
                value=True,
            )
            yield RadioButton(
                'Remote (Another Server)',
                id='mode-remote',
            )

        # Local mode description
        with Vertical(id='local-section'):
            yield Static(
                '  [green]✓[/green] Docker on this machine  '
                '[green]✓[/green] Full control  '
                '[green]✓[/green] Auto-start services\n'
                '  [yellow]○[/yellow] Requires Docker (~3-5GB disk, ~1.5GB RAM)',
            )

        # Remote mode section (hidden by default)
        with Vertical(id='remote-section', classes='hidden'):
            yield Static(
                '  [green]✓[/green] No Docker needed locally  '
                '[green]✓[/green] Lightweight  '
                '[yellow]○[/yellow] Server must be running',
            )

            yield Static(
                '\n[yellow]Before using remote mode:[/yellow]\n'
                '  1. Run this wizard on your server FIRST (local mode)\n'
                '  2. Obsidian + vault must exist on the server\n'
                '  3. Start services there ([cyan]thoth start[/cyan])',
                classes='help-text',
            )

            yield Static('', id='remote-status', classes='help-text')

            yield Label('[cyan]Thoth Server URL:[/cyan]')
            yield Input(
                placeholder='http://your-server:8000',
                value='http://localhost:8000',
                id='thoth-api-url',
            )

            yield Button('Test Connection', id='test-connection', variant='primary')

        yield Static(
            '\n[dim]Use ↑/↓ arrows to switch mode. Change later in plugin settings.[/dim]',
            classes='help-text',
        )

    def on_mount(self) -> None:
        """Run when screen is mounted."""
        pass  # Nothing to auto-detect yet

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle mode selection changes."""
        selected_id = event.pressed.id
        logger.info(f'Deployment mode selected: {selected_id}')

        local_section = self.query_one('#local-section')
        remote_section = self.query_one('#remote-section')

        if selected_id == 'mode-remote':
            local_section.add_class('hidden')
            remote_section.remove_class('hidden')
            self._focus_task = asyncio.create_task(self._focus_widget('#thoth-api-url'))
        else:
            remote_section.add_class('hidden')
            local_section.remove_class('hidden')

    async def _focus_widget(self, selector: str) -> None:
        """Focus a widget after a brief delay for the UI to update."""
        await asyncio.sleep(0.1)
        try:
            widget = self.query_one(selector, Input)
            widget.focus()
        except Exception as e:
            logger.debug('Widget not ready to focus: %s', e)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id

        if button_id == 'cancel':
            self.action_cancel()
        elif button_id == 'back':
            self.action_back()
        elif button_id == 'test-connection':
            await self._test_remote_connection()
        elif button_id == 'next':
            data = await self.validate_and_proceed()
            if data is not None:
                if hasattr(self.app, 'wizard_data'):
                    self.app.wizard_data.update(data)
                await self.on_next_screen()

    async def _test_remote_connection(self) -> None:
        """Test connection to remote Thoth server."""
        url_input = self.query_one('#thoth-api-url', Input)
        url = url_input.value.strip()

        if not url:
            self.show_error('Please enter a server URL')
            return

        self.show_info(f'Testing connection to {url}...')
        status_widget = self.query_one('#remote-status', Static)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f'{url}/health', timeout=10.0)

                if resp.status_code == 200:
                    health_data = resp.json()
                    version = health_data.get('version', 'unknown')
                    self.detected_version = version

                    self.clear_messages()
                    self.show_success(f'Connected to Thoth v{version}')
                    status_widget.update(
                        f'[green]✓ Thoth v{version} is reachable at {url}[/green]'
                    )
                else:
                    self.show_error(
                        f'Server returned status {resp.status_code}. '
                        'Is this a Thoth server?'
                    )
                    status_widget.update(
                        f'[yellow]Server at {url} is not responding correctly[/yellow]'
                    )

        except httpx.ConnectError:
            self.show_error(f'Cannot connect to {url}. Check the URL and network.')
            status_widget.update(f'[red]✗ Cannot reach {url}[/red]')
        except httpx.TimeoutError:  # type: ignore[attr-defined]
            self.show_error(f'Connection to {url} timed out.')
            status_widget.update(f'[red]✗ Timeout connecting to {url}[/red]')
        except Exception as e:
            self.show_error(f'Connection test failed: {e}')
            status_widget.update(f'[red]✗ Error: {e}[/red]')

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate deployment mode and remote URL if needed.

        Returns:
            Dict with deployment_mode, thoth_api_url, thoth_mcp_url,
            or None if validation fails.
        """
        # Get selected mode
        try:
            radio_set = self.query_one('#mode-selection', RadioSet)
            pressed_button = radio_set.pressed_button

            if pressed_button is None:
                self.show_error('Please select a deployment mode')
                return None

            self.selected_mode = (
                'remote' if pressed_button.id == 'mode-remote' else 'local'
            )
        except Exception as e:
            logger.error(f'Error reading mode selection: {e}')
            self.show_error(f'Failed to read mode selection: {e}')
            return None

        # --- Local mode ---
        if self.selected_mode == 'local':
            return {
                'deployment_mode': 'local',
                'thoth_api_url': 'http://localhost:8000',
                'thoth_mcp_url': 'http://localhost:8001',
            }

        # --- Remote mode ---
        url_input = self.query_one('#thoth-api-url', Input)
        api_url = url_input.value.strip()

        if not api_url:
            self.show_error('Please enter the Thoth API server URL')
            url_input.focus()
            return None

        # Validate URL format
        try:
            parsed = urlparse(api_url)
            if not parsed.scheme or not parsed.netloc:
                self.show_error(
                    'Invalid URL format. Must include protocol (http:// or https://)'
                )
                url_input.focus()
                return None
        except Exception:
            self.show_error('Invalid URL format')
            url_input.focus()
            return None

        # Derive MCP URL from API URL (same host, port 8001)
        parsed = urlparse(api_url)
        mcp_url = f'{parsed.scheme}://{parsed.hostname}:8001'

        # Try to connect (non-blocking warning if unreachable)
        self.show_info(f'Verifying connection to {api_url}...')
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f'{api_url}/health', timeout=10.0)

                if resp.status_code == 200:
                    health_data = resp.json()
                    version = health_data.get('version', 'unknown')
                    self.clear_messages()
                    self.show_success(f'Connected to Thoth v{version}')
                else:
                    self.show_warning(
                        f'Server returned status {resp.status_code}. '
                        'Proceeding anyway - verify the URL is correct.'
                    )
                    await asyncio.sleep(1)
                    self.clear_messages()

        except Exception as e:
            self.show_warning(
                f'Cannot reach {api_url}: {e}\n'
                'Proceeding anyway - ensure the server is running before using Thoth.'
            )
            await asyncio.sleep(1.5)
            self.clear_messages()

        logger.info(f'Remote deployment: API={api_url}, MCP={mcp_url} (auto-derived)')

        return {
            'deployment_mode': 'remote',
            'thoth_api_url': api_url,
            'thoth_mcp_url': mcp_url,  # Auto-derived, not shown to user
        }

    async def on_next_screen(self) -> None:
        """Navigate to Letta mode selection screen."""
        from .letta_mode_selection import LettaModeSelectionScreen

        deployment_mode = 'local'
        if hasattr(self.app, 'wizard_data'):
            deployment_mode = self.app.wizard_data.get('deployment_mode', 'local')

        logger.info(
            f'Proceeding to Letta mode selection (deployment={deployment_mode})'
        )
        await self.app.push_screen(
            LettaModeSelectionScreen(deployment_mode=deployment_mode)
        )

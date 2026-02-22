"""Deployment mode selection screen for setup wizard.

Allows users to choose between local (Docker on this machine) or remote
(Thoth already running on another server).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from ..config_manager import ConfigManager
from .base import BaseScreen


class DeploymentModeScreen(BaseScreen):
    """Screen for selecting deployment mode: local or remote."""

    def __init__(self, vault_path: Path | None = None) -> None:
        """Initialize deployment mode selection screen.

        Args:
            vault_path: Path to Obsidian vault for loading existing config.
        """
        super().__init__(
            title='Select Deployment Mode',
            subtitle='Choose where Thoth will run',
        )
        self.selected_mode: str = ''  # 'local' or 'remote'
        self.thoth_api_url: str = 'http://localhost:8000'
        self.detected_version: str | None = None
        self.verified_user_info: dict[str, Any] | None = None
        self.existing_config: dict[str, Any] = {}
        self.vault_path: Path | None = vault_path

        if vault_path:
            try:
                cm = ConfigManager(vault_path)
                self.existing_config = cm.load_existing() or {}
            except Exception as e:
                logger.debug(f'Could not load existing config: {e}')

    def compose_content(self) -> ComposeResult:
        """Compose deployment mode selection content.

        Returns:
            Content widgets
        """
        # Determine defaults from existing config
        existing_mode = self._get_existing_deployment_mode()
        is_remote = existing_mode == 'remote'

        yield Static(
            "Choose whether you're setting up Thoth locally or "
            'connecting to an existing remote installation.',
            classes='help-text',
        )

        with RadioSet(id='mode-selection'):
            yield RadioButton(
                'Local (This Machine) - Recommended',
                id='mode-local',
                value=not is_remote,
            )
            yield RadioButton(
                'Remote (Another Server)',
                id='mode-remote',
                value=is_remote,
            )

        with Vertical(id='local-section', classes='hidden' if is_remote else ''):
            yield Static(
                '  [green]✓[/green] Docker on this machine  '
                '[green]✓[/green] Full control  '
                '[green]✓[/green] Auto-start services\n'
                '  [yellow]○[/yellow] Requires Docker (~3-5GB disk, ~1.5GB RAM)',
            )

        with Vertical(id='remote-section', classes='' if is_remote else 'hidden'):
            yield Static(
                '  [green]✓[/green] No Docker needed locally  '
                '[green]✓[/green] Lightweight  '
                '[yellow]○[/yellow] Server must be running',
            )

            yield Static(
                '\n[yellow]Your admin provides these values when creating your account.[/yellow]',
                classes='help-text',
            )

            yield Static('', id='remote-status', classes='help-text')

            yield Label('[cyan]Thoth Server URL:[/cyan]')
            yield Input(
                placeholder='https://your-server/thoth',
                value=self._get_existing_api_url(),
                id='thoth-api-url',
            )

            yield Label('[cyan]Letta Server URL:[/cyan]')
            yield Input(
                placeholder='https://your-server/letta',
                value=self._get_existing_letta_url(),
                id='letta-api-url',
            )

            yield Label('[cyan]API Token (multi-user):[/cyan]')
            yield Input(
                placeholder='thoth_...',
                password=True,
                value=self._get_existing_api_token(),
                id='api-token',
            )

            yield Button('Verify Connection', id='test-connection', variant='primary')

        yield Static(
            '\n[dim]Use ↑/↓ arrows to switch mode. Change later in plugin settings.[/dim]',
            classes='help-text',
        )

    def on_mount(self) -> None:
        """Run when screen is mounted."""

    def _get_existing_deployment_mode(self) -> str:
        """Infer deployment mode from existing settings.json.

        Returns:
            'local' or 'remote' based on existing API base URL.
        """
        servers = self.existing_config.get('servers', {})
        api = servers.get('api', {})
        base_url = api.get('baseUrl', 'http://localhost:8000')
        parsed = urlparse(base_url)
        if parsed.hostname and parsed.hostname not in ('localhost', '127.0.0.1'):
            return 'remote'
        return 'local'

    def _get_existing_letta_url(self) -> str:
        """Get existing Letta URL from settings.json.

        Returns:
            Letta URL string.
        """
        letta = self.existing_config.get('letta', {})
        return letta.get('url', '')

    def _get_existing_api_token(self) -> str:
        """Get existing API token from plugin data.json if available.

        Returns:
            Token string, or empty string.
        """
        if not self.vault_path:
            return ''
        try:
            import json

            data_path = (
                self.vault_path
                / '.obsidian'
                / 'plugins'
                / 'thoth-obsidian'
                / 'data.json'
            )
            if data_path.exists():
                data = json.loads(data_path.read_text())
                return data.get('apiToken', '')
        except Exception:
            pass
        return ''

    def _get_existing_api_url(self) -> str:
        """Get existing API URL from settings.json, or the default.

        Returns:
            API URL string.
        """
        servers = self.existing_config.get('servers', {})
        api = servers.get('api', {})
        return api.get('baseUrl', 'http://localhost:8000')

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
        """Test connection to remote Thoth server and verify API token."""
        url_input = self.query_one('#thoth-api-url', Input)
        token_input = self.query_one('#api-token', Input)
        url = url_input.value.strip().rstrip('/')
        token = token_input.value.strip()

        if not url:
            self.show_error('Please enter a server URL')
            return

        self.show_info(f'Testing connection to {url}...')
        status_widget = self.query_one('#remote-status', Static)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f'{url}/health', timeout=10.0)

                if resp.status_code not in (200, 503):
                    self.show_error(
                        f'Server returned {resp.status_code}. Is this a Thoth server?'
                    )
                    status_widget.update(
                        f'[yellow]Server at {url} is not responding correctly[/yellow]'
                    )
                    return

                lines = [f'[green]✓ Thoth server reachable at {url}[/green]']

                if token:
                    me_resp = await client.get(
                        f'{url}/auth/me',
                        headers={'Authorization': f'Bearer {token}'},
                        timeout=10.0,
                    )
                    if me_resp.status_code == 200:
                        user_info = me_resp.json()
                        username = user_info.get('username', '?')
                        lines.append(
                            f'[green]✓ Authenticated as [bold]{username}[/bold][/green]'
                        )
                        self.verified_user_info = user_info
                    elif me_resp.status_code == 401:
                        lines.append('[red]✗ Invalid token[/red]')
                    else:
                        lines.append(
                            f'[yellow]Token check returned {me_resp.status_code}[/yellow]'
                        )
                else:
                    lines.append(
                        '[yellow]No token entered — enter your token to verify[/yellow]'
                    )

                self.clear_messages()
                status_widget.update('\n'.join(lines))

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

        # Read Letta URL and API token from the form
        letta_input = self.query_one('#letta-api-url', Input)
        token_input = self.query_one('#api-token', Input)
        letta_url = letta_input.value.strip().rstrip('/')
        api_token = token_input.value.strip()

        if not letta_url:
            self.show_error('Please enter the Letta server URL')
            letta_input.focus()
            return None

        # Derive MCP URL from API URL (same host, port 8001)
        parsed = urlparse(api_url)
        mcp_url = f'{parsed.scheme}://{parsed.hostname}:8001'

        # Verify connection (non-blocking)
        self.show_info(f'Verifying connection to {api_url}...')
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f'{api_url}/health', timeout=10.0)

                if resp.status_code in (200, 503):
                    self.clear_messages()
                    self.show_success('Server reachable')
                else:
                    self.show_warning(
                        f'Server returned {resp.status_code}. Proceeding anyway.'
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

        result: dict[str, Any] = {
            'deployment_mode': 'remote',
            'thoth_api_url': api_url,
            'thoth_mcp_url': mcp_url,
            'letta_url': letta_url,
        }

        if api_token:
            result['api_token'] = api_token

        if self.verified_user_info:
            result['user_info'] = self.verified_user_info

        logger.info(
            f'Remote deployment: API={api_url}, Letta={letta_url}, '
            f'token={"set" if api_token else "none"}'
        )

        return result

    async def on_next_screen(self) -> None:
        """Navigate to Letta mode selection screen."""
        from .letta_mode_selection import LettaModeSelectionScreen

        deployment_mode = 'local'
        vault_path = None
        if hasattr(self.app, 'wizard_data'):
            deployment_mode = self.app.wizard_data.get('deployment_mode', 'local')
            vault_path = self.app.wizard_data.get('vault_path')

        logger.info(
            f'Proceeding to Letta mode selection (deployment={deployment_mode})'
        )
        await self.app.push_screen(
            LettaModeSelectionScreen(
                deployment_mode=deployment_mode,
                vault_path=vault_path,
            )
        )

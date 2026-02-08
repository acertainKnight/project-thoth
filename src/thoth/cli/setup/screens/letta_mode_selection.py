"""
Letta mode selection screen for setup wizard.

Allows users to choose between self-hosted Letta (Docker) or Letta Cloud (API).
When self-hosted is selected, auto-detects a running Letta instance and fetches
available models from its /v1/models/ endpoint.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Label, RadioButton, RadioSet, Static

from ..detectors.letta import LettaDetector
from .base import BaseScreen


class LettaModeSelectionScreen(BaseScreen):
    """Screen for selecting Letta mode: self-hosted or cloud."""

    def __init__(self, deployment_mode: str = 'local') -> None:
        """
        Initialize Letta mode selection screen.

        Args:
            deployment_mode: 'local' or 'remote', passed from DeploymentModeScreen
        """
        super().__init__(
            title='Select Letta Mode',
            subtitle='Choose how you want to run Letta agent memory',
        )
        self.selected_mode: str = ''  # 'self-hosted', 'cloud', or 'remote'
        self.cloud_api_key: str = ''
        self.letta_url: str = ''
        self.letta_live_models: list[str] = []
        self.deployment_mode: str = deployment_mode

    def compose_content(self) -> ComposeResult:
        """
        Compose Letta mode selection content.

        Returns:
            Content widgets
        """
        if self.deployment_mode == 'local':
            yield Static(
                'Letta provides persistent memory for AI agents.',
                classes='help-text',
            )
        else:
            yield Static(
                'Letta provides persistent memory for AI agents.\n'
                '[dim]Since Thoth is remote, Letta must also be reachable by the '
                'remote server (local Docker is not shown).[/dim]',
                classes='help-text',
            )

        # Mode selection with RadioSet - different options based on deployment mode
        with RadioSet(id='mode-selection'):
            if self.deployment_mode == 'local':
                yield RadioButton(
                    'Self-Hosted (via Docker) - Recommended',
                    id='mode-self-hosted',
                    value=True,
                )
                yield RadioButton(
                    'Letta Cloud (API-based)',
                    id='mode-cloud',
                )
            else:
                # Remote deployment - show remote Letta option
                yield RadioButton(
                    'Remote Server (Connect to existing Letta)',
                    id='mode-remote',
                    value=True,
                )
                yield RadioButton(
                    'Letta Cloud (API-based)',
                    id='mode-cloud',
                )

        # Self-hosted section (shown by default for local deployment)
        with Vertical(
            id='self-hosted-section',
            classes='hidden' if self.deployment_mode == 'remote' else '',
        ):
            yield Static(
                '  [green]✓[/green] Full control  [green]✓[/green] Offline  '
                '[green]✓[/green] No rate limits  [yellow]○[/yellow] Needs Docker',
            )
            yield Static('', id='self-hosted-status', classes='help-text')
            yield Label('[cyan]Letta Server URL:[/cyan]')
            yield Input(
                placeholder='http://localhost:8283',
                value='http://localhost:8283',
                id='self-hosted-url',
            )

        # Remote section (shown by default for remote deployment)
        with Vertical(
            id='remote-section',
            classes='' if self.deployment_mode == 'remote' else 'hidden',
        ):
            yield Static(
                '  [green]✓[/green] No local Docker  [green]✓[/green] Centralized  '
                '[yellow]○[/yellow] Server must be running',
            )
            yield Static('', id='remote-status', classes='help-text')
            yield Label('[cyan]Letta Server URL:[/cyan]')
            yield Input(
                placeholder='http://your-server:8283',
                value='http://localhost:8283',
                id='remote-url',
            )

        # Cloud section (hidden by default)
        with Vertical(id='cloud-section', classes='hidden'):
            yield Static(
                '  [green]✓[/green] Instant setup  [green]✓[/green] No infra  '
                '[yellow]○[/yellow] Needs internet',
            )
            yield Label('[cyan]Letta Cloud API Key:[/cyan]')
            yield Static(
                '[dim]Get key at: https://app.letta.com/api-keys[/dim]',
                classes='help-text',
            )
            yield Input(
                placeholder='Enter your Letta Cloud API key',
                password=True,
                id='cloud-api-key',
            )

        yield Static(
            '\n[dim]You can change this later with: thoth letta configure[/dim]',
            classes='help-text',
        )

    def on_mount(self) -> None:
        """Run when screen is mounted. Auto-detect running Letta instance."""
        # For remote deployment, pre-fill remote Letta URL from Thoth API URL
        if self.deployment_mode == 'remote' and hasattr(self.app, 'wizard_data'):
            thoth_api_url = self.app.wizard_data.get('thoth_api_url', '')
            if thoth_api_url:
                # Derive Letta URL: same host, port 8283
                from urllib.parse import urlparse

                parsed = urlparse(thoth_api_url)
                suggested_letta_url = f'{parsed.scheme}://{parsed.hostname}:8283'
                try:
                    remote_url_input = self.query_one('#remote-url', Input)
                    remote_url_input.value = suggested_letta_url
                except Exception:
                    pass

        self._detect_task = asyncio.create_task(self._detect_letta())

    async def _detect_letta(self) -> None:
        """Auto-detect a running Letta instance and update the UI."""
        if self.deployment_mode == 'local':
            # Only auto-detect for local self-hosted mode
            try:
                status_widget = self.query_one('#self-hosted-status', Static)
                status_widget.update(
                    '[dim]Checking for running Letta instance...[/dim]'
                )

                url, version = await LettaDetector.find_running_instance()

                if url:
                    version_str = f' (v{version})' if version else ''
                    status_widget.update(
                        f'[green]✓ Letta detected at {url}{version_str}[/green]'
                    )
                    # Pre-fill the URL
                    try:
                        url_input = self.query_one('#self-hosted-url', Input)
                        url_input.value = url
                    except Exception:
                        pass

                    self.letta_url = url

                    # Fetch live model list
                    models = await LettaDetector.fetch_models(url)
                    if models:
                        self.letta_live_models = [
                            f'{m["provider"]}/{m["id"]}'
                            if m.get('provider')
                            else m['id']
                            for m in models
                        ]
                        status_widget.update(
                            f'[green]✓ Letta detected at {url}{version_str} '
                            f'— {len(self.letta_live_models)} models available[/green]'
                        )
                        logger.info(
                            f'Fetched {len(self.letta_live_models)} live models from Letta'
                        )
                else:
                    status_widget.update(
                        '[yellow]No running Letta found. '
                        "It will start automatically with 'thoth start'.[/yellow]"
                    )
            except Exception:
                pass  # Widget might not exist yet
        elif self.deployment_mode == 'remote':
            # For remote mode, try to detect from the pre-filled URL
            try:
                remote_url_input = self.query_one('#remote-url', Input)
                url = remote_url_input.value.strip()
                if url:
                    status_widget = self.query_one('#remote-status', Static)
                    status_widget.update('[dim]Checking remote Letta server...[/dim]')

                    available, version, healthy = await LettaDetector.check_server(
                        url, timeout=3
                    )
                    if available and healthy:
                        status_widget.update(
                            f'[green]✓ Letta v{version or "unknown"} detected at {url}[/green]'
                        )
                        # Fetch models
                        models = await LettaDetector.fetch_models(url)
                        if models:
                            self.letta_live_models = [
                                f'{m["provider"]}/{m["id"]}'
                                if m.get('provider')
                                else m['id']
                                for m in models
                            ]
                            logger.info(
                                f'Fetched {len(self.letta_live_models)} live models from remote Letta'
                            )
                    else:
                        status_widget.update(
                            "[yellow]Remote Letta server not reachable. Verify the URL and ensure it's running.[/yellow]"
                        )
            except Exception:
                pass  # Widget might not exist yet

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle mode selection changes."""
        selected_id = event.pressed.id
        logger.info(f'Letta mode selected: {selected_id}')

        self_hosted_section = self.query_one('#self-hosted-section')
        cloud_section = self.query_one('#cloud-section')
        remote_section = self.query_one('#remote-section')

        if selected_id == 'mode-cloud':
            self_hosted_section.add_class('hidden')
            remote_section.add_class('hidden')
            cloud_section.remove_class('hidden')
            self._focus_task = asyncio.create_task(self._focus_widget('#cloud-api-key'))
        elif selected_id == 'mode-remote':
            self_hosted_section.add_class('hidden')
            cloud_section.add_class('hidden')
            remote_section.remove_class('hidden')
            self._focus_task = asyncio.create_task(self._focus_widget('#remote-url'))
        else:  # mode-self-hosted
            cloud_section.add_class('hidden')
            remote_section.add_class('hidden')
            self_hosted_section.remove_class('hidden')

    async def _focus_widget(self, selector: str) -> None:
        """Focus a widget after a brief delay for the UI to update."""
        await asyncio.sleep(0.1)
        try:
            widget = self.query_one(selector, Input)
            widget.focus()
        except Exception:
            pass

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate mode selection and connection details.

        Returns:
            Dict with letta_mode, letta_url, letta_api_key, letta_live_models,
            or None if validation fails.
        """
        # Get selected mode
        try:
            radio_set = self.query_one('#mode-selection', RadioSet)
            pressed_button = radio_set.pressed_button

            if pressed_button is None:
                self.show_error('Please select a Letta mode')
                return None

            if pressed_button.id == 'mode-cloud':
                self.selected_mode = 'cloud'
            elif pressed_button.id == 'mode-remote':
                self.selected_mode = 'remote'
            else:
                self.selected_mode = 'self-hosted'
        except Exception as e:
            logger.error(f'Error reading mode selection: {e}')
            self.show_error(f'Failed to read mode selection: {e}')
            return None

        # --- Remote validation ---
        if self.selected_mode == 'remote':
            url_input = self.query_one('#remote-url', Input)
            self.letta_url = url_input.value.strip()

            if not self.letta_url:
                self.show_error('Please enter the remote Letta server URL')
                url_input.focus()
                return None

            # Try to reach the server
            self.show_info(f'Connecting to remote Letta at {self.letta_url}...')
            available, version, healthy = await LettaDetector.check_server(
                self.letta_url, timeout=10
            )

            if available and healthy:
                self.clear_messages()
                self.show_success(
                    f'Connected to Letta (v{version or "unknown"}) at {self.letta_url}'
                )
                # Fetch models from the remote server
                models = await LettaDetector.fetch_models(self.letta_url)
                if models:
                    self.letta_live_models = [
                        f'{m["provider"]}/{m["id"]}' if m.get('provider') else m['id']
                        for m in models
                    ]
                    logger.info(
                        f'Fetched {len(self.letta_live_models)} models from remote Letta'
                    )
            else:
                self.show_warning(
                    f'Cannot reach Letta at {self.letta_url}. '
                    'Proceeding anyway - ensure the server is running before using Thoth.'
                )
                await asyncio.sleep(1.5)
                self.clear_messages()

            return {
                'letta_mode': 'remote',
                'letta_url': self.letta_url,
                'letta_api_key': '',
                'letta_live_models': self.letta_live_models,
            }

        # --- Self-hosted validation ---
        if self.selected_mode == 'self-hosted':
            url_input = self.query_one('#self-hosted-url', Input)
            self.letta_url = url_input.value.strip() or 'http://localhost:8283'

            # Try to reach the server (non-blocking, don't fail if unreachable)
            self.show_info(f'Checking Letta at {self.letta_url}...')
            available, version, healthy = await LettaDetector.check_server(
                self.letta_url, timeout=3
            )

            if available and healthy:
                self.clear_messages()
                self.show_success(
                    f'Connected to Letta (v{version or "unknown"}) at {self.letta_url}'
                )
                # Refresh models from the live server
                models = await LettaDetector.fetch_models(self.letta_url)
                if models:
                    self.letta_live_models = [
                        f'{m["provider"]}/{m["id"]}' if m.get('provider') else m['id']
                        for m in models
                    ]
            else:
                self.clear_messages()
                self.show_info(
                    f"Letta not reachable at {self.letta_url} — that's OK. "
                    'Using default model list.'
                )
                await asyncio.sleep(1)
                self.clear_messages()

            return {
                'letta_mode': 'self-hosted',
                'letta_url': self.letta_url,
                'letta_api_key': '',
                'letta_live_models': self.letta_live_models,
            }

        # --- Cloud validation ---
        try:
            api_key_input = self.query_one('#cloud-api-key', Input)
            self.cloud_api_key = api_key_input.value.strip()

            if not self.cloud_api_key:
                self.show_error(
                    'Please enter your Letta Cloud API key. '
                    'Get one at https://app.letta.com/api-keys'
                )
                api_key_input.focus()
                return None

            self.show_info('Validating Letta Cloud API key...')
            cloud_url = 'https://api.letta.com'
            available, version, healthy = await LettaDetector.check_server(
                url=cloud_url,
                api_key=self.cloud_api_key,
                timeout=10,
            )

            if not available or not healthy:
                self.show_error(
                    'Failed to authenticate with Letta Cloud. '
                    'Please verify your API key at https://app.letta.com/api-keys'
                )
                api_key_input.focus()
                return None

            # Fetch cloud models
            models = await LettaDetector.fetch_models(
                cloud_url, api_key=self.cloud_api_key
            )
            if models:
                self.letta_live_models = [
                    f'{m["provider"]}/{m["id"]}' if m.get('provider') else m['id']
                    for m in models
                ]

            self.clear_messages()
            self.show_success(f'Connected to Letta Cloud (v{version or "unknown"})')

            return {
                'letta_mode': 'cloud',
                'letta_url': cloud_url,
                'letta_api_key': self.cloud_api_key,
                'letta_live_models': self.letta_live_models,
            }

        except Exception as e:
            logger.error(f'Error validating cloud API key: {e}')
            self.show_error(
                f'Failed to connect to Letta Cloud: {e}\n'
                'Please check your internet connection and API key.'
            )
            return None

    async def on_next_screen(self) -> None:
        """Navigate to API keys screen."""
        from .api_keys import APIKeysScreen

        vault_path = None
        if hasattr(self.app, 'wizard_data'):
            vault_path = self.app.wizard_data.get('vault_path')

        logger.info('Proceeding to API keys configuration')
        await self.app.push_screen(APIKeysScreen(vault_path=vault_path))

"""
Welcome screen for setup wizard.

Displays welcome message, introduction, and prerequisites check.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.widgets import Button, Static

from .base import BaseScreen


def _is_docker_setup() -> bool:
    """Check if running inside the Docker setup container."""
    return os.environ.get('THOTH_DOCKER_SETUP') == '1'


def _host_to_container_path(host_path: Path) -> Path:
    """Translate a host filesystem path to the equivalent container path."""
    host_home = os.environ.get('THOTH_HOST_HOME', '')
    if not host_home:
        return host_path
    container_home = str(Path.home())
    path_str = str(host_path)
    if path_str.startswith(host_home):
        return Path(container_home + path_str[len(host_home) :])
    return host_path


def _container_to_host_path(container_path: Path) -> Path:
    """Translate a container path back to the host filesystem path."""
    host_home = os.environ.get('THOTH_HOST_HOME', '')
    if not host_home:
        return container_path
    container_home = str(Path.home())
    path_str = str(container_path)
    if path_str.startswith(container_home):
        return Path(host_home + path_str[len(container_home) :])
    return container_path


class WelcomeScreen(BaseScreen):
    """Welcome screen for Thoth setup wizard."""

    def __init__(self) -> None:
        """Initialize welcome screen."""
        super().__init__(
            title='Welcome to Thoth Setup',
            subtitle='AI-Powered Research Assistant for Obsidian',
        )
        self.existing_config: dict[str, Any] | None = None
        self.has_existing_installation = False

    def on_mount(self) -> None:
        """Run when screen is mounted - detect existing installation."""
        self._detect_existing_installation()

    def _detect_existing_installation(self) -> None:
        """Check if there's already a valid Thoth installation."""
        vault_path_str = os.environ.get('OBSIDIAN_VAULT_PATH', '').strip()
        if not vault_path_str:
            logger.info('No OBSIDIAN_VAULT_PATH in environment')
            return

        try:
            # Resolve the vault path
            vault_path = Path(vault_path_str).expanduser().resolve()

            # Handle Docker path translation
            if _is_docker_setup() and not vault_path.exists():
                vault_path = _host_to_container_path(vault_path)

            if not vault_path.exists() or not vault_path.is_dir():
                logger.info(f'Vault path does not exist: {vault_path}')
                return

            # Check for settings.json (new and legacy locations)
            settings_path = vault_path / 'thoth' / '_thoth' / 'settings.json'
            legacy_path = vault_path / '_thoth' / 'settings.json'

            if not settings_path.exists() and legacy_path.exists():
                settings_path = legacy_path

            if not settings_path.exists():
                logger.info(f'No settings.json found in vault: {vault_path}')
                return

            # Try to load settings with Pydantic validation
            from thoth.config import Settings

            settings = Settings.from_json_file(settings_path)

            # If we got here, we have a valid config
            self.has_existing_installation = True

            # Store config info for the update path
            vault_path_host = vault_path
            if _is_docker_setup():
                vault_path_host = _container_to_host_path(vault_path)

            self.existing_config = {
                'vault_path': vault_path,
                'vault_path_host': vault_path_host,
                'settings_path': settings_path,
                'settings': settings,
                'version': settings.version or 'unknown',
            }

            logger.info(
                f'Detected existing installation at {vault_path} (version: {settings.version})'
            )

            # Update UI to show the update option
            self._show_update_option()

        except Exception as e:
            logger.debug(f'Error detecting existing installation: {e}')
            # Not fatal - user can still do full setup

    def _show_update_option(self) -> None:
        """Update the UI to show the update option."""
        if not self.existing_config:
            return

        try:
            # Update the welcome text to show detected config
            welcome_widget = self.query_one('.welcome-content', Static)
            vault_display = self.existing_config['vault_path_host']
            version = self.existing_config['version']

            new_text = f"""
[bold cyan]Welcome to Thoth![/bold cyan]

[bold green]Existing installation detected![/bold green]

  Vault: [cyan]{vault_display}[/cyan]
  Version: [cyan]{version}[/cyan]

[bold]Choose how to proceed:[/bold]

  • [yellow]Update Software[/yellow] - Keep your settings, update templates & plugin
  • [cyan]Begin Setup[/cyan] - Reconfigure everything (will preserve existing files)

[bold cyan]Navigation:[/bold cyan]
  • [dim]Tab to switch between buttons[/dim]
  • [dim]Enter to select[/dim]
  • [dim]ESC to exit wizard[/dim]
            """

            welcome_widget.update(new_text.strip())

            # Show the update button
            try:
                update_btn = self.query_one('#update', Button)
                update_btn.styles.display = 'block'
            except Exception:
                pass  # Button might not exist yet

        except Exception as e:
            logger.debug(f'Could not update UI: {e}')

    def compose_content(self) -> ComposeResult:
        """
        Compose welcome content.

        Returns:
            Content widgets
        """
        welcome_text = """
[bold cyan]Welcome to Thoth![/bold cyan]

Thoth is an AI-powered research assistant that integrates with Obsidian
to help you discover, analyze, and manage academic papers and research.

[bold]This wizard will guide you through:[/bold]

  • [cyan]✓[/cyan] Selecting your Obsidian vault
  • [cyan]✓[/cyan] Configuring AI models and API keys
  • [cyan]✓[/cyan] Setting up Letta memory service
  • [cyan]✓[/cyan] Installing the Obsidian plugin
  • [cyan]✓[/cyan] Testing your configuration

[bold]Prerequisites:[/bold]

  • [bold]Docker installed and running[/bold] (required)
  • Obsidian installed (we'll help you download it if needed)
  • API keys for at least one LLM provider (OpenAI, Anthropic, or Google)
  • ~5 GB free disk space
  • Internet connection

[bold cyan]Navigation:[/bold cyan]
  • [dim]← / → arrow keys to go Back / Next[/dim]
  • [dim]Tab/Shift+Tab to move between fields[/dim]
  • [dim]↑ / ↓ to select options in lists[/dim]
  • [dim]Space to toggle checkboxes[/dim]
  • [dim]Enter for Next[/dim]
  • [dim]ESC to exit wizard[/dim]
  • [dim]F1 for help anytime[/dim]

[dim]Press Enter or → to start.[/dim]
        """

        yield Static(welcome_text, classes='welcome-content')

    def compose_buttons(self) -> ComposeResult:
        """
        Compose buttons for welcome screen.

        Returns:
            Button widgets
        """
        yield Button('Exit', id='cancel', variant='error')

        # Update button (hidden by default, shown when existing config detected)
        update_btn = Button('Update Software', id='update', variant='primary')
        update_btn.styles.display = 'none'
        yield update_btn

        yield Button('Begin Setup', id='next', variant='success')

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        Args:
            event: Button pressed event
        """
        button_id = event.button.id

        if button_id == 'update':
            await self._handle_update_path()
        else:
            # Delegate to base class for cancel/next
            await super().on_button_pressed(event)

    async def _handle_update_path(self) -> None:
        """Handle the update-only path - skip config and go to installation."""
        if not self.existing_config:
            self.show_error('No existing configuration detected')
            return

        logger.info('User chose update-only path')

        # Extract paths from existing settings
        settings = self.existing_config['settings']
        paths_config = {
            'workspace': settings.paths.workspace,
            'pdf': settings.paths.pdf,
            'markdown': settings.paths.markdown,
            'notes': settings.paths.notes,
        }

        # Populate wizard_data with minimal info needed for installation
        if hasattr(self.app, 'wizard_data'):
            self.app.wizard_data.update(
                {
                    'vault_path': self.existing_config['vault_path'],
                    'vault_path_host': self.existing_config['vault_path_host'],
                    'paths_config': paths_config,
                    'update_only': True,
                }
            )

        # Jump directly to installation
        from .installation import InstallationScreen

        logger.info('Jumping to installation for update-only')
        await self.app.push_screen(InstallationScreen())

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate welcome screen (always passes).

        Returns:
            Empty dict (no data to collect from welcome screen)
        """
        logger.info('Starting Thoth setup wizard')
        return {}

    async def on_next_screen(self) -> None:
        """Navigate to vault selection screen."""
        from .vault_selection import VaultSelectionScreen

        logger.info('Proceeding to vault selection')
        await self.app.push_screen(VaultSelectionScreen())

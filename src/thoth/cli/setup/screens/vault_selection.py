"""Vault selection screen for setup wizard.

Detects and displays available Obsidian vaults for user selection.
Includes an advanced expandable section for customising Thoth's
directory paths (PDFs, notes, markdown, workspace).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Collapsible, Input, Label, RadioButton, RadioSet, Static

from ..detectors.obsidian import ObsidianDetector, ObsidianStatus, ObsidianVault
from .base import BaseScreen


def _is_docker_setup() -> bool:
    """Check if running inside the Docker setup container."""
    return os.environ.get('THOTH_DOCKER_SETUP') == '1'


def _host_to_container_path(host_path: Path) -> Path:
    """Translate a host filesystem path to the equivalent container path.

    Inside the Docker setup container, the host's home directory is mounted
    at /root (e.g. /Users/alice/Documents -> /root/Documents).

    Args:
        host_path: Absolute path on the host filesystem.

    Returns:
        Equivalent path inside the container, or the original path unchanged.
    """
    host_home = os.environ.get('THOTH_HOST_HOME', '')
    if not host_home:
        return host_path
    container_home = str(Path.home())
    path_str = str(host_path)
    if path_str.startswith(host_home):
        return Path(container_home + path_str[len(host_home) :])
    return host_path


def _container_to_host_path(container_path: Path) -> Path:
    """Translate a container path back to the host filesystem path.

    Args:
        container_path: Absolute path inside the container.

    Returns:
        Equivalent path on the host, or the original path unchanged.
    """
    host_home = os.environ.get('THOTH_HOST_HOME', '')
    if not host_home:
        return container_path
    container_home = str(Path.home())
    path_str = str(container_path)
    if path_str.startswith(container_home):
        return Path(host_home + path_str[len(container_home) :])
    return container_path


# Default paths relative to vault root
DEFAULT_PATHS = {
    'pdf': 'thoth/papers/pdfs',
    'notes': 'thoth/notes',
    'markdown': 'thoth/papers/markdown',
    'workspace': 'thoth/_thoth',
}


class VaultSelectionScreen(BaseScreen):
    """Screen for selecting Obsidian vault."""

    def __init__(self) -> None:
        """Initialize vault selection screen."""
        super().__init__(
            title='Select Obsidian Vault',
            subtitle='Choose the vault where Thoth will be installed',
        )
        self.obsidian_status: ObsidianStatus | None = None
        self.vaults: list[ObsidianVault] = []
        self.selected_vault: Path | None = None
        self.custom_path: str = ''

    def on_mount(self) -> None:
        """Run when screen is mounted."""
        # Detect Obsidian and vaults in background
        self._detect_task = asyncio.create_task(self.detect_obsidian())

    async def detect_obsidian(self) -> None:
        """Detect Obsidian installation and vaults."""
        self.show_info('Detecting Obsidian installation and vaults...')

        try:
            # First, check if vault is already configured via environment
            env_vault = ObsidianDetector.detect_vault_from_env()
            if env_vault:
                logger.info(f'Vault detected from environment: {env_vault}')
                # Create a vault entry from the environment variable
                self.vaults = [
                    ObsidianVault(
                        path=env_vault,
                        name=env_vault.name,
                        has_thoth_workspace=(
                            (env_vault / 'thoth' / '_thoth').exists()
                            or (env_vault / '_thoth').exists()
                        ),
                        config_exists=(
                            (env_vault / 'thoth' / '_thoth' / 'settings.json').exists()
                            or (env_vault / '_thoth' / 'settings.json').exists()
                        ),
                    )
                ]
                self.clear_messages()
                self.show_info(f'Found vault from environment: {env_vault.name}')
                self.refresh()
                return

            # Detect Obsidian installation
            self.obsidian_status = ObsidianDetector.get_status()

            if not self.obsidian_status.installed:
                download_url = ObsidianDetector.get_download_url()
                self.show_error(f'Obsidian not detected. Download from: {download_url}')
            else:
                logger.info(
                    f'Obsidian detected: {self.obsidian_status.version or "unknown version"}'
                )

            # Get vaults (with timeout protection)
            self.vaults = self.obsidian_status.vaults

            if not self.vaults:
                self.clear_messages()
                self.show_error(
                    'No vaults found automatically. Please enter your vault path below.'
                )
                # Focus the custom path input
                await asyncio.sleep(0.1)  # Let UI update
                try:
                    custom_input = self.query_one('#custom-path', Input)
                    custom_input.focus()
                except Exception:
                    pass  # Input might not be mounted yet
            else:
                self.clear_messages()
                logger.info(f'Found {len(self.vaults)} vault(s)')

            # Refresh UI to show vaults
            self.refresh()

        except Exception as e:
            logger.error(f'Error detecting Obsidian: {e}')
            self.show_error(f'Failed to detect Obsidian: {e}')

    def compose_content(self) -> ComposeResult:
        """Compose vault selection content.

        Returns:
            Content widgets
        """
        # Vault list section (only show if we have vaults)
        if self.vaults:
            yield Static('[bold]Detected Vaults:[/bold]', classes='section-title')
            with Vertical(id='vault-list'):
                with RadioSet(id='vault-radio'):
                    for vault in self.vaults:
                        status = ''
                        if vault.has_thoth_workspace:
                            status = ' [cyan](Thoth installed)[/cyan]'
                        # Show the host path when running in Docker
                        display_path = vault.path
                        if _is_docker_setup():
                            display_path = _container_to_host_path(vault.path)
                        yield RadioButton(
                            f'{vault.name} - {display_path}{status}',
                            value=str(vault.path),  # type: ignore[arg-type]
                        )

            # Custom path as alternative
            yield Label('\n[bold]Or enter vault path manually:[/bold]')
        else:
            # No vaults found - make custom path primary
            yield Static(
                '[yellow]No vaults found automatically[/yellow]',
                classes='section-title',
            )
            yield Static(
                '[dim]Searching timed out or no vaults in common locations.[/dim]'
            )
            yield Label(
                '\n[bold cyan]Please enter your Obsidian vault path:[/bold cyan]'
            )

        # Custom path input (always shown)
        yield Input(
            placeholder='/path/to/your/obsidian/vault (e.g., ~/Documents/MyVault)',
            id='custom-path',
        )

        # Help text
        if not self.vaults:
            if _is_docker_setup():
                yield Static(
                    '\n[dim]Enter the path as it appears on your computer '
                    '(e.g., ~/Documents/My Vault).\n'
                    'The installer will translate it automatically.[/dim]',
                    classes='help-text',
                )
            else:
                yield Static(
                    '\n[dim]You can also set the OBSIDIAN_VAULT_PATH '
                    'environment variable.[/dim]',
                    classes='help-text',
                )

        # Advanced: directory path configuration
        with Collapsible(title='Advanced: Customize Directory Paths', collapsed=True):
            yield Static(
                '[dim]Paths are relative to your vault. For example, if your vault\n'
                'is at [bold]~/Documents/MyVault[/bold], the default PDF path becomes\n'
                '[bold]~/Documents/MyVault/thoth/papers/pdfs[/bold].\n'
                'Defaults are fine for most users.[/dim]\n',
            )

            yield Label('[cyan]PDF Directory[/cyan]')
            yield Static(
                '[dim]Where Thoth stores and reads research PDFs.  vault/[bold]...[/bold][/dim]',
            )
            yield Input(
                placeholder=DEFAULT_PATHS['pdf'],
                value=DEFAULT_PATHS['pdf'],
                id='path-pdf',
            )

            yield Label('[cyan]Notes Directory[/cyan]')
            yield Static(
                '[dim]Where Thoth creates analysis notes and summaries.  vault/[bold]...[/bold][/dim]',
            )
            yield Input(
                placeholder=DEFAULT_PATHS['notes'],
                value=DEFAULT_PATHS['notes'],
                id='path-notes',
            )

            yield Label('[cyan]Markdown Directory[/cyan]')
            yield Static(
                '[dim]Parsed markdown from PDFs (used for RAG indexing).  vault/[bold]...[/bold][/dim]',
            )
            yield Input(
                placeholder=DEFAULT_PATHS['markdown'],
                value=DEFAULT_PATHS['markdown'],
                id='path-markdown',
            )

            yield Label('[cyan]Workspace Directory[/cyan]')
            yield Static(
                '[dim]Internal data (settings, cache, logs). Usually no need to change.  vault/[bold]...[/bold][/dim]',
            )
            yield Input(
                placeholder=DEFAULT_PATHS['workspace'],
                value=DEFAULT_PATHS['workspace'],
                id='path-workspace',
            )

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """Validate vault selection and collect directory path settings.

        Returns:
            Dict with selected vault path and custom paths, or None if invalid.
        """
        # Get selected vault from radio buttons (if any vaults were found)
        selected_value = None
        if self.vaults:
            try:
                radio_set = self.query_one('#vault-radio', RadioSet)
                selected_value = radio_set.pressed_button
            except Exception as e:
                logger.debug(f'Radio set might not exist if no vaults: {e}')

        if selected_value:
            # Radio value is already a container path (from auto-detection)
            self.selected_vault = Path(str(selected_value.value))
        else:
            # Check custom path
            custom_input = self.query_one('#custom-path', Input)
            custom_path_str = custom_input.value.strip()

            if custom_path_str:
                self.selected_vault = Path(custom_path_str).expanduser().resolve()

                # In Docker, the user likely entered a host path (e.g.
                # /Users/alice/Documents/MyVault). Translate to the container
                # path for validation since host paths don't exist here.
                if _is_docker_setup() and not self.selected_vault.exists():
                    translated = _host_to_container_path(self.selected_vault)
                    if translated != self.selected_vault and translated.exists():
                        logger.info(
                            f'Translated host path {self.selected_vault} '
                            f'-> container path {translated}'
                        )
                        self.selected_vault = translated
            else:
                if self.vaults:
                    self.show_error('Please select a vault or enter a custom path')
                else:
                    self.show_error('Please enter your Obsidian vault path')
                return None

        # Validate vault path (against the container filesystem when in Docker)
        if not self.selected_vault.exists():
            display_path = self.selected_vault
            hint = ''
            if _is_docker_setup():
                display_path = _container_to_host_path(self.selected_vault)
                hint = (
                    '\nMake sure the vault is inside ~/Documents '
                    '(or ~/Obsidian) so the installer can access it.'
                )
            self.show_error(f'Vault path does not exist: {display_path}{hint}')
            return None

        if not self.selected_vault.is_dir():
            self.show_error(f'Vault path is not a directory: {self.selected_vault}')
            return None

        # Check if it's a valid Obsidian vault
        if not ObsidianDetector.is_valid_vault(self.selected_vault):
            self.show_error(
                'Selected path is not a valid Obsidian vault (missing .obsidian directory)'
            )
            return None

        # Collect directory path settings from advanced section
        paths_config: dict[str, str] = {}
        for key in ('pdf', 'notes', 'markdown', 'workspace'):
            try:
                path_input = self.query_one(f'#path-{key}', Input)
                value = path_input.value.strip()
                paths_config[key] = value if value else DEFAULT_PATHS[key]
            except Exception as e:
                logger.debug(f'Could not read path input for {key}, using default: {e}')
                paths_config[key] = DEFAULT_PATHS[key]

        # Validate paths don't contain suspicious characters
        for key, path_val in paths_config.items():
            if '..' in path_val:
                self.show_error(f"Path for {key} must not contain '..'")
                return None
            if path_val.startswith('/') or path_val.startswith('~'):
                self.show_error(
                    f'Path for {key} must be relative to the vault root '
                    f"(got '{path_val}')"
                )
                return None

        # vault_path = path for file ops (container); vault_path_host = for config(host)
        vault_path_host = self.selected_vault
        if _is_docker_setup():
            vault_path_host = _container_to_host_path(self.selected_vault)

        logger.info(f'Selected vault: {self.selected_vault}')
        if _is_docker_setup():
            logger.info(f'Host vault path (for config): {vault_path_host}')
        logger.info(f'Paths config: {paths_config}')
        return {
            'vault_path': self.selected_vault,
            'vault_path_host': vault_path_host,
            'paths_config': paths_config,
        }

    async def on_next_screen(self) -> None:
        """Navigate to deployment mode selection screen."""
        from .deployment_mode import DeploymentModeScreen

        vault_path = None
        if hasattr(self.app, 'wizard_data'):
            vault_path = self.app.wizard_data.get('vault_path')

        logger.info('Proceeding to deployment mode selection')
        await self.app.push_screen(DeploymentModeScreen(vault_path=vault_path))

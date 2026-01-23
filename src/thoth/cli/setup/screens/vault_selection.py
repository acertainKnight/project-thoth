"""
Vault selection screen for setup wizard.

Detects and displays available Obsidian vaults for user selection.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Label, RadioButton, RadioSet, Static

from ..detectors.obsidian import ObsidianDetector, ObsidianStatus, ObsidianVault
from .base import BaseScreen


class VaultSelectionScreen(BaseScreen):
    """Screen for selecting Obsidian vault."""

    def __init__(self) -> None:
        """Initialize vault selection screen."""
        super().__init__(
            title="Select Obsidian Vault",
            subtitle="Choose the vault where Thoth will be installed",
        )
        self.obsidian_status: ObsidianStatus | None = None
        self.vaults: list[ObsidianVault] = []
        self.selected_vault: Path | None = None
        self.custom_path: str = ""

    def on_mount(self) -> None:
        """Run when screen is mounted."""
        # Detect Obsidian and vaults in background
        self._detect_task = asyncio.create_task(self.detect_obsidian())

    async def detect_obsidian(self) -> None:
        """Detect Obsidian installation and vaults."""
        self.show_info("Detecting Obsidian installation and vaults...")

        try:
            # First, check if vault is already configured via environment
            env_vault = ObsidianDetector.detect_vault_from_env()
            if env_vault:
                logger.info(f"Vault detected from environment: {env_vault}")
                # Create a vault entry from the environment variable
                self.vaults = [
                    ObsidianVault(
                        path=env_vault,
                        name=env_vault.name,
                        has_thoth_workspace=(env_vault / "_thoth").exists(),
                        config_exists=(
                            env_vault / "_thoth" / "settings.json"
                        ).exists(),
                    )
                ]
                self.clear_messages()
                self.show_info(
                    f"Found vault from environment: {env_vault.name}"
                )
                self.refresh()
                return

            # Detect Obsidian installation
            self.obsidian_status = ObsidianDetector.get_status()

            if not self.obsidian_status.installed:
                download_url = ObsidianDetector.get_download_url()
                self.show_error(
                    f"Obsidian not detected. Download from: {download_url}"
                )
            else:
                logger.info(
                    f"Obsidian detected: {self.obsidian_status.version or 'unknown version'}"
                )

            # Get vaults (with timeout protection)
            self.vaults = self.obsidian_status.vaults

            if not self.vaults:
                self.clear_messages()
                self.show_error(
                    "No vaults found automatically. Please enter your vault path below."
                )
                # Focus the custom path input
                await asyncio.sleep(0.1)  # Let UI update
                try:
                    custom_input = self.query_one("#custom-path", Input)
                    custom_input.focus()
                except Exception:
                    pass  # Input might not be mounted yet
            else:
                self.clear_messages()
                logger.info(f"Found {len(self.vaults)} vault(s)")

            # Refresh UI to show vaults
            self.refresh()

        except Exception as e:
            logger.error(f"Error detecting Obsidian: {e}")
            self.show_error(f"Failed to detect Obsidian: {e}")

    def compose_content(self) -> ComposeResult:
        """
        Compose vault selection content.

        Returns:
            Content widgets
        """
        # Vault list section (only show if we have vaults)
        if self.vaults:
            yield Static("[bold]Detected Vaults:[/bold]", classes="section-title")
            with Vertical(id="vault-list"):
                with RadioSet(id="vault-radio"):
                    for vault in self.vaults:
                        status = ""
                        if vault.has_thoth_workspace:
                            status = " [cyan](Thoth installed)[/cyan]"
                        yield RadioButton(
                            f"{vault.name} - {vault.path}{status}",
                            value=str(vault.path),
                        )

            # Custom path as alternative
            yield Label("\n[bold]Or enter vault path manually:[/bold]")
        else:
            # No vaults found - make custom path primary
            yield Static(
                "[yellow]⚠ No vaults found automatically[/yellow]",
                classes="section-title",
            )
            yield Static(
                "[dim]Searching timed out or no vaults in common locations.[/dim]"
            )
            yield Label("\n[bold cyan]Please enter your Obsidian vault path:[/bold cyan]")

        # Custom path input (always shown)
        yield Input(
            placeholder="/path/to/your/obsidian/vault (e.g., ~/Documents/MyVault)",
            id="custom-path",
        )

        # Help text
        if not self.vaults:
            yield Static(
                "\n[dim]Tip: You can also set OBSIDIAN_VAULT_PATH environment variable[/dim]",
                classes="help-text",
            )

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate vault selection.

        Returns:
            Dict with selected vault path, or None if invalid
        """
        # Get selected vault from radio buttons (if any vaults were found)
        selected_value = None
        if self.vaults:
            try:
                radio_set = self.query_one("#vault-radio", RadioSet)
                selected_value = radio_set.pressed_button
            except Exception:
                pass  # Radio set might not exist if no vaults

        if selected_value:
            self.selected_vault = Path(selected_value.value)
        else:
            # Check custom path
            custom_input = self.query_one("#custom-path", Input)
            custom_path_str = custom_input.value.strip()

            if custom_path_str:
                self.selected_vault = Path(custom_path_str).expanduser().resolve()
            else:
                if self.vaults:
                    self.show_error("Please select a vault or enter a custom path")
                else:
                    self.show_error("Please enter your Obsidian vault path")
                return None

        # Validate vault path
        if not self.selected_vault.exists():
            self.show_error(f"Vault path does not exist: {self.selected_vault}")
            return None

        if not self.selected_vault.is_dir():
            self.show_error(f"Vault path is not a directory: {self.selected_vault}")
            return None

        # Check if it's a valid Obsidian vault
        if not ObsidianDetector.is_valid_vault(self.selected_vault):
            self.show_error(
                "Selected path is not a valid Obsidian vault (missing .obsidian directory)"
            )
            return None

        logger.info(f"Selected vault: {self.selected_vault}")
        return {"vault_path": self.selected_vault}

    async def on_next_screen(self) -> None:
        """Navigate to configuration screen."""
        from .configuration import ConfigurationScreen

        logger.info("Proceeding to configuration")
        await self.app.push_screen(ConfigurationScreen())

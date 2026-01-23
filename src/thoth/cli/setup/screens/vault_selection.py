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
            # Detect Obsidian
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

            # Get vaults
            self.vaults = self.obsidian_status.vaults

            if not self.vaults:
                self.show_info(
                    "No vaults found. You can specify a custom vault path below."
                )
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
        yield Static("[bold]Detected Vaults:[/bold]", classes="section-title")

        # Vault list
        with Vertical(id="vault-list"):
            if self.vaults:
                with RadioSet(id="vault-radio"):
                    for vault in self.vaults:
                        status = ""
                        if vault.has_thoth_workspace:
                            status = " [cyan](Thoth installed)[/cyan]"
                        yield RadioButton(
                            f"{vault.name} - {vault.path}{status}",
                            value=str(vault.path),
                        )
            else:
                yield Static(
                    "[dim]No vaults detected yet. Searching...[/dim]",
                    classes="no-vaults",
                )

        # Custom path option
        yield Label("\n[bold]Or specify custom vault path:[/bold]")
        yield Input(
            placeholder="/path/to/your/obsidian/vault",
            id="custom-path",
        )

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate vault selection.

        Returns:
            Dict with selected vault path, or None if invalid
        """
        # Get selected vault from radio buttons
        radio_set = self.query_one("#vault-radio", RadioSet)
        selected_value = radio_set.pressed_button

        if selected_value:
            self.selected_vault = Path(selected_value.value)
        else:
            # Check custom path
            custom_input = self.query_one("#custom-path", Input)
            custom_path_str = custom_input.value.strip()

            if custom_path_str:
                self.selected_vault = Path(custom_path_str).expanduser().resolve()
            else:
                self.show_error("Please select a vault or specify a custom path")
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

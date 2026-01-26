"""
Letta mode selection screen for setup wizard.

Allows users to choose between self-hosted Letta (Docker) or Letta Cloud (API).
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

    def __init__(self) -> None:
        """Initialize Letta mode selection screen."""
        super().__init__(
            title="Select Letta Mode",
            subtitle="Choose how you want to run Letta agent memory",
        )
        self.selected_mode: str = ""  # 'self-hosted' or 'cloud'
        self.cloud_api_key: str = ""

    def compose_content(self) -> ComposeResult:
        """
        Compose Letta mode selection content.

        Returns:
            Content widgets
        """
        yield Static(
            "[bold]Choose how you want to run Letta:[/bold]\n",
            classes="section-title",
        )

        yield Static(
            "Letta provides persistent memory for AI agents. "
            "You can run it yourself or use the cloud service.",
            classes="help-text",
        )

        # Mode selection with RadioSet
        with RadioSet(id="mode-selection"):
            # Self-Hosted option
            with Vertical(classes="mode-option"):
                yield RadioButton(
                    "[cyan]Self-Hosted[/cyan] (via Docker)",
                    id="mode-self-hosted",
                    value=True,  # Default selection
                )
                yield Static(
                    "  [green]✓[/green] Full control and privacy\n"
                    "  [green]✓[/green] Works offline\n"
                    "  [green]✓[/green] No API rate limits\n"
                    "  [red]✗[/red] Requires Docker (~2GB disk, ~500MB RAM)\n"
                    "  [red]✗[/red] More complex setup",
                    classes="mode-description",
                )

            # Spacing
            yield Static("")

            # Cloud option
            with Vertical(classes="mode-option"):
                yield RadioButton(
                    "[cyan]Letta Cloud[/cyan]",
                    id="mode-cloud",
                )
                yield Static(
                    "  [green]✓[/green] Instant setup (just need API key)\n"
                    "  [green]✓[/green] No infrastructure to manage\n"
                    "  [green]✓[/green] Automatic updates\n"
                    "  [red]✗[/red] Requires internet connection\n"
                    "  [red]✗[/red] Subject to API rate limits",
                    classes="mode-description",
                )

        # Cloud API key input (initially hidden)
        with Vertical(id="cloud-api-key-section", classes="cloud-config"):
            yield Static("\n[bold]Letta Cloud API Key:[/bold]")
            yield Static(
                "Get your API key at: [link=https://app.letta.com/api-keys]"
                "https://app.letta.com/api-keys[/link]",
                classes="help-text",
            )
            yield Input(
                placeholder="Enter your Letta Cloud API key",
                password=True,
                id="cloud-api-key",
            )

        yield Static(
            "\n[dim]You can change this later with: thoth letta configure[/dim]",
            classes="help-text",
        )

    def on_mount(self) -> None:
        """Run when screen is mounted."""
        # Hide cloud config initially
        cloud_section = self.query_one("#cloud-api-key-section")
        cloud_section.styles.display = "none"

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle mode selection changes."""
        selected_id = event.pressed.id
        logger.info(f"Letta mode selected: {selected_id}")

        # Show/hide cloud API key section based on selection
        cloud_section = self.query_one("#cloud-api-key-section")

        if selected_id == "mode-cloud":
            cloud_section.styles.display = "block"
            # Focus the API key input
            asyncio.create_task(self._focus_api_key())
        else:
            cloud_section.styles.display = "none"

    async def _focus_api_key(self) -> None:
        """Focus the API key input after a brief delay."""
        await asyncio.sleep(0.1)  # Let UI update
        try:
            api_key_input = self.query_one("#cloud-api-key", Input)
            api_key_input.focus()
        except Exception:
            pass  # Input might not be ready yet

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate mode selection and cloud API key if needed.

        Returns:
            Dict with mode and api_key, or None if validation fails
        """
        # Get selected mode
        try:
            radio_set = self.query_one("#mode-selection", RadioSet)
            pressed_button = radio_set.pressed_button

            if pressed_button is None:
                self.show_error("Please select a Letta mode")
                return None

            if pressed_button.id == "mode-cloud":
                self.selected_mode = "cloud"
            else:
                self.selected_mode = "self-hosted"

        except Exception as e:
            logger.error(f"Error reading mode selection: {e}")
            self.show_error(f"Failed to read mode selection: {e}")
            return None

        # If cloud mode, validate API key
        if self.selected_mode == "cloud":
            try:
                api_key_input = self.query_one("#cloud-api-key", Input)
                self.cloud_api_key = api_key_input.value.strip()

                if not self.cloud_api_key:
                    self.show_error(
                        "Please enter your Letta Cloud API key. "
                        "Get one at https://app.letta.com/api-keys"
                    )
                    api_key_input.focus()
                    return None

                # Test cloud connection
                self.show_info("Validating Letta Cloud API key...")
                available, version, healthy = await LettaDetector.check_server(
                    url="https://api.letta.com",
                    api_key=self.cloud_api_key,
                    timeout=10,
                )

                if not available or not healthy:
                    self.show_error(
                        "Failed to authenticate with Letta Cloud. "
                        "Please verify your API key at https://app.letta.com/api-keys"
                    )
                    api_key_input.focus()
                    return None

                logger.info(
                    f"Successfully connected to Letta Cloud (version: {version})"
                )
                self.clear_messages()
                self.show_success("Successfully connected to Letta Cloud!")

            except Exception as e:
                logger.error(f"Error validating cloud API key: {e}")
                self.show_error(
                    f"Failed to connect to Letta Cloud: {e}\n"
                    "Please check your internet connection and API key."
                )
                return None

        logger.info(
            f"Letta mode selected: {self.selected_mode}, "
            f"API key provided: {bool(self.cloud_api_key)}"
        )

        return {
            "letta_mode": self.selected_mode,
            "letta_api_key": self.cloud_api_key if self.selected_mode == "cloud" else "",
        }

    async def on_next_screen(self) -> None:
        """Navigate to dependency check screen."""
        from .dependency_check import DependencyCheckScreen

        logger.info("Proceeding to dependency check")
        await self.app.push_screen(DependencyCheckScreen())

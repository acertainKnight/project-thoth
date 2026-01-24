"""
Review screen for setup wizard.

Display complete configuration summary before final confirmation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Static

from .base import BaseScreen


class ReviewScreen(BaseScreen):
    """Screen for reviewing complete configuration."""

    def __init__(self) -> None:
        """Initialize review screen."""
        super().__init__(
            title="Review Configuration",
            subtitle="Verify your settings before installation",
        )

    def compose_content(self) -> ComposeResult:
        """
        Compose review content.

        Returns:
            Content widgets
        """
        # Get wizard data
        wizard_data = {}
        if hasattr(self.app, "wizard_data"):
            wizard_data = self.app.wizard_data

        yield Static("[bold]Configuration Summary:[/bold]\n", classes="section-title")

        # Vault Configuration
        with Vertical(classes="review-section"):
            vault_path = wizard_data.get("vault_path", "[dim]Not set[/dim]")
            vault_text = f"[cyan]Obsidian Vault:[/cyan] {vault_path}"
            yield Static(vault_text)

        # LLM Configuration
        with Vertical(classes="review-section"):
            llm_settings = wizard_data.get("llm_settings", {})
            providers = []
            if "openai" in llm_settings:
                providers.append("OpenAI")
            if "anthropic" in llm_settings:
                providers.append("Anthropic")
            if "google" in llm_settings:
                providers.append("Google")

            providers_text = (
                ", ".join(providers) if providers else "[dim]None configured[/dim]"
            )
            yield Static(f"\n[cyan]LLM Providers:[/cyan] {providers_text}")

            # Show API keys (masked)
            for provider in providers:
                key_name = f"{provider.lower()}_api_key"
                if key_name in llm_settings.get(provider.lower(), {}):
                    yield Static(f"  • {provider}: [dim]sk-...****[/dim]")

        # Database Configuration
        with Vertical(classes="review-section"):
            postgres_available = wizard_data.get("postgres_available", False)
            db_status = "[green]Ready[/green]" if postgres_available else "[yellow]Not started[/yellow]"
            yield Static(f"\n[cyan]PostgreSQL:[/cyan] {db_status}")

        # Letta Configuration
        with Vertical(classes="review-section"):
            letta_available = wizard_data.get("letta_available", False)
            letta_status = "[green]Ready[/green]" if letta_available else "[yellow]Not started[/yellow]"
            yield Static(f"\n[cyan]Letta Memory:[/cyan] {letta_status}")

        # Optional Features
        with Vertical(classes="review-section"):
            rag_enabled = wizard_data.get("rag_enabled", False)
            discovery_enabled = wizard_data.get("discovery_enabled", False)
            citations_enabled = wizard_data.get("citations_enabled", False)

            features = []
            if rag_enabled:
                features.append("Vector Search")
            if discovery_enabled:
                features.append("Paper Discovery")
            if citations_enabled:
                features.append("Citation Resolution")

            features_text = (
                ", ".join(features) if features else "[dim]None enabled[/dim]"
            )
            yield Static(f"\n[cyan]Optional Features:[/cyan] {features_text}")

        # Installation Path
        with Vertical(classes="review-section"):
            if wizard_data.get("vault_path"):
                vault = Path(wizard_data["vault_path"])
                thoth_dir = vault / "_thoth"
                yield Static(f"\n[cyan]Installation Directory:[/cyan] {thoth_dir}")

        # Disk Usage Estimate
        with Vertical(classes="review-section"):
            base_size = "~50MB"
            optional_size = ""
            if rag_enabled:
                optional_size += " + ~500MB (RAG)"
            if discovery_enabled:
                optional_size += " + ~100-500MB (Discovery)"

            disk_usage = f"{base_size}{optional_size}"
            yield Static(f"\n[yellow]Estimated Disk Usage:[/yellow] {disk_usage}")

        # Edit instructions
        yield Static(
            "\n[dim]Use 'Back' button to modify settings[/dim]",
            classes="help-text",
        )

    def compose_buttons(self) -> ComposeResult:
        """
        Compose navigation buttons.

        Returns:
            Button widgets
        """
        yield Button("Back", id="back", variant="default")
        yield Button("Install", id="install", variant="success")

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate configuration and proceed to installation.

        Returns:
            Dict confirming review, or None if validation fails
        """
        # Basic validation
        if not hasattr(self.app, "wizard_data"):
            self.show_error("No configuration data found")
            return None

        wizard_data = self.app.wizard_data

        # Check required fields
        if not wizard_data.get("vault_path"):
            self.show_error("Vault path is required")
            return None

        logger.info("Configuration review validated successfully")
        return {"review_confirmed": True}

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        Handle button press events.

        Args:
            event: Button pressed event
        """
        button_id = event.button.id

        if button_id == "back":
            logger.info("Going back to optional features")
            self.app.pop_screen()
        elif button_id == "install":
            # Validate and proceed to installation
            data = await self.validate_and_proceed()
            if data is not None:
                logger.info("Review confirmed, proceeding to installation")
                # Store data in app state
                if hasattr(self.app, "wizard_data"):
                    self.app.wizard_data.update(data)
                # Proceed to installation screen
                await self.on_next_screen()

    async def on_next_screen(self) -> None:
        """Navigate to installation screen."""
        from .installation import InstallationScreen

        logger.info("Proceeding to installation")
        await self.app.push_screen(InstallationScreen())

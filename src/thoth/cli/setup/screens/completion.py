"""
Completion screen for setup wizard.

Shows installation summary and next steps.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.widgets import Button, Static

from .base import BaseScreen


class CompletionScreen(BaseScreen):
    """Screen showing setup completion and next steps."""

    def __init__(self) -> None:
        """Initialize completion screen."""
        super().__init__(
            title="Setup Complete!",
            subtitle="Thoth is ready to use",
        )

    def compose_content(self) -> ComposeResult:
        """
        Compose completion content.

        Returns:
            Content widgets
        """
        # Get installation summary from wizard data
        vault_path = ""
        providers_configured = 0

        if hasattr(self.app, "wizard_data"):
            vault_path = str(self.app.wizard_data.get("vault_path", ""))
            llm_settings = self.app.wizard_data.get("llm_settings", {})
            providers = llm_settings.get("providers", {})
            providers_configured = sum(
                1 for p in providers.values() if p.get("enabled", False)
            )

        completion_text = f"""
[bold green]✓ Thoth has been successfully installed![/bold green]

[bold]Installation Summary:[/bold]

  • [cyan]Vault:[/cyan] {vault_path}
  • [cyan]LLM Providers:[/cyan] {providers_configured} configured
  • [cyan]Workspace:[/cyan] {vault_path}/_thoth
  • [cyan]Plugin:[/cyan] Installed in Obsidian

[bold]Next Steps:[/bold]

  1. [bold]Restart Obsidian[/bold] to load the Thoth plugin
  2. [bold]Enable the plugin[/bold] in Obsidian Settings → Community Plugins
  3. [bold]Start the services[/bold] with:
     [cyan]docker compose up -d[/cyan]
  4. [bold]Open Thoth[/bold] from the Obsidian ribbon or command palette

[bold]Useful Commands:[/bold]

  • [cyan]thoth status[/cyan] - Check service status
  • [cyan]thoth discover[/cyan] - Start discovering papers
  • [cyan]thoth analyze[/cyan] - Analyze papers in your vault
  • [cyan]thoth chat[/cyan] - Chat with your research assistant

[bold]Documentation:[/bold]

  • Quick Start: https://docs.thoth.ai/quickstart
  • User Guide: https://docs.thoth.ai/guide
  • Troubleshooting: https://docs.thoth.ai/troubleshooting

[dim]Press Finish to exit the setup wizard.[/dim]
        """

        yield Static(completion_text, classes="completion-content")

    def compose_buttons(self) -> ComposeResult:
        """
        Compose buttons for completion screen.

        Returns:
            Button widgets
        """
        yield Button("Open Documentation", id="docs", variant="default")
        yield Button("Finish", id="finish", variant="success")

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate completion screen (always passes).

        Returns:
            Empty dict (setup is complete)
        """
        logger.info("Setup wizard completed successfully")
        return {}

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        Handle button press events.

        Args:
            event: Button pressed event
        """
        button_id = event.button.id

        if button_id == "docs":
            import webbrowser

            webbrowser.open("https://docs.thoth.ai/quickstart")
            logger.info("Opened documentation in browser")
        elif button_id == "finish":
            logger.info("User finished setup wizard")
            self.app.exit()

    async def on_next_screen(self) -> None:
        """No next screen - this is the final screen."""
        logger.info("Completion screen is the final screen")
        self.app.exit()

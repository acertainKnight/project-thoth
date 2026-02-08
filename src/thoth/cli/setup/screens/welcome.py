"""
Welcome screen for setup wizard.

Displays welcome message, introduction, and prerequisites check.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.widgets import Button, Static

from .base import BaseScreen


class WelcomeScreen(BaseScreen):
    """Welcome screen for Thoth setup wizard."""

    def __init__(self) -> None:
        """Initialize welcome screen."""
        super().__init__(
            title='Welcome to Thoth Setup',
            subtitle='AI-Powered Research Assistant for Obsidian',
        )

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
  • [cyan]✓[/cyan] Setting up dependencies (Docker, PostgreSQL, Letta)
  • [cyan]✓[/cyan] Installing the Obsidian plugin
  • [cyan]✓[/cyan] Testing your configuration

[bold]Prerequisites:[/bold]

  • Obsidian installed (we'll help you download it if needed)
  • API keys for at least one LLM provider (OpenAI, Anthropic, or Google)
  • ~3 GB free disk space (lightweight) or ~10 GB with local ML models
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
        yield Button('Begin Setup', id='next', variant='success')

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

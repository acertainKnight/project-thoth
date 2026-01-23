"""
Main setup wizard application.

Textual TUI application that orchestrates the setup wizard flow.
"""

from __future__ import annotations

from typing import Any, ClassVar

from loguru import logger
from textual.app import App

from .screens.welcome import WelcomeScreen


class SetupWizardApp(App):
    """Main setup wizard application."""

    CSS = """
    Screen {
        background: $surface;
    }

    .provider-section {
        margin: 1 0;
        padding: 1;
        border: solid $primary;
    }

    .provider-header {
        height: auto;
        margin-bottom: 1;
    }

    .provider-config {
        margin-left: 2;
        display: none;
    }

    .advanced-settings {
        margin: 1 0;
        padding: 1;
        border: solid $primary-darken-2;
    }

    .dependency-item {
        margin: 0 0 1 0;
    }

    .steps-list {
        margin: 1 0;
    }

    .status-section {
        margin: 1 0;
    }

    .completion-content {
        margin: 1 0;
    }

    #install-progress {
        margin: 1 0;
    }

    Label {
        margin: 1 0 0 0;
    }

    Input {
        margin: 0 0 1 0;
    }

    Select {
        margin: 0 0 1 0;
    }

    Checkbox {
        margin: 0 0 1 0;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("ctrl+c", "quit", "Quit"),
        ("f1", "help", "Help"),
    ]

    def __init__(self) -> None:
        """Initialize setup wizard app."""
        super().__init__()
        self.wizard_data: dict[str, Any] = {}

    def on_mount(self) -> None:
        """Run when app is mounted."""
        logger.info("Starting Thoth setup wizard")
        self.push_screen(WelcomeScreen())

    def action_help(self) -> None:
        """Show help message."""
        # TODO: Implement proper help overlay in future
        logger.info("Help requested")


def run_wizard() -> None:
    """
    Run the setup wizard.

    Entry point for the setup wizard CLI.
    """
    app = SetupWizardApp()
    app.run()


if __name__ == "__main__":
    run_wizard()

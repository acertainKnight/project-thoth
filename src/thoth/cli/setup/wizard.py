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

    /* Enhanced focus styling for better keyboard navigation visibility */
    Input:focus {
        border: tall $accent;
    }

    Button:focus {
        background: $accent;
    }

    RadioButton:focus {
        background: $primary-darken-1;
    }

    Checkbox:focus {
        background: $primary-darken-1;
    }

    .provider-config {
        margin-left: 2;
        height: auto;
        display: none;
    }

    .provider-config Input {
        margin: 0 0 0 0;
    }

    .provider-config Select {
        margin: 0 0 0 0;
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

    /* Collapsible widget styling for advanced section */
    Collapsible {
        margin: 1 0;
        border: solid $primary-lighten-1;
        background: $surface-darken-1;
    }

    Collapsible > CollapsibleTitle {
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
    }

    Collapsible > CollapsibleTitle:hover {
        background: $primary-darken-1;
    }

    Collapsible > Contents {
        padding: 1 2;
    }

    #advanced {
        border: solid $primary-lighten-1;
    }

    /* Context length warning labels */
    .context-warning {
        margin: 0 0 1 0;
        color: $warning;
        text-style: italic;
    }

    .hidden {
        display: none;
    }

    /* Section titles */
    .section-title {
        margin: 1 0 1 0;
    }

    .help-text {
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

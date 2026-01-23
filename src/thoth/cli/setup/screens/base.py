"""
Base screen class for setup wizard.

Provides common functionality for all wizard screens including navigation,
error handling, and consistent styling.
"""

from __future__ import annotations

from typing import Any, ClassVar

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static


class BaseScreen(Screen):
    """Base class for all setup wizard screens."""

    # CSS for consistent styling across all screens
    CSS = """
    BaseScreen {
        align: center middle;
    }

    .screen-container {
        width: 80;
        height: auto;
        border: solid $primary;
        padding: 1 2;
        background: $surface;
    }

    .screen-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .screen-content {
        width: 100%;
        height: auto;
        margin: 1 0;
    }

    .button-bar {
        width: 100%;
        height: auto;
        layout: horizontal;
        align: right middle;
        margin-top: 1;
    }

    .button-bar Button {
        margin-left: 1;
    }

    .error-message {
        width: 100%;
        background: $error;
        color: $text;
        padding: 1;
        margin: 1 0;
    }

    .info-message {
        width: 100%;
        background: $primary-darken-2;
        color: $text;
        padding: 1;
        margin: 1 0;
    }

    .success-message {
        width: 100%;
        background: $success;
        color: $text;
        padding: 1;
        margin: 1 0;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+c", "quit", "Quit"),
        ("f1", "help", "Help"),
    ]

    def __init__(
        self,
        title: str,
        subtitle: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """
        Initialize base screen.

        Args:
            title: Screen title
            subtitle: Optional subtitle
            name: Screen name
            id: Screen ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.screen_title = title
        self.screen_subtitle = subtitle
        self.error_msg: str | None = None
        self.info_msg: str | None = None

    def compose(self) -> ComposeResult:
        """
        Compose the screen layout.

        Returns:
            Screen widgets
        """
        yield Header(show_clock=True)

        with Container(classes="screen-container"):
            # Title
            title_text = f"[bold]{self.screen_title}[/bold]"
            if self.screen_subtitle:
                title_text += f"\n[dim]{self.screen_subtitle}[/dim]"
            yield Static(title_text, classes="screen-title")

            # Error/Info messages
            if self.error_msg:
                yield Static(f"⚠ {self.error_msg}", classes="error-message")
            if self.info_msg:
                yield Static(f"i {self.info_msg}", classes="info-message")

            # Content area (to be overridden by subclasses)
            with Vertical(classes="screen-content"):
                yield from self.compose_content()

            # Navigation buttons
            with Container(classes="button-bar"):
                yield from self.compose_buttons()

        yield Footer()

    def compose_content(self) -> ComposeResult:
        """
        Compose the main content area.

        To be overridden by subclasses.

        Returns:
            Content widgets
        """
        yield Static("Override compose_content() in subclass")

    def compose_buttons(self) -> ComposeResult:
        """
        Compose navigation buttons.

        Can be overridden by subclasses for custom buttons.

        Returns:
            Button widgets
        """
        yield Button("Cancel", id="cancel", variant="error")
        yield Button("Next", id="next", variant="primary")

    def show_error(self, message: str) -> None:
        """
        Display an error message.

        Args:
            message: Error message to display
        """
        self.error_msg = message
        logger.error(f"Screen error: {message}")
        self.refresh()

    def show_info(self, message: str) -> None:
        """
        Display an info message.

        Args:
            message: Info message to display
        """
        self.info_msg = message
        logger.info(f"Screen info: {message}")
        self.refresh()

    def clear_messages(self) -> None:
        """Clear error and info messages."""
        self.error_msg = None
        self.info_msg = None
        self.refresh()

    def action_cancel(self) -> None:
        """Handle cancel action."""
        logger.info(f"Canceling from screen: {self.screen_title}")
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Handle quit action."""
        logger.info("Quitting setup wizard")
        self.app.exit()

    def action_help(self) -> None:
        """Show help overlay."""
        # TODO: Implement help overlay in Phase 2
        self.show_info("Help: ESC=Cancel, Ctrl+C=Quit, F1=Help")

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate screen data and prepare for next screen.

        To be overridden by subclasses.

        Returns:
            Dictionary of validated data, or None if validation fails
        """
        return {}

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        Handle button press events.

        Args:
            event: Button pressed event
        """
        button_id = event.button.id

        if button_id == "cancel":
            self.action_cancel()
        elif button_id == "next":
            # Validate and proceed to next screen
            data = await self.validate_and_proceed()
            if data is not None:
                logger.info(f"Screen {self.screen_title} validated successfully")
                # Store data in app state
                if hasattr(self.app, 'wizard_data'):
                    self.app.wizard_data.update(data)
                # Proceed to next screen
                await self.on_next_screen()

    async def on_next_screen(self) -> None:
        """
        Navigate to the next screen.

        To be overridden by subclasses to define navigation logic.
        """
        logger.warning(f"on_next_screen not implemented for {self.screen_title}")
        self.show_error("Next screen not configured")

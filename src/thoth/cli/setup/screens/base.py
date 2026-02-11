"""Base screen class for setup wizard.

Provides common functionality for all wizard screens including navigation,
error handling, and consistent styling.
"""

from __future__ import annotations

from typing import Any, ClassVar, cast

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, Static


class BaseScreen(Screen):
    """Base class for all setup wizard screens."""

    # CSS for consistent styling across all screens
    CSS = """
    BaseScreen {
        layout: vertical;
    }

    .screen-container {
        width: 100%;
        height: 1fr;
        padding: 0 2;
        background: $surface;
    }

    .screen-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
        height: auto;
    }

    .screen-content {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
        margin: 0;
    }

    .button-bar {
        width: 100%;
        height: 3;
        layout: horizontal;
        align: right middle;
        dock: bottom;
        background: $surface;
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

    .help-text {
        color: $text-muted;
        margin: 0 0 1 0;
    }

    .hidden {
        display: none;
    }

    .no-vaults {
        color: $warning;
    }

    .feature-section {
        margin: 1 0;
        padding: 1;
        border: solid $primary-darken-2;
    }

    .feature-header {
        text-style: bold;
        color: $accent;
    }

    .feature-description {
        margin: 0 0 1 0;
    }

    .review-section {
        margin: 1 0;
    }
    """

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ('escape', 'cancel', 'Cancel & Exit'),
        ('ctrl+c', 'quit', 'Quit'),
        ('f1', 'help', 'Help'),
        ('enter', 'submit', 'Next'),
        ('ctrl+n', 'next', 'Next'),
        ('ctrl+b', 'back', 'Back'),
        ('right', 'arrow_next', 'Next'),
        ('left', 'arrow_back', 'Back'),
    ]

    def __init__(
        self,
        title: str,
        subtitle: str | None = None,
        show_back: bool = True,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize base screen.

        Args:
            title: Screen title
            subtitle: Optional subtitle
            show_back: Whether to show the Back button
            name: Screen name
            id: Screen ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.screen_title = title
        self.screen_subtitle = subtitle
        self.show_back = show_back
        self.error_msg: str | None = None
        self.info_msg: str | None = None
        self._message_widget: Static | None = None  # Cache for message widget

    def compose(self) -> ComposeResult:
        """Compose the screen layout.

        Returns:
            Screen widgets
        """
        with Container(classes='screen-container'):
            # Title
            title_text = f'[bold]{self.screen_title}[/bold]'
            if self.screen_subtitle:
                title_text += f'\n[dim]{self.screen_subtitle}[/dim]'
            yield Static(title_text, classes='screen-title')

            # Message area (always present but hidden when empty)
            yield Static('', id='message-area', classes='hidden')

            # Content area (to be overridden by subclasses)
            with Vertical(classes='screen-content'):
                yield from self.compose_content()

            # Navigation buttons
            with Container(classes='button-bar'):
                yield from self.compose_buttons()

    def compose_content(self) -> ComposeResult:
        """Compose the main content area.

        To be overridden by subclasses.

        Returns:
            Content widgets
        """
        yield Static('Override compose_content() in subclass')

    def compose_buttons(self) -> ComposeResult:
        """Compose navigation buttons.

        Can be overridden by subclasses for custom buttons.

        Returns:
            Button widgets
        """
        yield Button('Cancel & Exit', id='cancel', variant='error')
        if self.show_back:
            yield Button('← Back', id='back', variant='default')
        yield Button('Next →', id='next', variant='primary')

    def show_error(self, message: str) -> None:
        """Display an error message.

        Args:
            message: Error message to display
        """
        self.error_msg = message
        logger.error(f'Screen error: {message}')

        # Update message widget directly
        try:
            msg_widget = self.query_one('#message-area', Static)
            msg_widget.update(f'[bold red]{message}[/bold red]')
            msg_widget.remove_class('hidden')
            msg_widget.add_class('error-message')
            msg_widget.remove_class('info-message')
            msg_widget.remove_class('success-message')
        except Exception as e:
            # Widget not mounted yet, will show on next compose
            logger.debug(f'Widget not mounted yet, will show on next compose: {e}')
            self.refresh()

    def show_info(self, message: str) -> None:
        """Display an info message.

        Args:
            message: Info message to display
        """
        self.info_msg = message
        logger.info(f'Screen info: {message}')

        # Update message widget directly
        try:
            msg_widget = self.query_one('#message-area', Static)
            msg_widget.update(f'[cyan]i[/cyan] {message}')
            msg_widget.remove_class('hidden')
            msg_widget.add_class('info-message')
            msg_widget.remove_class('error-message')
            msg_widget.remove_class('success-message')
        except Exception as e:
            logger.debug(f'Widget not mounted yet, will show on next compose: {e}')
            self.refresh()

    def show_warning(self, message: str) -> None:
        """Display a warning message (uses info styling with warning prefix).

        Args:
            message: Warning message to display
        """
        self.info_msg = f'[yellow]Warning:[/yellow] {message}'
        logger.warning(f'Screen warning: {message}')

        # Update message widget directly
        try:
            msg_widget = self.query_one('#message-area', Static)
            msg_widget.update(f'[yellow]{message}[/yellow]')
            msg_widget.remove_class('hidden')
            msg_widget.add_class('info-message')
            msg_widget.remove_class('error-message')
            msg_widget.remove_class('success-message')
        except Exception as e:
            logger.debug(f'Widget not mounted yet, will show on next compose: {e}')
            self.refresh()

    def show_success(self, message: str) -> None:
        """Display a success message (uses info styling with success prefix).

        Args:
            message: Success message to display
        """
        self.info_msg = f'[green]✓[/green] {message}'
        logger.info(f'Screen success: {message}')

        # Update message widget directly
        try:
            msg_widget = self.query_one('#message-area', Static)
            msg_widget.update(f'[green]✓ {message}[/green]')
            msg_widget.remove_class('hidden')
            msg_widget.add_class('success-message')
            msg_widget.remove_class('error-message')
            msg_widget.remove_class('info-message')
        except Exception as e:
            logger.debug(f'Widget not mounted yet, will show on next compose: {e}')
            self.refresh()

    def clear_messages(self) -> None:
        """Clear error and info messages."""
        self.error_msg = None
        self.info_msg = None

        # Hide message widget
        try:
            msg_widget = self.query_one('#message-area', Static)
            msg_widget.update('')
            msg_widget.add_class('hidden')
        except Exception as e:
            logger.debug(f'Widget not mounted yet, will show on next compose: {e}')
            self.refresh()

    def action_cancel(self) -> None:
        """Handle cancel action - exits the wizard completely."""
        logger.info(f'Canceling wizard from screen: {self.screen_title}')
        self.app.exit(message='Setup wizard cancelled by user')

    def action_back(self) -> None:
        """Handle back action - return to previous screen."""
        logger.info(f'Going back from screen: {self.screen_title}')
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Handle quit action."""
        logger.info('Quitting setup wizard')
        self.app.exit()

    def _focus_uses_arrows(self) -> bool:
        """Check if the currently focused widget uses arrow keys internally.

        Returns:
            True if arrows should be passed through to the widget.
        """
        from textual.widgets import Input, RadioSet, Select

        focused = self.app.focused
        if focused is None:
            return False
        # Input uses left/right for cursor movement
        # RadioSet uses up/down/left/right for selection
        # Select uses arrows for dropdown navigation
        # Also check parent chain for RadioSet (RadioButtons are children)
        if isinstance(focused, (Input, RadioSet, Select)):
            return True
        # RadioButton's parent is a RadioSet
        node: Widget | None = focused
        while node is not None:
            if isinstance(node, RadioSet):
                return True
            node = cast(Widget | None, getattr(node, 'parent', None))
        return False

    def action_submit(self) -> None:
        """Handle Enter key - same as Next, but only if not in input field."""
        from textual.widgets import Input

        if isinstance(self.app.focused, Input):
            return

        try:
            next_button = self.query_one('#next', Button)
            next_button.press()
        except Exception as e:
            logger.debug(f'Next button might not exist on some screens: {e}')

    def action_next(self) -> None:
        """Handle Ctrl+N - trigger next action."""
        self.action_submit()

    def action_arrow_next(self) -> None:
        """Handle right arrow - go to next if not in text/selection widget."""
        if not self._focus_uses_arrows():
            self.action_submit()

    def action_arrow_back(self) -> None:
        """Handle left arrow - go back if focus isn't in a text/selection widget."""
        if not self._focus_uses_arrows():
            self.action_back()

    def action_help(self) -> None:
        """Show help overlay."""
        # TODO: Implement help overlay
        self.show_info(
            'Keyboard shortcuts:\n'
            '  ← / →: Previous / Next screen\n'
            '  Tab/Shift+Tab: Navigate between fields\n'
            '  ↑ / ↓: Select options in lists\n'
            '  Space: Toggle checkboxes/radio buttons\n'
            '  Enter: Next screen\n'
            '  ESC: Cancel & exit wizard\n'
            '  F1: Show this help'
        )

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """Validate screen data and prepare for next screen.

        To be overridden by subclasses.

        Returns:
            Dictionary of validated data, or None if validation fails
        """
        return {}

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        Args:
            event: Button pressed event
        """
        button_id = event.button.id

        if button_id == 'cancel':
            self.action_cancel()
        elif button_id == 'back':
            self.action_back()
        elif button_id == 'next':
            # Validate and proceed to next screen
            data = await self.validate_and_proceed()
            if data is not None:
                logger.info(f'Screen {self.screen_title} validated successfully')
                # Store data in app state
                if hasattr(self.app, 'wizard_data'):
                    self.app.wizard_data.update(data)
                # Proceed to next screen
                await self.on_next_screen()

    async def on_next_screen(self) -> None:
        """Navigate to the next screen.

        To be overridden by subclasses to define navigation logic.
        """
        logger.warning(f'on_next_screen not implemented for {self.screen_title}')
        self.show_error('Next screen not configured')

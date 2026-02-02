
"""
Progress tracking for setup wizard.

Provides progress bars, spinners, and status indicators for long-running operations.
"""
from __future__ import annotations

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from textual.widgets import ProgressBar


class ProgressTracker:
    """Tracks wizard progress and displays status."""

    def __init__(self, total_steps: int = 10):
        """
        Initialize progress tracker.

        Args:
            total_steps: Total number of wizard steps
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.console = Console()
        self.progress: Progress | None = None
        self.task_id: TaskID | None = None

    def start(self) -> None:
        """Start progress tracking."""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn('[progress.description]{task.description}'),
            BarColumn(),
            TextColumn('[progress.percentage]{task.percentage:>3.0f}%'),
            TimeElapsedColumn(),
            console=self.console,
        )
        self.progress.start()
        self.task_id = self.progress.add_task(
            '[cyan]Setup Wizard', total=self.total_steps
        )

    def stop(self) -> None:
        """Stop progress tracking."""
        if self.progress:
            self.progress.stop()

    def advance(self, description: str) -> None:
        """
        Advance to next step.

        Args:
            description: Description of current step
        """
        self.current_step += 1
        if self.progress and self.task_id is not None:
            self.progress.update(
                self.task_id, advance=1, description=f'[cyan]{description}'
            )

    def update_description(self, description: str) -> None:
        """
        Update current step description without advancing.

        Args:
            description: New description
        """
        if self.progress and self.task_id is not None:
            self.progress.update(self.task_id, description=f'[cyan]{description}')

    def get_percentage(self) -> float:
        """
        Get current completion percentage.

        Returns:
            Completion percentage (0-100)
        """
        if self.total_steps == 0:
            return 0.0
        return (self.current_step / self.total_steps) * 100


class WizardProgressBar(ProgressBar):
    """Textual progress bar widget for wizard."""

    def __init__(self, total_steps: int = 10, **kwargs):
        """
        Initialize wizard progress bar.

        Args:
            total_steps: Total number of wizard steps
            **kwargs: Additional keyword arguments for ProgressBar
        """
        super().__init__(total=total_steps, **kwargs)
        self.current_step = 0

    def advance_step(self) -> None:
        """Advance to next step."""
        self.current_step += 1
        self.advance(1)

    def set_step(self, step: int) -> None:
        """
        Set current step.

        Args:
            step: Step number (0-based)
        """
        self.current_step = step
        self.update(progress=step)


class StatusIndicator:
    """Status indicator for system checks and validations."""

    @staticmethod
    def success(message: str) -> str:
        """
        Format success message.

        Args:
            message: Success message

        Returns:
            Formatted string with success indicator
        """
        return f'[green]✓[/green] {message}'

    @staticmethod
    def failure(message: str) -> str:
        """
        Format failure message.

        Args:
            message: Failure message

        Returns:
            Formatted string with failure indicator
        """
        return f'[red]✗[/red] {message}'

    @staticmethod
    def warning(message: str) -> str:
        """
        Format warning message.

        Args:
            message: Warning message

        Returns:
            Formatted string with warning indicator
        """
        return f'[yellow]⚠[/yellow] {message}'

    @staticmethod
    def info(message: str) -> str:
        """
        Format info message.

        Args:
            message: Info message

        Returns:
            Formatted string with info indicator
        """
        return f'[blue]i[/blue] {message}'

    @staticmethod
    def pending(message: str) -> str:
        """
        Format pending message.

        Args:
            message: Pending message

        Returns:
            Formatted string with pending indicator
        """
        return f'[dim]○[/dim] {message}'

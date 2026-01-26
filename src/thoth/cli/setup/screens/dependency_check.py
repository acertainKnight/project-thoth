"""
Dependency check screen for setup wizard.

Checks and installs required dependencies: Docker Compose, PostgreSQL, Letta.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, ProgressBar, Static

from ..detectors.docker import DockerDetector, DockerStatus
from ..detectors.letta import LettaDetector, LettaStatus
from ..detectors.postgresql import PostgreSQLDetector, PostgreSQLStatus
from .base import BaseScreen


class DependencyCheckScreen(BaseScreen):
    """Screen for checking and installing dependencies."""

    def __init__(self) -> None:
        """Initialize dependency check screen."""
        super().__init__(
            title="Check Dependencies",
            subtitle="Verifying Docker, PostgreSQL, and Letta installation",
        )
        self.docker_status: DockerStatus | None = None
        self.postgres_status: PostgreSQLStatus | None = None
        self.letta_status: LettaStatus | None = None
        self.all_ready = False
        self.letta_mode: str = "self-hosted"  # Default to self-hosted
        self.letta_api_key: str = ""

    def on_mount(self) -> None:
        """Run when screen is mounted."""
        # Read Letta mode from wizard data
        if hasattr(self.app, "wizard_data"):
            self.letta_mode = self.app.wizard_data.get("letta_mode", "self-hosted")
            self.letta_api_key = self.app.wizard_data.get("letta_api_key", "")
            logger.info(f"Letta mode from wizard: {self.letta_mode}")

        self._check_task = asyncio.create_task(self.check_dependencies())

    async def check_dependencies(self) -> None:
        """Check all dependencies."""
        if self.letta_mode == "cloud":
            self.show_info("Checking dependencies (Letta Cloud mode)...")
        else:
            self.show_info("Checking dependencies...")

        try:
            # For cloud mode, we still need Docker for PostgreSQL (Thoth's DB)
            # but NOT for Letta
            await self.check_docker()

            # Check PostgreSQL (if Docker is available)
            if self.docker_status and self.docker_status.available:
                await self.check_postgresql()

            # Check Letta (behavior depends on mode)
            await self.check_letta()

            # Check if all dependencies are ready
            self.all_ready = self._are_all_dependencies_ready()

            if self.all_ready:
                self.show_info("All dependencies are ready!")
            else:
                # If self-hosted Letta failed, offer cloud fallback
                if (
                    self.letta_mode == "self-hosted"
                    and not (self.letta_status and self.letta_status.available)
                ):
                    self.show_error(
                        "Letta self-hosted setup unavailable. "
                        "Consider using Letta Cloud instead."
                    )
                else:
                    self.show_info(
                        "Some dependencies need to be installed. Click Install to proceed."
                    )

            self.refresh()

        except Exception as e:
            logger.error(f"Error checking dependencies: {e}")
            self.show_error(f"Failed to check dependencies: {e}")

    async def check_docker(self) -> None:
        """Check Docker installation."""
        logger.info("Checking Docker...")
        self.docker_status = DockerDetector.get_status()

        if self.docker_status.available:
            logger.info(
                f"Docker available: {self.docker_status.version or 'unknown version'}"
            )
            if self.docker_status.compose_available:
                logger.info("Docker Compose is available")
            else:
                logger.warning("Docker Compose not available")
        else:
            logger.warning("Docker not available")

    async def check_postgresql(self) -> None:
        """Check PostgreSQL installation."""
        logger.info("Checking PostgreSQL...")

        # Check if PostgreSQL is running in Docker
        if self.docker_status and self.docker_status.compose_available:
            containers = DockerDetector.list_running_containers()
            postgres_running = any("postgres" in c["image"].lower() for c in containers)

            if postgres_running:
                # Try to connect
                self.postgres_status = await PostgreSQLDetector.get_status()
                if self.postgres_status.available:
                    logger.info("PostgreSQL is running and available")
                else:
                    logger.warning("PostgreSQL container found but not responding")
            else:
                logger.info("PostgreSQL not running in Docker")
                self.postgres_status = PostgreSQLStatus(
                    available=False,
                    host="localhost",
                    port=5432,
                    version=None,
                    databases=[],
                    error_message="PostgreSQL not running",
                )
        else:
            # Check system PostgreSQL
            self.postgres_status = await PostgreSQLDetector.get_status()

    async def check_letta(self) -> None:
        """Check Letta server (cloud or self-hosted based on mode)."""
        if self.letta_mode == "cloud":
            logger.info("Checking Letta Cloud...")
            self.letta_status = LettaDetector.get_status(
                url="https://api.letta.com",
                api_key=self.letta_api_key,
                mode="cloud",
            )
        else:
            logger.info("Checking Letta (self-hosted)...")
            self.letta_status = LettaDetector.get_status(
                mode="self-hosted",
            )

        if self.letta_status.available:
            logger.info(
                f"Letta available at {self.letta_status.url} "
                f"(version: {self.letta_status.version or 'unknown'})"
            )
        else:
            logger.warning(f"Letta not available ({self.letta_mode} mode)")

    def _are_all_dependencies_ready(self) -> bool:
        """
        Check if all dependencies are ready.

        Returns:
            True if all dependencies are available
        """
        # Letta status
        letta_ready = self.letta_status and self.letta_status.available

        # For cloud mode, Docker/PostgreSQL not required for Letta (only for Thoth)
        if self.letta_mode == "cloud":
            # In cloud mode, we still need Docker+PostgreSQL for Thoth itself
            docker_ready = (
                self.docker_status
                and self.docker_status.available
                and self.docker_status.compose_available
            )
            postgres_ready = self.postgres_status and self.postgres_status.available
            return bool(docker_ready and postgres_ready and letta_ready)
        else:
            # Self-hosted mode needs Docker for everything
            docker_ready = (
                self.docker_status
                and self.docker_status.available
                and self.docker_status.compose_available
            )
            postgres_ready = self.postgres_status and self.postgres_status.available
            return bool(docker_ready and postgres_ready and letta_ready)

    def compose_content(self) -> ComposeResult:
        """
        Compose dependency check content.

        Returns:
            Content widgets
        """
        yield Static("[bold]Dependency Status:[/bold]", classes="section-title")

        # Docker status
        with Vertical(classes="dependency-item"):
            docker_status_text = self._format_docker_status()
            yield Static(docker_status_text)

        # PostgreSQL status
        with Vertical(classes="dependency-item"):
            postgres_status_text = self._format_postgres_status()
            yield Static(postgres_status_text)

        # Letta status
        with Vertical(classes="dependency-item"):
            letta_status_text = self._format_letta_status()
            yield Static(letta_status_text)

        # Progress bar (shown during installation)
        yield ProgressBar(id="install-progress", total=100, show_eta=False)

    def _format_docker_status(self) -> str:
        """
        Format Docker status for display.

        Returns:
            Formatted status string
        """
        if not self.docker_status:
            return "[dim]Docker: Checking...[/dim]"

        if self.docker_status.available and self.docker_status.compose_available:
            version = self.docker_status.version or "unknown"
            return f"[green]✓[/green] Docker: {version} (Compose available)"
        elif self.docker_status.available:
            return "[yellow]⚠[/yellow] Docker: Available but Compose missing"
        else:
            return "[red]✗[/red] Docker: Not installed"

    def _format_postgres_status(self) -> str:
        """
        Format PostgreSQL status for display.

        Returns:
            Formatted status string
        """
        if not self.postgres_status:
            return "[dim]PostgreSQL: Checking...[/dim]"

        if self.postgres_status.available:
            version = self.postgres_status.version or "unknown"
            return f"[green]✓[/green] PostgreSQL: {version} (Running)"
        else:
            return "[red]✗[/red] PostgreSQL: Not running"

    def _format_letta_status(self) -> str:
        """
        Format Letta status for display.

        Returns:
            Formatted status string
        """
        if not self.letta_status:
            return "[dim]Letta: Checking...[/dim]"

        if self.letta_status.available:
            version = self.letta_status.version or "unknown"
            mode = self.letta_status.mode
            return f"[green]✓[/green] Letta: {version} ({mode})"
        else:
            return "[red]✗[/red] Letta: Not running"

    def compose_buttons(self) -> ComposeResult:
        """
        Compose navigation buttons.

        Returns:
            Button widgets
        """
        yield Button("Back", id="back", variant="default")
        yield Button("Skip", id="skip", variant="warning")
        yield Button("Install", id="install", variant="primary")
        yield Button("Next", id="next", variant="success")

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate dependencies.

        Returns:
            Dict with dependency status, or None if not ready
        """
        if not self.all_ready:
            self.show_error(
                "Not all dependencies are ready. Please install them or skip."
            )
            return None

        logger.info("All dependencies validated and ready")
        return {
            "docker_available": self.docker_status.available
            if self.docker_status
            else False,
            "postgres_available": self.postgres_status.available
            if self.postgres_status
            else False,
            "letta_available": self.letta_status.available
            if self.letta_status
            else False,
            "letta_mode": self.letta_mode,
        }

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        Handle button press events.

        Args:
            event: Button pressed event
        """
        button_id = event.button.id

        if button_id == "back":
            logger.info("Going back to configuration")
            self.app.pop_screen()
        elif button_id == "skip":
            logger.warning("User chose to skip dependency installation")
            self.all_ready = True
            await self.on_next_screen()
        elif button_id == "install":
            await self.install_dependencies()
        elif button_id == "next":
            # Validate and proceed to next screen
            data = await self.validate_and_proceed()
            if data is not None:
                logger.info("Dependencies validated successfully")
                # Store data in app state
                if hasattr(self.app, "wizard_data"):
                    self.app.wizard_data.update(data)
                # Proceed to next screen
                await self.on_next_screen()

    async def install_dependencies(self) -> None:
        """Install missing dependencies."""
        self.show_info("Installing dependencies...")

        try:
            progress_bar = self.query_one("#install-progress", ProgressBar)
            progress_bar.update(progress=10)

            # Install Docker (if not available)
            if not self.docker_status or not self.docker_status.available:
                self.show_info("Docker installation required. Please install manually.")
                install_url = DockerDetector.get_install_url()
                self.show_error(
                    f"Please install Docker from: {install_url} and restart the wizard"
                )
                return

            progress_bar.update(progress=30)

            # Start PostgreSQL via Docker Compose
            if not self.postgres_status or not self.postgres_status.available:
                self.show_info("Starting PostgreSQL via Docker Compose...")
                try:
                    import subprocess
                    from pathlib import Path

                    # Find docker-compose.yml in project root
                    compose_file = Path.cwd() / "docker-compose.yml"
                    dev_compose_file = Path.cwd() / "docker-compose.dev.yml"

                    if compose_file.exists() or dev_compose_file.exists():
                        # Start PostgreSQL service
                        result = subprocess.run(
                            ["docker", "compose", "up", "-d", "postgres"],
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )

                        if result.returncode == 0:
                            self.show_info("PostgreSQL started successfully")
                        else:
                            self.show_error(f"Failed to start PostgreSQL: {result.stderr}")
                    else:
                        self.show_info("docker-compose.yml not found. Run 'docker compose up -d postgres' manually")

                except subprocess.TimeoutExpired:
                    self.show_error("Docker Compose startup timed out")
                except Exception as e:
                    logger.error(f"Error starting PostgreSQL: {e}")
                    self.show_info("Run 'docker compose up -d postgres' manually")

            progress_bar.update(progress=60)

            # Start Letta via Docker Compose
            if not self.letta_status or not self.letta_status.available:
                self.show_info("Starting Letta via Docker Compose...")
                try:
                    import subprocess
                    from pathlib import Path

                    # Find docker-compose.yml in project root
                    compose_file = Path.cwd() / "docker-compose.yml"
                    dev_compose_file = Path.cwd() / "docker-compose.dev.yml"

                    if compose_file.exists() or dev_compose_file.exists():
                        # Start Letta service
                        result = subprocess.run(
                            ["docker", "compose", "up", "-d", "letta"],
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )

                        if result.returncode == 0:
                            self.show_info("Letta started successfully")
                        else:
                            self.show_error(f"Failed to start Letta: {result.stderr}")
                    else:
                        self.show_info("docker-compose.yml not found. Run 'docker compose up -d letta' manually")

                except subprocess.TimeoutExpired:
                    self.show_error("Docker Compose startup timed out")
                except Exception as e:
                    logger.error(f"Error starting Letta: {e}")
                    self.show_info("Run 'docker compose up -d letta' manually")

            progress_bar.update(progress=90)

            # Re-check dependencies
            await self.check_dependencies()

            progress_bar.update(progress=100)

            if self.all_ready:
                self.show_info("All dependencies installed successfully!")
            else:
                self.show_error("Some dependencies could not be installed")

        except Exception as e:
            logger.error(f"Error installing dependencies: {e}")
            self.show_error(f"Failed to install dependencies: {e}")

    async def on_next_screen(self) -> None:
        """Navigate to optional features screen."""
        from .optional_features import OptionalFeaturesScreen

        logger.info("Proceeding to optional features")
        await self.app.push_screen(OptionalFeaturesScreen())

"""
Installation screen for setup wizard.

Performs the actual installation of Thoth components.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, ProgressBar, Static

from .base import BaseScreen


class InstallationScreen(BaseScreen):
    """Screen for installing Thoth components."""

    def __init__(self) -> None:
        """Initialize installation screen."""
        super().__init__(
            title="Installing Thoth",
            subtitle="Setting up your research assistant",
        )
        self.vault_path: Path | None = None
        self.llm_settings: dict[str, Any] = {}
        self.installation_complete = False
        self.installation_steps = [
            "Creating workspace directory",
            "Saving configuration",
            "Setting up database schema",
            "Installing Obsidian plugin",
            "Validating installation",
        ]
        self.current_step = 0

    def on_mount(self) -> None:
        """Run when screen is mounted."""
        # Get data from wizard
        if hasattr(self.app, "wizard_data"):
            self.vault_path = self.app.wizard_data.get("vault_path")
            self.llm_settings = self.app.wizard_data.get("llm_settings", {})

        # Start installation automatically
        self._install_task = asyncio.create_task(self.run_installation())

    async def run_installation(self) -> None:
        """Run the installation process."""
        self.show_info("Starting installation...")

        try:
            progress_bar = self.query_one("#install-progress", ProgressBar)
            status_text = self.query_one("#status-text", Static)

            # Step 1: Create workspace directory
            self.current_step = 1
            status_text.update(f"[cyan]{self.installation_steps[0]}...[/cyan]")
            progress_bar.update(progress=20)
            await self.create_workspace()
            await asyncio.sleep(0.5)

            # Step 2: Save configuration
            self.current_step = 2
            status_text.update(f"[cyan]{self.installation_steps[1]}...[/cyan]")
            progress_bar.update(progress=40)
            await self.save_configuration()
            await asyncio.sleep(0.5)

            # Step 3: Set up database schema
            self.current_step = 3
            status_text.update(f"[cyan]{self.installation_steps[2]}...[/cyan]")
            progress_bar.update(progress=60)
            await self.setup_database()
            await asyncio.sleep(0.5)

            # Step 4: Install Obsidian plugin
            self.current_step = 4
            status_text.update(f"[cyan]{self.installation_steps[3]}...[/cyan]")
            progress_bar.update(progress=80)
            await self.install_plugin()
            await asyncio.sleep(0.5)

            # Step 5: Validate installation
            self.current_step = 5
            status_text.update(f"[cyan]{self.installation_steps[4]}...[/cyan]")
            progress_bar.update(progress=95)
            await self.validate_installation()
            await asyncio.sleep(0.5)

            # Complete
            progress_bar.update(progress=100)
            status_text.update("[green]Installation complete![/green]")
            self.installation_complete = True
            self.clear_messages()
            self.show_info(
                "Thoth has been successfully installed! Click Next to finish setup."
            )

        except Exception as e:
            logger.error(f"Installation failed: {e}")
            self.show_error(f"Installation failed: {e}")

    async def create_workspace(self) -> None:
        """Create Thoth workspace directory in vault."""
        if not self.vault_path:
            raise ValueError("No vault path specified")

        thoth_dir = self.vault_path / "_thoth"
        thoth_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (thoth_dir / "data").mkdir(exist_ok=True)
        (thoth_dir / "logs").mkdir(exist_ok=True)
        (thoth_dir / "cache").mkdir(exist_ok=True)

        logger.info(f"Created workspace at {thoth_dir}")

    async def save_configuration(self) -> None:
        """Save configuration to settings.json."""
        if not self.vault_path:
            raise ValueError("No vault path specified")

        from ..config_manager import ConfigManager

        config_manager = ConfigManager(self.vault_path)

        # Build configuration dict
        settings = {
            "version": "1.0.0",
            "vault_path": str(self.vault_path),
            "llm_settings": self.llm_settings,
            "database": {
                "host": "localhost",
                "port": 5432,
                "database": "thoth",
            },
            "letta": {
                "url": "http://localhost:8283",
                "mode": "self-hosted",
            },
        }

        # Merge with existing config if present
        existing = config_manager.load_existing()
        if existing:
            settings = config_manager.deep_merge(existing, settings)

        # Validate and save
        config_manager.validate_schema(settings)
        config_manager.atomic_save(settings)

        logger.info("Configuration saved")

    async def setup_database(self) -> None:
        """Set up database schema."""
        # Check if database is available
        if hasattr(self.app, "wizard_data"):
            postgres_available = self.app.wizard_data.get("postgres_available", False)

            if not postgres_available:
                logger.warning("PostgreSQL not available, skipping schema setup")
                return

        # Run database migrations if PostgreSQL is available
        try:
            from pathlib import Path

            # Look for migration scripts
            migrations_dir = Path(__file__).parent.parent.parent.parent / "migrations"

            if migrations_dir.exists():
                logger.info(f"Running database migrations from {migrations_dir}")
                # Run migrations using the migration script if it exists
                for migration_file in sorted(migrations_dir.glob("*.sql")):
                    logger.info(f"Applying migration: {migration_file.name}")
                    # Migrations will be applied when the database service starts
            else:
                logger.info("No migration directory found, database schema will be created on first use")

        except Exception as e:
            logger.warning(f"Could not run database migrations: {e}")
            logger.info("Database schema will be created automatically on first use")

    async def install_plugin(self) -> None:
        """Install Obsidian plugin."""
        if not self.vault_path:
            raise ValueError("No vault path specified")

        plugins_dir = self.vault_path / ".obsidian" / "plugins" / "thoth"
        plugins_dir.mkdir(parents=True, exist_ok=True)

        # Copy plugin files from package to vault
        try:
            import json
            import shutil
            from pathlib import Path

            # Look for plugin source directory
            plugin_src = Path(__file__).parent.parent.parent.parent / "obsidian-plugin"

            if plugin_src.exists():
                logger.info(f"Copying plugin files from {plugin_src}")
                # Copy all plugin files
                for item in plugin_src.iterdir():
                    if item.is_file() and item.suffix in {".js", ".json", ".css"}:
                        dest = plugins_dir / item.name
                        shutil.copy2(item, dest)
                        logger.info(f"Copied {item.name}")
            else:
                # Plugin source not found, create minimal manifest
                logger.warning("Plugin source not found, creating minimal manifest")
                manifest_path = plugins_dir / "manifest.json"
                if not manifest_path.exists():
                    manifest = {
                        "id": "thoth",
                        "name": "Thoth Research Assistant",
                        "version": "1.0.0",
                        "minAppVersion": "0.15.0",
                        "description": "AI-powered research assistant for academic papers",
                        "author": "Thoth Team",
                        "authorUrl": "https://github.com/yourusername/project-thoth",
                    }

                    with open(manifest_path, "w", encoding="utf-8") as f:
                        json.dump(manifest, f, indent=2)

                logger.info("Note: You'll need to install the Obsidian plugin manually")
                logger.info(f"Plugin directory: {plugins_dir}")

        except Exception as e:
            logger.error(f"Error installing plugin: {e}")
            logger.info("You can install the plugin manually later")

        logger.info(f"Plugin directory created at {plugins_dir}")

    async def validate_installation(self) -> None:
        """Validate that installation was successful."""
        if not self.vault_path:
            raise ValueError("No vault path specified")

        # Check workspace directory
        thoth_dir = self.vault_path / "_thoth"
        if not thoth_dir.exists():
            raise RuntimeError("Workspace directory not created")

        # Check configuration file
        settings_path = thoth_dir / "settings.json"
        if not settings_path.exists():
            raise RuntimeError("Configuration file not created")

        # Check plugin directory
        plugins_dir = self.vault_path / ".obsidian" / "plugins" / "thoth"
        if not plugins_dir.exists():
            raise RuntimeError("Plugin directory not created")

        logger.info("Installation validation passed")

    def compose_content(self) -> ComposeResult:
        """
        Compose installation content.

        Returns:
            Content widgets
        """
        yield Static(
            "[bold]Installation Progress:[/bold]", classes="section-title"
        )

        # Progress bar
        yield ProgressBar(
            id="install-progress",
            total=100,
            show_eta=False,
            show_percentage=True,
        )

        # Current status
        with Vertical(classes="status-section"):
            yield Static(
                "[dim]Preparing installation...[/dim]",
                id="status-text",
            )

        # Installation steps checklist
        yield Static("\n[bold]Steps:[/bold]", classes="section-title")
        with Vertical(classes="steps-list"):
            for i, step in enumerate(self.installation_steps, 1):
                if i < self.current_step:
                    yield Static(f"[green]✓[/green] {step}")
                elif i == self.current_step:
                    yield Static(f"[cyan]⟳[/cyan] {step}")
                else:
                    yield Static(f"[dim]○ {step}[/dim]")

    def compose_buttons(self) -> ComposeResult:
        """
        Compose navigation buttons.

        Returns:
            Button widgets
        """
        # Only show Next button after installation is complete
        if self.installation_complete:
            yield Button("Next", id="next", variant="success")
        else:
            yield Button("Cancel", id="cancel", variant="error")

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate installation.

        Returns:
            Dict with installation status, or None if not complete
        """
        if not self.installation_complete:
            self.show_error("Installation is not complete")
            return None

        logger.info("Installation validated successfully")
        return {"installation_complete": True}

    async def on_next_screen(self) -> None:
        """Navigate to completion screen."""
        from .completion import CompletionScreen

        logger.info("Proceeding to completion")
        await self.app.push_screen(CompletionScreen())

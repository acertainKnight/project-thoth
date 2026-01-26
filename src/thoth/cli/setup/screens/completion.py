"""
Completion screen for setup wizard.

Shows installation summary and next steps.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Horizontal
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
        self.services_started = False
        self.auto_start_asked = False

    def compose_content(self) -> ComposeResult:
        """
        Compose completion content.

        Returns:
            Content widgets
        """
        # Get installation summary from wizard data
        vault_path = ""
        providers_configured = 0
        letta_mode = "self-hosted"

        if hasattr(self.app, "wizard_data"):
            vault_path = str(self.app.wizard_data.get("vault_path", ""))
            letta_mode = self.app.wizard_data.get("letta_mode", "self-hosted")
            llm_settings = self.app.wizard_data.get("llm_settings", {})
            providers = llm_settings.get("providers", {})
            providers_configured = sum(
                1 for p in providers.values() if p.get("enabled", False)
            )

        if not self.auto_start_asked:
            # Initial completion message with auto-start prompt
            completion_text = f"""
[bold green]✓ Thoth has been successfully installed![/bold green]

[bold]Installation Summary:[/bold]

  • [cyan]Vault:[/cyan] {vault_path}
  • [cyan]Letta Mode:[/cyan] {letta_mode.title()}
  • [cyan]LLM Providers:[/cyan] {providers_configured} configured
  • [cyan]Workspace:[/cyan] {vault_path}/_thoth

[bold]Start Thoth services now?[/bold]

Services will use approximately [yellow]1-1.5GB RAM[/yellow] depending on Letta mode:
  • Cloud mode: ~1GB (Thoth services only)
  • Self-hosted: ~1.5GB (Thoth + Letta containers)

You can stop services anytime with: [cyan]thoth stop[/cyan]

[dim]Choose an option below:[/dim]
            """
        else:
            # After start choice - show next steps
            completion_text = f"""
[bold green]✓ Setup complete!{'  Services running!' if self.services_started else ''}[/bold green]

[bold]Next Steps:[/bold]

  1. [bold]Restart Obsidian[/bold] to load the Thoth plugin
  2. [bold]Enable the plugin[/bold] in Settings → Community Plugins
  3. [bold]Upload vault files[/bold] with: [cyan]thoth letta sync[/cyan]
  4. [bold]Open Thoth[/bold] from the Obsidian ribbon

[bold]Useful Commands:[/bold]

  • [cyan]thoth start[/cyan]   - Start services
  • [cyan]thoth stop[/cyan]    - Stop services (free RAM)
  • [cyan]thoth status[/cyan]  - Check what's running
  • [cyan]thoth logs[/cyan]    - View service logs
  • [cyan]thoth letta sync[/cyan] - Upload notes to Letta

[bold]Documentation:[/bold]

  • README: https://github.com/acertainKnight/project-thoth
  • Issues: https://github.com/acertainKnight/project-thoth/issues

[dim]Press Finish to exit the setup wizard.[/dim]
            """

        yield Static(completion_text, classes="completion-content")

    def compose_buttons(self) -> ComposeResult:
        """
        Compose buttons for completion screen.

        Returns:
            Button widgets
        """
        if not self.auto_start_asked:
            # First show: Start now or Finish
            yield Button("Start Thoth Now", id="start-now", variant="success")
            yield Button("I'll Start Manually", id="manual-start", variant="default")
        else:
            # After auto-start choice: show docs and finish
            yield Button("Open Documentation", id="docs", variant="default")
            yield Button("Finish", id="finish", variant="success")

    async def start_services(self) -> None:
        """Start Docker Compose services."""
        self.show_info("[bold]Starting Thoth services...[/bold]")
        
        try:
            # Get project root (parent of vault/_thoth)
            vault_path = self.app.wizard_data.get("vault_path", "")
            if not vault_path:
                self.show_error("Vault path not found. Please start services manually with: thoth start")
                return
            
            vault_root = Path(vault_path).resolve()
            project_root = vault_root.parent if vault_root.name == "_thoth" else vault_root
            while project_root.name != "project-thoth" and project_root != project_root.parent:
                project_root = project_root.parent
            
            # Check Letta mode
            letta_mode = self.app.wizard_data.get("letta_mode", "self-hosted")
            
            # Start Letta if self-hosted
            if letta_mode == "self-hosted":
                self.show_info("Starting Letta (self-hosted mode)...")
                result = subprocess.run(
                    ["docker", "compose", "-f", "docker-compose.letta.yml", "up", "-d"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    logger.warning(f"Letta start had issues: {result.stderr}")
                    self.show_warning("Letta containers may need manual start")
                else:
                    self.show_success("✓ Letta started")
                
                # Wait for Letta to be ready
                import time
                time.sleep(3)
            
            # Start Thoth services
            self.show_info("Starting Thoth services...")
            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.services_started = True
                self.show_success(
                    "\n[bold green]✓ Thoth is now running![/bold green]\n\n"
                    "[bold]Access points:[/bold]\n"
                    "  • API Server: [cyan]http://localhost:8000[/cyan]\n"
                    "  • MCP Server: [cyan]http://localhost:8001[/cyan]\n"
                    f"  • Letta: [cyan]{'Cloud' if letta_mode == 'cloud' else 'http://localhost:8283'}[/cyan]\n\n"
                    "[bold]Quick commands:[/bold]\n"
                    "  • [cyan]thoth status[/cyan]  - Check running services\n"
                    "  • [cyan]thoth logs[/cyan]    - View logs\n"
                    "  • [cyan]thoth stop[/cyan]    - Stop services (save RAM)\n"
                )
            else:
                self.show_error(
                    f"Failed to start services: {result.stderr}\n\n"
                    "You can start manually with: [cyan]thoth start[/cyan]"
                )
        
        except subprocess.TimeoutExpired:
            self.show_error("Service startup timed out. Try: [cyan]thoth start[/cyan]")
        except Exception as e:
            logger.error(f"Error starting services: {e}")
            self.show_error(f"Error: {e}\n\nStart manually with: [cyan]thoth start[/cyan]")
    
    def show_manual_start_instructions(self) -> None:
        """Show instructions for manual service start."""
        self.show_info(
            "\n[bold]Services not started[/bold]\n\n"
            "When ready to use Thoth, run:\n"
            "  [cyan]thoth start[/cyan]\n\n"
            "This will start all services (~1-1.5GB RAM).\n"
            "You can stop anytime with: [cyan]thoth stop[/cyan]\n"
        )

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

        if button_id == "start-now":
            logger.info("User chose to start services now")
            self.auto_start_asked = True
            await self.start_services()
            # Refresh screen to show new buttons
            await self.refresh_content()
        elif button_id == "manual-start":
            logger.info("User chose to start services manually")
            self.auto_start_asked = True
            self.show_manual_start_instructions()
            # Refresh screen to show new buttons
            await self.refresh_content()
        elif button_id == "docs":
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

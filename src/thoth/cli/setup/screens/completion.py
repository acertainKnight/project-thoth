"""Completion screen for setup wizard.

Shows installation summary and next steps.
"""

from __future__ import annotations

import subprocess  # nosec B404  # Required for platform detection and plugin building
import urllib.request  # nosec B310  # Required for downloading plugin from GitHub releases
import zipfile
from pathlib import Path
from typing import Any

# Note: CompletionScreen uses custom button handler, not base on_button_pressed
from loguru import logger
from textual.app import ComposeResult
from textual.widgets import Button, Static

from .base import BaseScreen


class CompletionScreen(BaseScreen):
    """Screen showing setup completion and next steps."""

    def __init__(self) -> None:
        """Initialize completion screen."""
        super().__init__(
            title='Setup Complete!',
            subtitle='Thoth is ready to use',
        )
        self.services_started = False
        self.auto_start_asked = False
        self.plugin_installed = False

    async def on_mount(self) -> None:
        """Called when screen is mounted."""
        # Install plugin when screen loads
        if not self.plugin_installed:
            self.plugin_installed = await self.install_obsidian_plugin()

    def compose_content(self) -> ComposeResult:
        """Compose completion content.

        Returns:
            Content widgets
        """
        # Get installation summary from wizard data
        vault_path = ''
        providers_configured = 0
        letta_mode = 'self-hosted'
        deployment_mode = 'local'

        if hasattr(self.app, 'wizard_data'):
            wd = getattr(self.app, 'wizard_data', {})
            vault_path = str(wd.get('vault_path_host', wd.get('vault_path', '')))
            letta_mode = getattr(self.app, 'wizard_data', {}).get(
                'letta_mode', 'self-hosted'
            )
            deployment_mode = getattr(self.app, 'wizard_data', {}).get(
                'deployment_mode', 'local'
            )
            llm_settings = getattr(self.app, 'wizard_data', {}).get('llm_settings', {})
            providers = llm_settings.get('providers', {})
            providers_configured = sum(
                1 for p in providers.values() if p.get('enabled', False)
            )

        # Get workspace path from paths config
        paths_config = {}
        if hasattr(self.app, 'wizard_data'):
            paths_config = getattr(self.app, 'wizard_data', {}).get('paths_config', {})
        workspace_rel = paths_config.get('workspace', 'thoth/_thoth')

        # Different messages for local vs remote deployment
        if deployment_mode == 'remote':
            thoth_api_url = getattr(self.app, 'wizard_data', {}).get(
                'thoth_api_url', 'http://localhost:8000'
            )
            letta_url = getattr(self.app, 'wizard_data', {}).get(
                'letta_url', 'http://localhost:8283'
            )

            yield Static(
                f'[bold green]✓ Thoth has been successfully configured![/bold green]\n\n'
                f'[bold]Configuration Summary:[/bold]\n'
                f'  • [cyan]Deployment Mode:[/cyan] Remote\n'
                f'  • [cyan]Vault:[/cyan] {vault_path}\n'
                f'  • [cyan]Thoth Server:[/cyan] {thoth_api_url}\n'
                f'  • [cyan]Letta Server:[/cyan] {letta_url}\n'
                f'  • [cyan]LLM Providers:[/cyan] {providers_configured} configured\n'
                f'  • [cyan]Workspace:[/cyan] {vault_path}/{workspace_rel}',
                id='summary-text',
            )

            # Remote mode - no service start needed
            yield Static(
                '\n[bold green]✓ Configuration complete![/bold green]\n\n'
                'Your Obsidian plugin is configured to connect to:\n'
                f'  • Thoth API: [cyan]{thoth_api_url}[/cyan]\n'
                f'  • Letta: [cyan]{letta_url}[/cyan]\n\n'
                '[yellow]Important:[/yellow] Ensure your remote servers are running before using Thoth.\n\n'
                '[bold]Recommended: Obsidian Sync[/bold]\n'
                'Thoth does not sync your vault between devices. We strongly\n'
                'recommend [cyan]Obsidian Sync[/cyan] for remote deployments:\n'
                '  • Keeps your vault in sync with the remote server\n'
                '  • Enable [bold]Sync community plugins[/bold] and [bold]Settings[/bold]\n'
                '    so local config changes hot-reload into Thoth\n'
                '  • Enables mobile access to your Thoth-powered vault',
                id='start-prompt',
            )
        else:
            # Local mode - show service start prompt
            yield Static(
                f'[bold green]✓ Thoth has been successfully installed![/bold green]\n\n'
                f'[bold]Installation Summary:[/bold]\n'
                f'  • [cyan]Deployment Mode:[/cyan] Local\n'
                f'  • [cyan]Vault:[/cyan] {vault_path}\n'
                f'  • [cyan]Letta Mode:[/cyan] {letta_mode.title()}\n'
                f'  • [cyan]LLM Providers:[/cyan] {providers_configured} configured\n'
                f'  • [cyan]Workspace:[/cyan] {vault_path}/{workspace_rel}',
                id='summary-text',
            )

            # Service start prompt
            yield Static(
                '\n[bold]Start Thoth services now?[/bold]\n'
                'RAM usage: [yellow]~1GB[/yellow] (Cloud) or [yellow]~1.5GB[/yellow] (Self-hosted)\n'
                'Stop anytime with: [cyan]thoth stop[/cyan]',
                id='start-prompt',
            )

        # Status area for service start / next steps (updated dynamically)
        yield Static('', id='status-area')

    def compose_buttons(self) -> ComposeResult:
        """Compose buttons for completion screen.

        Returns:
            Button widgets
        """
        # Check deployment mode to decide button visibility
        deployment_mode = 'local'
        if hasattr(self.app, 'wizard_data'):
            deployment_mode = getattr(self.app, 'wizard_data', {}).get(
                'deployment_mode', 'local'
            )

        if deployment_mode == 'remote':
            # Remote mode - only show Finish button
            yield Button('Finish', id='finish', variant='success')
        else:
            # Local mode - show Start and Skip buttons
            yield Button('Start Thoth Now', id='start-now', variant='success')
            yield Button('Skip → Finish', id='finish', variant='default')

    async def install_obsidian_plugin(self) -> bool:
        """Install Obsidian plugin to vault.

        Returns:
            True if successful, False otherwise
        """
        vault_path = getattr(self.app, 'wizard_data', {}).get('vault_path', '')
        if not vault_path:
            return False

        vault_root = Path(vault_path).resolve()
        plugin_dir = vault_root / '.obsidian' / 'plugins' / 'thoth-obsidian'
        plugin_dir.mkdir(parents=True, exist_ok=True)

        self.show_info('[bold]Installing Obsidian plugin...[/bold]')

        try:
            # Try to download pre-built plugin from latest release
            latest_release_url = 'https://api.github.com/repos/acertainknight/project-thoth/releases/latest'

            try:
                with urllib.request.urlopen(latest_release_url, timeout=10) as response:  # nosec B310  # URL is from GitHub API
                    import json

                    release_data = json.loads(response.read().decode())

                    # Find plugin zip in assets
                    plugin_asset = None
                    for asset in release_data.get('assets', []):
                        if asset['name'].startswith('thoth-obsidian-') and asset[
                            'name'
                        ].endswith('.zip'):
                            plugin_asset = asset
                            break

                    if plugin_asset:
                        # Download plugin
                        self.show_info(
                            f'Downloading plugin v{release_data["tag_name"]}...'
                        )
                        zip_path = plugin_dir / 'plugin.zip'

                        urllib.request.urlretrieve(  # nosec B310  # URL is from GitHub API
                            plugin_asset['browser_download_url'], zip_path
                        )

                        # Extract
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(plugin_dir)

                        zip_path.unlink()  # Remove zip
                        self.show_success('✓ Plugin downloaded from release')
                        return True

            except Exception as e:
                logger.debug(f'Could not download plugin from release: {e}')
                self.show_info('Release version not available, building locally...')

            # Fallback: Try to find and build plugin from project source
            plugin_src = self._find_plugin_source(vault_root)

            if plugin_src and plugin_src.exists():
                self.show_info('Building plugin from source...')
                try:
                    result = subprocess.run(  # nosec B603  # Safe: command from trusted source
                        ['npm', 'install'],
                        cwd=plugin_src,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )

                    if result.returncode == 0:
                        result = subprocess.run(  # nosec B603  # Safe: command from trusted source
                            ['npm', 'run', 'build'],
                            cwd=plugin_src,
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )

                    if result.returncode == 0:
                        import shutil

                        for file in ['main.js', 'manifest.json', 'styles.css']:
                            src = plugin_src / file
                            if src.exists():
                                shutil.copy(src, plugin_dir / file)
                        self.show_success('✓ Plugin built and installed')
                        return True
                except Exception as e:
                    logger.debug(f'Local build failed: {e}')

            # Final fallback: Create plugin directory with data.json
            # so the user can manually install plugin files later
            self._write_plugin_data_json(plugin_dir)
            self.show_warning(
                'Could not download or build plugin automatically.\n'
                'Plugin directory created with endpoint config.\n'
                'Install plugin files manually from the GitHub releases page.'
            )
            return False

        except Exception as e:
            logger.error(f'Plugin installation failed: {e}')
            self.show_warning(f'Could not install plugin: {e}')
            return False

    def _find_project_root(self) -> Path | None:
        """Find the project root (where docker-compose.yml lives).

        Returns:
            Path to project root, or None if not found.
        """
        import os

        env_root = os.environ.get('THOTH_PROJECT_ROOT')
        if env_root:
            p = Path(env_root)
            if p.is_dir():
                return p

        for candidate in [
            Path.cwd(),
            Path.home() / 'thoth',
        ]:
            if candidate.is_dir() and (candidate / 'docker-compose.yml').exists():
                return candidate

        # Walk up from this file
        current = Path(__file__).resolve().parent
        for _ in range(10):
            if (current / 'pyproject.toml').exists():
                return current
            if current == current.parent:
                break
            current = current.parent

        return None

    def _find_plugin_source(self, vault_root: Path) -> Path | None:
        """Find plugin source directory by searching common locations.

        Args:
            vault_root: Path to the Obsidian vault

        Returns:
            Path to plugin source or None
        """
        # Try walking up from vault to find project root
        candidate = vault_root
        for _ in range(10):
            plugin_src = candidate / 'obsidian-plugin' / 'thoth-obsidian'
            if plugin_src.exists():
                return plugin_src
            if candidate == candidate.parent:
                break
            candidate = candidate.parent

        # Try common locations
        for path in [
            Path('/app/obsidian-plugin/thoth-obsidian'),  # Docker container
            Path.home() / 'project-thoth' / 'obsidian-plugin' / 'thoth-obsidian',
            Path.cwd() / 'obsidian-plugin' / 'thoth-obsidian',
        ]:
            if path.exists():
                return path

        return None

    def _write_plugin_data_json(self, plugin_dir: Path) -> None:
        """Write data.json to plugin directory with endpoint configuration.

        This ensures the plugin knows where to connect even if the full
        plugin files need to be installed manually.

        Args:
            plugin_dir: Path to plugin directory
        """
        import json

        wizard_data = (
            getattr(self.app, 'wizard_data', {})
            if hasattr(self.app, 'wizard_data')
            else {}
        )
        deployment_mode = wizard_data.get('deployment_mode', 'local')
        thoth_api_url = wizard_data.get('thoth_api_url', 'http://localhost:8000')
        letta_url = wizard_data.get('letta_url', 'http://localhost:8283')
        is_remote = deployment_mode == 'remote'

        data = {
            'remoteMode': is_remote,
            'remoteEndpointUrl': thoth_api_url
            if is_remote
            else 'http://localhost:8000',
            'lettaEndpointUrl': letta_url,
        }

        try:
            plugin_dir.mkdir(parents=True, exist_ok=True)
            data_path = plugin_dir / 'data.json'
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.info(f'Wrote plugin data.json to {data_path}')
        except Exception as e:
            logger.error(f'Failed to write plugin data.json: {e}')

    async def start_services(self) -> None:
        """Start Docker Compose services (local deployment only)."""
        import os

        # Check deployment mode - skip if remote
        deployment_mode = getattr(self.app, 'wizard_data', {}).get(
            'deployment_mode', 'local'
        )
        if deployment_mode == 'remote':
            self.show_info(
                '[yellow]Remote deployment detected - Docker services not needed.[/yellow]\n'
                'Your remote Thoth and Letta servers should already be running.'
            )
            return

        # Inside the Docker setup container, we can't start compose services
        # because the Docker daemon runs on the host and volume mount paths
        # from the compose file would resolve to container paths, not host
        # paths. Defer to install.sh which runs on the host after the wizard.
        if os.environ.get('THOTH_DOCKER_SETUP') == '1':
            self.services_started = True
            self.show_success(
                '\n[bold green]Configuration saved successfully![/bold green]\n\n'
                'Services will start automatically after the wizard exits.\n'
                'Or start them manually any time with:\n\n'
                '  [cyan]thoth start[/cyan]\n'
            )
            return

        self.show_info('[bold]Starting Thoth services...[/bold]')

        try:
            project_root = self._find_project_root()
            if not project_root:
                self.show_error(
                    'Could not find project root. '
                    'Start services manually with: thoth start'
                )
                return

            letta_mode = getattr(self.app, 'wizard_data', {}).get(
                'letta_mode', 'self-hosted'
            )

            # Start Letta if self-hosted
            if letta_mode == 'self-hosted':
                self.show_info('Starting Letta (self-hosted mode)...')
                result = subprocess.run(  # nosec B603
                    ['docker', 'compose', '-f', 'docker-compose.letta.yml', 'up', '-d'],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    logger.warning(f'Letta start had issues: {result.stderr}')
                    self.show_warning('Letta containers may need manual start')
                else:
                    self.show_success('Letta started')

                import time

                time.sleep(3)

            # Start Thoth microservices
            self.show_info('Starting Thoth services...')
            result = subprocess.run(  # nosec B603
                [
                    'docker',
                    'compose',
                    'up',
                    '-d',
                    '--build',
                ],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                self.services_started = True
                self.show_success(
                    '\n[bold green]Thoth is now running![/bold green]\n\n'
                    '[bold]Access points:[/bold]\n'
                    '  API Server: [cyan]http://localhost:8080[/cyan]\n'
                    '  MCP Server: [cyan]http://localhost:8082[/cyan]\n'
                    f'  Letta: [cyan]{"Cloud" if letta_mode == "cloud" else "http://localhost:8283"}[/cyan]\n\n'
                    '[bold]Quick commands:[/bold]\n'
                    '  [cyan]thoth status[/cyan]  - Check running services\n'
                    '  [cyan]thoth logs[/cyan]    - View logs\n'
                    '  [cyan]thoth stop[/cyan]    - Stop services (save RAM)\n'
                )
            else:
                self.show_error(
                    f'Failed to start services: {result.stderr}\n\n'
                    'You can start manually with: [cyan]thoth start[/cyan]'
                )

        except subprocess.TimeoutExpired:
            self.show_error('Service startup timed out. Try: [cyan]thoth start[/cyan]')
        except Exception as e:
            logger.error(f'Error starting services: {e}')
            self.show_error(
                f'Error: {e}\n\nStart manually with: [cyan]thoth start[/cyan]'
            )

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """Validate completion screen (always passes).

        Returns:
            Empty dict (setup is complete)
        """
        logger.info('Setup wizard completed successfully')
        return {}

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        Args:
            event: Button pressed event
        """
        button_id = event.button.id

        if button_id == 'start-now':
            logger.info('User chose to start services now')
            await self.start_services()
            self._show_next_steps()
        elif button_id == 'finish':
            logger.info('User finished setup wizard')
            self.app.exit()
        elif button_id == 'cancel':
            self.action_cancel()

    def _show_next_steps(self) -> None:
        """Update status area with next steps after service start attempt."""
        # Check deployment mode for different next steps
        deployment_mode = 'local'
        if hasattr(self.app, 'wizard_data'):
            deployment_mode = getattr(self.app, 'wizard_data', {}).get(
                'deployment_mode', 'local'
            )

        if deployment_mode == 'remote':
            next_steps = (
                '\n[bold]Next Steps:[/bold]\n'
                '  1. Restart Obsidian to load the Thoth plugin\n'
                '  2. Enable plugin in Settings → Community Plugins → Thoth\n'
                '  3. Verify your remote servers are running\n'
                '  4. Open Thoth from the Obsidian ribbon icon\n\n'
                '[bold]Remote Endpoints:[/bold]\n'
                f'  Thoth: [cyan]{getattr(self.app, "wizard_data", {}).get("thoth_api_url", "N/A")}[/cyan]\n'
                f'  Letta: [cyan]{getattr(self.app, "wizard_data", {}).get("letta_url", "N/A")}[/cyan]\n\n'
                '[dim]Press Finish to exit the wizard.[/dim]'
            )
        else:
            next_steps = (
                '\n[bold]Next Steps:[/bold]\n'
                '  1. Restart Obsidian to load the Thoth plugin\n'
                '  2. Enable plugin in Settings → Community Plugins → Thoth\n'
                '  3. Upload notes with: [cyan]thoth letta sync[/cyan]\n'
                '  4. Open Thoth from the Obsidian ribbon icon\n\n'
                '[bold]Useful Commands:[/bold]\n'
                '  [cyan]thoth start[/cyan]   Start services\n'
                '  [cyan]thoth stop[/cyan]    Stop services\n'
                "  [cyan]thoth status[/cyan]  Check what's running\n"
                '  [cyan]thoth logs[/cyan]    View service logs\n\n'
                '[dim]Press Skip → Finish to exit the wizard.[/dim]'
            )

        try:
            status_area = self.query_one('#status-area', Static)
            status_area.update(next_steps)

            # Hide the start prompt
            start_prompt = self.query_one('#start-prompt', Static)
            start_prompt.update('')

            # Update buttons based on deployment mode
            if deployment_mode != 'remote':
                # Local mode: hide Start button, rename Finish
                try:
                    start_btn = self.query_one('#start-now', Button)
                    start_btn.styles.display = 'none'
                except Exception as e:
                    logger.debug(f'Start button might not exist: {e}')

            finish_btn = self.query_one('#finish', Button)
            finish_btn.label = 'Finish'
            finish_btn.variant = 'success'
        except Exception as e:
            logger.debug(f'UI update failed: {e}')

    async def on_next_screen(self) -> None:
        """No next screen - this is the final screen."""
        logger.info('Completion screen is the final screen')
        self.app.exit()

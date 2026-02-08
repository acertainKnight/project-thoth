"""Installation screen for setup wizard.

Performs the actual installation of Thoth components.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.widgets import Button, ProgressBar, Static

from ..transaction import Transaction
from .base import BaseScreen


class InstallationScreen(BaseScreen):
    """Screen for installing Thoth components."""

    def __init__(self) -> None:
        """Initialize installation screen."""
        super().__init__(
            title='Installing Thoth',
            subtitle='Setting up your research assistant',
        )
        self.vault_path: Path | None = None
        self.installation_complete = False
        self.installation_steps = [
            'Creating workspace directory',
            'Saving configuration',
            'Setting up database schema',
            'Installing Obsidian plugin',
            'Validating installation',
        ]
        self.current_step = 0
        self.transaction = Transaction()

    def on_mount(self) -> None:
        """Run when screen is mounted."""
        # Get vault path from wizard
        if hasattr(self.app, 'wizard_data'):
            self.vault_path = self.app.wizard_data.get('vault_path')

        # Start installation automatically
        self._install_task = asyncio.create_task(self.run_installation())

    def _update_step(self, step_num: int, state: str = 'pending') -> None:
        """Update a step's visual state dynamically.

        Args:
            step_num: Step number (1-based)
            state: One of 'pending', 'active', 'done', 'error'
        """
        if step_num < 1 or step_num > len(self.installation_steps):
            return
        step_name = self.installation_steps[step_num - 1]
        icons = {
            'pending': f'[dim]○ {step_name}[/dim]',
            'active': f'[cyan]⟳ {step_name}...[/cyan]',
            'done': f'[green]✓ {step_name}[/green]',
            'error': f'[red]✗ {step_name}[/red]',
        }
        try:
            widget = self.query_one(f'#step-{step_num}', Static)
            widget.update(icons.get(state, icons['pending']))
        except Exception:
            pass

    async def run_installation(self) -> None:
        """Run the installation process with transaction support."""
        self.show_info('Starting installation...')

        try:
            progress_bar = self.query_one('#install-progress', ProgressBar)
            status_text = self.query_one('#status-text', Static)

            # Step 1: Create workspace directory
            self.current_step = 1
            self._update_step(1, 'active')
            status_text.update(f'[cyan]{self.installation_steps[0]}...[/cyan]')
            progress_bar.update(progress=20)
            await self.create_workspace()
            self._update_step(1, 'done')
            await asyncio.sleep(0.3)

            # Step 2: Save configuration
            self.current_step = 2
            self._update_step(2, 'active')
            status_text.update(f'[cyan]{self.installation_steps[1]}...[/cyan]')
            progress_bar.update(progress=40)
            await self.save_configuration()
            self._update_step(2, 'done')
            await asyncio.sleep(0.3)

            # Step 3: Set up database schema
            self.current_step = 3
            self._update_step(3, 'active')
            status_text.update(f'[cyan]{self.installation_steps[2]}...[/cyan]')
            progress_bar.update(progress=60)
            await self.setup_database()
            self._update_step(3, 'done')
            await asyncio.sleep(0.3)

            # Step 4: Install Obsidian plugin
            self.current_step = 4
            self._update_step(4, 'active')
            status_text.update(f'[cyan]{self.installation_steps[3]}...[/cyan]')
            progress_bar.update(progress=80)
            await self.install_plugin()
            self._update_step(4, 'done')
            await asyncio.sleep(0.3)

            # Step 5: Validate installation
            self.current_step = 5
            self._update_step(5, 'active')
            status_text.update(f'[cyan]{self.installation_steps[4]}...[/cyan]')
            progress_bar.update(progress=95)
            await self.validate_installation()
            self._update_step(5, 'done')
            await asyncio.sleep(0.3)

            # Complete - commit transaction
            self.transaction.commit()
            progress_bar.update(progress=100)
            status_text.update('[bold green]✓ Installation complete![/bold green]')
            self.installation_complete = True
            self.clear_messages()
            self.show_success(
                'Thoth installed successfully! Press Next → to finish setup.'
            )

            # Show the Next button now
            self._show_next_button()

        except Exception as e:
            logger.error(f'Installation failed: {e}')
            # Mark current step as error
            self._update_step(self.current_step, 'error')
            self.show_error(f'Installation failed: {e}')
            # Rollback on error
            self.transaction.rollback()
            self.show_error(
                f'Step {self.current_step} failed: {e}\n'
                'Changes have been rolled back. Fix the issue and try again.'
            )

    def _show_next_button(self) -> None:
        """Show the Next button after installation completes."""
        try:
            next_btn = self.query_one('#next', Button)
            next_btn.styles.display = 'block'
        except Exception:
            pass

    async def create_workspace(self) -> None:
        """Create Thoth workspace and user-facing directories in vault."""
        if not self.vault_path:
            raise ValueError('No vault path specified')

        # Get path settings from wizard data (or use defaults)
        wizard_data = self.app.wizard_data if hasattr(self.app, 'wizard_data') else {}
        paths_config = wizard_data.get('paths_config', {})
        workspace_rel = paths_config.get('workspace', 'thoth/_thoth')
        pdf_rel = paths_config.get('pdf', 'thoth/papers/pdfs')
        notes_rel = paths_config.get('notes', 'thoth/notes')
        markdown_rel = paths_config.get('markdown', 'thoth/papers/markdown')

        # Create workspace (internal data)
        workspace_dir = self.vault_path / workspace_rel
        for subdir in [
            workspace_dir,
            workspace_dir / 'data',
            workspace_dir / 'logs',
            workspace_dir / 'cache',
            workspace_dir / 'backups',
        ]:
            if not subdir.exists():
                subdir.mkdir(parents=True, exist_ok=True)
                self.transaction.record_create_directory(subdir)

        # Create user-facing directories
        for rel_path in (pdf_rel, notes_rel, markdown_rel):
            full = self.vault_path / rel_path
            if not full.exists():
                full.mkdir(parents=True, exist_ok=True)
                self.transaction.record_create_directory(full)

        logger.info(f'Created workspace at {workspace_dir}')
        logger.info(f'Created PDF dir at {self.vault_path / pdf_rel}')
        logger.info(f'Created notes dir at {self.vault_path / notes_rel}')
        logger.info(f'Created markdown dir at {self.vault_path / markdown_rel}')

    async def save_configuration(self) -> None:
        """Save configuration to settings.json, .env, and .env.letta."""
        if not self.vault_path:
            raise ValueError('No vault path specified')

        from ..config_manager import ConfigManager

        config_manager = ConfigManager(self.vault_path)

        # Get wizard data
        wizard_data = self.app.wizard_data if hasattr(self.app, 'wizard_data') else {}

        # Get API keys
        api_keys = wizard_data.get('api_keys', {})

        # Get model settings
        model_settings = wizard_data.get('model_settings', {})

        # Get Letta configuration
        letta_mode = wizard_data.get('letta_mode', 'self-hosted')
        letta_api_key = wizard_data.get('letta_api_key', '')
        letta_url = wizard_data.get('letta_url') or (
            'https://api.letta.com'
            if letta_mode == 'cloud'
            else 'http://localhost:8283'
        )

        # Get deployment configuration
        deployment_mode = wizard_data.get('deployment_mode', 'local')
        thoth_api_url = wizard_data.get('thoth_api_url', 'http://localhost:8000')
        thoth_mcp_url = wizard_data.get('thoth_mcp_url', 'http://localhost:8001')

        # Get path configuration from vault selection screen
        paths_config = wizard_data.get('paths_config', {})

        # Parse URLs for host/port (for backend settings.json)
        from urllib.parse import urlparse

        api_parsed = urlparse(thoth_api_url)
        mcp_parsed = urlparse(thoth_mcp_url)

        # Build configuration dict that matches settings.json schema
        workspace_path = paths_config.get('workspace', 'thoth/_thoth')
        settings: dict[str, Any] = {
            'version': '1.0.0',
            'vault_path': str(self.vault_path),
            'paths': {
                'workspace': workspace_path,
                'pdf': paths_config.get('pdf', 'thoth/papers/pdfs'),
                'markdown': paths_config.get('markdown', 'thoth/papers/markdown'),
                'notes': paths_config.get('notes', 'thoth/notes'),
                'prompts': f'{workspace_path}/data/prompts',
                'templates': f'{workspace_path}/data/templates',
                'output': f'{workspace_path}/data/output',
                'knowledgeBase': f'{workspace_path}/data/knowledge',
                'graphStorage': f'{workspace_path}/data/graph/citations.graphml',
                'queries': f'{workspace_path}/data/queries',
                'agentStorage': f'{workspace_path}/data/agent',
                'logs': f'{workspace_path}/logs',
            },
            'database': {
                'host': 'localhost',
                'port': 5432,
                'database': 'thoth',
            },
            'letta': {
                'url': letta_url,
                'mode': letta_mode,
            },
            'servers': {
                'api': {
                    'baseUrl': thoth_api_url,
                    'host': api_parsed.hostname or 'localhost',
                    'port': api_parsed.port or 8000,
                },
                'mcp': {
                    'host': mcp_parsed.hostname or 'localhost',
                    'port': mcp_parsed.port or 8001,
                },
            },
        }

        # Map model_settings to the full settings.json structure
        if model_settings:
            # LLM settings
            llm_config = model_settings.get('llm', {})
            if llm_config:
                settings['llm'] = llm_config

            # RAG settings
            rag_config = model_settings.get('rag', {})
            if rag_config:
                settings['rag'] = rag_config

            # Memory settings (Letta agent model)
            memory_config = model_settings.get('memory', {})
            if memory_config:
                settings['memory'] = memory_config

        # Add API keys to apiKeys section
        if api_keys:
            settings['apiKeys'] = {
                'openaiKey': api_keys.get('openai', ''),
                'anthropicKey': api_keys.get('anthropic', ''),
                'openrouterKey': api_keys.get('openrouter', ''),
                'googleApiKey': api_keys.get('google', ''),
                'mistralKey': api_keys.get('mistral', ''),
            }

        # Add Letta API key if cloud mode
        if letta_mode == 'cloud' and letta_api_key:
            if 'apiKeys' not in settings:
                settings['apiKeys'] = {}
            settings['apiKeys']['lettaApiKey'] = letta_api_key

        # Merge with existing config if present
        existing = config_manager.load_existing()
        if existing:
            settings = config_manager.deep_merge(existing, settings)

        # Create backup before modifying
        workspace_rel = paths_config.get('workspace', 'thoth/_thoth')
        settings_path = self.vault_path / workspace_rel / 'settings.json'
        if settings_path.exists():
            backup_path = config_manager.backup()
            if backup_path is not None:
                self.transaction.record_modify_config(settings_path, backup_path)

        # Validate and save
        config_manager.validate_schema(settings)
        config_manager.atomic_save(settings)
        self.transaction.record_write_file(settings_path)
        logger.info('Configuration saved to settings.json')

        # --- Write plugin data.json with remote mode settings ---
        await self._write_plugin_data(deployment_mode, thoth_api_url, letta_url)

        # --- Write API keys to .env and .env.letta ---
        await self._write_env_files(api_keys, letta_mode)

    async def _write_plugin_data(
        self,
        deployment_mode: str,
        thoth_api_url: str,
        letta_url: str,
    ) -> None:
        """Write plugin data.json with remote mode and endpoint settings.

        Args:
            deployment_mode: 'local' or 'remote'
            thoth_api_url: Thoth API endpoint URL
            letta_url: Letta API endpoint URL
        """
        if not self.vault_path:
            logger.warning('No vault path, skipping plugin data.json')
            return

        import json

        plugins_dir = self.vault_path / '.obsidian' / 'plugins' / 'thoth'
        data_json_path = plugins_dir / 'data.json'

        # Read existing data.json if present
        existing_data = {}
        if data_json_path.exists():
            try:
                with open(data_json_path, encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logger.warning(f'Could not read existing data.json: {e}')

        # Build plugin settings
        is_remote = deployment_mode == 'remote'
        plugin_data = {
            **existing_data,  # Preserve any existing settings
            'remoteMode': is_remote,
            'remoteEndpointUrl': thoth_api_url
            if is_remote
            else 'http://localhost:8000',  # Only Thoth API URL
            'lettaEndpointUrl': letta_url,
        }

        # Write data.json
        try:
            plugins_dir.mkdir(parents=True, exist_ok=True)
            with open(data_json_path, 'w', encoding='utf-8') as f:
                json.dump(plugin_data, f, indent=2)
            self.transaction.record_write_file(data_json_path)
            logger.info(f'Plugin data.json written with remoteMode={is_remote}')
        except Exception as e:
            logger.error(f'Failed to write plugin data.json: {e}')

    async def _write_env_files(
        self,
        api_keys: dict[str, str],
        letta_mode: str,
    ) -> None:
        """Write API keys to .env (Thoth) and .env.letta (Letta server).

        Reads existing files, updates only the key lines, preserves everything else.

        Args:
            api_keys: Dict of provider -> API key
            letta_mode: 'self-hosted', 'cloud', or 'remote'
        """
        # Extract keys
        openai_key = api_keys.get('openai', '')
        anthropic_key = api_keys.get('anthropic', '')
        google_key = api_keys.get('google', '')
        mistral_key = api_keys.get('mistral', '')
        openrouter_key = api_keys.get('openrouter', '')

        # Find project root (where .env files live)
        project_root = self._find_project_root()
        if not project_root:
            logger.warning('Could not find project root, skipping .env file writes')
            return

        # --- Update .env (Thoth services) ---
        env_path = project_root / '.env'
        thoth_env_keys = {
            'OPENAI_API_KEY': openai_key,
            'API_OPENAI_KEY': openai_key,
            'ANTHROPIC_API_KEY': anthropic_key,
            'API_MISTRAL_KEY': mistral_key,
            'API_OPENROUTER_KEY': openrouter_key,
            'GOOGLE_API_KEY': google_key,
        }
        self._update_env_file(env_path, thoth_env_keys)
        logger.info(f'Updated API keys in {env_path}')

        # --- Update .env.letta (Letta server) - only for self-hosted ---
        if letta_mode == 'self-hosted':
            letta_env_path = project_root / '.env.letta'
            letta_env_keys = {
                'OPENAI_API_KEY': openai_key,
                'OPENAI_EMBEDDING_API_KEY': openai_key,
                'ANTHROPIC_API_KEY': anthropic_key,
                'GOOGLE_API_KEY': google_key,
            }
            self._update_env_file(letta_env_path, letta_env_keys)
            logger.info(f'Updated API keys in {letta_env_path}')

    def _find_project_root(self) -> Path | None:
        """Find the project root directory (where docker-compose.yml lives).

        Returns:
            Path to project root, or None if not found.
        """
        # Try common locations
        candidates = [
            Path.cwd(),
            Path(__file__).resolve().parent.parent.parent.parent.parent,
        ]
        for candidate in candidates:
            if (candidate / 'docker-compose.letta.yml').exists():
                return candidate
            if (candidate / 'pyproject.toml').exists():
                return candidate
        return None

    def _update_env_file(self, env_path: Path, keys: dict[str, str]) -> None:
        """Update specific keys in a .env file, preserving all other content.

        If a key exists in the file, its value is replaced in-place.
        If a key doesn't exist, it's appended.

        Args:
            env_path: Path to the .env file
            keys: Dict of KEY=value pairs to set (empty values are skipped)
        """
        # Filter out empty keys
        keys_to_write = {k: v for k, v in keys.items() if v}
        if not keys_to_write:
            return

        # Read existing file
        lines: list[str] = []
        if env_path.exists():
            lines = env_path.read_text().splitlines()

        # Track which keys we've updated
        updated_keys: set[str] = set()

        # Update existing lines
        new_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            # Skip comments and blank lines (preserve as-is)
            if not stripped or stripped.startswith('#'):
                new_lines.append(line)
                continue

            # Check if this line sets one of our keys
            key_match = stripped.split('=', 1)[0].strip() if '=' in stripped else None
            if key_match and key_match in keys_to_write:
                new_lines.append(f'{key_match}={keys_to_write[key_match]}')
                updated_keys.add(key_match)
            else:
                new_lines.append(line)

        # Append any keys that weren't already in the file
        for key, value in keys_to_write.items():
            if key not in updated_keys:
                new_lines.append(f'{key}={value}')

        env_path.write_text('\n'.join(new_lines) + '\n')

    async def setup_database(self) -> None:
        """Set up database schema using migration manager."""
        # Check if database is available
        postgres_available = False
        if hasattr(self.app, 'wizard_data'):
            postgres_available = self.app.wizard_data.get('postgres_available', False)

        if not postgres_available:
            logger.warning('PostgreSQL not available, skipping schema setup')
            logger.info('Database schema will need to be initialized manually')
            return

        # Run database migrations using the migration manager
        try:
            from thoth.migrations.migration_manager import MigrationManager

            # Build database URL from settings
            database_url = 'postgresql://thoth:thoth_password@localhost:5432/thoth'

            # Try to get custom database URL if configured
            if self.vault_path:
                wizard_data_db = (
                    self.app.wizard_data if hasattr(self.app, 'wizard_data') else {}
                )
                ws_rel = wizard_data_db.get('paths_config', {}).get(
                    'workspace', 'thoth/_thoth'
                )
                settings_path = self.vault_path / ws_rel / 'settings.json'
                if settings_path.exists():
                    import json

                    with open(settings_path) as f:
                        settings = json.load(f)
                        if 'database' in settings:
                            db = settings['database']
                            host = db.get('host', 'localhost')
                            port = db.get('port', 5432)
                            database = db.get('database', 'thoth')
                            user = db.get('user', 'thoth')
                            password = db.get('password', 'thoth_password')
                            database_url = f'postgresql://{user}:{password}@{host}:{port}/{database}'

            logger.info('Initializing database schema...')
            migration_manager = MigrationManager(database_url)

            # Apply all migrations
            success = await migration_manager.initialize_database()

            if success:
                logger.success('✓ Database schema initialized successfully!')

                # Show migration status
                status = await migration_manager.get_migration_status()
                if status['applied_count'] > 0:
                    logger.info(f'Applied {status["applied_count"]} migration(s)')
                    if status['last_migration']:
                        last = status['last_migration']
                        logger.info(
                            f'Current version: {last["version"]} ({last["name"]})'
                        )
            else:
                raise RuntimeError('Database initialization failed')

        except Exception as e:
            logger.error(f'Failed to initialize database: {e}')
            raise RuntimeError(f'Database setup failed: {e}') from e

    async def install_plugin(self) -> None:
        """Install Obsidian plugin."""
        if not self.vault_path:
            raise ValueError('No vault path specified')

        plugins_dir = self.vault_path / '.obsidian' / 'plugins' / 'thoth'
        plugins_dir.mkdir(parents=True, exist_ok=True)

        # Copy plugin files from package to vault
        try:
            import json
            import shutil
            from pathlib import Path

            # Look for plugin source directory
            plugin_src = Path(__file__).parent.parent.parent.parent / 'obsidian-plugin'

            if plugin_src.exists():
                logger.info(f'Copying plugin files from {plugin_src}')
                # Copy all plugin files
                for item in plugin_src.iterdir():
                    if item.is_file() and item.suffix in {'.js', '.json', '.css'}:
                        dest = plugins_dir / item.name
                        shutil.copy2(item, dest)
                        logger.info(f'Copied {item.name}')
            else:
                # Plugin source not found, create minimal manifest
                logger.warning('Plugin source not found, creating minimal manifest')
                manifest_path = plugins_dir / 'manifest.json'
                if not manifest_path.exists():
                    manifest = {
                        'id': 'thoth',
                        'name': 'Thoth Research Assistant',
                        'version': '1.0.0',
                        'minAppVersion': '0.15.0',
                        'description': 'AI-powered research assistant for academic papers',
                        'author': 'Thoth Team',
                        'authorUrl': 'https://github.com/yourusername/project-thoth',
                    }

                    with open(manifest_path, 'w', encoding='utf-8') as f:
                        json.dump(manifest, f, indent=2)

                logger.info("Note: You'll need to install the Obsidian plugin manually")
                logger.info(f'Plugin directory: {plugins_dir}')

        except Exception as e:
            logger.error(f'Error installing plugin: {e}')
            logger.info('You can install the plugin manually later')

        logger.info(f'Plugin directory created at {plugins_dir}')

    async def validate_installation(self) -> None:
        """Validate that installation was successful."""
        if not self.vault_path:
            raise ValueError('No vault path specified')

        # Get workspace path from wizard data
        wizard_data = self.app.wizard_data if hasattr(self.app, 'wizard_data') else {}
        paths_config = wizard_data.get('paths_config', {})
        workspace_rel = paths_config.get('workspace', 'thoth/_thoth')

        # Check workspace directory
        workspace_dir = self.vault_path / workspace_rel
        if not workspace_dir.exists():
            raise RuntimeError(f'Workspace directory not created: {workspace_dir}')

        # Check configuration file
        settings_path = workspace_dir / 'settings.json'
        if not settings_path.exists():
            raise RuntimeError('Configuration file not created')

        # Check plugin directory
        plugins_dir = self.vault_path / '.obsidian' / 'plugins' / 'thoth'
        if not plugins_dir.exists():
            raise RuntimeError('Plugin directory not created')

        logger.info('Installation validation passed')

    def compose_content(self) -> ComposeResult:
        """Compose installation content.

        Returns:
            Content widgets
        """
        yield Static('[bold]Installation Progress:[/bold]\n', classes='section-title')

        # Progress bar
        yield ProgressBar(
            id='install-progress',
            total=100,
            show_eta=False,
            show_percentage=True,
        )

        # Current status
        yield Static(
            '[dim]Preparing installation...[/dim]',
            id='status-text',
        )

        # Installation steps checklist - each step has an ID for dynamic updates
        yield Static('\n[bold]Steps:[/bold]')
        for i, step in enumerate(self.installation_steps, 1):
            yield Static(
                f'[dim]○ {step}[/dim]',
                id=f'step-{i}',
            )

    def compose_buttons(self) -> ComposeResult:
        """Compose navigation buttons.

        Returns:
            Button widgets
        """
        yield Button('Cancel & Exit', id='cancel', variant='error')
        # Next button starts hidden, shown after installation completes
        next_btn = Button('Next →', id='next', variant='success')
        next_btn.styles.display = 'none'
        yield next_btn

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """Validate installation.

        Returns:
            Dict with installation status, or None if not complete
        """
        if not self.installation_complete:
            self.show_error('Installation is not complete')
            return None

        logger.info('Installation validated successfully')
        return {'installation_complete': True}

    async def on_next_screen(self) -> None:
        """Navigate to completion screen."""
        from .completion import CompletionScreen

        logger.info('Proceeding to completion')
        await self.app.push_screen(CompletionScreen())

"""
Vault provisioning service for creating user vault directories.

Handles creation of vault directory structure, copying templates,
and initializing settings for new users in multi-tenant deployments.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    pass


class VaultProvisioner:
    """
    Service for provisioning user vault directories.

    Extracts vault creation logic from InstallationScreen for reuse
    in user registration, CLI commands, and setup wizard.

    Example:
        >>> provisioner = VaultProvisioner()
        >>> await provisioner.provision_vault('alice', Path('/vaults'))
    """

    def __init__(self):
        """Initialize vault provisioner."""
        pass

    def _find_project_root(self) -> Path | None:
        """
        Find project root containing templates and prompts.

        Returns:
            Path to project root, or None if not found
        """
        current = Path(__file__).resolve()
        for parent in [current, *list(current.parents)]:
            if (parent / 'templates').exists() or (parent / 'pyproject.toml').exists():
                return parent
        return None

    async def provision_vault(
        self,
        username: str,
        vaults_root: Path,
        paths_config: dict[str, str] | None = None,
    ) -> Path:
        """
        Provision a new user vault directory.

        Creates the full vault structure: workspace, PDFs, notes, markdown,
        templates, prompts, and a default settings.json.

        Args:
            username: Username (used as vault directory name)
            vaults_root: Parent directory containing all user vaults
            paths_config: Optional custom path configuration

        Returns:
            Path to the created vault directory

        Raises:
            ValueError: If vault already exists or creation fails

        Example:
            >>> provisioner = VaultProvisioner()
            >>> vault = await provisioner.provision_vault(
            ...     'alice',
            ...     Path('/vaults'),
            ...     {'workspace': 'thoth/_thoth', 'pdf': 'thoth/papers/pdfs'},
            ... )
            >>> print(vault)
            /vaults/alice
        """
        vault_path = vaults_root / username

        if vault_path.exists():
            raise ValueError(f'Vault already exists for user {username}: {vault_path}')

        logger.info(f'Provisioning vault for user {username} at {vault_path}')

        # Default path configuration
        if paths_config is None:
            paths_config = {
                'workspace': 'thoth/_thoth',
                'pdf': 'thoth/papers/pdfs',
                'notes': 'thoth/notes',
                'markdown': 'thoth/papers/markdown',
            }

        workspace_rel = paths_config.get('workspace', 'thoth/_thoth')
        pdf_rel = paths_config.get('pdf', 'thoth/papers/pdfs')
        notes_rel = paths_config.get('notes', 'thoth/notes')
        markdown_rel = paths_config.get('markdown', 'thoth/papers/markdown')

        # Create workspace (internal data)
        workspace_dir = vault_path / workspace_rel
        for subdir in [
            workspace_dir,
            workspace_dir / 'data',
            workspace_dir / 'logs',
            workspace_dir / 'cache',
            workspace_dir / 'backups',
        ]:
            subdir.mkdir(parents=True, exist_ok=True)
            logger.debug(f'Created directory: {subdir}')

        # Create user-facing directories
        for rel_path in (pdf_rel, notes_rel, markdown_rel):
            full = vault_path / rel_path
            full.mkdir(parents=True, exist_ok=True)
            logger.debug(f'Created directory: {full}')

        # Copy template files from project to vault
        templates_dest = workspace_dir / 'templates'
        templates_dest.mkdir(parents=True, exist_ok=True)

        repo_root = self._find_project_root()
        if repo_root:
            templates_source = repo_root / 'templates'

            if templates_source.exists():
                for template_file in templates_source.glob('*'):
                    if template_file.is_file():
                        dest_file = templates_dest / template_file.name
                        shutil.copy2(template_file, dest_file)
                        logger.debug(f'Copied template: {template_file.name}')

                # Copy analysis_schema.json to workspace root
                schema_source = templates_source / 'analysis_schema.json'
                if schema_source.exists():
                    schema_dest = workspace_dir / 'analysis_schema.json'
                    shutil.copy2(schema_source, schema_dest)
                    logger.debug('Copied analysis_schema.json')
            else:
                logger.warning(f'Template source not found: {templates_source}')

            # Copy prompt files from project to vault
            prompts_dest = workspace_dir / 'prompts'
            prompts_dest.mkdir(parents=True, exist_ok=True)

            prompts_source = repo_root / 'data' / 'prompts'

            if prompts_source.exists():
                for item in prompts_source.iterdir():
                    if item.is_dir():
                        dest_subdir = prompts_dest / item.name
                        if not dest_subdir.exists():
                            shutil.copytree(item, dest_subdir)
                            logger.debug(f'Copied prompts subdirectory: {item.name}')
                    elif item.is_file():
                        dest_file = prompts_dest / item.name
                        shutil.copy2(item, dest_file)
                        logger.debug(f'Copied prompt: {item.name}')
            else:
                logger.warning(f'Prompts source not found: {prompts_source}')
        else:
            logger.warning('Could not find project root for templates/prompts')

        # Create default settings.json
        await self._create_default_settings(workspace_dir, username)

        # Create .obsidian directory for Obsidian to recognize it
        obsidian_dir = vault_path / '.obsidian'
        obsidian_dir.mkdir(parents=True, exist_ok=True)

        # Minimal app.json for Obsidian
        app_json = obsidian_dir / 'app.json'
        app_json.write_text(
            json.dumps({'vimMode': False, 'showLineNumber': True}, indent=2)
        )

        logger.success(f'Vault provisioned for user {username}')
        logger.info(f'Workspace: {workspace_dir}')
        logger.info(f'PDF dir: {vault_path / pdf_rel}')
        logger.info(f'Notes dir: {vault_path / notes_rel}')
        logger.info(f'Markdown dir: {vault_path / markdown_rel}')

        return vault_path

    async def _create_default_settings(
        self, workspace_dir: Path, username: str
    ) -> None:
        """
        Create a default settings.json for a new user.

        Args:
            workspace_dir: Path to the workspace directory (thoth/_thoth)
            username: Username (for logging)
        """
        settings_file = workspace_dir / 'settings.json'

        # Minimal working settings - user can customize via UI
        default_settings = {
            'api_keys': {
                'openai_key': None,
                'anthropic_key': None,
                'google_key': None,
            },
            'llm_config': {
                'default': {'model': 'gemini-2.0-flash-exp', 'provider': 'google'},
                'citation': {
                    'model': 'gemini-2.0-flash-exp',
                    'provider': 'google',
                },
            },
            'paths': {
                'workspace': 'thoth/_thoth',
                'pdf': 'thoth/papers/pdfs',
                'markdown': 'thoth/papers/markdown',
                'notes': 'thoth/notes',
                'prompts': 'thoth/_thoth/prompts',
                'templates': 'thoth/_thoth/templates',
                'output': 'thoth/output',
                'knowledge_base': 'thoth/knowledge_base',
                'graph_storage': 'thoth/_thoth/graph.json',
                'queries': 'thoth/queries',
                'agent_storage': 'thoth/_thoth/agents',
                'logs': 'thoth/_thoth/logs',
                'discovery': {
                    'sources': 'thoth/_thoth/discovery/sources',
                    'results': 'thoth/_thoth/discovery/results',
                    'chrome_configs': 'thoth/_thoth/discovery/chrome_configs',
                },
            },
            'servers': {
                'api': {'host': '0.0.0.0', 'port': 8080},  # nosec B104
                'mcp': {
                    'host': '127.0.0.1',
                    'port': 8081,
                    'external_servers_file': 'thoth/_thoth/mcps.json',
                },
            },
            'postgres': {
                'host': 'localhost',
                'port': 5432,
                'database': 'thoth',
                'user': 'thoth',
            },
            'logging': {
                'console': {'enabled': True, 'level': 'INFO'},
                'file': {'enabled': True, 'level': 'DEBUG'},
            },
        }

        settings_file.write_text(json.dumps(default_settings, indent=2))
        logger.debug(f'Created default settings.json for {username}')

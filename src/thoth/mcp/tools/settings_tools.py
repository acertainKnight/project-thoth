"""
MCP tools for managing Thoth settings.

These tools allow the research agent to view and modify configuration settings
stored in thoth.settings.json. API keys and sensitive data remain in .env file.
"""

from typing import Any

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult, NoInputTool
from thoth.services.settings_service import SettingsService
from thoth.utilities.openrouter import ModelRegistry


class ViewSettingsMCPTool(MCPTool):
    """View current configuration settings."""

    @property
    def name(self) -> str:
        return 'view_settings'

    @property
    def description(self) -> str:
        return (
            'View current Thoth configuration settings. Can view all settings or a specific path. '
            'Note: API keys and sensitive data are not shown (they remain in .env file).'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'path': {
                    'type': 'string',
                    'description': "Optional setting path using dot notation (e.g., 'llm.default.model'). If not provided, shows all settings.",
                },
                'list_paths': {
                    'type': 'boolean',
                    'description': 'If true, returns a list of all available setting paths instead of values',
                    'default': False,
                },
            },
            'required': [],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """View settings."""
        try:
            settings_service = SettingsService()

            # List all available paths if requested
            if arguments.get('list_paths', False):
                paths = settings_service.get_all_settings_paths()
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Available setting paths ({len(paths)} total):\n'
                            + '\n'.join(f'  - {path}' for path in paths),
                        }
                    ]
                )

            # Get specific setting or all settings
            path = arguments.get('path')
            if path:
                value = settings_service.get_setting(path)
                if value is None:
                    return MCPToolCallResult(
                        content=[
                            {'type': 'text', 'text': f'Setting not found: {path}'}
                        ],
                        isError=True,
                    )

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': f"Setting '{path}' = {value!r}"}]
                )
            else:
                # Show all settings
                settings = settings_service.load_settings()

                # Remove internal fields
                settings_display = {
                    k: v for k, v in settings.items() if not k.startswith('_')
                }

                import json

                settings_json = json.dumps(settings_display, indent=2)

                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Current Thoth settings:\n\n{settings_json}',
                        }
                    ]
                )

        except Exception as e:
            return self.handle_error(e)


class UpdateSettingsMCPTool(MCPTool):
    """Update Thoth configuration settings."""

    # Model setting paths that should be validated against OpenRouter
    MODEL_SETTING_PATHS = {
        'llm.default.model',
        'llm.citation.model',
        'llm.tagConsolidator.consolidateModel',
        'llm.tagConsolidator.suggestModel',
        'llm.tagConsolidator.mapModel',
        'llm.researchAgent.model',
        'llm.scrapeFilter.model',
        'llm.queryBasedRouting.routingModel',
        'rag.qa.model',
        'memory.letta.agentModel',
    }

    @property
    def name(self) -> str:
        return 'update_settings'

    @property
    def description(self) -> str:
        return (
            'Update Thoth configuration settings. Use dot notation to specify the setting path. '
            "Example: update 'llm.default.model' to 'anthropic/claude-3.5-sonnet'. "
            'Note: Cannot modify API keys or sensitive data (those remain in .env file).'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'path': {
                    'type': 'string',
                    'description': "Setting path using dot notation (e.g., 'llm.default.model', 'rag.chunkSize')",
                },
                'value': {
                    'type': ['string', 'number', 'boolean', 'array', 'object', 'null'],
                    'description': 'New value for the setting (can be string, number, boolean, array, or object)',
                },
                'action': {
                    'type': 'string',
                    'enum': ['set', 'append', 'remove'],
                    'default': 'set',
                    'description': "Action to perform: 'set' replaces value, 'append' adds to array, 'remove' deletes",
                },
            },
            'required': ['path', 'value'],
        }

    async def _check_model_availability(self, model_id: str) -> str | None:
        """
        Check if a model exists in OpenRouter registry (advisory only).

        Args:
            model_id: Model identifier to check

        Returns:
            Warning message if model not found, None if found or check fails
        """
        try:
            # Fetch models from registry (uses cache)
            models = await ModelRegistry.get_openrouter_models()
            model_ids = {m.id for m in models}

            if model_id not in model_ids:
                # Check context length as extra info
                context_len = ModelRegistry.get_context_length(model_id)
                if context_len is None:
                    return (
                        f"Advisory: Model '{model_id}' not found in OpenRouter registry. "
                        'This may be a newly added model or a typo. '
                        'The setting was still updated successfully.'
                    )
            return None
        except Exception:
            # If we can't check (offline, API error), don't block the update
            return None

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Update a setting."""
        path = arguments['path']
        value = arguments['value']
        action = arguments.get('action', 'set')

        # Prevent modification of sensitive paths
        sensitive_paths = ['apiKeys', 'security', 'encryption', 'jwt', 'database']
        for sensitive in sensitive_paths:
            if sensitive.lower() in path.lower():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Cannot modify sensitive setting '{path}'. API keys and security settings must be changed in .env file.",
                        }
                    ],
                    isError=True,
                )

        try:
            settings_service = SettingsService()

            # Get current value for comparison
            old_value = settings_service.get_setting(path)

            # Update the setting
            success = settings_service.update_setting(path, value, action)

            if success:
                # Verify the change
                new_value = settings_service.get_setting(path)

                result_text = f"Successfully updated setting '{path}'"
                if action == 'set':
                    result_text += (
                        f'\nOld value: {old_value!r}\nNew value: {new_value!r}'
                    )
                elif action == 'append':
                    result_text += (
                        f'\nAppended: {value!r}\nCurrent value: {new_value!r}'
                    )
                elif action == 'remove':
                    result_text += f'\nRemoved: {value!r}\nCurrent value: {new_value!r}'

                # Advisory check for model settings (never blocks)
                if path in self.MODEL_SETTING_PATHS and isinstance(value, str):
                    warning = await self._check_model_availability(value)
                    if warning:
                        result_text += f'\n\n⚠️  {warning}'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': result_text}]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': f"Failed to update setting '{path}'"}
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class ValidateSettingsMCPTool(NoInputTool):
    """Validate current settings against schema."""

    @property
    def name(self) -> str:
        return 'validate_settings'

    @property
    def description(self) -> str:
        return 'Validate current Thoth settings against the JSON schema to check for errors or issues.'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Validate settings."""
        try:
            settings_service = SettingsService()
            settings = settings_service.load_settings()

            is_valid, errors = settings_service.validate_settings(settings)

            if is_valid:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Settings validation passed! All settings are valid according to the schema.',
                        }
                    ]
                )
            else:
                error_text = 'Settings validation failed:\n'
                for i, error in enumerate(errors, 1):
                    error_text += f'\n{i}. {error}'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': error_text}], isError=True
                )

        except Exception as e:
            return self.handle_error(e)


class MigrateSettingsMCPTool(NoInputTool):
    """Migrate current environment configuration to settings.json."""

    @property
    def name(self) -> str:
        return 'migrate_settings'

    @property
    def description(self) -> str:
        return (
            'Migrate current configuration from environment variables to thoth.settings.json format. '
            'This creates or updates the settings file with non-sensitive configuration values. '
            'API keys and secrets remain in .env file.'
        )

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Migrate settings from environment."""
        try:
            settings_service = SettingsService()

            # Perform migration
            migrated_settings = settings_service.migrate_from_env()

            # Save migrated settings
            success = settings_service.save_settings(migrated_settings)

            if success:
                # Count settings
                setting_count = len(settings_service.get_all_settings_paths())

                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': (
                                f'Successfully migrated configuration to thoth.settings.json!\n\n'
                                f'- {setting_count} settings migrated\n'
                                f'- API keys remain in .env file for security\n'
                                f'- Settings file: thoth.settings.json\n'
                                f'- Version: {migrated_settings.get("version", "1.0.0")}\n\n'
                                'You can now modify settings using the update_settings tool.'
                            ),
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Failed to save migrated settings'}
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class ResetSettingsMCPTool(MCPTool):
    """Reset settings to defaults."""

    @property
    def name(self) -> str:
        return 'reset_settings'

    @property
    def description(self) -> str:
        return (
            'Reset Thoth settings to defaults. Can reset all settings or a specific section. '
            'Creates a backup before resetting. API keys in .env are not affected.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'section': {
                    'type': 'string',
                    'description': "Optional section to reset (e.g., 'llm', 'rag', 'performance'). If not provided, resets all settings.",
                    'enum': [
                        'llm',
                        'rag',
                        'paths',
                        'servers',
                        'discovery',
                        'citation',
                        'performance',
                        'logging',
                        'memory',
                        'all',
                    ],
                },
                'confirm': {
                    'type': 'boolean',
                    'description': 'Confirmation required to reset settings',
                    'default': False,
                },
            },
            'required': ['confirm'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Reset settings."""
        if not arguments.get('confirm', False):
            return MCPToolCallResult(
                content=[
                    {
                        'type': 'text',
                        'text': "Reset cancelled. Set 'confirm' to true to reset settings.",
                    }
                ],
                isError=True,
            )

        section = arguments.get('section', 'all')

        try:
            settings_service = SettingsService()

            if section == 'all':
                # Load example settings as defaults
                import json
                from pathlib import Path

                example_path = Path('thoth.settings.example.json')
                if example_path.exists():
                    with open(example_path) as f:
                        default_settings = json.load(f)

                    success = settings_service.save_settings(default_settings)
                    if success:
                        return MCPToolCallResult(
                            content=[
                                {
                                    'type': 'text',
                                    'text': 'Successfully reset all settings to defaults. A backup was created.',
                                }
                            ]
                        )
            else:
                # Reset specific section
                current_settings = settings_service.load_settings()

                # Load defaults for the section
                example_path = Path('thoth.settings.example.json')
                if example_path.exists():
                    with open(example_path) as f:
                        default_settings = json.load(f)

                    if section in default_settings:
                        current_settings[section] = default_settings[section]
                        success = settings_service.save_settings(current_settings)
                        if success:
                            return MCPToolCallResult(
                                content=[
                                    {
                                        'type': 'text',
                                        'text': f"Successfully reset '{section}' settings to defaults. A backup was created.",
                                    }
                                ]
                            )
                    else:
                        return MCPToolCallResult(
                            content=[
                                {
                                    'type': 'text',
                                    'text': f"Section '{section}' not found in default settings",
                                }
                            ],
                            isError=True,
                        )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': 'Failed to reset settings'}],
                isError=True,
            )

        except Exception as e:
            return self.handle_error(e)

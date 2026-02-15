"""
MCP tools for managing analysis schemas.

Provides tools for listing, switching, and managing analysis schemas.
"""

import json
from typing import Any

from thoth.mcp.base_tools import MCPTool
from thoth.mcp.protocol import MCPToolCallResult


class GetSchemaInfoTool(MCPTool):
    """Get information about the current analysis schema."""

    @property
    def name(self) -> str:
        return 'get_schema_info'

    @property
    def description(self) -> str:
        return 'Get information about the currently active analysis schema including preset name, version, and available fields'

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {'type': 'object', 'properties': {}, 'required': []}

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            # Get schema service
            if not self.service_manager or not hasattr(
                self.service_manager, 'processing'
            ):
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Processing service not available'}
                    ],
                    isError=True,
                )

            schema_service = self.service_manager.processing.analysis_schema_service

            # Get current schema info
            preset_name = schema_service.get_active_preset_name()
            version = schema_service.get_schema_version()
            instructions = schema_service.get_preset_instructions()

            # Get model fields
            model = schema_service.get_active_model()
            fields = list(model.model_fields.keys())

            result_text = f"""**Schema Information**

**Preset Name:** {preset_name}
**Version:** {version}
**Instructions:** {instructions}
**Field Count:** {len(fields)}
**Fields:** {', '.join(fields)}
**Schema Path:** {schema_service.schema_path}"""

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            return self.handle_error(e)


class ListSchemaPresetsTool(MCPTool):
    """List all available analysis schema presets."""

    @property
    def name(self) -> str:
        return 'list_schema_presets'

    @property
    def description(self) -> str:
        return 'List all available analysis schema presets with their descriptions'

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {'type': 'object', 'properties': {}, 'required': []}

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            # Get schema service
            if not self.service_manager or not hasattr(
                self.service_manager, 'processing'
            ):
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Processing service not available'}
                    ],
                    isError=True,
                )

            schema_service = self.service_manager.processing.analysis_schema_service

            # Get available presets
            presets = schema_service.list_available_presets()
            active_preset = schema_service.get_active_preset_name()

            result_text = f"""**Available Schema Presets**

**Active Preset:** {active_preset}
**Total Presets:** {len(presets)}

**Presets:**
"""
            for preset in presets:
                marker = '→ ' if preset == active_preset else '  '
                result_text += f'{marker}{preset}\n'

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            return self.handle_error(e)


class SetSchemaPresetTool(MCPTool):
    """Switch to a different analysis schema preset."""

    @property
    def name(self) -> str:
        return 'set_schema_preset'

    @property
    def description(self) -> str:
        return "Switch the active analysis schema preset (e.g., 'standard', 'detailed', 'minimal')"

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            'type': 'object',
            'properties': {
                'preset': {
                    'type': 'string',
                    'description': "The preset name to activate (e.g., 'standard', 'detailed', 'minimal', 'custom')",
                }
            },
            'required': ['preset'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            preset = arguments.get('preset')
            if not preset:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': "Error: 'preset' argument is required"}
                    ],
                    isError=True,
                )

            # Get schema service
            if not self.service_manager or not hasattr(
                self.service_manager, 'processing'
            ):
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Processing service not available'}
                    ],
                    isError=True,
                )

            schema_service = self.service_manager.processing.analysis_schema_service

            # Load current schema
            schema_config = schema_service.load_schema()

            # Check if preset exists
            if preset not in schema_config['presets']:
                available = list(schema_config['presets'].keys())
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Preset '{preset}' not found. Available presets: {', '.join(available)}",
                        }
                    ],
                    isError=True,
                )

            # Update active preset
            schema_config['active_preset'] = preset

            # Save back to file
            schema_path = schema_service.schema_path
            with open(schema_path, 'w', encoding='utf-8') as f:
                json.dump(schema_config, f, indent=2, ensure_ascii=False)

            # Reload schema
            schema_service.load_schema(force_reload=True)

            # Get new preset info
            new_model = schema_service.get_active_model()
            field_count = len(new_model.model_fields)
            instructions = schema_service.get_preset_instructions()

            result_text = f"""**Schema Preset Changed**

✓ Switched to '{preset}' preset
**Field Count:** {field_count}
**Instructions:** {instructions}"""

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            return self.handle_error(e)


class GetPresetDetailsTool(MCPTool):
    """Get detailed information about a specific preset."""

    @property
    def name(self) -> str:
        return 'get_preset_details'

    @property
    def description(self) -> str:
        return 'Get detailed information about a specific analysis schema preset including all fields and their specifications'

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            'type': 'object',
            'properties': {
                'preset': {
                    'type': 'string',
                    'description': "The preset name to get details for (e.g., 'standard', 'detailed', 'minimal')",
                }
            },
            'required': ['preset'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            preset = arguments.get('preset')
            if not preset:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': "Error: 'preset' argument is required"}
                    ],
                    isError=True,
                )

            # Get schema service
            if not self.service_manager or not hasattr(
                self.service_manager, 'processing'
            ):
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Processing service not available'}
                    ],
                    isError=True,
                )

            schema_service = self.service_manager.processing.analysis_schema_service

            # Load schema
            schema_config = schema_service.load_schema()

            # Check if preset exists
            if preset not in schema_config['presets']:
                available = list(schema_config['presets'].keys())
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Preset '{preset}' not found. Available presets: {', '.join(available)}",
                        }
                    ],
                    isError=True,
                )

            preset_config = schema_config['presets'][preset]

            # Extract field details
            result_text = f"""**Preset Details: {preset}**

**Name:** {preset_config.get('name', preset)}
**Description:** {preset_config.get('description', '')}
**Instructions:** {preset_config.get('instructions', '')}

**Fields:**
"""
            for field_name, field_spec in preset_config.get('fields', {}).items():
                field_type = field_spec.get('type', 'string')
                required = (
                    'required' if field_spec.get('required', False) else 'optional'
                )
                description = field_spec.get('description', '')
                result_text += (
                    f'  - **{field_name}** ({field_type}, {required}): {description}\n'
                )

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            return self.handle_error(e)


class ValidateSchemaFileTool(MCPTool):
    """Validate the analysis schema configuration file."""

    @property
    def name(self) -> str:
        return 'validate_schema_file'

    @property
    def description(self) -> str:
        return 'Validate the analysis schema configuration file for syntax and structure errors'

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {'type': 'object', 'properties': {}, 'required': []}

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            # Get schema service
            if not self.service_manager or not hasattr(
                self.service_manager, 'processing'
            ):
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Processing service not available'}
                    ],
                    isError=True,
                )

            schema_service = self.service_manager.processing.analysis_schema_service
            schema_path = schema_service.schema_path

            # Check file exists
            if not schema_path.exists():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Schema file not found: {schema_path}',
                        }
                    ],
                    isError=True,
                )

            # Try to load and validate
            try:
                with open(schema_path, encoding='utf-8') as f:
                    schema_config = json.load(f)

                # Validate structure
                schema_service._validate_schema_config(schema_config)

                # Get validation details
                version = schema_config.get('version', 'unknown')
                active_preset = schema_config.get('active_preset', 'unknown')
                preset_count = len(schema_config.get('presets', {}))

                result_text = f"""**Schema Validation: PASSED**

✓ Schema file is valid
**Schema Path:** {schema_path}
**Version:** {version}
**Active Preset:** {active_preset}
**Preset Count:** {preset_count}"""

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': result_text}]
                )

            except json.JSONDecodeError as e:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': f'Invalid JSON in schema file: {e}'}
                    ],
                    isError=True,
                )
            except Exception as e:
                return self.handle_error(e)

        except Exception as e:
            return self.handle_error(e)


class UpdateSchemaFieldTool(MCPTool):
    """Add, update, or remove a field in an analysis schema preset."""

    @property
    def name(self) -> str:
        return 'update_schema_field'

    @property
    def description(self) -> str:
        return 'Add, update, or remove a field in an analysis schema preset. Use this to customize what information is extracted from papers.'

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            'type': 'object',
            'properties': {
                'preset': {
                    'type': 'string',
                    'description': "The preset name to modify (e.g., 'standard', 'detailed', 'custom')",
                },
                'field_name': {
                    'type': 'string',
                    'description': 'The field name to add/update/remove (e.g., "funding_sources")',
                },
                'field_spec': {
                    'type': 'object',
                    'description': 'Field specification with type, required, description. Omit to remove field.',
                    'properties': {
                        'type': {
                            'type': 'string',
                            'description': 'Field type: string, integer, array, etc.',
                        },
                        'required': {
                            'type': 'boolean',
                            'description': 'Whether this field is required',
                        },
                        'description': {
                            'type': 'string',
                            'description': 'Description of what this field should contain',
                        },
                        'items': {
                            'type': 'string',
                            'description': 'For array types, the type of items (e.g., "string")',
                        },
                    },
                },
                'remove': {
                    'type': 'boolean',
                    'description': 'Set to true to remove the field from the preset',
                },
            },
            'required': ['preset', 'field_name'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            preset = arguments.get('preset')
            field_name = arguments.get('field_name')
            field_spec = arguments.get('field_spec')
            remove = arguments.get('remove', False)

            if not preset or not field_name:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': "Error: 'preset' and 'field_name' are required",
                        }
                    ],
                    isError=True,
                )

            # Get schema service
            if not self.service_manager or not hasattr(
                self.service_manager, 'processing'
            ):
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Processing service not available'}
                    ],
                    isError=True,
                )

            schema_service = self.service_manager.processing.analysis_schema_service
            schema_path = schema_service.schema_path

            # Load current schema
            schema_config = schema_service.load_schema()

            # Check preset exists
            if preset not in schema_config['presets']:
                available = list(schema_config['presets'].keys())
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Preset '{preset}' not found. Available: {', '.join(available)}",
                        }
                    ],
                    isError=True,
                )

            # Create backup
            import shutil

            backup_path = schema_path.with_suffix('.json.bak')
            shutil.copy(schema_path, backup_path)

            # Modify the preset
            preset_config = schema_config['presets'][preset]

            if remove:
                # Remove field
                if field_name in preset_config.get('fields', {}):
                    del preset_config['fields'][field_name]
                    action = f"Removed field '{field_name}'"
                else:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f"Field '{field_name}' not found in preset '{preset}'",
                            }
                        ],
                        isError=True,
                    )
            else:
                # Add or update field
                if not field_spec:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': "Error: 'field_spec' required when not removing field",
                            }
                        ],
                        isError=True,
                    )

                if 'fields' not in preset_config:
                    preset_config['fields'] = {}

                was_new = field_name not in preset_config['fields']
                preset_config['fields'][field_name] = field_spec
                action = f"{'Added' if was_new else 'Updated'} field '{field_name}'"

            # Validate modified schema
            try:
                schema_service._validate_schema_config(schema_config)
            except Exception as e:
                # Restore from backup
                shutil.copy(backup_path, schema_path)
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Schema validation failed: {e}\nChanges rolled back.',
                        }
                    ],
                    isError=True,
                )

            # Save modified schema
            with open(schema_path, 'w', encoding='utf-8') as f:
                json.dump(schema_config, f, indent=2, ensure_ascii=False)

            # Reload schema
            schema_service.load_schema(force_reload=True)

            result_text = f"""**Schema Field Updated**

✓ {action} in preset '{preset}'
**Backup saved:** {backup_path.name}
**Changes take effect:** Next analysis run

Current fields in '{preset}': {len(preset_config.get('fields', {}))}"""

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            return self.handle_error(e)


class UpdateSchemaInstructionsTool(MCPTool):
    """Update the extraction instructions for an analysis schema preset."""

    @property
    def name(self) -> str:
        return 'update_schema_instructions'

    @property
    def description(self) -> str:
        return 'Update the extraction instructions for an analysis schema preset. Instructions guide the LLM on how to extract information from papers.'

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            'type': 'object',
            'properties': {
                'preset': {
                    'type': 'string',
                    'description': "The preset name to modify (e.g., 'standard', 'detailed', 'custom')",
                },
                'instructions': {
                    'type': 'string',
                    'description': 'The new extraction instructions for the LLM',
                },
            },
            'required': ['preset', 'instructions'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            preset = arguments.get('preset')
            instructions = arguments.get('instructions')

            if not preset or instructions is None:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': "Error: 'preset' and 'instructions' are required",
                        }
                    ],
                    isError=True,
                )

            # Get schema service
            if not self.service_manager or not hasattr(
                self.service_manager, 'processing'
            ):
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Processing service not available'}
                    ],
                    isError=True,
                )

            schema_service = self.service_manager.processing.analysis_schema_service
            schema_path = schema_service.schema_path

            # Load current schema
            schema_config = schema_service.load_schema()

            # Check preset exists
            if preset not in schema_config['presets']:
                available = list(schema_config['presets'].keys())
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Preset '{preset}' not found. Available: {', '.join(available)}",
                        }
                    ],
                    isError=True,
                )

            # Create backup
            import shutil

            backup_path = schema_path.with_suffix('.json.bak')
            shutil.copy(schema_path, backup_path)

            # Update instructions
            schema_config['presets'][preset]['instructions'] = instructions

            # Validate modified schema
            try:
                schema_service._validate_schema_config(schema_config)
            except Exception as e:
                # Restore from backup
                shutil.copy(backup_path, schema_path)
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Schema validation failed: {e}\nChanges rolled back.',
                        }
                    ],
                    isError=True,
                )

            # Save modified schema
            with open(schema_path, 'w', encoding='utf-8') as f:
                json.dump(schema_config, f, indent=2, ensure_ascii=False)

            # Reload schema
            schema_service.load_schema(force_reload=True)

            result_text = f"""**Schema Instructions Updated**

✓ Updated extraction instructions for preset '{preset}'
**Backup saved:** {backup_path.name}
**Changes take effect:** Next analysis run

**New instructions:** {instructions[:200]}{'...' if len(instructions) > 200 else ''}"""

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            return self.handle_error(e)


class ResetSchemaToDefaultTool(MCPTool):
    """Reset analysis schema to default template from repository."""

    @property
    def name(self) -> str:
        return 'reset_schema_to_default'

    @property
    def description(self) -> str:
        return 'Reset analysis schema (or a specific preset) to the default template from the repository. Use this to recover from bad edits.'

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            'type': 'object',
            'properties': {
                'preset': {
                    'type': 'string',
                    'description': "Optional: Reset only this preset (e.g., 'custom'). Omit to reset entire schema file.",
                },
                'confirm': {
                    'type': 'boolean',
                    'description': 'Must be true to confirm reset (prevents accidents)',
                },
            },
            'required': ['confirm'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            preset = arguments.get('preset')
            confirm = arguments.get('confirm', False)

            if not confirm:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': "Error: Must set 'confirm: true' to reset schema",
                        }
                    ],
                    isError=True,
                )

            # Get schema service
            if not self.service_manager or not hasattr(
                self.service_manager, 'processing'
            ):
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Processing service not available'}
                    ],
                    isError=True,
                )

            schema_service = self.service_manager.processing.analysis_schema_service
            schema_path = schema_service.schema_path

            # Find default template
            from pathlib import Path

            repo_root = Path(__file__).resolve().parents[3]
            template_path = repo_root / 'templates' / 'analysis_schema.json'

            if not template_path.exists():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Default template not found: {template_path}',
                        }
                    ],
                    isError=True,
                )

            # Load default template
            with open(template_path, encoding='utf-8') as f:
                default_config = json.load(f)

            if preset:
                # Reset only specific preset
                if preset not in default_config['presets']:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f"Preset '{preset}' not found in default template",
                            }
                        ],
                        isError=True,
                    )

                # Load current schema
                schema_config = schema_service.load_schema()

                # Create backup
                import shutil

                backup_path = schema_path.with_suffix('.json.bak')
                shutil.copy(schema_path, backup_path)

                # Replace preset
                schema_config['presets'][preset] = default_config['presets'][preset]

                # Save
                with open(schema_path, 'w', encoding='utf-8') as f:
                    json.dump(schema_config, f, indent=2, ensure_ascii=False)

                result = f"preset '{preset}'"
            else:
                # Reset entire file
                import shutil

                backup_path = schema_path.with_suffix('.json.bak')
                shutil.copy(schema_path, backup_path)

                # Copy default template
                shutil.copy(template_path, schema_path)

                result = 'entire schema file'

            # Reload schema
            schema_service.load_schema(force_reload=True)

            result_text = f"""**Schema Reset to Default**

✓ Reset {result} to repository defaults
**Backup saved:** {backup_path.name}
**Changes take effect:** Immediately

All custom modifications to {result} have been removed."""

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            return self.handle_error(e)


# Register tools
TOOLS = [
    GetSchemaInfoTool,
    ListSchemaPresetsTool,
    SetSchemaPresetTool,
    GetPresetDetailsTool,
    ValidateSchemaFileTool,
    UpdateSchemaFieldTool,
    UpdateSchemaInstructionsTool,
    ResetSchemaToDefaultTool,
]

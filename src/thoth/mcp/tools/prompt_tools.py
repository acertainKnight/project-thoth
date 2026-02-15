"""
MCP tools for managing prompt templates.

Provides tools for listing, reading, updating, and resetting Jinja2 prompt templates
used for LLM-based document analysis.
"""

import re
from pathlib import Path
from typing import Any

from thoth.mcp.base_tools import MCPTool
from thoth.mcp.protocol import MCPToolCallResult


class ListPromptTemplatesMCPTool(MCPTool):
    """List all available prompt templates with custom/default status."""

    @property
    def name(self) -> str:
        return 'list_prompt_templates'

    @property
    def description(self) -> str:
        return 'List all available prompt templates, showing which are custom (vault) vs default (repo), organized by provider'

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            'type': 'object',
            'properties': {
                'provider': {
                    'type': 'string',
                    'description': "Optional: Filter by provider (e.g., 'google', 'openai', 'default', 'agent')",
                }
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            provider_filter = arguments.get('provider')

            # Get config for paths
            if not self.service_manager or not hasattr(self.service_manager, 'config'):
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Config not available'}],
                    isError=True,
                )

            config = self.service_manager.config

            # Custom prompts directory (vault)
            custom_dir = Path(config.prompts_dir)

            # Default prompts directory (repo)
            repo_root = Path(__file__).resolve().parents[3]
            default_dir = repo_root / 'templates' / 'prompts'

            if not default_dir.exists():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Default prompts directory not found: {default_dir}',
                        }
                    ],
                    isError=True,
                )

            # Scan for templates
            templates_by_provider: dict[str, list[dict[str, Any]]] = {}

            # Scan default templates
            for provider_dir in default_dir.iterdir():
                if not provider_dir.is_dir():
                    continue

                provider_name = provider_dir.name
                if provider_filter and provider_name != provider_filter:
                    continue

                if provider_name not in templates_by_provider:
                    templates_by_provider[provider_name] = []

                for template_file in provider_dir.glob('*.j2'):
                    template_name = template_file.name

                    # Check if custom override exists
                    custom_path = custom_dir / provider_name / template_name
                    has_custom = custom_path.exists()

                    templates_by_provider[provider_name].append(
                        {
                            'name': template_name,
                            'has_custom': has_custom,
                            'default_path': str(template_file),
                            'custom_path': str(custom_path) if has_custom else None,
                        }
                    )

            # Check for custom-only templates (not in defaults)
            if custom_dir.exists():
                for provider_dir in custom_dir.iterdir():
                    if not provider_dir.is_dir():
                        continue

                    provider_name = provider_dir.name
                    if provider_filter and provider_name != provider_filter:
                        continue

                    if provider_name not in templates_by_provider:
                        templates_by_provider[provider_name] = []

                    for template_file in provider_dir.glob('*.j2'):
                        template_name = template_file.name

                        # Check if already in list (from defaults scan)
                        existing = any(
                            t['name'] == template_name
                            for t in templates_by_provider[provider_name]
                        )

                        if not existing:
                            # Custom-only template
                            templates_by_provider[provider_name].append(
                                {
                                    'name': template_name,
                                    'has_custom': True,
                                    'default_path': None,
                                    'custom_path': str(template_file),
                                }
                            )

            # Build result text
            result_text = '**Prompt Templates**\n\n'

            if not templates_by_provider:
                result_text += 'No templates found.\n'
            else:
                for provider_name in sorted(templates_by_provider.keys()):
                    templates = templates_by_provider[provider_name]
                    result_text += f'**Provider: {provider_name}** ({len(templates)} templates)\n\n'

                    for template in sorted(templates, key=lambda t: t['name']):
                        status = '✓ Custom' if template['has_custom'] else '  Default'
                        result_text += f'{status} `{template["name"]}`\n'

                    result_text += '\n'

            result_text += f'\n**Custom prompts directory:** {custom_dir}'
            result_text += f'\n**Default prompts directory:** {default_dir}'

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            return self.handle_error(e)


class ReadPromptTemplateMCPTool(MCPTool):
    """Read the contents of a specific prompt template."""

    @property
    def name(self) -> str:
        return 'read_prompt_template'

    @property
    def description(self) -> str:
        return 'Read the contents of a specific prompt template. Reads custom version if it exists, otherwise reads default.'

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            'type': 'object',
            'properties': {
                'template_name': {
                    'type': 'string',
                    'description': 'Template filename (e.g., "analyze_content.j2")',
                },
                'provider': {
                    'type': 'string',
                    'description': 'Provider name (e.g., "google", "openai", "default", "agent")',
                },
            },
            'required': ['template_name', 'provider'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            template_name = arguments.get('template_name')
            provider = arguments.get('provider')

            if not template_name or not provider:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': "Error: 'template_name' and 'provider' are required",
                        }
                    ],
                    isError=True,
                )

            # Get config for paths
            if not self.service_manager or not hasattr(self.service_manager, 'config'):
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Config not available'}],
                    isError=True,
                )

            config = self.service_manager.config

            # Custom prompts directory (vault)
            custom_path = Path(config.prompts_dir) / provider / template_name

            # Default prompts directory (repo)
            repo_root = Path(__file__).resolve().parents[3]
            default_path = (
                repo_root / 'templates' / 'prompts' / provider / template_name
            )

            # Check which exists and read
            if custom_path.exists():
                template_path = custom_path
                source = 'custom (vault)'
            elif default_path.exists():
                template_path = default_path
                source = 'default (repo)'
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Template not found: {template_name} for provider '{provider}'",
                        }
                    ],
                    isError=True,
                )

            # Read template content
            with open(template_path, encoding='utf-8') as f:
                content = f.read()

            result_text = f"""**Prompt Template: {template_name}**

**Provider:** {provider}
**Source:** {source}
**Path:** {template_path}
**Size:** {len(content)} characters

**Content:**
```
{content}
```"""

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            return self.handle_error(e)


class UpdatePromptTemplateMCPTool(MCPTool):
    """Update a prompt template in the custom prompts directory."""

    @property
    def name(self) -> str:
        return 'update_prompt_template'

    @property
    def description(self) -> str:
        return 'Update a prompt template in the vault custom prompts directory. Creates provider directory if needed. Changes are hot-reloaded automatically.'

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            'type': 'object',
            'properties': {
                'template_name': {
                    'type': 'string',
                    'description': 'Template filename (e.g., "analyze_content.j2")',
                },
                'provider': {
                    'type': 'string',
                    'description': 'Provider name (e.g., "google", "openai", "default", "agent")',
                },
                'content': {
                    'type': 'string',
                    'description': 'New template content (Jinja2 format)',
                },
            },
            'required': ['template_name', 'provider', 'content'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            template_name = arguments.get('template_name')
            provider = arguments.get('provider')
            content = arguments.get('content')

            if not template_name or not provider or content is None:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': "Error: 'template_name', 'provider', and 'content' are required",
                        }
                    ],
                    isError=True,
                )

            # Get config for paths
            if not self.service_manager or not hasattr(self.service_manager, 'config'):
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Config not available'}],
                    isError=True,
                )

            config = self.service_manager.config

            # Custom prompts directory (vault)
            custom_dir = Path(config.prompts_dir) / provider
            custom_path = custom_dir / template_name

            # Validate Jinja2 content based on template type
            validation_warnings = []

            # Analysis templates should have certain variables
            if 'analyze' in template_name or 'reduce' in template_name:
                if '{{ content }}' not in content and '{{ chunk' not in content:
                    validation_warnings.append(
                        'Warning: Analysis template missing {{ content }} or {{ chunk }} variable'
                    )
                if '{{ analysis_schema }}' not in content:
                    validation_warnings.append(
                        'Warning: Analysis template missing {{ analysis_schema }} variable'
                    )

            # Check for basic Jinja2 syntax
            if not re.search(r'\{\{.*?\}\}', content):
                validation_warnings.append(
                    'Warning: No Jinja2 variables found ({{...}}). Is this intentional?'
                )

            # Create backup if file exists
            backup_path = None
            if custom_path.exists():
                import shutil

                backup_path = custom_path.with_suffix('.j2.bak')
                shutil.copy(custom_path, backup_path)

            # Ensure directory exists
            custom_dir.mkdir(parents=True, exist_ok=True)

            # Write new content
            with open(custom_path, 'w', encoding='utf-8') as f:
                f.write(content)

            result_text = f"""**Prompt Template Updated**

✓ Updated template: {template_name}
**Provider:** {provider}
**Path:** {custom_path}
**Size:** {len(content)} characters
{'**Backup saved:** ' + backup_path.name if backup_path else '**New file created**'}
**Changes take effect:** Immediately (hot-reloaded)
"""

            if validation_warnings:
                result_text += '\n**Validation Warnings:**\n'
                for warning in validation_warnings:
                    result_text += f'- {warning}\n'

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            return self.handle_error(e)


class ResetPromptTemplateMCPTool(MCPTool):
    """Delete custom prompt override, reverting to default."""

    @property
    def name(self) -> str:
        return 'reset_prompt_template'

    @property
    def description(self) -> str:
        return 'Delete a custom prompt template override from the vault, reverting to the default template from the repository'

    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            'type': 'object',
            'properties': {
                'template_name': {
                    'type': 'string',
                    'description': 'Template filename (e.g., "analyze_content.j2")',
                },
                'provider': {
                    'type': 'string',
                    'description': 'Provider name (e.g., "google", "openai", "default", "agent")',
                },
                'confirm': {
                    'type': 'boolean',
                    'description': 'Must be true to confirm deletion',
                },
            },
            'required': ['template_name', 'provider', 'confirm'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            template_name = arguments.get('template_name')
            provider = arguments.get('provider')
            confirm = arguments.get('confirm', False)

            if not template_name or not provider:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': "Error: 'template_name' and 'provider' are required",
                        }
                    ],
                    isError=True,
                )

            if not confirm:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': "Error: Must set 'confirm: true' to delete custom template",
                        }
                    ],
                    isError=True,
                )

            # Get config for paths
            if not self.service_manager or not hasattr(self.service_manager, 'config'):
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Config not available'}],
                    isError=True,
                )

            config = self.service_manager.config

            # Custom prompts directory (vault)
            custom_path = Path(config.prompts_dir) / provider / template_name

            # Check if custom file exists
            if not custom_path.exists():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Custom template not found: {custom_path}\n(Already using default)',
                        }
                    ],
                    isError=True,
                )

            # Check if default exists
            repo_root = Path(__file__).resolve().parents[3]
            default_path = (
                repo_root / 'templates' / 'prompts' / provider / template_name
            )

            has_default = default_path.exists()

            # Create backup before deletion
            import shutil

            backup_path = custom_path.with_suffix('.j2.bak')
            shutil.copy(custom_path, backup_path)

            # Delete custom file
            custom_path.unlink()

            result_text = f"""**Prompt Template Reset**

✓ Deleted custom template: {template_name}
**Provider:** {provider}
**Backup saved:** {backup_path}
**Now using:** {'Default template from repo' if has_default else 'No template (default was missing!)'}
**Changes take effect:** Immediately (hot-reloaded)
"""

            if not has_default:
                result_text += (
                    '\n⚠️ Warning: No default template exists. '
                    'You may need to restore from backup.'
                )

            return MCPToolCallResult(content=[{'type': 'text', 'text': result_text}])

        except Exception as e:
            return self.handle_error(e)


# Register tools
TOOLS = [
    ListPromptTemplatesMCPTool,
    ReadPromptTemplateMCPTool,
    UpdatePromptTemplateMCPTool,
    ResetPromptTemplateMCPTool,
]

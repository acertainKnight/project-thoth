"""
MCP tools for managing agent skills.

These tools allow agents to dynamically load and unload skills from bundled
and vault locations, enabling specialized knowledge and workflows for different tasks.
"""

from typing import Any

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult
from thoth.services.skill_service import SkillService


class ListSkillsMCPTool(MCPTool):
    """List all available skills from bundled and vault locations."""

    @property
    def name(self) -> str:
        return 'list_skills'

    @property
    def description(self) -> str:
        return (
            'List all available skills that can be loaded. Skills provide specialized '
            'knowledge and workflows for different research tasks. Returns skill IDs, '
            'names, descriptions, and sources (bundled or vault).'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'source_filter': {
                    'type': 'string',
                    'enum': ['all', 'bundled', 'vault'],
                    'description': 'Filter skills by source. Options: all (default), bundled (built-in), vault (custom user skills)',
                    'default': 'all',
                },
                'show_details': {
                    'type': 'boolean',
                    'description': 'If true, includes full descriptions. If false, shows compact list.',
                    'default': False,
                },
            },
            'required': [],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """List available skills."""
        try:
            skill_service = SkillService()
            skills = skill_service.discover_skills()

            if not skills:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'No skills found. Check skill directories.'}
                    ]
                )

            # Filter by source
            source_filter = arguments.get('source_filter', 'all')
            if source_filter != 'all':
                skills = {
                    k: v for k, v in skills.items() if v['source'] == source_filter
                }

            # Format output
            show_details = arguments.get('show_details', False)

            if show_details:
                # Detailed view with descriptions
                lines = [f"Found {len(skills)} available skills:\n"]
                for skill_id, skill_info in sorted(skills.items()):
                    source_label = '📦 bundled' if skill_info['source'] == 'bundled' else '📁 vault'
                    lines.append(f"### {skill_info['name']} ({source_label})")
                    lines.append(f"ID: `{skill_id}`")
                    lines.append(f"Description: {skill_info['description']}")
                    lines.append("")
            else:
                # Compact list view
                lines = [f"Available skills ({len(skills)} total):\n"]
                for skill_id, skill_info in sorted(skills.items()):
                    source_icon = '📦' if skill_info['source'] == 'bundled' else '📁'
                    lines.append(f"  {source_icon} {skill_id} - {skill_info['name']}")

                lines.append("\nUse show_details=true to see full descriptions.")
                lines.append("Use load_skill to load skills into your context.")

            return MCPToolCallResult(content=[{'type': 'text', 'text': '\n'.join(lines)}])

        except Exception as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error listing skills: {e!s}'}],
                isError=True,
            )


class LoadSkillMCPTool(MCPTool):
    """Load skills into agent context for use."""

    @property
    def name(self) -> str:
        return 'load_skill'

    @property
    def description(self) -> str:
        return (
            'Load one or more skills into your context. Skills provide specialized knowledge '
            'and workflows for different research tasks. Once loaded, you can use the guidance '
            'provided in the skill to help users more effectively. Use list_skills to see '
            'available skills first.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'skill_ids': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'List of skill IDs to load. Use list_skills to see available skill IDs.',
                    'minItems': 1,
                },
            },
            'required': ['skill_ids'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Load skills into context."""
        try:
            skill_service = SkillService()
            skill_ids = arguments.get('skill_ids', [])

            if not skill_ids:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: No skill IDs provided. Use list_skills to see available skills.',
                        }
                    ],
                    isError=True,
                )

            # Load each skill
            results = []
            loaded_count = 0
            failed_count = 0

            for skill_id in skill_ids:
                skill_content = skill_service.get_skill_content(skill_id)

                if skill_content is None:
                    results.append(f"❌ Failed to load '{skill_id}': Skill not found")
                    failed_count += 1
                else:
                    results.append(f"✅ Loaded '{skill_id}' successfully")
                    loaded_count += 1

                    # Add skill content to results
                    results.append(f"\n--- BEGIN SKILL: {skill_id} ---\n")
                    results.append(skill_content)
                    results.append(f"\n--- END SKILL: {skill_id} ---\n")

            # Summary
            summary = [
                f"\nSkill Loading Summary:",
                f"  ✅ Loaded: {loaded_count}",
                f"  ❌ Failed: {failed_count}",
            ]

            if failed_count > 0:
                summary.append("\nUse list_skills to see available skill IDs.")

            all_text = '\n'.join(results + summary)

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': all_text}],
                isError=(failed_count > 0 and loaded_count == 0),
            )

        except Exception as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error loading skills: {e!s}'}],
                isError=True,
            )


class UnloadSkillMCPTool(MCPTool):
    """Unload skills from agent context."""

    @property
    def name(self) -> str:
        return 'unload_skill'

    @property
    def description(self) -> str:
        return (
            'Unload one or more skills from your context to free up space. '
            'This removes the skill content from your working memory. '
            'Note: In the current implementation, skills are stateless - this tool '
            'is mainly for documentation purposes. Skills naturally leave context as '
            'conversation progresses.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'skill_ids': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'List of skill IDs to unload.',
                    'minItems': 1,
                },
            },
            'required': ['skill_ids'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Unload skills from context."""
        try:
            skill_ids = arguments.get('skill_ids', [])

            if not skill_ids:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Error: No skill IDs provided.'}
                    ],
                    isError=True,
                )

            # In current implementation, skills are stateless and exist only in message history
            # This tool acknowledges the unload request
            results = []
            for skill_id in skill_ids:
                results.append(f"✅ Acknowledged unload request for '{skill_id}'")

            results.append(
                "\nNote: Skills exist in conversation history and will naturally "
                "leave context as the conversation progresses. Consider this skill "
                "no longer active for your current workflow."
            )

            return MCPToolCallResult(content=[{'type': 'text', 'text': '\n'.join(results)}])

        except Exception as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error unloading skills: {e!s}'}],
                isError=True,
            )

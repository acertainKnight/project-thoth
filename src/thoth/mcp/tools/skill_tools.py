"""
MCP tools for managing agent skills with dynamic tool attachment.

These tools allow agents to dynamically load and unload skills from bundled
and vault locations. When a skill is loaded, the tools required by that skill
are automatically attached to the calling agent via the Letta API.
"""

from typing import Any

from loguru import logger

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult
from thoth.services.letta_service import LettaService
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
                    'enum': ['all', 'bundled', 'vault', 'bundle'],
                    'description': 'Filter skills by source. Options: all (default), bundled (built-in), vault (custom user skills), bundle (role-based bundles)',
                    'default': 'all',
                },
                'role_filter': {
                    'type': 'string',
                    'enum': [
                        'orchestrator',
                        'discovery',
                        'document',
                        'citation',
                        'analyst',
                        'curator',
                        'maintenance',
                    ],
                    'description': 'Filter skills by agent role. Shows skills available for that role including bundles.',
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

            # Get role filter if specified
            role_filter = arguments.get('role_filter')

            if role_filter:
                # Get skills for specific role (includes bundles)
                skill_ids = skill_service.get_skills_for_role(role_filter)
                skills = {}

                # Get metadata for each skill
                all_skills = skill_service.discover_skills()
                bundles = skill_service.discover_bundle_skills()

                for skill_id in skill_ids:
                    if skill_id.startswith('bundles/'):
                        # Bundle skill
                        parts = skill_id.split('/')
                        bundle_name = parts[1]
                        skill_name = parts[2]
                        skill_path = (
                            skill_service.bundles_dir
                            / bundle_name
                            / skill_name
                            / 'SKILL.md'
                        )

                        if skill_path.exists():
                            metadata = skill_service._parse_skill_metadata(skill_path)
                            skills[skill_id] = {
                                'name': metadata.get('name', skill_name),
                                'description': metadata.get('description', ''),
                                'source': 'bundle',
                                'bundle': bundle_name,
                            }
                    elif skill_id in all_skills:
                        skills[skill_id] = all_skills[skill_id]
            else:
                # Get all skills
                skills = skill_service.discover_skills()

                # Filter by source
                source_filter = arguments.get('source_filter', 'all')
                if source_filter != 'all':
                    skills = {
                        k: v for k, v in skills.items() if v['source'] == source_filter
                    }

            if not skills:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'No skills found. Check skill directories.',
                        }
                    ]
                )

            # Format output
            show_details = arguments.get('show_details', False)

            if show_details:
                # Detailed view with descriptions
                lines = [f'Found {len(skills)} available skills:\n']
                for skill_id, skill_info in sorted(skills.items()):
                    if skill_info.get('source') == 'bundle':
                        source_label = f'🎯 bundle ({skill_info.get("bundle")})'
                    elif skill_info['source'] == 'bundled':
                        source_label = '📦 bundled'
                    else:
                        source_label = '📁 vault'

                    lines.append(f'### {skill_info["name"]} ({source_label})')
                    lines.append(f'ID: `{skill_id}`')
                    lines.append(f'Description: {skill_info["description"]}')
                    lines.append('')
            else:
                # Compact list view
                lines = [f'Available skills ({len(skills)} total):\n']
                for skill_id, skill_info in sorted(skills.items()):
                    if skill_info.get('source') == 'bundle':
                        source_icon = '🎯'
                    elif skill_info['source'] == 'bundled':
                        source_icon = '📦'
                    else:
                        source_icon = '📁'
                    lines.append(f'  {source_icon} {skill_id} - {skill_info["name"]}')

                lines.append('\nUse show_details=true to see full descriptions.')
                lines.append(
                    "Use role_filter='role' to see skills for a specific agent role."
                )
                lines.append('Use load_skill to load skills into your context.')

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(lines)}]
            )

        except Exception as e:
            return self.handle_error(e)


class LoadSkillMCPTool(MCPTool):
    """Load skills into agent context and attach required tools."""

    @property
    def name(self) -> str:
        return 'load_skill'

    @property
    def description(self) -> str:
        return (
            'Load one or more skills into your context and attach the required tools. '
            'Skills provide specialized knowledge and workflows for different research tasks. '
            'When loaded, the tools needed for that skill are automatically attached to you. '
            'IMPORTANT: Pass your agent_id so the required tools can be attached to you.'
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
                'agent_id': {
                    'type': 'string',
                    'description': 'Your agent ID (required for tool attachment). You can find this in your persona memory block.',
                },
            },
            'required': ['skill_ids'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Load skills into context and attach required tools."""
        try:
            skill_service = SkillService()
            letta_service = LettaService()

            skill_ids = arguments.get('skill_ids', [])
            agent_id = arguments.get('agent_id')

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
            all_tools_to_attach = []

            for skill_id in skill_ids:
                skill_content = skill_service.get_skill_content(skill_id)

                if skill_content is None:
                    results.append(f"❌ Failed to load '{skill_id}': Skill not found")
                    failed_count += 1
                else:
                    # Get required tools for this skill
                    required_tools = skill_service.get_skill_tools(skill_id)
                    all_tools_to_attach.extend(required_tools)

                    results.append(f"✅ Loaded '{skill_id}' successfully")
                    if required_tools:
                        results.append(
                            f'   Required tools: {", ".join(required_tools)}'
                        )
                    loaded_count += 1

                    # Add skill content to results
                    results.append(f'\n--- BEGIN SKILL: {skill_id} ---\n')
                    results.append(skill_content)
                    results.append(f'\n--- END SKILL: {skill_id} ---\n')

            # Attach tools to agent if agent_id provided
            tool_attachment_result = None
            if agent_id and all_tools_to_attach:
                # Remove duplicates while preserving order
                unique_tools = list(dict.fromkeys(all_tools_to_attach))

                logger.info(
                    f'Attaching {len(unique_tools)} tools to agent {agent_id[:8]}...'
                )
                tool_attachment_result = letta_service.attach_tools_to_agent(
                    agent_id=agent_id, tool_names=unique_tools
                )

                results.append('\n--- TOOL ATTACHMENT ---')
                if tool_attachment_result['attached']:
                    results.append(
                        f'🔧 Attached: {", ".join(tool_attachment_result["attached"])}'
                    )
                if tool_attachment_result['already_attached']:
                    results.append(
                        f'✓ Already had: {", ".join(tool_attachment_result["already_attached"])}'
                    )
                if tool_attachment_result['not_found']:
                    results.append(
                        f'⚠ Not found: {", ".join(tool_attachment_result["not_found"])}'
                    )
                    logger.warning(
                        f'Tools not found in Letta: {tool_attachment_result["not_found"]}'
                    )
                results.append('--- END TOOL ATTACHMENT ---\n')
            elif all_tools_to_attach and not agent_id:
                results.append(
                    '\n⚠ Note: agent_id not provided. Tools could not be auto-attached.'
                )
                results.append(
                    '   To attach tools, call load_skill with your agent_id.'
                )
                results.append(
                    f'   Required tools: {", ".join(set(all_tools_to_attach))}'
                )

            # Summary
            summary = [
                '\nSkill Loading Summary:',
                f'  ✅ Skills loaded: {loaded_count}',
                f'  ❌ Skills failed: {failed_count}',
            ]

            if tool_attachment_result:
                total_attached = len(tool_attachment_result['attached']) + len(
                    tool_attachment_result['already_attached']
                )
                summary.append(f'  🔧 Tools available: {total_attached}')

            if failed_count > 0:
                summary.append('\nUse list_skills to see available skill IDs.')

            all_text = '\n'.join(results + summary)

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': all_text}],
                isError=(failed_count > 0 and loaded_count == 0),
            )

        except Exception as e:
            logger.error(f'Error loading skills: {e}')
            return self.handle_error(e)


class UnloadSkillMCPTool(MCPTool):
    """Unload skills from agent context and optionally detach tools."""

    @property
    def name(self) -> str:
        return 'unload_skill'

    @property
    def description(self) -> str:
        return (
            'Unload one or more skills from your context. '
            'Optionally detach the tools that were attached when the skill was loaded. '
            'Pass your agent_id and set detach_tools=true to remove skill-specific tools.'
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
                'agent_id': {
                    'type': 'string',
                    'description': 'Your agent ID (required for tool detachment).',
                },
                'detach_tools': {
                    'type': 'boolean',
                    'description': 'If true, detach tools that were attached with this skill. Default: false (keep tools).',
                    'default': False,
                },
            },
            'required': ['skill_ids'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Unload skills from context and optionally detach tools."""
        try:
            skill_service = SkillService()
            letta_service = LettaService()

            skill_ids = arguments.get('skill_ids', [])
            agent_id = arguments.get('agent_id')
            detach_tools = arguments.get('detach_tools', False)

            if not skill_ids:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Error: No skill IDs provided.'}],
                    isError=True,
                )

            results = []
            all_tools_to_detach = []

            for skill_id in skill_ids:
                results.append(f"✅ Unloaded '{skill_id}'")

                # Get tools associated with this skill
                if detach_tools:
                    required_tools = skill_service.get_skill_tools(skill_id)
                    all_tools_to_detach.extend(required_tools)

            # Detach tools if requested
            if detach_tools and agent_id and all_tools_to_detach:
                unique_tools = list(dict.fromkeys(all_tools_to_detach))

                logger.info(
                    f'Detaching {len(unique_tools)} tools from agent {agent_id[:8]}...'
                )
                detach_result = letta_service.detach_tools_from_agent(
                    agent_id=agent_id, tool_names=unique_tools
                )

                results.append('\n--- TOOL DETACHMENT ---')
                if detach_result['detached']:
                    results.append(
                        f'🔧 Detached: {", ".join(detach_result["detached"])}'
                    )
                if detach_result['not_attached']:
                    results.append(
                        f'✓ Already removed: {", ".join(detach_result["not_attached"])}'
                    )
                results.append('--- END TOOL DETACHMENT ---')
            elif detach_tools and not agent_id:
                results.append(
                    '\n⚠ Note: agent_id not provided. Tools could not be detached.'
                )
            else:
                results.append(
                    '\nNote: Tools remain attached. Use detach_tools=true to remove skill tools.'
                )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(results)}]
            )

        except Exception as e:
            logger.error(f'Error unloading skills: {e}')
            return self.handle_error(e)

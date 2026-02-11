"""
MCP tools for managing agent skills with dynamic tool attachment.

These tools allow agents to dynamically load and unload skills from bundled
and vault locations. When a skill is loaded, the tools required by that skill
are automatically attached to the calling agent via the Letta API.

SKILL LOADING BEHAVIOR:
- Only ONE skill can be loaded at a time per agent
- When load_skill is called:
  1. The skill content and tools are loaded
  2. load_skill tool is REMOVED from the agent
  3. unload_skill tool is ADDED to the agent
- When unload_skill is called:
  1. The skill is unloaded and tools are detached
  2. unload_skill tool is REMOVED from the agent
  3. load_skill tool is ADDED back to the agent
"""

from typing import Any

from loguru import logger

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult
from thoth.services.letta_service import LettaService
from thoth.services.skill_service import SkillService

# Global registry to track which agents have skills loaded
# Key: agent_id, Value: list of loaded skill_ids
_AGENT_LOADED_SKILLS: dict[str, list[str]] = {}


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
                            name = metadata.get('name', skill_name)
                            display_name = name.replace('-', ' ').title()

                            skills[skill_id] = {
                                'name': name,  # AgentSkills.io: matches directory
                                'display_name': display_name,  # Human-readable
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
                        source_label = f'bundle ({skill_info.get("bundle")})'
                    elif skill_info['source'] == 'bundled':
                        source_label = 'bundled'
                    else:
                        source_label = 'vault'

                    display_name = skill_info.get('display_name', skill_info['name'])
                    lines.append(f'### {display_name} ({source_label})')
                    lines.append(f'ID: `{skill_id}`')
                    lines.append(f'Description: {skill_info["description"]}')
                    lines.append('')
            else:
                # Compact list view
                lines = [f'Available skills ({len(skills)} total):\n']
                for skill_id, skill_info in sorted(skills.items()):
                    if skill_info.get('source') == 'bundle':
                        source_icon = '[bundle]'
                    elif skill_info['source'] == 'bundled':
                        source_icon = '[bundled]'
                    else:
                        source_icon = '[vault]'
                    display_name = skill_info.get('display_name', skill_info['name'])
                    lines.append(f'  {source_icon} {skill_id} - {display_name}')

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
                    'description': 'Your agent ID (REQUIRED for tool attachment and tool swapping). You can find this in your persona memory block.',
                },
            },
            'required': ['skill_ids', 'agent_id'],
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

            # Check if agent_id is provided (required for tool swapping)
            if not agent_id:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: agent_id is required to load skills. Pass your agent_id to enable skill loading.',
                        }
                    ],
                    isError=True,
                )

            # Check if agent already has a skill loaded (only one at a time)
            if _AGENT_LOADED_SKILLS.get(agent_id):
                currently_loaded = ', '.join(_AGENT_LOADED_SKILLS[agent_id])
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Error: You already have skill(s) loaded: {currently_loaded}\n\n'
                            f'Only ONE skill can be loaded at a time. Please use unload_skill first to unload the current skill, then load a new one.',
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
                    results.append(f"Failed to load '{skill_id}': Skill not found")
                    failed_count += 1
                else:
                    # Get required tools for this skill
                    required_tools = skill_service.get_skill_tools(skill_id)
                    all_tools_to_attach.extend(required_tools)

                    results.append(f"Loaded '{skill_id}' successfully")
                    if required_tools:
                        results.append(
                            f'   Required tools: {", ".join(required_tools)}'
                        )
                    loaded_count += 1

                    # Add skill content to results
                    results.append(f'\n--- BEGIN SKILL: {skill_id} ---\n')
                    results.append(skill_content)
                    results.append(f'\n--- END SKILL: {skill_id} ---\n')

            # If all skills failed to load, return early
            if loaded_count == 0:
                summary = [
                    '\nSkill Loading Summary:',
                    f'  Skills failed: {failed_count}',
                    '\nUse list_skills to see available skill IDs.',
                ]
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': '\n'.join(results + summary)}],
                    isError=True,
                )

            # Attach skill tools to agent
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
                    f'Attached: {", ".join(tool_attachment_result["attached"])}'
                )
            if tool_attachment_result['already_attached']:
                results.append(
                    f'✓ Already had: {", ".join(tool_attachment_result["already_attached"])}'
                )
            if tool_attachment_result['not_found']:
                results.append(
                    f'Not found: {", ".join(tool_attachment_result["not_found"])}'
                )
                logger.warning(
                    f'Tools not found in Letta: {tool_attachment_result["not_found"]}'
                )
            results.append('--- END TOOL ATTACHMENT ---\n')

            # SWAP TOOLS: Remove load_skill, add unload_skill
            results.append('\n--- SKILL TOOL SWAP ---')
            logger.info(
                f'Swapping skill tools for agent {agent_id[:8]}: removing load_skill, adding unload_skill'
            )

            # Detach load_skill
            detach_result = letta_service.detach_tools_from_agent(
                agent_id=agent_id, tool_names=['load_skill']
            )
            if detach_result['detached']:
                results.append('✓ Removed load_skill tool')
                logger.info(f'Removed load_skill from agent {agent_id[:8]}')
            else:
                results.append(
                    'Failed to remove load_skill (may not have been attached)'
                )
                logger.warning(f'Failed to remove load_skill from agent {agent_id[:8]}')

            # Attach unload_skill
            attach_result = letta_service.attach_tools_to_agent(
                agent_id=agent_id, tool_names=['unload_skill']
            )
            if attach_result['attached'] or attach_result['already_attached']:
                results.append('✓ Added unload_skill tool')
                logger.info(f'Added unload_skill to agent {agent_id[:8]}')
            else:
                results.append('Failed to add unload_skill')
                logger.warning(f'Failed to add unload_skill to agent {agent_id[:8]}')

            results.append(
                '\nWhen you are done with this skill, use unload_skill to unload it and restore load_skill capability.'
            )
            results.append('--- END SKILL TOOL SWAP ---\n')

            # Track loaded skills for this agent
            if agent_id not in _AGENT_LOADED_SKILLS:
                _AGENT_LOADED_SKILLS[agent_id] = []
            _AGENT_LOADED_SKILLS[agent_id].extend(skill_ids[:loaded_count])
            logger.info(
                f'Agent {agent_id[:8]} now has skills loaded: {_AGENT_LOADED_SKILLS[agent_id]}'
            )

            # Summary
            summary = [
                '\nSkill Loading Summary:',
                f'  Skills loaded: {loaded_count}',
                f'  Skills failed: {failed_count}',
            ]

            total_attached = len(tool_attachment_result['attached']) + len(
                tool_attachment_result['already_attached']
            )
            summary.append(f'  Tools available: {total_attached}')

            if failed_count > 0:
                summary.append(
                    '\nNote: Some skills failed to load. Use list_skills to see available skill IDs.'
                )

            all_text = '\n'.join(results + summary)

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': all_text}],
                isError=False,
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
            'Unload one or more skills from your context and restore the load_skill capability. '
            'This detaches skill-specific tools and swaps back the load_skill tool. '
            'IMPORTANT: You must call this when you are done with a skill to be able to load new skills. '
            'Pass your agent_id to complete the unload process.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'skill_ids': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'List of skill IDs to unload. Must match the currently loaded skills.',
                    'minItems': 1,
                },
                'agent_id': {
                    'type': 'string',
                    'description': 'Your agent ID (REQUIRED for tool swapping back to load_skill).',
                },
            },
            'required': ['skill_ids', 'agent_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """
        Unload skills from context, detach tools, and restore load_skill.
        """
        try:
            skill_service = SkillService()
            letta_service = LettaService()

            skill_ids = arguments.get('skill_ids', [])
            agent_id = arguments.get('agent_id')

            if not skill_ids:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Error: No skill IDs provided.'}],
                    isError=True,
                )

            if not agent_id:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: agent_id is required to unload skills and restore load_skill capability.',
                        }
                    ],
                    isError=True,
                )

            # Check if this agent has any skills loaded
            if (
                agent_id not in _AGENT_LOADED_SKILLS
                or not _AGENT_LOADED_SKILLS[agent_id]
            ):
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'No skills are currently loaded for this agent. Nothing to unload.',
                        }
                    ],
                    isError=False,
                )

            # Verify the skill_ids match what's loaded
            currently_loaded = set(_AGENT_LOADED_SKILLS[agent_id])
            requested_unload = set(skill_ids)

            if not requested_unload.issubset(currently_loaded):
                unrecognized = requested_unload - currently_loaded
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Error: Skills {unrecognized} are not currently loaded.\n'
                            f'Currently loaded: {", ".join(currently_loaded)}\n'
                            f'Please unload only the skills that are currently loaded.',
                        }
                    ],
                    isError=True,
                )

            results = []
            all_tools_to_detach = []

            # Collect tools to detach from all skills being unloaded
            for skill_id in skill_ids:
                results.append(f"Unloading '{skill_id}'")
                required_tools = skill_service.get_skill_tools(skill_id)
                all_tools_to_detach.extend(required_tools)

            # Detach skill tools
            if all_tools_to_detach:
                unique_tools = list(dict.fromkeys(all_tools_to_detach))

                logger.info(
                    f'Detaching {len(unique_tools)} tools from agent {agent_id[:8]}...'
                )
                detach_result = letta_service.detach_tools_from_agent(
                    agent_id=agent_id, tool_names=unique_tools
                )

                results.append('\n--- TOOL DETACHMENT ---')
                if detach_result['detached']:
                    results.append(f'Detached: {", ".join(detach_result["detached"])}')
                if detach_result['not_attached']:
                    results.append(
                        f'✓ Already removed: {", ".join(detach_result["not_attached"])}'
                    )
                results.append('--- END TOOL DETACHMENT ---\n')

            # SWAP TOOLS: Remove unload_skill, add load_skill
            results.append('\n--- SKILL TOOL SWAP ---')
            logger.info(
                f'Swapping skill tools for agent {agent_id[:8]}: removing unload_skill, adding load_skill'
            )

            # Detach unload_skill
            detach_result = letta_service.detach_tools_from_agent(
                agent_id=agent_id, tool_names=['unload_skill']
            )
            if detach_result['detached']:
                results.append('✓ Removed unload_skill tool')
                logger.info(f'Removed unload_skill from agent {agent_id[:8]}')
            else:
                results.append(
                    'Failed to remove unload_skill (may not have been attached)'
                )
                logger.warning(
                    f'Failed to remove unload_skill from agent {agent_id[:8]}'
                )

            # Attach load_skill
            attach_result = letta_service.attach_tools_to_agent(
                agent_id=agent_id, tool_names=['load_skill']
            )
            if attach_result['attached'] or attach_result['already_attached']:
                results.append('✓ Added load_skill tool back')
                logger.info(f'Added load_skill back to agent {agent_id[:8]}')
            else:
                results.append('Failed to add load_skill back')
                logger.warning(f'Failed to add load_skill back to agent {agent_id[:8]}')

            results.append('\nYou can now use load_skill to load a new skill.')
            results.append('--- END SKILL TOOL SWAP ---\n')

            # Clear loaded skills for this agent
            for skill_id in skill_ids:
                if skill_id in _AGENT_LOADED_SKILLS[agent_id]:
                    _AGENT_LOADED_SKILLS[agent_id].remove(skill_id)

            if not _AGENT_LOADED_SKILLS[agent_id]:
                del _AGENT_LOADED_SKILLS[agent_id]
                logger.info(f'Agent {agent_id[:8]} has no skills loaded')
            else:
                logger.info(
                    f'Agent {agent_id[:8]} still has skills loaded: {_AGENT_LOADED_SKILLS[agent_id]}'
                )

            results.append(
                f'\nSuccessfully unloaded {len(skill_ids)} skill(s) and restored load_skill capability.'
            )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(results)}]
            )

        except Exception as e:
            logger.error(f'Error unloading skills: {e}')
            return self.handle_error(e)

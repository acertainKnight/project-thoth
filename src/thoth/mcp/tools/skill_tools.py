"""
MCP tools for managing agent skills with dynamic tool attachment.

These tools allow agents to dynamically load and unload skills from bundled
and vault locations. When a skill is loaded, the tools required by that skill
are automatically attached to the calling agent via the Letta API.

Skill state is persisted in PostgreSQL (agent_loaded_skills table) so it
survives MCP server restarts.

SKILL LOADING BEHAVIOR:
- Maximum 3 skills can be loaded per agent at a time
- When load_skill is called:
  1. The skill content and tools are loaded
  2. On first load (0 -> 1): unload_skill tool is attached
  3. On third load (2 -> 3): load_skill tool is detached
- When unload_skill is called:
  1. The skill is unloaded and tools are detached
  2. On unload from 3 to 2: load_skill tool is re-attached
  3. On unload from 1 to 0: unload_skill tool is detached
"""

from typing import Any

from loguru import logger

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult
from thoth.services.letta_service import LettaService
from thoth.services.skill_service import SkillService

MAX_LOADED_SKILLS = 3


# --- Database helpers for skill tracking ---


async def _get_loaded_skills(postgres, agent_id: str) -> list[str]:
    """Return skill IDs currently loaded for an agent."""
    rows = await postgres.fetch(
        'SELECT skill_id FROM agent_loaded_skills WHERE agent_id = $1 ORDER BY loaded_at',
        agent_id,
    )
    return [row['skill_id'] for row in rows]


async def _add_loaded_skill(postgres, agent_id: str, skill_id: str) -> None:
    """Record a newly loaded skill. Ignores duplicates."""
    await postgres.execute(
        'INSERT INTO agent_loaded_skills (agent_id, skill_id) VALUES ($1, $2) '
        'ON CONFLICT (agent_id, skill_id) DO NOTHING',
        agent_id,
        skill_id,
    )


async def _remove_loaded_skill(postgres, agent_id: str, skill_id: str) -> None:
    """Remove a skill from the loaded set."""
    await postgres.execute(
        'DELETE FROM agent_loaded_skills WHERE agent_id = $1 AND skill_id = $2',
        agent_id,
        skill_id,
    )


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
            'IMPORTANT: Maximum 3 skills can be loaded at a time. '
            'When you reach the limit, use unload_skill to free a slot. '
            'Pass your agent_id so the required tools can be attached to you.'
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
            postgres = self.service_manager.postgres

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

            # Check capacity from the database
            currently_loaded = await _get_loaded_skills(postgres, agent_id)
            slots_available = MAX_LOADED_SKILLS - len(currently_loaded)

            if slots_available <= 0:
                loaded_list = ', '.join(currently_loaded)
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Skill Memory Full: You have {MAX_LOADED_SKILLS} skills loaded.\n\n'
                            f'Currently loaded: {loaded_list}\n\n'
                            f'Use unload_skill to free a slot before loading new skills.',
                        }
                    ],
                    isError=True,
                )

            # Trim request to available capacity
            if len(skill_ids) > slots_available:
                skill_ids = skill_ids[:slots_available]
                logger.info(
                    f'Trimmed skill load request to {slots_available} available slots'
                )

            skills_before = len(currently_loaded)

            # Load each skill
            results = []
            loaded_count = 0
            failed_count = 0
            all_tools_to_attach = []
            successfully_loaded_ids = []

            for skill_id in skill_ids:
                if skill_id in currently_loaded:
                    results.append(f"'{skill_id}' is already loaded, skipping")
                    continue

                skill_content = skill_service.get_skill_content(skill_id)

                if skill_content is None:
                    results.append(f"Failed to load '{skill_id}': Skill not found")
                    failed_count += 1
                else:
                    required_tools = skill_service.get_skill_tools(skill_id)
                    all_tools_to_attach.extend(required_tools)

                    results.append(f"Loaded '{skill_id}' successfully")
                    if required_tools:
                        results.append(
                            f'   Required tools: {", ".join(required_tools)}'
                        )
                    loaded_count += 1
                    successfully_loaded_ids.append(skill_id)

                    results.append(f'\n--- BEGIN SKILL: {skill_id} ---\n')
                    results.append(skill_content)
                    results.append(f'\n--- END SKILL: {skill_id} ---\n')

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

            # Attach skill tools to agent (deduplicated)
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
                    f'Already had: {", ".join(tool_attachment_result["already_attached"])}'
                )
            if tool_attachment_result['not_found']:
                results.append(
                    f'Not found: {", ".join(tool_attachment_result["not_found"])}'
                )
                logger.warning(
                    f'Tools not found in Letta: {tool_attachment_result["not_found"]}'
                )
            results.append('--- END TOOL ATTACHMENT ---\n')

            # Persist loaded skills to database
            for skill_id in successfully_loaded_ids:
                await _add_loaded_skill(postgres, agent_id, skill_id)

            skills_after = skills_before + loaded_count

            logger.info(f'Agent {agent_id[:8]} now has {skills_after} skills loaded')

            # Dynamic tool management based on count thresholds
            if skills_before == 0 and skills_after > 0:
                logger.info(
                    f'First skill loaded for agent {agent_id[:8]}, attaching unload_skill'
                )
                attach_result = letta_service.attach_tools_to_agent(
                    agent_id=agent_id, tool_names=['unload_skill']
                )
                if attach_result['attached'] or attach_result['already_attached']:
                    logger.info(f'Attached unload_skill to agent {agent_id[:8]}')

            if skills_after >= MAX_LOADED_SKILLS:
                logger.info(
                    f'Agent {agent_id[:8]} at skill capacity ({MAX_LOADED_SKILLS}), detaching load_skill'
                )
                detach_result = letta_service.detach_tools_from_agent(
                    agent_id=agent_id, tool_names=['load_skill']
                )
                if detach_result['detached']:
                    logger.info(f'Detached load_skill from agent {agent_id[:8]}')

            # Memory status banner
            all_loaded = await _get_loaded_skills(postgres, agent_id)
            memory_banner = f'\n**Skill Memory: {len(all_loaded)}/{MAX_LOADED_SKILLS} slots used**\n'
            if all_loaded:
                memory_banner += '\nCurrently loaded:\n'
                memory_banner += '\n'.join(
                    f'  {i + 1}. {sid}' for i, sid in enumerate(all_loaded)
                )
            if len(all_loaded) >= MAX_LOADED_SKILLS:
                memory_banner += (
                    '\n\nSkill memory full. Use unload_skill to free a slot.'
                )
            elif all_loaded:
                memory_banner += (
                    '\n\nUse unload_skill to free slots when done with a skill.'
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
                    '\nSome skills failed to load. Use list_skills to see available skill IDs.'
                )

            if len(skill_ids) < len(arguments.get('skill_ids', [])):
                skipped = arguments['skill_ids'][slots_available:]
                summary.append(f'\nSkipped (no capacity): {", ".join(skipped)}')

            all_text = '\n'.join(results + summary) + '\n' + memory_banner

            # Tell the agent that tools are attached and it should wrap up this turn.
            # The client sends an automatic follow-up to start a new turn where
            # the agent can use the newly attached tools with the original request.
            all_text += '\n\nYour new tools are now attached. Finish this turn with a brief acknowledgment -- the user will be prompted to continue automatically.'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': all_text}],
                isError=False,
            )

        except Exception as e:
            logger.error(f'Error loading skills: {e}')
            return self.handle_error(e)


class UnloadSkillMCPTool(MCPTool):
    """Unload skills from agent context and detach their tools."""

    @property
    def name(self) -> str:
        return 'unload_skill'

    @property
    def description(self) -> str:
        return (
            'Unload one or more skills from your working memory to free skill slots. '
            'Use this when you are done with a skill and need to load a different one. '
            'Maximum 3 skills can be loaded at a time. '
            'When you unload from 3 to 2 skills, load_skill becomes available again. '
            'IMPORTANT: Pass your agent_id and the skill IDs to unload.'
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
        """Unload skills from context and detach their tools."""
        try:
            skill_service = SkillService()
            letta_service = LettaService()
            postgres = self.service_manager.postgres

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
                            'text': 'Error: agent_id is required to unload skills.',
                        }
                    ],
                    isError=True,
                )

            currently_loaded = await _get_loaded_skills(postgres, agent_id)

            if not currently_loaded:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'No skills are currently loaded. Nothing to unload.',
                        }
                    ],
                    isError=False,
                )

            # Verify the requested skills are actually loaded
            currently_loaded_set = set(currently_loaded)
            requested_unload = set(skill_ids)

            if not requested_unload.issubset(currently_loaded_set):
                unrecognized = requested_unload - currently_loaded_set
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Error: Skills {unrecognized} are not currently loaded.\n'
                            f'Currently loaded: {", ".join(currently_loaded)}\n'
                            f'Unload only skills that are currently loaded.',
                        }
                    ],
                    isError=True,
                )

            skills_before = len(currently_loaded)

            # Figure out which tools to detach. Keep tools that are
            # shared with skills that will remain loaded.
            remaining_skill_ids = currently_loaded_set - requested_unload
            remaining_tools: set[str] = set()
            for sid in remaining_skill_ids:
                remaining_tools.update(skill_service.get_skill_tools(sid))

            results = []
            all_tools_to_detach = []

            for skill_id in skill_ids:
                results.append(f"Unloading '{skill_id}'")
                required_tools = skill_service.get_skill_tools(skill_id)
                all_tools_to_detach.extend(required_tools)

            # Only detach tools that aren't needed by remaining skills
            unique_tools = list(dict.fromkeys(all_tools_to_detach))
            safe_to_detach = [t for t in unique_tools if t not in remaining_tools]

            if safe_to_detach:
                logger.info(
                    f'Detaching {len(safe_to_detach)} tools from agent {agent_id[:8]}...'
                )
                detach_result = letta_service.detach_tools_from_agent(
                    agent_id=agent_id, tool_names=safe_to_detach
                )

                results.append('\n--- TOOL DETACHMENT ---')
                if detach_result['detached']:
                    results.append(f'Detached: {", ".join(detach_result["detached"])}')
                if detach_result['not_attached']:
                    results.append(
                        f'Already removed: {", ".join(detach_result["not_attached"])}'
                    )
                results.append('--- END TOOL DETACHMENT ---\n')

            kept_tools = set(unique_tools) & remaining_tools
            if kept_tools:
                results.append(
                    f'Kept tools shared with other loaded skills: {", ".join(kept_tools)}'
                )

            # Remove skills from the database
            for skill_id in skill_ids:
                await _remove_loaded_skill(postgres, agent_id, skill_id)

            skills_after = skills_before - len(skill_ids)

            # Dynamic tool management based on count thresholds
            if skills_after < MAX_LOADED_SKILLS:
                logger.info(f'Ensuring load_skill is attached for agent {agent_id[:8]}')
                attach_result = letta_service.attach_tools_to_agent(
                    agent_id=agent_id, tool_names=['load_skill']
                )
                if attach_result['attached']:
                    logger.info(f'Re-attached load_skill to agent {agent_id[:8]}')

            if skills_after == 0:
                logger.info(
                    f'All skills unloaded for agent {agent_id[:8]}, detaching unload_skill'
                )
                detach_result = letta_service.detach_tools_from_agent(
                    agent_id=agent_id, tool_names=['unload_skill']
                )
                if detach_result['detached']:
                    logger.info(f'Detached unload_skill from agent {agent_id[:8]}')
            else:
                logger.info(
                    f'Agent {agent_id[:8]} has {skills_after} skill(s) remaining'
                )

            # Memory status banner
            all_loaded = await _get_loaded_skills(postgres, agent_id)
            memory_banner = (
                f'\n**Skill Memory: {len(all_loaded)}/{MAX_LOADED_SKILLS} slots used**'
            )
            if all_loaded:
                memory_banner += '\n\nCurrently loaded:\n'
                memory_banner += '\n'.join(
                    f'  {i + 1}. {sid}' for i, sid in enumerate(all_loaded)
                )
                memory_banner += '\n\nYou can load more skills or unload others.'
            else:
                memory_banner += '\n\nAll skill slots are free.'

            results.append(f'\nUnloaded {len(skill_ids)} skill(s).')
            results.append(memory_banner)
            results.append(
                '\nTools detached. Finish this turn with a brief acknowledgment -- the user will be prompted to continue automatically.'
            )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(results)}]
            )

        except Exception as e:
            logger.error(f'Error unloading skills: {e}')
            return self.handle_error(e)

"""
MCP tools for creating and managing skills.

These tools enable agents to create and update skills dynamically,
making the system self-improving and allowing agents to expand their
own capabilities through the skills system.
"""

from typing import Any

from loguru import logger

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult
from thoth.services.skill_service import SkillService


class CreateSkillMCPTool(MCPTool):
    """Create a new skill in the vault."""

    @property
    def name(self) -> str:
        return 'create_skill'

    @property
    def description(self) -> str:
        return (
            'Create a new skill in the vault following the AgentSkills.io open standard. '
            'Skills provide specialized knowledge and workflows that can be loaded dynamically. '
            'This tool creates the skill directory and SKILL.md file with proper YAML frontmatter. '
            'The skill_id must match the directory name (AgentSkills.io requirement). '
            'Use this when you need to create a new reusable workflow or capability.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'skill_id': {
                    'type': 'string',
                    'description': 'Unique identifier for the skill - lowercase alphanumeric and hyphens only (1-64 chars). Cannot start/end with hyphens or have consecutive hyphens. Becomes directory name and YAML name field per AgentSkills.io standard. Example: "paper-analysis"',
                    'pattern': '^[a-z0-9]([a-z0-9-]*[a-z0-9])?$',
                    'minLength': 1,
                    'maxLength': 64,
                },
                'display_name': {
                    'type': 'string',
                    'description': 'Human-readable display name for the skill (e.g., "Paper Analysis"). Optional - if not provided, skill_id will be title-cased.',
                    'minLength': 1,
                    'maxLength': 200,
                },
                'description': {
                    'type': 'string',
                    'description': 'Clear description (1-1024 chars) of what the skill does and when to use it, per AgentSkills.io standard',
                    'minLength': 1,
                    'maxLength': 1024,
                },
                'content': {
                    'type': 'string',
                    'description': 'Full markdown content of the skill (without frontmatter). Include workflow steps, conversation patterns, examples, and troubleshooting.',
                    'minLength': 50,
                },
                'tools': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'List of tool names required by this skill (e.g., ["search_articles", "answer_research_question"]). Leave empty if no tools needed. Optional per AgentSkills.io.',
                    'default': [],
                },
                'license': {
                    'type': 'string',
                    'description': 'Optional: License name or reference to bundled license file (AgentSkills.io standard)',
                },
                'compatibility': {
                    'type': 'string',
                    'description': 'Optional: Environment requirements (max 500 chars, AgentSkills.io standard)',
                    'maxLength': 500,
                },
                'bundle': {
                    'type': 'string',
                    'description': 'Optional bundle name to organize the skill (e.g., "orchestrator", "discovery", "analyst"). Creates in bundles/{bundle}/{skill_id}/',
                },
            },
            'required': ['skill_id', 'description', 'content'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create a new skill in the vault following AgentSkills.io standard."""
        try:
            skill_service = SkillService()

            skill_id = arguments.get('skill_id', '').strip().lower()
            display_name = arguments.get('display_name', '').strip()
            description = arguments.get('description', '').strip()
            content = arguments.get('content', '').strip()
            tools = arguments.get('tools', [])
            license_info = arguments.get('license')
            compatibility = arguments.get('compatibility')
            bundle = arguments.get('bundle')

            # Validate skill_id per AgentSkills.io standard
            # Must be 1-64 chars, lowercase alphanumeric and hyphens only
            # Cannot start/end with hyphen or have consecutive hyphens
            if not skill_id:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: skill_id is required.',
                        }
                    ],
                    isError=True,
                )

            if len(skill_id) < 1 or len(skill_id) > 64:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: skill_id must be 1-64 characters (AgentSkills.io standard).',
                        }
                    ],
                    isError=True,
                )

            if skill_id.startswith('-') or skill_id.endswith('-') or '--' in skill_id:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: skill_id cannot start/end with hyphen or contain consecutive hyphens (AgentSkills.io standard).',
                        }
                    ],
                    isError=True,
                )

            if not all(c.isalnum() or c == '-' for c in skill_id):
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: skill_id must contain only lowercase letters, numbers, and hyphens (AgentSkills.io standard).',
                        }
                    ],
                    isError=True,
                )

            # Validate description per AgentSkills.io standard (1-1024 chars)
            if not description or len(description) > 1024:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: description is required and must be 1-1024 characters (AgentSkills.io standard).',
                        }
                    ],
                    isError=True,
                )

            if not content:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: content is required and cannot be empty.',
                        }
                    ],
                    isError=True,
                )

            # Validate compatibility if provided (max 500 chars per AgentSkills.io)
            if compatibility and len(compatibility) > 500:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: compatibility must be max 500 characters (AgentSkills.io standard).',
                        }
                    ],
                    isError=True,
                )

            # Generate display_name from skill_id if not provided
            if not display_name:
                display_name = skill_id.replace('-', ' ').title()

            # Determine skill path
            if bundle:
                skill_dir = skill_service.bundles_dir / bundle / skill_id
                full_skill_id = f'bundles/{bundle}/{skill_id}'
            else:
                skill_dir = skill_service.vault_skills_dir / skill_id
                full_skill_id = skill_id

            # Check if skill already exists
            if skill_dir.exists():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Error: Skill already exists at {skill_dir}\n\n'
                            f'Use update_skill to modify existing skills, or choose a different skill_id.',
                        }
                    ],
                    isError=True,
                )

            # Create skill directory (skill_id matches directory name per
            # AgentSkills.io)
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Build YAML frontmatter per AgentSkills.io standard
            # Required: name (matching directory), description
            # Optional: tools, license, compatibility, metadata
            frontmatter_lines = [
                '---',
                f'name: {skill_id}',  # MUST match directory name per AgentSkills.io
                f'description: {description}',
            ]

            # Add optional fields per AgentSkills.io standard
            if tools:
                frontmatter_lines.append('tools:')
                for tool in tools:
                    frontmatter_lines.append(f'  - {tool}')

            if license_info:
                frontmatter_lines.append(f'license: {license_info}')

            if compatibility:
                frontmatter_lines.append(f'compatibility: {compatibility}')

            frontmatter_lines.append('---')

            # Create SKILL.md with frontmatter + content
            skill_file = skill_dir / 'SKILL.md'
            skill_content = '\n'.join(frontmatter_lines) + '\n\n' + content

            with open(skill_file, 'w', encoding='utf-8') as f:
                f.write(skill_content)

            logger.info(
                f'Created AgentSkills.io compliant skill: {full_skill_id} at {skill_file}'
            )

            # Build success message
            result_lines = [
                f'Successfully created skill: {full_skill_id}',
                '',
                '**AgentSkills.io Standard Compliance:**',
                f'- name: {skill_id} (matches directory ✓)',
                f'- description: {len(description)} chars (1-1024 ✓)',
                '',
                f'**Location**: {skill_file}',
                f'**Display Name**: {display_name}',
                f'**Description**: {description}',
            ]

            if tools:
                result_lines.append(f'**Tools**: {", ".join(tools)}')

            if license_info:
                result_lines.append(f'**License**: {license_info}')

            if compatibility:
                result_lines.append(f'**Compatibility**: {compatibility}')

            result_lines.extend(
                [
                    '',
                    '**Next steps**:',
                    '1. The skill is now available - use `list_skills` to see it',
                    f'2. Load it with: `load_skill(skill_ids=["{skill_id}"], agent_id="<your-agent-id>")`',
                    '3. Test the skill workflow with a real scenario',
                    '4. Refine based on testing using `update_skill` if needed',
                    '',
                    '**AgentSkills.io**: Skill follows open standard for AI skills',
                ]
            )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(result_lines)}]
            )

        except Exception as e:
            logger.error(f'Error creating skill: {e}')
            return self.handle_error(e)


class UpdateSkillMCPTool(MCPTool):
    """Update an existing skill in the vault."""

    @property
    def name(self) -> str:
        return 'update_skill'

    @property
    def description(self) -> str:
        return (
            'Update an existing skill in the vault following the AgentSkills.io standard. '
            'Can update description, content, tools, license, or compatibility fields. '
            'The name field is automatically set to match the directory name (AgentSkills.io requirement). '
            'Only vault and bundle skills can be updated (bundled skills are read-only). '
            'Use this to refine skills based on testing or to fix issues.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'skill_id': {
                    'type': 'string',
                    'description': 'Skill identifier to update (e.g., "paper-analysis" or "bundles/orchestrator/workflow")',
                    'minLength': 1,
                },
                'description': {
                    'type': 'string',
                    'description': 'Updated description (1-1024 chars per AgentSkills.io standard, optional)',
                    'minLength': 1,
                    'maxLength': 1024,
                },
                'content': {
                    'type': 'string',
                    'description': 'Updated markdown content (optional). Replaces entire content.',
                    'minLength': 50,
                },
                'tools': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Updated tools list (optional). Replaces entire tools list.',
                },
                'license': {
                    'type': 'string',
                    'description': 'Updated license (optional, AgentSkills.io standard)',
                },
                'compatibility': {
                    'type': 'string',
                    'description': 'Updated compatibility requirements (max 500 chars, optional, AgentSkills.io standard)',
                    'maxLength': 500,
                },
            },
            'required': ['skill_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Update an existing skill following AgentSkills.io standard."""
        try:
            skill_service = SkillService()

            skill_id = arguments.get('skill_id', '').strip()
            new_description = arguments.get('description')
            new_content = arguments.get('content')
            new_tools = arguments.get('tools')
            new_license = arguments.get('license')
            new_compatibility = arguments.get('compatibility')

            # Validate at least one update is provided
            if not any(
                [
                    new_description,
                    new_content,
                    new_tools,
                    new_license,
                    new_compatibility,
                ]
            ):
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: At least one field must be provided to update (description, content, tools, license, or compatibility).',
                        }
                    ],
                    isError=True,
                )

            # Validate description if provided (1-1024 chars per AgentSkills.io)
            if new_description and (
                len(new_description) < 1 or len(new_description) > 1024
            ):
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: description must be 1-1024 characters (AgentSkills.io standard).',
                        }
                    ],
                    isError=True,
                )

            # Validate compatibility if provided (max 500 chars per AgentSkills.io)
            if new_compatibility and len(new_compatibility) > 500:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: compatibility must be max 500 characters (AgentSkills.io standard).',
                        }
                    ],
                    isError=True,
                )

            # Get current skill
            current_content_full = skill_service.get_skill_content(skill_id)
            if current_content_full is None:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Error: Skill not found: {skill_id}\n\n'
                            f'Use list_skills to see available skills.',
                        }
                    ],
                    isError=True,
                )

            # Determine skill file path
            if skill_id.startswith('bundles/'):
                parts = skill_id.split('/')
                bundle_name = parts[1]
                skill_name = parts[2]
                skill_file = (
                    skill_service.bundles_dir / bundle_name / skill_name / 'SKILL.md'
                )
            else:
                skills = skill_service.discover_skills()
                if skill_id not in skills:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f'Error: Skill not found: {skill_id}',
                            }
                        ],
                        isError=True,
                    )

                skill_info = skills[skill_id]
                if skill_info['source'] == 'bundled':
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f'Error: Cannot update bundled skills.\n\n'
                                f'Skill "{skill_id}" is a built-in skill and cannot be modified. '
                                f'Create a new skill in the vault instead.',
                            }
                        ],
                        isError=True,
                    )

                from pathlib import Path

                skill_file = Path(skill_info['path'])

            # Parse current metadata
            current_metadata = skill_service._parse_skill_metadata(skill_file)

            # Determine updated values (name must match directory per AgentSkills.io)
            # Extract skill name from path
            skill_dir_name = skill_file.parent.name

            updated_description = (
                new_description
                if new_description
                else current_metadata.get('description', '')
            )
            updated_tools = (
                new_tools
                if new_tools is not None
                else current_metadata.get('tools', [])
            )
            updated_license = (
                new_license
                if new_license is not None
                else current_metadata.get('license')
            )
            updated_compatibility = (
                new_compatibility
                if new_compatibility is not None
                else current_metadata.get('compatibility')
            )

            # Get updated content
            if new_content is not None:
                updated_content = new_content
            else:
                # Extract current content (remove frontmatter)
                parts = current_content_full.split('---', 2)
                updated_content = (
                    parts[2].strip() if len(parts) >= 3 else current_content_full
                )

            # Build new YAML frontmatter per AgentSkills.io standard
            # name MUST match directory name
            frontmatter_lines = [
                '---',
                f'name: {skill_dir_name}',  # MUST match directory per AgentSkills.io
                f'description: {updated_description}',
            ]

            # Add optional fields per AgentSkills.io standard
            if updated_tools:
                frontmatter_lines.append('tools:')
                for tool in updated_tools:
                    frontmatter_lines.append(f'  - {tool}')

            if updated_license:
                frontmatter_lines.append(f'license: {updated_license}')

            if updated_compatibility:
                frontmatter_lines.append(f'compatibility: {updated_compatibility}')

            frontmatter_lines.append('---')

            # Write updated skill
            final_content = '\n'.join(frontmatter_lines) + '\n\n' + updated_content

            with open(skill_file, 'w', encoding='utf-8') as f:
                f.write(final_content)

            logger.info(f'Updated AgentSkills.io compliant skill: {skill_id}')

            # Build success message
            result_lines = [
                f'Successfully updated skill: {skill_id}',
                '',
                '**AgentSkills.io Standard Compliance:**',
                f'- name: {skill_dir_name} (matches directory ✓)',
                f'- description: {len(updated_description)} chars (1-1024 ✓)',
                '',
                f'**Location**: {skill_file}',
            ]

            # Show what was updated
            updated_fields = []
            if new_description:
                updated_fields.append('description')
            if new_content:
                updated_fields.append(f'content ({len(new_content)} characters)')
            if new_tools is not None:
                updated_fields.append(f'tools ({len(updated_tools)} tools)')
            if new_license is not None:
                updated_fields.append('license')
            if new_compatibility is not None:
                updated_fields.append('compatibility')

            result_lines.append(f'**Updated**: {", ".join(updated_fields)}')

            if updated_tools:
                result_lines.append(f'**Tools**: {", ".join(updated_tools)}')

            if updated_license:
                result_lines.append(f'**License**: {updated_license}')

            if updated_compatibility:
                result_lines.append(f'**Compatibility**: {updated_compatibility}')

            result_lines.extend(
                [
                    '',
                    '**Next steps**:',
                    '1. If the skill is currently loaded, unload and reload it to see changes',
                    '2. Test the updated workflow',
                    '3. Further refine if needed',
                ]
            )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(result_lines)}]
            )

        except Exception as e:
            logger.error(f'Error updating skill: {e}')
            return self.handle_error(e)

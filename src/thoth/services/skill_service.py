"""
Skill Service for managing agent skills with two-tier discovery and role-based loading.

This service discovers and manages skills from both bundled default locations
and user-specific vault locations, following the agentskills.io standard.

Features:
- Two-tier discovery (bundled + vault)
- Role-based skill bundles for specialized agents
- Token-efficient skill summaries
- On-demand full content loading
"""

from pathlib import Path
from typing import Any

from thoth.services.base import BaseService


class SkillService(BaseService):
    """
    Service for discovering and managing agent skills.

    Implements a three-tier system:
    - Bundled skills (shipped with Thoth): src/thoth/.skills/
    - User skills (vault-specific): vault/thoth/_thoth/skills/
    - Role-based bundles: vault/thoth/_thoth/skills/bundles/{role}/

    User skills override bundled skills with the same name.
    Role-based bundles enable automatic skill loading per agent type.
    """

    # Role-to-skill mapping for the optimized 2-agent architecture
    # Maps agent roles to the skills they should have access to
    ROLE_SKILLS = {
        # Research Orchestrator - user-facing coordinator
        'orchestrator': [
            'paper-discovery',
            'knowledge-base-qa',
            'research-query-management',
            'research-project-coordination',
        ],
        # Research Analyst - deep analysis specialist
        'analyst': [
            'deep-research',
            'knowledge-base-qa',
        ],
        # Legacy role mappings for backward compatibility
        'coordinator': [
            'paper-discovery',
            'knowledge-base-qa',
            'research-project-coordination',
        ],
        'discovery': ['paper-discovery', 'research-query-management'],
        'document': ['paper-discovery'],
        'citation': ['deep-research'],
        'curator': ['knowledge-base-qa'],
        'maintenance': [],
    }

    def __init__(self, config=None):
        """
        Initialize the Skill Service.

        Args:
            config: Configuration object
        """
        super().__init__(config)

        # Bundled skills directory (shipped with Thoth)
        self.bundled_skills_dir = Path(__file__).parent.parent / '.skills'

        # Vault skills directory (user-specific, hot-reloadable)
        # Use resolved workspace dir for vault skills (thoth/_thoth/skills/)
        self.vault_skills_dir = self.config.workspace_dir / 'skills'
        self.vault_skills_dir.mkdir(parents=True, exist_ok=True)

        # Role-based bundles directories (bundled first, vault can override)
        self.bundled_bundles_dir = self.bundled_skills_dir / 'bundles'
        self.vault_bundles_dir = self.vault_skills_dir / 'bundles'
        self.vault_bundles_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            f'SkillService initialized:\n'
            f'  Bundled: {self.bundled_skills_dir}\n'
            f'  Vault: {self.vault_skills_dir}\n'
            f'  Bundled Bundles: {self.bundled_bundles_dir}\n'
            f'  Vault Bundles: {self.vault_bundles_dir}'
        )

    def initialize(self) -> None:
        """Initialize the skill service."""
        self.logger.info('SkillService initialized')

    def discover_skills(self) -> dict[str, dict[str, Any]]:
        """
        Discover skills from both bundled and vault locations.

        Priority: vault skills override bundled skills with same name.

        Returns:
            dict: Mapping of skill_id to skill metadata:
                {
                    'skill_id': {
                        'name': 'Skill Name',
                        'description': 'Skill description',
                        'path': Path to SKILL.md,
                        'source': 'bundled' or 'vault',
                    }
                }
        """
        skills = {}

        # Load bundled skills first
        if self.bundled_skills_dir.exists():
            for skill_dir in self.bundled_skills_dir.glob('*/'):
                if skill_dir.is_dir():
                    skill_file = skill_dir / 'SKILL.md'
                    if skill_file.exists():
                        skill_id = skill_dir.name
                        metadata = self._parse_skill_metadata(skill_file)
                        skills[skill_id] = {
                            'name': metadata.get('name', skill_id),
                            'description': metadata.get('description', ''),
                            'path': skill_file,
                            'source': 'bundled',
                        }
                        self.logger.debug(f'Discovered bundled skill: {skill_id}')

        # Load vault skills (overrides bundled)
        if self.vault_skills_dir.exists():
            for skill_dir in self.vault_skills_dir.glob('*/'):
                if skill_dir.is_dir():
                    skill_file = skill_dir / 'SKILL.md'
                    if skill_file.exists():
                        skill_id = skill_dir.name
                        metadata = self._parse_skill_metadata(skill_file)

                        # Check if overriding bundled skill
                        if skill_id in skills:
                            self.logger.info(
                                f"Vault skill '{skill_id}' overrides bundled skill"
                            )

                        skills[skill_id] = {
                            'name': metadata.get('name', skill_id),
                            'description': metadata.get('description', ''),
                            'path': skill_file,
                            'source': 'vault',
                        }
                        self.logger.debug(f'Discovered vault skill: {skill_id}')

        self.logger.info(
            f'Discovered {len(skills)} skills: '
            f'{sum(1 for s in skills.values() if s["source"] == "bundled")} bundled, '
            f'{sum(1 for s in skills.values() if s["source"] == "vault")} vault'
        )

        return skills

    def _parse_skill_metadata(self, skill_file: Path) -> dict[str, Any]:
        """
        Parse YAML frontmatter from SKILL.md file.

        Args:
            skill_file: Path to SKILL.md file

        Returns:
            dict: Parsed metadata (name, description, tools)
        """
        try:
            import yaml

            with open(skill_file, encoding='utf-8') as f:
                content = f.read()

            # Parse YAML frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = parts[1].strip()
                    try:
                        # Use yaml.safe_load for proper parsing of lists
                        metadata = yaml.safe_load(frontmatter)
                        return metadata if metadata else {}
                    except yaml.YAMLError:
                        # Fallback to simple parsing for basic key: value
                        metadata = {}
                        for line in frontmatter.split('\n'):
                            if ':' in line and not line.strip().startswith('-'):
                                key, value = line.split(':', 1)
                                metadata[key.strip()] = value.strip()
                        return metadata

            return {}

        except Exception as e:
            self.logger.warning(
                f'Failed to parse skill metadata from {skill_file}: {e}'
            )
            return {}

    def get_skill_tools(self, skill_id: str) -> list[str]:
        """
        Get the list of tools required by a skill.

        Args:
            skill_id: Skill identifier

        Returns:
            list: Tool names required by this skill
        """
        # Find the skill file
        skills = self.discover_skills()

        if skill_id in skills:
            skill_path = skills[skill_id]['path']
            metadata = self._parse_skill_metadata(skill_path)
            return metadata.get('tools', [])

        # Check bundle skills
        if skill_id.startswith('bundles/'):
            parts = skill_id.split('/')
            if len(parts) == 3:
                bundle_name = parts[1]
                skill_name = parts[2]
                skill_path = self._find_bundle_skill_path(bundle_name, skill_name)
                if skill_path and skill_path.exists():
                    metadata = self._parse_skill_metadata(skill_path)
                    return metadata.get('tools', [])

        return []

    def get_skill_content(self, skill_id: str) -> str | None:
        """
        Get the full content of a skill by ID.

        Supports both standalone skills and bundle skills.

        Args:
            skill_id: Skill identifier (e.g., 'research-deep-dive' or 'bundles/orchestrator/research-workflow-coordination')

        Returns:
            str: Full SKILL.md content, or None if not found
        """
        # Check if it's a bundle skill
        if skill_id.startswith('bundles/'):
            return self.get_bundle_skill_content(skill_id)

        # Standalone skill
        skills = self.discover_skills()

        if skill_id not in skills:
            self.logger.warning(f"Skill '{skill_id}' not found")
            return None

        skill_path = skills[skill_id]['path']

        try:
            with open(skill_path, encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(
                f"Failed to read skill '{skill_id}' from {skill_path}: {e}"
            )
            return None

    def format_skills_summary(self) -> str:
        """
        Format a summary of available skills for agent memory.

        Returns:
            str: Formatted summary of all available skills
        """
        skills = self.discover_skills()

        if not skills:
            return 'No skills available.'

        lines = [
            f'Skills Directory: {self.bundled_skills_dir}',
            f'Global Skills Directory: {self.vault_skills_dir}',
            '',
            'Available Skills:',
            '(source: bundled = built-in to Thoth, vault = custom user skills)',
            '',
        ]

        for skill_id, skill_info in sorted(skills.items()):
            source_label = 'vault' if skill_info['source'] == 'vault' else 'bundled'
            lines.append(f'### {skill_info["name"]} ({source_label})')
            lines.append(f'ID: `{skill_id}`')
            lines.append(f'Description: {skill_info["description"]}')
            lines.append('')

        return '\n'.join(lines)

    def _find_bundle_skill_path(self, bundle_name: str, skill_name: str) -> Path | None:
        """
        Find a bundle skill path, checking vault first then bundled.

        Args:
            bundle_name: Bundle name (e.g., 'orchestrator')
            skill_name: Skill name within the bundle

        Returns:
            Path to SKILL.md or None if not found
        """
        # Check vault bundles first (can override bundled)
        vault_path = self.vault_bundles_dir / bundle_name / skill_name / 'SKILL.md'
        if vault_path.exists():
            return vault_path

        # Check bundled bundles
        bundled_path = self.bundled_bundles_dir / bundle_name / skill_name / 'SKILL.md'
        if bundled_path.exists():
            return bundled_path

        return None

    def discover_bundle_skills(self) -> dict[str, list[str]]:
        """
        Discover skills organized in role-based bundles.

        Checks both bundled and vault bundles directories.
        Vault bundles can override bundled ones with the same name.

        Returns:
            dict: Mapping of bundle_name to list of skill_ids
                {
                    'orchestrator': ['research-workflow-coordination', ...],
                    'discovery': ['research-discovery-execution', ...],
                    'analysis': ['research-deep-dive', ...],
                }
        """
        bundles = {}

        # Helper to scan a bundles directory
        def scan_bundles_dir(bundles_dir: Path, source: str):
            if not bundles_dir.exists():
                return

            for bundle_dir in bundles_dir.glob('*/'):
                if bundle_dir.is_dir():
                    bundle_name = bundle_dir.name

                    if bundle_name not in bundles:
                        bundles[bundle_name] = []

                    # Find all skills in this bundle
                    for skill_dir in bundle_dir.glob('*/'):
                        if skill_dir.is_dir():
                            skill_file = skill_dir / 'SKILL.md'
                            if skill_file.exists():
                                skill_id = f'bundles/{bundle_name}/{skill_dir.name}'
                                if skill_id not in bundles[bundle_name]:
                                    bundles[bundle_name].append(skill_id)

                    self.logger.debug(
                        f"Discovered {source} bundle '{bundle_name}' "
                        f'with {len(bundles[bundle_name])} skills'
                    )

        # Scan bundled bundles first
        scan_bundles_dir(self.bundled_bundles_dir, 'bundled')

        # Scan vault bundles (can add more or override)
        scan_bundles_dir(self.vault_bundles_dir, 'vault')

        return bundles

    def get_skills_for_role(self, role: str) -> list[str]:
        """
        Get skill IDs appropriate for an agent role.

        Uses the ROLE_SKILLS mapping to determine which skills
        are relevant for each agent role in the optimized 2-agent architecture.

        Args:
            role: Agent role (e.g., 'orchestrator', 'analyst')

        Returns:
            list: List of skill IDs for this role
        """
        # Get skills from role mapping
        role_skill_names = self.ROLE_SKILLS.get(role, [])

        # Discover all available skills
        all_skills = self.discover_skills()

        # Match skill names to discovered skills
        skill_ids = []
        for skill_name in role_skill_names:
            if skill_name in all_skills:
                skill_ids.append(skill_name)

        # Also check bundle skills for backward compatibility
        bundles = self.discover_bundle_skills()
        for bundle_name, bundle_skills in bundles.items():
            # Include bundle skills if they match role
            for bundle_skill_id in bundle_skills:
                if bundle_skill_id not in skill_ids:
                    skill_ids.append(bundle_skill_id)

        return skill_ids

    def format_role_skills_summary(self, role: str) -> str:
        """
        Format a token-efficient summary of skills for a specific role.

        This provides lightweight skill metadata (name + 1-line description)
        without full content, optimizing for token efficiency. Full skill
        content is loaded on-demand via load_skill MCP tool.

        Args:
            role: Agent role

        Returns:
            str: Lightweight skills summary (~50 tokens per skill)
        """
        skill_ids = self.get_skills_for_role(role)

        if not skill_ids:
            return f"No skills available for role '{role}'"

        lines = [
            f'=== Skills Available for {role.title()} ===',
            '',
            f'You have access to {len(skill_ids)} specialized skills.',
            "To use a skill, call: load_skill(skill_ids=['skill-id'])",
            '',
            'Available skills:',
            '',
        ]

        # Get metadata for each skill
        all_skills = self.discover_skills()
        bundles = self.discover_bundle_skills()

        for skill_id in skill_ids:
            # Handle bundle skills
            if skill_id.startswith('bundles/'):
                # Extract skill path from bundles
                parts = skill_id.split('/')
                bundle_name = parts[1]
                skill_name = parts[2]
                skill_path = self.bundles_dir / bundle_name / skill_name / 'SKILL.md'

                if skill_path.exists():
                    metadata = self._parse_skill_metadata(skill_path)
                    name = metadata.get('name', skill_name)
                    desc = metadata.get('description', '')
                    lines.append(f'• {name}')
                    lines.append(f'  ID: {skill_id}')
                    lines.append(f'  Use: {desc}')
                    lines.append('')
            elif skill_id in all_skills:
                # Standalone skill
                skill_info = all_skills[skill_id]
                lines.append(f'• {skill_info["name"]}')
                lines.append(f'  ID: {skill_id}')
                lines.append(f'  Use: {skill_info["description"]}')
                lines.append('')

        lines.extend(
            [
                'To see full skill details:',
                "1. Call load_skill(skill_ids=['skill-id'])",
                '2. Read the complete skill guidance',
                "3. Follow the skill's instructions",
                '',
                'Skills are loaded on-demand to conserve context tokens.',
            ]
        )

        return '\n'.join(lines)

    def get_bundle_skill_content(self, skill_id: str) -> str | None:
        """
        Get content for a skill from bundles.

        Checks both bundled and vault bundles directories.

        Args:
            skill_id: Skill ID in format 'bundles/{bundle}/{skill}'

        Returns:
            str: Skill content or None if not found
        """
        if not skill_id.startswith('bundles/'):
            return None

        parts = skill_id.split('/')
        if len(parts) != 3:
            return None

        bundle_name = parts[1]
        skill_name = parts[2]
        skill_path = self._find_bundle_skill_path(bundle_name, skill_name)

        if not skill_path:
            self.logger.warning(f'Bundle skill not found: {skill_id}')
            return None

        try:
            with open(skill_path, encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Failed to read bundle skill '{skill_id}': {e}")
            return None

    def filter_by_role(
        self, skills: dict[str, dict[str, Any]], role: str
    ) -> dict[str, dict[str, Any]]:
        """
        Filter skills dictionary to only include skills for a specific role.

        Args:
            skills: Full skills dictionary from discover_skills()
            role: Agent role to filter for

        Returns:
            dict: Filtered skills dictionary
        """
        role_skill_ids = set(self.get_skills_for_role(role))
        return {k: v for k, v in skills.items() if k in role_skill_ids}

    def watch_vault_skills(self, callback) -> None:
        """
        Watch vault skills directory for changes (hot-reload).

        This method sets up file system watching for the vault skills directory.
        When changes are detected, the callback is triggered.

        Args:
            callback: Function to call when skills directory changes

        Note:
            This integrates with the existing config hot-reload system.
        """
        # This will be integrated with config's hot-reload callbacks
        # The callback will trigger skill refresh in agent memory
        self.logger.info(f'Watching vault skills directory: {self.vault_skills_dir}')
        # Implementation will be added when integrating with config hot-reload

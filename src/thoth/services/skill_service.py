"""
Skill Service for managing agent skills with two-tier discovery.

This service discovers and manages skills from both bundled default locations
and user-specific vault locations, following the agentskills.io standard.
"""

from pathlib import Path
from typing import Any

from thoth.services.base import BaseService


class SkillService(BaseService):
    """
    Service for discovering and managing agent skills.
    
    Implements a two-tier system:
    - Bundled skills (shipped with Thoth): src/thoth/.skills/
    - User skills (vault-specific): vault/_thoth/skills/
    
    User skills override bundled skills with the same name.
    """

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
        self.vault_skills_dir = self.config.vault_root / '_thoth' / 'skills'
        self.vault_skills_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(
            f'SkillService initialized:\n'
            f'  Bundled: {self.bundled_skills_dir}\n'
            f'  Vault: {self.vault_skills_dir}'
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
                        self.logger.debug(f"Discovered bundled skill: {skill_id}")
        
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
                        self.logger.debug(f"Discovered vault skill: {skill_id}")
        
        self.logger.info(
            f"Discovered {len(skills)} skills: "
            f"{sum(1 for s in skills.values() if s['source'] == 'bundled')} bundled, "
            f"{sum(1 for s in skills.values() if s['source'] == 'vault')} vault"
        )
        
        return skills

    def _parse_skill_metadata(self, skill_file: Path) -> dict[str, str]:
        """
        Parse YAML frontmatter from SKILL.md file.
        
        Args:
            skill_file: Path to SKILL.md file
        
        Returns:
            dict: Parsed metadata (name, description)
        """
        try:
            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse YAML frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = parts[1].strip()
                    metadata = {}
                    for line in frontmatter.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            metadata[key.strip()] = value.strip()
                    return metadata
            
            return {}
        
        except Exception as e:
            self.logger.warning(f"Failed to parse skill metadata from {skill_file}: {e}")
            return {}

    def get_skill_content(self, skill_id: str) -> str | None:
        """
        Get the full content of a skill by ID.
        
        Args:
            skill_id: Skill identifier
        
        Returns:
            str: Full SKILL.md content, or None if not found
        """
        skills = self.discover_skills()
        
        if skill_id not in skills:
            self.logger.warning(f"Skill '{skill_id}' not found")
            return None
        
        skill_path = skills[skill_id]['path']
        
        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Failed to read skill '{skill_id}' from {skill_path}: {e}")
            return None

    def format_skills_summary(self) -> str:
        """
        Format a summary of available skills for agent memory.
        
        Returns:
            str: Formatted summary of all available skills
        """
        skills = self.discover_skills()
        
        if not skills:
            return "No skills available."
        
        lines = [
            f"Skills Directory: {self.bundled_skills_dir}",
            f"Global Skills Directory: {self.vault_skills_dir}",
            "",
            "Available Skills:",
            "(source: bundled = built-in to Thoth, vault = custom user skills)",
            "",
        ]
        
        for skill_id, skill_info in sorted(skills.items()):
            source_label = "vault" if skill_info['source'] == 'vault' else "bundled"
            lines.append(f"### {skill_info['name']} ({source_label})")
            lines.append(f"ID: `{skill_id}`")
            lines.append(f"Description: {skill_info['description']}")
            lines.append("")
        
        return '\n'.join(lines)

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
        self.logger.info(f"Watching vault skills directory: {self.vault_skills_dir}")
        # Implementation will be added when integrating with config hot-reload

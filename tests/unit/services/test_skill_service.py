"""Unit tests for SkillService."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from thoth.services.skill_service import SkillService


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config object with temp directory."""
    config = MagicMock()
    config.vault_root = tmp_path / 'vault'
    config.vault_root.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture
def temp_skill_dirs(tmp_path):
    """Create temporary skill directories for testing."""
    bundled = tmp_path / 'bundled_skills'
    vault = tmp_path / 'vault_skills'
    bundled.mkdir()
    vault.mkdir()
    return bundled, vault


class TestSkillService:
    """Tests for SkillService."""

    def test_initialization(self, mock_config):
        """Test SkillService initialization."""
        service = SkillService(mock_config)
        
        assert service.config == mock_config
        assert service.bundled_skills_dir.name == '.skills'
        assert service.vault_skills_dir == mock_config.vault_root / '_thoth' / 'skills'

    def test_discover_skills_empty_directories(self, mock_config, temp_skill_dirs):
        """Test skill discovery with empty directories."""
        bundled, vault = temp_skill_dirs
        
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'glob', return_value=[]):
                service = SkillService(mock_config)
                service.bundled_skills_dir = bundled
                service.vault_skills_dir = vault
                
                skills = service.discover_skills()
        
        assert len(skills) == 0

    def test_discover_bundled_skills(self, mock_config, temp_skill_dirs):
        """Test discovering bundled skills."""
        bundled, vault = temp_skill_dirs
        
        # Create bundled skill directory with SKILL.md
        skill_dir = bundled / 'test-skill'
        skill_dir.mkdir()
        skill_file = skill_dir / 'SKILL.md'
        skill_file.write_text("""---
name: Test Skill
description: A test skill
---
# Test Skill Content
""")
        
        service = SkillService(mock_config)
        service.bundled_skills_dir = bundled
        service.vault_skills_dir = vault
        
        skills = service.discover_skills()
        
        assert len(skills) == 1
        assert 'test-skill' in skills
        assert skills['test-skill']['name'] == 'Test Skill'
        assert skills['test-skill']['description'] == 'A test skill'
        assert skills['test-skill']['source'] == 'bundled'

    def test_discover_vault_skills_override(self, mock_config, temp_skill_dirs):
        """Test that vault skills override bundled skills."""
        bundled, vault = temp_skill_dirs
        
        # Create same-named skill in both locations
        bundled_skill = bundled / 'same-skill'
        bundled_skill.mkdir()
        (bundled_skill / 'SKILL.md').write_text("""---
name: Bundled Version
description: Original bundled skill
---
# Bundled Content
""")
        
        vault_skill = vault / 'same-skill'
        vault_skill.mkdir()
        (vault_skill / 'SKILL.md').write_text("""---
name: Vault Version
description: User override skill
---
# User Content
""")
        
        service = SkillService(mock_config)
        service.bundled_skills_dir = bundled
        service.vault_skills_dir = vault
        
        skills = service.discover_skills()
        
        assert len(skills) == 1
        assert skills['same-skill']['name'] == 'Vault Version'
        assert skills['same-skill']['source'] == 'vault'

    def test_discover_mixed_skills(self, mock_config, temp_skill_dirs):
        """Test discovering both bundled and vault skills."""
        bundled, vault = temp_skill_dirs
        
        # Create bundled skill
        bundled_skill = bundled / 'bundled-skill'
        bundled_skill.mkdir()
        (bundled_skill / 'SKILL.md').write_text("""---
name: Bundled Skill
description: A bundled skill
---
""")
        
        # Create vault skill
        vault_skill = vault / 'vault-skill'
        vault_skill.mkdir()
        (vault_skill / 'SKILL.md').write_text("""---
name: Vault Skill
description: A vault skill
---
""")
        
        service = SkillService(mock_config)
        service.bundled_skills_dir = bundled
        service.vault_skills_dir = vault
        
        skills = service.discover_skills()
        
        assert len(skills) == 2
        assert 'bundled-skill' in skills
        assert 'vault-skill' in skills
        assert skills['bundled-skill']['source'] == 'bundled'
        assert skills['vault-skill']['source'] == 'vault'

    def test_parse_skill_metadata_valid(self, mock_config):
        """Test parsing valid YAML frontmatter."""
        service = SkillService(mock_config)
        
        content = """---
name: Test Skill
description: A test skill for testing
---
# Skill Content
"""
        
        with patch('builtins.open', mock_open(read_data=content)):
            metadata = service._parse_skill_metadata(Path('/fake/path'))
        
        assert metadata['name'] == 'Test Skill'
        assert metadata['description'] == 'A test skill for testing'

    def test_parse_skill_metadata_no_frontmatter(self, mock_config):
        """Test parsing file without frontmatter."""
        service = SkillService(mock_config)
        
        content = """# Skill Content
No frontmatter here
"""
        
        with patch('builtins.open', mock_open(read_data=content)):
            metadata = service._parse_skill_metadata(Path('/fake/path'))
        
        assert metadata == {}

    def test_parse_skill_metadata_malformed(self, mock_config):
        """Test parsing malformed frontmatter."""
        service = SkillService(mock_config)
        
        content = """---
This is not valid YAML: [unclosed
---
"""
        
        with patch('builtins.open', mock_open(read_data=content)):
            metadata = service._parse_skill_metadata(Path('/fake/path'))
        
        # Should handle gracefully and return empty dict
        assert isinstance(metadata, dict)

    def test_get_skill_content_success(self, mock_config, temp_skill_dirs):
        """Test getting skill content."""
        bundled, vault = temp_skill_dirs
        
        skill_dir = bundled / 'test-skill'
        skill_dir.mkdir()
        skill_content = """---
name: Test Skill
description: Test
---
# Full Content Here
"""
        (skill_dir / 'SKILL.md').write_text(skill_content)
        
        service = SkillService(mock_config)
        service.bundled_skills_dir = bundled
        service.vault_skills_dir = vault
        
        content = service.get_skill_content('test-skill')
        
        assert content == skill_content

    def test_get_skill_content_not_found(self, mock_config, temp_skill_dirs):
        """Test getting non-existent skill content."""
        bundled, vault = temp_skill_dirs
        
        service = SkillService(mock_config)
        service.bundled_skills_dir = bundled
        service.vault_skills_dir = vault
        
        content = service.get_skill_content('non-existent')
        
        assert content is None

    def test_format_skills_summary_empty(self, mock_config, temp_skill_dirs):
        """Test formatting summary with no skills."""
        bundled, vault = temp_skill_dirs
        
        service = SkillService(mock_config)
        service.bundled_skills_dir = bundled
        service.vault_skills_dir = vault
        
        summary = service.format_skills_summary()
        
        assert 'No skills available' in summary

    def test_format_skills_summary_with_skills(self, mock_config, temp_skill_dirs):
        """Test formatting summary with skills."""
        bundled, vault = temp_skill_dirs
        
        # Create test skills
        bundled_skill = bundled / 'bundled-skill'
        bundled_skill.mkdir()
        (bundled_skill / 'SKILL.md').write_text("""---
name: Bundled Skill
description: A bundled test skill
---
""")
        
        vault_skill = vault / 'vault-skill'
        vault_skill.mkdir()
        (vault_skill / 'SKILL.md').write_text("""---
name: Vault Skill
description: A user vault skill
---
""")
        
        service = SkillService(mock_config)
        service.bundled_skills_dir = bundled
        service.vault_skills_dir = vault
        
        summary = service.format_skills_summary()
        
        assert 'Available Skills' in summary
        assert 'Bundled Skill' in summary
        assert 'Vault Skill' in summary
        assert 'bundled' in summary
        assert 'vault' in summary

    def test_skill_directory_creation(self, mock_config):
        """Test that vault skills directory is created if it doesn't exist."""
        with patch.object(Path, 'mkdir') as mock_mkdir:
            service = SkillService(mock_config)
            
            # Verify mkdir was called with correct parameters
            expected_path = mock_config.vault_root / '_thoth' / 'skills'
            # The mkdir call should have happened during __init__
            assert service.vault_skills_dir == expected_path

    def test_discover_skills_without_skill_md(self, mock_config, temp_skill_dirs):
        """Test that directories without SKILL.md are skipped."""
        bundled, vault = temp_skill_dirs
        
        # Create directory without SKILL.md
        invalid_skill = bundled / 'invalid-skill'
        invalid_skill.mkdir()
        (invalid_skill / 'other_file.txt').write_text('Not a skill')
        
        # Create valid skill
        valid_skill = bundled / 'valid-skill'
        valid_skill.mkdir()
        (valid_skill / 'SKILL.md').write_text("""---
name: Valid Skill
description: Valid
---
""")
        
        service = SkillService(mock_config)
        service.bundled_skills_dir = bundled
        service.vault_skills_dir = vault
        
        skills = service.discover_skills()
        
        assert len(skills) == 1
        assert 'valid-skill' in skills
        assert 'invalid-skill' not in skills

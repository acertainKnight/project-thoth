#!/usr/bin/env python3
"""Quick test script to verify vault settings.json configuration loading."""

import os
import sys
from pathlib import Path

# Set environment to point to vault
os.environ['THOTH_SETTINGS_FILE'] = (
    '/mnt/c/Users/nghal/Documents/Obsidian Vault/_thoth/settings.json'
)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))


def test_config_loading():
    """Test that configuration loads correctly from vault settings."""
    print('=' * 80)
    print('Testing Vault Settings Configuration Loading')
    print('=' * 80)

    try:
        from thoth.utilities.config import load_config

        print('\n1. Loading configuration from vault settings.json...')
        config = load_config()
        print('✅ Configuration loaded successfully!')

        print('\n2. Checking workspace directory...')
        print(f'   Workspace Dir: {config.workspace_dir}')
        print(f'   Exists: {config.workspace_dir.exists()}')

        print('\n3. Checking templates directory...')
        print(f'   Templates Dir: {config.templates_dir}')
        print(f'   Exists: {config.templates_dir.exists()}')

        template_file = config.templates_dir / 'obsidian_note.md'
        print(f'   Template File: {template_file}')
        print(f'   Exists: {template_file.exists()}')

        if template_file.exists():
            print('   ✅ Template file found!')
        else:
            print('   ❌ Template file NOT found!')
            return False

        print('\n4. Checking other critical paths...')
        paths_to_check = {
            'PDF Dir': config.pdf_dir,
            'Markdown Dir': config.markdown_dir,
            'Notes Dir': config.notes_dir,
            'Prompts Dir': config.prompts_dir,
            'Output Dir': config.output_dir,
            'Knowledge Base': config.knowledge_base_dir,
        }

        for name, path in paths_to_check.items():
            print(f'   {name}: {path}')
            print(f'      Exists: {path.exists()}, Absolute: {path.is_absolute()}')

        print('\n5. Testing NoteService initialization...')
        from thoth.services.note_service import NoteService

        note_service = NoteService(config=config)
        print(f'   NoteService templates_dir: {note_service.templates_dir}')
        print(
            f'   Jinja env loader searchpath: {note_service.jinja_env.loader.searchpath}'
        )

        # Try to get the template
        try:
            _ = note_service.jinja_env.get_template('obsidian_note.md')
            print('   ✅ NoteService can load template!')
        except Exception as e:
            print(f'   ❌ NoteService CANNOT load template: {e}')
            return False

        print('\n' + '=' * 80)
        print('✅ ALL TESTS PASSED!')
        print('=' * 80)
        return True

    except Exception as e:
        print(f'\n❌ ERROR: {e}')
        import traceback

        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_config_loading()
    sys.exit(0 if success else 1)

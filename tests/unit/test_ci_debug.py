"""
Debug test to help diagnose CI failures.

This test outputs environment information and will help us understand
why tests pass locally but fail in CI.
"""

import os
import sys
from pathlib import Path


def test_ci_environment_debug():
    """Output diagnostic information about the CI environment."""
    info = []
    info.append('=' * 80)
    info.append('CI ENVIRONMENT DIAGNOSTIC')
    info.append('=' * 80)
    info.append(f'Python version: {sys.version}')
    info.append(f'Python executable: {sys.executable}')
    info.append(f'Current working directory: {os.getcwd()}')
    info.append('')
    info.append('Environment variables:')
    for key in sorted(os.environ.keys()):
        if 'THOTH' in key or 'OBSIDIAN' in key or 'VAULT' in key:
            info.append(f'  {key}={os.environ[key]}')
    info.append('')
    info.append('Key paths:')
    info.append(f'  tests/ exists: {Path("tests").exists()}')
    info.append(f'  tests/fixtures/ exists: {Path("tests/fixtures").exists()}')
    info.append(f'  src/thoth/ exists: {Path("src/thoth").exists()}')
    info.append('')

    # Try importing config
    try:
        from thoth.config import config

        info.append('✅ Config import: SUCCESS')
        info.append(f'  Vault root: {config.vault_root}')
    except Exception as e:
        info.append('❌ Config import: FAILED')
        info.append(f'  Error: {type(e).__name__}: {e}')

    info.append('=' * 80)

    # Print all info
    message = '\n'.join(info)
    print(message)

    # Always pass so we can see the output
    assert True, message

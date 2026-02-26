"""Shared fixtures for router unit tests."""

from pathlib import Path

import pytest

from thoth.auth.context import UserContext


@pytest.fixture
def mock_user_context() -> UserContext:
    """Provide a default mock UserContext for authenticated endpoints."""
    return UserContext(
        user_id='test-user-id-0000',
        username='testuser',
        vault_path=Path('/tmp/test-vault'),
        is_admin=False,
        settings=None,
    )

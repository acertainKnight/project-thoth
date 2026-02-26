"""
User context dataclass for request-scoped user information.

This module provides the UserContext that flows through the entire
request lifecycle, ensuring all operations are scoped to the correct user.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from thoth.config import Settings


@dataclass
class UserContext:
    """
    User context for request-scoped operations.

    Carries user identity, vault information, and user-specific settings
    through the request lifecycle from middleware -> routes -> services -> repositories.

    Args:
        user_id: Unique user identifier (UUID string)
        username: Human-readable username
        vault_path: Absolute path to this user's vault directory on server
        is_admin: Whether the user has admin privileges
        settings: User-specific Settings object (multi-user mode only)

    Example:
        >>> ctx = UserContext(
        ...     user_id='550e8400-e29b-41d4-a716-446655440000',
        ...     username='alice',
        ...     vault_path=Path('/vaults/alice'),
        ...     is_admin=False,
        ...     settings=user_settings,
        ... )
    """

    user_id: str
    username: str
    vault_path: Path
    is_admin: bool = False
    settings: Settings | None = None  # Per-user settings in multi-user mode

    def to_dict(self) -> dict[str, str | bool]:
        """
        Convert context to JSON-serializable dict.

        Returns:
            Dict with user_id, username, vault_path (as string), is_admin

        Note:
            settings is intentionally excluded from serialization
        """
        return {
            'user_id': self.user_id,
            'username': self.username,
            'vault_path': str(self.vault_path),
            'is_admin': self.is_admin,
        }

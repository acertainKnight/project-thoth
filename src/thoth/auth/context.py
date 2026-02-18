"""
User context dataclass for request-scoped user information.

This module provides the UserContext that flows through the entire
request lifecycle, ensuring all operations are scoped to the correct user.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class UserContext:
    """
    User context for request-scoped operations.

    Carries user identity and vault information through the request
    lifecycle from middleware -> routes -> services -> repositories.

    Args:
        user_id: Unique user identifier (UUID string)
        username: Human-readable username
        vault_path: Absolute path to this user's vault directory on server
        is_admin: Whether the user has admin privileges

    Example:
        >>> ctx = UserContext(
        ...     user_id='550e8400-e29b-41d4-a716-446655440000',
        ...     username='alice',
        ...     vault_path=Path('/vaults/alice'),
        ...     is_admin=False,
        ... )
    """

    user_id: str
    username: str
    vault_path: Path
    is_admin: bool = False

    def to_dict(self) -> dict[str, str | bool]:
        """
        Convert context to JSON-serializable dict.

        Returns:
            Dict with user_id, username, vault_path (as string), is_admin
        """
        return {
            'user_id': self.user_id,
            'username': self.username,
            'vault_path': str(self.vault_path),
            'is_admin': self.is_admin,
        }

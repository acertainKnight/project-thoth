"""
User data models for authentication.

Provides Pydantic models for user management in multi-tenant deployments.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class User(BaseModel):
    """
    User model representing an authenticated Thoth user.

    Each user has their own isolated vault directory, database records,
    and Letta agents in a multi-tenant deployment.

    Args:
        id: Unique user identifier
        username: Unique username for login and identification
        email: Optional email address for user contact
        api_token: Long-lived API token for authentication (Bearer token)
        vault_path: Relative path from vaults root to user's vault directory
        orchestrator_agent_id: Letta agent ID for orchestrator agent
        analyst_agent_id: Letta agent ID for research analyst agent
        is_admin: Whether user has admin privileges
        is_active: Whether user account is active
        created_at: Account creation timestamp
        updated_at: Last update timestamp

    Example:
        >>> user = User(
        ...     id=UUID('550e8400-e29b-41d4-a716-446655440000'),
        ...     username='alice',
        ...     email='alice@example.com',
        ...     api_token='thoth_abc123...',
        ...     vault_path='alice',
        ...     is_admin=False,
        ...     is_active=True,
        ...     created_at=datetime.now(),
        ...     updated_at=datetime.now(),
        ... )
    """

    id: UUID
    username: str = Field(min_length=3, max_length=50)
    email: str | None = None
    api_token: str
    vault_path: str
    orchestrator_agent_id: str | None = None
    analyst_agent_id: str | None = None
    is_admin: bool = False
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True


class UserCreate(BaseModel):
    """
    Request model for user creation.

    Args:
        username: Desired username (3-50 chars, unique)
        email: Optional email address

    Example:
        >>> create_req = UserCreate(username='alice', email='alice@example.com')
    """

    username: str = Field(min_length=3, max_length=50)
    email: str | None = None


class UserResponse(BaseModel):
    """
    Response model for user registration/creation.

    Returns the user ID and API token for authentication.

    Args:
        user_id: UUID of created user
        username: Username
        api_token: Generated API token (Bearer token)

    Example:
        >>> resp = UserResponse(
        ...     user_id='550e8400-e29b-41d4-a716-446655440000',
        ...     username='alice',
        ...     api_token='thoth_abc123...',
        ... )
    """

    user_id: str
    username: str
    api_token: str


class UserInfo(BaseModel):
    """
    Public user information model (no sensitive data).

    Args:
        id: User ID
        username: Username
        email: Email address if provided
        vault_path: Relative vault path
        orchestrator_agent_id: Letta orchestrator agent ID (for plugin agent resolution)
        analyst_agent_id: Letta analyst agent ID
        is_admin: Admin status
        is_active: Active status
        created_at: Creation timestamp
    """

    id: str
    username: str
    email: str | None = None
    vault_path: str
    orchestrator_agent_id: str | None = None
    analyst_agent_id: str | None = None
    is_admin: bool
    is_active: bool
    created_at: datetime | None = None

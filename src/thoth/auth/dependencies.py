"""
FastAPI dependencies for user context injection.

Provides dependency injection for routes to access the authenticated
user's context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from fastapi import Request

    from thoth.auth.context import UserContext


async def get_user_context(request: Request) -> UserContext:
    """
    FastAPI dependency for injecting UserContext into route handlers.

    Extracts the user context from request.state (populated by middleware).

    Args:
        request: FastAPI request object

    Returns:
        UserContext for the authenticated user

    Raises:
        HTTPException: 401 if no user context available

    Example:
        >>> @router.get('/papers')
        >>> async def list_papers(
        ...     user_context: UserContext = Depends(get_user_context),
        ... ):
        ...     return await paper_service.list_all(user_context.user_id)
    """
    user_context: UserContext | None = getattr(request.state, 'user_context', None)

    if user_context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication required',
        )

    return user_context

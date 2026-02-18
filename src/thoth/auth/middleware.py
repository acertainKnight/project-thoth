"""
FastAPI middleware for token-based authentication.

Extracts Bearer tokens from requests and populates request state
with user context for multi-tenant routing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from thoth.auth.context import UserContext
from thoth.auth.service import AuthService

if TYPE_CHECKING:
    from starlette.responses import Response
    from starlette.types import ASGIApp


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for token-based authentication.

    In multi-user mode (THOTH_MULTI_USER=true):
    - Extracts Bearer token from Authorization header
    - Looks up user and populates request.state.user_context
    - Returns 401 if token is invalid or missing (except exempt routes)

    In single-user mode (default):
    - Skips authentication
    - Populates request.state.user_context with default_user

    Args:
        app: ASGI application
        auth_service: Authentication service for token validation
        vaults_root: Root directory for user vaults (multi-user mode)
        vault_root: Single vault directory (single-user mode)

    Example:
        >>> app.add_middleware(
        ...     TokenAuthMiddleware,
        ...     auth_service=auth_service,
        ...     vaults_root=Path('/vaults'),
        ...     vault_root=Path('/vault'),
        ... )
    """

    EXEMPT_PATHS: ClassVar[set[str]] = {'/health', '/auth/register', '/auth/me'}

    def __init__(
        self,
        app: ASGIApp,
        auth_service: AuthService,
        vaults_root: Path | None = None,
        vault_root: Path | None = None,
    ):
        """
        Initialize middleware.

        Args:
            app: ASGI application
            auth_service: Auth service for token validation
            vaults_root: Root directory for user vaults (multi-user)
            vault_root: Single vault directory (single-user)
        """
        super().__init__(app)
        self.auth_service = auth_service
        self.vaults_root = vaults_root
        self.vault_root = vault_root
        self.multi_user = os.getenv('THOTH_MULTI_USER', 'false').lower() == 'true'

    def _is_exempt(self, path: str) -> bool:
        """
        Check if request path is exempt from authentication.

        Args:
            path: Request path

        Returns:
            True if path should skip auth
        """
        return any(path.startswith(exempt) for exempt in self.EXEMPT_PATHS)

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request and inject user context.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            Response from downstream handlers
        """
        if not self.multi_user:
            request.state.user_context = UserContext(
                user_id='default_user',
                username='default',
                vault_path=self.vault_root or Path('/vault'),
                is_admin=True,
            )
            return await call_next(request)

        if self._is_exempt(request.url.path):
            request.state.user_context = None
            return await call_next(request)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            logger.warning(
                f'Missing or invalid Authorization header for {request.url.path}'
            )
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=401,
                content={'error': 'Missing or invalid authorization header'},
            )

        token = auth_header[7:]

        if not self.vaults_root:
            logger.error('THOTH_VAULTS_ROOT not configured in multi-user mode')
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=500,
                content={'error': 'Server configuration error'},
            )

        auth_service = self.auth_service
        if auth_service is None:
            logger.error('AuthService not initialized')
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=500,
                content={'error': 'Authentication service not available'},
            )

        user_context = await auth_service.get_user_context_from_token(
            token, self.vaults_root
        )

        if not user_context:
            logger.warning(f'Invalid token for {request.url.path}')
            from starlette.responses import JSONResponse

            return JSONResponse(status_code=401, content={'error': 'Invalid token'})

        request.state.user_context = user_context
        logger.debug(f'Authenticated as {user_context.username}')

        return await call_next(request)

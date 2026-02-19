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
from starlette.responses import JSONResponse

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

    EXEMPT_PATHS: ClassVar[set[str]] = {'/health', '/auth/register'}

    def __init__(
        self,
        app: ASGIApp,
        auth_service: AuthService | None = None,
        vaults_root: Path | None = None,
        vault_root: Path | None = None,
        multi_user: bool | None = None,
    ):
        """
        Initialize middleware.

        auth_service may be None at creation time (before lifespan runs).
        The middleware lazily resolves it from request.app.state.service_manager
        on first dispatch so it always uses the live service.

        Args:
            app: ASGI application
            auth_service: Auth service for token validation (optional at init)
            vaults_root: Root directory for user vaults (multi-user)
            vault_root: Single vault directory (single-user)
            multi_user: Override for multi-user mode (uses THOTH_MULTI_USER env
                var at dispatch time when None)
        """
        super().__init__(app)
        self._auth_service = auth_service
        self.vaults_root = vaults_root
        self.vault_root = vault_root
        # None = read from THOTH_MULTI_USER env var lazily at dispatch time
        self._multi_user_override: bool | None = multi_user

    def _resolve_auth_service(self, request) -> AuthService | None:
        """
        Resolve AuthService, preferring live service from app state.

        Args:
            request: Incoming request (has access to app.state)

        Returns:
            AuthService instance or None
        """
        service_manager = getattr(getattr(request, 'app', None), 'state', None)
        if service_manager:
            sm = getattr(service_manager, 'service_manager', None)
            if sm and hasattr(sm, 'auth'):
                return sm.auth
        return self._auth_service

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
        if self._multi_user_override is not None:
            multi_user = self._multi_user_override
        else:
            multi_user = os.getenv('THOTH_MULTI_USER', 'false').lower() == 'true'
        if not multi_user:
            request.state.user_context = UserContext(
                user_id='default_user',
                username='default_user',
                vault_path=self.vault_root or Path('/vault'),
                is_admin=True,
            )
            return await call_next(request)

        if self._is_exempt(request.url.path):
            # Exempt endpoints (health, register) get default_user context
            # so route handlers always have a valid context object.
            request.state.user_context = UserContext(
                user_id='default_user',
                username='default_user',
                vault_path=self.vault_root or Path('/vault'),
                is_admin=True,
            )
            return await call_next(request)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            logger.warning(
                f'Missing or invalid Authorization header for {request.url.path}'
            )
            return JSONResponse(
                status_code=401,
                content={'error': 'Missing or invalid authorization header'},
            )

        token = auth_header[7:]

        if not self.vaults_root:
            logger.error('THOTH_VAULTS_ROOT not configured in multi-user mode')
            return JSONResponse(
                status_code=500,
                content={'error': 'Server configuration error'},
            )

        auth_service = self._resolve_auth_service(request)
        if auth_service is None:
            logger.error('AuthService not initialized')
            return JSONResponse(
                status_code=500,
                content={'error': 'Authentication service not available'},
            )

        user_context = await auth_service.get_user_context_from_token(
            token, self.vaults_root
        )

        if not user_context:
            logger.warning(f'Invalid token for {request.url.path}')
            return JSONResponse(status_code=401, content={'error': 'Invalid token'})

        # Load user-specific settings in multi-user mode
        from thoth.config import config

        if config.multi_user and config.user_config_manager:
            try:
                user_context.settings = config.user_config_manager.get_settings(
                    user_context.username
                )
            except FileNotFoundError:
                logger.warning(
                    f"Settings not found for user '{user_context.username}', "
                    f'using server defaults'
                )
                # Continue with None settings - services will fall back to server config

        request.state.user_context = user_context
        logger.debug(f'Authenticated as {user_context.username}')

        return await call_next(request)

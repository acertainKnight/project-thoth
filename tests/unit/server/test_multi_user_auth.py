"""
Unit tests for multi-user authentication: AuthService, TokenAuthMiddleware,
and UserContext dependency injection.

These tests use mocked database calls so they run without a live PostgreSQL
instance. Integration tests in tests/integration/ cover real DB flows.
"""

from __future__ import annotations

import os
from datetime import UTC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from thoth.auth.context import UserContext
from thoth.auth.middleware import TokenAuthMiddleware
from thoth.auth.models import User
from thoth.auth.service import AuthService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user() -> User:
    """Sample User object returned by AuthService lookups."""
    import uuid
    from datetime import datetime

    return User(
        id=uuid.uuid4(),
        username='alice',
        email='alice@example.com',
        api_token='thoth_test_token_abc123',
        vault_path='/vaults/alice',
        orchestrator_agent_id='agent-orch-alice',
        analyst_agent_id='agent-ana-alice',
        is_admin=False,
        is_active=True,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


@pytest.fixture
def mock_postgres():
    """Mock PostgresService with async fetch/execute methods."""
    pg = MagicMock()
    pg.fetchrow = AsyncMock(return_value=None)
    pg.fetch = AsyncMock(return_value=[])
    pg.execute = AsyncMock(return_value=None)
    return pg


@pytest.fixture
def auth_service(mock_postgres) -> AuthService:
    """AuthService wired to mock postgres."""
    return AuthService(postgres=mock_postgres)


# ---------------------------------------------------------------------------
# AuthService unit tests
# ---------------------------------------------------------------------------


class TestAuthService:
    """Tests for token generation, user creation, and lookup."""

    def test_generate_token_format(self, auth_service: AuthService):
        """Token must start with 'thoth_' and be reasonably long."""
        token = auth_service.generate_token()
        assert token.startswith('thoth_')
        assert len(token) > 20

    def test_generate_token_unique(self, auth_service: AuthService):
        """Each call produces a different token."""
        tokens = {auth_service.generate_token() for _ in range(100)}
        assert len(tokens) == 100, 'Token collision detected'

    @pytest.mark.asyncio
    async def test_get_user_by_token_returns_none_for_missing(
        self, auth_service: AuthService, mock_postgres
    ):
        """Returns None when token is not found in DB."""
        mock_postgres.fetchrow.return_value = None
        user = await auth_service.get_user_by_token('thoth_nonexistent')
        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_token_returns_user(
        self, auth_service: AuthService, mock_postgres, mock_user: User
    ):
        """Returns a User object when token matches."""
        mock_postgres.fetchrow.return_value = {
            'id': str(mock_user.id),
            'username': mock_user.username,
            'email': mock_user.email,
            'api_token': mock_user.api_token,
            'vault_path': mock_user.vault_path,
            'orchestrator_agent_id': mock_user.orchestrator_agent_id,
            'analyst_agent_id': mock_user.analyst_agent_id,
            'is_admin': mock_user.is_admin,
            'is_active': mock_user.is_active,
            'created_at': mock_user.created_at,
            'updated_at': mock_user.updated_at,
        }
        user = await auth_service.get_user_by_token(mock_user.api_token)
        assert user is not None
        assert user.username == 'alice'
        assert user.orchestrator_agent_id == 'agent-orch-alice'

    @pytest.mark.asyncio
    async def test_get_user_context_from_token(
        self, auth_service: AuthService, mock_postgres, mock_user: User
    ):
        """get_user_context_from_token returns a UserContext with correct fields."""
        mock_postgres.fetchrow.return_value = {
            'id': str(mock_user.id),
            'username': mock_user.username,
            'email': mock_user.email,
            'api_token': mock_user.api_token,
            'vault_path': mock_user.vault_path,
            'orchestrator_agent_id': mock_user.orchestrator_agent_id,
            'analyst_agent_id': mock_user.analyst_agent_id,
            'is_admin': mock_user.is_admin,
            'is_active': True,
            'created_at': mock_user.created_at,
            'updated_at': mock_user.updated_at,
        }
        ctx = await auth_service.get_user_context_from_token(
            mock_user.api_token, Path('/vaults')
        )
        assert ctx is not None
        assert ctx.username == 'alice'
        # vault_path stored in DB is '/vaults/alice' (absolute), so path join
        # yields Path('/vaults/alice') — absolute path on RHS wins in Path division
        assert ctx.vault_path == Path('/vaults/alice')
        assert ctx.is_admin is False

    @pytest.mark.asyncio
    async def test_get_user_context_inactive_user_returns_none(
        self, auth_service: AuthService, mock_postgres
    ):
        """Inactive users are rejected (context is None).

        get_user_by_token uses 'AND is_active = TRUE' in its SQL, so an
        inactive user returns no row — the DB mock returns None to simulate this.
        """
        # Simulate DB returning no row (the SQL filters out inactive users)
        mock_postgres.fetchrow.return_value = None
        ctx = await auth_service.get_user_context_from_token(
            'thoth_inactive_token', Path('/vaults')
        )
        assert ctx is None


# ---------------------------------------------------------------------------
# UserContext tests
# ---------------------------------------------------------------------------


class TestUserContext:
    """Tests for the UserContext dataclass."""

    def test_to_dict(self):
        ctx = UserContext(
            user_id='alice-uuid',
            username='alice',
            vault_path=Path('/vaults/alice'),
            is_admin=False,
        )
        d = ctx.to_dict()
        assert d['username'] == 'alice'
        assert d['vault_path'] == '/vaults/alice'
        assert d['is_admin'] is False

    def test_default_user_context(self):
        """default_user context is used in single-user mode."""
        ctx = UserContext(
            user_id='default_user',
            username='default_user',
            vault_path=Path('/vault'),
            is_admin=True,
        )
        assert ctx.user_id == 'default_user'


# ---------------------------------------------------------------------------
# Middleware tests (via FastAPI TestClient for proper ASGI lifecycle)
# ---------------------------------------------------------------------------


def _build_client(
    multi_user: bool, mock_auth=None, raise_server_exceptions: bool = True
):
    """
    Build a FastAPI TestClient with TokenAuthMiddleware under env patch.

    The client must be created inside the patch context so Starlette
    builds the middleware stack (which reads THOTH_MULTI_USER) correctly.
    """
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient

    inner = FastAPI()

    @inner.get('/chat')
    async def chat_ep(request: Request):
        ctx = getattr(request.state, 'user_context', None)
        return JSONResponse({'username': ctx.username if ctx else None})

    @inner.get('/health')
    async def health_ep(request: Request):
        ctx = getattr(request.state, 'user_context', None)
        return JSONResponse({'username': ctx.username if ctx else None})

    if mock_auth:
        mock_sm = MagicMock()
        mock_sm.auth = mock_auth
        inner.state.service_manager = mock_sm

    inner.add_middleware(
        TokenAuthMiddleware,
        multi_user=multi_user,
        auth_service=mock_auth,  # pass directly so lazy resolution isn't needed
        vaults_root=Path('/vaults') if multi_user else None,
    )
    return TestClient(inner, raise_server_exceptions=raise_server_exceptions)


class TestTokenAuthMiddleware:
    """Tests for TokenAuthMiddleware behavior in single-user and multi-user modes."""

    def test_single_user_mode_sets_default_context(self):
        """In single-user mode, middleware sets default_user context without auth."""
        client = _build_client(multi_user=False)
        resp = client.get('/chat')
        assert resp.status_code == 200
        assert resp.json()['username'] == 'default_user'

    def test_exempt_paths_skip_auth(self):
        """Health endpoint is exempt: gets default_user context in multi-user mode."""
        client = _build_client(multi_user=True, raise_server_exceptions=False)
        resp = client.get('/health')  # no token
        assert resp.status_code == 200
        assert resp.json()['username'] == 'default_user'

    def test_multi_user_missing_token_returns_401(self):
        """In multi-user mode, a request without a Bearer token gets 401."""
        client = _build_client(multi_user=True, raise_server_exceptions=False)
        resp = client.get('/chat')  # no token
        assert resp.status_code == 401

    def test_multi_user_valid_token_sets_context(self, mock_user: User):
        """Valid token in multi-user mode resolves to the correct UserContext."""
        user_ctx = UserContext(
            user_id=str(mock_user.id),
            username=mock_user.username,
            vault_path=Path(mock_user.vault_path),
            is_admin=mock_user.is_admin,
        )
        mock_auth = AsyncMock()
        mock_auth.get_user_context_from_token.return_value = user_ctx

        client = _build_client(multi_user=True, mock_auth=mock_auth)
        resp = client.get('/chat', headers={'Authorization': 'Bearer thoth_test'})

        assert resp.status_code == 200
        assert resp.json()['username'] == 'alice'


# ---------------------------------------------------------------------------
# Config multi-user tests
# ---------------------------------------------------------------------------


class TestConfigMultiUser:
    """Tests for Config.resolve_user_vault_path."""

    def test_resolve_user_vault_path_single_user(self, tmp_path: Path):
        """In single-user mode, returns vault_root regardless of username."""
        with patch.dict(
            os.environ,
            {
                'THOTH_MULTI_USER': 'false',
                'OBSIDIAN_VAULT_PATH': str(tmp_path),
                'THOTH_DISABLE_AUTODETECT': '1',
            },
        ):
            # Reset singleton
            from thoth.config import Config

            Config._instance = None
            Config._instance = None

            try:
                cfg = Config()
                cfg.multi_user = False
                cfg.vaults_root = None
                cfg.vault_root = tmp_path

                result = cfg.resolve_user_vault_path('alice')
                assert result == tmp_path
            finally:
                Config._instance = None

    def test_resolve_user_vault_path_multi_user(self, tmp_path: Path):
        """In multi-user mode, returns vaults_root / username."""
        with patch.dict(
            os.environ,
            {
                'THOTH_MULTI_USER': 'true',
                'THOTH_VAULTS_ROOT': str(tmp_path),
                'OBSIDIAN_VAULT_PATH': str(tmp_path),
                'THOTH_DISABLE_AUTODETECT': '1',
            },
        ):
            from thoth.config import Config

            Config._instance = None
            try:
                cfg = Config()
                result = cfg.resolve_user_vault_path('alice')
                assert result == tmp_path / 'alice'
            finally:
                Config._instance = None

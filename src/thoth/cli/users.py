"""
User management CLI commands for multi-user Thoth deployments.

Provides admin commands to create, list, deactivate, and reset tokens
for users in multi-user mode. These commands connect directly to the
database. Agent initialization requires the Letta server to be running.

Usage:
    thoth users create <username> [--email EMAIL] [--admin] [--skip-agents]
    thoth users list
    thoth users reset-token <username>
    thoth users deactivate <username>
    thoth users info <username>
    thoth users sync-agents [--username USERNAME]
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path


def _get_database_url() -> str:
    """Get database URL from configuration or environment."""
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url

    try:
        from thoth.config import config

        if hasattr(config, 'secrets') and hasattr(config.secrets, 'database_url'):
            return config.secrets.database_url
    except Exception:
        pass

    return 'postgresql://thoth:thoth_password@localhost:5432/thoth'


async def _get_auth_service():
    """Build a minimal auth service connected to the database."""
    import asyncpg

    from thoth.auth.service import AuthService

    database_url = _get_database_url()

    class _MinimalPostgres:
        """Thin wrapper providing fetchrow/execute for AuthService."""

        def __init__(self, conn):
            self._conn = conn

        async def fetchrow(self, query: str, *args):
            return await self._conn.fetchrow(query, *args)

        async def fetch(self, query: str, *args):
            return await self._conn.fetch(query, *args)

        async def execute(self, query: str, *args):
            return await self._conn.execute(query, *args)

    conn = await asyncpg.connect(database_url)
    postgres = _MinimalPostgres(conn)
    return AuthService(postgres=postgres), conn


async def _initialize_user_agents(
    username: str,
    user_id: str,
    vault_path: Path,
    auth_service,
    existing_agent_ids: dict[str, str] | None = None,
) -> None:
    """
    Create or update Letta agents for a user and store their IDs in the DB.

    When ``existing_agent_ids`` is provided (from the DB), those agents are
    updated in-place preserving memory and conversation history.  New agents
    are only created when the user has none.

    Args:
        username: The user's username (used as agent name suffix for new agents).
        user_id: UUID string for the user record.
        vault_path: Absolute path to the user's vault directory.
        auth_service: AuthService instance for updating agent IDs.
        existing_agent_ids: Optional dict with 'orchestrator' and/or 'analyst'
            keys mapped to Letta agent IDs already assigned to this user.
    """
    from thoth.auth.context import UserContext
    from thoth.services.agent_initialization_service import AgentInitializationService

    svc = AgentInitializationService()
    ctx = UserContext(
        user_id=user_id,
        username=username,
        vault_path=vault_path,
        is_admin=False,
    )

    agent_ids = await svc.initialize_agents_for_user(
        ctx, existing_agent_ids=existing_agent_ids
    )
    if agent_ids:
        await auth_service.update_agent_ids(
            user_id,
            orchestrator_agent_id=agent_ids.get('orchestrator'),
            analyst_agent_id=agent_ids.get('analyst'),
        )
        action = 'Updated' if existing_agent_ids else 'Created'
        print(f'  Orchestrator : {agent_ids.get("orchestrator", "failed")} ({action})')
        print(f'  Analyst      : {agent_ids.get("analyst", "failed")} ({action})')
    else:
        print('  Warning: Agent creation returned no IDs')


async def create_command(args) -> None:
    """
    Create a new user, provision their vault, and initialize Letta agents.

    Args:
        args: Parsed CLI args with username, email, admin, skip_agents
    """
    if os.getenv('THOTH_MULTI_USER', 'false').lower() != 'true':
        print(
            'Warning: THOTH_MULTI_USER is not set to true. '
            'Creating user anyway for future multi-user use.'
        )

    auth_service, conn = await _get_auth_service()
    try:
        existing = await auth_service.get_user_by_username(args.username)
        if existing:
            print(f"Error: Username '{args.username}' already exists.")
            return

        user = await auth_service.create_user(
            username=args.username,
            email=getattr(args, 'email', None),
            is_admin=getattr(args, 'admin', False),
        )

        print()
        print('✓ User created successfully')
        print(f'  Username : {user.username}')
        if user.email:
            print(f'  Email    : {user.email}')
        print(f'  User ID  : {user.id}')
        print(f'  Admin    : {user.is_admin}')
        print()
        print('  API Token (save this — it will not be shown again):')
        print(f'  {user.api_token}')
        print()
        print('  The user should set this token in their Obsidian plugin settings')
        print('  under Settings → Thoth → API Token.')
        print()

        vaults_root = Path(os.getenv('THOTH_VAULTS_ROOT', '/vaults'))

        # Provision vault
        if vaults_root.exists() or os.getenv('THOTH_MULTI_USER', '') == 'true':
            try:
                from thoth.services.vault_provisioner import VaultProvisioner

                provisioner = VaultProvisioner()
                await provisioner.provision_vault(user.username, vaults_root)
                print(f'  Vault provisioned at: {vaults_root / user.username}')
            except Exception as e:
                print(f'  Warning: Could not provision vault: {e}')

        # Initialize Letta agents (unless --skip-agents)
        if not getattr(args, 'skip_agents', False):
            print()
            print('  Initializing Letta agents...')
            try:
                await _initialize_user_agents(
                    username=user.username,
                    user_id=str(user.id),
                    vault_path=vaults_root / user.username,
                    auth_service=auth_service,
                )
                print('  ✓ Agents created')
            except Exception as e:
                print(f'  Warning: Could not create agents: {e}')
                print('  Run `thoth users sync-agents` later when Letta is available.')
        else:
            print('  Skipped agent creation (--skip-agents)')
        print()

    finally:
        await conn.close()


async def list_command(_args) -> None:
    """List all users."""
    auth_service, conn = await _get_auth_service()
    try:
        rows = await auth_service.postgres.fetch(
            """
            SELECT id, username, email, vault_path, is_admin, is_active,
                   orchestrator_agent_id IS NOT NULL AS has_agents,
                   created_at
            FROM users
            ORDER BY created_at
            """
        )

        if not rows:
            print('No users found.')
            return

        print()
        print(f'{"USERNAME":<20} {"ADMIN":<6} {"ACTIVE":<7} {"AGENTS":<7} CREATED')
        print('-' * 70)
        for row in rows:
            created = (
                row['created_at'].strftime('%Y-%m-%d') if row['created_at'] else '-'
            )
            print(
                f'{row["username"]:<20} '
                f'{"yes" if row["is_admin"] else "no":<6} '
                f'{"yes" if row["is_active"] else "no":<7} '
                f'{"yes" if row["has_agents"] else "no":<7} '
                f'{created}'
            )
        print()
        print(f'Total: {len(rows)} user(s)')
    finally:
        await conn.close()


async def reset_token_command(args) -> None:
    """Reset API token for a user."""
    auth_service, conn = await _get_auth_service()
    try:
        user = await auth_service.get_user_by_username(args.username)
        if not user:
            print(f"Error: User '{args.username}' not found.")
            return

        new_token = await auth_service.reset_token(user.id)
        print()
        print(f"✓ Token reset for '{args.username}'")
        print()
        print('  New API Token (save this — it will not be shown again):')
        print(f'  {new_token}')
        print()
        print('  Update the token in the Obsidian plugin settings.')
        print()
    finally:
        await conn.close()


async def deactivate_command(args) -> None:
    """Deactivate a user account."""
    auth_service, conn = await _get_auth_service()
    try:
        user = await auth_service.get_user_by_username(args.username)
        if not user:
            print(f"Error: User '{args.username}' not found.")
            return

        if not user.is_active:
            print(f"User '{args.username}' is already inactive.")
            return

        confirm = input(
            f"Deactivate user '{args.username}'? Their token will stop working. [y/N] "
        )
        if confirm.lower() != 'y':
            print('Aborted.')
            return

        success = await auth_service.deactivate_user(user.id)
        if success:
            print(f"✓ User '{args.username}' deactivated.")
        else:
            print('Error: Deactivation failed.')
    finally:
        await conn.close()


async def info_command(args) -> None:
    """Show detailed info for a user."""
    auth_service, conn = await _get_auth_service()
    try:
        user = await auth_service.get_user_by_username(args.username)
        if not user:
            print(f"Error: User '{args.username}' not found.")
            return

        print()
        print(f'User: {user.username}')
        print(f'  ID              : {user.id}')
        print(f'  Email           : {user.email or "-"}')
        print(f'  Vault path      : {user.vault_path}')
        print(f'  Admin           : {user.is_admin}')
        print(f'  Active          : {user.is_active}')
        print(f'  Orchestrator ID : {user.orchestrator_agent_id or "not initialized"}')
        print(f'  Analyst ID      : {user.analyst_agent_id or "not initialized"}')
        print(f'  Created         : {user.created_at}')
        print(f'  Updated         : {user.updated_at}')
        print()
    finally:
        await conn.close()


async def sync_agents_command(args) -> None:
    """
    Create or update Letta agents for all (or a specific) active user.

    If a user already has agents assigned, those agents are updated in-place
    (tools, system prompt, memory blocks) preserving their conversation
    history.  New agents are only created for users who have none.

    Useful after software updates (to apply new tool configs) or for users
    created with ``--skip-agents``.  Requires Letta to be running.

    Args:
        args: Parsed CLI args with optional username filter.
    """
    auth_service, conn = await _get_auth_service()
    try:
        target_username = getattr(args, 'username', None)

        query = (
            'SELECT id, username, vault_path, '
            '       orchestrator_agent_id, analyst_agent_id '
            'FROM users WHERE is_active = TRUE'
        )
        if target_username:
            query += ' AND username = $1'
            rows = await auth_service.postgres.fetch(query, target_username)
        else:
            query += ' ORDER BY created_at'
            rows = await auth_service.postgres.fetch(query)

        if not rows:
            print('No matching active users found.')
            return

        vaults_root = Path(os.getenv('THOTH_VAULTS_ROOT', '/vaults'))

        synced = 0
        for row in rows:
            username = row['username']

            # Build existing IDs dict from the DB so we update, not recreate
            existing: dict[str, str] = {}
            if row['orchestrator_agent_id']:
                existing['orchestrator'] = row['orchestrator_agent_id']
            if row['analyst_agent_id']:
                existing['analyst'] = row['analyst_agent_id']

            label = 'updating' if existing else 'creating'
            print(f'  {username}: {label} agents...')
            try:
                await _initialize_user_agents(
                    username=username,
                    user_id=str(row['id']),
                    vault_path=vaults_root / row['vault_path'],
                    auth_service=auth_service,
                    existing_agent_ids=existing or None,
                )
                synced += 1
            except Exception as e:
                print(f'  {username}: failed — {e}')

        print()
        print(f'✓ Synced agents for {synced}/{len(rows)} user(s)')

    finally:
        await conn.close()


def configure_subparser(subparsers: argparse._SubParsersAction) -> None:
    """
    Register the 'users' command group with the CLI.

    Args:
        subparsers: Argparse subparsers action to add commands to
    """
    users_parser = subparsers.add_parser('users', help='Manage Thoth users')
    users_subparsers = users_parser.add_subparsers(
        dest='users_command', help='User management command', required=True
    )

    # users create
    create_parser = users_subparsers.add_parser('create', help='Create a new user')
    create_parser.add_argument('username', help='Username (3-50 chars)')
    create_parser.add_argument('--email', help='Email address (optional)')
    create_parser.add_argument(
        '--admin', action='store_true', help='Grant admin privileges'
    )
    create_parser.add_argument(
        '--skip-agents',
        action='store_true',
        help='Skip Letta agent creation (use if Letta is not running)',
    )
    create_parser.set_defaults(
        func=lambda args, _p=None: asyncio.run(create_command(args))
    )

    # users list
    list_parser = users_subparsers.add_parser('list', help='List all users')
    list_parser.set_defaults(func=lambda args, _p=None: asyncio.run(list_command(args)))

    # users reset-token
    reset_parser = users_subparsers.add_parser(
        'reset-token', help='Reset API token for a user'
    )
    reset_parser.add_argument('username', help='Username')
    reset_parser.set_defaults(
        func=lambda args, _p=None: asyncio.run(reset_token_command(args))
    )

    # users deactivate
    deactivate_parser = users_subparsers.add_parser(
        'deactivate', help='Deactivate a user account'
    )
    deactivate_parser.add_argument('username', help='Username')
    deactivate_parser.set_defaults(
        func=lambda args, _p=None: asyncio.run(deactivate_command(args))
    )

    # users info
    info_parser = users_subparsers.add_parser('info', help='Show user details')
    info_parser.add_argument('username', help='Username')
    info_parser.set_defaults(func=lambda args, _p=None: asyncio.run(info_command(args)))

    # users sync-agents
    sync_parser = users_subparsers.add_parser(
        'sync-agents',
        help='Create/update Letta agents for users (run after software updates)',
    )
    sync_parser.add_argument(
        '--username', help='Sync agents for a specific user only (default: all users)'
    )
    sync_parser.set_defaults(
        func=lambda args, _p=None: asyncio.run(sync_agents_command(args))
    )

    # Dispatch from the top-level 'users' parser to the sub-command
    users_parser.set_defaults(func=lambda _args: users_parser.print_help())

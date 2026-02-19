"""
User management CLI commands for multi-user Thoth deployments.

Provides admin commands to create, list, deactivate, and reset tokens
for users in multi-user mode. These commands connect directly to the
database and do not require the server to be running.

Usage:
    thoth users create <username> [--email EMAIL] [--admin]
    thoth users list
    thoth users reset-token <username>
    thoth users deactivate <username>
    thoth users info <username>
"""

from __future__ import annotations

import argparse
import asyncio
import os


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


async def create_command(args) -> None:
    """
    Create a new user and print their API token.

    Args:
        args: Parsed CLI args with username, email, admin
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

        # Provision vault if in multi-user mode
        vaults_root_str = os.getenv('THOTH_VAULTS_ROOT', '/vaults')
        from pathlib import Path

        vaults_root = Path(vaults_root_str)
        if vaults_root.exists() or os.getenv('THOTH_MULTI_USER', '') == 'true':
            try:
                from thoth.services.vault_provisioner import VaultProvisioner

                provisioner = VaultProvisioner()
                await provisioner.provision_vault(user.username, vaults_root)
                print(f'  Vault provisioned at: {vaults_root / user.username}')
            except Exception as e:
                print(f'  Warning: Could not provision vault: {e}')

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
    create_parser.set_defaults(func=lambda args: asyncio.run(create_command(args)))

    # users list
    list_parser = users_subparsers.add_parser('list', help='List all users')
    list_parser.set_defaults(func=lambda args: asyncio.run(list_command(args)))

    # users reset-token
    reset_parser = users_subparsers.add_parser(
        'reset-token', help='Reset API token for a user'
    )
    reset_parser.add_argument('username', help='Username')
    reset_parser.set_defaults(func=lambda args: asyncio.run(reset_token_command(args)))

    # users deactivate
    deactivate_parser = users_subparsers.add_parser(
        'deactivate', help='Deactivate a user account'
    )
    deactivate_parser.add_argument('username', help='Username')
    deactivate_parser.set_defaults(
        func=lambda args: asyncio.run(deactivate_command(args))
    )

    # users info
    info_parser = users_subparsers.add_parser('info', help='Show user details')
    info_parser.add_argument('username', help='Username')
    info_parser.set_defaults(func=lambda args: asyncio.run(info_command(args)))

    # Dispatch from the top-level 'users' parser to the sub-command
    users_parser.set_defaults(func=lambda _args: users_parser.print_help())

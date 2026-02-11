"""
Database management CLI commands.

Provides commands for database migrations, status checks, and maintenance.
"""

import argparse

from loguru import logger

from thoth.config import config
from thoth.migrations.migration_manager import MigrationManager


def _get_database_url() -> str:
    """Get database URL from configuration."""
    # Try to get from config
    if hasattr(config, 'secrets') and hasattr(config.secrets, 'database_url'):
        return config.secrets.database_url

    # Fall back to default
    return 'postgresql://thoth:thoth_password@localhost:5432/thoth'


async def migrate_command(_args) -> None:
    """Run database migrations."""
    database_url = _get_database_url()
    migration_manager = MigrationManager(database_url)

    try:
        logger.info('Checking for pending migrations...')
        success = await migration_manager.initialize_database()

        if success:
            logger.success('Database migrations completed successfully!')
        else:
            logger.error('Database migrations failed')
            exit(1)

    except Exception as e:
        logger.error(f'Migration failed: {e}')
        exit(1)


async def status_command(_args) -> None:
    """Show database migration status."""
    database_url = _get_database_url()
    migration_manager = MigrationManager(database_url)

    try:
        status = await migration_manager.get_migration_status()

        logger.info('=== Database Migration Status ===')
        logger.info(f'Applied migrations: {status["applied_count"]}')
        logger.info(f'Pending migrations: {status["pending_count"]}')

        if status['applied_versions']:
            logger.info(
                f'Applied versions: {", ".join(map(str, status["applied_versions"]))}'
            )

        if status['last_migration']:
            last = status['last_migration']
            logger.info(f'Current version: {last["version"]} ({last["name"]})')
            logger.info(f'Last applied: {last["applied_at"]}')

        if status['pending_migrations']:
            logger.warning('Pending migrations:')
            for version, name in status['pending_migrations']:
                logger.warning(f'- {version:03d}: {name}')
            logger.warning("Run 'thoth db migrate'to apply pending migrations")
        else:
            logger.success('Database is up to date')

    except Exception as e:
        logger.error(f'Failed to get status: {e}')
        exit(1)


async def reset_command(args) -> None:
    """Reset database (DANGEROUS - asks for confirmation)."""
    if not args.confirm:
        logger.error('This will DROP ALL TABLES and re-run migrations!')
        logger.error('Add --confirm flag if you really want to do this')
        exit(1)

    database_url = _get_database_url()

    try:
        import asyncpg

        conn = await asyncpg.connect(database_url)

        logger.warning('Dropping all tables...')

        # Get all tables
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
        """)

        for table in tables:
            table_name = table['tablename']
            logger.info(f'Dropping table: {table_name}')
            await conn.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')

        await conn.close()

        logger.success('All tables dropped')

        # Re-run migrations
        logger.info('Re-running migrations...')
        migration_manager = MigrationManager(database_url)
        success = await migration_manager.initialize_database()

        if success:
            logger.success('Database reset complete!')
        else:
            logger.error('Migration failed after reset')
            exit(1)

    except Exception as e:
        logger.error(f'Reset failed: {e}')
        exit(1)


def configure_subparser(subparsers: argparse._SubParsersAction) -> None:
    """
    Configure the database subcommand parser.

    Args:
        subparsers: Subparsers from main argument parser
    """
    db_parser = subparsers.add_parser(
        'db',
        help='Database management commands',
        description='Manage database schema and migrations',
    )

    db_subparsers = db_parser.add_subparsers(
        dest='db_command', help='Database command to run', required=True
    )

    # Migrate command
    migrate_parser = db_subparsers.add_parser(
        'migrate',
        help='Run pending database migrations',
        description='Apply all pending database schema migrations',
    )
    migrate_parser.set_defaults(func=migrate_command)

    # Status command
    status_parser = db_subparsers.add_parser(
        'status',
        help='Show migration status',
        description='Display current database migration status',
    )
    status_parser.set_defaults(func=status_command)

    # Reset command (dangerous)
    reset_parser = db_subparsers.add_parser(
        'reset',
        help='Reset database (DANGEROUS)',
        description='Drop all tables and re-run migrations. WARNING: ALL DATA WILL BE LOST!',
    )
    reset_parser.add_argument(
        '--confirm', action='store_true', help='Confirm you want to reset the database'
    )
    reset_parser.set_defaults(func=reset_command)

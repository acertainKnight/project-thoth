"""
Database migration manager for Thoth.

Handles versioned SQL migrations with tracking to ensure migrations
are applied exactly once and in order.
"""

import asyncio
from pathlib import Path
from typing import List, Tuple, Optional

from loguru import logger
import asyncpg


class MigrationManager:
    """
    Manages database schema migrations.

    Tracks applied migrations in a special migrations table and ensures
    migrations are applied in order, exactly once.
    """

    def __init__(self, database_url: str):
        """
        Initialize migration manager.

        Args:
            database_url: PostgreSQL connection string
        """
        self.database_url = database_url
        self.migrations_dir = Path(__file__).parent

    async def _get_connection(self) -> asyncpg.Connection:
        """Get a database connection."""
        return await asyncpg.connect(self.database_url)

    async def _ensure_migrations_table(self, conn: asyncpg.Connection) -> None:
        """Create the migrations tracking table if it doesn't exist."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW(),
                checksum TEXT,
                execution_time_ms INTEGER
            )
        """)
        logger.debug("Migrations tracking table ready")

    async def get_applied_migrations(self) -> List[int]:
        """
        Get list of applied migration versions.

        Returns:
            List of migration version numbers that have been applied
        """
        conn = await self._get_connection()
        try:
            await self._ensure_migrations_table(conn)
            rows = await conn.fetch(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
            return [row['version'] for row in rows]
        finally:
            await conn.close()

    async def get_pending_migrations(self) -> List[Tuple[int, Path]]:
        """
        Get list of pending migrations that need to be applied.

        Returns:
            List of (version, file_path) tuples for pending migrations
        """
        applied = await self.get_applied_migrations()

        # Find all .sql files in migrations directory
        migration_files = sorted(self.migrations_dir.glob("*.sql"))

        pending = []
        for migration_file in migration_files:
            # Extract version from filename (e.g., "001_initial.sql" -> 1)
            try:
                version = int(migration_file.stem.split('_')[0])
                if version not in applied:
                    pending.append((version, migration_file))
            except (ValueError, IndexError):
                logger.warning(f"Skipping invalid migration filename: {migration_file.name}")
                continue

        return sorted(pending, key=lambda x: x[0])

    async def apply_migration(
        self,
        version: int,
        migration_file: Path
    ) -> bool:
        """
        Apply a single migration.

        Args:
            version: Migration version number
            migration_file: Path to SQL migration file

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Applying migration {version}: {migration_file.name}")

        # Read migration SQL
        try:
            sql_content = migration_file.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to read migration file {migration_file}: {e}")
            return False

        # Execute migration in a transaction
        conn = await self._get_connection()
        try:
            await self._ensure_migrations_table(conn)

            # Check if already applied (race condition protection)
            existing = await conn.fetchval(
                "SELECT version FROM schema_migrations WHERE version = $1",
                version
            )
            if existing:
                logger.info(f"Migration {version} already applied, skipping")
                return True

            start_time = asyncio.get_event_loop().time()

            # Execute migration SQL
            async with conn.transaction():
                await conn.execute(sql_content)

                # Record migration
                execution_time = int((asyncio.get_event_loop().time() - start_time) * 1000)
                await conn.execute("""
                    INSERT INTO schema_migrations (version, name, execution_time_ms)
                    VALUES ($1, $2, $3)
                """, version, migration_file.stem, execution_time)

            logger.success(
                f"✓ Migration {version} applied successfully ({execution_time}ms)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            return False
        finally:
            await conn.close()

    async def apply_all_pending(self) -> Tuple[int, int]:
        """
        Apply all pending migrations.

        Returns:
            Tuple of (successful_count, failed_count)
        """
        pending = await self.get_pending_migrations()

        if not pending:
            logger.info("No pending migrations")
            return (0, 0)

        logger.info(f"Found {len(pending)} pending migration(s)")

        successful = 0
        failed = 0

        for version, migration_file in pending:
            success = await self.apply_migration(version, migration_file)
            if success:
                successful += 1
            else:
                failed += 1
                logger.error(f"Stopping migration process due to failure at version {version}")
                break  # Stop on first failure

        return (successful, failed)

    async def get_migration_status(self) -> dict:
        """
        Get current migration status.

        Returns:
            Dictionary with migration status information
        """
        applied = await self.get_applied_migrations()
        pending = await self.get_pending_migrations()

        conn = await self._get_connection()
        try:
            await self._ensure_migrations_table(conn)
            last_migration = await conn.fetchrow("""
                SELECT version, name, applied_at, execution_time_ms
                FROM schema_migrations
                ORDER BY version DESC
                LIMIT 1
            """)
        finally:
            await conn.close()

        return {
            'applied_count': len(applied),
            'pending_count': len(pending),
            'applied_versions': applied,
            'pending_migrations': [(v, f.name) for v, f in pending],
            'last_migration': dict(last_migration) if last_migration else None,
            'up_to_date': len(pending) == 0
        }

    async def initialize_database(self) -> bool:
        """
        Initialize database with all migrations.

        This is the main entry point for setup wizard.
        Creates the migrations table and applies all pending migrations.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Initializing database schema...")

            # Check if database is accessible
            conn = await self._get_connection()
            await conn.close()

            # Apply all pending migrations
            successful, failed = await self.apply_all_pending()

            if failed > 0:
                logger.error(f"Database initialization failed: {failed} migration(s) failed")
                return False

            if successful == 0:
                logger.info("Database already up to date")
            else:
                logger.success(f"Database initialized: {successful} migration(s) applied")

            # Show final status
            status = await self.get_migration_status()
            logger.info(f"Database version: {max(status['applied_versions']) if status['applied_versions'] else 0}")

            return True

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False

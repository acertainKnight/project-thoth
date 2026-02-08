"""
PostgreSQL detection and connection testing.

Tests PostgreSQL connectivity, validates pgvector extension, and checks health.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urlparse

from loguru import logger


@dataclass
class PostgreSQLStatus:
    """PostgreSQL connection and status information."""

    connected: bool
    version: str | None
    pgvector_available: bool
    host: str | None
    port: int | None
    database: str | None
    error_message: str | None = None

    @property
    def available(self) -> bool:
        """PostgreSQL is available when connected."""
        return self.connected


class PostgreSQLDetector:
    """Detects and validates PostgreSQL connections."""

    @staticmethod
    def parse_database_url(url: str) -> dict:
        """
        Parse PostgreSQL database URL.

        Args:
            url: Database URL (postgresql://user:pass@host:port/db)

        Returns:
            Dictionary with connection parameters
        """
        parsed = urlparse(url)

        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/') if parsed.path else 'postgres',
            'user': parsed.username or 'postgres',
            'password': parsed.password or '',
        }

    @staticmethod
    async def test_connection(database_url: str, timeout: int = 10) -> PostgreSQLStatus:
        """
        Test PostgreSQL connection asynchronously.

        Args:
            database_url: PostgreSQL connection URL
            timeout: Connection timeout in seconds

        Returns:
            PostgreSQLStatus object with connection results
        """
        try:
            import asyncpg
        except ImportError:
            return PostgreSQLStatus(
                connected=False,
                version=None,
                pgvector_available=False,
                host=None,
                port=None,
                database=None,
                error_message='asyncpg not installed (run: pip install asyncpg)',
            )

        params = PostgreSQLDetector.parse_database_url(database_url)

        try:
            # Attempt connection with timeout
            conn = await asyncio.wait_for(
                asyncpg.connect(
                    host=params['host'],
                    port=params['port'],
                    database=params['database'],
                    user=params['user'],
                    password=params['password'],
                ),
                timeout=timeout,
            )

            try:
                # Get PostgreSQL version
                version_result = await conn.fetchval('SELECT version()')
                version = version_result.split()[1] if version_result else 'unknown'

                # Check for pgvector extension
                pgvector_query = """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_extension WHERE extname = 'vector'
                    )
                """
                pgvector_available = await conn.fetchval(pgvector_query)

                logger.info(
                    f'Connected to PostgreSQL {version} '
                    f'(pgvector: {pgvector_available})'
                )

                return PostgreSQLStatus(
                    connected=True,
                    version=version,
                    pgvector_available=pgvector_available,
                    host=params['host'],
                    port=params['port'],
                    database=params['database'],
                )

            finally:
                await conn.close()

        except TimeoutError:
            return PostgreSQLStatus(
                connected=False,
                version=None,
                pgvector_available=False,
                host=params['host'],
                port=params['port'],
                database=params['database'],
                error_message=f'Connection timeout after {timeout}s',
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f'PostgreSQL connection failed: {error_msg}')

            return PostgreSQLStatus(
                connected=False,
                version=None,
                pgvector_available=False,
                host=params['host'],
                port=params['port'],
                database=params['database'],
                error_message=error_msg,
            )

    @staticmethod
    def test_connection_sync(database_url: str, timeout: int = 10) -> PostgreSQLStatus:
        """
        Test PostgreSQL connection synchronously (wrapper for async version).

        Args:
            database_url: PostgreSQL connection URL
            timeout: Connection timeout in seconds

        Returns:
            PostgreSQLStatus object with connection results
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            PostgreSQLDetector.test_connection(database_url, timeout)
        )

    @staticmethod
    def check_docker_postgres() -> bool:
        """
        Check if PostgreSQL is running in Docker.

        Returns:
            True if PostgreSQL container is running
        """
        try:
            from .docker import DockerDetector

            containers = DockerDetector.list_running_containers()
            return any('postgres' in c['image'].lower() for c in containers)

        except Exception as e:
            logger.error(f'Error checking Docker PostgreSQL: {e}')
            return False

    @staticmethod
    async def create_database(
        admin_url: str, database_name: str, timeout: int = 10
    ) -> tuple[bool, str | None]:
        """
        Create a new database.

        Args:
            admin_url: Admin connection URL (typically postgres database)
            database_name: Name of database to create
            timeout: Operation timeout in seconds

        Returns:
            Tuple of (success, error_message)
        """
        try:
            import asyncpg
        except ImportError:
            return False, 'asyncpg not installed'

        params = PostgreSQLDetector.parse_database_url(admin_url)

        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(
                    host=params['host'],
                    port=params['port'],
                    database='postgres',  # Connect to default database
                    user=params['user'],
                    password=params['password'],
                ),
                timeout=timeout,
            )

            try:
                # Check if database exists
                exists = await conn.fetchval(
                    'SELECT 1 FROM pg_database WHERE datname = $1', database_name
                )

                if exists:
                    logger.info(f'Database {database_name} already exists')
                    return True, None

                # Create database
                await conn.execute(f'CREATE DATABASE {database_name}')
                logger.info(f'Created database: {database_name}')
                return True, None

            finally:
                await conn.close()

        except Exception as e:
            error_msg = f'Failed to create database: {e}'
            logger.error(error_msg)
            return False, error_msg

    @staticmethod
    async def install_pgvector(
        database_url: str, timeout: int = 10
    ) -> tuple[bool, str | None]:
        """
        Install pgvector extension in database.

        Args:
            database_url: Database connection URL
            timeout: Operation timeout in seconds

        Returns:
            Tuple of (success, error_message)
        """
        try:
            import asyncpg
        except ImportError:
            return False, 'asyncpg not installed'

        params = PostgreSQLDetector.parse_database_url(database_url)

        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(
                    host=params['host'],
                    port=params['port'],
                    database=params['database'],
                    user=params['user'],
                    password=params['password'],
                ),
                timeout=timeout,
            )

            try:
                # Check if extension exists
                exists = await conn.fetchval(
                    "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
                )

                if exists:
                    logger.info('pgvector extension already installed')
                    return True, None

                # Install extension
                await conn.execute('CREATE EXTENSION vector')
                logger.info('Installed pgvector extension')
                return True, None

            finally:
                await conn.close()

        except Exception as e:
            error_msg = f'Failed to install pgvector: {e}'
            logger.error(error_msg)
            return False, error_msg

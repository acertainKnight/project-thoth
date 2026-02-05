"""
Database migrations module for Thoth.

Provides schema management and versioned migrations for PostgreSQL.
"""

from thoth.migrations.migration_manager import MigrationManager

__all__ = ['MigrationManager']

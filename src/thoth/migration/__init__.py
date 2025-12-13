"""PostgreSQL migration for Thoth."""

from .migrate import run_migration

__all__ = ["run_migration"]

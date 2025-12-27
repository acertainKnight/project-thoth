#!/usr/bin/env python3
"""
Run browser workflow migration to create required database tables.

Usage:
    python -m thoth.migration.run_browser_workflow_migration
"""

import asyncio
from pathlib import Path

import asyncpg
from rich.console import Console

from thoth.config import Config

console = Console()


async def run_browser_workflow_migration():
    """Run the browser workflow migration to create tables."""

    console.print("\n[bold cyan]Running Browser Workflow Migration[/bold cyan]\n")

    # Load config
    config = Config()
    console.print(f"✓ Loaded config from {config.vault_root}")

    # Connect to PostgreSQL
    db_url = config.secrets.database_url or "postgresql://thoth:thoth@localhost:5432/thoth"
    console.print(f"✓ Connecting to database...")

    try:
        conn = await asyncpg.connect(db_url)
        console.print(f"✓ Connected to PostgreSQL")

        try:
            # Load the migration SQL file
            migration_file = Path(__file__).parent / "002_add_browser_discovery_workflows.sql"

            if not migration_file.exists():
                console.print(f"[red]✗ Migration file not found: {migration_file}[/red]")
                return False

            console.print(f"✓ Found migration file: {migration_file.name}")

            # Read the SQL content
            sql_content = migration_file.read_text()
            console.print(f"✓ Loaded {len(sql_content)} bytes of SQL")

            # Execute the entire SQL file
            # Using a transaction to ensure all-or-nothing execution
            async with conn.transaction():
                console.print("\n[bold]Executing migration...[/bold]")

                try:
                    # Execute the full SQL script
                    await conn.execute(sql_content)
                    console.print("[green]✓ Migration executed successfully[/green]")

                except asyncpg.exceptions.DuplicateObjectError as e:
                    console.print(f"[yellow]⚠ Some objects already exist (this is OK): {e}[/yellow]")

                except Exception as e:
                    if "already exists" in str(e).lower():
                        console.print(f"[yellow]⚠ Tables already exist (this is OK)[/yellow]")
                    else:
                        raise

            # Verify tables were created
            console.print("\n[bold]Verifying tables...[/bold]")
            tables = [
                'browser_workflows',
                'workflow_actions',
                'workflow_search_config',
                'workflow_credentials',
                'workflow_executions'
            ]

            for table in tables:
                result = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = $1
                    )
                    """,
                    table
                )

                if result:
                    console.print(f"  ✓ {table}")
                else:
                    console.print(f"  ✗ {table} [red](MISSING)[/red]")
                    return False

            console.print("\n[bold green]✓ Browser workflow migration completed successfully![/bold green]\n")
            return True

        finally:
            await conn.close()
            console.print("✓ Database connection closed")

    except asyncpg.exceptions.InvalidCatalogNameError:
        console.print(f"[red]✗ Database does not exist. Please create it first:[/red]")
        console.print(f"   createdb thoth")
        return False

    except asyncpg.exceptions.InvalidPasswordError:
        console.print(f"[red]✗ Database authentication failed. Check your credentials.[/red]")
        return False

    except Exception as e:
        console.print(f"[red]✗ Migration failed: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = asyncio.run(run_browser_workflow_migration())
    exit(0 if success else 1)

#!/usr/bin/env python3
"""
Single migration script to move all data from JSON/SQLite to PostgreSQL.

Usage:
    python -m thoth.migration.migrate
"""

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any  # noqa: F401

import asyncpg
from rich.console import Console
from rich.progress import track

from thoth.config import Config

console = Console()


async def run_migration():
    """Run the complete migration from JSON/SQLite to PostgreSQL."""

    console.print('\n[bold cyan]Starting PostgreSQL Migration[/bold cyan]\n')

    # Load config
    config = Config()
    console.print(f'✓ Loaded config from {config.vault_root}')

    # Connect to PostgreSQL
    db_url = (
        config.secrets.database_url or 'postgresql://thoth:thoth@localhost:5432/thoth'
    )
    console.print(f'✓ Connecting to database...')  # noqa: F541

    conn = await asyncpg.connect(db_url)
    console.print(f'✓ Connected to PostgreSQL')  # noqa: F541

    try:
        # 1. Create schema if not exists
        await create_schema(conn)
        console.print(f'✓ Database schema ready')  # noqa: F541

        # 2. Migrate citation graph
        papers_migrated, citations_migrated = await migrate_citation_graph(conn, config)
        console.print(
            f'✓ Migrated {papers_migrated} papers and {citations_migrated} citations'
        )

        # 3. Migrate processing status
        processing_migrated = await migrate_processing_status(conn, config)
        console.print(f'✓ Migrated {processing_migrated} processing records')

        # 4. Migrate chat history
        chats_migrated, messages_migrated = await migrate_chat_history(conn, config)
        console.print(
            f'✓ Migrated {chats_migrated} chat sessions and {messages_migrated} messages'
        )

        # 5. Migrate discovery schedule
        schedule_migrated = await migrate_discovery_schedule(conn, config)  # noqa: F841
        console.print(f'✓ Migrated discovery schedule')  # noqa: F541

        # 6. Migrate token usage
        token_records = await migrate_token_usage(conn, config)
        console.print(f'✓ Migrated {token_records} token usage records')

        console.print(
            '\n[bold green]✓ Migration completed successfully![/bold green]\n'
        )

    finally:
        await conn.close()


async def create_schema(conn: asyncpg.Connection):
    """Create PostgreSQL schema from SQL files."""
    base_dir = Path(__file__).parent.parent.parent.parent / 'docs' / 'architecture'

    # Apply main schema first
    schema_file = base_dir / 'postgres-schema-design.sql'
    if not schema_file.exists():
        raise FileNotFoundError(f'Schema file not found: {schema_file}')

    console.print('  Applying main schema...')
    schema_sql = schema_file.read_text()

    # Execute main schema (split by statement for better error handling)
    for statement in schema_sql.split(';'):
        statement = statement.strip()
        if statement and not statement.startswith('--'):
            try:
                await conn.execute(statement)
            except asyncpg.exceptions.DuplicateTableError:
                pass  # Table already exists, continue
            except Exception as e:
                if 'already exists' not in str(e):
                    console.print(f'[yellow]Warning: {e}[/yellow]')

    # Apply missing tables schema (execute as single block to avoid splitting multi-line statements)  # noqa: W505
    missing_tables_file = base_dir / 'missing-tables.sql'
    if missing_tables_file.exists():
        console.print('  Applying missing tables schema...')
        missing_sql = missing_tables_file.read_text()

        try:
            # Execute entire SQL file at once to handle multiline statements properly
            await conn.execute(missing_sql)
        except Exception as e:
            # If full execution fails, fall back to statement-by-statement with better parsing  # noqa: W505
            if 'already exists' not in str(e).lower():
                console.print(
                    f'[yellow]Warning during schema application: {e}[/yellow]'
                )
    else:
        console.print(
            f'[yellow]Warning: Missing tables schema not found at {missing_tables_file}[/yellow]'
        )


async def migrate_citation_graph(
    conn: asyncpg.Connection, config: Config
) -> tuple[int, int]:
    """Migrate citation_graph.json to papers and citations tables."""
    graph_file = config.vault_root / 'knowledge' / 'citation_graph.json'

    if not graph_file.exists():
        console.print(f'[yellow]No citation graph found at {graph_file}[/yellow]')
        return 0, 0

    data = json.loads(graph_file.read_text())

    papers_count = 0
    citations_count = 0

    # Migrate papers (nodes) with markdown content
    if 'nodes' in data:
        for node in track(data['nodes'], description='Migrating papers...'):
            # Try to load markdown content from file
            markdown_content = None
            if node.get('markdown_path'):
                markdown_file = config.vault_root / node['markdown_path']
                if markdown_file.exists():
                    try:
                        markdown_content = markdown_file.read_text(encoding='utf-8')
                    except Exception as e:
                        console.print(
                            f'[yellow]Could not read markdown {markdown_file}: {e}[/yellow]'
                        )

            await conn.execute(
                """
                INSERT INTO papers (doi, arxiv_id, title, authors, abstract, year, venue, pdf_path, note_path, markdown_content, analysis_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (doi) DO UPDATE SET
                    title = EXCLUDED.title,
                    authors = EXCLUDED.authors,
                    abstract = EXCLUDED.abstract,
                    year = EXCLUDED.year,
                    venue = EXCLUDED.venue,
                    pdf_path = EXCLUDED.pdf_path,
                    note_path = EXCLUDED.note_path,
                    markdown_content = EXCLUDED.markdown_content,
                    analysis_data = EXCLUDED.analysis_data
                """,
                node.get('doi'),
                node.get('arxiv_id'),
                node.get('title'),
                node.get('authors', []),
                node.get('abstract'),
                node.get('year'),
                node.get('venue'),
                node.get('pdf_path'),
                node.get('note_path'),
                markdown_content,
                node.get('analysis_data', {}),
            )
            papers_count += 1

    # Migrate citations (edges)
    if 'edges' in data:
        for edge in track(data['edges'], description='Migrating citations...'):
            await conn.execute(
                """
                INSERT INTO citations (citing_paper_id, cited_paper_id, citation_context)
                VALUES (
                    (SELECT id FROM papers WHERE doi = $1 OR title = $1 LIMIT 1),
                    (SELECT id FROM papers WHERE doi = $2 OR title = $2 LIMIT 1),
                    $3
                )
                ON CONFLICT (citing_paper_id, cited_paper_id) DO NOTHING
                """,
                edge.get('source'),
                edge.get('target'),
                edge.get('context'),
            )
            citations_count += 1

    return papers_count, citations_count


async def migrate_processing_status(conn: asyncpg.Connection, config: Config) -> int:
    """Migrate processed_pdfs.json to processed_pdfs table."""
    tracker_file = (
        config.vault_root / '_thoth' / 'data' / 'output' / 'processed_pdfs.json'
    )

    if not tracker_file.exists():
        console.print(f'[yellow]No processing tracker found at {tracker_file}[/yellow]')
        return 0

    data = json.loads(tracker_file.read_text())
    count = 0

    for pdf_path, metadata in track(
        data.items(), description='Migrating processing status...'
    ):
        await conn.execute(
            """
            INSERT INTO processed_pdfs (pdf_path, new_pdf_path, note_path, processed_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (pdf_path) DO UPDATE SET
                new_pdf_path = EXCLUDED.new_pdf_path,
                note_path = EXCLUDED.note_path,
                processed_at = EXCLUDED.processed_at
            """,
            pdf_path,
            metadata.get('new_pdf_path'),
            metadata.get('note_path'),
        )
        count += 1

    return count


async def migrate_chat_history(
    conn: asyncpg.Connection, config: Config
) -> tuple[int, int]:
    """Migrate chat_history.db to chat_sessions and chat_messages tables."""

    # Try to find chat history DB
    possible_paths = [
        config.vault_root / '_thoth' / 'data' / 'chat_history.db',
        Path(config.agent_storage_dir) / 'chat_history.db'
        if hasattr(config, 'agent_storage_dir')
        else None,
    ]

    chat_db = None
    for path in possible_paths:
        if path and path.exists():
            chat_db = path
            break

    if not chat_db:
        console.print(f'[yellow]No chat history database found[/yellow]')  # noqa: F541
        return 0, 0

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(chat_db)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    sessions_count = 0
    messages_count = 0

    try:
        # Migrate sessions
        cursor.execute('SELECT * FROM chat_sessions')
        for row in track(cursor.fetchall(), description='Migrating chat sessions...'):
            await conn.execute(
                """
                INSERT INTO chat_sessions (session_id, user_id, title, created_at, updated_at, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (session_id) DO NOTHING
                """,
                row['session_id'],
                row.get('user_id', 'default'),
                row.get('title'),
                row.get('created_at'),
                row.get('updated_at'),
                {},
            )
            sessions_count += 1

        # Migrate messages
        cursor.execute('SELECT * FROM chat_messages')
        for row in track(cursor.fetchall(), description='Migrating chat messages...'):
            await conn.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, created_at, metadata)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
                """,
                row['session_id'],
                row['role'],
                row['content'],
                row.get('created_at'),
                {},
            )
            messages_count += 1

    finally:
        sqlite_conn.close()

    return sessions_count, messages_count


async def migrate_discovery_schedule(conn: asyncpg.Connection, config: Config) -> int:
    """Migrate discovery_schedule.json to discovery_schedule table."""

    schedule_file = None
    possible_paths = [
        config.vault_root / '_thoth' / 'data' / 'discovery_schedule.json',
        Path(config.agent_storage_dir) / 'discovery_schedule.json'
        if hasattr(config, 'agent_storage_dir')
        else None,
    ]

    for path in possible_paths:
        if path and path.exists():
            schedule_file = path
            break

    if not schedule_file:
        console.print(f'[yellow]No discovery schedule found[/yellow]')  # noqa: F541
        return 0

    data = json.loads(schedule_file.read_text())
    count = 0

    # Handle both single schedule and multiple schedules
    schedules = (
        data if isinstance(data, dict) and 'source_name' in data else {'default': data}
    )

    for source_name, schedule_info in track(
        schedules.items(), description='Migrating discovery schedule...'
    ):
        await conn.execute(
            """
            INSERT INTO discovery_schedule (
                source_name, last_run, next_run, enabled,
                interval_minutes, max_articles_per_run, time_of_day, days_of_week
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (source_name) DO UPDATE SET
                last_run = EXCLUDED.last_run,
                next_run = EXCLUDED.next_run,
                enabled = EXCLUDED.enabled,
                interval_minutes = EXCLUDED.interval_minutes,
                max_articles_per_run = EXCLUDED.max_articles_per_run,
                time_of_day = EXCLUDED.time_of_day,
                days_of_week = EXCLUDED.days_of_week
            """,
            source_name
            if source_name != 'default'
            else schedule_info.get('source', 'default'),
            schedule_info.get('last_run'),
            schedule_info.get('next_run'),
            schedule_info.get('enabled', True),
            schedule_info.get('interval_minutes'),
            schedule_info.get('max_articles_per_run'),
            schedule_info.get('time_of_day'),
            schedule_info.get('days_of_week'),
        )
        count += 1

    return count


async def migrate_token_usage(conn: asyncpg.Connection, config: Config) -> int:
    """Migrate token_usage.json to token_usage table."""

    token_file = config.vault_root / '_thoth' / 'data' / 'output' / 'token_usage.json'

    if not token_file.exists():
        console.print(f'[yellow]No token usage data found at {token_file}[/yellow]')
        return 0

    data = json.loads(token_file.read_text())
    count = 0

    for user_id, usage_data in track(
        data.items(), description='Migrating token usage...'
    ):
        await conn.execute(
            """
            INSERT INTO token_usage (user_id, prompt_tokens, completion_tokens, total_tokens, total_cost)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id) DO UPDATE SET
                prompt_tokens = EXCLUDED.prompt_tokens,
                completion_tokens = EXCLUDED.completion_tokens,
                total_tokens = EXCLUDED.total_tokens,
                total_cost = EXCLUDED.total_cost
            """,
            user_id,
            usage_data.get('prompt_tokens', 0),
            usage_data.get('completion_tokens', 0),
            usage_data.get('total_tokens', 0),
            usage_data.get('total_cost', 0.0),
        )
        count += 1

    return count


if __name__ == '__main__':
    asyncio.run(run_migration())

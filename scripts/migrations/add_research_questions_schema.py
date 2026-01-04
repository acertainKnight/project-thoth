#!/usr/bin/env python3
"""
Week 1 Migration: Add Research Question Centric Schema

This migration adds the new research-question-centric tables to support
the paradigm shift from source-centric to research-question-centric discovery.

Tables added:
- research_questions: User-defined research questions with search criteria
- available_sources: Master registry of discovery plugins
- research_question_sources: Many-to-many junction table
- article_research_matches: Article-to-question relevance mappings
- discovery_execution_log: Audit trail for discovery runs

Usage:
    uv run python -m thoth.migration.add_research_questions_schema

Or as part of full migration:
    uv run python -m thoth.migration.migrate
"""

import asyncio
from pathlib import Path

import asyncpg
from rich.console import Console

from thoth.config import Config

console = Console()


async def apply_research_question_schema(conn: asyncpg.Connection):
    """Apply research question schema to existing database."""

    console.print(
        '\n[bold cyan]Applying Research Question Schema (Week 1)[/bold cyan]\n'
    )

    # Read the schema file
    schema_file = (
        Path(__file__).parent.parent.parent.parent
        / 'docs'
        / 'architecture'
        / 'research-question-schema.sql'
    )

    if not schema_file.exists():
        console.print(f'[yellow]Schema file not found at {schema_file}[/yellow]')
        console.print('[yellow]Creating inline schema...[/yellow]')
        await create_inline_schema(conn)
        return

    # Apply schema from file
    schema_sql = schema_file.read_text()

    # Execute each statement
    for statement in schema_sql.split(';'):
        statement = statement.strip()
        if statement and not statement.startswith('--'):
            try:
                await conn.execute(statement)
                console.print(f'[green]✓[/green] Executed statement')  # noqa: F541
            except asyncpg.exceptions.DuplicateTableError:
                console.print(f'[yellow]⊙[/yellow] Table already exists')  # noqa: F541
            except Exception as e:
                if 'already exists' in str(e).lower():
                    console.print(f'[yellow]⊙[/yellow] Object already exists')  # noqa: F541
                else:
                    console.print(f'[red]✗[/red] Error: {e}')
                    raise


async def create_inline_schema(conn: asyncpg.Connection):
    """Create research question schema using inline SQL."""

    console.print('  [cyan]Creating research_questions table...[/cyan]')
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS research_questions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,

            -- Search criteria
            keywords TEXT[] DEFAULT '{}',
            topics TEXT[] DEFAULT '{}',
            authors TEXT[] DEFAULT '{}',

            -- Source selection: ['arxiv', 'pubmed'] or ['*'] for ALL
            selected_sources TEXT[] NOT NULL DEFAULT '{*}',

            -- Relevance filtering
            min_relevance_score FLOAT DEFAULT 0.5 CHECK (min_relevance_score >= 0.0 AND min_relevance_score <= 1.0),

            -- Scheduling
            schedule_frequency VARCHAR(50) DEFAULT 'daily' CHECK (schedule_frequency IN ('daily', 'weekly', 'monthly', 'custom')),
            schedule_time TIME DEFAULT '02:00:00',
            schedule_days_of_week INTEGER[] DEFAULT '{1,2,3,4,5,6,7}',
            last_run_at TIMESTAMP,
            next_run_at TIMESTAMP,

            -- Status
            is_active BOOLEAN DEFAULT true,

            -- Auto-download settings
            auto_download_enabled BOOLEAN DEFAULT false,
            auto_download_min_score FLOAT DEFAULT 0.7,

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Constraints
            CONSTRAINT research_questions_user_name_unique UNIQUE (user_id, name)
        );
    """)
    console.print('  [green]✓[/green] research_questions table created')

    console.print('  [cyan]Creating available_sources table...[/cyan]')
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS available_sources (
            name VARCHAR(100) PRIMARY KEY,
            display_name VARCHAR(255) NOT NULL,
            description TEXT,
            source_type VARCHAR(50) NOT NULL,

            -- Capabilities and configuration
            capabilities JSONB DEFAULT '{}',
            default_config JSONB DEFAULT '{}',
            rate_limit_per_minute INTEGER DEFAULT 60,

            -- Health monitoring
            is_active BOOLEAN DEFAULT true,
            last_health_check TIMESTAMP,
            health_status VARCHAR(50) DEFAULT 'unknown',
            error_count INTEGER DEFAULT 0,

            -- Statistics
            total_queries INTEGER DEFAULT 0,
            total_articles_found INTEGER DEFAULT 0,
            avg_response_time_ms FLOAT,

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    console.print('  [green]✓[/green] available_sources table created')

    console.print('  [cyan]Creating research_question_sources junction table...[/cyan]')
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS research_question_sources (
            question_id UUID REFERENCES research_questions(id) ON DELETE CASCADE,
            source_name VARCHAR(100) REFERENCES available_sources(name) ON DELETE CASCADE,

            -- Per-source configuration overrides
            is_enabled BOOLEAN DEFAULT true,
            source_specific_config JSONB DEFAULT '{}',

            -- Statistics
            last_queried_at TIMESTAMP,
            total_queries INTEGER DEFAULT 0,
            total_matches INTEGER DEFAULT 0,

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (question_id, source_name)
        );
    """)
    console.print('  [green]✓[/green] research_question_sources junction table created')

    console.print('  [cyan]Creating article_research_matches table...[/cyan]')
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS article_research_matches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            article_id UUID NOT NULL,
            question_id UUID REFERENCES research_questions(id) ON DELETE CASCADE,

            -- Relevance scoring
            relevance_score FLOAT NOT NULL CHECK (relevance_score >= 0.0 AND relevance_score <= 1.0),

            -- Match details
            matched_keywords TEXT[] DEFAULT '{}',
            matched_topics TEXT[] DEFAULT '{}',
            matched_authors TEXT[] DEFAULT '{}',

            -- Discovery metadata
            discovered_via_source VARCHAR(100) REFERENCES available_sources(name),
            discovery_run_id UUID,

            -- User interaction
            is_viewed BOOLEAN DEFAULT false,
            is_bookmarked BOOLEAN DEFAULT false,
            user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
            user_notes TEXT,

            -- Timestamps
            matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            viewed_at TIMESTAMP,

            -- Constraints
            CONSTRAINT article_research_matches_unique UNIQUE (article_id, question_id)
        );
    """)
    console.print('  [green]✓[/green] article_research_matches table created')

    console.print('  [cyan]Creating discovery_execution_log table...[/cyan]')
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS discovery_execution_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            question_id UUID REFERENCES research_questions(id) ON DELETE CASCADE,

            -- Execution details
            status VARCHAR(50) NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
            started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            duration_seconds FLOAT,

            -- Results
            sources_queried TEXT[] DEFAULT '{}',
            total_articles_found INTEGER DEFAULT 0,
            new_articles INTEGER DEFAULT 0,
            duplicate_articles INTEGER DEFAULT 0,
            relevant_articles INTEGER DEFAULT 0,
            high_relevance_articles INTEGER DEFAULT 0,

            -- Error tracking
            error_message TEXT,
            error_details JSONB,

            -- Performance metrics
            avg_query_time_ms FLOAT,
            total_api_calls INTEGER DEFAULT 0,

            -- Metadata
            triggered_by VARCHAR(50) DEFAULT 'scheduler',
            metadata JSONB DEFAULT '{}'
        );
    """)
    console.print('  [green]✓[/green] discovery_execution_log table created')

    # Create indexes
    console.print('\n  [cyan]Creating indexes for performance...[/cyan]')

    indexes = [
        # research_questions indexes
        ('idx_research_questions_user', 'research_questions', 'user_id'),
        ('idx_research_questions_active', 'research_questions', 'is_active'),
        ('idx_research_questions_next_run', 'research_questions', 'next_run_at'),
        # article_research_matches indexes
        ('idx_arm_article', 'article_research_matches', 'article_id'),
        ('idx_arm_question', 'article_research_matches', 'question_id'),
        ('idx_arm_relevance', 'article_research_matches', 'relevance_score DESC'),
        ('idx_arm_source', 'article_research_matches', 'discovered_via_source'),
        ('idx_arm_viewed', 'article_research_matches', 'is_viewed'),
        ('idx_arm_bookmarked', 'article_research_matches', 'is_bookmarked'),
        # research_question_sources indexes
        ('idx_rqs_question', 'research_question_sources', 'question_id'),
        ('idx_rqs_source', 'research_question_sources', 'source_name'),
        # discovery_execution_log indexes
        ('idx_del_question', 'discovery_execution_log', 'question_id'),
        ('idx_del_status', 'discovery_execution_log', 'status'),
        ('idx_del_started', 'discovery_execution_log', 'started_at DESC'),
        # available_sources indexes
        ('idx_sources_active', 'available_sources', 'is_active'),
    ]

    for idx_name, table_name, column in indexes:
        try:
            await conn.execute(
                f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}({column})'
            )
            console.print(f'  [green]✓[/green] Index {idx_name} created')
        except Exception as e:
            if 'already exists' in str(e).lower():
                console.print(f'  [yellow]⊙[/yellow] Index {idx_name} already exists')
            else:
                console.print(f'  [red]✗[/red] Error creating index {idx_name}: {e}')

    # Create triggers for updated_at
    console.print('\n  [cyan]Creating triggers...[/cyan]')

    # Trigger function
    await conn.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    console.print('  [green]✓[/green] Trigger function created')

    # Triggers for each table
    trigger_tables = ['research_questions', 'available_sources']
    for table in trigger_tables:
        try:
            await conn.execute(f"""
                CREATE TRIGGER update_{table}_updated_at
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
            """)
            console.print(f'  [green]✓[/green] Trigger for {table} created')
        except Exception as e:
            if 'already exists' in str(e).lower():
                console.print(
                    f'  [yellow]⊙[/yellow] Trigger for {table} already exists'
                )
            else:
                console.print(f'  [red]✗[/red] Error creating trigger for {table}: {e}')

    console.print(
        '\n[bold green]✓ Research Question Schema Applied Successfully![/bold green]\n'
    )


async def seed_available_sources(conn: asyncpg.Connection):
    """Seed the available_sources table with known plugins."""

    console.print('[cyan]Seeding available_sources with known plugins...[/cyan]')

    sources = [
        {
            'name': 'arxiv',
            'display_name': 'arXiv',
            'description': 'Open access e-print archive for physics, mathematics, computer science, and more',
            'source_type': 'api',
            'capabilities': {
                'search_by_keywords': True,
                'search_by_authors': True,
                'search_by_categories': True,
            },
            'rate_limit_per_minute': 60,
        },
        {
            'name': 'pubmed',
            'display_name': 'PubMed',
            'description': 'Database of biomedical literature from MEDLINE and life science journals',
            'source_type': 'api',
            'capabilities': {
                'search_by_keywords': True,
                'search_by_authors': True,
                'mesh_terms': True,
            },
            'rate_limit_per_minute': 30,
        },
        {
            'name': 'crossref',
            'display_name': 'CrossRef',
            'description': 'Official DOI Registration Agency of the International DOI Foundation',
            'source_type': 'api',
            'capabilities': {
                'search_by_keywords': True,
                'search_by_doi': True,
                'citation_data': True,
            },
            'rate_limit_per_minute': 60,
        },
        {
            'name': 'openalex',
            'display_name': 'OpenAlex',
            'description': 'Open catalog of scholarly papers, authors, institutions, and more',
            'source_type': 'api',
            'capabilities': {
                'search_by_keywords': True,
                'search_by_authors': True,
                'institution_data': True,
            },
            'rate_limit_per_minute': 100,
        },
        {
            'name': 'biorxiv',
            'display_name': 'bioRxiv',
            'description': 'Preprint server for biology',
            'source_type': 'api',
            'capabilities': {
                'search_by_keywords': True,
                'search_by_authors': True,
                'preprints': True,
            },
            'rate_limit_per_minute': 60,
        },
    ]

    for source in sources:
        try:
            await conn.execute(
                """
                INSERT INTO available_sources (
                    name, display_name, description, source_type,
                    capabilities, rate_limit_per_minute, is_active, health_status
                )
                VALUES ($1, $2, $3, $4, $5, $6, true, 'active')
                ON CONFLICT (name) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    description = EXCLUDED.description,
                    capabilities = EXCLUDED.capabilities,
                    rate_limit_per_minute = EXCLUDED.rate_limit_per_minute
            """,
                source['name'],
                source['display_name'],
                source['description'],
                source['source_type'],
                source['capabilities'],
                source['rate_limit_per_minute'],
            )
            console.print(f'  [green]✓[/green] Seeded source: {source["display_name"]}')
        except Exception as e:
            console.print(f'  [red]✗[/red] Error seeding {source["name"]}: {e}')

    console.print('[bold green]✓ Available sources seeded successfully![/bold green]\n')


async def verify_schema(conn: asyncpg.Connection):
    """Verify that all tables and indexes were created correctly."""

    console.print('[cyan]Verifying schema...[/cyan]')

    tables = [
        'research_questions',
        'available_sources',
        'research_question_sources',
        'article_research_matches',
        'discovery_execution_log',
    ]

    for table in tables:
        try:
            count = await conn.fetchval(f'SELECT COUNT(*) FROM {table}')
            console.print(f'  [green]✓[/green] Table {table} exists (rows: {count})')
        except Exception as e:
            console.print(f'  [red]✗[/red] Table {table} verification failed: {e}')
            return False

    console.print('[bold green]✓ Schema verification complete![/bold green]\n')
    return True


async def run_migration():
    """Run the research question schema migration."""

    console.print(
        '\n[bold cyan]═══════════════════════════════════════════════[/bold cyan]'
    )
    console.print(
        '[bold cyan]  Research Question Schema Migration - Week 1  [/bold cyan]'
    )
    console.print(
        '[bold cyan]═══════════════════════════════════════════════[/bold cyan]\n'
    )

    # Load config
    config = Config()
    console.print(f'[green]✓[/green] Loaded config from {config.vault_root}')

    # Connect to PostgreSQL
    db_url = (
        config.secrets.database_url or 'postgresql://thoth:thoth@localhost:5432/thoth'
    )
    console.print(f'[green]✓[/green] Connecting to database...')  # noqa: F541

    conn = await asyncpg.connect(db_url)
    console.print(f'[green]✓[/green] Connected to PostgreSQL\n')  # noqa: F541

    try:
        # Apply schema
        await apply_research_question_schema(conn)

        # Seed available sources
        await seed_available_sources(conn)

        # Verify schema
        success = await verify_schema(conn)

        if success:
            console.print(
                '\n[bold green]═══════════════════════════════════════════════[/bold green]'
            )
            console.print(
                '[bold green]     Migration completed successfully! 🎉      [/bold green]'
            )
            console.print(
                '[bold green]═══════════════════════════════════════════════[/bold green]\n'
            )

            console.print('[cyan]Next steps:[/cyan]')
            console.print('  1. Review the new tables in your database')
            console.print('  2. Proceed to Week 2: Repository Layer')
            console.print('  3. See docs/IMPLEMENTATION-CHECKLIST.md for details\n')
        else:
            console.print('\n[bold red]Migration completed with warnings[/bold red]\n')

    except Exception as e:
        console.print(f'\n[bold red]Migration failed: {e}[/bold red]\n')
        raise

    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(run_migration())

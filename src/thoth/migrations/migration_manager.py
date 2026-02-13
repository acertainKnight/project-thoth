"""
Database migration manager for Thoth.

Handles schema versioning and migration execution for PostgreSQL.
"""

from typing import Any

import asyncpg
from loguru import logger


class MigrationManager:
    """
    Manages database schema migrations.

    Tracks applied migrations in a migrations table and applies
    pending migrations in order.
    """

    def __init__(self, database_url: str):
        """
        Initialize the migration manager.

        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        self._migrations = self._load_migrations()

    def _load_migrations(self) -> list[tuple[int, str, str]]:
        """
        Load all available migrations.

        Returns:
            List of (version, name, sql) tuples sorted by version
        """
        # Define migrations inline for simplicity and portability
        migrations = [
            (1, 'initial_schema', MIGRATION_001_INITIAL_SCHEMA),
            (2, 'add_publication_date_range', MIGRATION_002_ADD_PUBLICATION_DATE_RANGE),
            (3, 'add_hybrid_search_support', MIGRATION_003_ADD_HYBRID_SEARCH_SUPPORT),
            (4, 'agent_loaded_skills', MIGRATION_004_AGENT_LOADED_SKILLS),
        ]
        return sorted(migrations, key=lambda x: x[0])

    async def initialize_database(self) -> bool:
        """
        Initialize database with all migrations.

        Creates migrations tracking table if needed, then applies
        any pending migrations.

        Returns:
            bool: True if successful
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            try:
                # Create migrations tracking table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS _migrations (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)

                # Get applied versions
                applied = await conn.fetch(
                    'SELECT version FROM _migrations ORDER BY version'
                )
                applied_versions = {row['version'] for row in applied}

                # Apply pending migrations
                for version, name, sql in self._migrations:
                    if version not in applied_versions:
                        logger.info(f'Applying migration {version:03d}: {name}')

                        try:
                            # Execute migration SQL
                            await conn.execute(sql)

                            # Record migration
                            await conn.execute(
                                'INSERT INTO _migrations (version, name) VALUES ($1, $2)',
                                version,
                                name,
                            )

                            logger.success(f'Applied migration {version:03d}: {name}')
                        except asyncpg.exceptions.PostgresError as e:
                            # Check if "already exists" error from migration 001
                            if version == 1 and (
                                'already exists' in str(e).lower()
                                or 'does not exist' in str(e).lower()
                            ):
                                logger.warning(
                                    f'Migration 001 partially applied (tables '
                                    f'already exist). Marking as applied: {e}'
                                )
                                # Mark migration 001 as applied since tables exist
                                await conn.execute(
                                    'INSERT INTO _migrations (version, name) VALUES ($1, $2) ON CONFLICT DO NOTHING',
                                    version,
                                    name,
                                )
                            else:
                                # Re-raise other errors
                                raise

                return True

            finally:
                await conn.close()

        except Exception as e:
            logger.error(f'Migration failed: {e}')
            return False

    async def get_migration_status(self) -> dict[str, Any]:
        """
        Get current migration status.

        Returns:
            dict with applied_count, pending_count, applied_versions,
            pending_migrations, and last_migration info
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            try:
                # Get applied migrations
                applied = await conn.fetch(
                    'SELECT version, name, applied_at FROM _migrations ORDER BY version'
                )
                applied_versions = [row['version'] for row in applied]

                # Calculate pending
                pending = [
                    (v, n) for v, n, _ in self._migrations if v not in applied_versions
                ]

                # Get last migration info
                last_migration = None
                if applied:
                    last = applied[-1]
                    last_migration = {
                        'version': last['version'],
                        'name': last['name'],
                        'applied_at': last['applied_at'].isoformat()
                        if last['applied_at']
                        else None,
                    }

                return {
                    'applied_count': len(applied_versions),
                    'pending_count': len(pending),
                    'applied_versions': applied_versions,
                    'pending_migrations': pending,
                    'last_migration': last_migration,
                }

            finally:
                await conn.close()

        except asyncpg.UndefinedTableError:
            # Migrations table doesn't exist yet
            return {
                'applied_count': 0,
                'pending_count': len(self._migrations),
                'applied_versions': [],
                'pending_migrations': [(v, n) for v, n, _ in self._migrations],
                'last_migration': None,
            }


# =============================================================================
# Migration SQL Definitions
# =============================================================================

MIGRATION_001_INITIAL_SCHEMA = """
-- Migration 001: Initial Schema
-- Creates all core tables for Thoth

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================================================
-- Core Tables
-- =============================================================================

-- Paper metadata (source of truth for paper info)
CREATE TABLE IF NOT EXISTS paper_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doi TEXT,
    arxiv_id TEXT,
    title TEXT NOT NULL,
    title_normalized TEXT,
    authors JSONB,
    affiliations JSONB,
    publication_date DATE,
    year INTEGER,
    journal TEXT,
    venue TEXT,
    volume TEXT,
    issue TEXT,
    pages TEXT,
    publisher TEXT,
    abstract TEXT,
    keywords JSONB,
    fields_of_study JSONB,
    url TEXT,
    pdf_url TEXT,
    pdf_source TEXT,
    is_open_access BOOLEAN DEFAULT FALSE,
    citation_count INTEGER DEFAULT 0,
    reference_count INTEGER DEFAULT 0,
    influential_citation_count INTEGER DEFAULT 0,
    source_of_truth TEXT CHECK (source_of_truth IN ('processed', 'citation', 'discovered', 'merged')),
    original_papers_id UUID,
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, ''))
    ) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for paper_metadata
CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_metadata_doi
    ON paper_metadata(doi) WHERE doi IS NOT NULL AND doi <> '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_metadata_arxiv
    ON paper_metadata(arxiv_id) WHERE arxiv_id IS NOT NULL AND arxiv_id <> '';
CREATE INDEX IF NOT EXISTS idx_paper_metadata_title_trgm
    ON paper_metadata USING gin (title_normalized gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_paper_metadata_search
    ON paper_metadata USING gin (search_vector);
CREATE INDEX IF NOT EXISTS idx_paper_metadata_year ON paper_metadata(year);
CREATE INDEX IF NOT EXISTS idx_paper_metadata_source ON paper_metadata(source_of_truth);
CREATE INDEX IF NOT EXISTS idx_paper_metadata_updated ON paper_metadata(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_paper_metadata_authors
    ON paper_metadata USING gin (authors jsonb_path_ops);

-- Processed papers (user's read papers with file paths and content)
CREATE TABLE IF NOT EXISTS processed_papers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID NOT NULL UNIQUE REFERENCES paper_metadata(id) ON DELETE CASCADE,
    pdf_path TEXT,
    markdown_path TEXT,
    note_path TEXT,
    obsidian_uri TEXT,
    markdown_content TEXT,
    processing_status TEXT DEFAULT 'pending',
    processed_at TIMESTAMP WITH TIME ZONE,
    last_accessed TIMESTAMP WITH TIME ZONE,
    user_notes TEXT,
    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
    user_tags JSONB,
    analysis_schema_name VARCHAR(100),
    analysis_schema_version VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for processed_papers
CREATE INDEX IF NOT EXISTS idx_processed_papers_status ON processed_papers(processing_status);
CREATE INDEX IF NOT EXISTS idx_processed_papers_accessed ON processed_papers(last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_processed_papers_rating
    ON processed_papers(user_rating) WHERE user_rating IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_processed_papers_pdf_path
    ON processed_papers(pdf_path) WHERE pdf_path IS NOT NULL;

-- Papers VIEW (backward-compatible interface)
CREATE OR REPLACE VIEW papers AS
SELECT
    pm.id,
    pm.doi,
    pm.arxiv_id,
    NULL::text AS backup_id,
    pm.authors,
    pm.affiliations,
    pm.year,
    pm.publication_date,
    pm.journal,
    pm.venue,
    pm.volume,
    pm.issue,
    pm.pages,
    pm.publisher,
    pm.abstract,
    pm.keywords,
    pm.fields_of_study,
    NULL::jsonb AS s2_fields_of_study,
    pm.url,
    pm.pdf_url,
    pm.pdf_source,
    pp.obsidian_uri,
    pm.citation_count,
    pm.reference_count,
    pm.influential_citation_count,
    pm.is_open_access,
    CASE
        WHEN pm.source_of_truth = 'citation' THEN true
        ELSE false
    END AS is_document_citation,
    pm.created_at,
    pm.updated_at,
    pp.pdf_path,
    pp.markdown_path,
    pp.note_path,
    pp.markdown_content,
    pp.processing_status,
    pp.user_notes,
    pp.user_rating,
    pp.user_tags,
    pp.analysis_schema_name,
    pp.analysis_schema_version,
    pm.search_vector,
    pm.title
FROM paper_metadata pm
LEFT JOIN processed_papers pp ON pp.paper_id = pm.id;

-- =============================================================================
-- Citations Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    citing_paper_id UUID NOT NULL REFERENCES paper_metadata(id) ON DELETE CASCADE,
    cited_paper_id UUID REFERENCES paper_metadata(id) ON DELETE SET NULL,
    citation_text TEXT,
    citation_context TEXT,
    citation_number INTEGER,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolution_method TEXT,
    confidence_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_citations_citing ON citations(citing_paper_id);
CREATE INDEX IF NOT EXISTS idx_citations_cited ON citations(cited_paper_id);
CREATE INDEX IF NOT EXISTS idx_citations_resolved ON citations(is_resolved);

-- =============================================================================
-- Research Questions & Discovery
-- =============================================================================

CREATE TABLE IF NOT EXISTS research_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
    priority INTEGER DEFAULT 0,
    search_terms JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS research_question_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_question_id UUID NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
    paper_id UUID NOT NULL REFERENCES paper_metadata(id) ON DELETE CASCADE,
    relevance_score FLOAT,
    match_reason TEXT,
    is_reviewed BOOLEAN DEFAULT FALSE,
    is_accepted BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(research_question_id, paper_id)
);

CREATE TABLE IF NOT EXISTS research_question_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_question_id UUID NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    last_checked TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Discovery & Sources
-- =============================================================================

CREATE TABLE IF NOT EXISTS discovery_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    config JSONB,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS available_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    source_type TEXT NOT NULL,
    description TEXT,
    requires_auth BOOLEAN DEFAULT FALSE,
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS discovered_papers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID REFERENCES paper_metadata(id) ON DELETE SET NULL,
    source_name TEXT NOT NULL,
    source_id TEXT,
    discovery_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB,
    is_processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_discoveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID REFERENCES paper_metadata(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS article_discoveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB,
    is_processed BOOLEAN DEFAULT FALSE
);

-- =============================================================================
-- Discovery Scheduling
-- =============================================================================

CREATE TABLE IF NOT EXISTS discovery_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_question_id UUID REFERENCES research_questions(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,
    schedule_type TEXT NOT NULL,
    cron_expression TEXT,
    interval_hours INTEGER,
    is_enabled BOOLEAN DEFAULT TRUE,
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS discovery_execution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id UUID REFERENCES discovery_schedule(id) ON DELETE CASCADE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status TEXT NOT NULL,
    papers_found INTEGER DEFAULT 0,
    papers_new INTEGER DEFAULT 0,
    error_message TEXT
);

-- =============================================================================
-- Processing & Queue
-- =============================================================================

CREATE TABLE IF NOT EXISTS processing_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID REFERENCES paper_metadata(id) ON DELETE CASCADE,
    pdf_path TEXT,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS processed_pdfs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pdf_path TEXT NOT NULL UNIQUE,
    file_hash TEXT,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT DEFAULT 'completed',
    paper_id UUID REFERENCES paper_metadata(id) ON DELETE SET NULL
);

-- =============================================================================
-- Tags
-- =============================================================================

CREATE TABLE IF NOT EXISTS tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    color TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_tags (
    paper_id UUID NOT NULL REFERENCES paper_metadata(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (paper_id, tag_id)
);

-- =============================================================================
-- Browser Workflows
-- =============================================================================

CREATE TABLE IF NOT EXISTS browser_workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    workflow_type TEXT NOT NULL,
    config JSONB NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES browser_workflows(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    result JSONB,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS workflow_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES browser_workflows(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    action_order INTEGER NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    service TEXT NOT NULL,
    credentials_encrypted TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_search_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES browser_workflows(id) ON DELETE CASCADE,
    search_terms JSONB,
    filters JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Caching & Token Usage
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_enrichment_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT NOT NULL UNIQUE,
    data JSONB NOT NULL,
    source TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cache_key ON api_enrichment_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON api_enrichment_cache(expires_at);

CREATE TABLE IF NOT EXISTS token_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model TEXT NOT NULL,
    operation TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_estimate FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Search History & Document Chunks
-- =============================================================================

CREATE TABLE IF NOT EXISTS search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    search_type TEXT NOT NULL,
    results_count INTEGER DEFAULT 0,
    filters JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID REFERENCES paper_metadata(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_paper ON document_chunks(paper_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);

-- =============================================================================
-- Memory Table (for Letta integration)
-- =============================================================================

CREATE TABLE IF NOT EXISTS memory (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    agent_id TEXT,
    scope TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    salience_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_user_id ON memory(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_user_scope ON memory(user_id, scope);
CREATE INDEX IF NOT EXISTS idx_memory_created_at ON memory(created_at);
CREATE INDEX IF NOT EXISTS idx_memory_salience ON memory(salience_score);
"""

MIGRATION_002_ADD_PUBLICATION_DATE_RANGE = """
-- Migration 002: Add publication_date_range to research_questions
-- Adds JSONB field to store date range filtering for publications

ALTER TABLE research_questions
ADD COLUMN IF NOT EXISTS publication_date_range JSONB;

-- Add comment explaining the field structure
COMMENT ON COLUMN research_questions.publication_date_range IS
'Date range for filtering publications. Expected structure: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD" or "present"}';
"""

MIGRATION_003_ADD_HYBRID_SEARCH_SUPPORT = """
-- Migration 003: Add hybrid search support to document_chunks
-- Enables BM25-style full-text search to complement vector search

-- Add tsvector column for full-text search (auto-updates when content changes)
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS search_vector tsvector
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

-- Add GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS idx_chunks_fts
ON document_chunks USING gin(search_vector);

-- Add columns for advanced chunking strategies
-- Parent-child chunk relationships for hierarchical retrieval
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS parent_chunk_id UUID REFERENCES document_chunks(id);

-- Track embedding version to support re-indexing when strategy changes
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS embedding_version VARCHAR(32) DEFAULT 'v1';

-- Track chunk type for filtering (content, table, figure_caption, abstract, references)
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(32) DEFAULT 'content';

-- Track token count for context window management
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS token_count INTEGER;

-- Add updated_at timestamp for tracking changes
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Add index for parent-child lookups
CREATE INDEX IF NOT EXISTS idx_chunks_parent ON document_chunks(parent_chunk_id);

-- Add index for embedding version (useful for batch re-indexing)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_version ON document_chunks(embedding_version);

-- Add index for chunk type filtering
CREATE INDEX IF NOT EXISTS idx_chunks_type ON document_chunks(chunk_type);

-- Add unique constraint for paper_id + chunk_index (prevents duplicates)
CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_paper_chunk
ON document_chunks(paper_id, chunk_index);

-- Add comments for documentation
COMMENT ON COLUMN document_chunks.search_vector IS
'Full-text search vector for BM25-style keyword matching. Auto-generated from content.';

COMMENT ON COLUMN document_chunks.parent_chunk_id IS
'Reference to parent chunk for hierarchical retrieval. Small chunks for precise search, large chunks for context.';

COMMENT ON COLUMN document_chunks.embedding_version IS
'Tracks embedding strategy version (e.g., v1, v2-contextual). Used to identify chunks needing re-indexing.';

COMMENT ON COLUMN document_chunks.chunk_type IS
'Type of chunk content: content (default), table, figure_caption, abstract, references.';

COMMENT ON COLUMN document_chunks.token_count IS
'Approximate token count for context window management and retrieval strategies.';
"""

MIGRATION_004_AGENT_LOADED_SKILLS = """
-- Migration 004: Track which skills each agent has loaded
-- Replaces the volatile in-memory registry so skill state survives MCP restarts.

CREATE TABLE IF NOT EXISTS agent_loaded_skills (
    agent_id    TEXT NOT NULL,
    skill_id    TEXT NOT NULL,
    loaded_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (agent_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_loaded_skills_agent
ON agent_loaded_skills(agent_id);
"""

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
            (
                5,
                'add_discovered_articles_table',
                MIGRATION_005_ADD_DISCOVERED_ARTICLES_TABLE,
            ),
            (6, 'add_knowledge_collections', MIGRATION_006_ADD_KNOWLEDGE_COLLECTIONS),
            (7, 'add_multi_user_support', MIGRATION_007_ADD_MULTI_USER_SUPPORT),
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

MIGRATION_005_ADD_DISCOVERED_ARTICLES_TABLE = """
-- Migration 005: discovered_articles + rebuild article_discoveries + database functions
--
-- Fixes two schema gaps:
--
-- 1. discovered_articles never existed. The ArticleRepository, WorkflowEngine, and
--    ExtractionService all reference it. This is the raw staging table for articles
--    found by browser workflows and API sources *before* they get promoted to
--    paper_metadata and matched against research questions.
--
-- 2. article_discoveries (created in migration 001) had placeholder columns
--    (title, source, is_processed) that don't match what the ArticleRepository
--    actually writes to (article_id FK, source_id FK, discovery_query, relevance_score,
--    rank_in_results, source_metadata, external_id, processed). We drop and recreate
--    it with the correct schema.
--
-- Also installs the database functions that several repositories call:
--    normalize_title, find_duplicate_article, find_duplicate_paper,
--    has_article_been_processed, mark_article_as_processed, get_new_articles_since

-- =============================================================================
-- 1. discovered_articles -- raw article staging table
-- =============================================================================
--
-- Lifecycle position:
--   source query  ->  [discovered_articles]  ->  dedup  ->  paper_metadata
--                                                        ->  research_question_matches

CREATE TABLE IF NOT EXISTS discovered_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identifiers (used for dedup)
    doi TEXT,
    arxiv_id TEXT,
    title TEXT NOT NULL,
    title_normalized TEXT,

    -- Paper metadata
    authors JSONB,
    abstract TEXT,
    publication_date DATE,
    journal TEXT,
    url TEXT,
    pdf_url TEXT,
    keywords JSONB,

    -- Discovery provenance
    source TEXT NOT NULL,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Processing pipeline status
    processing_status TEXT DEFAULT 'pending',
    processed_at TIMESTAMP WITH TIME ZONE,
    paper_id UUID REFERENCES paper_metadata(id) ON DELETE SET NULL,

    -- Flexible metadata buckets
    source_metadata JSONB,
    additional_metadata JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dedup indexes (partial unique on non-null identifiers)
CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_articles_doi
    ON discovered_articles(doi) WHERE doi IS NOT NULL AND doi <> '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_articles_arxiv
    ON discovered_articles(arxiv_id) WHERE arxiv_id IS NOT NULL AND arxiv_id <> '';

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_discovered_articles_title_trgm
    ON discovered_articles USING gin (title_normalized gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_discovered_articles_source
    ON discovered_articles(source);
CREATE INDEX IF NOT EXISTS idx_discovered_articles_status
    ON discovered_articles(processing_status);
CREATE INDEX IF NOT EXISTS idx_discovered_articles_discovered
    ON discovered_articles(discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_discovered_articles_paper
    ON discovered_articles(paper_id) WHERE paper_id IS NOT NULL;


-- =============================================================================
-- 2. article_discoveries -- many-to-many join: articles <-> discovery sources
-- =============================================================================
--
-- Migration 001 created this table with (title, source, is_processed) but the
-- ArticleRepository writes (article_id, source_id, discovery_query, ...).
-- Drop and recreate with the real columns.
--
-- available_sources may have been created without a UUID id column (PK on name).
-- Add one if missing so the FK below works.

ALTER TABLE available_sources
    ADD COLUMN IF NOT EXISTS id UUID DEFAULT gen_random_uuid();
UPDATE available_sources SET id = gen_random_uuid() WHERE id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_available_sources_id ON available_sources(id);

DROP TABLE IF EXISTS article_discoveries CASCADE;

CREATE TABLE article_discoveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID NOT NULL REFERENCES discovered_articles(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES available_sources(id) ON DELETE CASCADE,

    -- Discovery context
    discovery_query TEXT,
    relevance_score FLOAT,
    rank_in_results INTEGER,
    source_metadata JSONB,
    external_id TEXT,

    -- Processing tracking
    processed BOOLEAN DEFAULT FALSE,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Each source discovers an article at most once
    UNIQUE(article_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_article_discoveries_article
    ON article_discoveries(article_id);
CREATE INDEX IF NOT EXISTS idx_article_discoveries_source
    ON article_discoveries(source_id);
CREATE INDEX IF NOT EXISTS idx_article_discoveries_processed
    ON article_discoveries(processed);


-- =============================================================================
-- 3. Database functions
-- =============================================================================

-- Drop existing functions first to handle parameter name changes cleanly
DROP FUNCTION IF EXISTS normalize_title(TEXT);
DROP FUNCTION IF EXISTS find_duplicate_article(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS find_duplicate_paper(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS has_article_been_processed(UUID, UUID);
DROP FUNCTION IF EXISTS mark_article_as_processed(UUID, UUID);
DROP FUNCTION IF EXISTS get_new_articles_since(UUID, TIMESTAMP WITH TIME ZONE);

-- normalize_title(text) -> text
-- Lowercase, strip punctuation, collapse whitespace. Used by dedup logic
-- in both discovered_articles and paper_metadata.
CREATE OR REPLACE FUNCTION normalize_title(title_input TEXT)
RETURNS TEXT AS $$
BEGIN
    IF title_input IS NULL OR title_input = '' THEN
        RETURN '';
    END IF;

    RETURN TRIM(BOTH FROM
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                LOWER(title_input),
                '[^\\w\\s]', '', 'g'    -- remove punctuation
            ),
            '\\s+', ' ', 'g'           -- collapse whitespace
        )
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;


-- find_duplicate_article(doi, arxiv_id, title) -> uuid
-- Looks in discovered_articles. Priority: DOI > ArXiv ID > normalized title.
CREATE OR REPLACE FUNCTION find_duplicate_article(
    doi_input TEXT,
    arxiv_id_input TEXT,
    title_input TEXT
)
RETURNS UUID AS $$
DECLARE
    found_id UUID;
BEGIN
    -- DOI match (case-insensitive)
    IF doi_input IS NOT NULL AND doi_input <> '' THEN
        SELECT id INTO found_id
        FROM discovered_articles
        WHERE LOWER(doi) = LOWER(doi_input)
        LIMIT 1;
        IF found_id IS NOT NULL THEN RETURN found_id; END IF;
    END IF;

    -- ArXiv ID match (strip version suffix)
    IF arxiv_id_input IS NOT NULL AND arxiv_id_input <> '' THEN
        SELECT id INTO found_id
        FROM discovered_articles
        WHERE REGEXP_REPLACE(LOWER(arxiv_id), 'v[0-9]+$', '') =
              REGEXP_REPLACE(LOWER(arxiv_id_input), 'v[0-9]+$', '')
        LIMIT 1;
        IF found_id IS NOT NULL THEN RETURN found_id; END IF;
    END IF;

    -- Normalized title match
    IF title_input IS NOT NULL AND title_input <> '' THEN
        SELECT id INTO found_id
        FROM discovered_articles
        WHERE title_normalized = normalize_title(title_input)
        LIMIT 1;
        IF found_id IS NOT NULL THEN RETURN found_id; END IF;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;


-- find_duplicate_paper(doi, arxiv_id, title) -> uuid
-- Same logic against paper_metadata. Falls back to trigram similarity.
CREATE OR REPLACE FUNCTION find_duplicate_paper(
    doi_input TEXT,
    arxiv_id_input TEXT,
    title_input TEXT
)
RETURNS UUID AS $$
DECLARE
    found_id UUID;
    norm TEXT;
BEGIN
    IF doi_input IS NOT NULL AND doi_input <> '' THEN
        SELECT id INTO found_id
        FROM paper_metadata
        WHERE LOWER(doi) = LOWER(doi_input)
        LIMIT 1;
        IF found_id IS NOT NULL THEN RETURN found_id; END IF;
    END IF;

    IF arxiv_id_input IS NOT NULL AND arxiv_id_input <> '' THEN
        SELECT id INTO found_id
        FROM paper_metadata
        WHERE REGEXP_REPLACE(LOWER(arxiv_id), 'v[0-9]+$', '') =
              REGEXP_REPLACE(LOWER(arxiv_id_input), 'v[0-9]+$', '')
        LIMIT 1;
        IF found_id IS NOT NULL THEN RETURN found_id; END IF;
    END IF;

    IF title_input IS NOT NULL AND title_input <> '' THEN
        norm := normalize_title(title_input);

        -- Exact normalized match
        SELECT id INTO found_id
        FROM paper_metadata
        WHERE title_normalized = norm
        LIMIT 1;
        IF found_id IS NOT NULL THEN RETURN found_id; END IF;

        -- Fuzzy fallback via trigram similarity (pg_trgm)
        SELECT id INTO found_id
        FROM paper_metadata
        WHERE title_normalized IS NOT NULL
          AND title_normalized % norm
        ORDER BY similarity(title_normalized, norm) DESC
        LIMIT 1;
        IF found_id IS NOT NULL THEN RETURN found_id; END IF;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;


-- has_article_been_processed(article_id, source_id) -> boolean
CREATE OR REPLACE FUNCTION has_article_been_processed(
    article_id_input UUID,
    source_id_input UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS(
        SELECT 1
        FROM article_discoveries
        WHERE article_id = article_id_input
          AND source_id = source_id_input
          AND processed = true
    );
END;
$$ LANGUAGE plpgsql;


-- mark_article_as_processed(article_id, source_id) -> boolean
CREATE OR REPLACE FUNCTION mark_article_as_processed(
    article_id_input UUID,
    source_id_input UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE article_discoveries
    SET processed = true,
        updated_at = NOW()
    WHERE article_id = article_id_input
      AND source_id = source_id_input;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;


-- get_new_articles_since(source_id, timestamp) -> setof discovered_articles
CREATE OR REPLACE FUNCTION get_new_articles_since(
    source_id_input UUID,
    since_timestamp TIMESTAMP WITH TIME ZONE
)
RETURNS SETOF discovered_articles AS $$
BEGIN
    RETURN QUERY
    SELECT da.*
    FROM discovered_articles da
    JOIN article_discoveries ad ON ad.article_id = da.id
    WHERE ad.source_id = source_id_input
      AND ad.discovered_at >= since_timestamp
    ORDER BY ad.discovered_at DESC;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- 4. Views
-- =============================================================================

-- pending_articles: raw articles waiting to be processed
CREATE OR REPLACE VIEW pending_articles AS
SELECT *
FROM discovered_articles
WHERE processing_status = 'pending'
ORDER BY discovered_at DESC;

-- multi_source_articles: articles found by more than one source
-- Uses the article_discoveries join table for actual counting.
CREATE OR REPLACE VIEW multi_source_articles AS
SELECT
    da.*,
    agg.source_count
FROM discovered_articles da
JOIN (
    SELECT article_id, COUNT(DISTINCT source_id) AS source_count
    FROM article_discoveries
    GROUP BY article_id
    HAVING COUNT(DISTINCT source_id) >= 2
) agg ON agg.article_id = da.id
ORDER BY agg.source_count DESC, da.discovered_at DESC;
"""

MIGRATION_006_ADD_KNOWLEDGE_COLLECTIONS = """
-- Migration 006: Knowledge Collections
-- Adds support for external knowledge documents organized into collections

-- =============================================================================
-- 1. knowledge_collections table
-- =============================================================================
CREATE TABLE IF NOT EXISTS knowledge_collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_collections_name
    ON knowledge_collections(name);

-- =============================================================================
-- 2. Alter paper_metadata for external knowledge support
-- =============================================================================

-- Add collection_id (nullable FK to knowledge_collections)
ALTER TABLE paper_metadata
    ADD COLUMN IF NOT EXISTS collection_id UUID REFERENCES knowledge_collections(id) ON DELETE SET NULL;

-- Add document_category (research_paper or external)
ALTER TABLE paper_metadata
    ADD COLUMN IF NOT EXISTS document_category VARCHAR(32) NOT NULL DEFAULT 'research_paper';

-- Index for filtering by category and collection
CREATE INDEX IF NOT EXISTS idx_paper_metadata_category
    ON paper_metadata(document_category);

CREATE INDEX IF NOT EXISTS idx_paper_metadata_collection
    ON paper_metadata(collection_id) WHERE collection_id IS NOT NULL;

-- =============================================================================
-- 3. Update papers view to include new columns
-- =============================================================================

-- The papers view is a LEFT JOIN of paper_metadata + processed_papers.
-- Migration 001 created this view with explicit column names that differ from
-- pm.*, so CREATE OR REPLACE fails. Drop first, then recreate.
DROP VIEW IF EXISTS papers CASCADE;

CREATE VIEW papers AS
SELECT
    pm.*,
    pp.pdf_path,
    pp.markdown_path,
    pp.note_path,
    pp.markdown_content,
    pp.obsidian_uri,
    pp.processing_status,
    pp.processed_at,
    pp.last_accessed,
    pp.user_notes,
    pp.user_rating,
    pp.user_tags,
    pp.analysis_schema_name,
    pp.analysis_schema_version
FROM paper_metadata pm
LEFT JOIN processed_papers pp ON pm.id = pp.paper_id;
"""


MIGRATION_007_ADD_MULTI_USER_SUPPORT = """
-- Migration 007: Multi-User Support
-- Adds users table and user_id columns for tenant isolation

-- 1. Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    api_token TEXT NOT NULL UNIQUE,
    vault_path TEXT NOT NULL,
    orchestrator_agent_id TEXT,
    analyst_agent_id TEXT,
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_token ON users(api_token);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = TRUE;

-- 2. Add user_id columns to tenant-scoped tables
-- Paper tables
ALTER TABLE paper_metadata ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_paper_metadata_user_id ON paper_metadata(user_id);

ALTER TABLE processed_papers ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_processed_papers_user_id ON processed_papers(user_id);

ALTER TABLE citations ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_citations_user_id ON citations(user_id);

-- Research questions (ensure index exists)
CREATE INDEX IF NOT EXISTS idx_research_questions_user_id ON research_questions(user_id);

ALTER TABLE research_question_matches ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_research_question_matches_user_id ON research_question_matches(user_id);

ALTER TABLE research_question_sources ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_research_question_sources_user_id ON research_question_sources(user_id);

-- Discovery tables
ALTER TABLE discovered_papers ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_discovered_papers_user_id ON discovered_papers(user_id);

ALTER TABLE paper_discoveries ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_paper_discoveries_user_id ON paper_discoveries(user_id);

ALTER TABLE discovered_articles ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_discovered_articles_user_id ON discovered_articles(user_id);

ALTER TABLE article_discoveries ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_article_discoveries_user_id ON article_discoveries(user_id);

ALTER TABLE discovery_sources ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_discovery_sources_user_id ON discovery_sources(user_id);

ALTER TABLE discovery_schedule ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_discovery_schedule_user_id ON discovery_schedule(user_id);

ALTER TABLE discovery_execution_log ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_discovery_execution_log_user_id ON discovery_execution_log(user_id);

-- Processing tables
ALTER TABLE processing_queue ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_processing_queue_user_id ON processing_queue(user_id);

ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_processing_jobs_user_id ON processing_jobs(user_id);

ALTER TABLE processed_pdfs ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_processed_pdfs_user_id ON processed_pdfs(user_id);

-- Tags
ALTER TABLE tags ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_tags_user_id ON tags(user_id);

ALTER TABLE paper_tags ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_paper_tags_user_id ON paper_tags(user_id);

-- Workflows
ALTER TABLE browser_workflows ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_browser_workflows_user_id ON browser_workflows(user_id);

ALTER TABLE workflow_executions ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_workflow_executions_user_id ON workflow_executions(user_id);

ALTER TABLE workflow_actions ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_workflow_actions_user_id ON workflow_actions(user_id);

ALTER TABLE workflow_credentials ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_workflow_credentials_user_id ON workflow_credentials(user_id);

-- RAG and search
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_document_chunks_user_id ON document_chunks(user_id);

CREATE INDEX IF NOT EXISTS idx_memory_user_id ON memory(user_id);

ALTER TABLE search_history ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_search_history_user_id ON search_history(user_id);

-- Agent and knowledge
ALTER TABLE agent_loaded_skills ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_agent_loaded_skills_user_id ON agent_loaded_skills(user_id);

ALTER TABLE knowledge_collections ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_knowledge_collections_user_id ON knowledge_collections(user_id);

-- Usage tracking
ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';
CREATE INDEX IF NOT EXISTS idx_token_usage_user_id ON token_usage(user_id);
"""

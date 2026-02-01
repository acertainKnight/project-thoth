-- ============================================================================
-- Migration 004: Restructure Papers Schema
--
-- Purpose: Separate processed papers from citation metadata
-- Creates: paper_metadata (single source of truth), processed_papers, research_question_matches
-- Maintains: Backward compatibility through papers view
--
-- Estimated execution time: 15-20 minutes
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: Create New Tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS paper_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Unique Identifiers
    doi TEXT,
    arxiv_id TEXT,
    title TEXT NOT NULL,
    title_normalized TEXT,

    -- Core Metadata
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

    -- Content
    abstract TEXT,
    keywords JSONB,
    fields_of_study JSONB,

    -- URLs & Access
    url TEXT,
    pdf_url TEXT,
    pdf_source TEXT,
    is_open_access BOOLEAN DEFAULT false,

    -- Metrics
    citation_count INTEGER DEFAULT 0,
    reference_count INTEGER DEFAULT 0,
    influential_citation_count INTEGER DEFAULT 0,

    -- Provenance
    source_of_truth TEXT CHECK (source_of_truth IN ('processed', 'citation', 'discovered', 'merged')),
    original_papers_id UUID,  -- FK to old papers.id for migration tracking

    -- Full-text search
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, ''))
    ) STORED,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique Constraints
CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_metadata_doi ON paper_metadata(doi)
    WHERE doi IS NOT NULL AND doi != '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_metadata_arxiv ON paper_metadata(arxiv_id)
    WHERE arxiv_id IS NOT NULL AND arxiv_id != '';

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_paper_metadata_search ON paper_metadata USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_paper_metadata_year ON paper_metadata(year);
CREATE INDEX IF NOT EXISTS idx_paper_metadata_authors ON paper_metadata USING GIN(authors jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_paper_metadata_title_trgm ON paper_metadata USING GIN(title_normalized gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_paper_metadata_source ON paper_metadata(source_of_truth);
CREATE INDEX IF NOT EXISTS idx_paper_metadata_updated ON paper_metadata(updated_at DESC);


-- ============================================================================
-- Processed Papers Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS processed_papers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID NOT NULL REFERENCES paper_metadata(id) ON DELETE CASCADE,

    -- File Paths (What makes this "processed")
    pdf_path TEXT,
    markdown_path TEXT,
    note_path TEXT,
    obsidian_uri TEXT,

    -- Processing Status
    processing_status TEXT DEFAULT 'pending',
    processed_at TIMESTAMPTZ,
    last_accessed TIMESTAMPTZ,

    -- User Data
    user_notes TEXT,
    user_rating INTEGER CHECK (user_rating BETWEEN 1 AND 5),
    user_tags JSONB,

    -- Analysis Schema
    analysis_schema_name VARCHAR(100),
    analysis_schema_version VARCHAR(50),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(paper_id)
);

CREATE INDEX IF NOT EXISTS idx_processed_papers_status ON processed_papers(processing_status);
CREATE INDEX IF NOT EXISTS idx_processed_papers_accessed ON processed_papers(last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_processed_papers_rating ON processed_papers(user_rating) WHERE user_rating IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_processed_papers_pdf_path ON processed_papers(pdf_path) WHERE pdf_path IS NOT NULL;


-- ============================================================================
-- PHASE 2: Migrate Data from papers → paper_metadata
-- ============================================================================

INSERT INTO paper_metadata (
    id, doi, arxiv_id, title, title_normalized,
    authors, affiliations, publication_date, year,
    journal, venue, volume, issue, pages, publisher,
    abstract, keywords, fields_of_study,
    url, pdf_url, pdf_source,
    citation_count, reference_count, influential_citation_count,
    is_open_access,
    source_of_truth,
    original_papers_id,
    created_at, updated_at
)
SELECT
    p.id,
    p.doi,
    p.arxiv_id,
    p.title,
    LOWER(REGEXP_REPLACE(p.title, '[^a-zA-Z0-9 ]', '', 'g')) as title_normalized,
    p.authors,
    p.affiliations,
    p.publication_date,
    p.year,
    p.journal,
    p.venue,
    p.volume,
    p.issue,
    p.pages,
    p.publisher,
    p.abstract,
    p.keywords,
    p.fields_of_study,
    p.url,
    p.pdf_url,
    p.pdf_source,
    p.citation_count,
    p.reference_count,
    p.influential_citation_count,
    p.is_open_access,
    -- Determine source_of_truth
    CASE
        WHEN (p.pdf_path IS NOT NULL OR p.markdown_path IS NOT NULL OR p.note_path IS NOT NULL)
            THEN 'processed'
        ELSE 'citation'
    END as source_of_truth,
    p.id as original_papers_id,
    p.created_at,
    p.updated_at
FROM papers p;

-- Verify count
DO $$
DECLARE
    old_count INTEGER;
    new_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO old_count FROM papers;
    SELECT COUNT(*) INTO new_count FROM paper_metadata;

    IF old_count != new_count THEN
        RAISE EXCEPTION 'Migration count mismatch: papers=%, paper_metadata=%', old_count, new_count;
    END IF;

END $$;

-- ============================================================================
-- PHASE 3: Migrate processed papers
-- ============================================================================

INSERT INTO processed_papers (
    paper_id, pdf_path, markdown_path, note_path, obsidian_uri,
    processing_status, processed_at,
    created_at, updated_at
)
SELECT
    p.id as paper_id,
    p.pdf_path,
    p.markdown_path,
    p.note_path,
    p.obsidian_uri,
    COALESCE(p.processing_status, 'completed') as processing_status,
    p.processed_at,
    p.created_at,
    p.updated_at
FROM papers p
WHERE (p.pdf_path IS NOT NULL OR p.markdown_path IS NOT NULL OR p.note_path IS NOT NULL);

-- Verify count
DO $$
DECLARE
    actual_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO actual_count FROM processed_papers;
END $$;

-- ============================================================================
-- PHASE 4: Backfill PDF URLs for processed papers only
-- ============================================================================

UPDATE paper_metadata pm
SET pdf_url = CASE
    -- ArXiv: /abs/ -> /pdf/ + .pdf
    WHEN pm.url LIKE '%arxiv.org/abs/%'
        THEN REPLACE(pm.url, '/abs/', '/pdf/') || '.pdf'

    -- bioRxiv/medRxiv: add .full.pdf
    WHEN pm.url LIKE '%biorxiv.org/content/%' OR pm.url LIKE '%medrxiv.org/content/%'
        THEN SPLIT_PART(SPLIT_PART(pm.url, '#', 1), '?', 1) || '.full.pdf'

    -- OSF preprints: add /download
    WHEN pm.url LIKE '%psyarxiv.com%' OR pm.url LIKE '%socarxiv.org%' OR pm.url LIKE '%osf.io/preprints%'
        THEN SPLIT_PART(pm.url, '?', 1) || '/download'

    ELSE NULL
END
WHERE pm.source_of_truth = 'processed'
  AND (pm.pdf_url IS NULL OR pm.pdf_url = '')
  AND pm.url IS NOT NULL;

-- Report results
DO $$
DECLARE
    backfilled INTEGER;
BEGIN
    SELECT COUNT(*) INTO backfilled
    FROM paper_metadata
    WHERE source_of_truth = 'processed' AND pdf_url IS NOT NULL;

END $$;

-- ============================================================================
-- PHASE 5: Update citations foreign keys
-- ============================================================================

-- Drop old constraints
ALTER TABLE citations DROP CONSTRAINT IF EXISTS citations_citing_paper_id_fkey;
ALTER TABLE citations DROP CONSTRAINT IF EXISTS citations_cited_paper_id_fkey;

-- Add new constraints pointing to paper_metadata
ALTER TABLE citations
    ADD CONSTRAINT citations_citing_paper_id_fkey
    FOREIGN KEY (citing_paper_id) REFERENCES paper_metadata(id) ON DELETE CASCADE;

ALTER TABLE citations
    ADD CONSTRAINT citations_cited_paper_id_fkey
    FOREIGN KEY (cited_paper_id) REFERENCES paper_metadata(id) ON DELETE SET NULL;

-- Verify citation relationships intact
DO $$
DECLARE
    orphaned_citations INTEGER;
    total_citations INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphaned_citations
    FROM citations c
    WHERE NOT EXISTS (SELECT 1 FROM paper_metadata pm WHERE pm.id = c.citing_paper_id)
       OR (c.cited_paper_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM paper_metadata pm WHERE pm.id = c.cited_paper_id));

    IF orphaned_citations > 0 THEN
        RAISE EXCEPTION 'Found % orphaned citations after migration', orphaned_citations;
    END IF;

    SELECT COUNT(*) INTO total_citations FROM citations;
END $$;

-- ============================================================================
-- PHASE 6: Migrate discovered_articles → research_question_matches
-- ============================================================================

-- Clean up orphaned article_research_matches (articles that no longer exist)
DELETE FROM article_research_matches arm
WHERE NOT EXISTS (
    SELECT 1 FROM discovered_articles da WHERE da.id = arm.article_id
);

-- Create deduplication mapping: discovered_articles → paper_metadata
CREATE TEMP TABLE article_to_paper_mapping AS
SELECT DISTINCT ON (da.id)
    da.id as article_id,
    pm.id as paper_metadata_id,
    CASE
        WHEN da.doi IS NOT NULL AND da.doi = pm.doi THEN 'doi'
        WHEN da.arxiv_id IS NOT NULL AND da.arxiv_id = pm.arxiv_id THEN 'arxiv_id'
        WHEN LOWER(REGEXP_REPLACE(da.title, '[^a-zA-Z0-9 ]', '', 'g')) = pm.title_normalized THEN 'title'
        ELSE NULL
    END as match_type
FROM discovered_articles da
LEFT JOIN paper_metadata pm ON (
    (da.doi IS NOT NULL AND da.doi = pm.doi) OR
    (da.arxiv_id IS NOT NULL AND da.arxiv_id = pm.arxiv_id) OR
    (LOWER(REGEXP_REPLACE(da.title, '[^a-zA-Z0-9 ]', '', 'g')) = pm.title_normalized)
)
ORDER BY da.id, match_type;

-- Insert discovered articles that don't exist in paper_metadata
INSERT INTO paper_metadata (
    doi, arxiv_id, title, title_normalized,
    authors, abstract, publication_date, year, journal,
    url, pdf_url,
    source_of_truth,
    created_at, updated_at
)
SELECT
    da.doi,
    da.arxiv_id,
    da.title,
    LOWER(REGEXP_REPLACE(da.title, '[^a-zA-Z0-9 ]', '', 'g')) as title_normalized,
    da.authors,
    da.abstract,
    da.publication_date,
    da.year,
    da.journal,
    da.url,
    da.pdf_url,
    'discovered' as source_of_truth,
    da.first_discovered_at as created_at,
    da.updated_at
FROM discovered_articles da
WHERE NOT EXISTS (
    SELECT 1 FROM article_to_paper_mapping m
    WHERE m.article_id = da.id AND m.paper_metadata_id IS NOT NULL
);

-- Recreate mapping table to include all newly inserted papers
DROP TABLE article_to_paper_mapping;

CREATE TEMP TABLE article_to_paper_mapping AS
SELECT DISTINCT ON (da.id)
    da.id as article_id,
    pm.id as paper_metadata_id,
    CASE
        WHEN da.doi IS NOT NULL AND da.doi = pm.doi THEN 'doi'
        WHEN da.arxiv_id IS NOT NULL AND da.arxiv_id = pm.arxiv_id THEN 'arxiv_id'
        WHEN LOWER(REGEXP_REPLACE(da.title, '[^a-zA-Z0-9 ]', '', 'g')) = pm.title_normalized THEN 'title'
        ELSE NULL
    END as match_type
FROM discovered_articles da
JOIN paper_metadata pm ON (
    (da.doi IS NOT NULL AND da.doi = pm.doi) OR
    (da.arxiv_id IS NOT NULL AND da.arxiv_id = pm.arxiv_id) OR
    (LOWER(REGEXP_REPLACE(da.title, '[^a-zA-Z0-9 ]', '', 'g')) = pm.title_normalized)
)
ORDER BY da.id, match_type;

-- Create new research_question_matches table
CREATE TABLE IF NOT EXISTS research_question_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID NOT NULL REFERENCES paper_metadata(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,

    -- Matching metadata
    relevance_score FLOAT CHECK (relevance_score BETWEEN 0 AND 1),
    matched_keywords TEXT[],
    matched_topics TEXT[],
    matched_authors TEXT[],
    discovered_via_source TEXT,

    -- User interaction
    is_viewed BOOLEAN DEFAULT false,
    is_bookmarked BOOLEAN DEFAULT false,
    user_sentiment TEXT CHECK (user_sentiment IN ('like', 'dislike', 'neutral', 'skip')),
    sentiment_recorded_at TIMESTAMPTZ,

    -- Timestamps
    matched_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(paper_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_rqm_paper_id ON research_question_matches(paper_id);
CREATE INDEX IF NOT EXISTS idx_rqm_question_id ON research_question_matches(question_id);
CREATE INDEX IF NOT EXISTS idx_rqm_relevance ON research_question_matches(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_rqm_matched_at ON research_question_matches(matched_at DESC);

-- Migrate data using mapping
INSERT INTO research_question_matches (
    id, paper_id, question_id,
    relevance_score, matched_keywords, matched_topics, matched_authors,
    discovered_via_source,
    is_viewed, is_bookmarked, user_sentiment, sentiment_recorded_at,
    matched_at, created_at, updated_at
)
SELECT
    arm.id,
    m.paper_metadata_id,
    arm.question_id,
    arm.relevance_score,
    arm.matched_keywords,
    arm.matched_topics,
    arm.matched_authors,
    arm.discovered_via_source,
    arm.is_viewed,
    arm.is_bookmarked,
    arm.user_sentiment,
    arm.sentiment_recorded_at,
    arm.matched_at,
    arm.matched_at as created_at,
    NOW() as updated_at
FROM article_research_matches arm
JOIN article_to_paper_mapping m ON m.article_id = arm.article_id;

-- Verify migration
DO $$
DECLARE
    old_count INTEGER;
    new_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO old_count FROM article_research_matches;
    SELECT COUNT(*) INTO new_count FROM research_question_matches;

    IF old_count != new_count THEN
        RAISE EXCEPTION 'Research matches migration failed: old=%, new=%', old_count, new_count;
    END IF;

END $$;

-- ============================================================================
-- PHASE 7: Update database functions
-- ============================================================================

-- Drop old functions
DROP FUNCTION IF EXISTS find_duplicate_article(TEXT, TEXT, TEXT);

-- Create new functions for paper_metadata
CREATE OR REPLACE FUNCTION find_duplicate_paper(
    p_doi TEXT,
    p_arxiv_id TEXT,
    p_title TEXT
) RETURNS UUID AS $$
DECLARE
    found_id UUID;
    normalized_title TEXT;
BEGIN
    -- Normalize title for fuzzy matching
    normalized_title := LOWER(REGEXP_REPLACE(p_title, '[^a-zA-Z0-9 ]', '', 'g'));

    -- Try exact DOI match
    IF p_doi IS NOT NULL AND p_doi != '' THEN
        SELECT id INTO found_id FROM paper_metadata WHERE doi = p_doi LIMIT 1;
        IF found_id IS NOT NULL THEN RETURN found_id; END IF;
    END IF;

    -- Try exact ArXiv ID match
    IF p_arxiv_id IS NOT NULL AND p_arxiv_id != '' THEN
        SELECT id INTO found_id FROM paper_metadata WHERE arxiv_id = p_arxiv_id LIMIT 1;
        IF found_id IS NOT NULL THEN RETURN found_id; END IF;
    END IF;

    -- Try normalized title match
    SELECT id INTO found_id FROM paper_metadata
    WHERE title_normalized = normalized_title LIMIT 1;

    RETURN found_id;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- PHASE 8: Rename old tables for safety
-- ============================================================================

ALTER TABLE papers RENAME TO papers_old_backup;
ALTER TABLE discovered_articles RENAME TO discovered_articles_old_backup;
ALTER TABLE article_research_matches RENAME TO article_research_matches_old_backup;

-- Drop old views that referenced discovered_articles
DROP VIEW IF EXISTS articles_with_discoveries;
DROP VIEW IF EXISTS pending_articles;
DROP VIEW IF EXISTS multi_source_articles;


-- ============================================================================
-- PHASE 9: Create backward compatibility view
-- ============================================================================

CREATE OR REPLACE VIEW papers AS
SELECT
    pm.id,
    pm.doi,
    pm.arxiv_id,
    NULL::TEXT as backup_id,  -- Deprecated field
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
    NULL::JSONB as s2_fields_of_study,  -- Deprecated
    pm.url,
    pm.pdf_url,
    pm.pdf_source,
    pp.obsidian_uri,
    pm.citation_count,
    pm.reference_count,
    pm.influential_citation_count,
    pm.is_open_access,
    CASE WHEN pm.source_of_truth = 'citation' THEN true ELSE false END as is_document_citation,
    pm.created_at,
    pm.updated_at,
    -- Processed paper fields
    pp.pdf_path,
    pp.markdown_path,
    pp.note_path,
    pp.processing_status,
    pp.user_notes,
    pp.user_rating,
    pp.user_tags,
    pp.analysis_schema_name,
    pp.analysis_schema_version,
    -- Full-text search
    pm.search_vector,
    pm.title  -- Add title explicitly
FROM paper_metadata pm
LEFT JOIN processed_papers pp ON pp.paper_id = pm.id;


-- ============================================================================
-- Final Verification
-- ============================================================================

DO $$
DECLARE
    pm_count INTEGER;
    pp_count INTEGER;
    rqm_count INTEGER;
    citations_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO pm_count FROM paper_metadata;
    SELECT COUNT(*) INTO pp_count FROM processed_papers;
    SELECT COUNT(*) INTO rqm_count FROM research_question_matches;
    SELECT COUNT(*) INTO citations_count FROM citations;

END $$;

COMMIT;

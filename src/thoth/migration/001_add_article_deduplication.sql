-- ============================================================================
-- Article Deduplication and Cross-Discovery Tracking Migration
-- ============================================================================
-- Purpose: Add tables and indexes for tracking articles across multiple discoveries
-- Version: 001
-- Date: 2025-12-03
-- ============================================================================

-- ============================================================================
-- DISCOVERED_ARTICLES: Unified article metadata with deduplication
-- ============================================================================

CREATE TABLE IF NOT EXISTS discovered_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Unique identifiers (for deduplication)
    doi TEXT,
    arxiv_id TEXT,
    title TEXT NOT NULL,
    title_normalized TEXT NOT NULL,  -- Lowercase, no punctuation for fuzzy matching

    -- Authors (JSONB for flexibility)
    authors JSONB DEFAULT '[]',
    first_author TEXT,  -- Extracted for quick filtering

    -- Publication Details
    abstract TEXT,
    publication_date DATE,
    journal TEXT,
    year INTEGER,

    -- URLs and Access
    url TEXT,
    pdf_url TEXT,

    -- Discovery Metadata
    first_discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    discovery_count INTEGER DEFAULT 1,  -- How many times discovered

    -- Processing Status
    processing_status TEXT DEFAULT 'pending',  -- pending, downloaded, processing, completed, failed, ignored
    paper_id UUID,  -- Future link to papers table when it exists (currently null)
    processed_at TIMESTAMP WITH TIME ZONE,

    -- Relevance Scoring
    max_relevance_score REAL,  -- Best relevance score across all discoveries
    priority INTEGER DEFAULT 5,  -- Processing priority (1-10)

    -- Additional metadata
    keywords JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',  -- Additional source-specific metadata

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_processing_status CHECK (
        processing_status IN ('pending', 'downloaded', 'processing', 'completed', 'failed', 'ignored')
    ),
    CONSTRAINT valid_year CHECK (year IS NULL OR (year >= 1900 AND year <= 2100))
);

-- Indexes for discovered_articles
CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_articles_doi
    ON discovered_articles(doi) WHERE doi IS NOT NULL AND doi != '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_articles_arxiv
    ON discovered_articles(arxiv_id) WHERE arxiv_id IS NOT NULL AND arxiv_id != '';

CREATE INDEX IF NOT EXISTS idx_discovered_articles_title_normalized
    ON discovered_articles(title_normalized);

CREATE INDEX IF NOT EXISTS idx_discovered_articles_status
    ON discovered_articles(processing_status, priority DESC, first_discovered_at);

CREATE INDEX IF NOT EXISTS idx_discovered_articles_last_seen
    ON discovered_articles(last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_discovered_articles_paper
    ON discovered_articles(paper_id) WHERE paper_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_discovered_articles_first_author
    ON discovered_articles(first_author) WHERE first_author IS NOT NULL;

-- Trigram index for fuzzy title matching
CREATE INDEX IF NOT EXISTS idx_discovered_articles_title_trgm
    ON discovered_articles USING GIN(title_normalized gin_trgm_ops);

-- Full-text search on title and abstract
CREATE INDEX IF NOT EXISTS idx_discovered_articles_search
    ON discovered_articles USING GIN(
        to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, ''))
    );

-- ============================================================================
-- ARTICLE_DISCOVERIES: Many-to-many relationship between articles and sources
-- ============================================================================

CREATE TABLE IF NOT EXISTS article_discoveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Relationships
    article_id UUID NOT NULL REFERENCES discovered_articles(id) ON DELETE CASCADE,
    source_name VARCHAR(100) NOT NULL REFERENCES available_sources(name) ON DELETE CASCADE,

    -- Discovery Context
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    discovery_query TEXT,  -- Query that found this article
    relevance_score REAL,  -- Relevance to discovery query
    rank_in_results INTEGER,  -- Position in search results

    -- Source-specific metadata
    source_metadata JSONB DEFAULT '{}',
    external_id TEXT,  -- Source-specific ID (e.g., arXiv ID, PubMed ID)

    -- Processing tracking
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Ensure unique article-source pairs
    UNIQUE(article_id, source_name)
);

-- Indexes for article_discoveries
CREATE INDEX IF NOT EXISTS idx_article_discoveries_article
    ON article_discoveries(article_id);

CREATE INDEX IF NOT EXISTS idx_article_discoveries_source
    ON article_discoveries(source_name);

CREATE INDEX IF NOT EXISTS idx_article_discoveries_time
    ON article_discoveries(discovered_at DESC);

CREATE INDEX IF NOT EXISTS idx_article_discoveries_processed
    ON article_discoveries(processed, discovered_at DESC) WHERE NOT processed;

CREATE INDEX IF NOT EXISTS idx_article_discoveries_relevance
    ON article_discoveries(relevance_score DESC NULLS LAST);

-- ============================================================================
-- TRIGGERS: Auto-update timestamps and maintain statistics
-- ============================================================================

-- Update updated_at timestamp on discovered_articles
CREATE OR REPLACE FUNCTION update_discovered_articles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER discovered_articles_updated_at
    BEFORE UPDATE ON discovered_articles
    FOR EACH ROW
    EXECUTE FUNCTION update_discovered_articles_updated_at();

-- Update discovery count and last_seen_at when new discovery is added
CREATE OR REPLACE FUNCTION update_article_discovery_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE discovered_articles
        SET
            discovery_count = discovery_count + 1,
            last_seen_at = CURRENT_TIMESTAMP,
            max_relevance_score = GREATEST(
                COALESCE(max_relevance_score, 0),
                COALESCE(NEW.relevance_score, 0)
            )
        WHERE id = NEW.article_id;

        -- Update discovery source statistics
        UPDATE available_sources
        SET
            total_papers_discovered = total_papers_discovered + 1,
            last_run_at = CURRENT_TIMESTAMP
        WHERE name = NEW.source_name;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER article_discoveries_stats
    AFTER INSERT ON article_discoveries
    FOR EACH ROW
    EXECUTE FUNCTION update_article_discovery_stats();

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function to normalize title for deduplication
CREATE OR REPLACE FUNCTION normalize_title(title TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN lower(
        regexp_replace(
            regexp_replace(title, '[^\w\s]', '', 'g'),  -- Remove punctuation
            '\s+', ' ', 'g'  -- Normalize whitespace
        )
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to find duplicate articles by identifiers
CREATE OR REPLACE FUNCTION find_duplicate_article(
    p_doi TEXT DEFAULT NULL,
    p_arxiv_id TEXT DEFAULT NULL,
    p_title TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    article_id UUID;
    normalized_title TEXT;
BEGIN
    -- Try DOI first (most reliable)
    IF p_doi IS NOT NULL AND p_doi != '' THEN
        SELECT id INTO article_id
        FROM discovered_articles
        WHERE doi = p_doi
        LIMIT 1;

        IF article_id IS NOT NULL THEN
            RETURN article_id;
        END IF;
    END IF;

    -- Try arXiv ID
    IF p_arxiv_id IS NOT NULL AND p_arxiv_id != '' THEN
        SELECT id INTO article_id
        FROM discovered_articles
        WHERE arxiv_id = p_arxiv_id
        LIMIT 1;

        IF article_id IS NOT NULL THEN
            RETURN article_id;
        END IF;
    END IF;

    -- Try normalized title (fuzzy match)
    IF p_title IS NOT NULL AND p_title != '' THEN
        normalized_title := normalize_title(p_title);

        SELECT id INTO article_id
        FROM discovered_articles
        WHERE title_normalized = normalized_title
        LIMIT 1;

        IF article_id IS NOT NULL THEN
            RETURN article_id;
        END IF;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Function to get new articles since timestamp for a source
CREATE OR REPLACE FUNCTION get_new_articles_since(
    p_source_name VARCHAR(100),
    p_since TIMESTAMP WITH TIME ZONE
)
RETURNS TABLE (
    article_id UUID,
    title TEXT,
    doi TEXT,
    arxiv_id TEXT,
    discovered_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        da.id,
        da.title,
        da.doi,
        da.arxiv_id,
        ad.discovered_at
    FROM discovered_articles da
    JOIN article_discoveries ad ON da.id = ad.article_id
    WHERE ad.source_name = p_source_name
      AND ad.discovered_at > p_since
      AND NOT ad.processed
    ORDER BY ad.discovered_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to check if article has been processed by a source
CREATE OR REPLACE FUNCTION has_article_been_processed(
    p_article_id UUID,
    p_source_name VARCHAR(100)
)
RETURNS BOOLEAN AS $$
DECLARE
    is_processed BOOLEAN;
BEGIN
    SELECT processed INTO is_processed
    FROM article_discoveries
    WHERE article_id = p_article_id
      AND source_name = p_source_name
    LIMIT 1;

    RETURN COALESCE(is_processed, FALSE);
END;
$$ LANGUAGE plpgsql;

-- Function to mark article as processed for a source
CREATE OR REPLACE FUNCTION mark_article_as_processed(
    p_article_id UUID,
    p_source_name VARCHAR(100)
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE article_discoveries
    SET
        processed = TRUE,
        processed_at = CURRENT_TIMESTAMP
    WHERE article_id = p_article_id
      AND source_name = p_source_name;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS: Convenient access patterns
-- ============================================================================

-- Articles with discovery information
CREATE OR REPLACE VIEW articles_with_discoveries AS
SELECT
    da.*,
    COUNT(DISTINCT ad.source_name) as source_count,
    array_agg(DISTINCT ad.source_name) as source_names,
    MAX(ad.discovered_at) as latest_discovery,
    MIN(ad.discovered_at) as earliest_discovery
FROM discovered_articles da
LEFT JOIN article_discoveries ad ON da.id = ad.article_id
GROUP BY da.id;

-- Pending articles ordered by priority
CREATE OR REPLACE VIEW pending_articles AS
SELECT *
FROM discovered_articles
WHERE processing_status = 'pending'
ORDER BY priority DESC, first_discovered_at;

-- Articles discovered by multiple sources
CREATE OR REPLACE VIEW multi_source_articles AS
SELECT
    da.*,
    COUNT(DISTINCT ad.source_name) as source_count
FROM discovered_articles da
JOIN article_discoveries ad ON da.id = ad.article_id
GROUP BY da.id
HAVING COUNT(DISTINCT ad.source_name) > 1
ORDER BY source_count DESC, da.max_relevance_score DESC NULLS LAST;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE discovered_articles IS 'Unified article metadata with deduplication across discovery sources';
COMMENT ON TABLE article_discoveries IS 'Many-to-many relationship tracking which sources discovered which articles';
COMMENT ON COLUMN discovered_articles.title_normalized IS 'Normalized title for fuzzy deduplication matching';
COMMENT ON COLUMN discovered_articles.discovery_count IS 'Number of times this article was discovered across all sources';
COMMENT ON COLUMN discovered_articles.max_relevance_score IS 'Best relevance score across all discoveries';
COMMENT ON COLUMN article_discoveries.processed IS 'Whether this article has been processed for this specific source';

-- ============================================================================
-- DATA MIGRATION: Migrate existing discovered_papers data
-- ============================================================================

-- Migrate data from old discovered_papers table if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'discovered_papers') THEN
        -- Insert unique articles from discovered_papers into discovered_articles
        INSERT INTO discovered_articles (
            doi, arxiv_id, title, title_normalized,
            authors, first_author, abstract,
            publication_date, journal, year,
            url, pdf_url,
            first_discovered_at, last_seen_at,
            processing_status, paper_id, processed_at,
            max_relevance_score, priority,
            keywords, metadata,
            created_at, updated_at
        )
        SELECT DISTINCT ON (COALESCE(doi, ''), COALESCE(arxiv_id, ''), LOWER(title))
            doi,
            arxiv_id,
            title,
            normalize_title(title),
            authors,
            CASE
                WHEN authors IS NOT NULL AND jsonb_array_length(authors) > 0
                THEN authors->0->>'name'
                ELSE NULL
            END,
            abstract,
            publication_date,
            journal,
            EXTRACT(YEAR FROM publication_date)::INTEGER,
            url,
            pdf_url,
            discovered_at,
            discovered_at,
            status,
            paper_id,
            processed_at,
            relevance_score,
            priority,
            COALESCE(discovery_metadata->'keywords', '[]'::jsonb),
            discovery_metadata,
            created_at,
            updated_at
        FROM discovered_papers
        WHERE title IS NOT NULL
        ON CONFLICT (doi) DO NOTHING;

        RAISE NOTICE 'Migrated data from discovered_papers to discovered_articles';
    END IF;
END $$;

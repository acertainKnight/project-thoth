-- Migration: Add analysis schema metadata columns to papers table
-- Description: Adds columns to track which analysis schema was used for each paper
-- Date: 2026-01-09
-- Version: 003

-- Add schema_name column (e.g., 'standard', 'detailed', 'minimal', 'custom')
ALTER TABLE papers
ADD COLUMN IF NOT EXISTS analysis_schema_name VARCHAR(100) DEFAULT 'default';

-- Add schema_version column (e.g., '1.0')
ALTER TABLE papers
ADD COLUMN IF NOT EXISTS analysis_schema_version VARCHAR(50) DEFAULT 'default';

-- Add index for schema queries
CREATE INDEX IF NOT EXISTS idx_papers_schema_name ON papers(analysis_schema_name);

-- Add comment explaining the columns
COMMENT ON COLUMN papers.analysis_schema_name IS 'Name of the analysis preset used (standard, detailed, minimal, custom, or default for legacy)';
COMMENT ON COLUMN papers.analysis_schema_version IS 'Version of the analysis schema file used (e.g., 1.0)';

-- For existing papers, set to 'default' to indicate they were processed with the original schema
UPDATE papers
SET analysis_schema_name = 'default', analysis_schema_version = 'default'
WHERE analysis_schema_name IS NULL OR analysis_schema_version IS NULL;

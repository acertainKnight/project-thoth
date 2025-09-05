-- =============================================================================
-- Letta Memory Database Initialization
-- =============================================================================

-- Create the database if it doesn't exist (handled by POSTGRES_DB env var)

-- Enable pgvector extension for vector operations
CREATE EXTENSION IF NOT EXISTS vector;

-- Create schema for Thoth memory namespace
CREATE SCHEMA IF NOT EXISTS thoth_memory;

-- Set default schema
SET search_path TO thoth_memory, public;

-- Create indexes for better performance
-- (Letta will create its own tables, these are optimizations)

-- Index for agent lookups
CREATE INDEX IF NOT EXISTS idx_agents_name ON agents (name);
CREATE INDEX IF NOT EXISTS idx_agents_created_at ON agents (created_at);

-- Index for memory operations
CREATE INDEX IF NOT EXISTS idx_messages_agent_id ON messages (agent_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages (created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages (role);

-- Index for archival memory searches
CREATE INDEX IF NOT EXISTS idx_archival_agent_id ON archival_memory (agent_id);
CREATE INDEX IF NOT EXISTS idx_archival_created_at
ON archival_memory (created_at);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_messages_agent_role_date
ON messages (agent_id, role, created_at);
CREATE INDEX IF NOT EXISTS idx_archival_agent_date
ON archival_memory (agent_id, created_at);

-- Grant permissions to letta user
GRANT ALL PRIVILEGES ON SCHEMA thoth_memory TO letta_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA thoth_memory TO letta_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA thoth_memory TO letta_user;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA thoth_memory
GRANT ALL ON TABLES TO letta_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA thoth_memory
GRANT ALL ON SEQUENCES TO letta_user;

-- Performance settings for memory operations
-- Note: These require superuser privileges and may need to be set
-- in postgresql.conf instead of via ALTER SYSTEM
-- ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements,auto_explain';
-- ALTER SYSTEM SET pg_stat_statements.track = 'all';
-- ALTER SYSTEM SET auto_explain.log_min_duration = '1s';

-- Vector search optimization
-- ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
-- ALTER SYSTEM SET max_parallel_workers = 8;

-- Memory settings for vector operations
-- ALTER SYSTEM SET work_mem = '256MB';
-- ALTER SYSTEM SET maintenance_work_mem = '512MB';

-- Reload configuration
-- SELECT pg_reload_conf ();

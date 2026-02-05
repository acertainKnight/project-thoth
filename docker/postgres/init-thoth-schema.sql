-- Thoth PostgreSQL Extensions
-- Table creation is handled by MigrationManager during setup wizard
-- This script only ensures required extensions are available

\connect thoth

-- Enable required extensions (needs superuser privileges)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Grant extension usage to thoth user
GRANT USAGE ON SCHEMA public TO thoth;

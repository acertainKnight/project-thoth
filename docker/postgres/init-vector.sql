-- PostgreSQL initialization script for Letta with pgvector support
-- This script creates the necessary extensions for Letta's vector storage capabilities

-- Create the vector extension for similarity search and embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the uuid extension for UUID generation (often used by Letta)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant necessary privileges to the letta user
GRANT ALL PRIVILEGES ON DATABASE letta TO letta;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'PostgreSQL database initialized successfully for Letta';
    RAISE NOTICE 'Extensions created: vector, uuid-ossp';
    RAISE NOTICE 'Privileges granted to user: letta';
END
$$;

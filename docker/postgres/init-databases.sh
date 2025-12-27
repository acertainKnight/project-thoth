#!/bin/bash
# PostgreSQL initialization script for Letta and Thoth databases
# This script creates both databases with necessary extensions

set -e

echo "==> Initializing PostgreSQL databases..."

# Create Thoth database and user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    -- Create thoth user if it doesn't exist
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'thoth') THEN
            CREATE USER thoth WITH PASSWORD 'thoth_password';
        END IF;
    END
    \$\$;

    -- Create thoth database if it doesn't exist
    SELECT 'CREATE DATABASE thoth OWNER thoth ENCODING UTF8'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'thoth')\gexec

    -- Grant privileges
    GRANT ALL PRIVILEGES ON DATABASE thoth TO thoth;

    \echo '==> Created thoth database and user'
EOSQL

# Connect to thoth database and create extensions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname=thoth <<-EOSQL
    -- Create extensions for Thoth
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Grant schema privileges to thoth user
    GRANT ALL ON SCHEMA public TO thoth;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO thoth;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO thoth;

    -- Set default privileges for future tables
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO thoth;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO thoth;

    \echo '==> Initialized thoth database with extensions'
EOSQL

# Connect to letta database and create extensions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname=letta <<-EOSQL
    -- Create extensions for Letta
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

    -- Grant privileges to letta user
    GRANT ALL PRIVILEGES ON DATABASE letta TO letta;
    GRANT ALL ON SCHEMA public TO letta;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO letta;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO letta;

    -- Set default privileges for future tables
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO letta;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO letta;

    \echo '==> Initialized letta database with extensions'
EOSQL

echo "==> PostgreSQL initialization complete!"
echo "  ✓ thoth database created (user: thoth)"
echo "  ✓ letta database created (user: letta)"
echo "  ✓ Extensions: uuid-ossp, vector"

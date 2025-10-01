#!/bin/bash
set -e

# Enable pgvector extension for Letta database
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    \dx vector
EOSQL

echo "pgvector extension installed successfully"

#!/bin/bash
set -e

echo "==> Initializing Letta database schema..."

# Wait for PostgreSQL to be ready
until python3 -c "import psycopg2; psycopg2.connect('$LETTA_PG_URI')" 2>/dev/null; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done

echo "PostgreSQL is ready!"

# Create schema using Letta ORM
python3 << 'EOF'
import os
from letta.orm import Base
from sqlalchemy import create_engine, inspect

# Get connection string from environment
pg_uri = os.environ.get('LETTA_PG_URI')
print(f"Creating schema with URI: {pg_uri}")

# Create engine and tables
engine = create_engine(pg_uri, echo=True)
Base.metadata.create_all(engine)

# Verify tables were created
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"\n==> Created {len(tables)} tables:")
for table in sorted(tables):
    print(f"  ✓ {table}")

if 'organizations' in tables:
    print("\n==> Schema initialization successful!")
else:
    print("\n==> ERROR: organizations table not found!")
    exit(1)
EOF

echo "==> Starting Letta server..."
exec letta server --host 0.0.0.0 --port 8283 --ade

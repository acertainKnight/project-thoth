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

# Register Thoth MCP server in database
echo "==> Registering Thoth MCP server in database..."
python3 << 'EOF'
import os
import uuid
from sqlalchemy import create_engine, text

pg_uri = os.environ.get('LETTA_PG_URI')
engine = create_engine(pg_uri)

# Check if MCP server already registered
with engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM mcp_server WHERE server_name = 'thoth-research-tools'"))
    count = result.scalar()

    if count == 0:
        # Insert MCP server registration
        # Note: Letta requires 'mcp_server-' prefix (underscore, not hyphen)
        mcp_server_id = f"mcp_server-{uuid.uuid4()}"
        conn.execute(text("""
            INSERT INTO mcp_server (
                id, server_name, server_type, server_url,
                organization_id, is_deleted,
                _created_by_id, _last_updated_by_id
            ) VALUES (
                :id, :name, :type, :url,
                'org-00000000-0000-4000-8000-000000000000', false,
                'user-00000000-0000-4000-8000-000000000000',
                'user-00000000-0000-4000-8000-000000000000'
            )
        """), {
            "id": mcp_server_id,
            "name": "thoth-research-tools",
            "type": "streamable_http",
            "url": "http://thoth-mcp:8000/mcp"
        })
        conn.commit()
        print(f"✓ Registered Thoth MCP server: {mcp_server_id}")
    else:
        print("✓ Thoth MCP server already registered")
EOF

echo "==> Starting Letta server..."
exec letta server --host 0.0.0.0 --port 8283 --ade

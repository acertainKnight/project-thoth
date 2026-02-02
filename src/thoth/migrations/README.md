# Database Migrations

This directory contains versioned SQL migrations for the Thoth database schema.

## How It Works

- **Migration Manager**: Tracks applied migrations in a `schema_migrations` table
- **Version Control**: Migrations are numbered (001, 002, 003, etc.)
- **Idempotent**: Safe to run multiple times - only pending migrations are applied
- **Transactional**: Each migration runs in a transaction (rolls back on error)

## Migration Files

Migrations must follow the naming convention:
```
NNN_description.sql
```

Where:
- `NNN` is a 3-digit version number (001, 002, 003, etc.)
- `description` is a short snake_case description
- Extension must be `.sql`

Example: `001_initial_schema.sql`

## Applying Migrations

### During Setup Wizard

Migrations are automatically applied when running the setup wizard:
```bash
thoth setup
```

### Manual Migration

To apply pending migrations to an existing database:
```bash
thoth db migrate
```

### Check Status

To see which migrations have been applied:
```bash
thoth db status
```

Output shows:
- Applied migration count
- Pending migration count
- Current database version
- List of pending migrations (if any)

### Reset Database (DANGER!)

To drop all tables and re-run migrations from scratch:
```bash
thoth db reset --confirm
```

**WARNING**: This will delete ALL data!

## Creating New Migrations

1. **Choose Next Version Number**
   ```bash
   ls src/thoth/migrations/*.sql
   # If latest is 001_initial_schema.sql, use 002 for next migration
   ```

2. **Create Migration File**
   ```bash
   touch src/thoth/migrations/002_add_new_feature.sql
   ```

3. **Write SQL**
   ```sql
   -- Add your DDL statements
   CREATE TABLE IF NOT EXISTS new_table (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       name TEXT NOT NULL,
       created_at TIMESTAMPTZ DEFAULT NOW()
   );

   CREATE INDEX IF NOT EXISTS idx_new_table_name ON new_table(name);
   ```

4. **Use IF NOT EXISTS**
   Always use `IF NOT EXISTS` for CREATE statements to make migrations safe to re-run.

5. **Test Migration**
   ```bash
   # Check what will be applied
   thoth db status

   # Apply the migration
   thoth db migrate
   ```

## Migration Best Practices

### ✅ DO:
- Use `IF NOT EXISTS` / `IF EXISTS` for safety
- Write both forward (CREATE) and backward (DROP) compatible SQL
- Test migrations on a copy of production data first
- Keep migrations small and focused
- Add comments explaining complex changes
- Use transactions implicitly (migration manager handles this)

### ❌ DON'T:
- Don't modify existing migration files after they've been applied
- Don't delete migration files
- Don't skip version numbers
- Don't mix DDL and large data migrations in one file
- Don't use database-specific features that break PostgreSQL compatibility

## Migration Tracking

The `schema_migrations` table tracks all applied migrations:

```sql
SELECT * FROM schema_migrations ORDER BY version;
```

Columns:
- `version` - Migration version number (primary key)
- `name` - Migration filename (without extension)
- `applied_at` - Timestamp when migration was applied
- `checksum` - (Future) File content hash for verification
- `execution_time_ms` - How long the migration took

## Troubleshooting

### Migration Failed Mid-Execution

Migrations run in transactions, so failed migrations automatically roll back. Fix the SQL and run `thoth db migrate` again.

### "Migration already applied" Error

The migration manager checks the `schema_migrations` table before applying. This error means the migration was already successfully applied.

### Manual Recovery

If you need to manually mark a migration as applied:
```sql
INSERT INTO schema_migrations (version, name)
VALUES (1, '001_initial_schema');
```

To force re-run a migration (dangerous):
```sql
DELETE FROM schema_migrations WHERE version = 1;
-- Then run: thoth db migrate
```

## Current Migrations

### 001_initial_schema.sql

Initial database schema with new architecture:

**Tables Created:**
- `paper_metadata` - Single source of truth for all papers (processed, cited, discovered)
- `processed_papers` - Papers the user has read/processed (with file paths)
- `research_question_matches` - Papers matched to research questions
- `schema_migrations` - Migration tracking (auto-created by migration manager)

**Views Created:**
- `papers` - Backward-compatible view joining paper_metadata + processed_papers

**Key Features:**
- Deduplication via DOI, arXiv ID, and normalized title
- Full-text search with `tsvector`
- Foreign keys with proper CASCADE rules
- JSONB for flexible metadata (authors, keywords, etc.)
- Comprehensive indexing for performance

## Future Migrations

When adding new migrations:
1. Increment version number: 002, 003, etc.
2. Follow naming convention: `NNN_description.sql`
3. Document changes in this README
4. Test thoroughly before committing

## Examples

### Adding a Column

```sql
-- 002_add_user_rating.sql
ALTER TABLE processed_papers
ADD COLUMN IF NOT EXISTS user_rating INTEGER
CHECK (user_rating >= 1 AND user_rating <= 5);

CREATE INDEX IF NOT EXISTS idx_processed_papers_rating
ON processed_papers(user_rating)
WHERE user_rating IS NOT NULL;
```

### Adding a Table

```sql
-- 003_add_reading_sessions.sql
CREATE TABLE IF NOT EXISTS reading_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID NOT NULL REFERENCES paper_metadata(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    pages_read INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reading_sessions_paper
ON reading_sessions(paper_id);

CREATE INDEX IF NOT EXISTS idx_reading_sessions_user
ON reading_sessions(user_id, started_at DESC);
```

### Data Migration

```sql
-- 004_migrate_legacy_tags.sql
-- Migrate old tag format to new format
UPDATE paper_metadata
SET keywords = (
    SELECT jsonb_agg(jsonb_build_object('name', tag))
    FROM unnest(string_to_array(legacy_tags, ',')) AS tag
)
WHERE legacy_tags IS NOT NULL;

-- Drop old column after migration
ALTER TABLE paper_metadata DROP COLUMN IF EXISTS legacy_tags;
```

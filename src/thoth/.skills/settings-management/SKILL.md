---
name: settings-management
description: View and modify Thoth configuration settings. Use when user wants to
  change API keys, paths, search settings, or other configuration options.
tools:
- view_settings
- update_settings
- validate_settings
- reset_settings
- migrate_settings
---

# Settings Management

Manage Thoth configuration including API credentials, file paths, search parameters, and system behavior. Settings are stored in `thoth.settings.json` and persist across sessions.

## Overview

The settings system provides:
1. **Centralized Configuration** - All settings in one place
2. **Validation** - Schema-based validation prevents errors
3. **Sections** - Organized by feature area
4. **Persistence** - Changes saved to file automatically

## Core Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `view_settings` | Display current configuration | Check current values |
| `update_settings` | Modify settings | Change configuration |
| `validate_settings` | Check settings validity | After changes or troubleshooting |
| `reset_settings` | Restore defaults | Fix broken configuration |
| `migrate_settings` | Import from environment | First-time setup |

## Settings Sections

### API Configuration (`api`)

```json
{
  "api": {
    "openai_api_key": "sk-...",
    "anthropic_api_key": "sk-ant-...",
    "semantic_scholar_api_key": "...",
    "openalex_email": "user@example.com"
  }
}
```

### File Paths (`paths`)

```json
{
  "paths": {
    "vault_path": "/path/to/obsidian/vault",
    "pdf_directory": "thoth/papers/pdfs",
    "data_directory": "thoth/data",
    "backup_directory": "thoth/backups"
  }
}
```

### RAG Settings (`rag`)

```json
{
  "rag": {
    "embedding_model": "text-embedding-3-small",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "collection_name": "thoth_articles"
  }
}
```

### Search Settings (`search`)

```json
{
  "search": {
    "default_limit": 10,
    "min_relevance": 0.7,
    "hybrid_search": true,
    "sources": ["semantic_scholar", "openalex", "arxiv"]
  }
}
```

### Discovery Settings (`discovery`)

```json
{
  "discovery": {
    "default_max_papers": 50,
    "default_relevance_threshold": 0.7,
    "auto_discovery_enabled": false,
    "discovery_interval_hours": 24
  }
}
```

### Database Settings (`database`)

```json
{
  "database": {
    "connection_string": "postgresql://...",
    "pool_size": 5
  }
}
```

## Viewing Settings

### View All Settings
```
view_settings()
→ Returns complete settings object
```

### View Specific Section
```
view_settings(section="api")
→ Returns only API configuration

view_settings(section="paths")
→ Returns only path configuration
```

### View Single Setting
```
view_settings(section="rag", key="embedding_model")
→ Returns: "text-embedding-3-small"
```

## Updating Settings

### Update Single Value
```
update_settings(
  section="search",
  updates={"default_limit": 20}
)
```

### Update Multiple Values
```
update_settings(
  section="rag",
  updates={
    "chunk_size": 1200,
    "chunk_overlap": 300
  }
)
```

### Important Notes
- Changes are validated before saving
- Some changes require service restart
- Some changes require reindexing (see RAG Administration skill)

## Validation

### Check Settings Validity
```
validate_settings()
→ Returns validation results

Example output:
{
  "valid": true,
  "warnings": [
    "semantic_scholar_api_key not set - rate limits will apply"
  ],
  "errors": []
}
```

### Common Validation Issues

| Issue | Solution |
|-------|----------|
| Missing required field | Set the field with update_settings |
| Invalid path | Check path exists and is accessible |
| Invalid API key format | Verify key is correctly copied |
| Invalid value type | Check expected type in schema |

## Resetting Settings

### Reset Single Section
```
reset_settings(section="search")
→ Restores search settings to defaults
```

### Reset All Settings
```
reset_settings(all=true)
→ Restores entire configuration to defaults
```

**Warning**: Reset will overwrite current values. Consider backup first.

## Migration from Environment Variables

For first-time setup or transitioning from `.env` files:

```
migrate_settings()
→ Imports settings from environment variables

Migrated:
- OPENAI_API_KEY → api.openai_api_key
- VAULT_PATH → paths.vault_path
- POSTGRES_URL → database.connection_string
...
```

## Workflow Examples

### Example 1: Change Vault Path

**User**: "I moved my Obsidian vault to a new location"

```
1. View current path
   view_settings(section="paths", key="vault_path")
   → /old/path/to/vault

2. Update path
   update_settings(
     section="paths",
     updates={"vault_path": "/new/path/to/vault"}
   )

3. Validate
   validate_settings()
   → valid: true

4. Response:
   "Updated your vault path to /new/path/to/vault.
   Changes are saved and will take effect immediately."
```

### Example 2: Configure API Keys

**User**: "I need to set up my Semantic Scholar API key"

```
1. Get current state
   view_settings(section="api")
   → Shows current API keys (masked)

2. Update key
   update_settings(
     section="api",
     updates={"semantic_scholar_api_key": "user-provided-key"}
   )

3. Validate
   validate_settings()
   → Check for warnings/errors

4. Response:
   "Semantic Scholar API key configured.
   You'll now have higher rate limits for paper discovery."
```

### Example 3: Optimize Search Configuration

**User**: "My searches are returning too few results"

```
1. Check current search settings
   view_settings(section="search")
   → default_limit: 10, min_relevance: 0.8

2. Adjust settings
   update_settings(
     section="search",
     updates={
       "default_limit": 25,
       "min_relevance": 0.6,
       "hybrid_search": true
     }
   )

3. Response:
   "Search settings updated:
   - Results limit: 10 → 25
   - Relevance threshold: 0.8 → 0.6 (more inclusive)
   - Hybrid search: enabled (combines semantic + keyword)

   Try your search again - you should see more results."
```

### Example 4: First-Time Setup

**User**: "I just installed Thoth, help me configure it"

```
1. Try migration from environment
   migrate_settings()
   → Imported 5 settings from environment

2. Check for missing required settings
   validate_settings()
   → warnings: ["vault_path not set"]

3. Set required paths
   update_settings(
     section="paths",
     updates={
       "vault_path": "/path/to/obsidian/vault",
       "pdf_directory": "thoth/papers/pdfs"
     }
   )

4. Verify API keys
   view_settings(section="api")
   → Check which keys are configured

5. Response:
   "Initial configuration complete!

   Configured:
   ✓ OpenAI API key
   ✓ Vault path
   ✓ PDF directory

   Optional (not configured):
   - Semantic Scholar API key (higher rate limits)
   - Anthropic API key (alternative LLM)

   You can now start using Thoth. Would you like me to:
   - Run a test search to verify everything works?
   - Help you import existing PDFs?"
```

## Settings Reference

### Required Settings

| Setting | Section | Purpose |
|---------|---------|---------|
| `openai_api_key` | api | LLM and embeddings |
| `vault_path` | paths | Obsidian vault location |

### Recommended Settings

| Setting | Section | Default | Purpose |
|---------|---------|---------|---------|
| `pdf_directory` | paths | thoth/papers/pdfs | PDF storage |
| `chunk_size` | rag | 1000 | RAG chunk size |
| `min_relevance` | search | 0.7 | Search threshold |

### Optional Settings

| Setting | Section | Purpose |
|---------|---------|---------|
| `semantic_scholar_api_key` | api | Higher rate limits |
| `anthropic_api_key` | api | Alternative LLM |
| `auto_discovery_enabled` | discovery | Background searches |

## Best Practices

### Security
- Never share API keys in chat
- Use environment variables for sensitive values in shared configs
- API keys are masked in view_settings output

### Configuration Changes
- Always validate after making changes
- Some RAG changes require reindexing (use RAG Administration skill)
- Test after major configuration changes

### Backup
- Settings are in `thoth.settings.json`
- Back up before major changes
- Use reset_settings cautiously

## Troubleshooting

### Settings Not Taking Effect
```
1. Validate settings: validate_settings()
2. Check for errors in validation output
3. Restart services if required
4. For RAG changes, run reindex
```

### Invalid Settings File
```
1. Try validate_settings() for specific errors
2. Reset specific section: reset_settings(section="broken_section")
3. As last resort: reset_settings(all=true)
```

### Missing Settings After Update
```
1. Check if migration was run: migrate_settings()
2. Verify file permissions on settings file
3. Check for typos in section/key names
```

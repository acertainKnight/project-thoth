# Multi-User Mode

Thoth supports running on a shared server where multiple users each have:

- Their own isolated Obsidian vault directory (`/vaults/{username}/`)
- Their own Letta agents (`thoth_main_orchestrator_{username}`, etc.)
- Their own scoped database rows (all tables have a `user_id` column)
- A unique API token for authentication

Single-user installations are **completely unaffected** — multi-user mode is opt-in.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│               Thoth Server (shared)                 │
│                                                     │
│  ┌───────────────┐    ┌───────────────────────────┐ │
│  │ TokenAuth     │    │ ServiceManager            │ │
│  │ Middleware    │───▶│  auth: AuthService        │ │
│  │               │    │  vault_provisioner:       │ │
│  │ Bearer token  │    │    VaultProvisioner       │ │
│  │ → UserContext │    └───────────────────────────┘ │
│  └───────────────┘                                  │
│                                                     │
│  /vaults/alice/thoth/  ← Alice's vault              │
│  /vaults/bob/thoth/    ← Bob's vault                │
│                                                     │
│  PostgreSQL:                                        │
│    users table (one row per user)                   │
│    research_questions.user_id                       │
│    discovery_schedule.user_id                       │
│    workflow_search_config.user_id                   │
│    (etc — all tenant tables have user_id)           │
│                                                     │
│  Letta:                                             │
│    thoth_main_orchestrator_alice                    │
│    thoth_research_analyst_alice                     │
│    thoth_main_orchestrator_bob                      │
└─────────────────────────────────────────────────────┘
```

---

## Server Setup

### 1. Enable multi-user mode in `.env`

```bash
THOTH_MULTI_USER=true
THOTH_VAULTS_ROOT=/vaults          # Host path for all user vaults
THOTH_ALLOW_REGISTRATION=false     # true = self-registration allowed
```

Or use the Makefile helper:

```bash
make multi-user-enable
```

### 2. Create the vaults directory

```bash
mkdir -p /vaults
```

### 3. Run database migrations

```bash
make db-migrate
# or: uv run thoth db migrate
```

Migration 007 creates the `users` table and adds `user_id` to all
tenant-scoped tables.

### 4. Create the first admin user

```bash
make user-create USERNAME=admin ADMIN=true
# or: uv run thoth users create admin --admin
```

The command prints a one-time API token. **Save it immediately** — it
cannot be retrieved again (use `user-reset-token` to regenerate).

### 5. Start the server

```bash
docker compose up -d
```

---

## User Onboarding

### Option A: Admin creates the account (recommended)

```bash
# On the server:
make user-create USERNAME=alice EMAIL=alice@lab.com
```

Copy the token and share it securely with the user (e.g. via Signal,
password manager, or encrypted email).

### Option B: Self-registration (if enabled)

```bash
curl -X POST https://thoth.yourlab.com:8080/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username": "alice", "email": "alice@lab.com"}'
```

Requires `THOTH_ALLOW_REGISTRATION=true`.

---

## User Setup (Obsidian Plugin)

Each user configures the plugin once:

1. Open Obsidian → Settings → Thoth
2. Set **Thoth API URL** to the server address (e.g. `https://thoth.yourlab.com:8080`)
3. Set **API Token** to the token provided by the admin (`thoth_…`)
4. Click **Verify Token & Connection** — the plugin confirms your username
5. Save settings

The plugin automatically:
- Resolves your personal Letta agent via `/auth/me` (no manual agent ID needed)
- Includes `Authorization: Bearer <token>` in all API requests
- Adds `?token=<token>` to WebSocket connections

---

## CLI Commands

All user management commands connect directly to the database and do not
require the server to be running.

| Command | Description |
|---------|-------------|
| `thoth users create <username> [--email EMAIL] [--admin]` | Create user + print token |
| `thoth users list` | List all users |
| `thoth users info <username>` | Show user details + agent IDs |
| `thoth users reset-token <username>` | Generate new token (old one stops working) |
| `thoth users deactivate <username>` | Deactivate account |

### Makefile shortcuts

```bash
make user-create USERNAME=alice EMAIL=alice@lab.com
make user-list
make user-info USERNAME=alice
make user-reset-token USERNAME=alice
make user-deactivate USERNAME=alice
```

---

## Testing the Multi-User Implementation

### Unit tests

The unit test suite covers: token generation, user lookup, inactive user
rejection, middleware in single-user mode, 401 on missing token, valid
token resolution, and `resolve_user_vault_path()`.

```bash
uv run pytest tests/unit/server/test_multi_user_auth.py -v
```

All 14 tests should pass with no database required.

### Smoke test migration against the live DB (single-user mode, safe)

Before enabling multi-user mode you can verify migration 007 runs cleanly
on the live database while the server is still in single-user mode:

```bash
docker exec thoth-dev-api python -m thoth db migrate
```

Migration 007 is **additive only** — it adds `user_id TEXT NOT NULL DEFAULT 'default_user'`
columns to all tenant tables and creates the `users` table. No existing
rows are modified and the server keeps running throughout.

Verify the new tables and columns exist:

```bash
docker exec letta-postgres psql -U thoth -d thoth -c "\dt users"
docker exec letta-postgres psql -U thoth -d thoth \
  -c "SELECT column_name FROM information_schema.columns \
      WHERE table_name = 'research_questions' AND column_name = 'user_id';"
```

### Smoke test the API endpoints

```bash
# Health check (always exempt from auth)
curl http://localhost:8080/health

# In single-user mode — no token needed, returns default_user context
curl http://localhost:8080/auth/me

# After enabling multi-user mode and creating a user:
curl http://localhost:8080/auth/me \
  -H "Authorization: Bearer thoth_your_token_here"
```

---

## Upgrading a Single-User Installation

Existing single-user installations can be upgraded without data loss.
The upgrade is safe to run with containers live — the migration is additive only.

### CLI path (Docker-based deployment)

```bash
# 1. Pull latest code and rebuild images
git pull
docker compose build thoth-api thoth-mcp

# 2. Run migration 007 while the existing containers are still running.
#    This is additive-only (adds columns, creates users table) — no downtime.
docker compose run --rm thoth-api python -m thoth db migrate

# 3. Verify migration succeeded
docker exec letta-postgres psql -U thoth -d thoth \
  -c "SELECT version, name FROM _migrations ORDER BY version;"
# Should show version 7 - add_multi_user_support

# 4. Restart with new images (still single-user mode — nothing changes yet)
docker compose up -d

# 5. Confirm existing behaviour is unchanged
curl http://localhost:8080/health      # → 200 OK
curl http://localhost:8080/auth/me     # → {"username": "default_user", ...}

# 6. Enable multi-user mode when ready
echo "THOTH_MULTI_USER=true" >> .env
echo "THOTH_VAULTS_ROOT=/vaults" >> .env
mkdir -p /vaults

# 7. Create the first admin account (DB-direct, no server restart needed)
uv run thoth users create admin --admin
# ← Token is printed once — save it securely

# 8. Restart services with multi-user mode enabled
docker compose up -d

# 9. Verify multi-user mode is active
curl http://localhost:8080/auth/me
# → 401 Unauthorized  (token now required)

curl http://localhost:8080/auth/me \
  -H "Authorization: Bearer thoth_your_admin_token"
# → {"username": "admin", "vault_path": "/vaults/admin", ...}
```

### CLI path (local/dev deployment)

```bash
# 1. Pull latest code
git pull

# 2. Enable multi-user mode
echo "THOTH_MULTI_USER=true" >> .env
echo "THOTH_VAULTS_ROOT=/vaults" >> .env

# 3. Run migrations (adds user_id columns, creates users table)
uv run thoth db migrate

# 4. Migrate existing data to 'default_user' (already the default)
# All existing rows were inserted with DEFAULT 'default_user'
# so no data migration SQL is needed.

# 5. Create an admin account
uv run thoth users create admin --admin

# 6. Restart services
docker compose up -d
```

### Setup wizard path

Run `thoth setup` and choose **Multi-User Server** when prompted for
deployment type. The wizard handles migrations and creates the first
admin account.

---

## Authentication Flow

```
Obsidian Plugin               Thoth API Server
      │                              │
      │  GET /auth/me                │
      │  Authorization: Bearer thoth_xxx  │
      │─────────────────────────────▶│
      │                              │ TokenAuthMiddleware:
      │                              │  1. Extract Bearer token
      │                              │  2. Look up in users table
      │                              │  3. Build UserContext
      │                              │    (user_id, username,
      │                              │     vault_path, is_admin)
      │                              │  4. Set request.state.user_context
      │  200 OK UserInfo             │
      │  (orchestrator_agent_id,     │
      │   analyst_agent_id, …)       │
      │◀─────────────────────────────│
      │                              │
      │  POST /chat (with Bearer)    │
      │─────────────────────────────▶│
      │                              │ Route handler:
      │                              │  get_user_context() → UserContext
      │                              │  All DB queries scoped to user_id
```

**Single-user mode:** If `THOTH_MULTI_USER=false` (the default), the
middleware always sets `user_context = default_user` regardless of
whether a token is present. The `users` table is unused.

---

## Security Notes

- Tokens are long-lived (`thoth_` + 32 random bytes). Treat them like
  passwords — share via secure channel, not email/Slack.
- Tokens are stored **hashed** in the database (SHA-256). Even if the DB
  is compromised, raw tokens are not exposed.
- Deactivating a user immediately invalidates their token — no TTL to wait
  for.
- There is no token expiry by default. Use `make user-reset-token` to
  rotate tokens periodically.
- `THOTH_ALLOW_REGISTRATION=false` is the safe default. Only enable it
  during an onboarding window, then disable again.

---

## Vault Management

Each user's vault lives at `{THOTH_VAULTS_ROOT}/{username}/`. The
`VaultProvisioner` creates the directory structure automatically:

```
/vaults/alice/
  thoth/
    _thoth/
      settings.json        ← pre-filled with sensible defaults
      logs/
    papers/
      pdfs/
      markdown/
    notes/
    discovery/
    queries/
```

Users sync this directory to their local machine via **Obsidian Sync**,
**Syncthing**, or any other sync tool. The server is the source of truth
for all data; local copies are for reading/editing notes in Obsidian.

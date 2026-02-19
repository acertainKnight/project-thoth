# Multi-User Mode

Thoth can run as a shared server where multiple people each get their own
vault, agents, and data. A single API token per user handles authentication.
Single-user deployments are unaffected — this is opt-in.

---

## How it works

Every API request carries an `Authorization: Bearer <token>` header. The
middleware looks up the token, finds the user, and attaches their identity to
the request. From there, all database queries are scoped to that user's ID and
all agent calls are routed to that user's named Letta agents.

```
Request:  Authorization: Bearer thoth_abc123
                      │
            TokenAuthMiddleware
            token lookup → user: alice
            UserContext(username="alice", vault="/vaults/alice")
                      │
            Route handler
            DB queries filtered to user_id = alice
            Agent calls go to thoth_main_orchestrator_alice
```

When multi-user mode is off, the middleware stamps every request with
`default_user` and moves on. The `users` table exists but is never queried.

---

## Fresh server setup

Already running single-user? Skip to [Upgrading an existing server](#upgrading-an-existing-server).

### 1. Pick a vault root

Each user gets a subdirectory: `/vaults/alice`, `/vaults/bob`, etc.

```bash
mkdir -p /vaults
```

Put it wherever makes sense. It just needs to be writable by the containers.

### 2. Set environment variables

In your `.env`:

```bash
THOTH_MULTI_USER=true
THOTH_VAULTS_ROOT=/vaults
THOTH_ALLOW_REGISTRATION=false
```

Or: `make multi-user-enable`

### 3. Run migrations

```bash
make db-migrate
```

This creates the `users` table and adds `user_id` to all tenant tables.
Additive only — safe to run on a live database.

### 4. Create the admin account

```bash
make user-create USERNAME=admin ADMIN=true
```

The token prints once. Save it somewhere secure. Lost it? `make user-reset-token USERNAME=admin`.

### 5. Start the server

```bash
docker compose up -d
```

All endpoints now require a token except `/health` and `/auth/register`
(if self-registration is on).

---

## Adding users

```bash
make user-create USERNAME=alice
make user-create USERNAME=alice EMAIL=alice@example.com
```

Send the token to the user through a password manager share or Signal.
Not Slack, not plain email.

If `THOTH_ALLOW_REGISTRATION=true`, users can also register themselves:

```bash
curl -X POST https://your-server/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username": "alice", "email": "alice@example.com"}'
```

Consider turning registration off after onboarding.

---

## Obsidian plugin setup

Each user does this once:

1. **Settings → Thoth**
2. Set the **Thoth API URL** to the server address
3. Paste the token into **API Token**
4. Hit **Verify Token & Connection** — should show your username
5. Save

The plugin handles the rest: it sends the token on every request, resolves
your agent IDs from `/auth/me`, and passes the token on WebSocket connections.

---

## Managing users

These commands connect straight to the database. The server doesn't need to be
running.

```bash
make user-list                              # all users
make user-info USERNAME=alice               # details + agent IDs
make user-reset-token USERNAME=alice        # new token, old one dies immediately
make user-deactivate USERNAME=alice         # prompts before deactivating
```

Same thing via CLI:

```bash
uv run thoth users list
uv run thoth users info alice
uv run thoth users reset-token alice
uv run thoth users deactivate alice
```

---

## Upgrading an existing server

You can do this with zero downtime. The migration only adds columns and
tables — existing data is untouched, and all current rows are assigned to
`default_user` automatically.

### 1. Update code, rebuild images

```bash
git pull
docker compose build
```

### 2. Run the migration (containers can stay up)

```bash
docker compose run --rm thoth-api python -m thoth db migrate
```

To confirm it worked, check the migrations table in your database:

```sql
SELECT version, name FROM _migrations ORDER BY version;
-- version 7: add_multi_user_support should be there
```

### 3. Restart, still in single-user mode

```bash
docker compose up -d
```

Make sure nothing broke:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/auth/me
```

Both should work like before. No rush on the next steps.

### 4. Flip multi-user on

Add to `.env`:

```bash
THOTH_MULTI_USER=true
THOTH_VAULTS_ROOT=/vaults
```

```bash
mkdir -p /vaults
uv run thoth users create admin --admin   # save the token
docker compose up -d
```

### 5. Check it

```bash
# Should 401 now
curl http://localhost:8080/auth/me

# Should return your user info
curl http://localhost:8080/auth/me \
  -H "Authorization: Bearer <your-token>"
```

---

## Testing

### Unit tests

```bash
uv run pytest tests/unit/server/test_multi_user_auth.py -v
```

14 tests, no database needed. Covers token generation, user lookup, middleware
in both modes, 401 handling, and vault path resolution.

### Checking the migration

```sql
SELECT version, name FROM _migrations ORDER BY version;

SELECT column_name FROM information_schema.columns
WHERE table_name = 'research_questions' AND column_name = 'user_id';
```

### Endpoint smoke tests

```bash
curl http://localhost:8080/health                                      # always 200
curl http://localhost:8080/auth/me                                     # 200 single-user, 401 multi-user
curl http://localhost:8080/auth/me -H "Authorization: Bearer <token>"  # 200 with valid token
curl http://localhost:8080/auth/me -H "Authorization: Bearer bad"      # 401
```

---

## Auth flow

```
Plugin                        Server
  │  GET /auth/me               │
  │  Authorization: Bearer ...  │
  ├────────────────────────────▶│
  │                             │  Middleware: extract token, look up user,
  │                             │  build UserContext, attach to request
  │  200 OK                     │
  │  { username, vault_path,    │
  │    orchestrator_agent_id,   │
  │    analyst_agent_id }       │
  │◀────────────────────────────┤
  │                             │
  │  POST /chat                 │
  ├────────────────────────────▶│
  │                             │  All queries scoped to this user's ID
```

---

## Security

Tokens are long-lived. No expiry, no refresh. Treat them like passwords.

- Share via password manager or Signal, not Slack/email
- Stored hashed (SHA-256) in the database — a DB breach doesn't leak raw tokens
- Deactivation and token reset are instant, no waiting for expiry
- Rotate periodically: `make user-reset-token USERNAME=alice`
- Keep `THOTH_ALLOW_REGISTRATION=false` when you're not actively onboarding

---

## Vault structure

Created automatically when a user account is made:

```
/vaults/
  alice/
    thoth/
      _thoth/
        settings.json
        logs/
      papers/
        pdfs/
        markdown/
      notes/
      discovery/
      queries/
```

Users sync this to their local machine with Obsidian Sync, Syncthing, or
whatever they prefer. The server is the source of truth — local copies are
for working in Obsidian.

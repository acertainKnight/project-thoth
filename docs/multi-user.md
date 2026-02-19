# Multi-User Mode

By default Thoth runs in single-user mode — one vault, one set of agents, one
database. Multi-user mode lets you run a single shared server where each person
has fully isolated data: their own Obsidian vault, their own Letta agents, and
their own rows in every database table. Everything is controlled by a simple
API token that each user puts in their Obsidian plugin settings.

If you are a single-user deployment, nothing in this document applies to you
and you don't need to do anything. Multi-user mode is completely opt-in.

---

## How it works

When multi-user mode is enabled, every incoming API request must carry a
`Authorization: Bearer <token>` header. The server looks that token up in the
database, finds the matching user account, and builds a `UserContext` object
that flows through the entire request — middleware → routes → services →
database queries. Every database table that holds user data has a `user_id`
column, so Alice's papers and Bob's papers never mix.

Each user also gets their own pair of Letta agents named after them
(`thoth_main_orchestrator_alice`, `thoth_research_analyst_alice`, etc.), so
their conversation history and agent memory are completely separate.

```
Shared server

  Request comes in with:  Authorization: Bearer thoth_abc123
                                    │
                          TokenAuthMiddleware
                          looks up token → user: alice
                          builds UserContext(username="alice", vault="/vaults/alice")
                                    │
                          Route handler runs
                          all DB queries filtered by user_id = alice
                          agent calls go to alice's named agents
```

In single-user mode, the middleware just stamps every request with a
`default_user` identity and moves on. The `users` table is created but
never queried. Your existing setup stays exactly the same.

---

## Setting up a new multi-user server

This section is for someone starting fresh. If you have an existing server
you want to convert, skip ahead to [Upgrading an existing server](#upgrading-an-existing-server).

### 1. Decide where vaults will live

Each user gets a subdirectory under a shared root, for example `/vaults/alice`,
`/vaults/bob`. Pick a path on the host machine and create it:

```bash
mkdir -p /vaults
```

You can put this anywhere — it just needs to be writable by the Docker containers.

### 2. Configure environment variables

Add these to your `.env` file:

```bash
# Turn on multi-user mode
THOTH_MULTI_USER=true

# The directory that will hold all user vault subdirectories
THOTH_VAULTS_ROOT=/vaults

# Whether users can register themselves (false = admin creates all accounts)
THOTH_ALLOW_REGISTRATION=false
```

Or run `make multi-user-enable` which writes these for you.

### 3. Run database migrations

```bash
make db-migrate
# or directly: uv run thoth db migrate
```

This creates the `users` table and adds a `user_id` column to every
tenant-scoped table. The migration is safe to run on a running server — it
only adds things, never changes or removes existing data.

### 4. Create the first admin account

```bash
make user-create USERNAME=admin ADMIN=true
# or: uv run thoth users create admin --admin
```

The token is printed once and only once. Copy it somewhere safe — a password
manager is ideal. If you lose it, run `make user-reset-token USERNAME=admin`
to generate a new one.

### 5. Start (or restart) the server

```bash
docker compose up -d
```

At this point the server requires a valid token for all non-exempt endpoints.
The `/health` endpoint is always open, and `/auth/register` is open if you've
enabled self-registration.

---

## Adding users

### Admin creates the account (recommended)

```bash
make user-create USERNAME=alice
# With email:
make user-create USERNAME=alice EMAIL=alice@example.com
```

Copy the printed token and send it to the user through a secure channel — a
password manager share, Signal, or encrypted email. Do not send tokens over
plain email or Slack.

### Self-registration (if you've enabled it)

If `THOTH_ALLOW_REGISTRATION=true`, users can register themselves:

```bash
curl -X POST https://your-server.example.com/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username": "alice", "email": "alice@example.com"}'
```

The response includes the token. Consider only turning this on for a short
onboarding window and then setting it back to `false`.

---

## User setup (Obsidian plugin)

Once a user has their token, they configure the plugin once on their local
Obsidian:

1. Open **Settings → Thoth**
2. Set **Thoth API URL** to the server address, for example `https://thoth.yourlab.com`
3. Paste the token into the **API Token** field (starts with `thoth_`)
4. Click **Verify Token & Connection** — the plugin will show your username on success
5. Save

After that, everything is automatic. The plugin sends the token with every
request, resolves your personal Letta agent IDs from `/auth/me`, and attaches
the token to WebSocket connections. You don't need to know or configure any
agent IDs manually.

---

## Managing users

All of these commands talk directly to the database and don't require the
server to be running.

```bash
# See all users
make user-list

# Get full details for one user (including their agent IDs)
make user-info USERNAME=alice

# Generate a new token (the old one stops working immediately)
make user-reset-token USERNAME=alice

# Deactivate an account (prompts for confirmation)
make user-deactivate USERNAME=alice
```

The equivalent `thoth users` CLI commands work the same way:

```bash
uv run thoth users list
uv run thoth users info alice
uv run thoth users reset-token alice
uv run thoth users deactivate alice
```

---

## Upgrading an existing server

If you have Thoth already running in single-user mode and want to add
multi-user support, the good news is you can do it without any downtime and
without touching existing data. The database migration only adds new columns
and tables — nothing is modified or removed, and all existing rows are
automatically assigned to a `default_user` identity.

### Step 1: Update your code

Pull the latest code and rebuild your images:

```bash
git pull
docker compose build
```

### Step 2: Run the migration

You can run this while your existing containers are still up. It's safe:

```bash
docker compose run --rm thoth-api python -m thoth db migrate
```

You should see confirmation that migration 007 (`add_multi_user_support`)
applied successfully. If you want to double-check, connect to your database
and verify:

```bash
# Substitute your actual postgres container name and credentials
docker exec <your-postgres-container> psql -U <user> -d <database> \
  -c "SELECT version, name FROM _migrations ORDER BY version;"
```

Version 7 should appear in the list.

### Step 3: Restart with the new images (still single-user)

```bash
docker compose up -d
```

At this point your server is running the new code but still in single-user
mode. Verify everything works exactly as it did before:

```bash
curl http://localhost:8080/health       # should return 200
curl http://localhost:8080/auth/me      # should return a default_user context
```

Take your time here. There is no rush to enable multi-user mode and no risk
in waiting.

### Step 4: Enable multi-user mode

When you're ready, add these to your `.env`:

```bash
THOTH_MULTI_USER=true
THOTH_VAULTS_ROOT=/vaults      # or wherever you want user vaults to live
```

Create the vaults directory if it doesn't exist:

```bash
mkdir -p /vaults
```

Create your admin account before restarting — this command talks directly to
the database so the server doesn't need to be running yet:

```bash
uv run thoth users create admin --admin
```

Save the token it prints. Then restart:

```bash
docker compose up -d
```

### Step 5: Verify

```bash
# Without a token, you should now get a 401
curl http://localhost:8080/auth/me

# With your token, you should get your user info back
curl http://localhost:8080/auth/me \
  -H "Authorization: Bearer thoth_your_token_here"
```

---

## Testing

### Running the unit tests

The unit test suite covers auth token generation, user lookup, inactive user
rejection, the middleware in single-user mode, 401 responses on missing tokens,
and vault path resolution. No database required:

```bash
uv run pytest tests/unit/server/test_multi_user_auth.py -v
```

All 14 tests should pass.

### Checking the migration manually

If you want to verify the migration ran correctly without writing SQL yourself,
these two queries tell you everything:

```sql
-- Should show version 7
SELECT version, name FROM _migrations ORDER BY version;

-- Should show 'user_id' in the list
SELECT column_name FROM information_schema.columns
WHERE table_name = 'research_questions' AND column_name = 'user_id';
```

### Testing endpoints with curl

```bash
# Always works regardless of auth mode
curl http://localhost:8080/health

# Single-user mode: returns default_user with no token
curl http://localhost:8080/auth/me

# Multi-user mode: returns your user info with a valid token
curl http://localhost:8080/auth/me \
  -H "Authorization: Bearer thoth_your_token_here"

# Multi-user mode: returns 401 with no token or a bad token
curl http://localhost:8080/auth/me \
  -H "Authorization: Bearer thoth_invalid"
```

---

## Authentication flow

For reference, here's what actually happens when a request comes in:

```
Plugin                        Server
  │                             │
  │  GET /auth/me               │
  │  Authorization: Bearer ...  │
  ├────────────────────────────▶│
  │                             │  1. Middleware extracts the Bearer token
  │                             │  2. Looks it up in the users table
  │                             │  3. Builds a UserContext (user ID, username,
  │                             │     vault path, admin status)
  │                             │  4. Attaches context to the request
  │                             │  5. Route handler returns user info
  │◀────────────────────────────┤
  │  200 OK                     │
  │  { username, vault_path,    │
  │    orchestrator_agent_id,   │
  │    analyst_agent_id }       │
  │                             │
  │  POST /chat                 │
  ├────────────────────────────▶│
  │                             │  All DB queries automatically scoped
  │                             │  to this user's ID — other users'
  │                             │  data is never touched
```

---

## Security notes

Tokens are long-lived by design — there's no expiry and no refresh flow.
This keeps the setup simple, but it means you should treat tokens like
passwords:

- Share tokens through a secure channel (password manager, Signal), not plain email or Slack
- Tokens are stored hashed in the database (SHA-256), so a database breach does not expose raw tokens
- Revoking a token is instant — deactivating a user or resetting their token takes effect on the very next request
- Consider rotating tokens periodically with `make user-reset-token USERNAME=alice`
- Keep `THOTH_ALLOW_REGISTRATION=false` unless you're actively onboarding users

---

## Vault structure

When a user account is created, Thoth provisions their vault directory
automatically. Under your `THOTH_VAULTS_ROOT`, it looks like this:

```
/vaults/
  alice/
    thoth/
      _thoth/
        settings.json     ← sensible defaults pre-filled
        logs/
      papers/
        pdfs/
        markdown/
      notes/
      discovery/
      queries/
  bob/
    thoth/
      ...
```

Users keep a local copy of their vault using Obsidian Sync, Syncthing, or
any other file sync tool. The server is the authoritative source of truth —
local copies exist so people can read and edit their notes in Obsidian, but
all processing, discovery, and agent work happens server-side.

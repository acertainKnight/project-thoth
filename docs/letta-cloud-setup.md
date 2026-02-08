# Letta Cloud Setup Guide

## Overview

Thoth can connect to either:
1. **Letta Cloud** (hosted at app.letta.com) - Includes free tier
2. **Self-hosted Letta** (local Docker container) - Full control

## Quick Start: Setup Wizard (Recommended)

**New in 2026:** Thoth's main setup wizard now includes Letta mode selection!

```bash
thoth setup
```

The setup wizard will:
1. Detect your Obsidian vault
2. **Ask you to choose: Letta Cloud or Self-Hosted** ⭐ (NEW!)
3. For cloud: Validate your API key
4. Configure all dependencies
5. Save your settings automatically

**Get your Letta Cloud API key**: https://app.letta.com/api-keys

### Alternative: Letta-Specific Setup

If you just want to configure Letta (not full setup):

```bash
thoth letta setup
```

This standalone wizard handles only Letta configuration.

## Letta Cloud Setup (Manual)

### Option 1: OAuth (Recommended)

OAuth provides the best user experience with automatic credential management.

1. **Authenticate with Letta Cloud**:
   ```bash
   thoth letta auth login
   ```

   This opens your browser to log in at app.letta.com. Credentials are saved to `~/.letta/credentials`.

2. **Update settings.json**:
   ```json
   {
     "memory": {
       "letta": {
         "mode": "cloud",
         "oauthEnabled": true
       }
     }
   }
   ```

3. **Start Thoth services**:
   ```bash
   # Only need PostgreSQL for Thoth database
   docker compose -f docker-compose.letta.yml up letta-postgres -d

   # Start Thoth services
   make dev
   ```

4. **Sync vault files**:
   ```bash
   thoth letta sync
   ```

### Option 2: API Key

If you prefer manual API key management:

1. **Create API key**:
   - Go to https://app.letta.com/api-keys
   - Create new API key
   - Copy the key (starts with `letta_sk_...`)

2. **Set environment variable**:
   ```bash
   export LETTA_CLOUD_API_KEY=letta_sk_...
   ```

   Or add to `.env`:
   ```bash
   LETTA_CLOUD_API_KEY=letta_sk_...
   ```

3. **Update settings.json**:
   ```json
   {
     "memory": {
       "letta": {
         "mode": "cloud",
         "oauthEnabled": false
       }
     }
   }
   ```

4. **Start services** (same as Option 1, steps 3-4)

## Self-Hosted Setup

For self-hosted Letta (current default):

```bash
# 1. Start full Letta stack (including Letta server)
docker compose -f docker-compose.letta.yml up -d

# 2. Start Thoth services
make dev

# 3. Sync vault files
thoth letta sync
```

## Switching Modes

### Interactive Mode Switcher

```bash
thoth letta switch-mode
```

### Command Line Mode Switch (NEW)

**Switch to Letta Cloud:**
```bash
thoth letta configure cloud --api-key=letta_sk_your_key_here
```

**Switch to Self-Hosted:**
```bash
thoth letta configure self-hosted
```

### Check Current Status

```bash
thoth letta status
```

This shows:
- Current mode (cloud or self-hosted)
- Server URL
- API key status (if cloud)
- Connection test results

This will:
- Guide you through authentication (if switching to cloud)
- Start/stop containers as needed
- Update your configuration
- Provide restart instructions

### Manual Mode Switching

**Self-Hosted → Cloud**:

1. Stop Letta server:
   ```bash
   docker compose -f docker-compose.letta.yml stop letta
   ```

2. Authenticate:
   ```bash
   thoth letta auth login
   ```

3. Update settings.json:
   ```json
   {
     "memory": {
       "letta": {
         "mode": "cloud"
       }
     }
   }
   ```

4. Restart Thoth:
   ```bash
   make dev-stop && make dev
   ```

**Cloud → Self-Hosted**:

1. Update settings.json:
   ```json
   {
     "memory": {
       "letta": {
         "mode": "self-hosted"
       }
     }
   }
   ```

2. Start Letta server:
   ```bash
   docker compose -f docker-compose.letta.yml up letta -d
   ```

3. Restart Thoth:
   ```bash
   make dev-stop && make dev
   ```

## Database Considerations

- **Thoth database**: Always uses local PostgreSQL (`thoth` database)
- **Letta database**:
  - Self-hosted: Uses local PostgreSQL (`letta` database)
  - Cloud: Uses Letta Cloud's database (nothing local needed)

## Authentication Commands

Check authentication status:

```bash
thoth letta auth status
```

Login to Letta Cloud:

```bash
thoth letta auth login
```

Logout from Letta Cloud:

```bash
thoth letta auth logout
```

## Configuration Reference

### Environment Variables

```bash
# Mode selection
LETTA_MODE=cloud  # or 'self-hosted' (default)

# Self-hosted mode
LETTA_SERVER_URL=http://localhost:8283  # Letta server URL
LETTA_API_KEY=letta_dev_password        # Optional password

# Cloud mode
LETTA_CLOUD_API_KEY=letta_sk_...        # Optional (if not using OAuth)
LETTA_CREDENTIALS_PATH=~/.letta/credentials  # Optional (custom path)
```

### Settings.json

```json
{
  "memory": {
    "letta": {
      "mode": "cloud",              // "cloud" or "self-hosted"
      "oauthEnabled": true,         // Use OAuth for cloud mode
      "cloudApiKey": "",            // Optional API key (overrides OAuth)
      "oauthCredentialsPath": "~/.letta/credentials",  // OAuth credentials
      "serverUrl": "http://localhost:8283"  // Self-hosted URL
    }
  }
}
```

## Troubleshooting

See [LETTA_CLOUD_TROUBLESHOOTING.md](./LETTA_CLOUD_TROUBLESHOOTING.md) for common issues and solutions.

## Quick Reference

```bash
# Setup wizard (first-time users)
thoth letta setup

# Authentication (cloud mode)
thoth letta auth login   # OAuth flow
thoth letta auth logout  # Clear credentials
thoth letta auth status  # Check current auth

# Mode switching (existing users)
thoth letta switch-mode  # Interactive mode switcher

# Existing commands (unchanged)
thoth letta sync         # Sync vault files to Letta
thoth letta folders      # List Letta folders
```

## Next Steps

After setup:

1. **Sync your vault**: `thoth letta sync`
2. **Start using agents**: Agents can now access your vault files
3. **Monitor sync status**: Check logs for any errors

For more information:
- [Letta Documentation](https://docs.letta.com)
- [Thoth Documentation](../README.md)

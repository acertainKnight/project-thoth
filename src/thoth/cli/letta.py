"""
CLI commands for Letta filesystem operations.

This module provides commands for syncing Obsidian vault files to Letta
filesystem, enabling agents to access vault content via Letta's file tools.
"""

import asyncio
import json
import os
import subprocess
import time
import webbrowser
from pathlib import Path

from loguru import logger

from thoth.config import config
from thoth.pipeline import ThothPipeline
from thoth.utilities.interactive import prompt_choice, prompt_text, confirm

# Check if Letta filesystem service is available
try:
    from thoth.services.letta_filesystem_service import LettaFilesystemService
    LETTA_AVAILABLE = True
except ImportError:
    LETTA_AVAILABLE = False
    LettaFilesystemService = None  # type: ignore


def handle_sync_filesystem(args, pipeline: ThothPipeline) -> int:
    """
    Sync vault files to Letta filesystem.

    Args:
        args: Command line arguments
        pipeline: ThothPipeline instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if not LETTA_AVAILABLE:
        logger.error('Letta filesystem service not available')
        logger.error('Please install letta extras: uv sync --extra memory')
        return 1
    
    try:
        # Initialize service
        letta_service = LettaFilesystemService(config)
        letta_service.initialize()

        logger.info('Starting Letta filesystem sync...')

        # Get or create folder
        folder_name = args.folder_name or 'thoth_processed_articles'
        embedding_model = args.embedding or config.rag_config.embedding_model

        logger.info(f'Using folder: {folder_name}')
        logger.info(f'Using embedding model: {embedding_model}')

        # Run sync
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Get or create folder
            folder_id = loop.run_until_complete(
                letta_service.get_or_create_folder(
                    name=folder_name,
                    embedding_model=embedding_model
                )
            )

            logger.info(f'Folder ID: {folder_id}')

            # Sync vault files
            stats = loop.run_until_complete(
                letta_service.sync_vault_to_folder(
                    folder_id=folder_id,
                    notes_dir=config.notes_dir if not args.notes_dir else Path(args.notes_dir)
                )
            )

            # Print results
            logger.info('=== Sync Complete ===')
            logger.info(f'Total files: {stats["total_files"]}')
            logger.info(f'Uploaded: {stats["uploaded"]}')
            logger.info(f'Skipped (unchanged): {stats["skipped"]}')

            if stats['errors']:
                logger.warning(f'Errors: {len(stats["errors"])}')
                for error in stats['errors']:
                    logger.error(f'  - {error}')

            # Attach to agent if requested
            if args.agent_id:
                logger.info(f'Attaching folder to agent: {args.agent_id}')
                loop.run_until_complete(
                    letta_service.attach_folder_to_agent(
                        agent_id=args.agent_id,
                        folder_id=folder_id
                    )
                )
                logger.info('Folder attached to agent successfully')

            return 0

        finally:
            loop.close()

    except Exception as e:
        logger.error(f'Sync failed: {e}')
        import traceback
        traceback.print_exc()
        return 1


def handle_folder_info(args, pipeline: ThothPipeline) -> int:
    """
    Show information about Letta folders.

    Args:
        args: Command line arguments
        pipeline: ThothPipeline instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if not LETTA_AVAILABLE:
        logger.error('Letta filesystem service not available')
        logger.error('Please install letta extras: uv sync --extra memory')
        return 1
    
    try:
        letta_service = LettaFilesystemService(config)
        letta_service.initialize()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # List folders
            folders = loop.run_until_complete(
                asyncio.to_thread(letta_service.client.folders.list)
            )

            if not folders:
                logger.info('No Letta folders found')
                return 0

            logger.info(f'Found {len(folders)} Letta folder(s):')
            logger.info('')

            for folder in folders:
                logger.info(f'Folder: {folder.name}')
                logger.info(f'  ID: {folder.id}')
                if hasattr(folder, 'embedding'):
                    logger.info(f'  Embedding: {folder.embedding}')
                if hasattr(folder, 'created_at'):
                    logger.info(f'  Created: {folder.created_at}')
                logger.info('')

            return 0

        finally:
            loop.close()

    except Exception as e:
        logger.error(f'Failed to list folders: {e}')
        import traceback
        traceback.print_exc()
        return 1


def handle_auth_login(args, pipeline: ThothPipeline) -> int:
    """
    Handle OAuth login to Letta Cloud.

    Args:
        args: Command line arguments
        pipeline: ThothPipeline instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.info('Opening browser for Letta Cloud authentication...')
        logger.info('Please log in at: https://app.letta.com/auth/cli')
        logger.info('')

        # Try to auto-open browser
        try:
            webbrowser.open('https://app.letta.com/auth/cli')
            logger.info('✓ Browser opened automatically')
        except Exception:
            logger.warning('⚠️  Could not open browser automatically')
            logger.info('Please manually visit: https://app.letta.com/auth/cli')

        logger.info('')
        logger.info('After logging in, credentials will be saved to: ~/.letta/credentials')

        # Try to use Letta SDK to complete OAuth flow
        try:
            from letta_client import Letta
            client = Letta()  # Triggers OAuth flow if not authenticated
            user_info = client.user.get()
            logger.info('')
            logger.success(f'✓ Successfully authenticated as: {user_info.email}')
            logger.success(f'✓ Credentials saved to: ~/.letta/credentials')
            return 0
        except Exception as e:
            logger.error('')
            logger.error(f'✗ Authentication failed: {e}')
            logger.info('Please try again or use API key authentication instead')
            logger.info('Get your API key from: https://app.letta.com/api-keys')
            logger.info('Then set: export LETTA_CLOUD_API_KEY=letta_sk_...')
            return 1

    except Exception as e:
        logger.error(f'Login failed: {e}')
        import traceback
        traceback.print_exc()
        return 1


def handle_auth_logout(args, pipeline: ThothPipeline) -> int:
    """
    Handle logout from Letta Cloud.

    Args:
        args: Command line arguments
        pipeline: ThothPipeline instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        creds_path = Path.home() / '.letta' / 'credentials'

        if creds_path.exists():
            os.remove(creds_path)
            logger.success('✓ Logged out successfully')
            logger.info(f'✓ Removed credentials from: {creds_path}')
        else:
            logger.info('No active session found')

        return 0

    except Exception as e:
        logger.error(f'Logout failed: {e}')
        return 1


def handle_auth_status(args, pipeline: ThothPipeline) -> int:
    """
    Check authentication status.

    Args:
        args: Command line arguments
        pipeline: ThothPipeline instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        creds_path = Path.home() / '.letta' / 'credentials'

        if creds_path.exists():
            logger.info('✓ Authenticated with Letta Cloud')
            logger.info(f'  Credentials: {creds_path}')

            # Try to get user info
            try:
                from letta_client import Letta
                client = Letta()
                user_info = client.user.get()
                logger.info(f'  User: {user_info.email}')
                if hasattr(user_info, 'org_name'):
                    logger.info(f'  Organization: {user_info.org_name}')
            except Exception as e:
                logger.warning(f'  Warning: Could not fetch user info: {e}')
        else:
            logger.info('✗ Not authenticated')
            logger.info('  Run "thoth letta auth login" to authenticate with Letta Cloud')
            logger.info('  Or set LETTA_CLOUD_API_KEY for API key authentication')

        # Check environment variables
        logger.info('')
        logger.info('Environment configuration:')
        mode = os.getenv('LETTA_MODE', 'self-hosted')
        logger.info(f'  Mode: {mode}')

        if mode == 'cloud':
            cloud_key = os.getenv('LETTA_CLOUD_API_KEY')
            if cloud_key:
                logger.info(f'  API Key: {cloud_key[:20]}...')
            else:
                logger.info('  API Key: Not set')
        else:
            server_url = os.getenv('LETTA_SERVER_URL', 'http://localhost:8283')
            logger.info(f'  Server URL: {server_url}')

        return 0

    except Exception as e:
        logger.error(f'Status check failed: {e}')
        return 1


def handle_setup(args, pipeline: ThothPipeline) -> int:
    """
    Interactive setup wizard for Letta configuration.

    Args:
        args: Command line arguments
        pipeline: ThothPipeline instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        print("=" * 70)
        print("Letta Setup Wizard")
        print("=" * 70)
        print()

        # Step 1: Choose mode
        mode = prompt_choice(
            "How do you want to use Letta?",
            [
                ("cloud", "Letta Cloud (hosted, includes free tier)"),
                ("self-hosted", "Self-hosted (local Docker container)")
            ]
        )

        config_updates = {}

        if mode == "cloud":
            print("📡 Setting up Letta Cloud...")
            print()

            # Step 2: Choose auth method
            auth_method = prompt_choice(
                "How do you want to authenticate?",
                [
                    ("oauth", "OAuth (recommended - opens browser)"),
                    ("apikey", "API Key (manual)")
                ]
            )

            if auth_method == "oauth":
                # OAuth flow
                print()
                print("🔐 Opening browser for authentication...")
                print("Please log in at: https://app.letta.com/auth/cli")
                print()

                # Try auto-open browser
                try:
                    webbrowser.open("https://app.letta.com/auth/cli")
                    print("✓ Browser opened automatically")
                except Exception:
                    print("⚠️  Could not open browser automatically")
                    print("Please manually visit: https://app.letta.com/auth/cli")

                print()
                print("Waiting for authentication...")

                # Wait for OAuth completion
                try:
                    from letta_client import Letta
                    client = Letta()  # Triggers OAuth flow
                    user_info = client.user.get()
                    print(f"✓ Authenticated as: {user_info.email}")
                    print()

                    config_updates = {
                        "mode": "cloud",
                        "oauthEnabled": True
                    }
                except Exception as e:
                    print(f"✗ Authentication failed: {e}")
                    return 1

            else:  # API key
                print()
                print("📋 To get your API key:")
                print("1. Go to: https://app.letta.com/api-keys")
                print("2. Create a new API key")
                print("3. Copy the key (starts with letta_sk_...)")
                print()

                api_key = prompt_text("Enter your Letta Cloud API key")

                if not api_key:
                    print("✗ API key is required")
                    return 1

                if not api_key.startswith("letta_sk_"):
                    print("⚠️  Warning: API key should start with 'letta_sk_'")

                # Test API key
                try:
                    from letta_client import Letta
                    client = Letta(token=api_key)
                    user_info = client.user.get()
                    print(f"✓ API key valid for: {user_info.email}")
                    print()

                    # Save to .env
                    env_path = Path.cwd() / ".env"
                    with open(env_path, "a") as f:
                        f.write(f"\nLETTA_CLOUD_API_KEY={api_key}\n")
                    print(f"✓ Saved API key to: {env_path}")

                    config_updates = {
                        "mode": "cloud",
                        "oauthEnabled": False,
                        "cloudApiKey": api_key
                    }
                except Exception as e:
                    print(f"✗ Invalid API key: {e}")
                    return 1

            # Optional: Custom credentials path
            use_custom = prompt_choice(
                "Use custom credentials path? (advanced)",
                [
                    ("no", "No, use default (~/.letta/credentials)"),
                    ("yes", "Yes, specify custom path")
                ]
            )

            if use_custom == "yes":
                creds_path = prompt_text("Enter credentials path")
                config_updates["oauthCredentialsPath"] = creds_path

                # Save to .env
                env_path = Path.cwd() / ".env"
                with open(env_path, "a") as f:
                    f.write(f"\nLETTA_CREDENTIALS_PATH={creds_path}\n")

        else:  # self-hosted
            print("🏠 Setting up self-hosted Letta...")
            print()
            print("Using default configuration:")
            print("  - Server URL: http://localhost:8283")
            print("  - Password: letta_dev_password")
            print()
            print("Start Letta with: docker compose -f docker-compose.letta.yml up -d")

            config_updates = {
                "mode": "self-hosted",
                "serverUrl": "http://localhost:8283"
            }

        # Step 3: Update settings.json
        settings_path = config.vault_root / "_thoth" / "settings.json"

        with open(settings_path) as f:
            settings = json.load(f)

        # Update memory.letta section
        if "memory" not in settings:
            settings["memory"] = {}
        if "letta" not in settings["memory"]:
            settings["memory"]["letta"] = {}

        settings["memory"]["letta"].update(config_updates)

        # Save settings
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)

        print()
        print(f"✓ Settings updated: {settings_path}")
        print()
        print("=" * 70)
        print("🎉 Letta setup complete!")
        print("=" * 70)

        if mode == "cloud":
            print()
            print("Next steps:")
            print("  1. Start Thoth: make dev")
            print("  2. Sync vault files: thoth letta sync")
        else:
            print()
            print("Next steps:")
            print("  1. Start Letta: docker compose -f docker-compose.letta.yml up -d")
            print("  2. Start Thoth: make dev")
            print("  3. Sync vault files: thoth letta sync")

        return 0

    except Exception as e:
        logger.error(f'Setup failed: {e}')
        import traceback
        traceback.print_exc()
        return 1


def handle_switch_mode(args, pipeline: ThothPipeline) -> int:
    """
    Interactive mode switcher for existing installations.

    Args:
        args: Command line arguments
        pipeline: ThothPipeline instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Get current mode
        current_mode = config.memory_config.letta.mode

        print("=" * 70)
        print("Letta Mode Switcher")
        print("=" * 70)
        print()
        print(f"Current mode: {current_mode}")
        print()

        new_mode = prompt_choice(
            "Switch to which mode?",
            [
                ("cloud", "Letta Cloud (hosted)"),
                ("self-hosted", "Self-hosted (local)")
            ]
        )

        if new_mode == current_mode:
            print(f"Already in {current_mode} mode. No changes needed.")
            return 0

        # Confirm switch
        if not confirm(f"Switch from {current_mode} to {new_mode}?"):
            print("Cancelled.")
            return 0

        print()
        print(f"🔄 Switching to {new_mode} mode...")
        print()

        config_updates = {"mode": new_mode}

        if new_mode == "cloud":
            # Cloud mode setup
            print("Choose authentication method:")
            auth_method = prompt_choice(
                "",
                [
                    ("oauth", "OAuth (opens browser)"),
                    ("apikey", "API Key")
                ]
            )

            if auth_method == "oauth":
                # Run OAuth login
                print()
                logger.info('Opening browser for Letta Cloud authentication...')
                try:
                    webbrowser.open('https://app.letta.com/auth/cli')
                except Exception:
                    pass

                from letta_client import Letta
                client = Letta()
                user_info = client.user.get()
                print(f"✓ Authenticated as: {user_info.email}")

                config_updates["oauthEnabled"] = True

            else:
                # Prompt for API key
                print()
                print("Get your API key from: https://app.letta.com/api-keys")
                api_key = prompt_text("Enter API key")

                # Save to .env
                env_path = Path.cwd() / ".env"
                with open(env_path, "a") as f:
                    f.write(f"\nLETTA_CLOUD_API_KEY={api_key}\n")

                config_updates["cloudApiKey"] = api_key
                config_updates["oauthEnabled"] = False

            # Stop self-hosted Letta
            print()
            print("📦 Stopping self-hosted Letta container...")
            subprocess.run(
                ["docker", "compose", "-f", "docker-compose.letta.yml", "stop", "letta"],
                capture_output=True
            )
            print("✓ Letta container stopped")

        else:  # self-hosted
            # Start self-hosted Letta
            print("📦 Starting self-hosted Letta container...")
            subprocess.run(
                ["docker", "compose", "-f", "docker-compose.letta.yml", "up", "-d", "letta"],
                capture_output=True
            )

            # Wait for health check
            print("Waiting for Letta to start...")
            for _ in range(30):
                try:
                    import requests
                    response = requests.get("http://localhost:8283/v1/health", timeout=1)
                    if response.status_code == 200:
                        print("✓ Letta started successfully")
                        break
                except:
                    pass
                time.sleep(1)

        # Update settings.json
        settings_path = config.vault_root / "_thoth" / "settings.json"
        with open(settings_path) as f:
            settings = json.load(f)

        settings["memory"]["letta"].update(config_updates)

        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)

        print()
        print(f"✓ Switched to {new_mode} mode")
        print("✓ Settings updated")
        print()
        print("=" * 70)
        print("🎉 Mode switch complete!")
        print("=" * 70)
        print()
        print("Restart Thoth services to apply changes:")
        print("  make dev-stop && make dev")

        return 0

    except Exception as e:
        logger.error(f'Mode switch failed: {e}')
        import traceback
        traceback.print_exc()
        return 1


def configure_subparser(subparsers) -> None:
    """
    Configure the letta subcommand parser.

    Args:
        subparsers: ArgumentParser subparsers object
    """
    parser = subparsers.add_parser(
        'letta',
        help='Letta filesystem operations'
    )
    letta_subparsers = parser.add_subparsers(
        dest='letta_command',
        help='Letta filesystem command',
        required=True
    )

    # Sync command
    sync_parser = letta_subparsers.add_parser(
        'sync',
        help='Sync vault files to Letta filesystem'
    )
    sync_parser.add_argument(
        '--folder-name',
        type=str,
        help='Letta folder name (default: thoth_processed_articles)'
    )
    sync_parser.add_argument(
        '--embedding',
        type=str,
        help='Embedding model to use (default: from config)'
    )
    sync_parser.add_argument(
        '--notes-dir',
        type=str,
        help='Notes directory to sync (default: from config)'
    )
    sync_parser.add_argument(
        '--agent-id',
        type=str,
        help='Attach folder to this agent ID after sync'
    )
    sync_parser.set_defaults(func=handle_sync_filesystem)

    # Folder info command
    info_parser = letta_subparsers.add_parser(
        'folders',
        help='List Letta folders'
    )
    info_parser.set_defaults(func=handle_folder_info)

    # Auth subcommand
    auth_parser = letta_subparsers.add_parser(
        'auth',
        help='Manage Letta Cloud authentication'
    )
    auth_subparsers = auth_parser.add_subparsers(
        dest='auth_command',
        help='Authentication command',
        required=True
    )

    # auth login
    login_parser = auth_subparsers.add_parser(
        'login',
        help='Login to Letta Cloud via OAuth'
    )
    login_parser.set_defaults(func=handle_auth_login)

    # auth logout
    logout_parser = auth_subparsers.add_parser(
        'logout',
        help='Logout from Letta Cloud'
    )
    logout_parser.set_defaults(func=handle_auth_logout)

    # auth status
    status_parser = auth_subparsers.add_parser(
        'status',
        help='Check authentication status'
    )
    status_parser.set_defaults(func=handle_auth_status)

    # Setup wizard
    setup_parser = letta_subparsers.add_parser(
        'setup',
        help='Interactive setup wizard for Letta configuration'
    )
    setup_parser.set_defaults(func=handle_setup)

    # Mode switcher
    switch_parser = letta_subparsers.add_parser(
        'switch-mode',
        help='Interactive mode switcher (cloud <-> self-hosted)'
    )
    switch_parser.set_defaults(func=handle_switch_mode)

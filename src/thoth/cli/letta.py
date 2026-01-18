"""
CLI commands for Letta filesystem operations.

This module provides commands for syncing Obsidian vault files to Letta
filesystem, enabling agents to access vault content via Letta's file tools.
"""

import asyncio
import os
import webbrowser
from pathlib import Path

from loguru import logger

from thoth.config import config
from thoth.pipeline import ThothPipeline

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

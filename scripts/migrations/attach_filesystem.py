#!/usr/bin/env python3
"""
Script to attach Obsidian vault filesystem to all Letta agents.

This script:
1. Syncs vault files to a Letta folder
2. Attaches the folder to all existing agents

Usage:
    python -m thoth.migration.attach_filesystem
"""

import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import track

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from thoth.config import Config
from thoth.services.letta_filesystem_service import LettaFilesystemService

console = Console()


async def attach_filesystem_to_agents():
    """Attach Obsidian vault filesystem to all Letta agents."""

    console.print('\n[bold cyan]Attaching Letta Filesystem to Agents[/bold cyan]\n')

    # Load config
    config = Config()
    console.print(f'✓ Loaded config from {config.vault_root}')

    # Initialize Letta filesystem service
    try:
        letta_service = LettaFilesystemService(config)
        letta_service.initialize()
        console.print('✓ Initialized Letta filesystem service')
    except Exception as e:
        console.print(f'[red]✗ Failed to initialize Letta service: {e}[/red]')
        return

    try:
        # Get folder name from config or use default
        folder_name = 'thoth_processed_articles'
        if hasattr(config, 'memory_config') and hasattr(config.memory_config, 'letta'):
            if hasattr(config.memory_config.letta, 'filesystem'):
                folder_name = config.memory_config.letta.filesystem.folder_name or folder_name

        console.print(f'Using folder name: {folder_name}')

        # Get embedding model from config
        embedding_model = 'text-embedding-3-small'
        if hasattr(config, 'rag_config'):
            # Extract model name from openai/text-embedding-3-small format
            full_model = config.rag_config.embedding_model
            if '/' in full_model:
                embedding_model = full_model.split('/')[-1]
            else:
                embedding_model = full_model

        console.print(f'Using embedding model: {embedding_model}')

        # Step 1: Get or create folder
        console.print('\n[bold]Step 1: Setting up Letta folder[/bold]')
        folder_id = await letta_service.get_or_create_folder(
            name=folder_name,
            embedding_model=embedding_model
        )
        console.print(f'✓ Folder ID: {folder_id}')

        # Step 2: Sync vault files to folder (including papers directory with PDFs)
        console.print('\n[bold]Step 2: Syncing vault files[/bold]')
        console.print('  Syncing both notes (markdown) and papers (PDFs)...')
        stats = await letta_service.sync_vault_to_folder(
            folder_id=folder_id,
            notes_dir=config.notes_dir,
            include_papers=True  # Critical: Include PDFs from papers directory
        )

        console.print(f'✓ Total files: {stats["total_files"]}')
        console.print(f'  - PDFs: {stats["pdfs"]}')
        console.print(f'  - Markdown: {stats["markdown"]}')
        console.print(f'✓ Uploaded: {stats["uploaded"]}')
        console.print(f'✓ Skipped (unchanged): {stats["skipped"]}')

        if stats['errors']:
            console.print(f'[yellow]⚠ Errors: {len(stats["errors"])}[/yellow]')
            for error in stats['errors'][:5]:  # Show first 5 errors
                console.print(f'  [yellow]{error}[/yellow]')

        # Step 3: Get all agents
        console.print('\n[bold]Step 3: Getting all agents[/bold]')
        agents = await asyncio.to_thread(
            letta_service._letta_client.agents.list
        )

        if not agents:
            console.print('[yellow]⚠ No agents found[/yellow]')
            console.print('Filesystem sync completed but no agents to attach to.')
            return

        console.print(f'✓ Found {len(agents)} agent(s)')

        # Step 4: Attach folder to each agent
        console.print('\n[bold]Step 4: Attaching folder to agents[/bold]')
        attached_count = 0
        error_count = 0

        for agent in track(agents, description='Attaching to agents...'):
            try:
                # Check if folder is already attached
                agent_folders = await asyncio.to_thread(
                    letta_service._letta_client.agents.folders.list,
                    agent.id
                )

                already_attached = any(f.id == folder_id for f in agent_folders)

                if already_attached:
                    console.print(f'  ⏭ Already attached: {agent.name} ({agent.id})')
                    attached_count += 1
                    continue

                # Attach folder to agent
                await letta_service.attach_folder_to_agent(
                    agent_id=agent.id,
                    folder_id=folder_id
                )
                console.print(f'  ✓ Attached: {agent.name} ({agent.id})')
                attached_count += 1

            except Exception as e:
                console.print(f'  [red]✗ Failed to attach to {agent.name}: {e}[/red]')
                error_count += 1

        # Summary
        console.print('\n[bold green]✓ Filesystem attachment completed![/bold green]\n')
        console.print(f'  Agents processed: {len(agents)}')
        console.print(f'  Successfully attached: {attached_count}')
        if error_count > 0:
            console.print(f'  [yellow]Errors: {error_count}[/yellow]')

    except Exception as e:
        console.print(f'\n[red]✗ Error during filesystem attachment: {e}[/red]')
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(attach_filesystem_to_agents())

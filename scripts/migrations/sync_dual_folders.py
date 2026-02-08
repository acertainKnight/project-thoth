#!/usr/bin/env python3
"""
Properly sync Obsidian vault to TWO separate Letta folders:
1. thoth_papers - for PDFs only
2. thoth_notes - for markdown only

This prevents duplicates and maintains proper organization.

Usage:
    python -m scripts.migrations.sync_dual_folders
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


async def sync_dual_folders():
    """Sync vault to two separate Letta folders (papers + notes)."""

    console.print('\n[bold cyan]Syncing Vault to Dual Letta Folders[/bold cyan]\n')

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
        # Get embedding model from config
        embedding_model = 'text-embedding-3-small'
        if hasattr(config, 'rag_config'):
            full_model = config.rag_config.embedding_model
            if '/' in full_model:
                embedding_model = full_model.split('/')[-1]
            else:
                embedding_model = full_model

        console.print(f'Using embedding model: {embedding_model}')

        # ============================================================
        # FOLDER 1: Papers (PDFs only)
        # ============================================================
        console.print('\n[bold]Step 1: Creating Papers Folder[/bold]')
        papers_folder_id = await letta_service.get_or_create_folder(
            name='thoth_papers', embedding_model=embedding_model
        )
        console.print(f'✓ Papers folder ID: {papers_folder_id}')

        # Sync PDFs from papers directory
        papers_dir = config.vault_root / 'thoth' / 'papers'
        if papers_dir.exists():
            console.print(f'\n[bold]Step 2: Syncing PDFs from {papers_dir}[/bold]')
            papers_stats = await letta_service.sync_directory_to_folder(
                folder_id=papers_folder_id,
                source_dir=papers_dir,
                file_extensions=['.pdf'],
            )

            console.print(f'✓ Total PDFs: {papers_stats["total_files"]}')
            console.print(f'✓ Uploaded: {papers_stats["uploaded"]}')
            console.print(f'✓ Skipped (unchanged): {papers_stats["skipped"]}')

            if papers_stats['errors']:
                console.print(
                    f'[yellow]⚠ Errors: {len(papers_stats["errors"])}[/yellow]'
                )
        else:
            console.print(
                f'[yellow]⚠ Papers directory not found: {papers_dir}[/yellow]'
            )
            papers_stats = {'total_files': 0, 'uploaded': 0, 'skipped': 0, 'errors': []}

        # ============================================================
        # FOLDER 2: Notes (Markdown only)
        # ============================================================
        console.print('\n[bold]Step 3: Creating Notes Folder[/bold]')
        notes_folder_id = await letta_service.get_or_create_folder(
            name='thoth_notes', embedding_model=embedding_model
        )
        console.print(f'✓ Notes folder ID: {notes_folder_id}')

        # Sync markdown from notes directory
        notes_dir = config.notes_dir
        if notes_dir.exists():
            console.print(f'\n[bold]Step 4: Syncing Markdown from {notes_dir}[/bold]')
            notes_stats = await letta_service.sync_directory_to_folder(
                folder_id=notes_folder_id, source_dir=notes_dir, file_extensions=['.md']
            )

            console.print(f'✓ Total markdown: {notes_stats["total_files"]}')
            console.print(f'✓ Uploaded: {notes_stats["uploaded"]}')
            console.print(f'✓ Skipped (unchanged): {notes_stats["skipped"]}')

            if notes_stats['errors']:
                console.print(
                    f'[yellow]⚠ Errors: {len(notes_stats["errors"])}[/yellow]'
                )
        else:
            console.print(f'[yellow]⚠ Notes directory not found: {notes_dir}[/yellow]')
            notes_stats = {'total_files': 0, 'uploaded': 0, 'skipped': 0, 'errors': []}

        # ============================================================
        # ATTACH BOTH FOLDERS TO ALL AGENTS
        # ============================================================
        console.print('\n[bold]Step 5: Attaching folders to agents[/bold]')
        agents = await asyncio.to_thread(letta_service._letta_client.agents.list)

        if not agents:
            console.print('[yellow]⚠ No agents found[/yellow]')
        else:
            console.print(f'✓ Found {len(agents)} agent(s)')

            attached_papers = 0
            attached_notes = 0

            for agent in track(agents, description='Attaching folders...'):
                try:
                    # Get current folders
                    agent_folders = await asyncio.to_thread(
                        letta_service._letta_client.agents.folders.list, agent.id
                    )
                    current_folder_ids = {f.id for f in agent_folders}

                    # Attach papers folder if not already attached
                    if papers_folder_id not in current_folder_ids:
                        await letta_service.attach_folder_to_agent(
                            agent_id=agent.id, folder_id=papers_folder_id
                        )
                        attached_papers += 1
                        console.print(f'  ✓ Attached papers to: {agent.name}')

                    # Attach notes folder if not already attached
                    if notes_folder_id not in current_folder_ids:
                        await letta_service.attach_folder_to_agent(
                            agent_id=agent.id, folder_id=notes_folder_id
                        )
                        attached_notes += 1
                        console.print(f'  ✓ Attached notes to: {agent.name}')

                except Exception as e:
                    console.print(
                        f'  [red]✗ Failed to attach to {agent.name}: {e}[/red]'
                    )

            console.print(f'\n✓ Papers folder attached to {attached_papers} agent(s)')
            console.print(f'✓ Notes folder attached to {attached_notes} agent(s)')

        # Summary
        console.print('\n[bold green]✓ Dual-folder sync completed![/bold green]\n')
        console.print('[bold]Summary:[/bold]')
        console.print(f'  Papers Folder ({papers_folder_id}):')
        console.print(f'    - PDFs synced: {papers_stats["total_files"]}')
        console.print(f'    - Uploaded: {papers_stats["uploaded"]}')
        console.print(f'  Notes Folder ({notes_folder_id}):')
        console.print(f'    - Markdown synced: {notes_stats["total_files"]}')
        console.print(f'    - Uploaded: {notes_stats["uploaded"]}')

    except Exception as e:
        console.print(f'\n[red]✗ Error during sync: {e}[/red]')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(sync_dual_folders())

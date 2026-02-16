"""
CLI commands for project management in Thoth.
"""

import asyncio

import click
from loguru import logger

from thoth.config import config
from thoth.repositories.knowledge_collection_repository import (
    KnowledgeCollectionRepository,
)
from thoth.services.llm_service import LLMService
from thoth.services.postgres_service import PostgresService
from thoth.services.project_organizer import ProjectOrganizer


@click.group()
def projects():
    """Manage research projects and paper organization."""
    pass


@projects.command('list')
async def list_projects_cmd():
    """List all projects with paper counts."""
    try:
        db = PostgresService()
        await db.initialize()

        async with db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    kc.name,
                    kc.description,
                    COUNT(pm.id) as paper_count,
                    kc.created_at
                FROM knowledge_collections kc
                LEFT JOIN paper_metadata pm ON pm.collection_id = kc.id
                WHERE pm.document_category = 'research_paper' OR pm.id IS NULL
                GROUP BY kc.id, kc.name, kc.description, kc.created_at
                ORDER BY paper_count DESC, kc.name
                """
            )

        if not rows:
            logger.info('No projects found')
            return

        logger.info(f'Found {len(rows)} projects:')
        for row in rows:
            logger.info(
                f'  {row["name"]}: {row["paper_count"]} papers (created: {row["created_at"].date()})'
            )

        await db.close()

    except Exception as e:
        logger.error(f'Failed to list projects: {e}')
        raise click.ClickException(str(e)) from e


@projects.command('organize')
@click.option(
    '--dry-run',
    is_flag=True,
    help='Show proposed organization without moving files',
)
@click.option(
    '--min-cluster-size',
    default=5,
    help='Minimum papers per cluster',
)
@click.option(
    '--max-clusters',
    default=15,
    help='Maximum number of clusters',
)
async def organize_papers_cmd(dry_run, min_cluster_size, max_clusters):
    """Auto-organize papers into projects."""
    try:
        logger.info('Initializing services...')
        db = PostgresService()
        await db.initialize()

        llm_service = LLMService()
        knowledge_repo = KnowledgeCollectionRepository(db)

        organizer = ProjectOrganizer(db, llm_service, knowledge_repo)

        # Step 1: Analyze papers
        logger.info('Step 1: Analyzing papers by tags...')
        clusters = await organizer.analyze_papers(min_cluster_size, max_clusters)

        if not clusters or (len(clusters) == 1 and 'Uncategorized' in clusters):
            logger.info('No papers to organize or insufficient clustering data')
            await db.close()
            return

        # Step 2: Refine with LLM
        logger.info('Step 2: Refining project names with LLM...')
        projects = await organizer.refine_with_llm(clusters)

        # Show proposed organization
        logger.info('\nProposed Organization:')
        logger.info('=' * 60)
        for project_name, paper_ids in projects.items():
            logger.info(f'{project_name}: {len(paper_ids)} papers')
        logger.info('=' * 60)

        if dry_run:
            logger.info('[DRY RUN] No files were moved')
        else:
            # Step 3: Execute
            logger.info('\nStep 3: Moving files and updating database...')
            summary = await organizer.execute_organization(projects, dry_run=False)

            logger.info('\nOrganization Summary:')
            logger.info(f'  Projects created: {summary["projects_created"]}')
            logger.info(f'  Papers moved: {summary["papers_moved"]}')
            logger.info(f'  Errors: {summary["errors"]}')

            if summary['error_details']:
                logger.warning('Errors encountered:')
                for error in summary['error_details'][:10]:  # Show first 10
                    logger.warning(f'  {error}')

        await db.close()

    except Exception as e:
        logger.error(f'Failed to organize papers: {e}')
        raise click.ClickException(str(e)) from e


@projects.command('move')
@click.argument('paper_id')
@click.argument('project_name')
async def move_paper_cmd(paper_id, project_name):
    """Move a single paper to a project."""
    try:
        import shutil

        from thoth.utilities.vault_path_resolver import VaultPathResolver

        db = PostgresService()
        await db.initialize()

        knowledge_repo = KnowledgeCollectionRepository(db)
        vault_resolver = VaultPathResolver(config.vault_root)

        # Get or create collection
        collection = await knowledge_repo.get_by_name(project_name)
        if not collection:
            collection = await knowledge_repo.create(
                name=project_name, description=f'Project: {project_name}'
            )
        collection_id = collection['id']

        # Get paper paths
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT pp.pdf_path, pp.markdown_path, pp.note_path
                FROM processed_papers pp
                WHERE pp.paper_id = $1
                """,
                paper_id,
            )

        if not row:
            raise click.ClickException(f'Paper {paper_id} not found')

        # Get current paths
        pdf_path = vault_resolver.resolve(row['pdf_path']) if row['pdf_path'] else None
        markdown_path = (
            vault_resolver.resolve(row['markdown_path'])
            if row['markdown_path']
            else None
        )
        note_path = (
            vault_resolver.resolve(row['note_path']) if row['note_path'] else None
        )

        # Create project directories
        pdf_project_dir = config.pdf_dir / project_name
        markdown_project_dir = config.markdown_dir / project_name
        notes_project_dir = config.notes_dir / project_name

        pdf_project_dir.mkdir(parents=True, exist_ok=True)
        markdown_project_dir.mkdir(parents=True, exist_ok=True)
        notes_project_dir.mkdir(parents=True, exist_ok=True)

        # Compute new paths
        new_pdf_path = pdf_project_dir / pdf_path.name if pdf_path else None
        new_markdown_path = (
            markdown_project_dir / markdown_path.name if markdown_path else None
        )
        new_note_path = notes_project_dir / note_path.name if note_path else None

        # Move files
        if pdf_path and pdf_path.exists():
            shutil.move(str(pdf_path), str(new_pdf_path))
            logger.info(f'Moved PDF to {new_pdf_path}')

        if markdown_path and markdown_path.exists():
            shutil.move(str(markdown_path), str(new_markdown_path))
            logger.info(f'Moved markdown to {new_markdown_path}')

        if note_path and note_path.exists():
            shutil.move(str(note_path), str(new_note_path))
            logger.info(f'Moved note to {new_note_path}')

        # Update database
        new_pdf_rel = (
            vault_resolver.make_relative(new_pdf_path) if new_pdf_path else None
        )
        new_markdown_rel = (
            vault_resolver.make_relative(new_markdown_path)
            if new_markdown_path
            else None
        )
        new_note_rel = (
            vault_resolver.make_relative(new_note_path) if new_note_path else None
        )

        async with db.acquire() as conn:
            await conn.execute(
                """
                UPDATE processed_papers
                SET pdf_path = $1, markdown_path = $2, note_path = $3, updated_at = NOW()
                WHERE paper_id = $4
                """,
                new_pdf_rel,
                new_markdown_rel,
                new_note_rel,
                paper_id,
            )

            await conn.execute(
                """
                UPDATE paper_metadata
                SET collection_id = $1, updated_at = NOW()
                WHERE id = $2
                """,
                collection_id,
                paper_id,
            )

        logger.success(f'Moved paper {paper_id[:8]} to project "{project_name}"')

        await db.close()

    except Exception as e:
        logger.error(f'Failed to move paper: {e}')
        raise click.ClickException(str(e)) from e


# Async wrappers for Click commands
def list_projects():
    asyncio.run(list_projects_cmd())


def organize_papers(dry_run, min_cluster_size, max_clusters):
    asyncio.run(organize_papers_cmd(dry_run, min_cluster_size, max_clusters))


def move_paper(paper_id, project_name):
    asyncio.run(move_paper_cmd(paper_id, project_name))

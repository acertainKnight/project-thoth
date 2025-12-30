#!/usr/bin/env python3
"""
Backfill script to populate missing data WITHOUT full PDF reprocessing.

This script backfills:
1. ✓ markdown_content - Read from existing _no_images.md files on disk
2. ✓ llm_model - Set to current config value (best guess)
3. ✓ embeddings - Generate from markdown_content using RAG service

Does NOT backfill:
✗ Citation metadata - Requires LLM extraction, needs full reprocessing

Usage:
    python -m thoth.migration.backfill_without_reprocessing

    # Or with options:
    python -m thoth.migration.backfill_without_reprocessing --skip-embeddings
"""

import asyncio
from pathlib import Path
from typing import List, Tuple
import asyncpg
from loguru import logger

from thoth.config import Config
from thoth.services.service_manager import ServiceManager


async def backfill_markdown_content(conn: asyncpg.Connection, config: Config) -> int:
    """
    Backfill markdown_content from existing _no_images.md files.

    Returns:
        Number of papers updated
    """
    logger.info("Step 1: Backfilling markdown_content from disk...")

    # Get papers missing markdown_content
    papers = await conn.fetch('''
        SELECT id, title, markdown_path
        FROM papers
        WHERE markdown_path IS NOT NULL
        AND markdown_content IS NULL
    ''')

    updated = 0
    errors = 0

    for paper in papers:
        try:
            md_path = Path(paper['markdown_path'])

            # Try _no_images version first (preferred for embeddings)
            if '_no_images' not in str(md_path):
                no_images_path = md_path.parent / f"{md_path.stem}_no_images{md_path.suffix}"
                if no_images_path.exists():
                    md_path = no_images_path

            if md_path.exists():
                markdown_content = md_path.read_text(encoding='utf-8')

                await conn.execute('''
                    UPDATE papers
                    SET markdown_content = $1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2
                ''', markdown_content, paper['id'])

                updated += 1
                if updated % 10 == 0:
                    logger.info(f"  Updated {updated} papers...")
            else:
                logger.warning(f"Markdown file not found: {md_path}")
                errors += 1

        except Exception as e:
            logger.error(f"Error reading {paper['markdown_path']}: {e}")
            errors += 1

    logger.success(f"✓ Backfilled markdown_content for {updated} papers ({errors} errors)")
    return updated


async def backfill_llm_model(conn: asyncpg.Connection, config: Config) -> int:
    """
    Backfill llm_model with current config value.

    Note: This is a best guess - we don't know which model was actually used
    for papers processed in the past. But it's better than NULL.

    Returns:
        Number of papers updated
    """
    logger.info("Step 2: Backfilling llm_model from config...")

    # Get current LLM model from config
    llm_model = getattr(config.llm_config, 'model', 'unknown')
    logger.info(f"  Using model: {llm_model}")

    # Update papers missing llm_model
    result = await conn.execute('''
        UPDATE papers
        SET llm_model = $1,
            updated_at = CURRENT_TIMESTAMP
        WHERE pdf_path IS NOT NULL
        AND llm_model IS NULL
    ''', llm_model)

    # Extract count from result string like "UPDATE 183"
    count = int(result.split()[-1]) if result.split() else 0

    logger.success(f"✓ Set llm_model for {count} papers")
    return count


async def generate_embeddings(config: Config, limit: int = None) -> Tuple[int, int]:
    """
    Generate embeddings for papers that have markdown_content but no embeddings.

    Args:
        config: Thoth configuration
        limit: Optional limit on number of papers to process

    Returns:
        Tuple of (papers_processed, total_chunks_created)
    """
    logger.info("Step 3: Generating embeddings from markdown_content...")

    # Initialize services
    services = ServiceManager(config=config)
    services.initialize()

    # Get connection
    conn = await asyncpg.connect(config.secrets.database_url)

    try:
        # Get papers with markdown_content but no embeddings
        query = '''
            SELECT p.id, p.title, p.markdown_content
            FROM papers p
            WHERE p.markdown_content IS NOT NULL
            AND NOT EXISTS(
                SELECT 1 FROM document_chunks c
                WHERE c.paper_id = p.id
            )
        '''

        if limit:
            query += f' LIMIT {limit}'

        papers = await conn.fetch(query)

        logger.info(f"  Found {len(papers)} papers needing embeddings")

        papers_processed = 0
        total_chunks = 0
        errors = 0

        for i, paper in enumerate(papers, 1):
            try:
                # Create documents from markdown content
                from langchain.schema import Document
                from langchain.text_splitter import RecursiveCharacterTextSplitter

                # Chunk the markdown content
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200,
                    length_function=len,
                )

                chunks = text_splitter.split_text(paper['markdown_content'])

                # Create Document objects
                documents = [
                    Document(
                        page_content=chunk,
                        metadata={
                            'source': paper['title'],
                            'paper_id': str(paper['id']),
                        }
                    )
                    for chunk in chunks
                ]

                # Add to vector store
                doc_ids = await services.rag.add_documents_async(
                    documents=documents,
                    paper_id=paper['id']
                )

                papers_processed += 1
                total_chunks += len(doc_ids)

                if papers_processed % 5 == 0:
                    logger.info(f"  Processed {papers_processed}/{len(papers)} papers, {total_chunks} chunks...")

            except Exception as e:
                logger.error(f"Error generating embeddings for {paper['title']}: {e}")
                errors += 1

        logger.success(f"✓ Generated embeddings for {papers_processed} papers ({total_chunks} chunks, {errors} errors)")
        return papers_processed, total_chunks

    finally:
        await conn.close()


async def main(skip_embeddings: bool = False, limit_embeddings: int = None):
    """
    Main backfill process.

    Args:
        skip_embeddings: Skip embedding generation (faster, but no semantic search)
        limit_embeddings: Limit number of papers to generate embeddings for
    """
    config = Config()

    logger.info("=" * 80)
    logger.info("BACKFILL WITHOUT REPROCESSING")
    logger.info("=" * 80)
    logger.info("This will backfill:")
    logger.info("  ✓ markdown_content (from _no_images.md files)")
    logger.info("  ✓ llm_model (from current config)")
    if not skip_embeddings:
        logger.info("  ✓ embeddings (generate from markdown_content)")
    else:
        logger.info("  ⏭  embeddings (skipped)")
    logger.info("")
    logger.info("Will NOT backfill:")
    logger.info("  ✗ citation metadata (requires full reprocessing)")
    logger.info("=" * 80)
    logger.info("")

    # Connect to database
    conn = await asyncpg.connect(config.secrets.database_url)

    try:
        # Step 1: Backfill markdown_content
        md_count = await backfill_markdown_content(conn, config)

        # Step 2: Backfill llm_model
        llm_count = await backfill_llm_model(conn, config)

        # Step 3: Generate embeddings (if not skipped)
        if not skip_embeddings:
            papers_processed, chunks_created = await generate_embeddings(config, limit_embeddings)
        else:
            papers_processed, chunks_created = 0, 0

        # Final summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 80)
        logger.info(f"✓ markdown_content: {md_count} papers updated")
        logger.info(f"✓ llm_model: {llm_count} papers updated")
        if not skip_embeddings:
            logger.info(f"✓ embeddings: {papers_processed} papers, {chunks_created} chunks")
        else:
            logger.info(f"⏭  embeddings: skipped")
        logger.info("")
        logger.info("Remaining work:")
        logger.info("  • Citation metadata requires full PDF reprocessing")
        logger.info("  • Or run citation extraction on existing markdown files")
        logger.info("=" * 80)

    finally:
        await conn.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Backfill data without full reprocessing')
    parser.add_argument('--skip-embeddings', action='store_true',
                        help='Skip embedding generation (faster)')
    parser.add_argument('--limit-embeddings', type=int,
                        help='Limit number of papers to generate embeddings for')

    args = parser.parse_args()

    asyncio.run(main(
        skip_embeddings=args.skip_embeddings,
        limit_embeddings=args.limit_embeddings
    ))

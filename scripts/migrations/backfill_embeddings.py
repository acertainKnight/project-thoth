"""
Backfill script to generate pgvector embeddings for existing markdown files.

This script:
1. Connects to PostgreSQL to find papers with markdown_content
2. Uses RAGService to index each markdown file
3. Generates document chunks with vector(1536) embeddings
4. Stores results in document_chunks table with HNSW index
"""

import sys
from pathlib import Path

from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from thoth.config import config
from thoth.services.service_manager import ServiceManager


def backfill_embeddings():
    """
    Backfill embeddings for papers with markdown_content.

    Process:
    1. Query papers table for papers with markdown_content
    2. For each paper, get the markdown_path
    3. Call RAGService.index_file() to generate embeddings
    4. Embeddings are stored in document_chunks table
    """
    logger.info('Starting embeddings backfill for existing papers')

    # Initialize service manager
    services = ServiceManager(config=config)
    services.initialize()

    if services.rag is None:
        logger.error('RAG service not available - requires embeddings extras')
        logger.error('Install with: uv sync --extra embeddings')
        return False

    # Connect to database to get papers with markdown
    import asyncpg  # noqa: I001
    import asyncio

    async def process_papers():
        db_url = getattr(config.secrets, 'database_url', None)
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        conn = await asyncpg.connect(db_url)
        try:
            # Get papers with markdown_content or markdown_path
            papers = await conn.fetch("""
                SELECT id, title, markdown_path, markdown_content
                FROM papers
                WHERE (markdown_path IS NOT NULL AND markdown_path != '')
                   OR (markdown_content IS NOT NULL AND markdown_content != '')
                ORDER BY created_at DESC
            """)

            logger.info(f'Found {len(papers)} papers with markdown to index')

            indexed = 0
            skipped = 0
            failed = 0

            for paper in papers:
                paper_id = paper['id']
                title = paper['title']
                markdown_path = paper['markdown_path']
                markdown_content = paper['markdown_content']

                try:
                    # Check if already indexed
                    existing = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM document_chunks
                        WHERE paper_id = $1
                    """,
                        paper_id,
                    )

                    if existing > 0:
                        logger.debug(f'Already indexed: {title} ({existing} chunks)')
                        skipped += 1
                        continue

                    # Try to index from file path first
                    if markdown_path:
                        file_path = Path(markdown_path)
                        if file_path.exists():
                            logger.info(f'Indexing from file: {title}')
                            doc_ids = services.rag.index_file(file_path)
                            logger.success(
                                f'Indexed {len(doc_ids)} chunks for: {title}'
                            )
                            indexed += 1
                            continue
                        else:
                            logger.warning(f'File not found: {markdown_path}')

                    # Fall back to markdown_content if file doesn't exist
                    if markdown_content:
                        logger.info(f'Indexing from content: {title}')
                        # Create temporary file with markdown content
                        import tempfile

                        with tempfile.NamedTemporaryFile(
                            mode='w', suffix='.md', delete=False
                        ) as tmp:
                            tmp.write(markdown_content)
                            tmp_path = Path(tmp.name)

                        try:
                            doc_ids = services.rag.index_file(tmp_path)
                            logger.success(
                                f'Indexed {len(doc_ids)} chunks for: {title}'
                            )
                            indexed += 1
                        finally:
                            tmp_path.unlink()
                        continue

                    logger.warning(f'No markdown available for: {title}')
                    skipped += 1

                except Exception as e:
                    logger.error(f'Failed to index {title}: {e}')
                    import traceback

                    traceback.print_exc()
                    failed += 1

            logger.info(f'\n=== Backfill Summary ===')  # noqa: F541
            logger.info(f'Total papers: {len(papers)}')
            logger.info(f'Indexed: {indexed}')
            logger.info(f'Skipped (already indexed): {skipped}')
            logger.info(f'Failed: {failed}')

            # Verify document_chunks table
            total_chunks = await conn.fetchval('SELECT COUNT(*) FROM document_chunks')
            papers_with_chunks = await conn.fetchval("""
                SELECT COUNT(DISTINCT paper_id) FROM document_chunks
            """)
            logger.info(f'\n=== Database Status ===')  # noqa: F541
            logger.info(f'Total document chunks: {total_chunks}')
            logger.info(f'Papers with embeddings: {papers_with_chunks}')

            return True

        finally:
            await conn.close()

    # Run async function
    try:
        success = asyncio.run(process_papers())
        return success
    except Exception as e:
        logger.error(f'Backfill failed: {e}')
        import traceback

        traceback.print_exc()
        return False


if __name__ == '__main__':
    logger.info('=' * 60)
    logger.info('EMBEDDINGS BACKFILL TO POSTGRESQL DOCUMENT_CHUNKS')
    logger.info('=' * 60)

    success = backfill_embeddings()

    logger.info('=' * 60)
    if success:
        logger.success('BACKFILL COMPLETED SUCCESSFULLY!')
        logger.info('\nTo verify embeddings:')
        logger.info('  SELECT COUNT(*) as total_chunks,')
        logger.info('         COUNT(DISTINCT paper_id) as papers_with_embeddings')
        logger.info('  FROM document_chunks;')
    else:
        logger.error('BACKFILL FAILED!')
    logger.info('=' * 60)

    sys.exit(0 if success else 1)

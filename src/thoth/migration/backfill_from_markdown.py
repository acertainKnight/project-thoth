"""Backfill embeddings from existing no_images markdown files."""

import sys
from pathlib import Path
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from thoth.config import config
from thoth.services.service_manager import ServiceManager


def backfill_from_markdown_files():
    """Backfill embeddings from no_images markdown files."""
    logger.info("Starting embeddings backfill")

    services = ServiceManager(config=config)
    services.initialize()

    if services.rag is None:
        logger.error("RAG service not available")
        return False

    markdown_dir = Path(config.markdown_dir)
    no_images_files = list(markdown_dir.glob("*_no_images.md"))

    logger.info(f"Found {len(no_images_files)} no_images files")

    if not no_images_files:
        logger.warning("No files found")
        return False

    indexed = 0
    skipped = 0
    failed = 0

    for file_path in no_images_files:
        try:
            paper_name = file_path.stem.replace("_no_images", "")
            logger.info(f"Processing: {paper_name}")

            doc_ids = services.rag.index_file(file_path)

            if doc_ids and len(doc_ids) > 0:
                logger.success(f"Indexed {len(doc_ids)} chunks: {paper_name}")
                indexed += 1
            else:
                logger.warning(f"No chunks: {paper_name}")
                skipped += 1

        except Exception as e:
            logger.error(f"Failed {file_path.name}: {e}")
            failed += 1

    logger.info(f"\nIndexed: {indexed}, Skipped: {skipped}, Failed: {failed}")

    import asyncpg, asyncio

    async def verify():
        conn = await asyncpg.connect(config.secrets.database_url)
        try:
            total = await conn.fetchval("SELECT COUNT(*) FROM document_chunks")
            papers = await conn.fetchval("SELECT COUNT(DISTINCT paper_id) FROM document_chunks")
            logger.info(f"Total chunks: {total}, Papers: {papers}")
        finally:
            await conn.close()

    try:
        asyncio.run(verify())
    except:
        pass

    return True


if __name__ == '__main__':
    logger.info("=" * 60)
    success = backfill_from_markdown_files()
    logger.success("COMPLETED!" if success else "FAILED!")
    logger.info("=" * 60)
    sys.exit(0 if success else 1)

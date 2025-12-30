#!/usr/bin/env python3
"""
Debug citation reprocessing for one paper with detailed logging.
"""

import asyncio
from pathlib import Path
import asyncpg
from loguru import logger
import sys

# Set DEBUG level
logger.remove()
logger.add(sys.stdout, level="DEBUG")

from thoth.config import Config
from thoth.services.service_manager import ServiceManager
from thoth.knowledge.graph import CitationGraph
from thoth.utilities.schemas import AnalysisResponse


async def async_main():
    """Process one paper with detailed debug logging."""
    config = Config()

    conn = await asyncpg.connect(config.secrets.database_url)

    try:
        # Get one paper
        query = '''
            SELECT
                id,
                title,
                doi,
                arxiv_id,
                pdf_path,
                markdown_path,
                analysis_data,
                llm_model
            FROM papers
            WHERE markdown_path IS NOT NULL
            AND pdf_path IS NOT NULL
            AND analysis_data IS NOT NULL
            LIMIT 1
        '''

        paper = await conn.fetchrow(query)

        if not paper:
            logger.error("No papers found")
            return

        logger.info(f"=== Processing paper: {paper['title'][:60]} ===")
        logger.info(f"PDF: {paper['pdf_path']}")
        logger.info(f"Markdown: {paper['markdown_path']}")

        # Check citation count BEFORE
        before_count = await conn.fetchval("SELECT COUNT(*) FROM citations")
        logger.info(f"✓ Citations in database BEFORE: {before_count}")

    finally:
        await conn.close()

    # Initialize services
    logger.info("✓ Initializing services...")
    services = ServiceManager(config=config)
    services.initialize()

    # Initialize citation tracker
    knowledge_dir = Path(config.knowledge_base_dir)
    logger.info("✓ Creating CitationGraph...")
    citation_tracker = CitationGraph(
        knowledge_base_dir=knowledge_dir,
        service_manager=services
    )

    # Disable note regeneration
    logger.info("✓ Disabling note regeneration...")
    citation_tracker.service_manager = None
    citation_tracker.note_generator = None

    # Prepare paths
    pdf_path = Path(paper['pdf_path'])
    markdown_path = Path(paper['markdown_path'])

    # Find no_images version
    if '_no_images' in markdown_path.name:
        md_for_citations = markdown_path
    else:
        no_images = markdown_path.parent / f"{markdown_path.stem}_no_images{markdown_path.suffix}"
        md_for_citations = no_images if no_images.exists() else markdown_path

    logger.info(f"✓ Using markdown for citations: {md_for_citations.name}")

    # Extract citations
    logger.info("✓ Extracting citations...")
    citations = services.citation.extract_citations(md_for_citations)

    ref_cites = [c for c in citations if not c.is_document_citation]
    doc_cites = [c for c in citations if c.is_document_citation]

    logger.info(f"✓ Extracted {len(citations)} total citations:")
    logger.info(f"  - Document citations: {len(doc_cites)}")
    logger.info(f"  - Reference citations: {len(ref_cites)}")

    if len(ref_cites) == 0:
        logger.error("❌ No reference citations extracted!")
        return

    # Convert analysis_data
    import json
    logger.info("✓ Parsing analysis data...")
    analysis_dict = json.loads(paper['analysis_data'])
    analysis = AnalysisResponse(**analysis_dict)

    # Read markdown content
    logger.info("✓ Reading markdown content...")
    markdown_content = md_for_citations.read_text(encoding='utf-8', errors='ignore').replace('\x00', '')
    logger.info(f"  - Content length: {len(markdown_content)} chars")

    # Process citations
    logger.info("=" * 80)
    logger.info("CALLING citation_tracker.process_citations()...")
    logger.info("=" * 80)

    try:
        article_id = citation_tracker.process_citations(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            analysis=analysis,
            citations=citations,
            llm_model=paper['llm_model'],
            no_images_markdown=markdown_content
        )

        logger.info("=" * 80)
        logger.info(f"✓ process_citations() returned: {article_id}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ ERROR in process_citations(): {e}")
        import traceback
        logger.error(traceback.format_exc())
        return

    # Check citation count AFTER
    conn = await asyncpg.connect(config.secrets.database_url)
    try:
        after_count = await conn.fetchval("SELECT COUNT(*) FROM citations")
        logger.info(f"✓ Citations in database AFTER: {after_count}")
        logger.info(f"✓ New citations created: {after_count - before_count}")

        if after_count == before_count:
            logger.error("=" * 80)
            logger.error("❌ NO CITATIONS WERE SAVED TO DATABASE!")
            logger.error("=" * 80)
        else:
            logger.success("=" * 80)
            logger.success(f"✅ Successfully saved {after_count - before_count} citations")
            logger.success("=" * 80)
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(async_main())

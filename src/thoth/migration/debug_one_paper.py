#!/usr/bin/env python3
"""Debug script to process one paper and trace citation saving."""

import asyncio  # noqa: I001
from pathlib import Path
from loguru import logger
import sys

# Setup logging
logger.remove()
logger.add(sys.stdout, level='DEBUG')

from thoth.config import Config  # noqa: I001, E402
from thoth.services.service_manager import ServiceManager  # noqa: E402
from thoth.analyze.citations.tracker import CitationTracker  # noqa: E402
from thoth.utilities.schemas import AnalysisResponse  # noqa: E402


async def debug_one_paper():
    """Process one paper with full debug logging."""

    # Initialize services
    config = Config()
    services = ServiceManager(config=config)
    services.initialize()

    citation_tracker = CitationTracker(config, services)

    # Get one paper from database
    from thoth.database.connection import get_db_connection

    conn = await get_db_connection()

    paper = await conn.fetchrow("""
        SELECT
            pdf_path,
            markdown_path,
            analysis_data::text,
            llm_model,
            title
        FROM processed_papers
        WHERE analysis_data IS NOT NULL
        LIMIT 1
    """)

    if not paper:
        logger.error('No papers found in database')
        return

    logger.info(f'Processing paper: {paper["title"]}')

    pdf_path = Path(paper['pdf_path'])
    markdown_path = Path(paper['markdown_path'])

    # Find no_images version
    if '_no_images' in markdown_path.name:
        md_for_citations = markdown_path
    else:
        no_images = (
            markdown_path.parent
            / f'{markdown_path.stem}_no_images{markdown_path.suffix}'
        )
        md_for_citations = no_images if no_images.exists() else markdown_path

    logger.info(f'Using markdown: {md_for_citations}')

    # Extract citations
    logger.info('Extracting citations...')
    citations = services.citation.extract_citations(md_for_citations)

    ref_cites = [c for c in citations if not c.is_document_citation]
    logger.info(f'Extracted {len(ref_cites)} reference citations')

    if len(ref_cites) == 0:
        logger.error('No citations extracted - stopping')
        return

    # Convert analysis_data
    import json

    analysis_dict = json.loads(paper['analysis_data'])
    analysis = AnalysisResponse(**analysis_dict)

    # Read markdown content
    markdown_content = md_for_citations.read_text(
        encoding='utf-8', errors='ignore'
    ).replace('\x00', '')

    # Check citation count BEFORE processing
    before_count = await conn.fetchval('SELECT COUNT(*) FROM citations')
    logger.info(f'Citations in database BEFORE: {before_count}')

    # Process citations
    logger.info('Processing citations (this calls CitationGraph.process_citations)...')
    article_id = citation_tracker.process_citations(
        pdf_path=pdf_path,
        markdown_path=markdown_path,
        analysis=analysis,
        citations=citations,
        llm_model=paper['llm_model'],
        no_images_markdown=markdown_content,
    )

    logger.info(f'process_citations returned article_id: {article_id}')

    # Check citation count AFTER processing
    after_count = await conn.fetchval('SELECT COUNT(*) FROM citations')
    logger.info(f'Citations in database AFTER: {after_count}')
    logger.info(f'New citations created: {after_count - before_count}')

    if after_count == before_count:
        logger.error('❌ NO CITATIONS WERE SAVED TO DATABASE!')
        logger.error(
            'Issue is in CitationGraph.process_citations or citation_tracker.process_citations'
        )
    else:
        logger.success(f'✅ Successfully saved {after_count - before_count} citations')

    await conn.close()


if __name__ == '__main__':
    asyncio.run(debug_one_paper())

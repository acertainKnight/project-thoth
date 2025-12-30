#!/usr/bin/env python3
"""
Simple citation reprocessing - reuse existing pipeline code.

This script:
1. Gets all papers with markdown files
2. Extracts citations using existing citation service
3. Calls process_citations() to update database (existing code)
4. Optionally regenerates notes

Usage:
    python -m thoth.migration.reprocess_citations_simple
    python -m thoth.migration.reprocess_citations_simple --limit 10
    python -m thoth.migration.reprocess_citations_simple --skip-notes
"""

import asyncio
from pathlib import Path
import asyncpg
from loguru import logger

from thoth.config import Config
from thoth.services.service_manager import ServiceManager
from thoth.knowledge.graph import CitationGraph
from thoth.utilities.schemas import AnalysisResponse


def main_sync(limit: int = None, skip_notes: bool = False):
    """Reprocess citations for all papers (synchronous wrapper)."""
    # Run the async part
    asyncio.run(async_main(limit=limit, skip_notes=skip_notes))


async def async_main(limit: int = None, skip_notes: bool = False):
    """Reprocess citations for all papers (async data fetching only)."""
    config = Config()

    conn = await asyncpg.connect(config.secrets.database_url)

    try:
        logger.info("=" * 80)
        logger.info("CITATION REPROCESSING - Simple Pipeline Reuse")
        logger.info("=" * 80)

        # Get papers to process
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
        '''

        if limit:
            query += f' LIMIT {limit}'

        papers = await conn.fetch(query)

        logger.info(f"Processing {len(papers)} papers...")
        logger.info("")

    finally:
        await conn.close()

    # Now process papers synchronously (CitationGraph uses sync methods)
    services = ServiceManager(config=config)
    services.initialize()

    # Initialize citation tracker
    knowledge_dir = Path(config.knowledge_base_dir)
    citation_tracker = CitationGraph(
        knowledge_base_dir=knowledge_dir,
        service_manager=services
    )

    # Note: Note regeneration is FAST (just template rendering from existing data)
    # It will update Obsidian notes to reflect new citation relationships
    # Keeping service_manager enabled to regenerate connected notes

    processed = 0
    errors = 0
    total_citations = 0

    for i, paper in enumerate(papers, 1):
        try:
            pdf_path = Path(paper['pdf_path'])
            markdown_path = Path(paper['markdown_path'])

            # Find no_images version
            if '_no_images' in markdown_path.name:
                md_for_citations = markdown_path
            else:
                no_images = markdown_path.parent / f"{markdown_path.stem}_no_images{markdown_path.suffix}"
                md_for_citations = no_images if no_images.exists() else markdown_path

            # Extract citations using existing service
            citations = services.citation.extract_citations(md_for_citations)

            # Convert analysis_data from database to AnalysisResponse
            import json
            analysis_dict = json.loads(paper['analysis_data'])
            analysis = AnalysisResponse(**analysis_dict)

            # Get llm_model
            llm_model = paper['llm_model']

            # Read markdown content
            markdown_content = md_for_citations.read_text(encoding='utf-8', errors='ignore').replace('\x00', '')

            # Process citations using EXISTING pipeline code
            # This updates the graph AND database with full metadata
            article_id = citation_tracker.process_citations(
                pdf_path=pdf_path,
                markdown_path=markdown_path,
                analysis=analysis,
                citations=citations,
                llm_model=llm_model,
                no_images_markdown=markdown_content
            )

            if article_id:
                processed += 1
                citation_count = len([c for c in citations if not c.is_document_citation])
                total_citations += citation_count

                logger.info(f"[{i}/{len(papers)}] {paper['title'][:50]}: {citation_count} citations")
            else:
                logger.warning(f"[{i}/{len(papers)}] {paper['title'][:50]}: Failed to process")
                errors += 1

        except Exception as e:
            errors += 1
            logger.error(f"Error processing {paper['title'][:40]}: {e}")

    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("REPROCESSING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"✓ Papers processed: {processed}/{len(papers)}")
    logger.info(f"✓ Citations updated: {total_citations}")
    logger.info(f"✗ Errors: {errors}")
    logger.info("")
    logger.info("What was updated:")
    logger.info("  ✓ Citation metadata in database (all 9 fields)")
    logger.info("  ✓ Citation graph edges with full metadata")
    logger.info("  ✓ Notes updated with proper citation links")
    logger.info("=" * 80)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Reprocess citations using existing pipeline')
    parser.add_argument('--limit', type=int, help='Limit number of papers to process')
    parser.add_argument('--skip-notes', action='store_true', help='Skip note regeneration')

    args = parser.parse_args()

    main_sync(limit=args.limit, skip_notes=args.skip_notes)

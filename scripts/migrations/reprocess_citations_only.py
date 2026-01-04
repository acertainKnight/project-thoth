#!/usr/bin/env python3
"""
Reprocess citations and notes WITHOUT full PDF reprocessing.

This script:
1. Extracts citations from existing markdown files (1 LLM call per paper)
2. Updates citation metadata in the database
3. Regenerates all Obsidian notes with complete data (NO LLM calls)

This is much faster than full reprocessing:
- ✓ Skips: PDF OCR, content analysis
- ✓ Only: Citation extraction (fast LLM call)
- ✓ Then: Note regeneration from database (no LLM)

Usage:
    python -m thoth.migration.reprocess_citations_only

    # Or with options:
    python -m thoth.migration.reprocess_citations_only --limit 10
    python -m thoth.migration.reprocess_citations_only --skip-note-regeneration
"""

import asyncio  # noqa: I001
from pathlib import Path
from typing import List  # noqa: UP035
import asyncpg
from loguru import logger

from thoth.config import Config
from thoth.services.service_manager import ServiceManager
from thoth.utilities.schemas import Citation, AnalysisResponse


async def extract_citations_from_markdown(
    services: ServiceManager,
    paper_id: str,  # noqa: ARG001
    markdown_path: Path,
) -> List[Citation]:  # noqa: UP006
    """
    Extract citations from a markdown file using LLM.

    Args:
        services: Service manager with citation service
        paper_id: Paper ID for the main document
        markdown_path: Path to markdown file

    Returns:
        List of Citation objects with metadata
    """
    try:
        # Extract citations using the citation service
        citations = services.citation.extract_citations(markdown_path)

        # Mark the first citation as the document itself (if it matches the paper)
        if citations and not any(c.is_document_citation for c in citations):
            citations[0].is_document_citation = True

        return citations
    except Exception as e:
        logger.error(f'Failed to extract citations from {markdown_path}: {e}')
        return []


async def update_citation_metadata(
    paper_id: str,
    citations: List[Citation],  # noqa: UP006
    citation_tracker,
    conn: asyncpg.Connection,
) -> int:
    """
    Update citation metadata in the database.

    Args:
        paper_id: ID of the citing paper
        citations: List of Citation objects with metadata
        citation_tracker: CitationGraph instance
        conn: Database connection

    Returns:
        Number of citations updated
    """
    updated = 0

    # Skip the document citation itself
    for citation in citations:
        if citation.is_document_citation:
            continue

        try:
            # Generate target article ID
            target_id = citation_tracker._generate_article_id(citation)

            # Add/update the cited article in the graph
            citation_tracker.add_article_from_citation(citation)

            # Get paper IDs from database
            citing_paper = await conn.fetchrow(
                """
                SELECT id FROM papers
                WHERE doi = $1 OR arxiv_id = $1 OR title = $1
                LIMIT 1
            """,
                paper_id.split(':', 1)[1] if ':' in paper_id else paper_id,
            )

            cited_paper = await conn.fetchrow(
                """
                SELECT id FROM papers
                WHERE doi = $1 OR arxiv_id = $1 OR title = $1
                LIMIT 1
            """,
                target_id.split(':', 1)[1] if ':' in target_id else target_id,
            )

            if not citing_paper or not cited_paper:
                continue

            # Update citation with full metadata
            import json

            authors_json = json.dumps(citation.authors) if citation.authors else None

            await conn.execute(
                """
                INSERT INTO citations (
                    citing_paper_id,
                    cited_paper_id,
                    citation_text,
                    extracted_title,
                    extracted_authors,
                    extracted_year,
                    extracted_venue,
                    is_influential
                )
                VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)
                ON CONFLICT (citing_paper_id, cited_paper_id) DO UPDATE SET
                    citation_text = COALESCE(EXCLUDED.citation_text, citations.citation_text),
                    extracted_title = COALESCE(EXCLUDED.extracted_title, citations.extracted_title),
                    extracted_authors = COALESCE(EXCLUDED.extracted_authors, citations.extracted_authors),
                    extracted_year = COALESCE(EXCLUDED.extracted_year, citations.extracted_year),
                    extracted_venue = COALESCE(EXCLUDED.extracted_venue, citations.extracted_venue),
                    is_influential = COALESCE(EXCLUDED.is_influential, citations.is_influential),
                    updated_at = CURRENT_TIMESTAMP
            """,
                citing_paper['id'],
                cited_paper['id'],
                citation.text,
                citation.title,
                authors_json,
                citation.year,
                citation.venue or citation.journal,
                citation.influential_citation_count
                and citation.influential_citation_count > 0,
            )

            updated += 1

        except Exception as e:
            logger.debug(f'Error updating citation metadata: {e}')
            continue

    return updated


async def regenerate_note(
    services: ServiceManager, paper_id: str, conn: asyncpg.Connection
) -> bool:
    """
    Regenerate Obsidian note from database data (NO LLM calls).

    Args:
        services: Service manager with note service
        paper_id: Paper ID
        conn: Database connection

    Returns:
        True if note was regenerated successfully
    """
    try:
        # Get paper data from database
        paper = await conn.fetchrow(
            """
            SELECT
                id,
                title,
                authors,
                year,
                doi,
                arxiv_id,
                pdf_path,
                markdown_path,
                note_path,
                analysis_data,
                keywords
            FROM papers
            WHERE doi = $1 OR arxiv_id = $1 OR title = $1
            LIMIT 1
        """,
            paper_id.split(':', 1)[1] if ':' in paper_id else paper_id,
        )

        if not paper:
            logger.warning(f'Paper not found: {paper_id}')
            return False

        # Get citations for this paper
        citations_data = await conn.fetch(
            """
            SELECT
                c.citation_text,
                c.extracted_title,
                c.extracted_authors,
                c.extracted_year,
                c.extracted_venue,
                p.doi,
                p.arxiv_id,
                p.title as cited_title
            FROM citations c
            JOIN papers p ON c.cited_paper_id = p.id
            WHERE c.citing_paper_id = $1
        """,
            paper['id'],
        )

        # Convert to Citation objects
        citations = []
        for cit in citations_data:
            import json

            authors = (
                json.loads(cit['extracted_authors'])
                if cit['extracted_authors']
                else None
            )

            citation = Citation(
                text=cit['citation_text'],
                title=cit['extracted_title'] or cit['cited_title'],
                authors=authors,
                year=cit['extracted_year'],
                venue=cit['extracted_venue'],
                doi=cit['doi'],
                arxiv_id=cit['arxiv_id'],
            )
            citations.append(citation)

        # Convert analysis_data to AnalysisResponse
        import json

        analysis_dict = (
            json.loads(paper['analysis_data']) if paper['analysis_data'] else {}
        )
        analysis = AnalysisResponse(**analysis_dict)

        # Regenerate note using note service
        # The note service will use the existing paths and just regenerate content
        if paper['pdf_path'] and paper['markdown_path']:
            note_path, _, _ = services.note.create_note(
                pdf_path=Path(paper['pdf_path']),
                markdown_path=Path(paper['markdown_path']),
                analysis=analysis,
                citations=citations,
            )

            logger.debug(f'Regenerated note: {note_path}')
            return True
        else:
            logger.warning(f'Missing paths for paper: {paper["title"]}')
            return False

    except Exception as e:
        logger.error(f'Failed to regenerate note for {paper_id}: {e}')
        return False


async def main(limit: int = None, skip_note_regeneration: bool = False):  # noqa: RUF013
    """
    Main reprocessing workflow.

    Args:
        limit: Optional limit on number of papers to process
        skip_note_regeneration: Skip note regeneration step
    """
    config = Config()
    services = ServiceManager(config=config)
    services.initialize()

    # Get citation tracker
    from thoth.knowledge.graph import CitationGraph

    knowledge_dir = Path(config.knowledge_base_dir)
    citation_tracker = CitationGraph(knowledge_dir)

    conn = await asyncpg.connect(config.secrets.database_url)

    try:
        logger.info('=' * 80)
        logger.info('REPROCESS CITATIONS ONLY - No Full PDF Reprocessing')
        logger.info('=' * 80)
        logger.info(
            'Step 1: Extract citations from markdown files (1 LLM call per paper)'
        )
        logger.info('Step 2: Update citation metadata in database')
        if not skip_note_regeneration:
            logger.info(
                'Step 3: Regenerate all notes with complete data (NO LLM calls)'
            )
        else:
            logger.info('Step 3: SKIPPED (use --skip-note-regeneration)')
        logger.info('=' * 80)
        logger.info('')

        # Get papers to process
        query = """
            SELECT
                id,
                title,
                doi,
                arxiv_id,
                markdown_path
            FROM papers
            WHERE markdown_path IS NOT NULL
            AND pdf_path IS NOT NULL
        """

        if limit:
            query += f' LIMIT {limit}'

        papers = await conn.fetch(query)

        logger.info(f'Processing {len(papers)} papers...')
        logger.info('')

        # Step 1 & 2: Extract citations and update metadata
        total_citations = 0
        papers_with_citations = 0
        errors = 0

        for i, paper in enumerate(papers, 1):
            try:
                # Generate paper_id
                if paper['doi']:
                    paper_id = f'doi:{paper["doi"]}'
                elif paper['arxiv_id']:
                    paper_id = f'arxiv:{paper["arxiv_id"]}'
                else:
                    paper_id = f'title:{paper["title"]}'

                # Extract citations from markdown
                markdown_path = Path(paper['markdown_path'])
                citations = await extract_citations_from_markdown(
                    services, paper_id, markdown_path
                )

                if citations:
                    # Update citation metadata in database
                    updated = await update_citation_metadata(
                        paper_id, citations, citation_tracker, conn
                    )

                    if updated > 0:
                        papers_with_citations += 1
                        total_citations += updated

                    logger.info(
                        f'[{i}/{len(papers)}] {paper["title"][:50]}: {updated} citations'
                    )
                else:
                    logger.debug(
                        f'[{i}/{len(papers)}] {paper["title"][:50]}: No citations found'
                    )

            except Exception as e:
                errors += 1
                logger.error(f'Error processing {paper["title"][:40]}: {e}')

        logger.info('')
        logger.success(f'✓ Extracted citations from {papers_with_citations} papers')
        logger.success(f'✓ Updated {total_citations} citation records')
        if errors > 0:
            logger.warning(f'⚠ {errors} errors occurred')

        # Step 3: Regenerate notes
        if not skip_note_regeneration:
            logger.info('')
            logger.info('Step 3: Regenerating notes from database...')

            notes_regenerated = 0
            note_errors = 0

            for i, paper in enumerate(papers, 1):  # noqa: B007
                try:
                    # Generate paper_id
                    if paper['doi']:
                        paper_id = f'doi:{paper["doi"]}'
                    elif paper['arxiv_id']:
                        paper_id = f'arxiv:{paper["arxiv_id"]}'
                    else:
                        paper_id = f'title:{paper["title"]}'

                    # Regenerate note
                    success = await regenerate_note(services, paper_id, conn)

                    if success:
                        notes_regenerated += 1
                        if notes_regenerated % 10 == 0:
                            logger.info(
                                f'  Regenerated {notes_regenerated}/{len(papers)} notes...'
                            )
                    else:
                        note_errors += 1

                except Exception as e:
                    note_errors += 1
                    logger.error(
                        f'Error regenerating note for {paper["title"][:40]}: {e}'
                    )

            logger.success(f'✓ Regenerated {notes_regenerated} notes')
            if note_errors > 0:
                logger.warning(f'⚠ {note_errors} note errors occurred')

        # Final summary
        logger.info('')
        logger.info('=' * 80)
        logger.info('REPROCESSING COMPLETE')
        logger.info('=' * 80)
        logger.info(f'✓ Papers processed: {len(papers)}')
        logger.info(f'✓ Citations extracted: {total_citations}')
        if not skip_note_regeneration:
            logger.info(f'✓ Notes regenerated: {notes_regenerated}')
        logger.info('')
        logger.info('LLM Calls Made:')
        logger.info(f'  • Citation extraction: {papers_with_citations} calls')
        logger.info(f'  • Content analysis: 0 calls (skipped)')  # noqa: F541
        logger.info(f'  • Note generation: 0 calls (used database data)')  # noqa: F541
        logger.info('=' * 80)

    finally:
        await conn.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Reprocess citations without full PDF reprocessing'
    )
    parser.add_argument('--limit', type=int, help='Limit number of papers to process')
    parser.add_argument(
        '--skip-note-regeneration',
        action='store_true',
        help='Skip note regeneration step',
    )

    args = parser.parse_args()

    asyncio.run(
        main(limit=args.limit, skip_note_regeneration=args.skip_note_regeneration)
    )

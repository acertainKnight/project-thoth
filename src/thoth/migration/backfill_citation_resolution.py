#!/usr/bin/env python3
"""
Citation Resolution Backfill Migration Script

This script backfills existing citations in the database using the new improved
citation resolution system (resolution_chain.py + enrichment_service.py).

Usage:
    # Test on small sample (run inside Docker)
    docker compose exec thoth-api python -m thoth.migration.backfill_citation_resolution --limit 20 --dry-run

    # Run full backfill
    docker compose exec thoth-api python -m thoth.migration.backfill_citation_resolution

Features:
- Batch processing with checkpoints
- Progress tracking and statistics
- Resume capability after interruption
- Dry-run mode for testing
- Detailed logging and reporting
"""  # noqa: W505

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
from loguru import logger

from thoth.analyze.citations.crossref_resolver import CrossrefResolver
from thoth.analyze.citations.enrichment_service import CitationEnrichmentService
from thoth.analyze.citations.openalex_resolver import OpenAlexResolver
from thoth.analyze.citations.resolution_chain import CitationResolutionChain
from thoth.analyze.citations.semanticscholar import SemanticScholarAPI
from thoth.config import Config
from thoth.utilities.schemas.citations import Citation


class BackfillStats:
    """Track backfill statistics."""

    def __init__(self):
        self.total_citations = 0
        self.processed = 0
        self.resolved = 0
        self.partial = 0
        self.manual_review = 0
        self.unresolved = 0
        self.failed = 0
        self.skipped = 0
        self.start_time = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return {
            'total_citations': self.total_citations,
            'processed': self.processed,
            'resolved': self.resolved,
            'partial': self.partial,
            'manual_review': self.manual_review,
            'unresolved': self.unresolved,
            'failed': self.failed,
            'skipped': self.skipped,
            'elapsed_seconds': elapsed,
            'citations_per_second': self.processed / elapsed if elapsed > 0 else 0,
        }

    def __str__(self) -> str:
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.processed / elapsed if elapsed > 0 else 0
        return (
            f'Backfill Stats:\n'
            f'  Total: {self.total_citations}\n'
            f'  Processed: {self.processed} ({rate:.2f}/s)\n'
            f'  Resolved: {self.resolved}\n'
            f'  Partial: {self.partial}\n'
            f'  Manual Review: {self.manual_review}\n'
            f'  Unresolved: {self.unresolved}\n'
            f'  Failed: {self.failed}\n'
            f'  Skipped (has DOI): {self.skipped}\n'
            f'  Elapsed: {elapsed:.1f}s'
        )


class CitationBackfillManager:
    """Manages the backfill process for citations."""

    def __init__(
        self,
        config: Config,
        dry_run: bool = False,
        checkpoint_dir: Path | None = None,
    ):
        self.config = config
        self.dry_run = dry_run
        self.checkpoint_dir = checkpoint_dir or (
            config.vault_root / '_thoth/data/backfill_checkpoints'
        )
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.stats = BackfillStats()
        self.db_url = config.secrets.database_url

        # Initialize resolution components
        logger.info('Initializing citation resolution system...')
        cache_dir = config.vault_root / '_thoth/data/api_cache'
        self.crossref_resolver = CrossrefResolver(
            enable_caching=False, cache_dir=str(cache_dir / 'crossref')
        )
        self.openalex_resolver = OpenAlexResolver()  # No caching parameter
        self.s2_api = SemanticScholarAPI(cache_dir=str(cache_dir / 'semanticscholar'))

        self.resolution_chain = CitationResolutionChain(
            crossref_resolver=self.crossref_resolver,
            openalex_resolver=self.openalex_resolver,
            semanticscholar_resolver=self.s2_api,
        )

        self.enrichment_service = CitationEnrichmentService()

        logger.info('Citation resolution system initialized')

    async def fetch_citations_to_backfill(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch citations from database that need resolution."""
        conn = await asyncpg.connect(self.db_url)
        try:
            query = """
                SELECT
                    c.id,
                    c.citation_text,
                    c.extracted_title,
                    c.extracted_authors,
                    c.extracted_year,
                    c.extracted_venue,
                    c.cited_paper_id,
                    p.doi as cited_paper_doi,
                    p.title as cited_paper_title
                FROM citations c
                LEFT JOIN papers p ON c.cited_paper_id = p.id
                WHERE c.extracted_title IS NOT NULL
                ORDER BY c.id
            """

            if limit:
                query += f' LIMIT {limit}'
            if offset:
                query += f' OFFSET {offset}'

            rows = await conn.fetch(query)
            return [dict(row) for row in rows]
        finally:
            await conn.close()

    async def update_citation_resolution(
        self,
        citation_id: int,
        doi: str | None,
        title: str | None,
        authors: list[str] | None,
        year: int | None,
        venue: str | None,
        abstract: str | None,
    ) -> None:
        """Update a citation record with resolution results."""
        if self.dry_run:
            logger.info(
                f'[DRY RUN] Would update citation {citation_id} with DOI: {doi}'
            )
            return

        conn = await asyncpg.connect(self.db_url)
        try:
            if doi:
                # Check if paper exists
                paper = await conn.fetchrow('SELECT id FROM papers WHERE doi = $1', doi)

                if paper:
                    paper_id = paper['id']
                    # Update existing paper
                    await conn.execute(
                        """
                        UPDATE papers SET
                            title = COALESCE($1, title),
                            authors = COALESCE($2::jsonb, authors),
                            year = COALESCE($3, year),
                            venue = COALESCE($4, venue),
                            abstract = COALESCE($5, abstract),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $6
                        """,
                        title,
                        json.dumps(authors) if authors else None,
                        year,
                        venue,
                        abstract,
                        paper_id,
                    )
                else:
                    # Create new paper
                    paper_id = await conn.fetchval(
                        """
                        INSERT INTO papers (doi, title, authors, year, venue, abstract)
                        VALUES ($1, $2, $3::jsonb, $4, $5, $6)
                        RETURNING id
                        """,
                        doi,
                        title,
                        json.dumps(authors) if authors else None,
                        year,
                        venue,
                        abstract,
                    )

                # Update citation to link to resolved paper
                await conn.execute(
                    """
                    UPDATE citations SET
                        cited_paper_id = $1,
                        extracted_title = COALESCE($2, extracted_title),
                        extracted_authors = COALESCE($3::jsonb, extracted_authors),
                        extracted_year = COALESCE($4, extracted_year),
                        extracted_venue = COALESCE($5, extracted_venue),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $6
                    """,
                    paper_id,
                    title,
                    json.dumps(authors) if authors else None,
                    year,
                    venue,
                    citation_id,
                )

                logger.debug(
                    f'Updated citation {citation_id} with paper {paper_id} (DOI: {doi})'
                )
        finally:
            await conn.close()

    async def process_citation_batch(
        self,
        citations: list[dict[str, Any]],
    ) -> None:
        """Process a batch of citations through the resolution chain."""
        logger.info(f'Processing batch of {len(citations)} citations...')

        for citation_record in citations:
            try:
                self.stats.processed += 1
                citation_id = citation_record['id']

                # Skip if cited paper already has DOI
                if citation_record['cited_paper_doi']:
                    self.stats.skipped += 1
                    logger.debug(
                        f'Citation {citation_id} already has DOI: {citation_record["cited_paper_doi"]}'
                    )
                    continue

                # Create Citation object from extracted metadata
                # Parse authors from JSON string if needed
                authors = citation_record['extracted_authors']
                if authors and isinstance(authors, str):
                    try:
                        authors = json.loads(authors)
                    except json.JSONDecodeError:
                        logger.warning(
                            f'Failed to parse authors JSON for citation {citation_id}: {authors}'
                        )
                        authors = []
                elif not authors:
                    authors = []

                citation = Citation(
                    text=citation_record['citation_text'],
                    title=citation_record['extracted_title'],
                    authors=authors,
                    year=citation_record['extracted_year'],
                    venue=citation_record['extracted_venue'],
                )

                logger.debug(f'Resolving citation {citation_id}: "{citation.title}"')

                # Run resolution chain
                result = await self.resolution_chain.resolve(citation)

                # Update statistics
                if result.status.value == 'resolved':
                    self.stats.resolved += 1
                elif result.status.value == 'partial':
                    self.stats.partial += 1
                elif result.status.value == 'manual_review':
                    self.stats.manual_review += 1
                elif result.status.value == 'unresolved':
                    self.stats.unresolved += 1

                # Handle resolved citations
                if result.matched_data:
                    doi = result.matched_data.get('doi')
                    arxiv_id = result.matched_data.get('arxiv_id')

                    # Strip URL prefix from DOI if present
                    if doi:
                        if doi.startswith('https://doi.org/'):
                            doi = doi.replace('https://doi.org/', '')
                        elif doi.startswith('http://dx.doi.org/'):
                            doi = doi.replace('http://dx.doi.org/', '')

                    # Enrich from DOI if available
                    if doi:
                        enriched = await self.enrichment_service.enrich_from_doi(
                            citation,
                            doi,
                        )
                    else:
                        # Use matched data directly if no DOI (e.g., arXiv-only matches)
                        enriched = citation

                    # Update database with matched data
                    await self.update_citation_resolution(
                        citation_id=citation_id,
                        doi=doi,
                        title=result.matched_data.get('title') or enriched.title,
                        authors=result.matched_data.get('authors') or enriched.authors,
                        year=result.matched_data.get('year') or enriched.year,
                        venue=result.matched_data.get('venue')
                        or result.matched_data.get('journal')
                        or enriched.venue
                        or enriched.journal,
                        abstract=result.matched_data.get('abstract')
                        or enriched.abstract,
                    )

                    identifier = (
                        doi or f'arxiv:{arxiv_id}' if arxiv_id else 'metadata-only'
                    )
                    logger.info(
                        f'Citation {citation_id} resolved: {identifier}, confidence={result.confidence_score:.3f}'
                    )
                else:
                    logger.info(
                        f'Citation {citation_id} could not be resolved: status={result.status.value}, confidence={result.confidence_score:.3f}'
                    )

                # Log progress every 10 citations
                if self.stats.processed % 10 == 0:
                    logger.info(self.stats)

            except Exception as e:
                self.stats.failed += 1
                logger.error(
                    f'Error processing citation {citation_record["id"]}: {e}',
                    exc_info=True,
                )

    def save_checkpoint(self, offset: int) -> None:
        """Save checkpoint for resume capability."""
        checkpoint_file = (
            self.checkpoint_dir
            / f'checkpoint_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        checkpoint_data = {
            'offset': offset,
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats.to_dict(),
        }

        with checkpoint_file.open('w') as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.info(f'Checkpoint saved: {checkpoint_file}')

    def load_latest_checkpoint(self) -> int:
        """Load the most recent checkpoint and return offset."""
        checkpoints = sorted(self.checkpoint_dir.glob('checkpoint_*.json'))
        if not checkpoints:
            logger.info('No checkpoints found, starting from beginning')
            return 0

        latest = checkpoints[-1]
        with latest.open() as f:
            data = json.load(f)

        offset = data['offset']
        logger.info(f'Resuming from checkpoint: {latest} (offset={offset})')
        return offset

    async def run_backfill(
        self,
        limit: int | None = None,
        resume: bool = False,
        batch_size: int = 100,
    ) -> None:
        """Run the full backfill process."""
        logger.info('=' * 80)
        logger.info('Starting Citation Resolution Backfill')
        logger.info(f'Dry run: {self.dry_run}')
        logger.info(f'Batch size: {batch_size}')
        logger.info(f'Limit: {limit or "unlimited"}')
        logger.info('=' * 80)

        # Determine starting offset
        offset = self.load_latest_checkpoint() if resume else 0

        # Fetch total count
        conn = await asyncpg.connect(self.db_url)
        try:
            total = await conn.fetchval(
                'SELECT COUNT(*) FROM citations WHERE extracted_title IS NOT NULL'
            )
            self.stats.total_citations = total
            logger.info(f'Total citations to process: {total}')
        finally:
            await conn.close()

        # Process in batches
        while True:
            # Fetch batch
            citations = await self.fetch_citations_to_backfill(
                limit=min(batch_size, limit - offset) if limit else batch_size,
                offset=offset,
            )

            if not citations:
                logger.info('No more citations to process')
                break

            # Process batch
            await self.process_citation_batch(citations)

            # Update offset and save checkpoint
            offset += len(citations)
            self.save_checkpoint(offset)

            # Check if we've reached the limit
            if limit and offset >= limit:
                logger.info(f'Reached limit of {limit} citations')
                break

        # Final statistics
        logger.info('=' * 80)
        logger.info('Backfill Complete!')
        logger.info(self.stats)
        logger.info('=' * 80)

        # Save final report
        report_file = (
            self.checkpoint_dir
            / f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        with report_file.open('w') as f:
            json.dump(self.stats.to_dict(), f, indent=2)
        logger.info(f'Final report saved: {report_file}')


async def main():
    """Main entry point for backfill script."""
    parser = argparse.ArgumentParser(
        description='Backfill citation resolution using improved resolution system'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of citations to process (default: all)',
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last checkpoint',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test run without updating database',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of citations per batch (default: 100)',
    )

    args = parser.parse_args()

    # Initialize
    config = Config()
    manager = CitationBackfillManager(config, dry_run=args.dry_run)

    # Run backfill
    try:
        await manager.run_backfill(
            limit=args.limit,
            resume=args.resume,
            batch_size=args.batch_size,
        )
    except KeyboardInterrupt:
        logger.warning('Backfill interrupted by user')
        logger.info(manager.stats)
    except Exception as e:
        logger.error(f'Backfill failed: {e}', exc_info=True)
        raise


if __name__ == '__main__':
    asyncio.run(main())

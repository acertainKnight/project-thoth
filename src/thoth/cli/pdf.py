"""
CLI commands for PDF management.

This module provides commands for locating and managing PDFs.
"""

from loguru import logger

from thoth.pipeline import ThothPipeline
from thoth.services import ServiceManager


def run_locate_pdf(args, pipeline: ThothPipeline):  # noqa: ARG001
    """
    Locate open-access PDFs for articles.
    """
    service_manager = ServiceManager()
    pdf_locator = service_manager.get_service('pdf_locator')

    if args.all:
        # Process all articles missing PDFs
        logger.info('Locating PDFs for all articles...')
        _process_all_articles(pdf_locator, args.update_existing, args.dry_run)
    elif args.doi or args.arxiv_id:
        # Process single article
        logger.info(f'Locating PDF for DOI: {args.doi}, arXiv: {args.arxiv_id}')
        location = pdf_locator.locate(doi=args.doi, arxiv_id=args.arxiv_id)

        if location:
            logger.info('✓ PDF found!')
            logger.info(f'  URL: {location.url}')
            logger.info(f'  Source: {location.source}')
            logger.info(f'  License: {location.licence or "Unknown"}')
            logger.info(f'  Open Access: {"Yes" if location.is_oa else "No"}')
            return 0
        else:
            logger.error('✗ No PDF found')
            return 1
    else:
        logger.error('Provide either a DOI, arXiv ID, or use --all')
        return 1


def run_pdf_stats(args, pipeline: ThothPipeline):  # noqa: ARG001
    """
    Show statistics about PDF availability.
    """
    # TODO: Implement statistics gathering from database
    logger.warning('PDF statistics not yet implemented')
    logger.info('This will show:')
    logger.info('- Total articles with/without PDFs')
    logger.info('- Breakdown by source (Crossref, Unpaywall, arXiv, etc.)')
    logger.info('- License distribution')
    logger.info('- Open Access percentage')
    return 0


def run_test_source(args, pipeline: ThothPipeline):  # noqa: ARG001
    """
    Test PDF location sources.
    """
    service_manager = ServiceManager()
    pdf_locator = service_manager.get_service('pdf_locator')

    # Test DOIs for different sources
    test_dois = {
        'crossref': '10.1038/nature12373',  # Nature article
        'unpaywall': '10.1371/journal.pone.0213692',  # PLOS ONE
        'arxiv': '10.48550/arXiv.1706.03762',  # Attention is All You Need
        's2': '10.18653/v1/D15-1166',  # ACL paper
    }

    if args.doi:
        test_dois = {args.source: args.doi}
    elif args.source != 'all':
        test_dois = {args.source: test_dois.get(args.source, test_dois['crossref'])}

    logger.info(f'Testing PDF location source(s): {args.source}')

    for test_source, test_doi in test_dois.items():
        if args.source != 'all' and test_source != args.source:
            continue

        logger.info(f'\nTesting {test_source}...')

        # Temporarily disable other sources to test specific one
        result = None
        if test_source == 'crossref':
            result = pdf_locator._from_crossref(test_doi)
        elif test_source == 'unpaywall':
            result = pdf_locator._from_unpaywall(test_doi)
        elif test_source == 'arxiv':
            result = pdf_locator._from_arxiv(test_doi, None)
        elif test_source == 's2':
            result = pdf_locator._from_semanticscholar(test_doi)

        if result:
            logger.info(f'  ✓ Found - {result.url}')
        else:
            logger.warning('  ✗ Not found')

    return 0


def _process_all_articles(
    pdf_locator,  # noqa: ARG001
    update_existing: bool,  # noqa: ARG001
    dry_run: bool,  # noqa: ARG001
):
    """Process all articles to locate PDFs."""
    # TODO: Implement database query to get articles
    logger.warning('Batch processing not yet implemented')
    logger.info('This will:')
    logger.info('1. Query all articles from the database')
    logger.info('2. Filter those without pdf_url (or all if --update-existing)')
    logger.info('3. Attempt to locate PDFs for each')
    logger.info('4. Update the database with results')


def configure_subparser(subparsers):
    """Configure the subparser for PDF-related commands."""

    # PDF locate command
    locate_parser = subparsers.add_parser(
        'pdf-locate', help='Locate open-access PDFs for articles'
    )
    locate_parser.add_argument('doi', nargs='?', help='DOI to locate PDF for')
    locate_parser.add_argument('--arxiv-id', help='arXiv identifier')
    locate_parser.add_argument(
        '--all', action='store_true', help='Process all articles missing PDFs'
    )
    locate_parser.add_argument(
        '--update-existing',
        action='store_true',
        help='Re-locate PDFs even if URL exists',
    )
    locate_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes',
    )
    locate_parser.set_defaults(func=run_locate_pdf)

    # PDF stats command
    stats_parser = subparsers.add_parser(
        'pdf-stats', help='Show statistics about PDF availability'
    )
    stats_parser.set_defaults(func=run_pdf_stats)

    # PDF test command
    test_parser = subparsers.add_parser('pdf-test', help='Test PDF location sources')
    test_parser.add_argument(
        'source',
        choices=['crossref', 'unpaywall', 'arxiv', 's2', 'all'],
        help='Source to test',
    )
    test_parser.add_argument('--doi', help='Test with specific DOI')
    test_parser.set_defaults(func=run_test_source)

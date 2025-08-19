import threading
import warnings
from pathlib import Path

from loguru import logger

from thoth.pipeline import ThothPipeline
from thoth.server.app import start_obsidian_server
from thoth.server.pdf_monitor import PDFMonitor
from thoth.utilities.config import get_config

# Optional optimized pipeline import
try:
    from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline
    from thoth.services.service_manager import ServiceManager

    OPTIMIZED_PIPELINE_AVAILABLE = True
except ImportError:
    OPTIMIZED_PIPELINE_AVAILABLE = False


def run_monitor(args, pipeline: ThothPipeline):
    """
    Run the PDF monitor with optional performance optimizations.
    """
    config = get_config()
    watch_dir = Path(args.watch_dir) if args.watch_dir else config.pdf_dir
    watch_dir.mkdir(parents=True, exist_ok=True)

    # Use optimized pipeline if available and requested
    monitor_pipeline = pipeline
    if args.optimized and OPTIMIZED_PIPELINE_AVAILABLE:
        logger.info('Initializing optimized pipeline for monitor')
        service_manager = ServiceManager(config)
        service_manager.initialize()

        monitor_pipeline = OptimizedDocumentPipeline(
            services=service_manager,
            citation_tracker=pipeline.citation_tracker,
            pdf_tracker=pipeline.pdf_tracker,
            output_dir=config.output_dir,
            notes_dir=config.notes_dir,
            markdown_dir=config.markdown_dir,
        )
        logger.info('✅ Monitor using optimized processing pipeline')
    elif args.optimized and not OPTIMIZED_PIPELINE_AVAILABLE:
        logger.warning(
            'Optimized pipeline requested but not available, using standard pipeline'
        )
    else:
        # Issue deprecation warning for non-optimized usage
        warnings.warn(
            'Using standard pipeline without --optimized flag. '
            "For better performance, consider using 'thoth monitor --optimized' "
            'which provides 50-65% faster processing with async I/O and intelligent caching.',
            DeprecationWarning,
            stacklevel=2,
        )
        logger.info('Monitor using standard processing pipeline')

    if args.api_server or config.api_server_config.auto_start:
        api_host = args.api_host or config.api_server_config.host
        api_port = args.api_port or config.api_server_config.port
        api_base_url = args.api_base_url or config.api_server_config.base_url

        api_thread = threading.Thread(
            target=start_obsidian_server,
            kwargs={
                'host': api_host,
                'port': api_port,
                'pdf_directory': Path(config.pdf_dir),
                'notes_directory': Path(config.notes_dir),
                'api_base_url': api_base_url,
                'pipeline': pipeline,
            },
            daemon=True,
        )
        logger.info(f'Starting Obsidian API server on {api_host}:{api_port}')
        api_thread.start()

    monitor = PDFMonitor(
        watch_dir=watch_dir,
        pipeline=monitor_pipeline,  # Use the selected pipeline (optimized or standard)
        polling_interval=args.polling_interval,
        recursive=args.recursive,
    )
    try:
        logger.info(
            f'Starting PDF monitor with polling interval {args.polling_interval}s '
            f'(recursive: {args.recursive})'
        )
        monitor.start()
    except KeyboardInterrupt:
        logger.info('Monitor stopped by user')
        monitor.stop()
    except Exception as e:
        logger.error(f'Error in PDF monitor: {e}')
        return 1
    return 0


def process_pdf(args, pipeline: ThothPipeline):
    """
    Process a single PDF file.
    """
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        logger.error(f'PDF file does not exist: {pdf_path}')
        return 1

    # Issue deprecation warning for direct PDF processing
    warnings.warn(
        "Direct PDF processing through 'thoth process' uses the standard pipeline. "
        'For better performance, consider using the performance CLI: '
        "'thoth performance batch --input /path/to/pdf --optimized' "
        'which provides 50-65% faster processing with async I/O and intelligent caching.',
        DeprecationWarning,
        stacklevel=2,
    )

    note_path, _, _ = pipeline.process_pdf(pdf_path)
    logger.info(f'Successfully processed: {pdf_path} -> {note_path}')


def run_api_server(args, pipeline: ThothPipeline):
    """
    Run the Obsidian API server.
    """
    config = get_config()
    host = args.host or config.api_server_config.host
    port = args.port or config.api_server_config.port
    base_url = args.base_url or config.api_server_config.base_url
    reload = getattr(args, 'reload', False)

    try:
        logger.info(
            f'Starting Obsidian API server on {host}:{port} with auto-reload={reload}'
        )
        start_obsidian_server(
            host=host,
            port=port,
            pipeline=pipeline,
            pdf_directory=config.pdf_dir,
            notes_directory=config.notes_dir,
            api_base_url=base_url,
            reload=reload,
        )
        return 0
    except Exception as e:
        logger.error(f'Error in API server: {e}')
        return 1


def run_scrape_filter_test(args, pipeline: ThothPipeline):
    """
    Test the filter with sample articles.
    """
    from thoth.utilities.schemas import ResearchQuery, ScrapedArticleMetadata

    logger.info('Testing filter functionality.')

    if args.create_sample_queries:
        sample_queries = [
            ResearchQuery(
                name='machine_learning',
                description='Machine learning and AI research',
                research_question='What are the latest developments in machine learning?',
                keywords=[
                    'machine learning',
                    'artificial intelligence',
                    'neural networks',
                ],
            ),
            ResearchQuery(
                name='nlp_research',
                description='Natural language processing research',
                research_question='How are transformer models being applied to NLP tasks?',
                keywords=['natural language processing', 'transformer', 'BERT', 'GPT'],
            ),
        ]
        for query in sample_queries:
            pipeline.services.query.create_query(query)
            logger.info(f'Created sample query: {query.name}')

    sample_articles = [
        ScrapedArticleMetadata(
            title='Attention Is All You Need',
            authors=['Vaswani, A.', 'Shazeer, N.', 'Parmar, N.'],
            abstract='We propose a new simple network architecture...',
            journal='NIPS',
            source='test',
        ),
        ScrapedArticleMetadata(
            title='BERT: Pre-training of Deep Bidirectional Transformers',
            authors=['Devlin, J.', 'Chang, M.', 'Lee, K.'],
            abstract='We introduce BERT, a new language representation model.',
            journal='NAACL',
            source='test',
        ),
    ]

    logger.info('Testing filter with sample articles...')
    for article in sample_articles:
        result = pipeline.filter.process_article(
            metadata=article,
            download_pdf=False,
        )
        logger.info(f'Article: {article.title}')
        logger.info(f'Decision: {result["decision"]}')
        logger.info(f'Score: {result["evaluation"].relevance_score:.2f}')
        logger.info(f'Reasoning: {result["evaluation"].reasoning}')
        logger.info('---')

    logger.info('Filter test completed successfully.')
    return 0


def configure_subparser(subparsers):
    """Configure the subparser for system commands."""
    monitor_parser = subparsers.add_parser('monitor', help='Run the PDF monitor')
    monitor_parser.add_argument(
        '--watch-dir',
        type=str,
        help='Directory to watch for PDF files. Defaults to config value.',
    )
    monitor_parser.add_argument(
        '--polling-interval',
        type=float,
        default=1.0,
        help='Interval in seconds for polling the directory. Default: 1.0',
    )
    monitor_parser.add_argument(
        '--recursive',
        action='store_true',
        help='Watch directory recursively. Default: False',
    )
    monitor_parser.add_argument(
        '--api-server',
        action='store_true',
        help='Start the Obsidian API server alongside the monitor.',
    )
    monitor_parser.add_argument('--api-host', type=str, help='Host for the API server.')
    monitor_parser.add_argument('--api-port', type=int, help='Port for the API server.')
    monitor_parser.add_argument(
        '--api-base-url', type=str, help='Base URL for the API server.'
    )
    monitor_parser.add_argument(
        '--optimized',
        action='store_true',
        help='Use optimized processing pipeline for better performance',
    )
    monitor_parser.set_defaults(func=run_monitor)

    process_parser = subparsers.add_parser('process', help='Process a PDF file')
    process_parser.add_argument(
        '--pdf-path', type=str, required=True, help='Path to the PDF file to process'
    )
    process_parser.set_defaults(func=process_pdf)

    api_parser = subparsers.add_parser('api', help='Run the Obsidian API server')
    api_parser.add_argument('--host', type=str, help='Host for the API server.')
    api_parser.add_argument('--port', type=int, help='Port for the API server.')
    api_parser.add_argument('--base-url', type=str, help='Base URL for the API server.')
    api_parser.add_argument(
        '--reload', action='store_true', help='Enable auto-reload for development.'
    )
    api_parser.set_defaults(func=run_api_server)

    filter_test_parser = subparsers.add_parser(
        'filter-test', help='Test the filter with sample articles'
    )
    filter_test_parser.add_argument(
        '--create-sample-queries',
        action='store_true',
        help='Create sample research queries for testing',
    )
    filter_test_parser.set_defaults(func=run_scrape_filter_test)

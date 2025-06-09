import threading
from pathlib import Path

from loguru import logger

from thoth.pipeline import ThothPipeline
from thoth.server.api_server import start_server as start_obsidian_server
from thoth.server.pdf_monitor import PDFMonitor
from thoth.utilities.config import get_config


def run_monitor(args, pipeline: ThothPipeline):
    """
    Run the PDF monitor.
    """
    config = get_config()
    watch_dir = Path(args.watch_dir) if args.watch_dir else config.pdf_dir
    watch_dir.mkdir(parents=True, exist_ok=True)

    if args.api_server or config.api_server_config.auto_start:
        api_host = args.api_host or config.api_server_config.host
        api_port = args.api_port or config.api_server_config.port
        api_base_url = args.api_base_url or config.api_server_config.base_url

        api_thread = threading.Thread(
            target=start_obsidian_server,
            args=(api_host, api_port, config.pdf_dir, config.notes_dir, api_base_url),
            daemon=True,
        )
        logger.info(f'Starting Obsidian API server on {api_host}:{api_port}')
        api_thread.start()

    monitor = PDFMonitor(
        watch_dir=watch_dir,
        pipeline=pipeline,
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

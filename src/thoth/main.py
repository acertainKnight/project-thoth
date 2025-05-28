#!/usr/bin/env python3
"""
Main entry point for Thoth.

This module provides a command-line interface for running the Thoth system.
"""

import argparse
import sys
import threading
import time
from pathlib import Path

from loguru import logger

from thoth.monitor.obsidian import start_server as start_obsidian_server
from thoth.monitor.pdf_monitor import PDFMonitor, PDFTracker
from thoth.pipeline import ThothPipeline
from thoth.utilities.config import get_config


def parse_args():
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description='Thoth - Academic PDF processing system'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Monitor command
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
        '--track-file',
        type=str,
        help="Path to the file tracking database. Defaults to 'processed_pdfs.json' in the output directory.",
    )
    monitor_parser.add_argument(
        '--api-server',
        action='store_true',
        help='Start the Obsidian API server alongside the monitor. Default: False',
    )
    monitor_parser.add_argument(
        '--api-host', type=str, help='Host for the API server. Overrides config value.'
    )
    monitor_parser.add_argument(
        '--api-port', type=int, help='Port for the API server. Overrides config value.'
    )
    monitor_parser.add_argument(
        '--api-base-url',
        type=str,
        help='Base URL for the API server. Overrides config value.',
    )

    # Process command
    process_parser = subparsers.add_parser('process', help='Process a PDF file')
    process_parser.add_argument(
        '--pdf-path', type=str, help='Path to the PDF file to process'
    )

    # API server command
    api_parser = subparsers.add_parser('api', help='Run the Obsidian API server')
    api_parser.add_argument(
        '--host', type=str, help='Host for the API server. Overrides config value.'
    )
    api_parser.add_argument(
        '--port', type=int, help='Port for the API server. Overrides config value.'
    )
    api_parser.add_argument(
        '--base-url',
        type=str,
        help='Base URL for the API server. Overrides config value.',
    )

    # Reprocess-note command
    reprocess_parser = subparsers.add_parser(
        'reprocess-note',
        help='Regenerate the note for an existing article in the graph',
    )
    reprocess_parser.add_argument(
        '--article-id',
        type=str,
        required=True,
        help='The unique ID of the article (e.g., DOI) whose note needs to be reprocessed.',
    )

    # Regenerate all notes command
    regenerate_all_parser = subparsers.add_parser(  # noqa: F841
        'regenerate-all-notes',
        help='Regenerate all markdown notes for all articles in the graph.',
    )

    # Consolidate tags command
    consolidate_tags_parser = subparsers.add_parser(  # noqa: F841
        'consolidate-tags',
        help='Consolidate existing tags and suggest additional relevant tags for all articles in the graph.',
    )

    # Consolidate tags only command (new)
    consolidate_tags_only_parser = subparsers.add_parser(  # noqa: F841
        'consolidate-tags-only',
        help='Consolidate existing tags without suggesting additional tags.',
    )

    # Suggest tags command (new)
    suggest_tags_parser = subparsers.add_parser(  # noqa: F841
        'suggest-tags',
        help='Suggest additional relevant tags for all articles using existing tag vocabulary.',
    )

    # Scrape filter command
    scrape_filter_parser = subparsers.add_parser(
        'scrape-filter',
        help='Test the scrape filter with sample articles',
    )
    scrape_filter_parser.add_argument(
        '--create-sample-queries',
        action='store_true',
        help='Create sample research queries for testing',
    )

    # Agent command
    agent_parser = subparsers.add_parser(  # noqa: F841
        'agent', help='Start an interactive chat with the research assistant agent'
    )

    # Discovery commands
    discovery_parser = subparsers.add_parser(
        'discovery',
        help='Manage article discovery sources and scheduling',
    )
    discovery_subparsers = discovery_parser.add_subparsers(
        dest='discovery_command', help='Discovery command to run'
    )

    # Discovery run command
    discovery_run_parser = discovery_subparsers.add_parser(
        'run', help='Run discovery for sources'
    )
    discovery_run_parser.add_argument(
        '--source',
        type=str,
        help='Specific source to run (runs all active if not specified)',
    )
    discovery_run_parser.add_argument(
        '--max-articles', type=int, help='Maximum articles to process'
    )

    # Discovery list command
    discovery_list_parser = discovery_subparsers.add_parser(  # noqa: F841
        'list', help='List all discovery sources'
    )

    # Discovery show command
    discovery_show_parser = discovery_subparsers.add_parser(
        'show', help='Show detailed information about a discovery source'
    )
    discovery_show_parser.add_argument(
        '--name', type=str, required=True, help='Name of the discovery source to show'
    )

    # Discovery create command
    discovery_create_parser = discovery_subparsers.add_parser(
        'create', help='Create a new discovery source'
    )
    discovery_create_parser.add_argument(
        '--name', type=str, required=True, help='Name for the discovery source'
    )
    discovery_create_parser.add_argument(
        '--type',
        type=str,
        choices=['api', 'scraper'],
        required=True,
        help='Type of source',
    )
    discovery_create_parser.add_argument(
        '--description', type=str, required=True, help='Description of the source'
    )
    discovery_create_parser.add_argument(
        '--config-file', type=str, help='JSON file containing source configuration'
    )

    # Discovery edit command
    discovery_edit_parser = discovery_subparsers.add_parser(
        'edit', help='Edit an existing discovery source'
    )
    discovery_edit_parser.add_argument(
        '--name', type=str, required=True, help='Name of the discovery source to edit'
    )
    discovery_edit_parser.add_argument(
        '--description', type=str, help='New description for the source'
    )
    discovery_edit_parser.add_argument(
        '--config-file',
        type=str,
        help='JSON file containing updated source configuration',
    )
    discovery_edit_parser.add_argument(
        '--active', type=str, choices=['true', 'false'], help='Set source active status'
    )

    # Discovery delete command
    discovery_delete_parser = discovery_subparsers.add_parser(
        'delete', help='Delete a discovery source'
    )
    discovery_delete_parser.add_argument(
        '--name', type=str, required=True, help='Name of the discovery source to delete'
    )
    discovery_delete_parser.add_argument(
        '--confirm', action='store_true', help='Confirm deletion without prompting'
    )

    # Discovery scheduler commands
    scheduler_parser = discovery_subparsers.add_parser(
        'scheduler', help='Manage discovery scheduler'
    )
    scheduler_subparsers = scheduler_parser.add_subparsers(
        dest='scheduler_command', help='Scheduler command to run'
    )

    # Scheduler start command
    scheduler_start_parser = scheduler_subparsers.add_parser(  # noqa: F841
        'start', help='Start the discovery scheduler'
    )

    # Scheduler stop command
    scheduler_stop_parser = scheduler_subparsers.add_parser(  # noqa: F841
        'stop', help='Stop the discovery scheduler'
    )

    # Scheduler status command
    scheduler_status_parser = scheduler_subparsers.add_parser(  # noqa: F841
        'status', help='Show scheduler status'
    )

    return parser.parse_args()


def run_monitor(args):
    """
    Run the PDF monitor.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    config = get_config()

    # Set up watch directory
    watch_dir = None
    if args.watch_dir:
        watch_dir = Path(args.watch_dir)
        logger.info(f'Using custom watch directory: {watch_dir}')
    else:
        watch_dir = config.pdf_dir
        logger.info(f'Using configured watch directory: {watch_dir}')

    # Ensure directory exists
    watch_dir.mkdir(parents=True, exist_ok=True)

    # Set up tracking file path if provided
    track_file = None
    if args.track_file:
        track_file = Path(args.track_file)
        logger.info(f'Using custom tracking file: {track_file}')

    # Start API server if requested or configured to auto-start
    start_api = args.api_server or config.api_server_config.auto_start
    if start_api:
        # Use command line args if provided, otherwise use config values
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

    # Set up and start monitor
    monitor = PDFMonitor(
        watch_dir=watch_dir,
        polling_interval=args.polling_interval,
        recursive=args.recursive,
        track_file=track_file,
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


def process_pdf(args):
    """
    Process a single PDF file.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    config = get_config()  # noqa: F841

    pdf_path = Path(args.pdf_path)

    # Check if file exists
    if not pdf_path.exists():
        logger.error(f'PDF file does not exist: {pdf_path}')
        return 1

    # Initialize pipeline
    pipeline = ThothPipeline()

    # Process the PDF
    note_path = pipeline.process_pdf(pdf_path)
    logger.info(f'Successfully processed: {pdf_path} -> {note_path}')


def run_reprocess_note(args):
    """
    Regenerate the note for an existing article.

    Args:
        args: Command line arguments containing 'article_id'.

    Returns:
        int: Exit code.
    """
    logger.info(f'Attempting to reprocess note for article_id: {args.article_id}')
    config = get_config()  # Ensure config is loaded if needed by pipeline components

    # Initialize pipeline
    # We need to pass the API base URL to ThothPipeline if it's used by NoteGenerator for links,  # noqa: W505
    # or ensure NoteGenerator can get it from config/env itself.
    # Assuming ThothPipeline and its components handle their config/env loading.
    pipeline = ThothPipeline(
        ocr_api_key=config.api_keys.mistral_key,
        llm_api_key=config.api_keys.openrouter_key,
        templates_dir=Path(config.templates_dir),
        prompts_dir=Path(config.prompts_dir),
        output_dir=Path(config.output_dir),
        notes_dir=Path(config.notes_dir),
        api_base_url=config.api_server_config.base_url,
    )

    article_id = args.article_id

    # Fetch data for regeneration from CitationTracker
    regen_data = pipeline.citation_tracker.get_article_data_for_regeneration(article_id)

    if not regen_data:
        logger.error(
            f"Could not retrieve data for article_id '{article_id}'. "
            'Ensure the article exists in the graph and has all necessary data (PDF path, Markdown path, analysis).'
        )
        return 1

    try:
        logger.info(f'Regenerating note for {article_id}...')
        # create_note returns (note_path_str, new_pdf_path, new_markdown_path)
        note_path, new_pdf_path, new_markdown_path = (
            pipeline.note_generator.create_note(
                pdf_path=regen_data['pdf_path'],
                markdown_path=regen_data['markdown_path'],
                analysis=regen_data['analysis'],
                citations=regen_data['citations'],
            )
        )
        logger.info(f'Successfully regenerated note for {article_id} at: {note_path}')
        logger.info(f'Associated PDF path: {new_pdf_path}')
        logger.info(f'Associated Markdown path: {new_markdown_path}')

        # Update the file paths in the tracker if they were changed by create_note
        # This is important if the original file paths in the graph were different from what create_note produced  # noqa: W505
        # (e.g., if a file was manually moved or if the title changed, leading to a new sanitized name)  # noqa: W505
        pipeline.citation_tracker.update_article_file_paths(
            article_id=article_id,
            new_pdf_path=new_pdf_path,
            new_markdown_path=new_markdown_path,
        )
        logger.info(f'Updated file paths in tracker for {article_id} if changed.')

        return 0
    except Exception as e:
        logger.error(
            f"Error during note reprocessing for article_id '{article_id}': {e}"
        )
        return 1


def run_regenerate_all_notes(args):  # noqa: ARG001
    """
    Regenerate all notes for all articles in the citation graph
    and update the processed files database.

    Args:
        args: Command line arguments (not used in this function but part of the
            pattern).

    Returns:
        int: Exit code.
    """
    logger.info('Attempting to regenerate all notes for all articles.')
    config = get_config()

    try:
        pipeline = ThothPipeline(
            ocr_api_key=config.api_keys.mistral_key,
            llm_api_key=config.api_keys.openrouter_key,
            templates_dir=Path(config.templates_dir),
            prompts_dir=Path(config.prompts_dir),
            output_dir=Path(config.output_dir),
            notes_dir=Path(config.notes_dir),
            api_base_url=config.api_server_config.base_url,
        )
        successfully_regenerated_files = pipeline.regenerate_all_notes()
        logger.info(
            f'Regeneration process completed. {len(successfully_regenerated_files)} notes reported as successfully regenerated.'
        )

        if successfully_regenerated_files:
            processed_db_filename = getattr(
                config, 'processed_pdfs_file', 'processed_pdfs.json'
            )
            processed_db_json_path = Path(config.output_dir) / processed_db_filename

            # Use PDFTracker to interact with the processed files database
            pdf_tracker = PDFTracker(track_file=processed_db_json_path)
            logger.info(
                f'Updating processed files database at: {processed_db_json_path}'
            )

            for final_pdf_path, final_note_path in successfully_regenerated_files:
                if not final_pdf_path.exists():
                    logger.warning(
                        f'Regenerated PDF path {final_pdf_path} does not exist. Cannot update tracking for it.'
                    )
                    continue
                try:
                    # PDFTracker's mark_processed method handles getting stats and saving  # noqa: W505
                    pdf_tracker.mark_processed(
                        final_pdf_path,
                        metadata={'note_path': str(final_note_path)},
                    )
                    logger.info(
                        f'Updated tracking for regenerated file: {final_pdf_path} -> {final_note_path}'
                    )
                except Exception as e:
                    logger.error(f'Error updating tracking for {final_pdf_path}: {e}')

        return 0
    except Exception as e:
        logger.error(f'Error during overall regeneration of all notes: {e}')
        return 1


def run_api_server(args):
    """
    Run the Obsidian API server.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    config = get_config()

    # Use command line args if provided, otherwise use config values
    host = args.host or config.api_server_config.host
    port = args.port or config.api_server_config.port
    base_url = args.base_url or config.api_server_config.base_url

    try:
        logger.info(f'Starting Obsidian API server on {host}:{port}')
        start_obsidian_server(
            host=host,
            port=port,
            pdf_directory=config.pdf_dir,
            notes_directory=config.notes_dir,
            api_base_url=base_url,
        )
        return 0
    except Exception as e:
        logger.error(f'Error in API server: {e}')
        return 1


def run_consolidate_tags(args):  # noqa: ARG001
    """
    Consolidate existing tags and suggest additional relevant tags for all articles.

    This function performs a complete tag consolidation and re-tagging process
    across all articles in the citation graph.

    Args:
        args: Command line arguments (not used in this function but part of the
            pattern).

    Returns:
        int: Exit code.
    """
    logger.info('Attempting to consolidate tags and retag all articles.')
    config = get_config()

    try:
        pipeline = ThothPipeline(
            ocr_api_key=config.api_keys.mistral_key,
            llm_api_key=config.api_keys.openrouter_key,
            templates_dir=Path(config.templates_dir),
            prompts_dir=Path(config.prompts_dir),
            output_dir=Path(config.output_dir),
            notes_dir=Path(config.notes_dir),
            api_base_url=config.api_server_config.base_url,
        )

        stats = pipeline.consolidate_and_retag_all_articles()

        logger.info('Tag consolidation and re-tagging process completed successfully.')
        logger.info('Summary statistics:')
        logger.info(f'  - Articles processed: {stats["articles_processed"]}')
        logger.info(f'  - Articles updated: {stats["articles_updated"]}')
        logger.info(f'  - Tags consolidated: {stats["tags_consolidated"]}')
        logger.info(f'  - Tags added: {stats["tags_added"]}')
        logger.info(f'  - Original tag count: {stats["original_tag_count"]}')
        logger.info(f'  - Final tag count: {stats["final_tag_count"]}')
        logger.info(f'  - Total vocabulary size: {stats["total_vocabulary_size"]}')

        if stats['consolidation_mappings']:
            logger.info('Tag consolidation mappings:')
            for old_tag, new_tag in stats['consolidation_mappings'].items():
                if old_tag != new_tag:  # Only show actual changes
                    logger.info(f'  {old_tag} -> {new_tag}')

        logger.info(
            f'All available tags in vocabulary ({len(stats["all_available_tags"])}):'
        )
        for tag in sorted(stats['all_available_tags']):
            logger.info(f'  {tag}')

        return 0
    except Exception as e:
        logger.error(f'Error during tag consolidation and re-tagging: {e}')
        return 1


def run_consolidate_tags_only(args):  # noqa: ARG001
    """
    Consolidate existing tags without suggesting additional tags.

    This function performs only the tag consolidation process across all articles
    in the citation graph, updating existing tags to their canonical forms.

    Args:
        args: Command line arguments (not used in this function but part of the
            pattern).

    Returns:
        int: Exit code.
    """
    logger.info('Attempting to consolidate existing tags only.')
    config = get_config()

    try:
        pipeline = ThothPipeline(
            ocr_api_key=config.api_keys.mistral_key,
            llm_api_key=config.api_keys.openrouter_key,
            templates_dir=Path(config.templates_dir),
            prompts_dir=Path(config.prompts_dir),
            output_dir=Path(config.output_dir),
            notes_dir=Path(config.notes_dir),
            api_base_url=config.api_server_config.base_url,
        )

        stats = pipeline.consolidate_tags_only()

        logger.info('Tag consolidation process completed successfully.')
        logger.info('Summary statistics:')
        logger.info(f'  - Articles processed: {stats["articles_processed"]}')
        logger.info(f'  - Articles updated: {stats["articles_updated"]}')
        logger.info(f'  - Tags consolidated: {stats["tags_consolidated"]}')
        logger.info(f'  - Original tag count: {stats["original_tag_count"]}')
        logger.info(f'  - Final tag count: {stats["final_tag_count"]}')
        logger.info(f'  - Total vocabulary size: {stats["total_vocabulary_size"]}')

        if stats['consolidation_mappings']:
            logger.info('Tag consolidation mappings:')
            for old_tag, new_tag in stats['consolidation_mappings'].items():
                if old_tag != new_tag:  # Only show actual changes
                    logger.info(f'  {old_tag} -> {new_tag}')

        logger.info(
            f'All available tags in vocabulary ({len(stats["all_available_tags"])}):'
        )
        for tag in sorted(stats['all_available_tags']):
            logger.info(f'  {tag}')

        return 0
    except Exception as e:
        logger.error(f'Error during tag consolidation: {e}')
        return 1


def run_suggest_tags(args):  # noqa: ARG001
    """
    Suggest additional relevant tags for all articles using existing tag vocabulary.

    This function suggests additional tags for articles based on their abstracts
    and the existing tag vocabulary in the citation graph.

    Args:
        args: Command line arguments (not used in this function but part of the
            pattern).

    Returns:
        int: Exit code.
    """
    logger.info('Attempting to suggest additional tags for all articles.')
    config = get_config()

    try:
        pipeline = ThothPipeline(
            ocr_api_key=config.api_keys.mistral_key,
            llm_api_key=config.api_keys.openrouter_key,
            templates_dir=Path(config.templates_dir),
            prompts_dir=Path(config.prompts_dir),
            output_dir=Path(config.output_dir),
            notes_dir=Path(config.notes_dir),
            api_base_url=config.api_server_config.base_url,
        )

        stats = pipeline.suggest_additional_tags()

        logger.info('Tag suggestion process completed successfully.')
        logger.info('Summary statistics:')
        logger.info(f'  - Articles processed: {stats["articles_processed"]}')
        logger.info(f'  - Articles updated: {stats["articles_updated"]}')
        logger.info(f'  - Tags added: {stats["tags_added"]}')
        logger.info(f'  - Available tag vocabulary size: {stats["vocabulary_size"]}')

        return 0
    except Exception as e:
        logger.error(f'Error during tag suggestion: {e}')
        return 1


def run_scrape_filter_test(args):
    """
    Test the scrape filter with sample articles.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    logger.info('Testing scrape filter functionality.')
    config = get_config()

    try:
        # Initialize pipeline to get scrape filter
        pipeline = ThothPipeline(
            ocr_api_key=config.api_keys.mistral_key,
            llm_api_key=config.api_keys.openrouter_key,
            templates_dir=Path(config.templates_dir),
            prompts_dir=Path(config.prompts_dir),
            output_dir=Path(config.output_dir),
            notes_dir=Path(config.notes_dir),
            api_base_url=config.api_server_config.base_url,
        )

        # Create sample queries if requested
        if args.create_sample_queries:
            from thoth.utilities.models import ResearchQuery

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
                    required_topics=['machine learning'],
                    preferred_topics=['deep learning', 'neural networks'],
                    excluded_topics=['hardware', 'robotics'],
                ),
                ResearchQuery(
                    name='nlp_research',
                    description='Natural language processing research',
                    research_question='How are transformer models being applied to NLP tasks?',
                    keywords=[
                        'natural language processing',
                        'transformer',
                        'BERT',
                        'GPT',
                    ],
                    required_topics=['natural language processing'],
                    preferred_topics=['transformer', 'attention mechanism'],
                    excluded_topics=['computer vision'],
                ),
            ]

            for query in sample_queries:
                pipeline.scrape_filter.agent.create_query(query)
                logger.info(f'Created sample query: {query.name}')

        # Test with sample article metadata
        from thoth.utilities.models import ScrapedArticleMetadata

        sample_articles = [
            ScrapedArticleMetadata(
                title='Attention Is All You Need',
                authors=['Vaswani, A.', 'Shazeer, N.', 'Parmar, N.'],
                abstract='We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.',
                journal='NIPS',
                source='test',
                keywords=['transformer', 'attention', 'neural networks'],
            ),
            ScrapedArticleMetadata(
                title='BERT: Pre-training of Deep Bidirectional Transformers',
                authors=['Devlin, J.', 'Chang, M.', 'Lee, K.'],
                abstract='We introduce BERT, a new language representation model.',
                journal='NAACL',
                source='test',
                keywords=['BERT', 'transformer', 'language model'],
            ),
        ]

        logger.info('Testing scrape filter with sample articles...')

        for article in sample_articles:
            result = pipeline.scrape_filter.process_scraped_article(
                metadata=article,
                download_pdf=False,  # Don't actually download for testing
            )

            logger.info(f'Article: {article.title}')
            logger.info(f'Decision: {result["decision"]}')
            logger.info(f'Score: {result["evaluation"].relevance_score:.2f}')
            logger.info(f'Reasoning: {result["evaluation"].reasoning}')
            logger.info('---')

        logger.info('Scrape filter test completed successfully.')
        return 0

    except Exception as e:
        logger.error(f'Error during scrape filter test: {e}')
        return 1


def run_agent_chat(args):  # noqa: ARG001
    """
    Start an interactive chat with the research assistant agent.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    try:
        from thoth.pipeline import ThothPipeline

        logger.info('Starting research assistant agent chat...')

        # Initialize pipeline to get proper configuration
        pipeline = ThothPipeline()
        agent = pipeline.scrape_filter.agent

        print('\n' + '=' * 70)
        print('🤖 Welcome to the Enhanced Thoth Research Assistant Agent!')
        print('=' * 70)
        print('I can help you manage research queries AND discovery sources for')
        print('automatic article discovery, filtering, and collection.')

        print('\n🔍 **Discovery Source Management:**')
        print("  • 'list discovery sources' - Show all configured sources")
        print(
            '  • \'create an arxiv source called "ml_papers" for machine learning\' - Create ArXiv source'
        )
        print(
            '  • \'create a pubmed source called "bio_research" searching for neuroscience\' - Create PubMed source'
        )
        print("  • 'run discovery for arxiv_test' - Run specific source")
        print("  • 'run discovery with max 5 articles' - Run all sources with limit")
        print("  • 'edit arxiv_test source' - Modify existing source")
        print("  • 'delete old_source' - Remove a source")

        print('\n📝 **Research Query Management:**')
        print("  • 'create query' - Create new research query")
        print("  • 'list queries' - Show existing queries")
        print("  • 'help' - Get help with using the system")

        print('\n🚀 **Quick Start:**')
        print("1. Try: 'list discovery sources' to see current sources")
        print(
            '2. Create: \'create an arxiv source called "my_research" for deep learning\''
        )
        print("3. Run: 'run discovery for my_research'")

        print('\n💡 **Tips:**')
        print('  • Use natural language - I understand context!')
        print('  • Discovery sources automatically filter using your research queries')
        print("  • Type 'exit' or 'quit' to end the session")
        print('=' * 70 + '\n')

        conversation_history = []

        while True:
            try:
                user_message = input('You: ').strip()

                if user_message.lower() in {'exit', 'quit', 'bye', 'done'}:
                    print('\n👋 Thank you for using the Thoth Research Assistant!')
                    print(
                        'Your queries and discovery sources have been saved and will be used for automatic filtering.'
                    )
                    break

                if not user_message:
                    continue

                # Get response from agent
                response = agent.chat(
                    user_message, conversation_history=conversation_history
                )

                print(f'\nAgent: {response["agent_response"]}')

                # Show available queries if relevant
                if response.get('available_queries'):
                    print(
                        f'\nAvailable queries: {", ".join(response["available_queries"])}'
                    )

                print()  # Add spacing

                # Update conversation history
                conversation_history.append({'role': 'user', 'content': user_message})
                conversation_history.append(
                    {'role': 'agent', 'content': response['agent_response']}
                )

                # Keep conversation history manageable
                if len(conversation_history) > 20:
                    conversation_history = conversation_history[-20:]

            except KeyboardInterrupt:
                print('\n\n👋 Session interrupted. Goodbye!')
                break
            except Exception as e:
                logger.error(f'Error in agent chat: {e}')
                print(f'\n❌ Error: {e}')
                print("Please try again or type 'exit' to quit.")

        return 0

    except Exception as e:
        logger.error(f'Failed to start agent chat: {e}')
        print(f'❌ Failed to start agent chat: {e}')
        return 1


def run_discovery_command(args):
    """
    Handle discovery commands.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    if not hasattr(args, 'discovery_command') or not args.discovery_command:
        logger.error('No discovery subcommand specified')
        return 1

    try:
        if args.discovery_command == 'run':
            return run_discovery_run(args)
        elif args.discovery_command == 'list':
            return run_discovery_list(args)
        elif args.discovery_command == 'create':
            return run_discovery_create(args)
        elif args.discovery_command == 'edit':
            return run_discovery_edit(args)
        elif args.discovery_command == 'delete':
            return run_discovery_delete(args)
        elif args.discovery_command == 'scheduler':
            return run_discovery_scheduler(args)
        elif args.discovery_command == 'show':
            return run_discovery_show(args)
        else:
            logger.error(f'Unknown discovery command: {args.discovery_command}')
            return 1

    except ImportError as e:
        logger.error(f'Discovery system not available: {e}')
        return 1


def run_discovery_run(args):
    """
    Run discovery for sources.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    try:
        from thoth.discovery import DiscoveryManager

        # Initialize discovery manager with scrape filter
        pipeline = ThothPipeline()

        discovery_manager = DiscoveryManager(
            scrape_filter=pipeline.scrape_filter,
        )

        # Run discovery
        result = discovery_manager.run_discovery(
            source_name=args.source,
            max_articles=args.max_articles,
        )

        logger.info('Discovery run completed:')
        logger.info(f'  Articles found: {result.articles_found}')
        logger.info(f'  Articles filtered: {result.articles_filtered}')
        logger.info(f'  Articles downloaded: {result.articles_downloaded}')
        logger.info(f'  Execution time: {result.execution_time_seconds:.2f}s')

        if result.errors:
            logger.warning(f'  Errors encountered: {len(result.errors)}')
            for error in result.errors:
                logger.warning(f'    - {error}')

        return 0

    except Exception as e:
        logger.error(f'Error running discovery: {e}')
        return 1


def run_discovery_list(args):  # noqa: ARG001
    """
    List all discovery sources.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    try:
        from thoth.discovery import DiscoveryManager

        discovery_manager = DiscoveryManager()
        sources = discovery_manager.list_sources()

        if not sources:
            logger.info('No discovery sources configured.')
            return 0

        logger.info(f'Found {len(sources)} discovery sources:')
        logger.info('')

        for source in sources:
            logger.info(f'Name: {source.name}')
            logger.info(f'  Type: {source.source_type}')
            logger.info(f'  Description: {source.description}')
            logger.info(f'  Active: {source.is_active}')
            logger.info(f'  Last run: {source.last_run or "Never"}')

            if source.schedule_config:
                logger.info(
                    f'  Schedule: Every {source.schedule_config.interval_minutes} minutes'
                )
                logger.info(
                    f'  Max articles: {source.schedule_config.max_articles_per_run}'
                )

            logger.info('')

        return 0

    except Exception as e:
        logger.error(f'Error listing discovery sources: {e}')
        return 1


def run_discovery_show(args):
    """
    Show detailed information about a discovery source.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    try:
        from thoth.discovery import DiscoveryManager

        discovery_manager = DiscoveryManager()
        source = discovery_manager.get_source(args.name)
        if not source:
            logger.error(f'Discovery source not found: {args.name}')
            return 1

        logger.info('Discovery Source Details:')
        logger.info(f'  Name: {source.name}')
        logger.info(f'  Type: {source.source_type}')
        logger.info(f'  Description: {source.description}')
        logger.info(f'  Active: {source.is_active}')
        logger.info(f'  Last run: {source.last_run or "Never"}')

        if source.schedule_config:
            logger.info(
                f'  Schedule: Every {source.schedule_config.interval_minutes} minutes'
            )
            logger.info(
                f'  Max articles: {source.schedule_config.max_articles_per_run}'
            )

        logger.info('')

        return 0

    except Exception as e:
        logger.error(f'Error showing discovery source: {e}')
        return 1


def run_discovery_create(args):
    """
    Create a new discovery source.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    try:
        import json

        from thoth.discovery import DiscoveryManager
        from thoth.utilities.models import DiscoverySource, ScheduleConfig

        discovery_manager = DiscoveryManager()

        # Load configuration from file if provided
        config_data = {}
        if args.config_file:
            config_file = Path(args.config_file)
            if not config_file.exists():
                logger.error(f'Configuration file not found: {config_file}')
                return 1

            with open(config_file) as f:
                config_data = json.load(f)

        # Create basic source configuration
        source_config = {
            'name': args.name,
            'source_type': args.type,
            'description': args.description,
            'is_active': True,
            'schedule_config': ScheduleConfig(
                interval_minutes=60,
                max_articles_per_run=50,
                enabled=True,
            ),
            'query_filters': [],
        }

        # Merge with config file data
        source_config.update(config_data)

        # Create source
        source = DiscoverySource(**source_config)
        discovery_manager.create_source(source)

        logger.info(f'Successfully created discovery source: {args.name}')
        logger.info(f'  Type: {args.type}')
        logger.info(f'  Description: {args.description}')

        return 0

    except Exception as e:
        logger.error(f'Error creating discovery source: {e}')
        return 1


def run_discovery_edit(args):
    """
    Edit an existing discovery source.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    try:
        import json

        from thoth.discovery import DiscoveryManager

        discovery_manager = DiscoveryManager()

        # Fetch existing source
        source = discovery_manager.get_source(args.name)
        if not source:
            logger.error(f'Discovery source not found: {args.name}')
            return 1

        logger.info(f'Editing discovery source: {args.name}')

        # Update source attributes
        if args.description:
            source.description = args.description
            logger.info(f'Updated description: {args.description}')

        if args.config_file:
            config_file = Path(args.config_file)
            if not config_file.exists():
                logger.error(f'Configuration file not found: {config_file}')
                return 1

            with open(config_file) as f:
                config_data = json.load(f)

            # Update configuration fields
            if 'api_config' in config_data:
                source.api_config = config_data['api_config']
                logger.info('Updated API configuration')

            if 'scraper_config' in config_data:
                source.scraper_config = config_data['scraper_config']
                logger.info('Updated scraper configuration')

            if 'schedule_config' in config_data:
                from thoth.utilities.models import ScheduleConfig

                source.schedule_config = ScheduleConfig(
                    **config_data['schedule_config']
                )
                logger.info('Updated schedule configuration')

            if 'query_filters' in config_data:
                source.query_filters = config_data['query_filters']
                logger.info('Updated query filters')

        # Update active status
        if args.active:
            source.is_active = args.active.lower() == 'true'
            logger.info(f'Updated active status: {source.is_active}')

        # Save updated source
        discovery_manager.update_source(source)

        logger.info(f'Successfully updated discovery source: {args.name}')
        logger.info(f'  Description: {source.description}')
        logger.info(f'  Active: {source.is_active}')

        return 0

    except Exception as e:
        logger.error(f'Error updating discovery source: {e}')
        return 1


def run_discovery_delete(args):
    """
    Delete a discovery source.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    try:
        from thoth.discovery import DiscoveryManager

        discovery_manager = DiscoveryManager()

        # Check if source exists
        source = discovery_manager.get_source(args.name)
        if not source:
            logger.error(f'Discovery source not found: {args.name}')
            return 1

        # Confirm deletion
        if not args.confirm:
            print('\nDiscovery Source Details:')
            print(f'  Name: {source.name}')
            print(f'  Type: {source.source_type}')
            print(f'  Description: {source.description}')
            print(f'  Active: {source.is_active}')
            print('\nAre you sure you want to delete this discovery source?')
            print('This action cannot be undone.')
            response = input('Type "delete" to confirm: ')
            if response.lower() != 'delete':
                logger.info('Deletion cancelled.')
                return 0

        # Delete source
        discovery_manager.delete_source(args.name)

        logger.info(f'Successfully deleted discovery source: {args.name}')
        return 0

    except Exception as e:
        logger.error(f'Error deleting discovery source: {e}')
        return 1


def run_discovery_scheduler(args):
    """
    Handle discovery scheduler commands.

    Args:
        args: Command line arguments.

    Returns:
        int: Exit code.
    """
    if not hasattr(args, 'scheduler_command') or not args.scheduler_command:
        logger.error('No scheduler subcommand specified')
        return 1

    try:
        from thoth.discovery import DiscoveryScheduler

        if args.scheduler_command == 'start':
            scheduler = DiscoveryScheduler()
            scheduler.start()
            logger.info('Discovery scheduler started. Press Ctrl+C to stop.')

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                scheduler.stop()
                logger.info('Discovery scheduler stopped.')

            return 0

        elif args.scheduler_command == 'status':
            scheduler = DiscoveryScheduler()
            status = scheduler.get_schedule_status()

            logger.info(f'Scheduler running: {status["running"]}')
            logger.info(f'Total sources: {status["total_sources"]}')
            logger.info(f'Enabled sources: {status["enabled_sources"]}')
            logger.info('')

            if status['sources']:
                logger.info('Sources:')
                for source in status['sources']:
                    logger.info(f'  {source["name"]}:')
                    logger.info(f'    Enabled: {source["enabled"]}')
                    logger.info(f'    Type: {source["source_type"]}')
                    logger.info(f'    Last run: {source["last_run"] or "Never"}')
                    logger.info(
                        f'    Next run: {source["next_run"] or "Not scheduled"}'
                    )
                    logger.info('')

            return 0

        else:
            logger.error(f'Unknown scheduler command: {args.scheduler_command}')
            return 1

    except Exception as e:
        logger.error(f'Error with scheduler command: {e}')
        return 1


def main():
    """
    Main entry point.

    Returns:
        int: Exit code.
    """
    args = parse_args()

    if args.command == 'monitor':
        return run_monitor(args)
    elif args.command == 'process':
        return process_pdf(args)
    elif args.command == 'api':
        return run_api_server(args)
    elif args.command == 'reprocess-note':
        return run_reprocess_note(args)
    elif args.command == 'regenerate-all-notes':
        return run_regenerate_all_notes(args)
    elif args.command == 'consolidate-tags':
        return run_consolidate_tags(args)
    elif args.command == 'consolidate-tags-only':
        return run_consolidate_tags_only(args)
    elif args.command == 'suggest-tags':
        return run_suggest_tags(args)
    elif args.command == 'scrape-filter':
        return run_scrape_filter_test(args)
    elif args.command == 'agent':
        return run_agent_chat(args)
    elif args.command == 'discovery':
        return run_discovery_command(args)
    else:
        logger.error('No command specified')
        return 1


if __name__ == '__main__':
    sys.exit(main())

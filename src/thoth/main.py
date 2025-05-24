#!/usr/bin/env python3
"""
Main entry point for Thoth.

This module provides a command-line interface for running the Thoth system.
"""

import argparse
import sys
import threading
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
        args: Command line arguments (not used in this function but part of the pattern).

    Returns:
        int: Exit code.
    """  # noqa: W505
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
    else:
        logger.error('No command specified')
        return 1


if __name__ == '__main__':
    sys.exit(main())

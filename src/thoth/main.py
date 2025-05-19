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
from thoth.monitor.pdf_monitor import PDFMonitor
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
    else:
        logger.error('No command specified')
        return 1


if __name__ == '__main__':
    sys.exit(main())

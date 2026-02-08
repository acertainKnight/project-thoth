#!/usr/bin/env python3
"""
Standalone PDF Monitor Entry Point

This module provides a direct entry point for the PDF monitor service that
bypasses the CLI infrastructure AND avoids triggering package __init__ imports.
It's designed to be simple and focused:
1. Load configuration
2. Initialize only required services (no discovery/CLI imports)
3. Watch folder for PDFs
4. Check database for processed PDFs
5. Process unprocessed PDFs through document pipeline

This eliminates the circular import issues and CLI overhead that were causing
initialization failures. The monitor should be as simple as:
    watch folder → check database → process if needed
"""

# Configure safe environment before any ML imports
import os
import sys

from loguru import logger

os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'
os.environ['TORCH_NUM_THREADS'] = '1'


def main() -> int:
    """
    Run the PDF monitor without CLI overhead.

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    logger.info('═══════════════════════════════════════════════════')
    logger.info('STANDALONE MONITOR: Starting initialization...')
    logger.info('═══════════════════════════════════════════════════')

    try:
        # Import initialize_thoth function (no CLI imports)
        logger.info('Importing initialize_thoth...')
        from thoth.initialization import initialize_thoth

        logger.info('✓ initialize_thoth imported successfully')

        # Initialize Thoth with optimized pipeline
        logger.info('Calling initialize_thoth()...')
        print('MONITOR: Calling initialize_thoth()...', flush=True)
        services, document_pipeline, citation_tracker = initialize_thoth()
        print('MONITOR: initialize_thoth() returned successfully!', flush=True)
        logger.info('✓ Thoth initialized successfully')
        print('MONITOR: ✓ Thoth initialized successfully', flush=True)

        # Import PDFMonitor directly from module (avoid server/__init__.py)
        print('MONITOR: About to import PDFMonitor...', flush=True)
        logger.info('Importing PDFMonitor...')
        from thoth.server.pdf_monitor import PDFMonitor

        print('MONITOR: PDFMonitor imported successfully!', flush=True)
        logger.info('✓ PDFMonitor imported successfully')

        # Load config for watch directory
        print('MONITOR: Loading configuration...', flush=True)
        logger.info('Loading configuration...')
        from thoth.config import config

        print('MONITOR: Configuration loaded', flush=True)
        logger.info('✓ Configuration loaded')

        # Determine watch directory
        print('MONITOR: Determining watch directory...', flush=True)
        watch_dir = None
        if hasattr(config, 'servers_config') and hasattr(
            config.servers_config, 'monitor'
        ):
            watch_dirs = config.servers_config.monitor.watch_directories
            if watch_dirs:
                # Use first watch directory (relative to vault root)
                watch_dir = config.vault_root / watch_dirs[0].lstrip('/')
                print(
                    f'MONITOR: Using watch directory from settings: {watch_dir}',
                    flush=True,
                )
                logger.info(f'Using watch directory from settings: {watch_dir}')

        if not watch_dir:
            watch_dir = config.pdf_dir
            print(f'MONITOR: Using default PDF directory: {watch_dir}', flush=True)
            logger.info(f'Using default PDF directory: {watch_dir}')

        # Ensure watch directory exists
        print(f'MONITOR: Ensuring watch directory exists: {watch_dir}', flush=True)
        watch_dir.mkdir(parents=True, exist_ok=True)
        print('MONITOR: Watch directory created/verified', flush=True)

        # Create monitor with document pipeline
        print('MONITOR: About to create PDFMonitor instance...', flush=True)
        logger.info('Creating PDFMonitor instance...')
        monitor = PDFMonitor(
            watch_dir=watch_dir,
            document_pipeline=document_pipeline,
            polling_interval=30.0,  # 30 seconds
            recursive=True,  # Watch subdirectories
        )
        print('MONITOR: PDFMonitor instance created successfully!', flush=True)
        logger.info('✓ PDFMonitor created successfully')

        # Start monitoring
        print(
            'MONITOR: ═══════════════════════════════════════════════════', flush=True
        )
        print(f'MONITOR: Starting PDF monitor on: {watch_dir}', flush=True)
        print('MONITOR: Polling interval: 30s | Recursive: True', flush=True)
        print(
            'MONITOR: ═══════════════════════════════════════════════════', flush=True
        )
        logger.info('═══════════════════════════════════════════════════')
        logger.info(f'Starting PDF monitor on: {watch_dir}')
        logger.info('Polling interval: 30s | Recursive: True')
        logger.info('═══════════════════════════════════════════════════')

        print('MONITOR: Calling monitor.start()...', flush=True)
        monitor.start()
        print('MONITOR: monitor.start() returned (monitor stopped)', flush=True)

        # Should only reach here if monitor stops normally
        logger.info('Monitor stopped normally')
        return 0

    except KeyboardInterrupt:
        logger.info('Monitor stopped by user (Ctrl+C)')
        return 0

    except Exception as e:
        logger.error(f'FATAL ERROR in monitor: {e}')
        logger.exception('Full traceback:')
        return 1


if __name__ == '__main__':
    sys.exit(main())

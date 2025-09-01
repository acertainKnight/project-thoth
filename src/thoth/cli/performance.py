"""
CLI commands for performance optimization and benchmarking.

This module provides commands for:
- Running optimized batch processing
- Performance benchmarking and monitoring
- Cache management
- System resource optimization
"""

import asyncio
import json
import time
from pathlib import Path

from loguru import logger

from thoth.pipeline import ThothPipeline
from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline
from thoth.services.cache_service import CacheService
from thoth.services.service_manager import ServiceManager
from thoth.utilities.config import get_config


def run_optimized_batch(args, pipeline: ThothPipeline):
    """
    Run optimized batch processing of PDFs.
    """
    config = get_config()

    # Load PDF list
    try:
        if args.input_file:
            with open(args.input_file) as f:
                processing_data = json.load(f)
            pdf_paths = [Path(p) for p in processing_data.get('all_files', [])]
        elif args.pdf_dir:
            pdf_dir = Path(args.pdf_dir)
            pdf_paths = list(pdf_dir.glob('*.pdf'))
        else:
            pdf_dir = config.pdf_dir
            pdf_paths = list(pdf_dir.glob('*.pdf'))
    except FileNotFoundError:
        logger.error(f'Input file not found: {args.input_file}')
        return 1

    if not pdf_paths:
        logger.error('No PDFs found to process')
        return 1

    # Limit files if requested
    if args.max_files:
        pdf_paths = pdf_paths[: args.max_files]

    logger.info(f'Processing {len(pdf_paths)} PDFs with optimizations')

    # Initialize optimized pipeline
    service_manager = ServiceManager(config)
    service_manager.initialize()

    optimized_pipeline = OptimizedDocumentPipeline(
        config=config,
        services=service_manager,
        markdown_dir=config.markdown_dir,
        notes_dir=config.notes_dir,
        pdf_tracker=pipeline.pdf_tracker,
        citation_tracker=pipeline.citation_tracker,
    )

    start_time = time.time()
    successful = 0
    failed = 0

    if args.async_mode:
        # Use async processing
        try:
            results = asyncio.run(
                optimized_pipeline.batch_process_pdfs_async(pdf_paths)
            )
            successful = len([r for r in results if r is not None])
            failed = len(pdf_paths) - successful
        except Exception as e:
            logger.error(f'Async batch processing failed: {e}')
            return 1
    else:
        # Use sync processing with optimizations
        for i, pdf_path in enumerate(pdf_paths, 1):
            try:
                _ = optimized_pipeline.process_pdf(pdf_path)
                successful += 1
                logger.info(f'[{i}/{len(pdf_paths)}] Processed: {pdf_path.name}')
            except Exception as e:
                failed += 1
                logger.error(f'[{i}/{len(pdf_paths)}] Failed: {pdf_path.name} - {e}')

            # Progress update every 5 files
            if i % 5 == 0 or i == len(pdf_paths):
                elapsed = time.time() - start_time
                rate = i / elapsed * 60 if elapsed > 0 else 0
                logger.info(
                    f'Progress: {i}/{len(pdf_paths)} | Rate: {rate:.1f} files/min'
                )

    total_time = time.time() - start_time

    # Print summary
    print('\n' + '=' * 60)
    print('OPTIMIZED BATCH PROCESSING COMPLETE')
    print('=' * 60)
    print(f'Total PDFs: {len(pdf_paths)}')
    print(f'Successful: {successful}')
    print(f'Failed: {failed}')
    print(f'Success Rate: {successful / len(pdf_paths) * 100:.1f}%')
    print(f'Total Time: {total_time:.1f} seconds')
    print(f'Average Time per PDF: {total_time / len(pdf_paths):.1f} seconds')
    print(f'Processing Rate: {successful / (total_time / 60):.1f} files/minute')

    # Get performance stats
    perf_stats = optimized_pipeline.get_performance_stats()
    print('\nPerformance Configuration:')
    print(f'   CPU Cores: {perf_stats.get("cpu_count", "Unknown")}')
    print(f'   Max Workers: {perf_stats.get("max_workers", {})}')
    print(f'   Async Enabled: {perf_stats.get("async_processing_enabled", False)}')

    return 0 if failed == 0 else 1


def run_benchmark(args, pipeline: ThothPipeline):
    """
    Run performance benchmark comparing standard vs optimized processing.
    """
    config = get_config()

    # Get test PDFs
    if args.benchmark_files:
        pdf_paths = [Path(f) for f in args.benchmark_files]
    else:
        # Use first 3-5 PDFs from the directory for quick benchmark
        pdf_dir = config.pdf_dir
        pdf_paths = list(pdf_dir.glob('*.pdf'))[
            : min(5, len(list(pdf_dir.glob('*.pdf'))))
        ]

    if not pdf_paths:
        logger.error('No PDFs found for benchmarking')
        return 1

    logger.info(f'Running benchmark with {len(pdf_paths)} PDFs')

    # Initialize optimized pipeline
    service_manager = ServiceManager(config)
    service_manager.initialize()

    optimized_pipeline = OptimizedDocumentPipeline(
        config=config,
        services=service_manager,
        markdown_dir=config.markdown_dir,
        notes_dir=config.notes_dir,
        pdf_tracker=pipeline.pdf_tracker,
        citation_tracker=pipeline.citation_tracker,
    )

    # Run standard processing
    logger.info('🐌 Running standard processing benchmark...')
    standard_start = time.time()
    standard_successful = 0

    for pdf_path in pdf_paths:
        try:
            pipeline.process_pdf(pdf_path)
            standard_successful += 1
        except Exception as e:
            logger.warning(f'Standard processing failed for {pdf_path.name}: {e}')

    standard_time = time.time() - standard_start

    # Small delay between tests
    time.sleep(2)

    # Run optimized processing
    logger.info('Running optimized processing benchmark...')
    optimized_start = time.time()
    optimized_successful = 0

    for pdf_path in pdf_paths:
        try:
            optimized_pipeline.process_pdf(pdf_path)
            optimized_successful += 1
        except Exception as e:
            logger.warning(f'Optimized processing failed for {pdf_path.name}: {e}')

    optimized_time = time.time() - optimized_start

    # Calculate improvements
    standard_avg = standard_time / len(pdf_paths) if pdf_paths else 0
    optimized_avg = optimized_time / len(pdf_paths) if pdf_paths else 0
    improvement = (
        (standard_avg - optimized_avg) / standard_avg * 100 if standard_avg > 0 else 0
    )
    speedup = standard_avg / optimized_avg if optimized_avg > 0 else 0

    # Print benchmark results
    print('\n' + '=' * 60)
    print('PERFORMANCE BENCHMARK RESULTS')
    print('=' * 60)
    print(f'Test Files: {len(pdf_paths)} PDFs')

    print('\n🐌 Standard Processing:')
    print(f'   Total Time: {standard_time:.1f} seconds')
    print(f'   Average per PDF: {standard_avg:.1f} seconds')
    print(f'   Successful: {standard_successful}/{len(pdf_paths)}')

    print('\nOptimized Processing:')
    print(f'   Total Time: {optimized_time:.1f} seconds')
    print(f'   Average per PDF: {optimized_avg:.1f} seconds')
    print(f'   Successful: {optimized_successful}/{len(pdf_paths)}')

    print('\nPerformance Improvement:')
    print(f'   Speed Improvement: {improvement:.1f}% faster')
    print(f'   Speedup Factor: {speedup:.1f}x')

    if improvement > 0:
        print(f'   Time Saved per PDF: {standard_avg - optimized_avg:.1f} seconds')
        print(
            f'   Estimated monthly savings: {(standard_avg - optimized_avg) * 30:.1f} seconds per PDF'
        )

    return 0


def run_cache_stats(args, pipeline: ThothPipeline):  # noqa: ARG001
    """
    Show cache statistics and management.
    """
    config = get_config()
    cache_service = CacheService(config)
    cache_service.initialize()

    stats = cache_service.get_cache_statistics()

    print('\n' + '=' * 50)
    print('💾 CACHE STATISTICS')
    print('=' * 50)

    print('Memory Cache:')
    print(f'   Size: {stats.get("memory_cache_size", 0)} items')
    print(f'   Limit: {stats.get("memory_cache_limit", 0)} items')

    print('\nDisk Cache:')
    print(f'   Total Files: {stats.get("total_disk_cache_files", 0)}')
    print(f'   Total Size: {stats.get("total_cache_size_mb", 0):.1f} MB')

    print('\nCache by Type:')
    for cache_type, type_stats in stats.get('cache_directories', {}).items():
        print(
            f'   {cache_type.title()}: {type_stats["files"]} files ({type_stats["size_mb"]:.1f} MB)'
        )

    # Cache management commands
    if args.clear_cache:
        cache_type = args.clear_cache if args.clear_cache != 'all' else None
        success = cache_service.clear_cache(cache_type)

        if success:
            if cache_type:
                print(f'\nCleared {cache_type} cache')
            else:
                print('\nCleared all caches')
        else:
            print('\nFailed to clear cache')
            return 1

    return 0


def run_system_info(args, pipeline: ThothPipeline):  # noqa: ARG001
    """
    Show system information and performance configuration.
    """
    import os

    import psutil

    config = get_config()

    print('\n' + '=' * 50)
    print('SYSTEM INFORMATION')
    print('=' * 50)

    # CPU Information
    print('CPU:')
    print(f'   Cores: {os.cpu_count()}')
    print(f'   Usage: {psutil.cpu_percent(interval=1)}%')

    # Memory Information
    memory = psutil.virtual_memory()
    print('\nMemory:')
    print(f'   Total: {memory.total / (1024**3):.1f} GB')
    print(f'   Available: {memory.available / (1024**3):.1f} GB')
    print(f'   Usage: {memory.percent}%')

    # Performance Configuration
    perf_config = config.performance_config
    print('\nPerformance Configuration:')
    print(f'   Auto Scale Workers: {perf_config.auto_scale_workers}')
    print(f'   Content Analysis Workers: {perf_config.content_analysis_workers}')
    print(
        f'   Citation Enhancement Workers: {perf_config.citation_enhancement_workers}'
    )
    print(f'   Citation Extraction Workers: {perf_config.citation_extraction_workers}')
    print(f'   OCR Max Concurrent: {perf_config.ocr_max_concurrent}')
    print(f'   Async Enabled: {perf_config.async_enabled}')
    print(f'   OCR Caching: {perf_config.ocr_enable_caching}')
    print(f'   Memory Optimization: {perf_config.memory_optimization_enabled}')

    return 0


def configure_subparser(subparsers):
    """Configure the performance subparser."""
    parser = subparsers.add_parser(
        'performance', help='Performance optimization and benchmarking commands'
    )
    perf_subparsers = parser.add_subparsers(
        dest='perf_command', help='Performance command to run'
    )

    # Optimized batch processing
    batch_parser = perf_subparsers.add_parser(
        'batch', help='Run optimized batch processing'
    )
    batch_parser.add_argument(
        '--input-file', help='JSON file with PDF list (from analyze_processing_gaps.py)'
    )
    batch_parser.add_argument('--pdf-dir', help='Directory containing PDFs to process')
    batch_parser.add_argument(
        '--max-files', type=int, help='Maximum number of files to process'
    )
    batch_parser.add_argument(
        '--async',
        dest='async_mode',
        action='store_true',
        help='Use async processing (recommended)',
    )
    batch_parser.set_defaults(func=run_optimized_batch)

    # Benchmark
    benchmark_parser = perf_subparsers.add_parser(
        'benchmark', help='Run performance benchmark'
    )
    benchmark_parser.add_argument(
        '--files',
        dest='benchmark_files',
        nargs='+',
        help='Specific PDF files to benchmark',
    )
    benchmark_parser.set_defaults(func=run_benchmark)

    # Cache management
    cache_parser = perf_subparsers.add_parser(
        'cache', help='Cache statistics and management'
    )
    cache_parser.add_argument(
        '--clear',
        dest='clear_cache',
        choices=['all', 'ocr', 'analysis', 'citations', 'api_responses', 'embeddings'],
        help='Clear specific cache type or all caches',
    )
    cache_parser.set_defaults(func=run_cache_stats)

    # System information
    info_parser = perf_subparsers.add_parser(
        'info', help='Show system information and performance configuration'
    )
    info_parser.set_defaults(func=run_system_info)

    # Set default function for when no subcommand is provided
    parser.set_defaults(func=run_system_info)

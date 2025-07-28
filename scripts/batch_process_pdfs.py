#!/usr/bin/env python3
"""
Batch PDF Processing Script

This script processes all PDFs that need processing or reprocessing
as identified by the analyze_processing_gaps.py script.
"""

import json
import time
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.pipeline import ThothPipeline


def load_processing_list(input_file: str = 'pdfs_to_process.json') -> dict[str, Any]:
    """
    Load the list of PDFs to process from the analysis file.

    Args:
        input_file: Path to the JSON file with processing list

    Returns:
        dict[str, Any]: Processing data from analysis
    """
    try:
        with open(input_file, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f'Processing list file not found: {input_file}')
        logger.info("Run 'python scripts/analyze_processing_gaps.py' first")
        return {}
    except Exception as e:
        logger.error(f'Failed to load processing list: {e}')
        return {}


def process_single_pdf(
    pipeline: ThothPipeline, pdf_path: str, index: int, total: int
) -> bool:
    """
    Process a single PDF through the pipeline.

    Args:
        pipeline: Thoth pipeline instance
        pdf_path: Path to the PDF file
        index: Current file index (for progress tracking)
        total: Total number of files

    Returns:
        bool: True if successful, False if failed
    """
    pdf_file = Path(pdf_path)

    if not pdf_file.exists():
        logger.warning(f'PDF file not found: {pdf_path}')
        return False

    logger.info(f'[{index + 1}/{total}] Processing: {pdf_file.name}')

    try:
        # Process the PDF through the pipeline
        result = pipeline.process_pdf(pdf_file)

        if result:
            logger.info(f'✅ Successfully processed: {pdf_file.name}')
            return True
        else:
            logger.error(f'❌ Failed to process: {pdf_file.name}')
            return False

    except Exception as e:
        logger.error(f'❌ Error processing {pdf_file.name}: {e}')
        return False


def batch_process_pdfs(
    processing_data: dict[str, Any],
    max_files: int | None = None,
    delay_between_files: float = 1.0,
) -> dict[str, Any]:
    """
    Process all PDFs in the processing list.

    Args:
        processing_data: Data from analyze_processing_gaps.py
        max_files: Maximum number of files to process (None for all)
        delay_between_files: Delay in seconds between processing files

    Returns:
        dict[str, Any]: Processing results summary
    """
    if not processing_data or not processing_data.get('all_files'):
        logger.error('No files to process')
        return {}

    # Initialize pipeline
    pipeline = ThothPipeline()

    # Get list of files to process
    all_files = processing_data['all_files']
    if max_files:
        all_files = all_files[:max_files]

    total_files = len(all_files)

    logger.info(f'🚀 Starting batch processing of {total_files} PDFs')
    logger.info(f'📁 PDF Directory: {processing_data["pdf_directory"]}')

    # Track results
    successful = []
    failed = []
    skipped = []

    start_time = time.time()

    for i, pdf_path in enumerate(all_files):
        pdf_file = Path(pdf_path)

        # Check if file exists
        if not pdf_file.exists():
            logger.warning(f'Skipping missing file: {pdf_file.name}')
            skipped.append(str(pdf_path))
            continue

        # Process the file
        success = process_single_pdf(pipeline, pdf_path, i, total_files)

        if success:
            successful.append(str(pdf_path))
        else:
            failed.append(str(pdf_path))

        # Progress update
        processed_count = len(successful) + len(failed)
        if processed_count % 5 == 0 or processed_count == total_files:
            elapsed = time.time() - start_time
            rate = processed_count / elapsed if elapsed > 0 else 0
            logger.info(
                f'Progress: {processed_count}/{total_files} files | '
                f'Success: {len(successful)} | '
                f'Failed: {len(failed)} | '
                f'Rate: {rate:.1f} files/min'
            )

        # Add delay between files to prevent overloading
        if i < total_files - 1:  # Don't delay after the last file
            time.sleep(delay_between_files)

    # Final summary
    total_time = time.time() - start_time

    results = {
        'total_attempted': total_files,
        'successful': len(successful),
        'failed': len(failed),
        'skipped': len(skipped),
        'processing_time_seconds': total_time,
        'processing_time_minutes': total_time / 60,
        'average_time_per_file': total_time / total_files if total_files > 0 else 0,
        'successful_files': successful,
        'failed_files': failed,
        'skipped_files': skipped,
    }

    return results


def print_results_summary(results: dict[str, Any]) -> None:
    """Print a formatted summary of the batch processing results."""
    if not results:
        print('❌ No results to display')
        return

    print('\n' + '=' * 60)
    print('🎯 BATCH PROCESSING COMPLETE')
    print('=' * 60)
    print(f'📊 Total Files Attempted: {results["total_attempted"]}')
    print(f'✅ Successfully Processed: {results["successful"]}')
    print(f'❌ Failed: {results["failed"]}')
    print(f'⏭️  Skipped (missing): {results["skipped"]}')

    success_rate = (
        (results['successful'] / results['total_attempted'] * 100)
        if results['total_attempted'] > 0
        else 0
    )
    print(f'📈 Success Rate: {success_rate:.1f}%')

    print(f'\n⏱️  Processing Time: {results["processing_time_minutes"]:.1f} minutes')
    print(f'⚡ Average Time per File: {results["average_time_per_file"]:.1f} seconds')

    if results['failed'] > 0:
        print(f'\n❌ Failed files ({results["failed"]}):')
        for i, failed_file in enumerate(results['failed_files'][:10]):
            print(f'   {i + 1}. {Path(failed_file).name}')
        if len(results['failed_files']) > 10:
            print(f'   ... and {len(results["failed_files"]) - 10} more')

    if results['successful'] > 0:
        print(
            f'\n✅ After processing, you should have ~{33 + results["successful"]} articles with analysis data!'
        )
        print("🏷️  Run 'thoth consolidate-tags' to retag all your articles")


def save_results(
    results: dict[str, Any], output_file: str = 'batch_processing_results.json'
) -> None:
    """Save processing results to a JSON file."""
    try:
        from datetime import datetime

        results['timestamp'] = datetime.now().isoformat()

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f'\n💾 Results saved to: {output_file}')
    except Exception as e:
        logger.error(f'Failed to save results: {e}')


def main():
    """Main function for batch processing."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Batch process PDFs through Thoth pipeline'
    )
    parser.add_argument(
        '--max-files',
        type=int,
        help='Maximum number of files to process (default: all)',
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Delay between files in seconds (default: 1.0)',
    )
    parser.add_argument(
        '--input-file',
        default='pdfs_to_process.json',
        help='Input file with processing list (default: pdfs_to_process.json)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without actually processing',
    )

    args = parser.parse_args()

    print('🔄 Thoth Batch PDF Processor')
    print('=' * 40)

    # Load processing list
    processing_data = load_processing_list(args.input_file)
    if not processing_data:
        return 1

    total_files = len(processing_data.get('all_files', []))
    files_to_process = (
        min(args.max_files, total_files) if args.max_files else total_files
    )

    print(f'📁 PDF Directory: {processing_data["pdf_directory"]}')
    print(f'📚 Total Files Available: {total_files}')
    print(f'🎯 Files to Process: {files_to_process}')
    print(f'⏱️  Delay Between Files: {args.delay}s')

    if args.dry_run:
        print('\n🔍 DRY RUN - Files that would be processed:')
        files_to_show = processing_data['all_files'][:files_to_process]
        for i, pdf_path in enumerate(files_to_show[:20]):
            print(f'   {i + 1:2d}. {Path(pdf_path).name}')
        if len(files_to_show) > 20:
            print(f'       ... and {len(files_to_show) - 20} more files')
        print('\nRun without --dry-run to actually process these files.')
        return 0

    # Confirm before processing
    if files_to_process > 10:
        response = input(
            f'\n⚠️  About to process {files_to_process} files. Continue? (y/N): '
        )
        if response.lower() != 'y':
            print('Processing cancelled.')
            return 0

    # Start processing
    print('\n🚀 Starting batch processing...')

    try:
        results = batch_process_pdfs(
            processing_data, max_files=args.max_files, delay_between_files=args.delay
        )

        print_results_summary(results)
        save_results(results)

        return 0 if results.get('failed', 0) == 0 else 1

    except KeyboardInterrupt:
        print('\n⚠️  Processing interrupted by user')
        return 1
    except Exception as e:
        logger.error(f'Batch processing failed: {e}')
        return 1


if __name__ == '__main__':
    exit(main())

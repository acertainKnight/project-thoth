#!/usr/bin/env python3
"""
Analysis script to identify which PDFs need processing or reprocessing.

This script compares:
1. PDFs in the directory
2. PDFs tracked as processed
3. Articles with analysis data in knowledge graph

It identifies which PDFs need to be reprocessed.
"""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.pipeline import ThothPipeline
from thoth.server.pdf_monitor import PDFTracker


def analyze_processing_gaps() -> dict[str, Any]:
    """
    Analyze processing gaps between PDF files and knowledge graph.

    Returns:
        dict[str, Any]: Detailed analysis of processing gaps
    """
    # Initialize components
    pipeline = ThothPipeline()
    tracker = PDFTracker()

    if not pipeline.citation_tracker:
        logger.error('Citation tracker not initialized')
        return {}

    # Get PDF directory from config
    pdf_dir = Path(pipeline.config.pdf_dir)
    if not pdf_dir.exists():
        logger.error(f'PDF directory does not exist: {pdf_dir}')
        return {}

    # 1. Get all PDF files in directory
    all_pdfs = list(pdf_dir.glob('*.pdf'))
    all_pdf_paths = {str(pdf): pdf for pdf in all_pdfs}

    # 2. Get tracked processed files
    processed_files = set(tracker.processed_files.keys())

    # 3. Get articles with analysis data from knowledge graph
    articles_with_analysis = []
    articles_without_analysis = []

    for article_id, node_data in pipeline.citation_tracker.graph.nodes(data=True):
        if node_data.get('analysis'):
            articles_with_analysis.append(
                {
                    'id': article_id,
                    'pdf_path': node_data.get('pdf_path'),
                    'title': node_data.get('metadata', {}).get('title', article_id),
                }
            )
        else:
            articles_without_analysis.append(
                {
                    'id': article_id,
                    'pdf_path': node_data.get('pdf_path'),
                    'title': node_data.get('metadata', {}).get('title', article_id),
                }
            )

    # 4. Categorize PDFs
    pdfs_in_directory = set(str(pdf) for pdf in all_pdfs)
    pdfs_tracked_processed = processed_files
    pdfs_with_analysis = set()

    for article in articles_with_analysis:
        if article['pdf_path']:
            pdfs_with_analysis.add(str(article['pdf_path']))

    # Find different categories
    unprocessed_pdfs = pdfs_in_directory - pdfs_tracked_processed
    processed_but_no_analysis = pdfs_tracked_processed - pdfs_with_analysis
    need_reprocessing = processed_but_no_analysis.intersection(pdfs_in_directory)

    # Convert back to Path objects for the files that need processing
    pdfs_to_process = []
    pdfs_to_reprocess = []

    for pdf_path_str in unprocessed_pdfs:
        if pdf_path_str in all_pdf_paths:
            pdfs_to_process.append(all_pdf_paths[pdf_path_str])

    for pdf_path_str in need_reprocessing:
        if pdf_path_str in all_pdf_paths:
            pdfs_to_reprocess.append(all_pdf_paths[pdf_path_str])

    analysis_result = {
        'pdf_directory': str(pdf_dir),
        'total_pdfs_in_directory': len(all_pdfs),
        'total_tracked_processed': len(processed_files),
        'total_with_analysis': len(articles_with_analysis),
        'unprocessed_pdfs': len(unprocessed_pdfs),
        'processed_but_no_analysis': len(processed_but_no_analysis),
        'need_reprocessing': len(need_reprocessing),
        'pdfs_to_process': [str(p) for p in pdfs_to_process],
        'pdfs_to_reprocess': [str(p) for p in pdfs_to_reprocess],
        'all_pdfs_needing_work': [str(p) for p in pdfs_to_process + pdfs_to_reprocess],
    }

    return analysis_result


def print_analysis_summary(analysis: dict[str, Any]) -> None:
    """Print a formatted summary of the processing gap analysis."""
    if not analysis:
        print('❌ Failed to analyze processing gaps')
        return

    print('🔍 PDF Processing Gap Analysis')
    print('=' * 60)
    print(f'📁 PDF Directory: {analysis["pdf_directory"]}')
    print(f'📚 Total PDFs in Directory: {analysis["total_pdfs_in_directory"]}')
    print(f'⏳ Tracked as Processed: {analysis["total_tracked_processed"]}')
    print(f'✅ With Full Analysis Data: {analysis["total_with_analysis"]}')
    print()
    print(f'🆕 Never Processed: {analysis["unprocessed_pdfs"]}')
    print(f'🔄 Processed but Missing Analysis: {analysis["processed_but_no_analysis"]}')
    print(f'⚠️  Need Reprocessing: {analysis["need_reprocessing"]}')

    total_needing_work = len(analysis['all_pdfs_needing_work'])
    print(f'🎯 Total PDFs Needing Work: {total_needing_work}')

    if total_needing_work > 0:
        print('\n📋 Files Needing Processing/Reprocessing:')
        print('-' * 50)
        for i, pdf_path in enumerate(analysis['all_pdfs_needing_work'][:15]):
            pdf_name = Path(pdf_path).name
            status = (
                '🆕 New' if pdf_path in analysis['pdfs_to_process'] else '🔄 Reprocess'
            )
            print(f'{i + 1:2d}. {status} {pdf_name}')

        if total_needing_work > 15:
            print(f'    ... and {total_needing_work - 15} more files')

    print('\n💡 Explanation:')
    print("🆕 Never Processed: PDFs that haven't been processed at all")
    print('🔄 Need Reprocessing: PDFs that were processed but missing analysis data')
    print('   (This can happen due to processing failures, interruptions, or errors)')


def save_processing_list(
    analysis: dict[str, Any], output_file: str = 'pdfs_to_process.json'
) -> None:
    """Save the list of PDFs that need processing to a JSON file."""
    try:
        from datetime import datetime

        processing_data = {
            'timestamp': datetime.now().isoformat(),
            'pdf_directory': analysis['pdf_directory'],
            'total_files_needing_work': len(analysis['all_pdfs_needing_work']),
            'files_to_process': analysis['pdfs_to_process'],
            'files_to_reprocess': analysis['pdfs_to_reprocess'],
            'all_files': analysis['all_pdfs_needing_work'],
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processing_data, f, indent=2)
        print(f'\n💾 Processing list saved to: {output_file}')
    except Exception as e:
        print(f'❌ Failed to save processing list: {e}')


def main():
    """Main function to run the processing gap analysis."""
    print('🔍 Analyzing PDF Processing Gaps...')
    print('This may take a moment...\n')

    try:
        analysis = analyze_processing_gaps()
        print_analysis_summary(analysis)

        if analysis and analysis['all_pdfs_needing_work']:
            save_processing_list(analysis)
            print(
                f'\n🚀 Next step: Run the batch processing script on {len(analysis["all_pdfs_needing_work"])} files'
            )
        else:
            print('\n✅ All PDFs are fully processed!')

    except Exception as e:
        logger.error(f'Failed to analyze processing gaps: {e}')
        print(f'❌ Analysis failed: {e}')


if __name__ == '__main__':
    main()

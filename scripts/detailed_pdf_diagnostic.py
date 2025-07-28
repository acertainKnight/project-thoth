#!/usr/bin/env python3
"""
Detailed PDF Processing Diagnostic Script

This script provides comprehensive diagnostics to understand exactly what's
happening with PDF processing, including path matching issues, processing
failures, and knowledge graph inconsistencies.
"""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.pipeline import ThothPipeline
from thoth.server.pdf_monitor import PDFTracker


def detailed_pdf_analysis() -> dict[str, Any]:
    """
    Perform comprehensive analysis of PDF processing status.

    Returns:
        dict[str, Any]: Detailed diagnostic information
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

    print(f'🔍 Analyzing PDF directory: {pdf_dir}')

    # 1. Get all PDF files in directory
    all_pdfs_in_dir = list(pdf_dir.glob('*.pdf'))
    print(f'📁 Found {len(all_pdfs_in_dir)} PDF files in directory')

    # 2. Get tracked processed files
    processed_files_dict = tracker.processed_files
    processed_file_paths = set(processed_files_dict.keys())
    print(f'⏳ Found {len(processed_file_paths)} tracked processed files')

    # 3. Analyze knowledge graph articles
    articles_with_analysis = []
    articles_without_analysis = []
    articles_with_pdf_paths = []

    for article_id, node_data in pipeline.citation_tracker.graph.nodes(data=True):
        has_analysis = bool(node_data.get('analysis'))
        pdf_path = node_data.get('pdf_path')

        metadata = node_data.get('metadata') or {}
        title = (
            metadata.get('title', article_id)
            if isinstance(metadata, dict)
            else article_id
        )

        article_info = {
            'id': article_id,
            'title': str(title)[:80] if title else article_id[:80],
            'pdf_path': str(pdf_path) if pdf_path else None,
            'markdown_path': str(node_data.get('markdown_path'))
            if node_data.get('markdown_path')
            else None,
            'obsidian_path': node_data.get('obsidian_path'),
            'has_analysis': has_analysis,
        }

        if has_analysis:
            articles_with_analysis.append(article_info)
        else:
            articles_without_analysis.append(article_info)

        if pdf_path:
            articles_with_pdf_paths.append(article_info)

    print(
        f'📊 Knowledge graph: {len(articles_with_analysis)} with analysis, {len(articles_without_analysis)} without'
    )
    print(f'📄 Articles with PDF paths: {len(articles_with_pdf_paths)}')

    # 4. Cross-reference analysis
    pdfs_in_dir_paths = set(str(pdf) for pdf in all_pdfs_in_dir)
    pdfs_with_analysis_paths = set()
    pdfs_in_graph_paths = set()

    for article in articles_with_analysis:
        if article['pdf_path']:
            pdfs_with_analysis_paths.add(article['pdf_path'])

    for article in articles_with_pdf_paths:
        if article['pdf_path']:
            pdfs_in_graph_paths.add(article['pdf_path'])

    # 5. Find mismatches and issues
    # PDFs in directory but not tracked as processed
    untracked_pdfs = pdfs_in_dir_paths - processed_file_paths

    # PDFs tracked as processed but not in directory
    tracked_but_missing = processed_file_paths - pdfs_in_dir_paths

    # PDFs tracked as processed but no analysis data
    tracked_no_analysis = processed_file_paths - pdfs_with_analysis_paths
    tracked_no_analysis_in_dir = tracked_no_analysis.intersection(pdfs_in_dir_paths)

    # PDFs in directory but not in knowledge graph at all
    not_in_graph = pdfs_in_dir_paths - pdfs_in_graph_paths

    # PDFs in graph but no analysis
    in_graph_no_analysis = pdfs_in_graph_paths - pdfs_with_analysis_paths
    in_graph_no_analysis_in_dir = in_graph_no_analysis.intersection(pdfs_in_dir_paths)

    # 6. Detailed file-by-file analysis
    file_details = []
    for pdf_path in all_pdfs_in_dir:
        pdf_str = str(pdf_path)

        # Check if tracked as processed
        is_tracked = pdf_str in processed_file_paths
        processing_info = processed_files_dict.get(pdf_str, {})

        # Check if in knowledge graph
        in_graph_with_analysis = pdf_str in pdfs_with_analysis_paths
        in_graph_without_analysis = (
            pdf_str in pdfs_in_graph_paths and not in_graph_with_analysis
        )
        not_in_graph_at_all = pdf_str not in pdfs_in_graph_paths

        # Determine status
        if in_graph_with_analysis:
            status = '✅ Complete'
        elif is_tracked and in_graph_without_analysis:
            status = '⚠️ Processed but no analysis'
        elif is_tracked and not_in_graph_at_all:
            status = '❌ Tracked but not in graph'
        elif not is_tracked:
            status = '🆕 Not processed'
        else:
            status = '❓ Unknown'

        file_details.append(
            {
                'path': pdf_str,
                'name': pdf_path.name,
                'status': status,
                'is_tracked': is_tracked,
                'in_graph_with_analysis': in_graph_with_analysis,
                'in_graph_without_analysis': in_graph_without_analysis,
                'not_in_graph': not_in_graph_at_all,
                'processing_info': processing_info,
            }
        )

    # 7. Summary statistics
    status_counts = {}
    for detail in file_details:
        status = detail['status']
        status_counts[status] = status_counts.get(status, 0) + 1

    analysis_result = {
        'pdf_directory': str(pdf_dir),
        'total_pdfs_in_directory': len(all_pdfs_in_dir),
        'total_tracked_processed': len(processed_file_paths),
        'total_with_analysis': len(articles_with_analysis),
        'total_in_graph_with_pdf': len(articles_with_pdf_paths),
        # Mismatch analysis
        'untracked_pdfs': len(untracked_pdfs),
        'tracked_but_missing_files': len(tracked_but_missing),
        'tracked_no_analysis': len(tracked_no_analysis),
        'tracked_no_analysis_in_dir': len(tracked_no_analysis_in_dir),
        'not_in_graph': len(not_in_graph),
        'in_graph_no_analysis_in_dir': len(in_graph_no_analysis_in_dir),
        # Status breakdown
        'status_counts': status_counts,
        # Detailed file information
        'file_details': file_details,
        # File lists for debugging
        'untracked_pdf_list': list(untracked_pdfs),
        'tracked_but_missing_list': list(tracked_but_missing),
        'tracked_no_analysis_in_dir_list': list(tracked_no_analysis_in_dir),
        'not_in_graph_list': list(not_in_graph),
    }

    return analysis_result


def print_detailed_summary(analysis: dict[str, Any]) -> None:
    """Print a comprehensive summary of the diagnostic analysis."""
    if not analysis:
        print('❌ Failed to analyze PDFs')
        return

    print('\n' + '=' * 80)
    print('🔬 DETAILED PDF PROCESSING DIAGNOSTIC')
    print('=' * 80)

    print(f'📁 PDF Directory: {analysis["pdf_directory"]}')
    print(f'📚 Total PDFs in Directory: {analysis["total_pdfs_in_directory"]}')
    print(f'⏳ Tracked as Processed: {analysis["total_tracked_processed"]}')
    print(f'✅ With Analysis Data: {analysis["total_with_analysis"]}')
    print(f'📄 In Graph with PDF Path: {analysis["total_in_graph_with_pdf"]}')

    print('\n📊 STATUS BREAKDOWN:')
    print('-' * 40)
    for status, count in analysis['status_counts'].items():
        print(f'{status}: {count} files')

    print('\n🔍 ISSUE ANALYSIS:')
    print('-' * 40)
    print(f'🆕 Not Tracked: {analysis["untracked_pdfs"]} files')
    print(
        f'👻 Tracked but Missing Files: {analysis["tracked_but_missing_files"]} files'
    )
    print(
        f'⚠️  Tracked but No Analysis: {analysis["tracked_no_analysis_in_dir"]} files in directory'
    )
    print(f'❓ Not in Knowledge Graph: {analysis["not_in_graph"]} files')
    print(
        f'🔄 In Graph but No Analysis: {analysis["in_graph_no_analysis_in_dir"]} files'
    )

    # Show problematic files
    if analysis['tracked_no_analysis_in_dir'] > 0:
        print('\n⚠️  FILES TRACKED AS PROCESSED BUT NO ANALYSIS DATA:')
        print('-' * 60)
        for i, pdf_path in enumerate(analysis['tracked_no_analysis_in_dir_list'][:10]):
            print(f'{i + 1:2d}. {Path(pdf_path).name}')
        if len(analysis['tracked_no_analysis_in_dir_list']) > 10:
            print(
                f'    ... and {len(analysis["tracked_no_analysis_in_dir_list"]) - 10} more'
            )

    if analysis['not_in_graph'] > 0:
        print('\n❓ FILES NOT IN KNOWLEDGE GRAPH AT ALL:')
        print('-' * 50)
        for i, pdf_path in enumerate(analysis['not_in_graph_list'][:10]):
            print(f'{i + 1:2d}. {Path(pdf_path).name}')
        if len(analysis['not_in_graph_list']) > 10:
            print(f'    ... and {len(analysis["not_in_graph_list"]) - 10} more')

    print('\n💡 RECOMMENDATIONS:')
    print('-' * 30)

    if analysis['tracked_no_analysis_in_dir'] > 0:
        print('🔄 Files are tracked as processed but missing analysis data.')
        print('   This suggests processing failures or incomplete processing.')
        print('   → Reprocess these files')

    if analysis['not_in_graph'] > 0:
        print("❓ Files exist but aren't in knowledge graph at all.")
        print('   → These need to be processed from scratch')

    if analysis['untracked_pdfs'] > 0:
        print("🆕 Files aren't tracked as processed yet.")
        print('   → These are completely new and need processing')

    total_needing_work = (
        analysis['untracked_pdfs']
        + analysis['tracked_no_analysis_in_dir']
        + analysis['not_in_graph']
    )

    print(f'\n🎯 TOTAL FILES NEEDING WORK: {total_needing_work}')

    if total_needing_work > 0:
        expected_final = analysis['total_with_analysis'] + total_needing_work
        print(f'📈 After processing: ~{expected_final} articles with analysis data')
        print(f'🏷️  That would give you ~{expected_final} articles for retagging!')


def save_detailed_report(
    analysis: dict[str, Any], output_file: str = 'detailed_pdf_diagnostic.json'
) -> None:
    """Save detailed diagnostic report to JSON file."""
    try:
        from datetime import datetime

        analysis['timestamp'] = datetime.now().isoformat()

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2)
        print(f'\n💾 Detailed diagnostic saved to: {output_file}')
    except Exception as e:
        logger.error(f'Failed to save detailed report: {e}')


def create_comprehensive_processing_list(analysis: dict[str, Any]) -> None:
    """Create a comprehensive list of all files that need processing."""
    try:
        from datetime import datetime

        files_to_process = []

        # Add untracked files (new)
        for pdf_path in analysis['untracked_pdf_list']:
            files_to_process.append(
                {'path': pdf_path, 'type': 'untracked', 'reason': 'Never processed'}
            )

        # Add files tracked but no analysis (reprocess)
        for pdf_path in analysis['tracked_no_analysis_in_dir_list']:
            files_to_process.append(
                {
                    'path': pdf_path,
                    'type': 'reprocess',
                    'reason': 'Processed but no analysis data',
                }
            )

        # Add files not in graph (process)
        for pdf_path in analysis['not_in_graph_list']:
            files_to_process.append(
                {
                    'path': pdf_path,
                    'type': 'not_in_graph',
                    'reason': 'Not in knowledge graph',
                }
            )

        processing_data = {
            'timestamp': datetime.now().isoformat(),
            'pdf_directory': analysis['pdf_directory'],
            'total_files_needing_work': len(files_to_process),
            'files_to_process': files_to_process,
            'all_files': [item['path'] for item in files_to_process],
        }

        with open('comprehensive_processing_list.json', 'w', encoding='utf-8') as f:
            json.dump(processing_data, f, indent=2)

        print(
            '\n📋 Comprehensive processing list saved to: comprehensive_processing_list.json'
        )
        print(f'🎯 Ready to process {len(files_to_process)} files')

    except Exception as e:
        logger.error(f'Failed to create processing list: {e}')


def main():
    """Main function for detailed PDF diagnostic."""
    print('🔬 Running Detailed PDF Processing Diagnostic...')
    print('This provides comprehensive analysis of processing status...\n')

    try:
        analysis = detailed_pdf_analysis()
        print_detailed_summary(analysis)
        save_detailed_report(analysis)
        create_comprehensive_processing_list(analysis)

    except Exception as e:
        logger.error(f'Detailed diagnostic failed: {e}')
        print(f'❌ Diagnostic failed: {e}')


if __name__ == '__main__':
    main()

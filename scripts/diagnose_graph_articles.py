#!/usr/bin/env python3
"""
Diagnostic script to analyze articles in the knowledge graph.

This script helps identify why some articles are not being processed
during tag consolidation by showing which articles have analysis data
versus those that are just citation references.
"""

import json
from typing import Any

from loguru import logger

from thoth.pipeline import ThothPipeline


def analyze_graph_articles() -> dict[str, Any]:
    """
    Analyze articles in the knowledge graph to understand processing coverage.

    Returns:
        dict[str, Any]: Detailed analysis of articles in the graph
    """
    # Initialize pipeline to get access to citation tracker
    pipeline = ThothPipeline()

    if not pipeline.citation_tracker:
        logger.error('Citation tracker not initialized')
        return {}

    graph = pipeline.citation_tracker.graph
    total_articles = len(graph.nodes)

    # Categorize articles
    articles_with_analysis = []
    articles_without_analysis = []
    citation_only_articles = []

    for article_id, node_data in graph.nodes(data=True):
        metadata = node_data.get('metadata', {})
        analysis = node_data.get('analysis')
        title = metadata.get('title', article_id)

        article_info = {
            'id': article_id,
            'title': title,
            'has_pdf_path': bool(node_data.get('pdf_path')),
            'has_markdown_path': bool(node_data.get('markdown_path')),
            'has_obsidian_path': bool(node_data.get('obsidian_path')),
            'metadata_keys': list(metadata.keys()) if metadata else [],
            'analysis_keys': list(analysis.keys()) if analysis else [],
        }

        if analysis:
            articles_with_analysis.append(article_info)
        else:
            articles_without_analysis.append(article_info)

            # Check if this is likely a citation-only reference
            if not node_data.get('pdf_path') and not node_data.get('markdown_path'):
                citation_only_articles.append(article_info)

    analysis_result = {
        'total_articles': total_articles,
        'articles_with_analysis': len(articles_with_analysis),
        'articles_without_analysis': len(articles_without_analysis),
        'citation_only_articles': len(citation_only_articles),
        'processable_for_tags': len(articles_with_analysis),
        'articles_with_analysis_list': articles_with_analysis,
        'articles_without_analysis_list': articles_without_analysis,
        'citation_only_list': citation_only_articles,
    }

    return analysis_result


def print_analysis_summary(analysis: dict[str, Any]) -> None:
    """Print a formatted summary of the graph analysis."""
    if not analysis:
        print('❌ Failed to analyze graph')
        return

    print('📊 Knowledge Graph Article Analysis')
    print('=' * 50)
    print(f'📚 Total Articles in Graph: {analysis["total_articles"]}')
    print(f'✅ Articles with Analysis Data: {analysis["articles_with_analysis"]}')
    print(f'⚠️  Articles without Analysis Data: {analysis["articles_without_analysis"]}')
    print(f'🔗 Citation-Only References: {analysis["citation_only_articles"]}')
    print(f'🏷️  Processable for Tagging: {analysis["processable_for_tags"]}')

    print('\n' + '=' * 50)

    if analysis['articles_without_analysis'] > 0:
        print('\n⚠️  Articles WITHOUT Analysis Data:')
        print('-' * 40)
        for i, article in enumerate(
            analysis['articles_without_analysis_list'][:10]
        ):  # Show first 10
            print(f'{i + 1:2d}. {article["title"][:60]}...')
            print(f'    ID: {article["id"]}')
            print(f'    Has PDF: {article["has_pdf_path"]}')
            print(f'    Has Markdown: {article["has_markdown_path"]}')
            print(f'    Metadata: {article["metadata_keys"]}')
            print()

        if len(analysis['articles_without_analysis_list']) > 10:
            remaining = len(analysis['articles_without_analysis_list']) - 10
            print(f'    ... and {remaining} more articles')

    print('\n💡 Explanation:')
    print(
        '- Articles with analysis data are fully processed PDFs with abstracts, tags, etc.'
    )
    print('- Articles without analysis data are typically:')
    print('  • Citation references from other papers')
    print('  • Failed PDF processing attempts')
    print('  • Incomplete processing results')
    print(
        '- Only articles with analysis data can be processed during tag consolidation'
    )

    if analysis['citation_only_articles'] > 0:
        print(
            f'\n🔗 You have {analysis["citation_only_articles"]} citation-only references'
        )
        print('   These were discovered through citations but not directly processed')


def save_detailed_report(
    analysis: dict[str, Any], output_file: str = 'graph_analysis_report.json'
) -> None:
    """Save detailed analysis to a JSON file."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f'\n💾 Detailed report saved to: {output_file}')
    except Exception as e:
        print(f'❌ Failed to save report: {e}')


def main():
    """Main function to run the analysis."""
    print('🔍 Analyzing Knowledge Graph Articles...')
    print('This may take a moment...\n')

    try:
        analysis = analyze_graph_articles()
        print_analysis_summary(analysis)
        save_detailed_report(analysis)

        print('\n🚀 Suggestions:')
        if analysis and analysis['articles_without_analysis'] > 0:
            print('1. To process more articles, run: thoth regenerate-all-notes')
            print('2. To reprocess specific PDFs, use: thoth process --pdf-path <path>')
            print('3. Citation-only references cannot be processed without their PDFs')
        else:
            print('✅ All articles in your graph have analysis data!')

    except Exception as e:
        logger.error(f'Failed to analyze graph: {e}')
        print(f'❌ Analysis failed: {e}')


if __name__ == '__main__':
    main()

"""
Backfill script to migrate citation graph from JSON file to PostgreSQL.

This script loads the legacy JSON graph file and saves all nodes and edges
to the PostgreSQL database, including tags, analysis data, and citations.
"""

import json
import sys
from pathlib import Path

import networkx as nx
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from thoth.config import config
from thoth.knowledge.graph import CitationGraph


def backfill_graph_to_postgres():
    """
    Backfill citation graph from JSON file to PostgreSQL.

    Process:
    1. Load the legacy JSON graph file
    2. Create CitationGraph instance
    3. Set the loaded graph
    4. Save to PostgreSQL using the fixed _save_to_postgres() method
    """
    logger.info('Starting citation graph backfill to PostgreSQL')

    # Load JSON graph file
    json_path = config.graph_storage_path
    logger.info(f'Loading graph from: {json_path}')

    if not Path(json_path).exists():
        logger.error(f'Graph file not found: {json_path}')
        return False

    with open(json_path) as f:
        data = json.load(f)

    # Convert to NetworkX graph
    logger.info('Converting JSON to NetworkX graph...')
    graph = nx.node_link_graph(data, edges='links')
    logger.info(f'Loaded graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges')

    # Count nodes with different data types
    nodes_with_analysis = sum(1 for _, d in graph.nodes(data=True) if 'analysis' in d)
    nodes_with_tags = sum(
        1
        for _, d in graph.nodes(data=True)
        if 'analysis' in d
        and isinstance(d['analysis'], dict)
        and d['analysis'].get('tags')
    )

    logger.info(f'  Nodes with analysis data: {nodes_with_analysis}')
    logger.info(f'  Nodes with tags: {nodes_with_tags}')

    # Create CitationGraph instance
    logger.info('Creating CitationGraph instance...')
    citation_graph = CitationGraph(service_manager=None)

    # Replace its graph with the loaded one
    citation_graph.graph = graph
    logger.info('Graph loaded into CitationGraph')

    # Save to PostgreSQL
    logger.info('Saving graph to PostgreSQL...')
    logger.info('This may take several minutes for large graphs...')

    try:
        citation_graph._save_graph()
        logger.success('✅ Graph successfully saved to PostgreSQL!')

        # Verify the save
        logger.info('\nVerification:')
        logger.info('  Run this query to check:')
        logger.info('  SELECT COUNT(*) as total_papers, ')
        logger.info(
            '         COUNT(CASE WHEN keywords IS NOT NULL AND jsonb_array_length(keywords) > 0 THEN 1 END) as papers_with_tags'
        )
        logger.info('  FROM papers;')

        return True

    except Exception as e:
        logger.error(f'❌ Failed to save graph: {e}')
        import traceback

        traceback.print_exc()
        return False


if __name__ == '__main__':
    logger.info('=' * 60)
    logger.info('CITATION GRAPH BACKFILL TO POSTGRESQL')
    logger.info('=' * 60)

    success = backfill_graph_to_postgres()

    logger.info('=' * 60)
    if success:
        logger.success('BACKFILL COMPLETED SUCCESSFULLY!')
    else:
        logger.error('BACKFILL FAILED!')
    logger.info('=' * 60)

    sys.exit(0 if success else 1)

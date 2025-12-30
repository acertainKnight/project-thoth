#!/usr/bin/env python3
"""
Backfill script to update existing papers with full file paths.

This script:
1. Loads the citation graph
2. Updates all nodes to store full paths instead of filenames
3. Re-saves the graph to PostgreSQL with all metadata
"""

import asyncio
from pathlib import Path
from loguru import logger

from thoth.config import Config
from thoth.knowledge.graph import CitationGraph


async def backfill_full_paths():
    """Backfill full file paths for all papers in the citation graph."""
    config = Config()

    # Initialize citation graph
    knowledge_dir = Path(config.knowledge_dir)
    citation_graph = CitationGraph(knowledge_dir)

    logger.info(f"Loaded citation graph with {len(citation_graph.graph.nodes)} nodes")

    # Track updates
    nodes_updated = 0
    nodes_with_paths = 0

    # Iterate through all nodes and update paths
    for node_id, node_data in citation_graph.graph.nodes(data=True):
        try:
            updated = False

            # Check if pdf_path exists and is just a filename
            pdf_path = node_data.get('pdf_path')
            if pdf_path and not pdf_path.startswith('/'):
                # Convert to full path
                full_pdf_path = Path(config.pdf_dir) / pdf_path
                if full_pdf_path.exists():
                    node_data['pdf_path'] = str(full_pdf_path)
                    updated = True
                    logger.debug(f"Updated pdf_path for {node_id}: {full_pdf_path}")

            # Check if markdown_path exists and is just a filename
            markdown_path = node_data.get('markdown_path')
            if markdown_path and not markdown_path.startswith('/'):
                # Convert to full path
                full_markdown_path = Path(config.markdown_dir) / markdown_path
                if full_markdown_path.exists():
                    node_data['markdown_path'] = str(full_markdown_path)
                    updated = True
                    logger.debug(f"Updated markdown_path for {node_id}: {full_markdown_path}")

            # Also look for _no_images.md files if markdown_path is missing
            if not node_data.get('markdown_path') and pdf_path:
                # Try to find markdown file based on PDF name
                pdf_name = Path(pdf_path).stem
                markdown_candidates = [
                    Path(config.markdown_dir) / f"{pdf_name}.md",
                    Path(config.markdown_dir) / f"{pdf_name}_no_images.md",
                ]
                for candidate in markdown_candidates:
                    if candidate.exists():
                        node_data['markdown_path'] = str(candidate)
                        updated = True
                        logger.info(f"Found and set markdown_path for {node_id}: {candidate}")
                        break

            if updated:
                nodes_updated += 1

            if node_data.get('pdf_path') or node_data.get('markdown_path'):
                nodes_with_paths += 1

        except Exception as e:
            logger.warning(f"Error updating paths for node {node_id}: {e}")
            continue

    logger.info(f"Updated {nodes_updated} nodes with full paths")
    logger.info(f"Total nodes with paths: {nodes_with_paths}")

    # Save the updated graph to disk and PostgreSQL
    logger.info("Saving updated graph to PostgreSQL...")
    citation_graph._save_graph()

    logger.success("✓ Backfill complete!")
    logger.info(f"  - Nodes in graph: {len(citation_graph.graph.nodes)}")
    logger.info(f"  - Citations in graph: {len(citation_graph.graph.edges)}")
    logger.info(f"  - Nodes updated: {nodes_updated}")
    logger.info(f"  - Nodes with paths: {nodes_with_paths}")


if __name__ == '__main__':
    asyncio.run(backfill_full_paths())

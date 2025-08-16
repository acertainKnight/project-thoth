"""
Citation graph storage component.

Handles persistence and loading of the citation graph.
"""

import pickle
from pathlib import Path
from typing import Any

import networkx as nx
from loguru import logger


class CitationStorage:
    """Handles loading and saving the citation graph."""
    
    def __init__(self, storage_path: Path):
        """
        Initialize the storage component.
        
        Args:
            storage_path: Path to the graph storage file
        """
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load_graph(self) -> nx.DiGraph:
        """
        Load the citation graph from disk.
        
        Returns:
            nx.DiGraph: The loaded graph, or empty graph if file doesn't exist
        """
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'rb') as f:
                    graph = pickle.load(f)
                logger.info(
                    f'Loaded citation graph with {graph.number_of_nodes()} nodes '
                    f'and {graph.number_of_edges()} edges'
                )
                return graph
            except Exception as e:
                logger.error(f'Failed to load citation graph: {e}')
                logger.info('Starting with empty citation graph')
        else:
            logger.info('No existing citation graph found, starting with empty graph')
        
        return nx.DiGraph()
    
    def save_graph(self, graph: nx.DiGraph) -> None:
        """
        Save the citation graph to disk.
        
        Args:
            graph: The graph to save
        """
        try:
            with open(self.storage_path, 'wb') as f:
                pickle.dump(graph, f)
            logger.debug(
                f'Saved citation graph with {graph.number_of_nodes()} nodes '
                f'and {graph.number_of_edges()} edges'
            )
        except Exception as e:
            logger.error(f'Failed to save citation graph: {e}')
    
    def backup_graph(self, graph: nx.DiGraph) -> Path | None:
        """
        Create a backup of the graph.
        
        Args:
            graph: The graph to backup
            
        Returns:
            Path to backup file if successful, None otherwise
        """
        try:
            backup_path = self.storage_path.with_suffix('.pkl.bak')
            with open(backup_path, 'wb') as f:
                pickle.dump(graph, f)
            logger.debug(f'Created graph backup at {backup_path}')
            return backup_path
        except Exception as e:
            logger.error(f'Failed to create graph backup: {e}')
            return None
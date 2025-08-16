"""
Citation graph analysis component.

Provides graph analysis and traversal functionality.
"""

from typing import Any

import networkx as nx
from loguru import logger


class GraphAnalyzer:
    """Handles citation network analysis and traversal."""
    
    def __init__(self, graph: nx.DiGraph):
        """
        Initialize the analyzer component.
        
        Args:
            graph: The citation graph to analyze
        """
        self.graph = graph
    
    def get_citation_network(self, article_id: str, depth: int = 1) -> nx.DiGraph:
        """
        Get a subgraph of the citation network around an article.
        
        Args:
            article_id: Center article ID
            depth: How many hops to include
            
        Returns:
            Subgraph containing the citation network
        """
        if article_id not in self.graph:
            logger.warning(f'Article {article_id} not found in graph')
            return nx.DiGraph()
        
        # Find all nodes within depth hops
        nodes_to_include = {article_id}
        current_layer = {article_id}
        
        for _ in range(depth):
            next_layer = set()
            for node in current_layer:
                # Add predecessors (articles that cite this one)
                next_layer.update(self.graph.predecessors(node))
                # Add successors (articles this one cites)
                next_layer.update(self.graph.successors(node))
            
            nodes_to_include.update(next_layer)
            current_layer = next_layer
        
        # Create subgraph
        subgraph = self.graph.subgraph(nodes_to_include).copy()
        
        logger.debug(
            f'Created citation network for {article_id} with depth {depth}: '
            f'{subgraph.number_of_nodes()} nodes, {subgraph.number_of_edges()} edges'
        )
        
        return subgraph
    
    def get_citing_articles(self, article_id: str) -> list[str]:
        """
        Get all articles that cite a given article.
        
        Args:
            article_id: Article to find citations for
            
        Returns:
            List of article IDs that cite the given article
        """
        if article_id not in self.graph:
            logger.warning(f'Article {article_id} not found in graph')
            return []
        
        citing = list(self.graph.predecessors(article_id))
        logger.debug(f'Found {len(citing)} articles citing {article_id}')
        return citing
    
    def get_cited_articles(self, article_id: str) -> list[str]:
        """
        Get all articles cited by a given article.
        
        Args:
            article_id: Article to find citations from
            
        Returns:
            List of article IDs cited by the given article
        """
        if article_id not in self.graph:
            logger.warning(f'Article {article_id} not found in graph')
            return []
        
        cited = list(self.graph.successors(article_id))
        logger.debug(f'Article {article_id} cites {len(cited)} articles')
        return cited
    
    def get_citation_count(self, article_id: str) -> int:
        """
        Get the number of times an article has been cited.
        
        Args:
            article_id: Article to check
            
        Returns:
            Number of citations
        """
        if article_id not in self.graph:
            return 0
        
        return self.graph.in_degree(article_id)
    
    def get_reference_count(self, article_id: str) -> int:
        """
        Get the number of references in an article.
        
        Args:
            article_id: Article to check
            
        Returns:
            Number of references
        """
        if article_id not in self.graph:
            return 0
        
        return self.graph.out_degree(article_id)
    
    def get_most_cited_articles(self, limit: int = 10) -> list[tuple[str, int]]:
        """
        Get the most cited articles in the graph.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of (article_id, citation_count) tuples
        """
        citation_counts = [(node, self.graph.in_degree(node)) for node in self.graph.nodes()]
        citation_counts.sort(key=lambda x: x[1], reverse=True)
        
        return citation_counts[:limit]
    
    def get_graph_statistics(self) -> dict[str, Any]:
        """
        Get overall statistics about the citation graph.
        
        Returns:
            Dictionary with graph statistics
        """
        stats = {
            'total_articles': self.graph.number_of_nodes(),
            'total_citations': self.graph.number_of_edges(),
            'avg_citations_per_article': 0.0,
            'avg_references_per_article': 0.0,
            'max_citations': 0,
            'max_references': 0,
            'orphaned_articles': 0,
            'connected_components': nx.number_weakly_connected_components(self.graph),
        }
        
        if stats['total_articles'] > 0:
            in_degrees = [self.graph.in_degree(n) for n in self.graph.nodes()]
            out_degrees = [self.graph.out_degree(n) for n in self.graph.nodes()]
            
            stats['avg_citations_per_article'] = sum(in_degrees) / len(in_degrees)
            stats['avg_references_per_article'] = sum(out_degrees) / len(out_degrees)
            stats['max_citations'] = max(in_degrees) if in_degrees else 0
            stats['max_references'] = max(out_degrees) if out_degrees else 0
            
            # Count orphaned articles
            stats['orphaned_articles'] = sum(
                1 for n in self.graph.nodes()
                if self.graph.in_degree(n) == 0 and self.graph.out_degree(n) == 0
            )
        
        return stats
    
    def find_citation_paths(self, source: str, target: str, max_length: int = 5) -> list[list[str]]:
        """
        Find all citation paths between two articles.
        
        Args:
            source: Starting article ID
            target: Target article ID
            max_length: Maximum path length
            
        Returns:
            List of paths (each path is a list of article IDs)
        """
        if source not in self.graph or target not in self.graph:
            return []
        
        try:
            paths = list(nx.all_simple_paths(
                self.graph, source, target, cutoff=max_length
            ))
            return paths
        except nx.NetworkXNoPath:
            return []
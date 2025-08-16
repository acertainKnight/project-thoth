"""
Citation search component.

Provides search functionality for the citation graph.
"""

import re
from typing import Any

import networkx as nx
from loguru import logger


class CitationSearch:
    """Handles searching within the citation graph."""
    
    def __init__(self, graph: nx.DiGraph):
        """
        Initialize the search component.
        
        Args:
            graph: The citation graph to search
        """
        self.graph = graph
    
    def search_articles(self, query: str) -> list[str]:
        """
        Search for articles by title, author, or DOI.
        
        Args:
            query: Search query string
            
        Returns:
            List of article IDs matching the query
        """
        query_lower = query.lower()
        matching_articles = []
        
        for node_id, data in self.graph.nodes(data=True):
            # Search in title
            title = data.get('title', '').lower()
            if query_lower in title:
                matching_articles.append(node_id)
                continue
            
            # Search in authors
            authors = data.get('authors', [])
            authors_str = ' '.join(authors).lower()
            if query_lower in authors_str:
                matching_articles.append(node_id)
                continue
            
            # Search in DOI
            doi = data.get('doi', '').lower()
            if doi and query_lower in doi:
                matching_articles.append(node_id)
                continue
            
            # Search in journal
            journal = data.get('journal', '').lower()
            if journal and query_lower in journal:
                matching_articles.append(node_id)
        
        logger.debug(f'Found {len(matching_articles)} articles matching "{query}"')
        return matching_articles
    
    def search_by_year(self, year: int) -> list[str]:
        """
        Find all articles published in a specific year.
        
        Args:
            year: Publication year
            
        Returns:
            List of article IDs from that year
        """
        matching_articles = []
        
        for node_id, data in self.graph.nodes(data=True):
            if data.get('year') == year:
                matching_articles.append(node_id)
        
        return matching_articles
    
    def search_by_author(self, author_name: str) -> list[str]:
        """
        Find all articles by a specific author.
        
        Args:
            author_name: Author name to search for
            
        Returns:
            List of article IDs by that author
        """
        author_lower = author_name.lower()
        matching_articles = []
        
        for node_id, data in self.graph.nodes(data=True):
            authors = data.get('authors', [])
            if any(author_lower in author.lower() for author in authors):
                matching_articles.append(node_id)
        
        return matching_articles
    
    def search_by_doi(self, doi: str) -> str | None:
        """
        Find article by DOI.
        
        Args:
            doi: DOI to search for
            
        Returns:
            Article ID if found, None otherwise
        """
        doi_lower = doi.lower()
        
        for node_id, data in self.graph.nodes(data=True):
            if data.get('doi', '').lower() == doi_lower:
                return node_id
        
        return None
    
    def get_articles_without_pdfs(self) -> list[str]:
        """
        Find all articles that don't have associated PDFs.
        
        Returns:
            List of article IDs without PDFs
        """
        articles_without_pdfs = []
        
        for node_id, data in self.graph.nodes(data=True):
            if not data.get('pdf_path'):
                articles_without_pdfs.append(node_id)
        
        return articles_without_pdfs
    
    def get_orphaned_articles(self) -> list[str]:
        """
        Find articles with no citations (neither citing nor cited).
        
        Returns:
            List of orphaned article IDs
        """
        orphaned = []
        
        for node_id in self.graph.nodes():
            in_degree = self.graph.in_degree(node_id)
            out_degree = self.graph.out_degree(node_id)
            
            if in_degree == 0 and out_degree == 0:
                orphaned.append(node_id)
        
        return orphaned
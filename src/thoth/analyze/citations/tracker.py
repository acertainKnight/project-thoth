"""
Citation tracker module for maintaining a knowledge graph of article citations.

This module provides functionality to track articles and their citations,
enabling proper linking between Obsidian markdown notes.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

import networkx as nx
from loguru import logger

from thoth.utilities.models import Citation


class CitationReference:
    """A reference to a citation in the citation graph."""

    def __init__(self, article_id: str, citation: Citation | None = None):
        """
        Initialize a citation reference.

        Args:
            article_id: The ID of the article in the citation graph
            citation: Optional Citation object with full citation data
        """
        self.article_id = article_id
        self.citation = citation

    def __str__(self) -> str:
        """String representation of the citation reference."""
        if self.citation:
            return f'{self.citation.title} ({self.citation.year})'
        return self.article_id


class CitationTracker:
    """
    Tracks and manages article citations in a knowledge graph structure.

    This class maintains a graph-based representation of articles and their
    citations, enabling proper linking between Obsidian markdown notes and
    providing insight into the citation network.
    """

    def __init__(
        self, knowledge_base_dir: Path, graph_storage_path: Path | None = None
    ) -> None:
        """
        Initialize the citation tracker.

        Args:
            knowledge_base_dir: Path to the knowledge base directory containing markdown notes
            graph_storage_path: Optional path to store the serialized knowledge graph
        """  # noqa: W505
        self.knowledge_base_dir = Path(knowledge_base_dir)
        self.graph_storage_path = (
            graph_storage_path or self.knowledge_base_dir / 'citation_graph.json'
        )

        # Initialize the citation graph
        self.graph = nx.DiGraph()

        # Load existing graph if available
        self._load_graph()

        logger.info(
            f'CitationTracker initialized with knowledge base at {knowledge_base_dir}'
        )

    def _load_graph(self) -> None:
        """
        Load the citation graph from storage if it exists.
        """
        if self.graph_storage_path.exists():
            try:
                # Load the graph from a JSON file
                with open(self.graph_storage_path, encoding='utf-8') as f:
                    graph_data = json.load(f)

                # Recreate the graph from the loaded data
                self.graph = nx.node_link_graph(graph_data)
                logger.info(
                    f'Loaded citation graph with {len(self.graph.nodes)} nodes and {len(self.graph.edges)} edges'
                )
            except Exception as e:
                logger.error(f'Error loading citation graph: {e}')
                # Initialize a new graph if loading fails
                self.graph = nx.DiGraph()
        else:
            logger.info('No existing citation graph found, creating new graph')

    def _save_graph(self) -> None:
        """
        Save the citation graph to storage.
        """
        try:
            os.makedirs(self.graph_storage_path.parent, exist_ok=True)
            # Convert the graph to a serializable format
            graph_data = nx.node_link_data(self.graph)
            # Save the graph to a JSON file
            with open(self.graph_storage_path, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, indent=2)

            logger.info(f'Saved citation graph to {self.graph_storage_path}')
        except Exception as e:
            logger.error(f'Error saving citation graph: {e}')

    def _generate_article_id(self, citation: Citation) -> str:
        """
        Generate a consistent article ID from a citation.

        Args:
            citation: Citation object containing article metadata

        Returns:
            str: The generated article ID
        """
        if citation.doi:
            return f'doi:{citation.doi}'
        elif hasattr(citation, 'backup_id') and citation.backup_id:
            return citation.backup_id
        else:
            return f'title:{self._sanitize_title(citation.title or citation.text)}'

    def add_article_from_citation(self, citation: Citation) -> str:
        """
        Add an article to the citation graph using a Citation object.

        Args:
            citation: Citation object containing article metadata

        Returns:
            str: The article ID used in the graph

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> citation = Citation(
            ...     text='Smith, J. (2023). Example Paper.',
            ...     authors=['Smith, J.'],
            ...     title='Example Paper',
            ...     year=2023,
            ...     doi='10.1234/example',
            ... )
            >>> article_id = tracker.add_article_from_citation(citation)
        """
        # Generate article ID based on available identifiers
        article_id = self._generate_article_id(citation)

        # Convert citation to metadata dictionary using the built-in dict() method
        metadata = citation.model_dump(exclude={'obsidian_uri'})

        # Add article to graph
        self.add_article(article_id, metadata, citation.obsidian_uri)

        return article_id

    def _node_exists(self, article_id: str) -> bool:
        """
        Check if an article node exists in the graph.

        Args:
            article_id: ID of the article to check

        Returns:
            bool: True if the node exists, False otherwise
        """
        exists = self.graph.has_node(article_id)
        if not exists:
            logger.warning(f'Article {article_id} not found in graph')
        return exists

    def add_article(
        self,
        article_id: str,
        metadata: dict[str, Any],
        obsidian_path: str | None = None,
    ) -> None:
        """
        Add an article to the citation graph.

        Args:
            article_id: Unique identifier for the article (e.g., DOI or sanitized title)
            metadata: Article metadata including title, authors, year, etc.
            obsidian_path: Path to the corresponding Obsidian markdown note if it exists

        Returns:
            None

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> tracker.add_article(
            ...     '10.1234/example',
            ...     {'title': 'Example Paper', 'authors': ['Smith, J.'], 'year': 2023},
            ...     '20230101-example-paper.md',
            ... )
        """
        node_data = {'metadata': metadata}
        if obsidian_path:
            node_data['obsidian_path'] = obsidian_path

        article_title = metadata.get('title', article_id)

        if not self.graph.has_node(article_id):
            # Add new node
            self.graph.add_node(article_id, **node_data)
            logger.info(f'Added article to citation graph: {article_title}')
        else:
            # Update existing node
            current_metadata = self.graph.nodes[article_id].get('metadata', {})
            current_metadata.update(metadata)
            self.graph.nodes[article_id]['metadata'] = current_metadata

            if obsidian_path:
                self.graph.nodes[article_id]['obsidian_path'] = obsidian_path

            logger.info(f'Updated article in citation graph: {article_title}')

        self._save_graph()

    def add_citation(
        self,
        source_id: str,
        target_id: str,
        citation_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a citation relationship between two articles.

        Args:
            source_id: ID of the citing article
            target_id: ID of the cited article
            citation_data: Optional additional data about the citation

        Returns:
            None

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> tracker.add_citation(
            ...     '10.1234/source',
            ...     '10.5678/target',
            ...     {'context': 'This work builds on [1]...'},
            ... )
        """
        # Ensure both articles exist in the graph
        if not self.graph.has_node(source_id):
            logger.warning(f'Source article {source_id} not found in graph')
            return

        if not self.graph.has_node(target_id):
            logger.warning(f'Target article {target_id} not found in graph')
            return

        # Add or update the citation edge
        if not self.graph.has_edge(source_id, target_id):
            self.graph.add_edge(source_id, target_id, data=citation_data or {})
            logger.info(f'Added citation from {source_id} to {target_id}')
        else:
            # Update existing edge with new data
            if citation_data:
                current_data = self.graph.edges[source_id, target_id].get('data', {})
                current_data.update(citation_data)
                self.graph.edges[source_id, target_id]['data'] = current_data

            logger.info(f'Updated citation from {source_id} to {target_id}')

        # Save the updated graph
        self._save_graph()

    def process_citations(self, citations: list[Citation]) -> None:
        """
        Process a list of citations for an article.

        Args:
            citations: List of Citation objects

        Returns:
            None

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> citations = [
            ...     Citation(
            ...         text='Smith, J. (2023). Example Paper.',
            ...         authors=['Smith, J.'],
            ...         title='Example Paper',
            ...         year=2023,
            ...     ),
            ...     Citation(
            ...         text='Jones, A. (2022). Another Paper.',
            ...         authors=['Jones, A.'],
            ...         title='Another Paper',
            ...         year=2022,
            ...     ),
            ... ]
            >>> tracker.process_citations(citations)
        """
        # Find the citation for the document itself (marked with is_document_citation flag)  # noqa: W505
        article_citation = next(
            (citation for citation in citations if citation.is_document_citation), None
        )

        # If no document citation is found, use the first citation as a fallback
        if article_citation is None and citations:
            article_citation = citations[0]
            logger.warning(
                'No document citation found, using first citation as fallback'
            )

        # Generate article ID based on available identifiers
        article_id = (
            self._generate_article_id(article_citation) if article_citation else None
        )

        if not article_id:
            logger.warning('No valid article citation found, cannot process citations')
            return
        for citation in citations:
            # Add the citation to the graph and get its ID
            target_id = self.add_article_from_citation(citation)

            # Add the citation relationship
            self.add_citation(article_id, target_id, {'citation_text': citation.text})

    def get_citation(self, article_id: str) -> Citation | None:
        """
        Get a Citation object for an article.

        Args:
            article_id: ID of the article

        Returns:
            Citation | None: Citation object if the article exists, None otherwise

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> citation = tracker.get_citation('10.1234/article')
            >>> citation.title
            'Example Paper'
        """
        if not self._node_exists(article_id):
            return None

        # Get metadata from the graph
        metadata = self.graph.nodes[article_id].get('metadata', {})
        obsidian_path = self.graph.nodes[article_id].get('obsidian_path')

        # Convert to Citation object
        try:
            # Create a Citation object by unpacking the metadata dictionary
            citation_dict = dict(metadata)

            # Add obsidian_uri separately if available
            if obsidian_path:
                citation_dict['obsidian_uri'] = obsidian_path

            return Citation(**citation_dict)
        except Exception as e:
            logger.error(f'Error creating Citation object for {article_id}: {e}')
            return None

    def get_citing_articles(self, article_id: str) -> list[str]:
        """
        Get articles that cite the specified article.

        Args:
            article_id: ID of the article

        Returns:
            list[str]: List of article IDs that cite the specified article

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> citing_articles = tracker.get_citing_articles('10.1234/article')
            >>> len(citing_articles)
            5
        """
        if not self._node_exists(article_id):
            return []

        # Get predecessors (incoming edges)
        return list(self.graph.predecessors(article_id))

    def get_cited_articles(self, article_id: str) -> list[str]:
        """
        Get articles cited by the specified article.

        Args:
            article_id: ID of the article

        Returns:
            list[str]: List of article IDs cited by the specified article

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> cited_articles = tracker.get_cited_articles('10.1234/article')
            >>> len(cited_articles)
            12
        """
        if not self._node_exists(article_id):
            return []

        # Get successors (outgoing edges)
        return list(self.graph.successors(article_id))

    def get_obsidian_path(self, article_id: str) -> str | None:
        """
        Get the Obsidian markdown path for an article if it exists.

        Args:
            article_id: ID of the article

        Returns:
            str | None: Path to the Obsidian markdown note or None if not found

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> path = tracker.get_obsidian_path('10.1234/article')
            >>> path
            '20230101-example-paper.md'
        """
        if not self._node_exists(article_id):
            return None

        return self.graph.nodes[article_id].get('obsidian_path')

    def get_article_metadata(self, article_id: str) -> dict[str, Any]:
        """
        Get metadata for an article.

        Args:
            article_id: ID of the article

        Returns:
            dict[str, Any]: Article metadata

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> metadata = tracker.get_article_metadata('10.1234/article')
            >>> metadata['title']
            'Example Paper'
        """
        if not self._node_exists(article_id):
            return {}

        return self.graph.nodes[article_id].get('metadata', {})

    def search_articles(self, query: str) -> list[str]:
        """
        Search for articles by title or author.

        Args:
            query: Search query

        Returns:
            list[str]: List of article IDs matching the query

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> results = tracker.search_articles('machine learning')
            >>> len(results)
            8
        """
        query = query.lower()
        results = []

        for node_id, node_data in self.graph.nodes(data=True):
            metadata = node_data.get('metadata', {})

            # Search in title
            if 'title' in metadata and query in metadata['title'].lower():
                results.append(node_id)
                continue

            # Search in authors
            if 'authors' in metadata:
                for author in metadata['authors']:
                    if query in author.lower():
                        results.append(node_id)
                        break

        return results

    def get_citation_network(self, article_id: str, depth: int = 1) -> nx.DiGraph:
        """
        Get the citation network around an article.

        Args:
            article_id: ID of the central article
            depth: How many levels of citations to include

        Returns:
            nx.DiGraph: A subgraph representing the citation network

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> network = tracker.get_citation_network('10.1234/article', depth=2)
            >>> len(network.nodes)
            15
        """
        if not self.graph.has_node(article_id):
            logger.warning(f'Article {article_id} not found in graph')
            return nx.DiGraph()

        # Start with the central article
        nodes_to_include = {article_id}
        current_nodes = {article_id}

        # Expand to include citing and cited articles up to the specified depth
        for _ in range(depth):
            next_nodes = set()

            for node in current_nodes:
                # Add citing articles
                citing = set(self.graph.predecessors(node))
                next_nodes.update(citing)

                # Add cited articles
                cited = set(self.graph.successors(node))
                next_nodes.update(cited)

            # Update the sets
            nodes_to_include.update(next_nodes)
            current_nodes = next_nodes

        # Create a subgraph with the selected nodes
        return self.graph.subgraph(nodes_to_include).copy()

    def update_obsidian_links(self, article_id: str) -> None:
        """
        Update Obsidian markdown links for an article's citations.

        This method finds all citations from the article and updates the
        corresponding Obsidian markdown note with proper wiki-links to
        existing notes for cited articles.

        Args:
            article_id: ID of the article to update

        Returns:
            None

        Example:
            >>> tracker = CitationTracker(Path('knowledge_base'))
            >>> tracker.update_obsidian_links('10.1234/article')
        """
        # Get the Obsidian path for the article
        obsidian_path = self.get_obsidian_path(article_id)
        if not obsidian_path:
            logger.warning(f'No Obsidian note found for article {article_id}')
            return

        # Get the full path to the markdown file
        md_path = self.knowledge_base_dir / obsidian_path
        if not md_path.exists():
            logger.warning(f'Markdown file not found: {md_path}')
            return

        # Get cited articles
        cited_articles = self.get_cited_articles(article_id)
        if not cited_articles:
            logger.info(f'No citations found for article {article_id}')
            return

        # Read the markdown content
        try:
            with open(md_path, encoding='utf-8') as f:
                content = f.read()

            # Process each cited article
            updated_content = content
            for cited_id in cited_articles:
                citation = self.get_citation(cited_id)
                if not citation or not citation.title:
                    continue

                cited_obsidian_path = self.get_obsidian_path(cited_id)
                if not cited_obsidian_path:
                    continue

                # Try to find references to this citation in the content
                title_pattern = re.escape(citation.title)
                wiki_link = (
                    f'[[{cited_obsidian_path.replace(".md", "")}|{citation.title}]]'
                )
                updated_content = re.sub(
                    f'({title_pattern})', wiki_link, updated_content
                )

            # Write the updated content if changes were made
            if updated_content != content:
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                logger.info(f'Updated Obsidian links in {md_path}')
            else:
                logger.info(f'No updates needed for {md_path}')

        except Exception as e:
            logger.error(f'Error updating Obsidian links for {article_id}: {e}')

    def _sanitize_title(self, title: str) -> str:
        """
        Create a sanitized ID from a title.

        Args:
            title: Article title

        Returns:
            str: Sanitized ID
        """
        # Replace spaces with hyphens and remove special characters
        sanitized = ''.join(
            c.lower() if c.isalnum() or c.isspace() else '-' for c in title
        )
        sanitized = '-'.join(filter(None, sanitized.split()))
        return sanitized

"""
Citation graph module for maintaining a knowledge graph of article citations.

This module provides functionality to track articles and their citations,
enabling proper linking between Obsidian markdown notes.
"""

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx
from loguru import logger

if TYPE_CHECKING:
    from thoth.services.service_manager import ServiceManager

from thoth.knowledge.components import (
    CitationFileManager,
    CitationSearch,
    CitationStorage,
    GraphAnalyzer,
)
from thoth.utilities.schemas import AnalysisResponse, Citation


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


class CitationGraph:
    """
    Tracks and manages article citations in a knowledge graph structure.

    This class maintains a graph-based representation of articles and their
    citations, enabling proper linking between Obsidian markdown notes and
    providing insight into the citation network.
    """

    def __init__(
        self,
        knowledge_base_dir: str | Path,
        graph_storage_path: str | Path | None = None,
        note_generator: Any | None = None,  # Deprecated
        pdf_dir: Path | None = None,
        markdown_dir: Path | None = None,
        notes_dir: Path | None = None,
        service_manager: 'ServiceManager | None' = None,
    ) -> None:
        """
        Initialize the CitationGraph.

        Args:
            knowledge_base_dir: Base directory for the knowledge base
            graph_storage_path: Path to save the citation graph. If None, defaults to
                knowledge_base_dir / 'citation_graph.pkl'
            note_generator: Deprecated - use service_manager instead
            pdf_dir: Directory where PDF files are stored
            markdown_dir: Directory where markdown files are stored
            notes_dir: Directory where notes are stored
            service_manager: ServiceManager instance for accessing services

        Returns:
            None

        Example:
            >>> from pathlib import Path
            >>> tracker = CitationGraph(Path('/home/user/knowledge_base'))
        """
        self.knowledge_base_dir = Path(knowledge_base_dir)
        self.knowledge_base_dir.mkdir(parents=True, exist_ok=True)

        if graph_storage_path:
            self.graph_storage_path = Path(graph_storage_path)
        else:
            self.graph_storage_path = self.knowledge_base_dir / 'citation_graph.pkl'

        self.note_generator = note_generator  # Keep for backward compatibility
        self.service_manager = service_manager
        self.pdf_dir = pdf_dir
        self.markdown_dir = markdown_dir
        self.notes_dir = notes_dir

        # Initialize graph
        self.graph: nx.DiGraph = nx.DiGraph()
        
        # Initialize components
        self.storage = CitationStorage(self.graph_storage_path)
        self.graph = self.storage.load_graph()
        
        self.search = CitationSearch(self.graph)
        self.analyzer = GraphAnalyzer(self.graph)
        self.file_manager = CitationFileManager(
            self.graph,
            self.knowledge_base_dir,
            markdown_dir=self.markdown_dir,
            notes_dir=self.notes_dir,
        )

        logger.info(
            f'CitationGraph initialized with {self.graph.number_of_nodes()} nodes '
            f'and {self.graph.number_of_edges()} edges'
        )

    def _load_graph(self) -> None:
        """Load the citation graph from disk (deprecated - handled by storage component)."""
        # This method is kept for backward compatibility
        pass

    def _save_graph(self) -> None:
        """Save the citation graph to disk."""
        self.storage.save_graph(self.graph)

    def _generate_article_id(self, citation: Citation) -> str:
        """
        Generate a unique article ID from citation data.

        Args:
            citation: Citation object

        Returns:
            Unique article ID string
        """
        # Prefer DOI as it's globally unique
        if citation.doi:
            return f'doi_{citation.doi.replace("/", "_").replace(".", "_")}'
        
        # Fallback to sanitized title + year
        if citation.title and citation.year:
            sanitized_title = re.sub(r'[^\w\s-]', '', citation.title)
            sanitized_title = re.sub(r'[-\s]+', '-', sanitized_title)
            return f'{sanitized_title[:50]}_{citation.year}'
        
        # Last resort: use hash of available data
        data_str = f'{citation.title}_{citation.authors}_{citation.year}'
        return f'article_{hash(data_str)}'

    def add_article_from_citation(self, citation: Citation) -> str:
        """
        Add an article to the graph from a Citation object.

        Args:
            citation: Citation object with article metadata

        Returns:
            The article ID in the graph
        """
        article_id = self._generate_article_id(citation)
        
        node_data = {
            'title': citation.title,
            'authors': citation.authors,
            'journal': citation.journal,
            'year': citation.year,
            'doi': citation.doi,
            'abstract': citation.abstract,
            'url': citation.url,
            'embedding': getattr(citation, 'embedding', None),
        }
        
        # Remove None values
        node_data = {k: v for k, v in node_data.items() if v is not None}
        
        self.graph.add_node(article_id, **node_data)
        self._save_graph()
        
        logger.debug(f'Added article {article_id} from citation')
        return article_id

    def _node_exists(self, article_id: str) -> bool:
        """
        Check if a node exists in the graph.

        Args:
            article_id: The article ID to check

        Returns:
            True if the node exists, False otherwise
        """
        return article_id in self.graph

    def add_article(
        self,
        title: str,
        authors: list[str] | None = None,
        journal: str | None = None,
        year: int | None = None,
        doi: str | None = None,
        abstract: str | None = None,
        pdf_path: str | None = None,
        obsidian_path: str | None = None,
        **kwargs,
    ) -> str:
        """
        Add an article to the citation graph.

        Args:
            title: Article title
            authors: List of author names
            journal: Journal name
            year: Publication year
            doi: Digital Object Identifier
            abstract: Article abstract
            pdf_path: Path to the PDF file
            obsidian_path: Path to the Obsidian note
            **kwargs: Additional metadata

        Returns:
            The article ID in the graph
        """
        # Create citation for ID generation
        citation = Citation(
            title=title,
            authors=authors or [],
            journal=journal,
            year=year,
            doi=doi,
            abstract=abstract,
        )
        
        article_id = self._generate_article_id(citation)
        
        # Build node data
        node_data = {
            'title': title,
            'authors': authors or [],
            'journal': journal,
            'year': year,
            'doi': doi,
            'abstract': abstract,
            'pdf_path': pdf_path,
            'obsidian_path': obsidian_path,
        }
        
        # Add any additional metadata
        node_data.update(kwargs)
        
        # Remove None values
        node_data = {k: v for k, v in node_data.items() if v is not None}
        
        # Add or update node
        if article_id in self.graph:
            self.graph.nodes[article_id].update(node_data)
            logger.debug(f'Updated existing article {article_id}')
        else:
            self.graph.add_node(article_id, **node_data)
            logger.debug(f'Added new article {article_id}')
        
        self._save_graph()
        return article_id

    def add_citation(
        self,
        citing_article_id: str,
        cited_article_id: str,
        context: str | None = None,
        confidence: float = 1.0,
    ) -> bool:
        """
        Add a citation relationship between two articles.

        Args:
            citing_article_id: ID of the article that contains the citation
            cited_article_id: ID of the article being cited
            context: Optional context where the citation appears
            confidence: Confidence score for the citation (0.0 to 1.0)

        Returns:
            True if citation was added, False if it already existed
        """
        # Ensure both articles exist
        if citing_article_id not in self.graph:
            logger.warning(f'Citing article {citing_article_id} not found in graph')
            return False
        
        if cited_article_id not in self.graph:
            logger.warning(f'Cited article {cited_article_id} not found in graph')
            return False
        
        # Check if edge already exists
        if self.graph.has_edge(citing_article_id, cited_article_id):
            # Update edge data if provided
            if context or confidence != 1.0:
                edge_data = self.graph.edges[citing_article_id, cited_article_id]
                if context:
                    edge_data['context'] = context
                edge_data['confidence'] = confidence
                self._save_graph()
            return False
        
        # Add the citation edge
        edge_data = {'confidence': confidence}
        if context:
            edge_data['context'] = context
        
        self.graph.add_edge(citing_article_id, cited_article_id, **edge_data)
        self._save_graph()
        
        logger.debug(f'Added citation: {citing_article_id} -> {cited_article_id}')
        return True

    def process_citations(
        self,
        article_id: str,
        analysis_response: AnalysisResponse,
        pdf_path: Path | None = None,
    ) -> dict[str, list[CitationReference]]:
        """
        Process citations from an analysis response and update the graph.

        Args:
            article_id: ID of the article containing the citations
            analysis_response: Analysis response with citation data
            pdf_path: Optional path to the PDF file

        Returns:
            Dictionary with 'found' and 'not_found' citation references
        """
        found_citations = []
        not_found_citations = []
        
        # Update article metadata from analysis
        update_data = {}
        if analysis_response.title:
            update_data['title'] = analysis_response.title
        if analysis_response.abstract:
            update_data['abstract'] = analysis_response.abstract
        if analysis_response.keywords:
            update_data['keywords'] = analysis_response.keywords
        if pdf_path:
            update_data['pdf_path'] = str(pdf_path)
        
        if update_data and article_id in self.graph:
            self.graph.nodes[article_id].update(update_data)
        
        # Process each citation
        for citation in analysis_response.citations:
            # Try to find existing article
            cited_id = None
            
            # Search by DOI first
            if citation.doi:
                cited_id = self.search.search_by_doi(citation.doi)
            
            # If not found by DOI, try to find by title/authors
            if not cited_id and citation.title:
                candidates = self.search.search_articles(citation.title)
                for candidate_id in candidates:
                    candidate_data = self.graph.nodes[candidate_id]
                    # Check if authors match
                    if citation.authors and candidate_data.get('authors'):
                        # Simple author matching - could be improved
                        if any(
                            author in ' '.join(candidate_data['authors'])
                            for author in citation.authors
                        ):
                            cited_id = candidate_id
                            break
            
            # Add article if not found
            if not cited_id:
                cited_id = self.add_article_from_citation(citation)
                not_found_citations.append(CitationReference(cited_id, citation))
            else:
                found_citations.append(CitationReference(cited_id, citation))
            
            # Add citation relationship
            self.add_citation(
                article_id,
                cited_id,
                context=citation.context,
                confidence=citation.confidence or 1.0,
            )
        
        self._save_graph()
        
        logger.info(
            f'Processed {len(analysis_response.citations)} citations for {article_id}: '
            f'{len(found_citations)} found, {len(not_found_citations)} new'
        )
        
        return {
            'found': found_citations,
            'not_found': not_found_citations,
        }

    def get_citation(self, article_id: str) -> Citation | None:
        """
        Get citation data for an article.

        Args:
            article_id: Article ID in the graph

        Returns:
            Citation object if found, None otherwise
        """
        if article_id not in self.graph:
            return None
        
        data = self.graph.nodes[article_id]
        
        return Citation(
            title=data.get('title', ''),
            authors=data.get('authors', []),
            journal=data.get('journal'),
            year=data.get('year'),
            doi=data.get('doi'),
            abstract=data.get('abstract'),
            url=data.get('url'),
            embedding=data.get('embedding'),
        )

    # Delegate to components
    def get_citing_articles(self, article_id: str) -> list[str]:
        """Get all articles that cite a given article."""
        return self.analyzer.get_citing_articles(article_id)

    def get_cited_articles(self, article_id: str) -> list[str]:
        """Get all articles cited by a given article."""
        return self.analyzer.get_cited_articles(article_id)

    def get_obsidian_path(self, article_id: str) -> str | None:
        """Get the Obsidian path for an article."""
        return self.file_manager.get_obsidian_path(article_id)

    def get_article_metadata(self, article_id: str) -> dict[str, Any]:
        """Get all metadata for an article."""
        if article_id not in self.graph:
            return {}
        return dict(self.graph.nodes[article_id])

    def search_articles(self, query: str) -> list[str]:
        """Search for articles by title, author, or DOI."""
        return self.search.search_articles(query)

    def get_citation_network(self, article_id: str, depth: int = 1) -> nx.DiGraph:
        """Get a subgraph of the citation network around an article."""
        return self.analyzer.get_citation_network(article_id, depth)

    def update_obsidian_links(self, article_id: str) -> None:
        """Update Obsidian links in the markdown file for an article."""
        self.file_manager.update_obsidian_links(article_id)
        self._save_graph()

    def _sanitize_title(self, title: str) -> str:
        """Sanitize a title for use as a filename."""
        return self.file_manager.sanitize_title(title)

    def get_article_data_for_regeneration(
        self, article_id: str
    ) -> dict[str, Any] | None:
        """
        Get article data formatted for note regeneration.

        Args:
            article_id: Article ID in the graph

        Returns:
            Dictionary with article data suitable for note generation, or None if not found
        """
        if article_id not in self.graph:
            logger.warning(f'Article {article_id} not found for regeneration')
            return None

        data = self.graph.nodes[article_id]

        # Get citation information
        citing_articles = self.get_citing_articles(article_id)
        cited_articles = self.get_cited_articles(article_id)

        # Format citing articles
        citing_refs = []
        for citing_id in citing_articles:
            if citing_id in self.graph:
                citing_data = self.graph.nodes[citing_id]
                citing_refs.append({
                    'title': citing_data.get('title', 'Unknown'),
                    'authors': citing_data.get('authors', []),
                    'year': citing_data.get('year'),
                    'obsidian_path': citing_data.get('obsidian_path'),
                })

        # Format cited articles
        cited_refs = []
        for cited_id in cited_articles:
            if cited_id in self.graph:
                cited_data = self.graph.nodes[cited_id]
                cited_refs.append({
                    'title': cited_data.get('title', 'Unknown'),
                    'authors': cited_data.get('authors', []),
                    'year': cited_data.get('year'),
                    'doi': cited_data.get('doi'),
                    'obsidian_path': cited_data.get('obsidian_path'),
                })

        # Build the complete data structure
        article_data = {
            'article_id': article_id,
            'title': data.get('title', 'Unknown Title'),
            'authors': data.get('authors', []),
            'journal': data.get('journal'),
            'year': data.get('year'),
            'doi': data.get('doi'),
            'abstract': data.get('abstract'),
            'url': data.get('url'),
            'pdf_path': data.get('pdf_path'),
            'obsidian_path': data.get('obsidian_path'),
            'keywords': data.get('keywords', []),
            'citing_articles': citing_refs,
            'cited_articles': cited_refs,
            'citation_count': len(citing_articles),
            'reference_count': len(cited_articles),
        }

        # Add any additional metadata
        for key, value in data.items():
            if key not in article_data and not key.startswith('_'):
                article_data[key] = value

        return article_data

    def update_article_file_paths(
        self,
        article_id: str,
        pdf_path: Path | None = None,
        obsidian_path: str | None = None,
    ) -> bool:
        """
        Update file paths for an article.

        Args:
            article_id: Article ID in the graph
            pdf_path: New PDF path (optional)
            obsidian_path: New Obsidian note path (optional)

        Returns:
            True if article was updated, False if not found
        """
        if article_id not in self.graph:
            logger.warning(f'Article {article_id} not found for path update')
            return False

        updated = False
        if pdf_path is not None:
            self.graph.nodes[article_id]['pdf_path'] = str(pdf_path)
            updated = True

        if obsidian_path is not None:
            self.graph.nodes[article_id]['obsidian_path'] = obsidian_path
            updated = True

        if updated:
            self._save_graph()
            logger.debug(f'Updated file paths for article {article_id}')

        return updated

    def regenerate_all_notes(self) -> list[tuple[Path, Path]]:
        """
        Regenerate notes for all articles in the graph.

        Returns:
            List of (old_path, new_path) tuples for renamed files
        """
        if not self.service_manager:
            logger.error('Service manager not available for note regeneration')
            return []

        note_service = self.service_manager.get_service('note_service')
        if not note_service:
            logger.error('Note service not available')
            return []

        renamed_files = []
        articles_processed = 0
        articles_failed = 0

        for article_id in self.graph.nodes():
            try:
                article_data = self.get_article_data_for_regeneration(article_id)
                if not article_data:
                    continue

                # Get current obsidian path
                old_obsidian_path = article_data.get('obsidian_path')

                # Generate new note
                result = note_service.generate_note(
                    article_title=article_data['title'],
                    article_authors=article_data['authors'],
                    article_journal=article_data['journal'],
                    article_year=article_data['year'],
                    article_doi=article_data['doi'],
                    article_abstract=article_data['abstract'],
                    article_url=article_data['url'],
                    pdf_path=article_data.get('pdf_path'),
                )

                if result and 'note_path' in result:
                    new_path = Path(result['note_path'])
                    
                    # Update obsidian path in graph
                    new_obsidian_path = new_path.stem  # Remove .md extension
                    self.update_article_file_paths(
                        article_id,
                        obsidian_path=new_obsidian_path
                    )

                    # Track renamed files
                    if old_obsidian_path and old_obsidian_path != new_obsidian_path:
                        old_path = self.notes_dir / f"{old_obsidian_path}.md"
                        if old_path.exists() and old_path != new_path:
                            renamed_files.append((old_path, new_path))

                    articles_processed += 1
                else:
                    articles_failed += 1
                    logger.warning(f'Failed to regenerate note for {article_id}')

            except Exception as e:
                articles_failed += 1
                logger.error(f'Error regenerating note for {article_id}: {e}')

        logger.info(
            f'Regenerated notes: {articles_processed} successful, '
            f'{articles_failed} failed, {len(renamed_files)} renamed'
        )

        return renamed_files

    def update_node_attributes(
        self, article_id: str, **attributes: Any
    ) -> bool:
        """
        Update attributes for a node in the graph.

        Args:
            article_id: Article ID in the graph
            **attributes: Key-value pairs to update

        Returns:
            True if node was updated, False if not found
        """
        if article_id not in self.graph:
            return False

        self.graph.nodes[article_id].update(attributes)
        self._save_graph()
        return True

    # Additional convenience methods
    def get_graph_statistics(self) -> dict[str, Any]:
        """Get overall statistics about the citation graph."""
        return self.analyzer.get_graph_statistics()

    def export_to_json(self, output_path: Path) -> None:
        """Export the graph to JSON format."""
        data = {
            'nodes': [
                {'id': node, **self.graph.nodes[node]}
                for node in self.graph.nodes()
            ],
            'edges': [
                {'source': u, 'target': v, **self.graph.edges[u, v]}
                for u, v in self.graph.edges()
            ],
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f'Exported graph to {output_path}')

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

        self.graph: nx.DiGraph = nx.DiGraph()
        self._load_graph()

        logger.info(
            f'CitationGraph initialized with knowledge base at {knowledge_base_dir}'
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
            >>> tracker = CitationGraph(Path('knowledge_base'))
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
        # For articles added this way, pdf_path and markdown_path are not directly known from citation obj.  # noqa: W505
        # They are typically set for the main processed article.
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
        pdf_path: Path | None = None,
        markdown_path: Path | None = None,
        analysis: AnalysisResponse | dict[str, Any] | None = None,
    ) -> None:
        """
        Add an article to the citation graph.

        Args:
            article_id: Unique identifier for the article (e.g., DOI or sanitized title)
            metadata: Article metadata including title, authors, year, etc.
            obsidian_path: Path to the corresponding Obsidian markdown note if it exists
            pdf_path: Path to the article's PDF file
            markdown_path: Path to the article's markdown file
            analysis: AnalysisResponse object or dictionary containing analysis data

        Returns:
            None

        Example:
            >>> tracker = CitationGraph(Path('knowledge_base'))
            >>> tracker.add_article(
            ...     '10.1234/example',
            ...     {'title': 'Example Paper', 'authors': ['Smith, J.'], 'year': 2023},
            ...     obsidian_path='20230101-example-paper.md',
            ...     pdf_path=Path('papers/example.pdf'),
            ...     markdown_path=Path('notes/example.md'),
            ...     analysis={'summary': 'This is an example paper.'},
            ... )
        """
        node_data = {'metadata': metadata}
        if obsidian_path:
            node_data['obsidian_path'] = (
                obsidian_path  # Should be the note stub/filename
            )
        if pdf_path:
            node_data['pdf_path'] = pdf_path.name  # Store as string (name/stub)
        if markdown_path:
            node_data['markdown_path'] = (
                markdown_path.name
            )  # Store as string (name/stub)
        if analysis:
            if isinstance(analysis, AnalysisResponse):
                node_data['analysis'] = analysis.model_dump()
            else:
                node_data['analysis'] = analysis

        article_title = metadata.get('title', article_id)

        if not self.graph.has_node(article_id):
            # Add new node
            self.graph.add_node(article_id, **node_data)
            logger.info(f'Added article to citation graph: {article_title}')
        else:
            # Update existing node
            existing_node_data = self.graph.nodes[article_id]
            existing_node_data.update(
                node_data
            )  # Merge new data, overwriting if keys exist

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
            >>> tracker = CitationGraph(Path('knowledge_base'))
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

    def process_citations(
        self,
        pdf_path: Path,
        markdown_path: Path,
        analysis: AnalysisResponse,
        citations: list[Citation],
    ) -> str | None:
        """
        Process a list of citations for an article.

        Args:
            pdf_path: Path to the PDF file
            markdown_path: Path to the markdown file
            analysis: AnalysisResponse object
            citations: List of Citation objects

        Returns:
            str | None: The article ID of the processed article or None if it exits early

        Example:
            >>> tracker = CitationGraph(Path('knowledge_base'))
            >>> citations = [
            ...     Citation(
            ...         text='Smith, J. (2023). Example Paper.',
            ...         authors=['Smith, J.'],
            ...         title='Example Paper',
            ...         year=2023,
            ...         is_document_citation=True,  # Mark this as the main article
            ...         doi='10.1234/main_article',
            ...     ),
            ...     Citation(
            ...         text='Jones, A. (2022). Another Paper.',
            ...         authors=['Jones, A.'],
            ...         title='Another Paper',
            ...         year=2022,
            ...         doi='10.5678/cited_article',
            ...     ),
            ... ]
            >>> analysis_response = AnalysisResponse(
            ...     summary='Main article summary', keywords=['test']
            ... )
            >>> article_id = tracker.process_citations(
            ...     Path('path/to/main.pdf'),
            ...     Path('path/to/main.md'),
            ...     analysis_response,
            ...     citations,
            ... )
        """  # noqa: W505
        # Find the citation for the document itself (marked with is_document_citation flag)  # noqa: W505
        article_citation = next(
            (citation for citation in citations if citation.is_document_citation), None
        )

        # If no document citation is found, use the first citation as a fallback
        if article_citation is None and citations:
            # Ensure the first citation is marked, if we decide to use it as the main document.  # noqa: W505
            # This logic might need refinement based on how `is_document_citation` is set.  # noqa: W505
            # For now, we assume if no explicit document citation, the first one might be it.  # noqa: W505
            # However, this could be risky if the first citation is not the document itself.  # noqa: W505
            # A better approach might be to require `is_document_citation` to be set.
            logger.warning(
                "No citation explicitly marked as 'is_document_citation'. "
                'Attempting to use the first citation as the main article. '
                'This may lead to incorrect main article identification.'
            )
            article_citation = citations[0]  # Fallback, consider implications

        if not article_citation:
            logger.error('No valid article citation found, cannot process citations.')
            return None

        # Generate article ID for the main document
        article_id = self._generate_article_id(article_citation)

        # Add or update the main article with all its details
        self.add_article(
            article_id=article_id,
            metadata=article_citation.model_dump(exclude={'obsidian_uri'}),
            obsidian_path=article_citation.obsidian_uri,  # This is the note stub
            pdf_path=pdf_path,  # Pass Path object, add_article will take .name
            markdown_path=markdown_path,  # Pass Path object, add_article will take .name
            analysis=analysis.model_dump(),
        )

        # Process other citations (references made by the main article)
        for citation in citations:
            if citation is article_citation:  # Skip the main article itself
                continue

            # Add the cited article to the graph and get its ID
            target_id = self.add_article_from_citation(citation)

            # Add the citation relationship from the main article to the cited article
            self.add_citation(article_id, target_id, {'citation_text': citation.text})

        # After processing all citations for the current article, regenerate notes for connected articles  # noqa: W505
        if self.service_manager or self.note_generator:
            connected_articles_ids = set()
            # Articles that cite the current article
            connected_articles_ids.update(self.get_citing_articles(article_id))
            # Articles cited by the current article
            connected_articles_ids.update(self.get_cited_articles(article_id))

            for connected_id in connected_articles_ids:
                if (
                    connected_id == article_id
                ):  # Don't regenerate the note we just created/updated
                    continue

                logger.info(
                    f'Attempting to regenerate note for connected article: {connected_id}'
                )
                regen_data = self.get_article_data_for_regeneration(connected_id)
                if regen_data:
                    try:
                        if self.service_manager:
                            # Use NoteService through ServiceManager
                            self.service_manager.note.create_note(
                                pdf_path=regen_data['pdf_path'],
                                markdown_path=regen_data['markdown_path'],
                                analysis=regen_data['analysis'],
                                citations=regen_data['citations'],
                            )
                        elif self.note_generator:
                            # Fallback to legacy note_generator
                            self.note_generator.create_note(
                                pdf_path=regen_data['pdf_path'],
                                markdown_path=regen_data['markdown_path'],
                                analysis=regen_data['analysis'],
                                citations=regen_data['citations'],
                            )
                        logger.info(
                            f'Successfully regenerated note for connected article: {connected_id}'
                        )
                    except Exception as e:
                        logger.error(
                            f'Failed to regenerate note for connected article {connected_id}: {e}'
                        )
                else:
                    logger.warning(
                        f'Could not retrieve data for connected article {connected_id}. Skipping note regeneration.'
                    )
        else:
            logger.debug(
                'Neither ServiceManager nor NoteGenerator configured in CitationGraph. Skipping regeneration of connected notes.'
            )

        return article_id

    def get_citation(self, article_id: str) -> Citation | None:
        """
        Get a Citation object for an article.

        Args:
            article_id: ID of the article

        Returns:
            Citation | None: Citation object if the article exists, None otherwise

        Example:
            >>> tracker = CitationGraph(Path('knowledge_base'))
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
            >>> tracker = CitationGraph(Path('knowledge_base'))
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
            >>> tracker = CitationGraph(Path('knowledge_base'))
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
            >>> tracker = CitationGraph(Path('knowledge_base'))
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
            >>> tracker = CitationGraph(Path('knowledge_base'))
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
            >>> tracker = CitationGraph(Path('knowledge_base'))
            >>> results = tracker.search_articles('machine learning')
            >>> len(results)
            8
        """
        if not query:
            return []

        query = query.lower()
        results = []

        for node_id, node_data in self.graph.nodes(data=True):
            metadata = node_data.get('metadata', {})

            # Search in title - check for None values
            title = metadata.get('title')
            if title and query in title.lower():
                results.append(node_id)
                continue

            # Search in authors - check for None values
            authors = metadata.get('authors', [])
            if authors:
                for author in authors:
                    # Ensure author is not None or empty
                    if author and query in author.lower():
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
            >>> tracker = CitationGraph(Path('knowledge_base'))
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
            >>> tracker = CitationGraph(Path('knowledge_base'))
            >>> tracker.update_obsidian_links('10.1234/article')
        """
        # Get the Obsidian path for the article
        obsidian_path_stub = self.get_obsidian_path(article_id)
        if not obsidian_path_stub:
            logger.warning(f'No Obsidian note found for article {article_id}')
            return

        if not self.notes_dir:
            logger.error(
                'Notes directory not configured in CitationGraph. Cannot update Obsidian links.'
            )
            return

        # Get the full path to the markdown file
        md_path = self.notes_dir / obsidian_path_stub
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

    def get_article_data_for_regeneration(
        self, article_id: str
    ) -> dict[str, Any] | None:
        """
        Retrieve all necessary data for an article to regenerate its note.

        Args:
            article_id: The ID of the article for which to retrieve data.

        Returns:
            A dictionary containing 'pdf_path', 'markdown_path', 'analysis',
            and 'citations' (list of Citation objects) if all data is found.
            Returns None otherwise.
        """
        if not self._node_exists(article_id):
            logger.warning(
                f'Article {article_id} not found. Cannot retrieve data for note regeneration.'
            )
            return None

        node_data = self.graph.nodes[article_id]

        pdf_stub = node_data.get('pdf_path')
        markdown_stub = node_data.get('markdown_path')
        analysis_dict = node_data.get('analysis')
        obsidian_stub = node_data.get('obsidian_path')  # This is the note stub

        if not all([pdf_stub, markdown_stub, analysis_dict]):
            missing_items = []
            if not pdf_stub:
                missing_items.append('PDF path stub')
            if not markdown_stub:
                missing_items.append('Markdown path stub')
            if not analysis_dict:
                missing_items.append('analysis')

            logger.warning(
                f'Missing essential data ({", ".join(missing_items)}) for article {article_id}. '
                'Cannot regenerate note.'
            )
            return None

        if not self.pdf_dir or not self.markdown_dir:
            logger.error(
                'PDF or Markdown directory not configured in CitationGraph. Cannot reconstruct paths.'
            )
            return None

        try:
            pdf_path = self.pdf_dir / pdf_stub
            markdown_path = self.markdown_dir / markdown_stub
            analysis = AnalysisResponse(**analysis_dict)
        except Exception as e:
            logger.error(
                f'Error reconstructing data for article {article_id}: {e}. Cannot regenerate note.'
            )
            return None

        # Get the main citation for this article_id
        main_citation_data = node_data.get('metadata', {})
        if not main_citation_data.get('title'):  # A basic check for valid metadata
            logger.warning(
                f'Missing metadata for main article {article_id}. Cannot regenerate note.'
            )
            return None

        # Pre-process s2_fields_of_study if it exists and is in the wrong format
        if main_citation_data.get('s2_fields_of_study'):
            if isinstance(main_citation_data['s2_fields_of_study'][0], dict):
                main_citation_data['s2_fields_of_study'] = [
                    field.get('category')
                    for field in main_citation_data['s2_fields_of_study']
                    if field.get('category')
                ]

        # Remove 'is_document_citation' from the dictionary before splatting,
        # to avoid "multiple values for keyword argument" error, then explicitly set it.
        main_citation_data.pop('is_document_citation', None)
        main_citation = Citation(**main_citation_data, is_document_citation=True)
        if obsidian_stub:  # Add obsidian_uri if it exists (obsidian_stub from graph)
            main_citation.obsidian_uri = obsidian_stub

        all_citations_for_note = [main_citation]

        # Get all cited articles (successors)
        cited_article_ids = self.get_cited_articles(article_id)
        for cited_id in cited_article_ids:
            cited_node_data = self.graph.nodes.get(cited_id)
            if cited_node_data and 'metadata' in cited_node_data:
                # Pre-process s2_fields_of_study for cited articles
                cited_metadata = cited_node_data['metadata']
                if cited_metadata.get('s2_fields_of_study'):
                    if isinstance(cited_metadata['s2_fields_of_study'][0], dict):
                        cited_metadata['s2_fields_of_study'] = [
                            field.get('category')
                            for field in cited_metadata['s2_fields_of_study']
                            if field.get('category')
                        ]

                citation_obj = self.get_citation(
                    cited_id
                )  # Use existing method to build Citation
                if citation_obj:
                    all_citations_for_note.append(citation_obj)
            else:
                logger.warning(
                    f'Metadata not found for cited article {cited_id} when regenerating for {article_id}'
                )

        # Prepare data for regeneration
        regeneration_data = {
            'pdf_path': pdf_path,
            'markdown_path': markdown_path,
            'analysis': analysis,
            'citations': all_citations_for_note,
        }

        return regeneration_data

    def update_article_file_paths(
        self, article_id: str, new_pdf_path: Path, new_markdown_path: Path
    ) -> None:
        """
        Update the stored PDF and Markdown paths for an article in the graph.

        Args:
            article_id: The ID of the article to update.
            new_pdf_path: The new Path object for the PDF file.
            new_markdown_path: The new Path object for the Markdown file.
        """
        if not self._node_exists(article_id):
            logger.warning(f'Article {article_id} not found. Cannot update file paths.')
            return

        node_data = self.graph.nodes[article_id]
        updated_paths = False
        if new_pdf_path and new_pdf_path.exists():
            node_data['pdf_path'] = new_pdf_path.name
            updated_paths = True
            logger.info(f'Updated pdf_path for {article_id} to {new_pdf_path.name}')
        else:
            logger.warning(
                f'New PDF path for {article_id} is invalid or file does not exist: {new_pdf_path}. Path not updated.'
            )

        if new_markdown_path and new_markdown_path.exists():
            node_data['markdown_path'] = new_markdown_path.name
            updated_paths = True
            logger.info(
                f'Updated markdown_path for {article_id} to {new_markdown_path.name}'
            )
        else:
            logger.warning(
                f'New Markdown path for {article_id} is invalid or file does not exist: {new_markdown_path}. Path not updated.'
            )

        if updated_paths:
            self._save_graph()

    def regenerate_all_notes(self) -> list[tuple[Path, Path]]:
        """
        Regenerate all markdown notes for all articles in the graph.

        This method iterates through each article in the citation graph,
        retrieves its data, uses the NoteService to recreate its
        markdown note, and returns a list of (PDF path, note path) tuples
        for successfully regenerated notes.

        Returns:
            list[tuple[Path, Path]]: A list of tuples, where each tuple
                                     contains the final Path to the PDF file
                                     and the final Path to its regenerated note.
        """
        if not (self.service_manager or self.note_generator):
            logger.error(
                'Neither ServiceManager nor NoteGenerator configured. Cannot regenerate all notes.'
            )
            return []

        logger.info(
            f'Starting regeneration of all notes for {len(self.graph.nodes)} articles.'
        )
        regenerated_count = 0
        failed_count = 0
        successfully_regenerated_files: list[tuple[Path, Path]] = []
        obsidian_paths: dict[str, Path] = {}
        markdown_paths: dict[str, Path] = {}
        pdf_paths: dict[str, Path] = {}

        for article_id in list(self.graph.nodes):  # Iterate over a copy of node IDs
            article_title = (
                self.graph.nodes[article_id]
                .get('metadata', {})
                .get('title', article_id)
            )
            logger.info(f'Attempting to regenerate note for: {article_title}')

            # Get the path to the old note before regeneration
            old_note_stub = self.graph.nodes[article_id].get('obsidian_path')
            old_note_path = (
                self.notes_dir / old_note_stub
                if self.notes_dir and old_note_stub
                else None
            )

            regeneration_data = self.get_article_data_for_regeneration(article_id)

            if regeneration_data:
                try:
                    if self.service_manager:
                        # Use NoteService through ServiceManager
                        (
                            note_path,
                            final_pdf_path,
                            markdown_path,
                        ) = self.service_manager.note.create_note(
                            pdf_path=regeneration_data['pdf_path'],
                            markdown_path=regeneration_data['markdown_path'],
                            analysis=regeneration_data['analysis'],
                            citations=regeneration_data['citations'],
                        )
                    elif self.note_generator:
                        # Fallback to legacy note_generator
                        (
                            note_path_str,
                            final_pdf_path,
                            markdown_path,
                        ) = self.note_generator.create_note(
                            pdf_path=regeneration_data['pdf_path'],
                            markdown_path=regeneration_data['markdown_path'],
                            analysis=regeneration_data['analysis'],
                            citations=regeneration_data['citations'],
                        )
                        note_path = Path(note_path_str)

                    # After successful creation, delete the old note if
                    # the path has changed
                    if (
                        old_note_path
                        and old_note_path.exists()
                        and old_note_path != note_path
                    ):
                        old_note_path.unlink()
                        logger.info(f'Deleted old note file: {old_note_path}')

                    logger.info(
                        f'Successfully regenerated note for: {article_title} at {note_path}'
                    )
                    regenerated_count += 1
                    successfully_regenerated_files.append((final_pdf_path, note_path))
                    obsidian_paths[article_id] = str(note_path)
                    markdown_paths[article_id] = str(markdown_path)
                    pdf_paths[article_id] = str(final_pdf_path)
                except Exception as e:
                    logger.error(
                        f'Failed to regenerate note for {article_title} (ID: {article_id}): {e}'
                    )
                    failed_count += 1
            else:
                logger.warning(
                    f'Could not retrieve sufficient data for {article_title} (ID: {article_id}). Skipping note regeneration.'
                )
                failed_count += 1

        logger.info(
            f'Finished regenerating notes. Successfully regenerated: {regenerated_count}, Failed: {failed_count}.'
        )

        self.update_node_attributes(
            attribute_name='obsidian_path',
            id_to_value_mapping=obsidian_paths,
        )
        self.update_node_attributes(
            attribute_name='markdown_path',
            id_to_value_mapping=markdown_paths,
        )
        self.update_node_attributes(
            attribute_name='pdf_path',
            id_to_value_mapping=pdf_paths,
        )

        self._save_graph()
        return successfully_regenerated_files

    def update_node_attributes(
        self, attribute_name: str, id_to_value_mapping: dict[str, Any]
    ) -> None:
        """
        Update or add a specific attribute for multiple nodes in the graph.

        If a value in the mapping is `None`, the corresponding node attribute
        will be set to `None`. This method only sets attribute values;
        it does not delete attributes if a value is `None` (it sets the attribute to `None`).

        Args:
            attribute_name: The name of the node attribute to update or add.
            id_to_value_mapping: A dictionary mapping article_id to the new
                                 value for the specified attribute.
        """  # noqa: W505
        if not attribute_name:
            logger.error('Attribute name cannot be empty.')
            return

        if not id_to_value_mapping:
            logger.info(
                f"Received an empty mapping for attribute '{attribute_name}'. No updates to perform."
            )
            return

        logger.info(
            f"Starting to update attribute '{attribute_name}' for specified nodes."
        )

        processed_existing_nodes_count = 0
        actually_changed_count = 0
        nodes_not_found_count = 0

        for node_id, new_value in id_to_value_mapping.items():
            if self.graph.has_node(node_id):
                processed_existing_nodes_count += 1
                node_data = self.graph.nodes[node_id]
                current_value = node_data.get(attribute_name)

                if current_value != new_value:
                    node_data[attribute_name] = new_value
                    actually_changed_count += 1
                    logger.debug(
                        f"Set attribute '{attribute_name}' to '{new_value}' for node {node_id}"
                    )
            else:
                logger.warning(
                    f"Node {node_id} not found in graph. Cannot update attribute '{attribute_name}'."
                )
                nodes_not_found_count += 1

        if actually_changed_count > 0:
            logger.info(
                f"Attribute '{attribute_name}' was newly set or changed for {actually_changed_count} "
                f'out of {processed_existing_nodes_count} processed existing nodes.'
            )
            self._save_graph()
        elif processed_existing_nodes_count > 0:
            logger.info(
                f"Processed {processed_existing_nodes_count} existing nodes for attribute '{attribute_name}'. "
                'No values required changing.'
            )
        else:  # Only if id_to_value_mapping was not empty but all nodes were not found
            logger.info(
                f"No existing nodes were updated for attribute '{attribute_name}' as no specified nodes were found in the graph."
            )

        if nodes_not_found_count > 0:
            logger.warning(
                f'{nodes_not_found_count} nodes specified in the mapping were not found in the graph.'
            )

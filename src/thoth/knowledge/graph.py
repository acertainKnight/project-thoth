"""
Citation graph module for maintaining a knowledge graph of article citations.

This module provides functionality to track articles and their citations,
enabling proper linking between Obsidian markdown notes.
"""

import json
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
        knowledge_base_dir: str
        | Path
        | None = None,  # Deprecated, kept for compatibility
        graph_storage_path: str
        | Path
        | None = None,  # Deprecated, kept for compatibility
        note_generator: Any | None = None,  # Deprecated
        pdf_dir: Path | None = None,
        markdown_dir: Path | None = None,
        notes_dir: Path | None = None,
        service_manager: 'ServiceManager | None' = None,
        config: 'Config | None' = None,  # CRITICAL FIX: Accept config to avoid creating new instance
    ) -> None:
        """
        Initialize the CitationGraph (database-only, no file system dependencies).

        Args:
            knowledge_base_dir: DEPRECATED - No longer used (database-only)
            graph_storage_path: DEPRECATED - No longer used (database-only)
            note_generator: Deprecated - use service_manager instead
            pdf_dir: Directory where PDF files are stored
            markdown_dir: Directory where markdown files are stored
            notes_dir: Directory where notes are stored
            service_manager: ServiceManager instance for accessing services

        Returns:
            None

        Example:
            >>> tracker = CitationGraph()  # Loads from PostgreSQL automatically
        """
        # Legacy parameters kept for backward compatibility but not used
        # All data is loaded from PostgreSQL - no file system dependencies
        self.note_generator = note_generator  # Keep for backward compatibility
        self.service_manager = service_manager
        self.pdf_dir = pdf_dir
        self.markdown_dir = markdown_dir
        self.notes_dir = notes_dir
        # CRITICAL FIX: Store config to avoid creating new instance later
        self.config = config

        self.graph: nx.DiGraph = nx.DiGraph()
        self._load_graph()

        logger.info('CitationGraph initialized (database-only mode)')

    def _run_async(self, coro):
        """
        Run async function in appropriate context.

        Detects if we're already in an async context and handles accordingly:
        - If in async context: schedules task in existing loop
        - If not: creates new loop with asyncio.run()

        Args:
            coro: Coroutine to execute

        Returns:
            Result of the coroutine execution
        """
        import asyncio

        try:
            # Try to get the running loop
            loop = asyncio.get_running_loop()
            # We're in an async context - need to handle this carefully
            # We can't use run_until_complete on a running loop, so we'll
            # need to use a different approach
            import threading

            # Create a new thread with its own event loop
            result = [None]
            exception = [None]

            def run_in_thread():
                try:
                    # Create a fresh event loop for this thread (threads don't share loops)
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result[0] = new_loop.run_until_complete(coro)
                    finally:
                        # Always close the loop even if coroutine fails
                        new_loop.close()
                except Exception as e:
                    exception[0] = e

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()

            if exception[0]:
                raise exception[0]
            return result[0]

        except RuntimeError:
            # No running loop - safe to use asyncio.run()
            return asyncio.run(coro)

    def _load_graph(self) -> None:
        """
        Load the citation graph from PostgreSQL, with fallback to legacy JSON file.
        """
        try:
            self._load_from_postgres()
        except Exception as e:
            logger.error(f'Error loading citation graph from PostgreSQL: {e}')
            # Try loading from legacy JSON file as fallback
            try:
                self._load_from_json_legacy()
            except Exception as json_error:
                logger.warning(f'Failed to load from legacy JSON file: {json_error}')
                self.graph = nx.DiGraph()

    def _load_from_json_legacy(self) -> None:
        """Load graph from legacy JSON file (fallback for migration)."""
        from thoth.config import Config

        config = Config()
        json_path = config.graph_storage_path

        if not Path(json_path).exists():
            raise FileNotFoundError(f'Legacy graph file not found: {json_path}')

        logger.info(f'Loading graph from legacy JSON file: {json_path}')

        with open(json_path) as f:
            data = json.load(f)

        # Convert node-link JSON to NetworkX graph
        self.graph = nx.node_link_graph(data, edges='links')

        logger.success(
            f'Loaded {len(self.graph.nodes)} nodes and {len(self.graph.edges)} edges from legacy JSON file'
        )

    def _load_from_postgres(self) -> None:
        """Load graph from PostgreSQL."""

        import asyncpg

        # CRITICAL FIX: Use existing config instead of creating new instance
        if self.config is None:
            from thoth.config import config as global_config

            config = global_config
        else:
            config = self.config

        db_url = (
            getattr(config.secrets, 'database_url', None)
            if hasattr(config, 'secrets')
            else None
        )
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        async def load():
            conn = await asyncpg.connect(db_url)
            try:
                # Load papers (nodes)
                papers = await conn.fetch('SELECT * FROM papers')
                for paper in papers:
                    self.graph.add_node(
                        paper['doi'] or f'title:{paper["title"]}', **dict(paper)
                    )

                # Load citations (edges)
                citations = await conn.fetch("""
                    SELECT
                        p1.doi as source_doi,
                        p1.title as source_title,
                        p2.doi as target_doi,
                        p2.title as target_title,
                        c.citation_context as context
                    FROM citations c
                    JOIN papers p1 ON c.citing_paper_id = p1.id
                    JOIN papers p2 ON c.cited_paper_id = p2.id
                """)
                for citation in citations:
                    # Use DOI if available, otherwise fall back to title-based ID
                    source_node = (
                        citation['source_doi'] or f'title:{citation["source_title"]}'
                    )
                    target_node = (
                        citation['target_doi'] or f'title:{citation["target_title"]}'
                    )

                    # Skip if either node ID is invalid
                    if not source_node or not target_node:
                        logger.warning(
                            f'Skipping citation with invalid node IDs: source={source_node}, target={target_node}'
                        )
                        continue

                    self.graph.add_edge(
                        source_node, target_node, context=citation['context']
                    )

                logger.info(
                    f'Loaded {len(papers)} papers and {len(citations)} citations from PostgreSQL'
                )
            finally:
                await conn.close()

        self._run_async(load())

    def _save_graph(self) -> None:
        """
        Save the citation graph to PostgreSQL.
        """
        try:
            self._save_to_postgres()
        except Exception as e:
            logger.error(f'Error saving citation graph: {e}')

    def _save_to_postgres(self) -> None:
        """Save graph to PostgreSQL."""
        import json as json_lib

        import asyncpg

        from thoth.config import Config

        config = Config()
        db_url = (
            getattr(config.secrets, 'database_url', None)
            if hasattr(config, 'secrets')
            else None
        )
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        async def save():
            conn = await asyncpg.connect(db_url)
            try:
                # Track successes and failures
                nodes_processed = 0
                nodes_inserted = 0
                nodes_updated = 0
                nodes_skipped = 0

                # Save papers (nodes) with markdown content
                for node_id, data in self.graph.nodes(data=True):
                    try:
                        nodes_processed += 1
                        # Get metadata dict (contains doi, arxiv_id, title, etc.)
                        metadata = data.get('metadata', {})

                        # Skip nodes without title (required field)
                        if not metadata.get('title'):
                            nodes_skipped += 1
                            continue

                        # Try to load markdown content if path exists
                        markdown_content = None
                        if data.get('markdown_path'):
                            try:
                                from pathlib import Path

                                markdown_file = Path(data['markdown_path'])
                                if markdown_file.exists():
                                    markdown_content = markdown_file.read_text(
                                        encoding='utf-8'
                                    )
                            except Exception:
                                pass

                        # Get analysis data - stored as 'analysis' in graph, save as 'analysis_data' in DB
                        analysis_data = data.get('analysis', {})

                        # Extract tags from analysis_data to also store in keywords field
                        keywords = (
                            analysis_data.get('tags', [])
                            if isinstance(analysis_data, dict)
                            else []
                        )

                        # Convert lists and dicts to JSON strings for JSONB columns
                        authors_json = json_lib.dumps(metadata.get('authors', []))
                        analysis_json = (
                            json_lib.dumps(analysis_data) if analysis_data else None
                        )
                        keywords_json = json_lib.dumps(keywords) if keywords else None

                        # Handle multiple unique constraints (doi, arxiv_id, title) by checking for existing paper first
                        doi = metadata.get('doi')
                        arxiv_id = metadata.get('arxiv_id')
                        title = metadata.get('title')

                        # Validate year - must be >= 1900 per database constraint
                        year = metadata.get('year')
                        if year and (year < 1900 or year > 2100):
                            year = None  # Set to NULL if outside valid range

                        # Try to find existing paper by any identifier (check all unique constraints)
                        existing = await conn.fetchrow(
                            """
                            SELECT id FROM papers
                            WHERE ($1::text IS NOT NULL AND $1 != '' AND doi = $1)
                               OR ($2::text IS NOT NULL AND $2 != '' AND arxiv_id = $2)
                               OR ($3::text IS NOT NULL AND title = $3)
                            LIMIT 1
                        """,
                            doi,
                            arxiv_id,
                            title,
                        )

                        if existing:
                            # Update existing paper
                            # Extract schema metadata from analysis_data if present
                            schema_name = 'default'
                            schema_version = 'default'
                            if analysis_json and isinstance(analysis_json, dict):
                                schema_name = analysis_json.get(
                                    '_schema_name', 'default'
                                )
                                schema_version = analysis_json.get(
                                    '_schema_version', 'default'
                                )

                            await conn.execute(
                                """
                                UPDATE papers SET
                                    doi = COALESCE(NULLIF($1, ''), doi),
                                    arxiv_id = COALESCE(NULLIF($2, ''), arxiv_id),
                                    title = $3,
                                    authors = $4::jsonb,
                                    abstract = COALESCE($5, abstract),
                                    year = COALESCE($6, year),
                                    venue = COALESCE($7, venue),
                                    pdf_path = COALESCE($8, pdf_path),
                                    note_path = COALESCE($9, note_path),
                                    markdown_content = COALESCE($10, markdown_content),
                                    analysis_data = $11::jsonb,
                                    llm_model = COALESCE($12, llm_model),
                                    keywords = $13::jsonb,
                                    analysis_schema_name = $14,
                                    analysis_schema_version = $15,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = $16
                            """,
                                doi,
                                arxiv_id,
                                title,
                                authors_json,
                                metadata.get('abstract'),
                                year,
                                metadata.get('venue'),
                                data.get('pdf_path'),
                                data.get('note_path'),
                                markdown_content,
                                analysis_json,
                                data.get('llm_model'),
                                keywords_json,
                                schema_name,
                                schema_version,
                                existing['id'],
                            )
                            nodes_updated += 1
                        else:
                            # Try to insert new paper - may still fail due to unique constraints
                            try:
                                # Extract schema metadata from analysis_data if present
                                schema_name = 'default'
                                schema_version = 'default'
                                if analysis_json and isinstance(analysis_json, dict):
                                    schema_name = analysis_json.get(
                                        '_schema_name', 'default'
                                    )
                                    schema_version = analysis_json.get(
                                        '_schema_version', 'default'
                                    )

                                await conn.execute(
                                    """
                                    INSERT INTO papers (doi, arxiv_id, title, authors, abstract, year, venue, pdf_path, note_path, markdown_content, analysis_data, llm_model, keywords, analysis_schema_name, analysis_schema_version)
                                    VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13::jsonb, $14, $15)
                                """,
                                    doi,
                                    arxiv_id,
                                    title,
                                    authors_json,
                                    metadata.get('abstract'),
                                    year,
                                    metadata.get('venue'),
                                    data.get('pdf_path'),
                                    data.get('note_path'),
                                    markdown_content,
                                    analysis_json,
                                    data.get('llm_model'),
                                    keywords_json,
                                    schema_name,
                                    schema_version,
                                )
                                nodes_inserted += 1
                            except asyncpg.exceptions.UniqueViolationError:
                                # If insert fails due to unique constraint, find and update the conflicting paper
                                existing = await conn.fetchrow(
                                    """
                                    SELECT id FROM papers
                                    WHERE ($1::text IS NOT NULL AND $1 != '' AND doi = $1)
                                       OR ($2::text IS NOT NULL AND $2 != '' AND arxiv_id = $2)
                                       OR ($3::text IS NOT NULL AND title = $3)
                                    LIMIT 1
                                """,
                                    doi,
                                    arxiv_id,
                                    title,
                                )
                                if existing:
                                    await conn.execute(
                                        """
                                        UPDATE papers SET
                                            doi = COALESCE(NULLIF($1, ''), doi),
                                            arxiv_id = COALESCE(NULLIF($2, ''), arxiv_id),
                                            title = $3,
                                            authors = $4::jsonb,
                                            abstract = COALESCE($5, abstract),
                                            year = COALESCE($6, year),
                                            venue = COALESCE($7, venue),
                                            pdf_path = COALESCE($8, pdf_path),
                                            note_path = COALESCE($9, note_path),
                                            markdown_content = COALESCE($10, markdown_content),
                                            analysis_data = $11::jsonb,
                                            llm_model = COALESCE($12, llm_model),
                                            keywords = $13::jsonb,
                                            updated_at = CURRENT_TIMESTAMP
                                        WHERE id = $14
                                    """,
                                        doi,
                                        arxiv_id,
                                        title,
                                        authors_json,
                                        metadata.get('abstract'),
                                        year,
                                        metadata.get('venue'),
                                        data.get('pdf_path'),
                                        data.get('note_path'),
                                        markdown_content,
                                        analysis_json,
                                        data.get('llm_model'),
                                        keywords_json,
                                        existing['id'],
                                    )
                                    nodes_updated += 1
                    except Exception as e:
                        # Log error but continue processing other nodes
                        logger.debug(f'Error processing node {node_id}: {e}')
                        nodes_skipped += 1
                        continue

                # Save citations (edges) with full metadata
                for source, target, edge_data in self.graph.edges(data=True):
                    try:
                        # Extract all citation metadata from edge data
                        citation_text = edge_data.get('citation_text') or edge_data.get(
                            'data', {}
                        ).get('citation_text')
                        citation_context = edge_data.get('context') or edge_data.get(
                            'citation_context'
                        )
                        extracted_title = edge_data.get(
                            'extracted_title'
                        ) or edge_data.get('data', {}).get('extracted_title')
                        extracted_authors = edge_data.get(
                            'extracted_authors'
                        ) or edge_data.get('data', {}).get('extracted_authors')
                        extracted_year = edge_data.get(
                            'extracted_year'
                        ) or edge_data.get('data', {}).get('extracted_year')
                        extracted_venue = edge_data.get(
                            'extracted_venue'
                        ) or edge_data.get('data', {}).get('extracted_venue')
                        is_influential = edge_data.get(
                            'is_influential'
                        ) or edge_data.get('data', {}).get('is_influential')
                        section = edge_data.get('section') or edge_data.get(
                            'data', {}
                        ).get('section')
                        citation_order = edge_data.get(
                            'citation_order'
                        ) or edge_data.get('data', {}).get('citation_order')

                        # Convert authors list to JSON if present
                        authors_json = (
                            json_lib.dumps(extracted_authors)
                            if extracted_authors
                            else None
                        )

                        # Get node metadata to access all available identifiers
                        source_node_data = self.graph.nodes[source]
                        target_node_data = self.graph.nodes[target]

                        source_metadata = source_node_data.get('metadata', {})
                        target_metadata = target_node_data.get('metadata', {})

                        # Extract identifiers with priority: DOI > ArXiv > Title
                        # Strip version suffixes from arxiv IDs (e.g., 1802.04223v2 -> 1802.04223)
                        import re

                        def get_identifiers(node_id, metadata):
                            """Extract all available identifiers from node metadata."""
                            identifiers = {}

                            # DOI (highest priority)
                            doi = metadata.get('doi')
                            if doi:
                                identifiers['doi'] = doi

                            # ArXiv ID
                            arxiv_id = metadata.get('arxiv_id')
                            if arxiv_id:
                                # Strip version suffix
                                identifiers['arxiv'] = re.sub(r'v\d+$', '', arxiv_id)

                            # Title (fallback)
                            title = metadata.get('title')
                            if title:
                                identifiers['title'] = title

                            return identifiers

                        source_ids = get_identifiers(source, source_metadata)
                        target_ids = get_identifiers(target, target_metadata)

                        # Build SQL query that tries DOI > ArXiv > Title for each node
                        # This ensures we find papers even if they were indexed by title but now have DOI
                        source_query = """(
                            SELECT id FROM papers
                            WHERE ($1::text IS NOT NULL AND doi = $1)
                               OR ($2::text IS NOT NULL AND arxiv_id = $2)
                               OR ($3::text IS NOT NULL AND title = $3)
                            LIMIT 1
                        )"""

                        target_query = """(
                            SELECT id FROM papers
                            WHERE ($4::text IS NOT NULL AND doi = $4)
                               OR ($5::text IS NOT NULL AND arxiv_id = $5)
                               OR ($6::text IS NOT NULL AND title = $6)
                            LIMIT 1
                        )"""

                        await conn.execute(
                            f"""
                            INSERT INTO citations (
                                citing_paper_id,
                                cited_paper_id,
                                citation_text,
                                citation_context,
                                extracted_title,
                                extracted_authors,
                                extracted_year,
                                extracted_venue,
                                is_influential,
                                section,
                                citation_order
                            )
                            VALUES (
                                {source_query},
                                {target_query},
                                $7, $8, $9, $10::jsonb, $11, $12, $13, $14, $15
                            )
                            ON CONFLICT (citing_paper_id, cited_paper_id) DO UPDATE SET
                                citation_text = COALESCE(EXCLUDED.citation_text, citations.citation_text),
                                citation_context = COALESCE(EXCLUDED.citation_context, citations.citation_context),
                                extracted_title = COALESCE(EXCLUDED.extracted_title, citations.extracted_title),
                                extracted_authors = COALESCE(EXCLUDED.extracted_authors, citations.extracted_authors),
                                extracted_year = COALESCE(EXCLUDED.extracted_year, citations.extracted_year),
                                extracted_venue = COALESCE(EXCLUDED.extracted_venue, citations.extracted_venue),
                                is_influential = COALESCE(EXCLUDED.is_influential, citations.is_influential),
                                section = COALESCE(EXCLUDED.section, citations.section),
                                citation_order = COALESCE(EXCLUDED.citation_order, citations.citation_order),
                                updated_at = CURRENT_TIMESTAMP
                        """,
                            source_ids.get('doi'),
                            source_ids.get('arxiv'),
                            source_ids.get('title'),
                            target_ids.get('doi'),
                            target_ids.get('arxiv'),
                            target_ids.get('title'),
                            citation_text,
                            citation_context,
                            extracted_title,
                            authors_json,
                            extracted_year,
                            extracted_venue,
                            is_influential,
                            section,
                            citation_order,
                        )
                    except Exception as e:
                        # Log error but continue processing other citations
                        logger.debug(
                            f'Error saving citation from {source} to {target}: {e}'
                        )
                        continue

                logger.info(
                    f'Saved graph to PostgreSQL: {nodes_inserted} inserted, {nodes_updated} updated, {nodes_skipped} skipped from {nodes_processed} nodes'
                )
            finally:
                await conn.close()

        self._run_async(save())

    def _save_markdown_content_to_postgres(
        self, article_id: str, markdown_content: str, markdown_path: str
    ) -> None:
        """
        Save markdown_content to processed_papers table for embeddings generation.

        The 'papers' is a VIEW, so we update the underlying processed_papers table
        by looking up the paper_id from paper_metadata first.

        Args:
            article_id: The article ID (doi:xxx, arxiv:xxx, or title:xxx)
            markdown_content: Full markdown text without images (for embeddings)
            markdown_path: Path to markdown file (for reference)
        """

        import asyncpg

        from thoth.config import Config

        config = Config()
        db_url = getattr(config.secrets, 'database_url', None)

        if not db_url:
            logger.warning('No database_url configured, skipping markdown_content save')
            return

        async def save():
            conn = await asyncpg.connect(db_url)
            try:
                # Extract identifier from article_id (format: "doi:10.1234" or "arxiv:1234.5678" or "title:xxx")
                id_type, id_value = (
                    article_id.split(':', 1)
                    if ':' in article_id
                    else ('title', article_id)
                )

                # First, find paper_id from paper_metadata
                if id_type == 'doi':
                    paper_id = await conn.fetchval(
                        'SELECT id FROM paper_metadata WHERE doi = $1', id_value
                    )
                elif id_type == 'arxiv':
                    paper_id = await conn.fetchval(
                        'SELECT id FROM paper_metadata WHERE arxiv_id = $1', id_value
                    )
                else:  # title-based
                    paper_id = await conn.fetchval(
                        'SELECT id FROM paper_metadata WHERE LOWER(title) = LOWER($1)',
                        id_value,
                    )

                if paper_id is None:
                    logger.warning(
                        f'No paper found with {id_type}={id_value}, markdown_content not saved'
                    )
                    return

                # Update or insert into processed_papers
                result = await conn.execute(
                    """
                    INSERT INTO processed_papers (paper_id, markdown_content, markdown_path, created_at, updated_at)
                    VALUES ($1, $2, $3, NOW(), NOW())
                    ON CONFLICT (paper_id) DO UPDATE SET
                        markdown_content = EXCLUDED.markdown_content,
                        markdown_path = EXCLUDED.markdown_path,
                        updated_at = NOW()
                """,
                    paper_id,
                    markdown_content,
                    markdown_path,
                )

                logger.info(
                    f'Saved markdown_content for {article_id} ({len(markdown_content)} chars)'
                )

            except Exception as e:
                logger.error(f'Error saving markdown_content to PostgreSQL: {e}')
            finally:
                await conn.close()

        self._run_async(save())

    def _generate_article_id(self, citation: Citation) -> str:
        """
        Generate a consistent article ID from a citation using ID hierarchy.

        Priority: DOI > ArXiv ID > backup_id > Title
        This ensures we use the most reliable and standardized identifier first.

        Args:
            citation: Citation object containing article metadata

        Returns:
            str: The generated article ID (e.g., 'doi:10.1234/example', 'arxiv:2301.12345', 'title:Paper Title')
        """
        # Priority 1: DOI (most reliable, globally unique)
        if citation.doi:
            return f'doi:{citation.doi}'

        # Priority 2: ArXiv ID (reliable for preprints)
        if hasattr(citation, 'arxiv_id') and citation.arxiv_id:
            # Strip version suffix if present (e.g., 2301.12345v2 -> 2301.12345)
            import re

            arxiv_id = re.sub(r'v\d+$', '', citation.arxiv_id)
            return f'arxiv:{arxiv_id}'

        # Priority 3: backup_id (from external services like Semantic Scholar)
        if hasattr(citation, 'backup_id') and citation.backup_id:
            return citation.backup_id

        # Priority 4: Title (fallback, least reliable due to variations)
        title = citation.title or citation.text
        if title:
            return f'title:{self._sanitize_title(title)}'

        # Priority 5: Generate from authors if available
        if citation.authors and len(citation.authors) > 0:
            author_part = (
                citation.authors[0].split()[0] if citation.authors[0] else 'unknown'
            )
            import uuid

            return f'unknown:{author_part}-{uuid.uuid4().hex[:8]}'

        # Last resort: generate unique ID
        import uuid

        return f'unknown:{uuid.uuid4().hex}'

    def add_article_from_citation(
        self, citation: Citation, batch_mode: bool = False
    ) -> str:
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
        self.add_article(
            article_id, metadata, citation.obsidian_uri, batch_mode=batch_mode
        )

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
        llm_model: str | None = None,
        batch_mode: bool = False,
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
            llm_model: Name of the LLM model used for analysis (e.g., "google/gemini-2.5-flash")

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
            ...     llm_model='google/gemini-2.5-flash',
            ... )
        """
        node_data = {'metadata': metadata}
        if obsidian_path:
            node_data['obsidian_path'] = (
                obsidian_path  # Should be the note stub/filename
            )
        if pdf_path:
            node_data['pdf_path'] = str(pdf_path)  # Store full path as string
        if markdown_path:
            node_data['markdown_path'] = str(markdown_path)  # Store full path as string
        if analysis:
            if isinstance(analysis, AnalysisResponse):
                node_data['analysis'] = analysis.model_dump()
            else:
                node_data['analysis'] = analysis
        if llm_model:
            node_data['llm_model'] = llm_model

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

        if not batch_mode:
            self._save_graph()

    def add_citation(
        self,
        source_id: str,
        target_id: str,
        citation_data: dict[str, Any] | None = None,
        batch_mode: bool = False,
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
        if not batch_mode:
            self._save_graph()

    def process_citations(
        self,
        pdf_path: Path,
        markdown_path: Path,
        analysis: AnalysisResponse,
        citations: list[Citation],
        llm_model: str | None = None,
        no_images_markdown: str | None = None,
    ) -> str | None:
        """
        Process a list of citations for an article.

        Args:
            pdf_path: Path to the PDF file
            markdown_path: Path to the markdown file
            analysis: AnalysisResponse object
            citations: List of Citation objects
            llm_model: Name of the LLM model used for analysis
            no_images_markdown: Full markdown content without images (for embeddings)

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

        # Add schema metadata to analysis if not already present
        if analysis and not isinstance(analysis, dict):
            # Convert Pydantic model to dict and add schema metadata
            analysis_dict = analysis.model_dump()
            # Try to get schema info from service manager if available
            if self.service_manager and hasattr(self.service_manager, 'processing'):
                try:
                    schema_service = (
                        self.service_manager.processing.analysis_schema_service
                    )
                    analysis_dict['_schema_name'] = (
                        schema_service.get_active_preset_name()
                    )
                    analysis_dict['_schema_version'] = (
                        schema_service.get_schema_version()
                    )
                except Exception as e:
                    logger.debug(f'Could not get schema metadata: {e}')
                    analysis_dict['_schema_name'] = 'default'
                    analysis_dict['_schema_version'] = 'default'
            else:
                analysis_dict['_schema_name'] = 'default'
                analysis_dict['_schema_version'] = 'default'
            analysis = analysis_dict
        elif isinstance(analysis, dict) and '_schema_name' not in analysis:
            # Dict provided but no schema metadata
            analysis['_schema_name'] = 'default'
            analysis['_schema_version'] = 'default'

        # Add or update the main article with all its details
        self.add_article(
            article_id=article_id,
            metadata=article_citation.model_dump(exclude={'obsidian_uri'}),
            obsidian_path=article_citation.obsidian_uri,  # This is the note stub
            pdf_path=pdf_path,  # Pass Path object, add_article will take .name
            markdown_path=markdown_path,  # Pass Path object, add_article will take .name
            analysis=analysis if isinstance(analysis, dict) else analysis.model_dump(),
            llm_model=llm_model,
        )

        # Save markdown_content to papers table for embeddings
        if no_images_markdown:
            self._save_markdown_content_to_postgres(
                article_id, no_images_markdown, str(markdown_path)
            )

        # Process other citations (references made by the main article)
        # Use batch mode to defer saves until all citations are processed
        logger.info(
            f'Processing {len(citations) - 1} reference citations in batch mode'
        )
        for citation in citations:
            if citation is article_citation:  # Skip the main article itself
                continue

            # Add the cited article to the graph and get its ID (batch mode)
            target_id = self.add_article_from_citation(citation, batch_mode=True)

            # Add the citation relationship with full metadata (batch mode)
            citation_data = {
                'citation_text': citation.text,
                'extracted_title': citation.title,
                'extracted_authors': citation.authors,
                'extracted_year': citation.year,
                'extracted_venue': citation.venue or citation.journal,
                'is_influential': citation.influential_citation_count
                and citation.influential_citation_count > 0,
                # Note: citation_context, section, and citation_order would need to come from text analysis
                # These are not available in the Citation object itself
            }
            self.add_citation(article_id, target_id, citation_data, batch_mode=True)

        # Save once after all citations are processed
        logger.info(
            f'Batch processing complete, saving {len(citations) - 1} citations to database'
        )
        self._save_graph()

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
        if not title:
            return 'untitled'

        # Replace spaces with hyphens and remove special characters
        sanitized = ''.join(
            c.lower() if c.isalnum() or c.isspace() else '-' for c in title
        )
        sanitized = '-'.join(filter(None, sanitized.split()))
        return sanitized or 'untitled'

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
            node_data['pdf_path'] = str(new_pdf_path)  # Store full path
            updated_paths = True
            logger.info(f'Updated pdf_path for {article_id} to {new_pdf_path}')
        else:
            logger.warning(
                f'New PDF path for {article_id} is invalid or file does not exist: {new_pdf_path}. Path not updated.'
            )

        if new_markdown_path and new_markdown_path.exists():
            node_data['markdown_path'] = str(new_markdown_path)  # Store full path
            updated_paths = True
            logger.info(
                f'Updated markdown_path for {article_id} to {new_markdown_path}'
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

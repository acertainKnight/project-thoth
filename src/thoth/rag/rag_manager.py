"""
RAG Manager for Thoth.

This module provides the main interface for the Retrieval-Augmented Generation
system, coordinating embeddings, vector storage, and question answering.
"""

from pathlib import Path  # noqa: I001
from typing import Any

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from loguru import logger

from thoth.rag.embeddings import EmbeddingManager
from thoth.rag.vector_store import VectorStoreManager
from thoth.rag.reranker import create_reranker, BaseReranker
from thoth.rag.contextual_enrichment import ContextualEnricher
from thoth.rag.query_router import QueryRouter
from thoth.rag.agentic_retrieval import AgenticRAGOrchestrator
from thoth.rag.document_grader import DocumentGrader
from thoth.rag.hallucination_checker import HallucinationChecker
from thoth.rag.knowledge_refiner import KnowledgeRefiner
from thoth.mcp.auth import get_mcp_user_id
from thoth.utilities import OpenRouterClient
from thoth.config import config


class RAGManager:
    """
    Main manager for the RAG system.

    This class coordinates:
    - Document processing and token-based chunking
    - Embedding generation
    - Vector storage and retrieval
    - Question answering with context
    """

    def __init__(
        self,
        embedding_model: str | None = None,
        llm_model: str | None = None,
        collection_name: str | None = None,
        vector_db_path: str | Path | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        chunk_encoding: str | None = None,
        openrouter_api_key: str | None = None,
    ):
        """
        Initialize the RAG manager.

        Args:
            embedding_model: Model to use for embeddings (defaults to config).
            llm_model: Model to use for question answering (defaults to config).
            collection_name: Name of the vector DB collection (defaults to config).
            vector_db_path: Path to persist vector DB (defaults to config).
            chunk_size: Size of text chunks in tokens (defaults to config).
            chunk_overlap: Overlap between chunks in tokens (defaults to config).
            chunk_encoding: Encoding for token counting (defaults to config).
            openrouter_api_key: API key for OpenRouter (defaults to config).
        """
        self.config = config

        # Set parameters from config or arguments
        self.embedding_model = embedding_model or self.config.rag_config.embedding_model
        self.llm_model = llm_model or self.config.rag_config.qa.model
        self.collection_name = collection_name or self.config.rag_config.collection_name
        self.vector_db_path = Path(
            vector_db_path or self.config.rag_config.vector_db_path
        )
        self.chunk_size = chunk_size or self.config.rag_config.chunk_size
        self.chunk_overlap = chunk_overlap or self.config.rag_config.chunk_overlap
        self.chunk_encoding = chunk_encoding or self.config.rag_config.chunk_encoding
        self.api_key = openrouter_api_key or self.config.api_keys.openrouter_key

        # Initialize components
        self._init_components()

        # Register for config reload notifications
        self.config.register_reload_callback('rag_manager', self._on_config_reload)
        logger.debug('RAGManager registered for config reload notifications')

        logger.info('RAGManager initialized successfully')

    def _init_components(self) -> None:
        """Initialize all RAG components."""
        # Initialize embedding manager
        self.embedding_manager = EmbeddingManager(
            model=self.embedding_model,
            openrouter_api_key=self.api_key,
        )

        # Initialize vector store manager
        self.vector_store_manager = VectorStoreManager(
            collection_name=self.collection_name,
            persist_directory=self.vector_db_path,
            embedding_function=self.embedding_manager.get_embedding_model(),
        )

        # Initialize text splitters (two-stage for markdown)
        # Stage 1: Split by markdown headers to preserve document structure
        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ('#', 'h1'),
                ('##', 'h2'),
                ('###', 'h3'),
                ('####', 'h4'),
            ],
            strip_headers=False,  # Keep headers in content for context
        )

        # Stage 2: Split large sections into smaller chunks (token-based)
        # disallowed_special=() lets text like <|endoftext|> pass through
        # without raising -- common in ML textbooks and technical docs
        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=self.chunk_encoding,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=['\n\n', '\n', ' ', ''],
            disallowed_special=(),
        )

        # Initialize LLM for QA
        self.llm = OpenRouterClient(
            api_key=self.api_key,
            model=self.llm_model,
            temperature=self.config.rag_config.qa.temperature,
            max_tokens=self.config.rag_config.qa.max_tokens,
        )

        # Initialize reranker
        if self.config.rag_config.reranking_enabled:
            api_keys = {
                'cohere_key': self.config.api_keys.cohere_key,
            }
            self.reranker: BaseReranker = create_reranker(
                provider=self.config.rag_config.reranker_provider,
                api_keys=api_keys,
                llm_client=self.llm,
                reranker_model=self.config.rag_config.reranker_model,
            )
            logger.debug(f'Initialized reranker: {self.reranker.get_name()}')
        else:
            from thoth.rag.reranker import NoOpReranker

            self.reranker = NoOpReranker()
            logger.debug('Reranking disabled')

        # Initialize contextual enricher
        contextual_enabled = getattr(
            self.config.rag_config, 'contextual_enrichment_enabled', False
        )
        self.contextual_enricher = ContextualEnricher(
            llm_client=self.llm,
            enabled=contextual_enabled,
        )
        logger.debug(f'Contextual enrichment: {contextual_enabled}')

        # Initialize query router
        routing_enabled = getattr(
            self.config.rag_config, 'adaptive_routing_enabled', False
        )
        use_semantic_router = getattr(
            self.config.rag_config, 'use_semantic_router', False
        )
        self.query_router = QueryRouter(
            enabled=routing_enabled,
            use_semantic_router=use_semantic_router,
        )
        logger.debug(f'Adaptive routing: {routing_enabled}')

        # Initialize agentic RAG components (if enabled)
        agentic_config = self.config.rag_config.agentic_retrieval
        agentic_enabled = agentic_config.enabled

        if agentic_enabled:
            # Initialize document grader
            self.document_grader = DocumentGrader(
                llm_client=self.llm,
                threshold=agentic_config.confidence_threshold,
            )

            # Initialize hallucination checker
            self.hallucination_checker = HallucinationChecker(
                llm_client=self.llm,
                strict_mode=agentic_config.strict_hallucination_check,
            )

            # Initialize knowledge refiner (for CRAG strip decomposition)
            self.knowledge_refiner = None
            if agentic_config.knowledge_refinement_enabled:
                self.knowledge_refiner = KnowledgeRefiner(
                    llm_client=self.llm,
                    max_strips_per_document=agentic_config.max_strips_per_document,
                )
                logger.info('Knowledge refiner initialized for CRAG')

            # Convert pydantic config to dict for orchestrator
            agentic_config_dict = {
                'enabled': agentic_config.enabled,
                'max_retries': agentic_config.max_retries,
                'document_grading_enabled': agentic_config.document_grading_enabled,
                'query_expansion_enabled': agentic_config.query_expansion_enabled,
                'hallucination_check_enabled': agentic_config.hallucination_check_enabled,
                'confidence_threshold': agentic_config.confidence_threshold,
                'web_search_fallback_enabled': agentic_config.web_search_fallback_enabled,
                'crag_upper_threshold': agentic_config.crag_upper_threshold,
                'crag_lower_threshold': agentic_config.crag_lower_threshold,
                'knowledge_refinement_enabled': agentic_config.knowledge_refinement_enabled,
            }

            # Initialize agentic orchestrator
            self.agentic_orchestrator = AgenticRAGOrchestrator(
                vector_store=self.vector_store_manager,
                query_router=self.query_router,
                document_grader=self.document_grader,
                hallucination_checker=self.hallucination_checker,
                reranker=self.reranker,
                llm_client=self.llm,
                knowledge_refiner=self.knowledge_refiner,
                config=agentic_config_dict,
            )
            logger.info('Agentic RAG orchestrator initialized')
        else:
            self.document_grader = None
            self.hallucination_checker = None
            self.agentic_orchestrator = None
            logger.debug('Agentic RAG disabled')

        logger.debug('All RAG components initialized')

    def _on_config_reload(self, config: 'Config') -> None:  # noqa: ARG002, F821
        """
        Handle configuration reload for RAG system.

        Args:
            config: Updated configuration object

        Updates:
        - Embedding model if changed
        - Chunk size/overlap if changed
        - Vector store connection if needed
        - QA model settings
        """
        try:
            logger.info('Reloading RAG configuration...')

            # Track changes for logging
            embedding_changed = (
                self.embedding_model != self.config.rag_config.embedding_model
            )
            qa_model_changed = self.llm_model != self.config.rag_config.qa.model
            chunk_size_changed = self.chunk_size != self.config.rag_config.chunk_size

            # Log what's changing
            if embedding_changed:
                logger.info(
                    f'Embedding model changed: {self.embedding_model} → {self.config.rag_config.embedding_model}'
                )
            if qa_model_changed:
                logger.info(
                    f'QA model changed: {self.llm_model} → {self.config.rag_config.qa.model}'
                )
            if chunk_size_changed:
                logger.info(
                    f'Chunk size changed: {self.chunk_size} → {self.config.rag_config.chunk_size}'
                )

            # Update configuration parameters
            self.embedding_model = self.config.rag_config.embedding_model
            self.llm_model = self.config.rag_config.qa.model
            self.collection_name = self.config.rag_config.collection_name
            self.vector_db_path = Path(self.config.rag_config.vector_db_path)
            self.chunk_size = self.config.rag_config.chunk_size
            self.chunk_overlap = self.config.rag_config.chunk_overlap
            self.chunk_encoding = self.config.rag_config.chunk_encoding
            self.api_key = self.config.api_keys.openrouter_key

            # Reinitialize components with new config
            # Note: This recreates embedding manager and LLM clients
            self._init_components()

            logger.success('RAG config reloaded successfully')

        except Exception as e:
            logger.error(f'RAG config reload failed: {e}')

    def _has_images(self, content: str) -> bool:
        """
        Check if markdown content contains images.

        Args:
            content: Markdown content to check.

        Returns:
            bool: True if content contains images, False otherwise.
        """
        import re

        # Check for markdown image syntax: ![alt text](url) or ![alt text][ref]
        image_pattern = r'!\[[^\]]*\]\([^)]+\)|!\[[^\]]*\]\[[^\]]*\]'
        return bool(re.search(image_pattern, content))

    def _strip_images(self, content: str) -> str:
        """
        Strip image references from markdown content.

        This removes markdown image syntax like ![alt](url) and ![alt][ref]
        while preserving the rest of the content.

        Args:
            content: Markdown content with potential image references.

        Returns:
            str: Content with image references removed.
        """
        import re

        # Remove markdown image syntax: ![alt text](url) or ![alt text][ref]
        # Also remove any surrounding whitespace/newlines left behind
        image_pattern = r'!\[[^\]]*\]\([^)]+\)|!\[[^\]]*\]\[[^\]]*\]'
        content = re.sub(image_pattern, '', content)

        # Clean up multiple consecutive newlines left by removed images
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content.strip()

    def _lookup_paper_id_by_title(self, title: str) -> str | None:
        """
        Look up a paper ID from the database by title.

        Args:
            title: Paper title to search for.

        Returns:
            Paper ID (UUID string) if found, None otherwise.
        """
        import asyncio

        import asyncpg

        db_url = getattr(self.config.secrets, 'database_url', None)
        if not db_url:
            logger.warning('DATABASE_URL not configured - cannot lookup paper_id')
            return None

        async def lookup():
            resolved_user_id = get_mcp_user_id()
            conn = await asyncpg.connect(db_url)
            try:
                # Try exact match first, then normalized match
                paper_id = await conn.fetchval(
                    'SELECT id FROM paper_metadata WHERE LOWER(title) = LOWER($1) AND user_id = $2',
                    title,
                    resolved_user_id,
                )
                if paper_id:
                    return str(paper_id)

                # Try fuzzy match with title normalization
                normalized_title = title.replace('_', ' ').replace('-', ' ')
                paper_id = await conn.fetchval(
                    'SELECT id FROM paper_metadata WHERE LOWER(title_normalized) = LOWER($1) AND user_id = $2',
                    normalized_title,
                    resolved_user_id,
                )
                return str(paper_id) if paper_id else None
            finally:
                await conn.close()

        try:
            asyncio.get_running_loop()
            # Already in async context - shouldn't happen in normal use
            return None
        except RuntimeError:
            # No event loop running - safe to use asyncio.run()
            return asyncio.run(lookup())

    def index_paper_by_id(
        self,
        paper_id: str,
        markdown_content: str | None = None,
        user_id: str | None = None,
    ) -> list[str]:
        """
        Index a paper directly from the database by its ID.

        Args:
            paper_id: UUID of the paper to index.
            markdown_content: Optional markdown content (if not provided,
                fetched from DB).
            user_id: Optional user ID for multi-tenant isolation.

        Returns:
            List of document IDs that were indexed.
        """
        import asyncio
        from uuid import UUID

        import asyncpg

        try:
            logger.info(f'Indexing paper by ID: {paper_id}')
            paper_uuid = UUID(paper_id)

            db_url = getattr(self.config.secrets, 'database_url', None)
            if not db_url:
                raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

            async def fetch_and_index():
                resolved_user_id = user_id or get_mcp_user_id()
                conn = await asyncpg.connect(db_url)
                try:
                    # Fetch paper details and markdown content including collection info
                    row = await conn.fetchrow(
                        """
                        SELECT
                            pm.id,
                            pm.title,
                            pm.doi,
                            pm.authors,
                            pm.collection_id,
                            pm.document_category,
                            kc.name as collection_name,
                            pp.markdown_content
                        FROM paper_metadata pm
                        LEFT JOIN processed_papers pp ON pp.paper_id = pm.id
                        LEFT JOIN knowledge_collections kc ON kc.id = pm.collection_id
                        WHERE pm.id = $1 AND pm.user_id = $2
                        """,
                        paper_uuid,
                        resolved_user_id,
                    )

                    if not row:
                        raise ValueError(f'Paper not found: {paper_id}')

                    content = markdown_content or row['markdown_content']
                    if not content:
                        logger.warning(f'No markdown content for paper {paper_id}')
                        return []

                    # Strip image references from content if configured
                    if (
                        self.config.rag_config.skip_files_with_images
                        and self._has_images(content)
                    ):
                        logger.debug(
                            f'Stripping image references from paper {paper_id}'
                        )
                        content = self._strip_images(content)

                        # Check if there's still meaningful content after
                        # stripping images
                        if len(content.strip()) < 100:
                            logger.warning(
                                f'Paper {paper_id} has insufficient content after image removal'
                            )
                            return []

                    # Prepare metadata including collection info
                    metadata = {
                        'paper_id': str(row['id']),
                        'title': row['title'] or 'Unknown',
                        'doi': row['doi'],
                        'authors': row['authors'],
                        'document_type': 'article',
                        'source': f'database:paper:{paper_id}',
                        'document_category': row['document_category']
                        or 'research_paper',
                    }

                    # Add collection metadata if present
                    if row['collection_id']:
                        metadata['collection_id'] = str(row['collection_id'])
                        metadata['collection_name'] = row['collection_name']

                    # Split into chunks using two-stage strategy
                    documents = self._split_markdown_content(content, metadata)
                    logger.debug(
                        f'Split paper into {len(documents)} chunks using two-stage strategy'
                    )

                    # Apply contextual enrichment if enabled
                    if self.contextual_enricher.enabled:
                        documents = await self.contextual_enricher.enrich_chunks_async(
                            chunks=documents,
                            document_text=content,
                            document_title=row['title'],
                        )
                        logger.debug('Applied contextual enrichment to chunks')

                    # Index documents using async method
                    doc_ids = await self.vector_store_manager.add_documents_async(
                        documents, paper_id=paper_uuid, user_id=user_id
                    )
                    logger.info(
                        f'Successfully indexed {len(doc_ids)} chunks for paper {paper_id}'
                    )
                    return doc_ids
                finally:
                    await conn.close()

            try:
                asyncio.get_running_loop()
                raise RuntimeError(
                    'index_paper_by_id() called from async context. '
                    "Use 'await index_paper_by_id_async()' instead."
                )
            except RuntimeError as e:
                if 'no running event loop' in str(e).lower():
                    return asyncio.run(fetch_and_index())
                else:
                    raise

        except Exception as e:
            logger.error(f'Error indexing paper {paper_id}: {e}')
            raise

    async def index_paper_by_id_async(
        self,
        paper_id: str,
        markdown_content: str | None = None,
        user_id: str | None = None,
    ) -> list[str]:
        """
        Index a paper from the database by its ID (async version).

        Args:
            paper_id: UUID of the paper to index.
            markdown_content: Optional markdown content (if not provided,
                fetched from DB).
            user_id: Optional user ID for multi-tenant isolation.

        Returns:
            List of document IDs that were indexed.
        """
        from uuid import UUID

        import asyncpg

        try:
            logger.info(f'Indexing paper by ID (async): {paper_id}')
            paper_uuid = UUID(paper_id)

            db_url = getattr(self.config.secrets, 'database_url', None)
            if not db_url:
                raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

            conn = await asyncpg.connect(db_url)
            try:
                resolved_user_id = user_id or get_mcp_user_id()
                row = await conn.fetchrow(
                    """
                    SELECT
                        pm.id,
                        pm.title,
                        pm.doi,
                        pm.authors,
                        pm.collection_id,
                        pm.document_category,
                        kc.name as collection_name,
                        pp.markdown_content
                    FROM paper_metadata pm
                    LEFT JOIN processed_papers pp ON pp.paper_id = pm.id
                    LEFT JOIN knowledge_collections kc ON kc.id = pm.collection_id
                    WHERE pm.id = $1 AND pm.user_id = $2
                    """,
                    paper_uuid,
                    resolved_user_id,
                )

                if not row:
                    raise ValueError(f'Paper not found: {paper_id}')

                content = markdown_content or row['markdown_content']
                if not content:
                    logger.warning(f'No markdown content for paper {paper_id}')
                    return []

                if self.config.rag_config.skip_files_with_images and self._has_images(
                    content
                ):
                    content = self._strip_images(content)
                    if len(content.strip()) < 100:
                        logger.warning(
                            f'Paper {paper_id} has insufficient content after image removal'
                        )
                        return []

                metadata = {
                    'paper_id': str(row['id']),
                    'title': row['title'] or 'Unknown',
                    'doi': row['doi'],
                    'authors': row['authors'],
                    'document_type': 'article',
                    'source': f'database:paper:{paper_id}',
                    'document_category': row['document_category'] or 'research_paper',
                }

                if row['collection_id']:
                    metadata['collection_id'] = str(row['collection_id'])
                    metadata['collection_name'] = row['collection_name']

                documents = self._split_markdown_content(content, metadata)

                if self.contextual_enricher.enabled:
                    documents = await self.contextual_enricher.enrich_chunks_async(
                        chunks=documents,
                        document_text=content,
                        document_title=row['title'],
                    )

                doc_ids = await self.vector_store_manager.add_documents_async(
                    documents, paper_id=paper_uuid, user_id=user_id
                )
                logger.info(
                    f'Successfully indexed {len(doc_ids)} chunks for paper {paper_id}'
                )
                return doc_ids
            finally:
                await conn.close()

        except Exception as e:
            logger.error(f'Error indexing paper {paper_id} (async): {e}')
            raise

    def index_markdown_file(
        self,
        file_path: Path,
        paper_id: str | None = None,
        user_id: str | None = None,
    ) -> list[str]:
        """
        Index a markdown file into the vector store.

        Args:
            file_path: Path to the markdown file.
            paper_id: Optional paper ID (UUID string). If not provided,
                attempts lookup by title.
            user_id: Optional user ID for multi-tenant isolation.

        Returns:
            List of document IDs that were indexed.
        """
        try:
            logger.info(f'Indexing markdown file: {file_path}')

            # Read the file
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            # Skip files with images if configured to do so
            if self.config.rag_config.skip_files_with_images and self._has_images(
                content
            ):
                logger.info(f'Skipping {file_path} - contains images')
                return []

            # Extract metadata from file
            metadata = self._extract_metadata_from_path(file_path)

            # Try to find paper_id if not provided
            if paper_id is None:
                title = metadata.get('title', file_path.stem)
                paper_id = self._lookup_paper_id_by_title(title)
                if paper_id:
                    logger.debug(f'Found paper_id {paper_id} for title: {title}')
                else:
                    logger.warning(
                        f'Could not find paper_id for: {title}. Using index_paper_by_id with database content is recommended.'
                    )
                    # For now, we'll create a fallback - but this requires
                    # paper_id in DB
                    raise ValueError(
                        f'Cannot index {file_path}: paper_id not found in database. '
                        'Ensure the paper exists in paper_metadata first, or use index_paper_by_id().'
                    )

            # If we have paper_id, use the database-backed method for consistency
            return self.index_paper_by_id(
                paper_id, markdown_content=content, user_id=user_id
            )

        except Exception as e:
            logger.error(f'Error indexing markdown file {file_path}: {e}')
            raise

    def index_directory(
        self,
        directory: Path,
        pattern: str = '*.md',
        recursive: bool = True,
    ) -> dict[str, list[str]]:
        """
        Index all markdown files in a directory.

        Args:
            directory: Directory containing markdown files.
            pattern: File pattern to match (default: "*.md").
            recursive: Whether to search recursively.

        Returns:
            Dictionary mapping file paths to their document IDs.
        """
        try:
            logger.info(f'Indexing directory: {directory}')

            # Find all markdown files
            if recursive:
                files = list(directory.rglob(pattern))
            else:
                files = list(directory.glob(pattern))

            logger.info(f'Found {len(files)} files to index')

            # Index each file
            results = {}
            for file_path in files:
                try:
                    doc_ids = self.index_markdown_file(file_path)
                    results[str(file_path)] = doc_ids
                except Exception as e:
                    logger.error(f'Failed to index {file_path}: {e}')
                    continue

            logger.info(f'Successfully indexed {len(results)} files')
            return results

        except Exception as e:
            logger.error(f'Error indexing directory {directory}: {e}')
            raise

    async def search_async(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        return_scores: bool = False,
    ) -> list[Document] | list[tuple[Document, float]]:
        """
        Search for relevant documents (async version).
        Use this from async contexts to avoid event loop conflicts.

        Supports hybrid search and reranking based on configuration.

        Args:
            query: Search query.
            k: Number of results to return.
            filter: Optional metadata filter.
            return_scores: Whether to return relevance scores.

        Returns:
            List of documents or tuples of (document, score).
        """
        try:
            # Determine if we should use reranking
            use_reranking = (
                self.config.rag_config.reranking_enabled
                and isinstance(self.reranker, BaseReranker)
                and self.reranker.get_name() != 'noop'
            )

            if use_reranking:
                # Over-retrieve candidates for reranking
                candidates_k = self.config.rag_config.retrieval_candidates
                candidates = await self.vector_store_manager.similarity_search_async(
                    query=query, k=candidates_k, filter=filter
                )

                # Rerank to top k
                reranked = await self.reranker.rerank_async(
                    query=query,
                    documents=candidates,
                    top_n=k,
                )

                if return_scores:
                    # Return with rerank scores
                    return [
                        (doc, doc.metadata.get('rerank_score', 0.0)) for doc in reranked
                    ]
                else:
                    return reranked
            else:
                # Standard search without reranking
                if return_scores:
                    return await self.vector_store_manager.similarity_search_with_score_async(
                        query=query,
                        k=k,
                        filter=filter,
                    )
                else:
                    return await self.vector_store_manager.similarity_search_async(
                        query=query,
                        k=k,
                        filter=filter,
                    )
        except Exception as e:
            logger.error(f'Error searching documents: {e}')
            raise

    def search(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        return_scores: bool = False,
    ) -> list[Document] | list[tuple[Document, float]]:
        """
        Search for relevant documents (sync wrapper).

        Supports hybrid search and reranking based on configuration.

        Args:
            query: Search query.
            k: Number of results to return.
            filter: Optional metadata filter.
            return_scores: Whether to return relevance scores.

        Returns:
            List of documents or tuples of (document, score).
        """
        try:
            # Determine if we should use reranking
            use_reranking = (
                self.config.rag_config.reranking_enabled
                and isinstance(self.reranker, BaseReranker)
                and self.reranker.get_name() != 'noop'
            )

            if use_reranking:
                # Over-retrieve candidates for reranking
                candidates_k = self.config.rag_config.retrieval_candidates
                candidates = self.vector_store_manager.similarity_search(
                    query=query, k=candidates_k, filter=filter
                )

                # Rerank to top k
                reranked = self.reranker.rerank(
                    query=query,
                    documents=candidates,
                    top_n=k,
                )

                if return_scores:
                    # Return with rerank scores
                    return [
                        (doc, doc.metadata.get('rerank_score', 0.0)) for doc in reranked
                    ]
                else:
                    return reranked
            else:
                # Standard search without reranking
                if return_scores:
                    return self.vector_store_manager.similarity_search_with_score(
                        query=query,
                        k=k,
                        filter=filter,
                    )
                else:
                    return self.vector_store_manager.similarity_search(
                        query=query,
                        k=k,
                        filter=filter,
                    )
        except Exception as e:
            logger.error(f'Error searching documents: {e}')
            raise

    def answer_question(
        self,
        question: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        return_sources: bool = True,
    ) -> dict[str, Any]:
        """
        Answer a question using the RAG system.

        Uses hybrid search and reranking if enabled in configuration.

        Args:
            question: The question to answer.
            k: Number of documents to retrieve for context (after reranking).
            filter: Optional metadata filter for retrieval.
            return_sources: Whether to return source documents.

        Returns:
            Dictionary containing the answer and optionally source documents.
        """
        try:
            logger.info(f'Answering question: {question}')

            # Retrieve relevant documents (uses reranking if enabled)
            docs = self.search(
                query=question,
                k=k,
                filter=filter,
                return_scores=False,
            )

            # Format context from retrieved documents
            def format_docs(documents: list[Document]) -> str:
                return '\n\n'.join(doc.page_content for doc in documents)

            context = format_docs(docs)

            # Create RAG prompt
            prompt = ChatPromptTemplate.from_template(
                """Answer the question based only on the following context.
If you cannot answer the question based on the context, say so.

Context:
{context}

Question: {question}

Answer:"""
            )

            # Create simple chain using LCEL
            chain = prompt | self.llm | StrOutputParser()

            # Get answer
            answer = chain.invoke({'context': context, 'question': question})

            # Format response
            response = {
                'question': question,
                'answer': answer,
            }

            if return_sources:
                response['sources'] = []
                for doc in docs:
                    source_info = {
                        'content': doc.page_content[:200] + '...',  # Preview
                        'metadata': doc.metadata,
                    }
                    response['sources'].append(source_info)

            logger.info('Successfully generated answer')
            return response

        except Exception as e:
            logger.error(f'Error answering question: {e}')
            raise

    async def agentic_answer_question_async(
        self,
        question: str,
        k: int = 5,
        max_retries: int = 2,
        progress_callback: Any = None,
        return_sources: bool = True,
    ) -> dict[str, Any]:
        """
        Answer question using agentic retrieval (async).

        Uses the AgenticRAGOrchestrator for adaptive, self-correcting retrieval
        with query classification, expansion, document grading, query rewriting,
        and hallucination detection.

        Args:
            question: The question to answer
            k: Number of documents to retrieve
            max_retries: Maximum number of retrieval retries on low confidence
            progress_callback: Optional callback for progress updates (step, message)
            return_sources: Whether to return source documents

        Returns:
            Dictionary containing answer, sources, and metadata

        Example:
            >>> result = await rag_manager.agentic_answer_question_async(
            ...     'Compare transformers and RNNs for sequence modeling'
            ... )
            >>> print(result['answer'])
        """
        if not self.agentic_orchestrator:
            logger.warning(
                'Agentic RAG not enabled, falling back to standard answer_question'
            )
            # Fall back to standard RAG
            return self.answer_question(
                question=question,
                k=k,
                return_sources=return_sources,
            )

        try:
            logger.info(f'Answering question with agentic RAG: {question}')

            # Use agentic orchestrator
            result = await self.agentic_orchestrator.answer_question_async(
                query=question,
                k=k,
                max_retries=max_retries,
                progress_callback=progress_callback,
            )

            # Format response
            response = {
                'question': question,
                'answer': result['answer'],
                'confidence': result['confidence'],
                'is_grounded': result['is_grounded'],
                'query_type': result['query_type'],
                'retry_count': result['retry_count'],
            }

            if return_sources:
                response['sources'] = result['sources']

            logger.info(
                f'Agentic RAG completed: confidence={result["confidence"]:.2f}, '
                f'retries={result["retry_count"]}'
            )
            return response

        except Exception as e:
            logger.error(f'Error in agentic answer: {e}')
            raise

    def agentic_answer_question(
        self,
        question: str,
        k: int = 5,
        max_retries: int = 2,
        progress_callback: Any = None,
        return_sources: bool = True,
    ) -> dict[str, Any]:
        """
        Answer question using agentic retrieval (sync wrapper).

        Args:
            question: The question to answer
            k: Number of documents to retrieve
            max_retries: Maximum number of retrieval retries
            progress_callback: Optional callback for progress updates
            return_sources: Whether to return source documents

        Returns:
            Dictionary containing answer, sources, and metadata
        """
        try:
            import asyncio

            asyncio.get_running_loop()
            raise RuntimeError(
                'agentic_answer_question() called from async context. '
                'Use await agentic_answer_question_async() instead.'
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                import asyncio

                return asyncio.run(
                    self.agentic_answer_question_async(
                        question=question,
                        k=k,
                        max_retries=max_retries,
                        progress_callback=progress_callback,
                        return_sources=return_sources,
                    )
                )
            else:
                raise

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the RAG system.

        Returns:
            Dictionary with system statistics.
        """
        try:
            vector_stats = self.vector_store_manager.get_collection_stats()

            stats = {
                'embedding_model': self.embedding_model,
                'qa_model': self.llm_model,
                'chunk_size': self.chunk_size,
                'chunk_overlap': self.chunk_overlap,
                'chunk_encoding': self.chunk_encoding,
                **vector_stats,
            }

            return stats

        except Exception as e:
            logger.error(f'Error getting RAG stats: {e}')
            raise

    def clear_index(self) -> None:
        """Clear the entire vector index."""
        try:
            logger.warning('Clearing entire vector index')
            self.vector_store_manager.clear_collection()
            logger.info('Vector index cleared')
        except Exception as e:
            logger.error(f'Error clearing index: {e}')
            raise

    def _extract_metadata_from_path(self, file_path: Path) -> dict[str, Any]:
        """
        Extract metadata from file path and name.

        Args:
            file_path: Path to the file.

        Returns:
            Dictionary of metadata.
        """
        metadata = {
            'source': str(file_path),
            'filename': file_path.name,
            'file_type': file_path.suffix,
        }

        # Check if it's a note or markdown
        if 'notes' in file_path.parts:
            metadata['document_type'] = 'note'
        elif 'markdown' in file_path.parts:
            metadata['document_type'] = 'article'
        else:
            metadata['document_type'] = 'other'

        # Try to extract title from filename
        title = file_path.stem.replace('_', ' ').replace('-', ' ')
        metadata['title'] = title

        return metadata

    def _split_markdown_content(
        self, content: str, base_metadata: dict[str, Any]
    ) -> list[Document]:
        """
        Split markdown content using two-stage strategy.

        Stage 1: Split by markdown headers to preserve document structure
        Stage 2: Subdivide large sections using token-based chunking

        Args:
            content: Markdown content to split
            base_metadata: Base metadata to attach to all chunks

        Returns:
            List of Document objects with hierarchical metadata
        """
        # Stage 1: Split by headers
        header_splits = self.header_splitter.split_text(content)

        # Stage 2: Further split large sections
        all_documents = []
        chunk_index = 0

        for header_doc in header_splits:
            # Extract header hierarchy from metadata
            header_metadata = (
                header_doc.metadata if hasattr(header_doc, 'metadata') else {}
            )

            # Build section path from headers
            section_path = []
            heading_level = 0
            for i in range(1, 5):  # h1 through h4
                header_key = f'h{i}'
                if header_key in header_metadata:
                    section_path.append(header_metadata[header_key])
                    heading_level = i

            # Check if section is large enough to need further splitting
            section_text = (
                header_doc.page_content
                if hasattr(header_doc, 'page_content')
                else str(header_doc)
            )

            # Count tokens approximately
            import tiktoken

            try:
                enc = tiktoken.get_encoding(self.chunk_encoding)
                token_count = len(enc.encode(section_text, disallowed_special=()))
            except Exception:
                # Fallback: estimate tokens as words * 1.3
                token_count = len(section_text.split()) * 1.3

            if token_count > self.chunk_size:
                # Need to split this section further
                subsections = self.text_splitter.split_text(section_text)

                for i, subsection in enumerate(subsections):
                    doc_metadata = {
                        **base_metadata,
                        'chunk_index': chunk_index,
                        'section_path': section_path,
                        'heading_level': heading_level,
                        'is_subsection': True,
                        'subsection_index': i,
                        'total_subsections': len(subsections),
                    }
                    all_documents.append(
                        Document(page_content=subsection, metadata=doc_metadata)
                    )
                    chunk_index += 1
            else:
                # Section is small enough, use as-is
                doc_metadata = {
                    **base_metadata,
                    'chunk_index': chunk_index,
                    'section_path': section_path,
                    'heading_level': heading_level,
                    'is_subsection': False,
                }
                all_documents.append(
                    Document(page_content=section_text, metadata=doc_metadata)
                )
                chunk_index += 1

        # Add total_chunks to all metadata
        for doc in all_documents:
            doc.metadata['total_chunks'] = len(all_documents)

        return all_documents

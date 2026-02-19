"""
Vector store manager for Thoth RAG system using PostgreSQL + pgvector.

This module provides database-only vector storage with no file system dependencies.
Supports hybrid search (vector + BM25) with Reciprocal Rank Fusion.
"""

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from langchain_core.documents import Document
from loguru import logger

from thoth.config import Config
from thoth.rag.search_backends import FullTextSearchBackend, create_backend


class VectorStoreManager:
    """
    Manages vector storage and retrieval using PostgreSQL + pgvector.

    This class provides functionality to:
    - Store document embeddings in PostgreSQL with pgvector
    - Perform similarity searches using HNSW index
    - Manage document chunks with metadata

    100% database-backed - no file system dependencies.
    """

    def __init__(
        self,
        collection_name: str | None = None,  # noqa: ARG002
        persist_directory: str  # noqa: ARG002
        | None = None,  # Deprecated, kept for compatibility
        embedding_function: Any | None = None,
    ):
        """
        Initialize the vector store manager with pgvector.

        Args:
            collection_name: DEPRECATED - pgvector uses single document_chunks table
            persist_directory: DEPRECATED - database-only, no file storage
            embedding_function: Embedding function to use (required).
        """
        self.config = Config()

        # Store embedding function
        if embedding_function is None:
            msg = 'Embedding function is required for VectorStoreManager'
            raise ValueError(msg)
        self.embedding_function = embedding_function

        # Get database URL
        self.db_url = getattr(self.config.secrets, 'database_url', None)
        if not self.db_url:
            raise ValueError('DATABASE_URL not configured')

        # Connection pool for async operations
        self._pool: asyncpg.Pool | None = None

        # Initialize full-text search backend for hybrid search
        backend_type = self.config.rag_config.full_text_backend
        self._ft_backend: FullTextSearchBackend = create_backend(backend_type)

        logger.info(
            f'VectorStoreManager initialized (PostgreSQL + pgvector + {self._ft_backend.get_backend_name()})'
        )

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool.

        Handles the case where the pool was created in a previous event loop
        that has since been closed.
        """
        # Check if we have a pool and if it's still valid
        if self._pool is not None:
            try:
                # Test if the pool is still usable
                async with self._pool.acquire() as conn:
                    await conn.execute('SELECT 1')
                return self._pool
            except Exception:
                # Pool is invalid (likely from a closed event loop), close and recreate
                try:
                    await self._pool.close()
                except Exception:  # nosec B110
                    # Suppress all errors during cleanup
                    pass
                self._pool = None

        # Create new pool
        self._pool = await asyncpg.create_pool(
            self.db_url, min_size=1, max_size=5, command_timeout=60
        )
        return self._pool

    async def _ensure_extension(self) -> None:
        """Ensure pgvector extension is enabled."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
            logger.debug('Ensured pgvector extension is enabled')

    async def add_documents_async(
        self, documents: list[Document], paper_id: UUID | None = None, **kwargs: Any
    ) -> list[str]:
        """
        Add documents to the vector store (async version).
        Use this from async contexts to avoid event loop conflicts.

        Args:
            documents: List of LangChain Document objects
            paper_id: UUID of the paper these chunks belong to
            **kwargs: Additional metadata

        Returns:
            List of document IDs (UUIDs as strings)
        """
        return await self._add_documents_async(documents, paper_id, **kwargs)

    def add_documents(
        self, documents: list[Document], paper_id: UUID | None = None, **kwargs: Any
    ) -> list[str]:
        """
        Add documents to the vector store (sync wrapper).
        Detects if running in async context and provides helpful error.

        Args:
            documents: List of LangChain Document objects
            paper_id: UUID of the paper these chunks belong to
            **kwargs: Additional metadata

        Returns:
            List of document IDs (UUIDs as strings)
        """
        try:
            loop = asyncio.get_running_loop()  # noqa: F841
            raise RuntimeError(
                'add_documents() called from async context. '
                "Use 'await add_documents_async()' instead to avoid event loop conflicts."
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                # Safe to use asyncio.run() - no loop running
                return asyncio.run(
                    self._add_documents_async(documents, paper_id, **kwargs)
                )
            else:
                # Already in async context - raise helpful error
                raise

    async def _add_documents_async(
        self,
        documents: list[Document],
        paper_id: UUID | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Add documents asynchronously.

        Args:
            documents: List of documents to add
            paper_id: Paper UUID
            user_id: User ID for multi-tenant isolation
            **kwargs: Additional metadata

        Returns:
            List of document chunk IDs
        """
        import json

        if not paper_id:
            raise ValueError('paper_id is required for document chunks')

        # Generate embeddings
        texts = [doc.page_content for doc in documents]
        embeddings = self.embedding_function.embed_documents(texts)

        pool = await self._get_pool()
        ids = []

        async with pool.acquire() as conn:
            # Set up JSON codec for the connection
            await conn.set_type_codec(
                'jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog'
            )

            for idx, (doc, embedding) in enumerate(zip(documents, embeddings)):  # noqa: B905
                metadata = {**doc.metadata, **kwargs}

                # Ensure metadata values are JSON-serializable
                clean_metadata = {}
                for k, v in metadata.items():
                    if v is None:
                        clean_metadata[k] = None
                    elif isinstance(v, (str, int, float, bool)):
                        clean_metadata[k] = v
                    elif isinstance(v, (list, dict)):
                        clean_metadata[k] = v
                    else:
                        clean_metadata[k] = str(v)

                # Convert embedding list to PostgreSQL vector format string
                # pgvector expects format like '[0.1, 0.2, 0.3]'
                embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'

                # Include user_id if provided
                if user_id:
                    result = await conn.fetchrow(
                        """
                        INSERT INTO document_chunks
                        (paper_id, content, chunk_index, chunk_type, metadata, embedding, token_count, user_id)
                        VALUES ($1, $2, $3, $4, $5::jsonb, $6::vector, $7, $8)
                        ON CONFLICT (paper_id, chunk_index)
                        DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata,
                            user_id = EXCLUDED.user_id,
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING id
                    """,
                        paper_id,
                        doc.page_content,
                        idx,
                        clean_metadata.get('chunk_type', 'content'),
                        clean_metadata,
                        embedding_str,
                        len(doc.page_content.split()),  # Rough token count
                        user_id,
                    )
                else:
                    result = await conn.fetchrow(
                        """
                        INSERT INTO document_chunks
                        (paper_id, content, chunk_index, chunk_type, metadata, embedding, token_count)
                        VALUES ($1, $2, $3, $4, $5::jsonb, $6::vector, $7)
                        ON CONFLICT (paper_id, chunk_index)
                        DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata,
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING id
                    """,
                        paper_id,
                        doc.page_content,
                        idx,
                        clean_metadata.get('chunk_type', 'content'),
                        clean_metadata,
                        embedding_str,
                        len(doc.page_content.split()),  # Rough token count
                    )

                ids.append(str(result['id']))

        logger.debug(f'Added {len(ids)} document chunks for paper {paper_id}')
        return ids

    async def similarity_search_async(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[Document]:
        """
        Perform similarity search (async version).
        Use this from async contexts to avoid event loop conflicts.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Metadata filter (not yet implemented)
            **kwargs: Additional search parameters

        Returns:
            List of similar documents
        """
        return await self._similarity_search_async(query, k, filter, **kwargs)

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[Document]:
        """
        Perform similarity search (sync wrapper).
        Detects if running in async context and provides helpful error.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Metadata filter (not yet implemented)
            **kwargs: Additional search parameters

        Returns:
            List of similar documents
        """
        try:
            loop = asyncio.get_running_loop()  # noqa: F841
            raise RuntimeError(
                'similarity_search() called from async context. '
                "Use 'await similarity_search_async()' instead to avoid event loop conflicts."
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                # Safe to use asyncio.run() - no loop running
                return asyncio.run(
                    self._similarity_search_async(query, k, filter, **kwargs)
                )
            else:
                # Already in async context - raise helpful error
                raise

    async def _similarity_search_async(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[Document]:
        """
        Perform similarity search asynchronously.

        Supports both pure vector search and hybrid search (vector + BM25)
        with Reciprocal Rank Fusion based on configuration.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Metadata filter (not yet implemented)
            **kwargs: Additional parameters (use_hybrid=True to force hybrid)

        Returns:
            List of Document objects ranked by relevance
        """
        # Check if hybrid search is enabled
        use_hybrid = kwargs.get(
            'use_hybrid', self.config.rag_config.hybrid_search_enabled
        )

        if use_hybrid:
            return await self._hybrid_search_async(query, k, filter)
        else:
            return await self._vector_only_search_async(query, k, filter)

    async def _vector_only_search_async(
        self,
        query: str,
        k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Pure vector similarity search with optional metadata filtering."""
        # Generate query embedding
        query_embedding = self.embedding_function.embed_query(query)

        # Convert embedding list to pgvector string format for asyncpg
        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Build WHERE clause with filters
            where_clauses = ['dc.embedding IS NOT NULL']
            params = [embedding_str, k]
            param_idx = 3

            if filter:
                filter_clause, filter_params, param_idx = self._build_filter_clause(
                    filter, param_idx
                )
                if filter_clause:
                    where_clauses.append(filter_clause)
                    params.extend(filter_params)

            where_sql = ' AND '.join(where_clauses)

            # Use pgvector cosine similarity search with HNSW index
            rows = await conn.fetch(
                f"""
                SELECT
                    dc.id,
                    dc.content,
                    dc.metadata,
                    dc.chunk_type,
                    p.title,
                    p.doi,
                    p.authors,
                    1 - (dc.embedding <=> $1::vector) as similarity
                FROM document_chunks dc
                JOIN papers p ON dc.paper_id = p.id
                WHERE {where_sql}
                ORDER BY dc.embedding <=> $1::vector
                LIMIT $2
            """,  # nosec B608
                *params,
            )

            documents = self._rows_to_documents(rows)
            logger.debug(f'Vector-only search found {len(documents)} documents')
            return documents

    async def _hybrid_search_async(
        self,
        query: str,
        k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """
        Hybrid search combining vector similarity and BM25 keyword matching.

        Uses Reciprocal Rank Fusion (RRF) to merge results from both methods.
        Over-retrieves from each method then fuses with RRF scoring.

        Args:
            query: Search query text
            k: Final number of results to return
            filter: Metadata filter (not yet implemented)

        Returns:
            List of Document objects ranked by RRF score
        """
        # Get config parameters
        rrf_k = self.config.rag_config.hybrid_rrf_k
        vector_weight = self.config.rag_config.hybrid_vector_weight
        text_weight = self.config.rag_config.hybrid_text_weight

        # Over-retrieve from each method (5x to ensure good fusion)
        candidates_per_method = k * 5

        # Generate query embedding for vector search
        query_embedding = self.embedding_function.embed_query(query)
        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Execute both searches in parallel using asyncio.gather
            vector_results, text_results = await asyncio.gather(
                self._get_vector_candidates(
                    conn, embedding_str, candidates_per_method, filter
                ),
                self._get_text_candidates(conn, query, candidates_per_method, filter),
                return_exceptions=True,
            )

            # Handle errors gracefully
            if isinstance(vector_results, Exception):
                logger.error(f'Vector search failed: {vector_results}')
                vector_results = []
            if isinstance(text_results, Exception):
                logger.warning(f'Text search failed: {text_results}, using vector-only')
                text_results = []

            # If text search returned nothing, fall back to vector-only
            if not text_results:
                logger.debug('No text search results, falling back to vector-only')
                return await self._vector_only_search_async(query, k, filter)

            # Apply RRF fusion
            fused_results = self._apply_rrf_fusion(
                vector_results, text_results, rrf_k, vector_weight, text_weight
            )

            # Fetch full document data for top k results
            documents = await self._fetch_documents_by_ids(
                conn, [r['id'] for r in fused_results[:k]]
            )

            logger.debug(
                f'Hybrid search: {len(vector_results)} vector + {len(text_results)} text '
                f'-> {len(documents)} fused results'
            )
            return documents

    async def _get_vector_candidates(
        self,
        conn: asyncpg.Connection,
        embedding_str: str,
        k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Get top-k vector similarity candidates with optional filtering."""
        # Build WHERE clause with filters
        where_clauses = ['dc.embedding IS NOT NULL']
        params = [embedding_str, k]
        param_idx = 3

        if filter:
            filter_clause, filter_params, param_idx = self._build_filter_clause(
                filter, param_idx
            )
            if filter_clause:
                where_clauses.append(filter_clause)
                params.extend(filter_params)

        where_sql = ' AND '.join(where_clauses)

        rows = await conn.fetch(
            f"""
            SELECT
                dc.id,
                dc.paper_id,
                1 - (dc.embedding <=> $1::vector) as score
            FROM document_chunks dc
            WHERE {where_sql}
            ORDER BY dc.embedding <=> $1::vector
            LIMIT $2
        """,  # nosec B608
            *params,
        )

        return [
            {'id': row['id'], 'paper_id': row['paper_id'], 'score': float(row['score'])}
            for row in rows
        ]

    async def _get_text_candidates(
        self,
        conn: asyncpg.Connection,
        query: str,
        k: int,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get top-k BM25/full-text candidates using backend with optional filtering.
        """
        # Build filter clause if needed
        filter_clause = ''
        filter_params = []

        if filter:
            filter_clause, filter_params, _ = self._build_filter_clause(
                filter, start_param_idx=1
            )

        results = await self._ft_backend.search(
            conn, query, k, filter_clause, filter_params
        )
        return [
            {'id': r['id'], 'paper_id': r['paper_id'], 'score': r['score']}
            for r in results
        ]

    def _apply_rrf_fusion(
        self,
        vector_results: list[dict[str, Any]],
        text_results: list[dict[str, Any]],
        rrf_k: int,
        vector_weight: float,
        text_weight: float,
    ) -> list[dict[str, Any]]:
        """
        Apply Reciprocal Rank Fusion to merge vector and text results.

        RRF formula: score = sum(weight / (rrf_k + rank))
        where rank is 1-indexed position in the result list.

        Args:
            vector_results: Results from vector search
            text_results: Results from full-text search
            rrf_k: RRF constant (typically 60)
            vector_weight: Weight for vector search (typically 0.7)
            text_weight: Weight for text search (typically 0.3)

        Returns:
            List of dicts with id, paper_id, rrf_score sorted by score desc
        """
        # Build score dictionary
        scores: dict[str, dict[str, Any]] = {}

        # Add vector scores
        for rank, result in enumerate(vector_results, start=1):
            doc_id = str(result['id'])
            rrf_score = vector_weight / (rrf_k + rank)
            scores[doc_id] = {
                'id': result['id'],
                'paper_id': result['paper_id'],
                'rrf_score': rrf_score,
                'vector_rank': rank,
                'text_rank': None,
            }

        # Add text scores
        for rank, result in enumerate(text_results, start=1):
            doc_id = str(result['id'])
            rrf_score = text_weight / (rrf_k + rank)

            if doc_id in scores:
                # Document appears in both - add scores
                scores[doc_id]['rrf_score'] += rrf_score
                scores[doc_id]['text_rank'] = rank
            else:
                # Document only in text results
                scores[doc_id] = {
                    'id': result['id'],
                    'paper_id': result['paper_id'],
                    'rrf_score': rrf_score,
                    'vector_rank': None,
                    'text_rank': rank,
                }

        # Sort by RRF score descending
        sorted_results = sorted(
            scores.values(), key=lambda x: x['rrf_score'], reverse=True
        )

        return sorted_results

    async def _fetch_documents_by_ids(
        self, conn: asyncpg.Connection, doc_ids: list[UUID]
    ) -> list[Document]:
        """Fetch full document data for given IDs."""
        if not doc_ids:
            return []

        rows = await conn.fetch(
            """
            SELECT
                dc.id,
                dc.content,
                dc.metadata,
                dc.chunk_type,
                p.title,
                p.doi,
                p.authors
            FROM document_chunks dc
            JOIN papers p ON dc.paper_id = p.id
            WHERE dc.id = ANY($1::uuid[])
            ORDER BY array_position($1::uuid[], dc.id)
        """,
            doc_ids,
        )

        return self._rows_to_documents(rows)

    def _build_filter_clause(
        self, filter: dict[str, Any], start_param_idx: int = 3
    ) -> tuple[str, list[Any], int]:
        """
        Build SQL WHERE clause from filter dictionary.

        Supports:
        - user_id: filter by dc.user_id (multi-tenant isolation)
        - collection_id: filter by metadata->>'collection_id'
        - document_category: filter by metadata->>'document_category'
        - paper_id: filter by dc.paper_id
        - collection_name: filter by metadata->>'collection_name'

        Args:
            filter: Filter dictionary
            start_param_idx: Starting parameter index for SQL placeholders

        Returns:
            Tuple of (where_clause, params, next_param_idx)
        """
        clauses = []
        params = []
        param_idx = start_param_idx

        if 'user_id' in filter:
            clauses.append(f'dc.user_id = ${param_idx}')
            params.append(filter['user_id'])
            param_idx += 1

        if 'paper_id' in filter:
            clauses.append(f'dc.paper_id = ${param_idx}::uuid')
            params.append(filter['paper_id'])
            param_idx += 1

        if 'document_category' in filter:
            clauses.append(f"dc.metadata->>'document_category' = ${param_idx}")
            params.append(filter['document_category'])
            param_idx += 1

        if 'collection_id' in filter:
            clauses.append(f"dc.metadata->>'collection_id' = ${param_idx}")
            params.append(str(filter['collection_id']))
            param_idx += 1

        if 'collection_name' in filter:
            clauses.append(f"dc.metadata->>'collection_name' = ${param_idx}")
            params.append(filter['collection_name'])
            param_idx += 1

        where_clause = ' AND '.join(clauses) if clauses else ''
        return where_clause, params, param_idx

    def _rows_to_documents(self, rows: list[asyncpg.Record]) -> list[Document]:
        """Convert database rows to LangChain Documents."""
        documents = []
        for row in rows:
            # Handle metadata
            raw_metadata = row['metadata']
            if isinstance(raw_metadata, dict):
                metadata = dict(raw_metadata)
            elif isinstance(raw_metadata, str):
                import json

                try:
                    metadata = json.loads(raw_metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            else:
                metadata = {}

            metadata.update(
                {
                    'chunk_id': str(row['id']),
                    'chunk_type': row.get('chunk_type', 'content'),
                    'paper_title': row.get('title'),
                    'doi': row.get('doi'),
                    'authors': row.get('authors'),
                }
            )

            # Add similarity if present
            if 'similarity' in row:
                metadata['similarity'] = float(row['similarity'])

            documents.append(Document(page_content=row['content'], metadata=metadata))

        return documents

    async def similarity_search_with_score_async(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[tuple[Document, float]]:
        """
        Perform similarity search with scores (async version).
        Use this from async contexts to avoid event loop conflicts.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Metadata filter
            **kwargs: Additional parameters

        Returns:
            List of (Document, score) tuples
        """
        documents = await self.similarity_search_async(query, k, filter, **kwargs)
        return [(doc, doc.metadata.get('similarity', 0.0)) for doc in documents]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[tuple[Document, float]]:
        """
        Perform similarity search with scores (sync wrapper).
        Detects if running in async context and provides helpful error.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Metadata filter
            **kwargs: Additional parameters

        Returns:
            List of (Document, score) tuples
        """
        try:
            loop = asyncio.get_running_loop()  # noqa: F841
            raise RuntimeError(
                'similarity_search_with_score() called from async context. '
                "Use 'await similarity_search_with_score_async()' instead to avoid event loop conflicts."
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                # Safe to use asyncio.run() - no loop running
                documents = asyncio.run(
                    self._similarity_search_async(query, k, filter, **kwargs)
                )
                return [(doc, doc.metadata.get('similarity', 0.0)) for doc in documents]
            else:
                # Already in async context - raise helpful error
                raise

    async def delete_documents_async(self, paper_id: UUID) -> None:
        """
        Delete all document chunks for a paper (async version).
        Use this from async contexts to avoid event loop conflicts.

        Args:
            paper_id: UUID of the paper to delete chunks for
        """
        await self._delete_documents_async(paper_id)

    def delete_documents(self, paper_id: UUID) -> None:
        """
        Delete all document chunks for a paper (sync wrapper).
        Detects if running in async context and provides helpful error.

        Args:
            paper_id: UUID of the paper to delete chunks for
        """
        try:
            loop = asyncio.get_running_loop()  # noqa: F841
            raise RuntimeError(
                'delete_documents() called from async context. '
                "Use 'await delete_documents_async()' instead to avoid event loop conflicts."
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                # Safe to use asyncio.run() - no loop running
                asyncio.run(self._delete_documents_async(paper_id))
            else:
                # Already in async context - raise helpful error
                raise

    async def _delete_documents_async(self, paper_id: UUID) -> None:
        """Delete documents asynchronously."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                'DELETE FROM document_chunks WHERE paper_id = $1', paper_id
            )
            logger.debug(f'Deleted chunks for paper {paper_id}: {result}')

    async def get_stats_async(self) -> dict[str, Any]:
        """
        Get statistics about the vector store (async version).
        Use this from async contexts to avoid event loop conflicts.

        Returns:
            Dictionary with collection statistics
        """
        return await self._get_stats_async()

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the vector store (sync wrapper).
        Detects if running in async context and provides helpful error.

        Returns:
            Dictionary with collection statistics
        """
        try:
            loop = asyncio.get_running_loop()  # noqa: F841
            raise RuntimeError(
                'get_stats() called from async context. '
                "Use 'await get_stats_async()' instead to avoid event loop conflicts."
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                # Safe to use asyncio.run() - no loop running
                return asyncio.run(self._get_stats_async())
            else:
                # Already in async context - raise helpful error
                raise

    async def _get_stats_async(self) -> dict[str, Any]:
        """Get statistics asynchronously."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_chunks,
                    COUNT(DISTINCT paper_id) as total_papers,
                    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as indexed_chunks
                FROM document_chunks
            """)

            return {
                'total_chunks': row['total_chunks'],
                'total_papers': row['total_papers'],
                'indexed_chunks': row['indexed_chunks'],
                'document_count': row['total_chunks'],  # Alias for compatibility
                'collection_name': 'document_chunks (pgvector)',
                'backend': 'PostgreSQL + pgvector',
            }

    def get_collection_stats(self) -> dict[str, Any]:
        """
        Get collection statistics (alias for get_stats for compatibility).

        Returns:
            Dictionary with collection statistics
        """
        return self.get_stats()

    async def clear_collection_async(self) -> None:
        """
        Clear all documents from the collection (async version).

        WARNING: This permanently deletes all indexed documents.
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                'TRUNCATE TABLE document_chunks RESTART IDENTITY CASCADE'
            )
            logger.warning(f'Cleared document_chunks table: {result}')

    def clear_collection(self) -> None:
        """
        Clear all documents from the collection (sync wrapper).

        WARNING: This permanently deletes all indexed documents.
        """
        try:
            loop = asyncio.get_running_loop()  # noqa: F841
            raise RuntimeError(
                'clear_collection() called from async context. '
                "Use 'await clear_collection_async()' instead."
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                asyncio.run(self.clear_collection_async())
            else:
                raise

    def get_retriever(self, search_kwargs: dict[str, Any] | None = None):
        """
        Get a retriever interface for the vector store.

        Args:
            search_kwargs: Search parameters (k, filter, etc.)

        Returns:
            A retriever object compatible with LangChain
        """
        from langchain_core.callbacks import CallbackManagerForRetrieverRun
        from langchain_core.retrievers import BaseRetriever

        search_kwargs = search_kwargs or {}

        class PgVectorRetriever(BaseRetriever):
            """Custom retriever for pgvector store."""

            vector_store: 'VectorStoreManager'
            k: int = 4
            filter: dict[str, Any] | None = None

            class Config:
                arbitrary_types_allowed = True

            def _get_relevant_documents(
                self,
                query: str,
                *,
                run_manager: CallbackManagerForRetrieverRun | None = None,  # noqa: ARG002
            ) -> list[Document]:
                """Get relevant documents synchronously."""
                return self.vector_store.similarity_search(
                    query=query,
                    k=self.k,
                    filter=self.filter,
                )

            async def _aget_relevant_documents(
                self,
                query: str,
                *,
                run_manager: CallbackManagerForRetrieverRun | None = None,  # noqa: ARG002
            ) -> list[Document]:
                """Get relevant documents asynchronously."""
                return await self.vector_store.similarity_search_async(
                    query=query,
                    k=self.k,
                    filter=self.filter,
                )

        return PgVectorRetriever(
            vector_store=self,
            k=search_kwargs.get('k', 4),
            filter=search_kwargs.get('filter'),
        )

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            logger.debug('Closed pgvector connection pool')

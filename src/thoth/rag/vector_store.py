"""
Vector store manager for Thoth RAG system using PostgreSQL + pgvector.

This module provides database-only vector storage with no file system dependencies.
"""

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from langchain_core.documents import Document
from loguru import logger

from thoth.config import Config


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

        logger.info('VectorStoreManager initialized (PostgreSQL + pgvector)')

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
                except Exception:
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
        self, documents: list[Document], paper_id: UUID | None = None, **kwargs: Any
    ) -> list[str]:
        """Add documents asynchronously."""
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
                'jsonb',
                encoder=json.dumps,
                decoder=json.loads,
                schema='pg_catalog'
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
        filter: dict[str, Any] | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> list[Document]:
        """Perform similarity search asynchronously."""
        # Generate query embedding
        query_embedding = self.embedding_function.embed_query(query)

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Use pgvector cosine similarity search with HNSW index
            # The <=> operator uses the HNSW index automatically
            rows = await conn.fetch(
                """
                SELECT
                    dc.id,
                    dc.content,
                    dc.metadata,
                    dc.chunk_type,
                    p.title,
                    p.doi,
                    p.authors,
                    1 - (dc.embedding <=> $1) as similarity
                FROM document_chunks dc
                JOIN papers p ON dc.paper_id = p.id
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> $1
                LIMIT $2
            """,
                query_embedding,
                k,
            )

            documents = []
            for row in rows:
                metadata = dict(row['metadata']) if row['metadata'] else {}
                metadata.update(
                    {
                        'chunk_id': str(row['id']),
                        'chunk_type': row['chunk_type'],
                        'paper_title': row['title'],
                        'doi': row['doi'],
                        'authors': row['authors'],
                        'similarity': float(row['similarity']),
                    }
                )

                documents.append(
                    Document(page_content=row['content'], metadata=metadata)
                )

            logger.debug(f'Found {len(documents)} similar documents for query')
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
            result = await conn.execute('TRUNCATE TABLE document_chunks RESTART IDENTITY CASCADE')
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
        from langchain_core.retrievers import BaseRetriever
        from langchain_core.callbacks import CallbackManagerForRetrieverRun

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
                run_manager: CallbackManagerForRetrieverRun | None = None,
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
                run_manager: CallbackManagerForRetrieverRun | None = None,
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

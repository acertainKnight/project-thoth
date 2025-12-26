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
        collection_name: str | None = None,
        persist_directory: str | None = None,  # Deprecated, kept for compatibility
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
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
        return self._pool

    async def _ensure_extension(self) -> None:
        """Ensure pgvector extension is enabled."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
            logger.debug('Ensured pgvector extension is enabled')

    def add_documents(
        self,
        documents: list[Document],
        paper_id: UUID | None = None,
        **kwargs: Any
    ) -> list[str]:
        """
        Add documents to the vector store.

        Args:
            documents: List of LangChain Document objects
            paper_id: UUID of the paper these chunks belong to
            **kwargs: Additional metadata

        Returns:
            List of document IDs (UUIDs as strings)
        """
        return asyncio.run(self._add_documents_async(documents, paper_id, **kwargs))

    async def _add_documents_async(
        self,
        documents: list[Document],
        paper_id: UUID | None = None,
        **kwargs: Any
    ) -> list[str]:
        """Add documents asynchronously."""
        if not paper_id:
            raise ValueError('paper_id is required for document chunks')

        # Generate embeddings
        texts = [doc.page_content for doc in documents]
        embeddings = self.embedding_function.embed_documents(texts)

        pool = await self._get_pool()
        ids = []

        async with pool.acquire() as conn:
            for idx, (doc, embedding) in enumerate(zip(documents, embeddings)):
                metadata = {**doc.metadata, **kwargs}

                result = await conn.fetchrow("""
                    INSERT INTO document_chunks
                    (paper_id, content, chunk_index, chunk_type, metadata, embedding, token_count)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
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
                    metadata.get('chunk_type', 'content'),
                    metadata,
                    embedding,
                    len(doc.page_content.split())  # Rough token count
                )

                ids.append(str(result['id']))

        logger.debug(f'Added {len(ids)} document chunks for paper {paper_id}')
        return ids

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        **kwargs: Any
    ) -> list[Document]:
        """
        Perform similarity search.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Metadata filter (not yet implemented)
            **kwargs: Additional search parameters

        Returns:
            List of similar documents
        """
        return asyncio.run(self._similarity_search_async(query, k, filter, **kwargs))

    async def _similarity_search_async(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        **kwargs: Any
    ) -> list[Document]:
        """Perform similarity search asynchronously."""
        # Generate query embedding
        query_embedding = self.embedding_function.embed_query(query)

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Use pgvector cosine similarity search with HNSW index
            # The <=> operator uses the HNSW index automatically
            rows = await conn.fetch("""
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
            """, query_embedding, k)

            documents = []
            for row in rows:
                metadata = dict(row['metadata']) if row['metadata'] else {}
                metadata.update({
                    'chunk_id': str(row['id']),
                    'chunk_type': row['chunk_type'],
                    'paper_title': row['title'],
                    'doi': row['doi'],
                    'authors': row['authors'],
                    'similarity': float(row['similarity'])
                })

                documents.append(Document(
                    page_content=row['content'],
                    metadata=metadata
                ))

            logger.debug(f'Found {len(documents)} similar documents for query')
            return documents

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        **kwargs: Any
    ) -> list[tuple[Document, float]]:
        """
        Perform similarity search with scores.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Metadata filter
            **kwargs: Additional parameters

        Returns:
            List of (Document, score) tuples
        """
        documents = self.similarity_search(query, k, filter, **kwargs)
        return [(doc, doc.metadata.get('similarity', 0.0)) for doc in documents]

    def delete_documents(self, paper_id: UUID) -> None:
        """
        Delete all document chunks for a paper.

        Args:
            paper_id: UUID of the paper to delete chunks for
        """
        asyncio.run(self._delete_documents_async(paper_id))

    async def _delete_documents_async(self, paper_id: UUID) -> None:
        """Delete documents asynchronously."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM document_chunks WHERE paper_id = $1",
                paper_id
            )
            logger.debug(f'Deleted chunks for paper {paper_id}: {result}')

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the vector store.

        Returns:
            Dictionary with collection statistics
        """
        return asyncio.run(self._get_stats_async())

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
                'collection_name': 'document_chunks (pgvector)',
                'backend': 'PostgreSQL + pgvector'
            }

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            logger.debug('Closed pgvector connection pool')

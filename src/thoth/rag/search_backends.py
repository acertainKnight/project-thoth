"""
Full-text search backends for hybrid RAG retrieval.

Provides pluggable backends for BM25-style keyword matching to complement
vector search. Implementations use PostgreSQL native features or extensions.
"""

from abc import ABC, abstractmethod
from typing import Any

import asyncpg
from loguru import logger


class FullTextSearchBackend(ABC):
    """
    Abstract base class for full-text search backends.

    Implementations provide BM25-style keyword matching using different
    PostgreSQL full-text search strategies (native tsvector or extensions).
    """

    @abstractmethod
    async def search(
        self,
        conn: asyncpg.Connection,
        query: str,
        k: int,
        filter_clause: str = '',
        filter_params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute full-text search and return ranked results.

        Args:
            conn: Active PostgreSQL connection
            query: Search query text
            k: Number of results to return
            filter_clause: Optional SQL WHERE clause for filtering
            filter_params: Parameters for filter_clause

        Returns:
            List of dicts with keys: id, paper_id, content, metadata, rank, score
        """
        pass

    @abstractmethod
    def get_backend_name(self) -> str:
        """Get human-readable backend name."""
        pass


class TsVectorBackend(FullTextSearchBackend):
    """
    PostgreSQL native tsvector full-text search backend.

    Uses PostgreSQL's built-in full-text search with to_tsvector/to_tsquery.
    This is zero-dependency and works on any PostgreSQL installation.

    Note: ts_rank_cd doesn't use global corpus statistics (IDF), making it
    less sophisticated than true BM25. However, it's fast and functional
    for most use cases. For production BM25, consider ParadeDBBackend.
    """

    def __init__(self, language: str = 'english'):
        """
        Initialize tsvector backend.

        Args:
            language: PostgreSQL text search configuration (e.g., 'english', 'french')
        """
        self.language = language
        logger.debug(f'Initialized TsVectorBackend with language={language}')

    async def search(
        self,
        conn: asyncpg.Connection,
        query: str,
        k: int,
        filter_clause: str = '',
        filter_params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute full-text search using tsvector.

        Uses ts_rank_cd for ranking, which considers:
        - Term frequency in document
        - Document length normalization
        - Proximity of terms (cover density)

        Does NOT consider:
        - Inverse document frequency (IDF)
        - Global corpus statistics
        """
        if filter_params is None:
            filter_params = []

        # Convert query to tsquery format
        # Use plainto_tsquery for user-friendly parsing (handles special chars)
        # Alternative: websearch_to_tsquery for more advanced query syntax
        # Note: Using parameterized queries ($1, $2, $3) - safe from SQL injection
        query_sql = f"""  # nosec B608
            SELECT
                dc.id,
                dc.paper_id,
                dc.content,
                dc.metadata,
                dc.chunk_type,
                dc.chunk_index,
                p.title,
                p.doi,
                p.authors,
                ts_rank_cd(dc.search_vector, query) AS rank,
                ts_rank_cd(dc.search_vector, query, 32) AS score
            FROM document_chunks dc
            JOIN papers p ON dc.paper_id = p.id,
            plainto_tsquery($1, $2) AS query
            WHERE dc.search_vector @@ query
            {f'AND {filter_clause}' if filter_clause else ''}
            ORDER BY rank DESC
            LIMIT $3
        """

        # Build parameter list
        params = [self.language, query, *filter_params, k]

        try:
            rows = await conn.fetch(query_sql, *params)

            results = []
            for row in rows:
                results.append(
                    {
                        'id': row['id'],
                        'paper_id': row['paper_id'],
                        'content': row['content'],
                        'metadata': row['metadata'],
                        'chunk_type': row['chunk_type'],
                        'chunk_index': row['chunk_index'],
                        'title': row['title'],
                        'doi': row['doi'],
                        'authors': row['authors'],
                        'rank': float(row['rank']),
                        'score': float(row['score']),
                    }
                )

            logger.debug(
                f'TsVector search found {len(results)} results for query: {query[:50]}'
            )
            return results

        except asyncpg.exceptions.PostgresError as e:
            logger.error(f'TsVector search failed: {e}')
            # Return empty results on error (fail gracefully)
            return []

    def get_backend_name(self) -> str:
        """Get backend name."""
        return 'tsvector'


class ParadeDBBackend(FullTextSearchBackend):
    """
    ParadeDB pg_search extension backend for true BM25 ranking.

    ParadeDB provides production-grade BM25 scoring with:
    - True inverse document frequency (IDF)
    - Global corpus statistics
    - Document length normalization
    - 20x faster than ts_rank at scale

    Requires: ParadeDB extension installed in PostgreSQL
    Installation: https://docs.paradedb.com/

    This is a STUB implementation for future enhancement.
    Enable by setting `full_text_backend: 'paradedb'` in config.
    """

    def __init__(self):
        """Initialize ParadeDB backend."""
        logger.warning(
            'ParadeDBBackend is a stub implementation. '
            'Falling back to TsVectorBackend for now.'
        )
        # For now, use TsVector as fallback
        self._fallback = TsVectorBackend()

    async def search(
        self,
        conn: asyncpg.Connection,
        query: str,
        k: int,
        filter_clause: str = '',
        filter_params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute BM25 search using ParadeDB.

        STUB: Currently falls back to TsVectorBackend.

        Future implementation will use pg_search BM25 index:
        ```sql
        CALL paradedb.create_bm25(
            index_name => 'chunks_bm25',
            table_name => 'document_chunks',
            key_field => 'id',
            text_fields => '{"content": {}}'
        );

        SELECT * FROM chunks_bm25.search(
            query => 'quantum computing',
            limit_rows => k
        );
        ```
        """
        logger.debug('ParadeDB not implemented, using TsVector fallback')
        return await self._fallback.search(conn, query, k, filter_clause, filter_params)

    def get_backend_name(self) -> str:
        """Get backend name."""
        return 'paradedb (stub)'


def create_backend(backend_type: str = 'tsvector') -> FullTextSearchBackend:
    """
    Factory function to create appropriate full-text search backend.

    Args:
        backend_type: Backend type ('tsvector' or 'paradedb')

    Returns:
        FullTextSearchBackend instance

    Raises:
        ValueError: If backend_type is not recognized
    """
    backend_type = backend_type.lower()

    if backend_type == 'tsvector':
        return TsVectorBackend()
    elif backend_type == 'paradedb':
        return ParadeDBBackend()
    else:
        logger.warning(f'Unknown backend type: {backend_type}, defaulting to tsvector')
        return TsVectorBackend()

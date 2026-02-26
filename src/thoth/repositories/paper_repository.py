"""
Paper repository for managing research papers in PostgreSQL.

This module provides specialized methods for paper data access,
including search, filtering, and relationship queries.

NOTE: After 2026-01 schema migration:
- papers table is now a VIEW over paper_metadata + processed_papers
- View provides backward compatibility with same interface
- For processed papers specifically, use ProcessedPaperRepository
- For paper metadata only, query paper_metadata table directly if needed
"""

from typing import Any, Dict, List  # noqa: I001, UP035
from loguru import logger

from thoth.repositories.base import BaseRepository


class PaperRepository(BaseRepository[Dict[str, Any]]):  # noqa: UP006
    """
    Repository for managing research paper records.

    Uses the papers VIEW which provides backward compatibility by joining
    paper_metadata with processed_papers. All queries work as before.
    """

    def __init__(self, postgres_service, **kwargs):
        """Initialize paper repository."""
        super().__init__(postgres_service, table_name='papers', **kwargs)

    async def get_by_doi(
        self, doi: str, user_id: str | None = None
    ) -> Dict[str, Any] | None:  # noqa: UP006
        """
        Get a paper by DOI.

        Args:
            doi: Digital Object Identifier

        Returns:
            Optional[Dict[str, Any]]: Paper data or None
        """
        user_id = self._resolve_user_id(user_id, 'get_by_doi')
        cache_key = self._cache_key('doi', doi, user_id=user_id)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            if user_id is not None:
                query = 'SELECT * FROM papers WHERE doi = $1 AND user_id = $2'
                result = await self.postgres.fetchrow(query, doi, user_id)
            else:
                query = 'SELECT * FROM papers WHERE doi = $1'
                result = await self.postgres.fetchrow(query, doi)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(f'Failed to get paper by DOI {doi}: {e}')
            return None

    async def get_by_arxiv_id(
        self, arxiv_id: str, user_id: str | None = None
    ) -> Dict[str, Any] | None:  # noqa: UP006
        """
        Get a paper by arXiv ID.

        Args:
            arxiv_id: arXiv identifier

        Returns:
            Optional[Dict[str, Any]]: Paper data or None
        """
        user_id = self._resolve_user_id(user_id, 'get_by_arxiv_id')
        cache_key = self._cache_key('arxiv', arxiv_id, user_id=user_id)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            if user_id is not None:
                query = 'SELECT * FROM papers WHERE arxiv_id = $1 AND user_id = $2'
                result = await self.postgres.fetchrow(query, arxiv_id, user_id)
            else:
                query = 'SELECT * FROM papers WHERE arxiv_id = $1'
                result = await self.postgres.fetchrow(query, arxiv_id)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(f'Failed to get paper by arXiv ID {arxiv_id}: {e}')
            return None

    async def search_by_title(
        self, title: str, limit: int = 10, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Search papers by title (case-insensitive, partial match).

        Args:
            title: Title to search for
            limit: Maximum number of results

        Returns:
            List[Dict[str, Any]]: Matching papers
        """
        try:
            user_id = self._resolve_user_id(user_id, 'search_by_title')
            query = """
                SELECT * FROM papers
                WHERE title ILIKE $1
                {user_filter}
                ORDER BY created_at DESC
                LIMIT $2
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND user_id = $3'),
                    f'%{title}%',
                    limit,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''),
                    f'%{title}%',
                    limit,
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Failed to search papers by title '{title}': {e}")
            return []

    async def get_by_tags(
        self,
        tags: list[str],
        match_all: bool = False,
        limit: int = 50,
        user_id: str | None = None,
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get papers with specific tags.

        Args:
            tags: List of tags to search for
            match_all: If True, paper must have all tags; if False, any tag
            limit: Maximum number of results

        Returns:
            List[Dict[str, Any]]: Matching papers
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_by_tags')
            if match_all:
                # All tags must be present
                query = """
                    SELECT p.* FROM papers p
                    WHERE p.tags @> $1::text[]
                    {user_filter}
                    ORDER BY p.created_at DESC
                    LIMIT $2
                """
            else:
                # Any tag matches
                query = """
                    SELECT p.* FROM papers p
                    WHERE p.tags && $1::text[]
                    {user_filter}
                    ORDER BY p.created_at DESC
                    LIMIT $2
                """

            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND p.user_id = $3'),
                    tags,
                    limit,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''),
                    tags,
                    limit,
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get papers by tags {tags}: {e}')
            return []

    async def get_recent(
        self, limit: int = 10, offset: int = 0, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get recent papers ordered by creation date.

        Args:
            limit: Maximum number of results
            offset: Number of records to skip

        Returns:
            List[Dict[str, Any]]: Recent papers
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_recent')
            query = """
                SELECT * FROM papers
                {user_filter}
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='WHERE user_id = $3'),
                    limit,
                    offset,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''), limit, offset
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get recent papers: {e}')
            return []

    async def update_tags(
        self, paper_id: int, tags: list[str], user_id: str | None = None
    ) -> bool:
        """
        Update paper tags.

        Args:
            paper_id: Paper ID
            tags: New list of tags

        Returns:
            bool: True if successful
        """
        try:
            user_id = self._resolve_user_id(user_id, 'update_tags')
            if user_id is not None:
                query = 'UPDATE papers SET tags = $1 WHERE id = $2 AND user_id = $3'
                await self.postgres.execute(query, tags, paper_id, user_id)
            else:
                query = 'UPDATE papers SET tags = $1 WHERE id = $2'
                await self.postgres.execute(query, tags, paper_id)

            # Invalidate cache
            self._invalidate_cache(str(paper_id))

            return True

        except Exception as e:
            logger.error(f'Failed to update tags for paper {paper_id}: {e}')
            return False

    async def get_all_tags(self, user_id: str | None = None) -> List[str]:  # noqa: UP006
        """
        Get all unique tags across all papers.

        Returns:
            List[str]: List of unique tags
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_all_tags')
            query = """
                SELECT DISTINCT unnest(tags) as tag
                FROM papers
                WHERE tags IS NOT NULL
                {user_filter}
                ORDER BY tag
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND user_id = $1'),
                    user_id,
                )
            else:
                results = await self.postgres.fetch(query.format(user_filter=''))
            return [row['tag'] for row in results]

        except Exception as e:
            logger.error(f'Failed to get all tags: {e}')
            return []

    async def full_text_search(
        self, search_text: str, limit: int = 20, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Full-text search across title, abstract, and content.

        Args:
            search_text: Text to search for
            limit: Maximum number of results

        Returns:
            List[Dict[str, Any]]: Matching papers sorted by relevance
        """
        try:
            user_id = self._resolve_user_id(user_id, 'full_text_search')
            query = """
                SELECT *,
                    ts_rank(
                        to_tsvector('english', COALESCE(title, '') || ' ' ||
                                             COALESCE(abstract, '') || ' ' ||
                                             COALESCE(content, '')),
                        plainto_tsquery('english', $1)
                    ) AS rank
                FROM papers
                WHERE to_tsvector('english', COALESCE(title, '') || ' ' ||
                                           COALESCE(abstract, '') || ' ' ||
                                           COALESCE(content, ''))
                    @@ plainto_tsquery('english', $1)
                {user_filter}
                ORDER BY rank DESC
                LIMIT $2
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND user_id = $3'),
                    search_text,
                    limit,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''),
                    search_text,
                    limit,
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Failed to perform full-text search for '{search_text}': {e}")
            return []

    async def get_processed_papers(
        self, limit: int = 100, offset: int = 0, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get only papers with file paths (processed papers).

        Args:
            limit: Maximum number of results
            offset: Number of records to skip

        Returns:
            List[Dict[str, Any]]: Processed papers
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_processed_papers')
            query = """
                SELECT * FROM papers
                WHERE (
                    pdf_path IS NOT NULL
                    OR markdown_path IS NOT NULL
                    OR note_path IS NOT NULL
                )
                {user_filter}
                ORDER BY updated_at DESC
                LIMIT $1 OFFSET $2
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND user_id = $3'),
                    limit,
                    offset,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''), limit, offset
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get processed papers: {e}')
            return []

    async def get_citation_metadata(
        self, limit: int = 100, offset: int = 0, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get citation metadata entries (not processed).

        These are papers that were referenced in citations but not read by user.

        Args:
            limit: Maximum number of results
            offset: Number of records to skip

        Returns:
            List[Dict[str, Any]]: Citation metadata papers
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_citation_metadata')
            query = """
                SELECT * FROM papers
                WHERE pdf_path IS NULL
                  AND markdown_path IS NULL
                  AND note_path IS NULL
                {user_filter}
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND user_id = $3'),
                    limit,
                    offset,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''), limit, offset
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get citation metadata: {e}')
            return []

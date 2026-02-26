"""
Citation repository for managing paper citations in PostgreSQL.

This module handles citation relationships between papers.

NOTE: After 2026-01 schema migration:
- citations table references paper_metadata.id via foreign keys
- JOIN with papers view (backward compatible) or paper_metadata directly
- All existing queries work unchanged via papers view
"""

from typing import Any, Dict, List  # noqa: I001, UP035
from loguru import logger

from thoth.repositories.base import BaseRepository


class CitationRepository(BaseRepository[Dict[str, Any]]):  # noqa: UP006
    """
    Repository for managing citation records.

    Citations reference paper_metadata via foreign keys. JOINs use the papers view
    for backward compatibility, which provides all necessary paper fields.
    """

    def __init__(self, postgres_service, **kwargs):
        """Initialize citation repository."""
        super().__init__(postgres_service, table_name='citations', **kwargs)

    async def get_citations_for_paper(
        self, paper_id: int, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get all citations made by a paper.

        Args:
            paper_id: Paper ID

        Returns:
            List[Dict[str, Any]]: List of citations
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_citations_for_paper')
            query = """
                SELECT c.*, p.*
                FROM citations c
                JOIN papers p ON c.cited_paper_id = p.id
                WHERE c.citing_paper_id = $1
                {user_filter}
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND c.user_id = $2 AND p.user_id = $2'),
                    paper_id,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''), paper_id
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get citations for paper {paper_id}: {e}')
            return []

    async def get_citing_papers(
        self, paper_id: int, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get all papers that cite this paper.

        Args:
            paper_id: Paper ID

        Returns:
            List[Dict[str, Any]]: List of citing papers
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_citing_papers')
            query = """
                SELECT c.*, p.*
                FROM citations c
                JOIN papers p ON c.citing_paper_id = p.id
                WHERE c.cited_paper_id = $1
                {user_filter}
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND c.user_id = $2 AND p.user_id = $2'),
                    paper_id,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''), paper_id
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get citing papers for {paper_id}: {e}')
            return []

    async def get_citation_network(
        self, paper_id: int, depth: int = 1, user_id: str | None = None
    ) -> Dict[str, Any]:  # noqa: UP006
        """
        Get citation network up to specified depth.

        Args:
            paper_id: Starting paper ID
            depth: Network depth to traverse

        Returns:
            Dict[str, Any]: Citation network data
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_citation_network')
            # Use recursive CTE to build network
            query = """
                WITH RECURSIVE citation_tree AS (
                    -- Base case: immediate citations
                    SELECT
                        citing_paper_id,
                        cited_paper_id,
                        1 as depth
                    FROM citations
                    WHERE citing_paper_id = $1
                    {base_user_filter}

                    UNION ALL

                    -- Recursive case: follow citations
                    SELECT
                        c.citing_paper_id,
                        c.cited_paper_id,
                        ct.depth + 1
                    FROM citations c
                    JOIN citation_tree ct ON c.citing_paper_id = ct.cited_paper_id
                    WHERE ct.depth < $2
                    {recursive_user_filter}
                )
                SELECT DISTINCT * FROM citation_tree
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(
                        base_user_filter='AND user_id = $3',
                        recursive_user_filter='AND c.user_id = $3',
                    ),
                    paper_id,
                    depth,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(base_user_filter='', recursive_user_filter=''),
                    paper_id,
                    depth,
                )

            # Build network structure
            network = {'nodes': set(), 'edges': []}

            for row in results:
                network['nodes'].add(row['citing_paper_id'])
                network['nodes'].add(row['cited_paper_id'])
                network['edges'].append(
                    {
                        'source': row['citing_paper_id'],
                        'target': row['cited_paper_id'],
                        'depth': row['depth'],
                    }
                )

            network['nodes'] = list(network['nodes'])
            return network

        except Exception as e:
            logger.error(f'Failed to get citation network for paper {paper_id}: {e}')
            return {'nodes': [], 'edges': []}

    async def get_citation_count(
        self, paper_id: int, user_id: str | None = None
    ) -> int:
        """
        Get count of papers citing this paper.

        Args:
            paper_id: Paper ID

        Returns:
            int: Citation count
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_citation_count')
            query = """
                SELECT COUNT(*) FROM citations
                WHERE cited_paper_id = $1
                {user_filter}
            """
            if user_id is not None:
                return (
                    await self.postgres.fetchval(
                        query.format(user_filter='AND user_id = $2'),
                        paper_id,
                        user_id,
                    )
                    or 0
                )
            return (
                await self.postgres.fetchval(query.format(user_filter=''), paper_id)
                or 0
            )

        except Exception as e:
            logger.error(f'Failed to get citation count for paper {paper_id}: {e}')
            return 0

    async def create_citation(
        self,
        citing_paper_id: int,
        cited_paper_id: int,
        metadata: Dict | None = None,  # noqa: UP006
        user_id: str | None = None,
    ) -> int | None:
        """
        Create a citation relationship.

        Args:
            citing_paper_id: ID of paper making the citation
            cited_paper_id: ID of paper being cited
            metadata: Optional citation metadata

        Returns:
            Optional[int]: Citation ID or None
        """
        try:
            user_id = self._resolve_user_id(user_id, 'create_citation')
            query = """
                INSERT INTO citations (citing_paper_id, cited_paper_id, metadata, user_id)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (citing_paper_id, cited_paper_id, user_id) DO NOTHING
                RETURNING id
            """
            result = await self.postgres.fetchval(
                query, citing_paper_id, cited_paper_id, metadata or {}, user_id
            )

            # Invalidate cache
            self._invalidate_cache()

            return result

        except Exception as e:
            logger.error(f'Failed to create citation: {e}')
            return None

    async def get_most_cited(
        self, limit: int = 10, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get most cited papers.

        Args:
            limit: Maximum number of results

        Returns:
            List[Dict[str, Any]]: Papers with citation counts
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_most_cited')
            query = """
                SELECT
                    p.*,
                    COUNT(c.id) as citation_count
                FROM papers p
                LEFT JOIN citations c ON p.id = c.cited_paper_id {join_user_filter}
                {where_user_filter}
                GROUP BY p.id
                ORDER BY citation_count DESC
                LIMIT $1
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(
                        join_user_filter='AND c.user_id = $2',
                        where_user_filter='WHERE p.user_id = $2',
                    ),
                    limit,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(join_user_filter='', where_user_filter=''),
                    limit,
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get most cited papers: {e}')
            return []

"""
Tag repository for managing paper tags in PostgreSQL.

This module handles tag associations and tag-based queries.
"""

from typing import Any, Dict, List  # noqa: I001, UP035
from loguru import logger

from thoth.repositories.base import BaseRepository


class TagRepository(BaseRepository[Dict[str, Any]]):  # noqa: UP006
    """Repository for managing tag records."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize tag repository."""
        super().__init__(postgres_service, table_name='tags', **kwargs)

    async def get_all_unique_tags(self, user_id: str | None = None) -> List[str]:  # noqa: UP006
        """
        Get all unique tags across the system.

        Returns:
            List[str]: List of unique tag names
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_all_unique_tags')
            if user_id is not None:
                query = (
                    'SELECT DISTINCT name FROM tags WHERE user_id = $1 ORDER BY name'
                )
                results = await self.postgres.fetch(query, user_id)
            else:
                query = 'SELECT DISTINCT name FROM tags ORDER BY name'
                results = await self.postgres.fetch(query)
            return [row['name'] for row in results]

        except Exception as e:
            logger.error(f'Failed to get all unique tags: {e}')
            return []

    async def get_tag_usage_count(
        self, tag_name: str, user_id: str | None = None
    ) -> int:
        """
        Get count of papers using a specific tag.

        Args:
            tag_name: Tag name

        Returns:
            int: Usage count
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_tag_usage_count')
            query = """
                SELECT COUNT(*) FROM papers
                WHERE $1 = ANY(tags)
                {user_filter}
            """
            if user_id is not None:
                return (
                    await self.postgres.fetchval(
                        query.format(user_filter='AND user_id = $2'),
                        tag_name,
                        user_id,
                    )
                    or 0
                )
            return (
                await self.postgres.fetchval(query.format(user_filter=''), tag_name)
                or 0
            )

        except Exception as e:
            logger.error(f"Failed to get usage count for tag '{tag_name}': {e}")
            return 0

    async def get_tag_statistics(
        self, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get statistics for all tags including usage counts.

        Returns:
            List[Dict[str, Any]]: Tag statistics
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_tag_statistics')
            query = """
                SELECT
                    unnest(tags) as tag_name,
                    COUNT(*) as usage_count
                FROM papers
                WHERE tags IS NOT NULL
                {user_filter}
                GROUP BY tag_name
                ORDER BY usage_count DESC, tag_name
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND user_id = $1'),
                    user_id,
                )
            else:
                results = await self.postgres.fetch(query.format(user_filter=''))
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get tag statistics: {e}')
            return []

    async def consolidate_tag(
        self, old_tag: str, new_tag: str, user_id: str | None = None
    ) -> int:
        """
        Consolidate an old tag into a new tag across all papers.

        Args:
            old_tag: Tag to be replaced
            new_tag: Replacement tag

        Returns:
            int: Number of papers updated
        """
        try:
            user_id = self._resolve_user_id(user_id, 'consolidate_tag')
            query = """
                UPDATE papers
                SET tags = array_replace(tags, $1, $2)
                WHERE $1 = ANY(tags)
                {user_filter}
            """
            if user_id is not None:
                result = await self.postgres.execute(
                    query.format(user_filter='AND user_id = $3'),
                    old_tag,
                    new_tag,
                    user_id,
                )
            else:
                result = await self.postgres.execute(
                    query.format(user_filter=''),
                    old_tag,
                    new_tag,
                )

            # Extract number from result string "UPDATE N"
            count = int(result.split()[-1]) if result else 0

            # Invalidate cache
            self._invalidate_cache()

            logger.info(
                f"Consolidated tag '{old_tag}' to '{new_tag}' in {count} papers"
            )
            return count

        except Exception as e:
            logger.error(f"Failed to consolidate tag '{old_tag}' to '{new_tag}': {e}")
            return 0

    async def add_tag_to_paper(
        self, paper_id: int, tag: str, user_id: str | None = None
    ) -> bool:
        """
        Add a tag to a paper.

        Args:
            paper_id: Paper ID
            tag: Tag to add

        Returns:
            bool: True if successful
        """
        try:
            user_id = self._resolve_user_id(user_id, 'add_tag_to_paper')
            query = """
                UPDATE papers
                SET tags = array_append(tags, $1)
                WHERE id = $2 AND NOT ($1 = ANY(tags))
                {user_filter}
            """
            if user_id is not None:
                await self.postgres.execute(
                    query.format(user_filter='AND user_id = $3'),
                    tag,
                    paper_id,
                    user_id,
                )
            else:
                await self.postgres.execute(query.format(user_filter=''), tag, paper_id)

            # Invalidate cache
            self._invalidate_cache(str(paper_id))

            return True

        except Exception as e:
            logger.error(f"Failed to add tag '{tag}' to paper {paper_id}: {e}")
            return False

    async def remove_tag_from_paper(
        self, paper_id: int, tag: str, user_id: str | None = None
    ) -> bool:
        """
        Remove a tag from a paper.

        Args:
            paper_id: Paper ID
            tag: Tag to remove

        Returns:
            bool: True if successful
        """
        try:
            user_id = self._resolve_user_id(user_id, 'remove_tag_from_paper')
            query = """
                UPDATE papers
                SET tags = array_remove(tags, $1)
                WHERE id = $2
                {user_filter}
            """
            if user_id is not None:
                await self.postgres.execute(
                    query.format(user_filter='AND user_id = $3'),
                    tag,
                    paper_id,
                    user_id,
                )
            else:
                await self.postgres.execute(query.format(user_filter=''), tag, paper_id)

            # Invalidate cache
            self._invalidate_cache(str(paper_id))

            return True

        except Exception as e:
            logger.error(f"Failed to remove tag '{tag}' from paper {paper_id}: {e}")
            return False

    async def get_related_tags(
        self, tag: str, limit: int = 10, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get tags that frequently co-occur with the given tag.

        Args:
            tag: Reference tag
            limit: Maximum number of results

        Returns:
            List[Dict[str, Any]]: Related tags with co-occurrence counts
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_related_tags')
            query = """
                SELECT
                    unnest(tags) as related_tag,
                    COUNT(*) as cooccurrence_count
                FROM papers
                WHERE $1 = ANY(tags)
                  AND tags IS NOT NULL
                  {user_filter}
                GROUP BY related_tag
                HAVING unnest(tags) != $1
                ORDER BY cooccurrence_count DESC
                LIMIT $2
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND user_id = $3'),
                    tag,
                    limit,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''),
                    tag,
                    limit,
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Failed to get related tags for '{tag}': {e}")
            return []

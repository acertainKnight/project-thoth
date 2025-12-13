"""
Tag repository for managing paper tags in PostgreSQL.

This module handles tag associations and tag-based queries.
"""

from typing import Any, Dict, List
from loguru import logger

from thoth.repositories.base import BaseRepository


class TagRepository(BaseRepository[Dict[str, Any]]):
    """Repository for managing tag records."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize tag repository."""
        super().__init__(postgres_service, table_name='tags', **kwargs)

    async def get_all_unique_tags(self) -> List[str]:
        """
        Get all unique tags across the system.

        Returns:
            List[str]: List of unique tag names
        """
        try:
            query = "SELECT DISTINCT name FROM tags ORDER BY name"
            results = await self.postgres.fetch(query)
            return [row['name'] for row in results]

        except Exception as e:
            logger.error(f"Failed to get all unique tags: {e}")
            return []

    async def get_tag_usage_count(self, tag_name: str) -> int:
        """
        Get count of papers using a specific tag.

        Args:
            tag_name: Tag name

        Returns:
            int: Usage count
        """
        try:
            query = """
                SELECT COUNT(*) FROM papers
                WHERE $1 = ANY(tags)
            """
            return await self.postgres.fetchval(query, tag_name) or 0

        except Exception as e:
            logger.error(f"Failed to get usage count for tag '{tag_name}': {e}")
            return 0

    async def get_tag_statistics(self) -> List[Dict[str, Any]]:
        """
        Get statistics for all tags including usage counts.

        Returns:
            List[Dict[str, Any]]: Tag statistics
        """
        try:
            query = """
                SELECT
                    unnest(tags) as tag_name,
                    COUNT(*) as usage_count
                FROM papers
                WHERE tags IS NOT NULL
                GROUP BY tag_name
                ORDER BY usage_count DESC, tag_name
            """
            results = await self.postgres.fetch(query)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Failed to get tag statistics: {e}")
            return []

    async def consolidate_tag(self, old_tag: str, new_tag: str) -> int:
        """
        Consolidate an old tag into a new tag across all papers.

        Args:
            old_tag: Tag to be replaced
            new_tag: Replacement tag

        Returns:
            int: Number of papers updated
        """
        try:
            query = """
                UPDATE papers
                SET tags = array_replace(tags, $1, $2)
                WHERE $1 = ANY(tags)
            """
            result = await self.postgres.execute(query, old_tag, new_tag)

            # Extract number from result string "UPDATE N"
            count = int(result.split()[-1]) if result else 0

            # Invalidate cache
            self._invalidate_cache()

            logger.info(f"Consolidated tag '{old_tag}' to '{new_tag}' in {count} papers")
            return count

        except Exception as e:
            logger.error(f"Failed to consolidate tag '{old_tag}' to '{new_tag}': {e}")
            return 0

    async def add_tag_to_paper(self, paper_id: int, tag: str) -> bool:
        """
        Add a tag to a paper.

        Args:
            paper_id: Paper ID
            tag: Tag to add

        Returns:
            bool: True if successful
        """
        try:
            query = """
                UPDATE papers
                SET tags = array_append(tags, $1)
                WHERE id = $2 AND NOT ($1 = ANY(tags))
            """
            await self.postgres.execute(query, tag, paper_id)

            # Invalidate cache
            self._invalidate_cache(str(paper_id))

            return True

        except Exception as e:
            logger.error(f"Failed to add tag '{tag}' to paper {paper_id}: {e}")
            return False

    async def remove_tag_from_paper(self, paper_id: int, tag: str) -> bool:
        """
        Remove a tag from a paper.

        Args:
            paper_id: Paper ID
            tag: Tag to remove

        Returns:
            bool: True if successful
        """
        try:
            query = """
                UPDATE papers
                SET tags = array_remove(tags, $1)
                WHERE id = $2
            """
            await self.postgres.execute(query, tag, paper_id)

            # Invalidate cache
            self._invalidate_cache(str(paper_id))

            return True

        except Exception as e:
            logger.error(f"Failed to remove tag '{tag}' from paper {paper_id}: {e}")
            return False

    async def get_related_tags(self, tag: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get tags that frequently co-occur with the given tag.

        Args:
            tag: Reference tag
            limit: Maximum number of results

        Returns:
            List[Dict[str, Any]]: Related tags with co-occurrence counts
        """
        try:
            query = """
                SELECT
                    unnest(tags) as related_tag,
                    COUNT(*) as cooccurrence_count
                FROM papers
                WHERE $1 = ANY(tags)
                  AND tags IS NOT NULL
                GROUP BY related_tag
                HAVING unnest(tags) != $1
                ORDER BY cooccurrence_count DESC
                LIMIT $2
            """
            results = await self.postgres.fetch(query, tag, limit)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Failed to get related tags for '{tag}': {e}")
            return []

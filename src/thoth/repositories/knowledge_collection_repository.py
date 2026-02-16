"""
Repository for knowledge collections.

Handles CRUD operations for the knowledge_collections table.
"""

from typing import Any
from uuid import UUID

from loguru import logger


class KnowledgeCollectionRepository:
    """Repository for managing knowledge collections."""

    def __init__(self, postgres_service):
        """
        Initialize the repository.

        Args:
            postgres_service: PostgreSQL service instance
        """
        self.db = postgres_service

    async def create(self, name: str, description: str | None = None) -> dict[str, Any]:
        """
        Create a new knowledge collection.

        Args:
            name: Collection name (must be unique)
            description: Optional description

        Returns:
            Dictionary with collection data

        Raises:
            ValueError: If collection with name already exists
        """
        async with self.db.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO knowledge_collections (name, description)
                    VALUES ($1, $2)
                    RETURNING id, name, description, created_at, updated_at
                    """,
                    name,
                    description,
                )

                logger.info(f'Created knowledge collection: {name} (id: {row["id"]})')

                return dict(row)

            except Exception as e:
                if 'unique constraint' in str(e).lower():
                    raise ValueError(
                        f'Collection with name "{name}" already exists'
                    ) from e
                raise

    async def get_by_id(self, collection_id: UUID) -> dict[str, Any] | None:
        """
        Get collection by ID.

        Args:
            collection_id: Collection UUID

        Returns:
            Collection dictionary or None if not found
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, description, created_at, updated_at
                FROM knowledge_collections
                WHERE id = $1
                """,
                collection_id,
            )

            return dict(row) if row else None

    async def get_by_name(self, name: str) -> dict[str, Any] | None:
        """
        Get collection by name.

        Args:
            name: Collection name

        Returns:
            Collection dictionary or None if not found
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, description, created_at, updated_at
                FROM knowledge_collections
                WHERE name = $1
                """,
                name,
            )

            return dict(row) if row else None

    async def list_all(self) -> list[dict[str, Any]]:
        """
        List all collections with document counts.

        Returns:
            List of collection dictionaries with document_count field
        """
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    kc.id,
                    kc.name,
                    kc.description,
                    kc.created_at,
                    kc.updated_at,
                    COUNT(pm.id) as document_count
                FROM knowledge_collections kc
                LEFT JOIN paper_metadata pm ON pm.collection_id = kc.id
                GROUP BY kc.id, kc.name, kc.description, kc.created_at, kc.updated_at
                ORDER BY kc.name
                """
            )

            return [dict(row) for row in rows]

    async def update(
        self,
        collection_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Update collection.

        Args:
            collection_id: Collection UUID
            name: New name (optional)
            description: New description (optional)

        Returns:
            Updated collection dictionary or None if not found

        Raises:
            ValueError: If new name conflicts with existing collection
        """
        async with self.db.acquire() as conn:
            # Build dynamic update query
            updates = []
            params = [collection_id]
            param_num = 2

            if name is not None:
                updates.append(f'name = ${param_num}')
                params.append(name)
                param_num += 1

            if description is not None:
                updates.append(f'description = ${param_num}')
                params.append(description)
                param_num += 1

            if not updates:
                return await self.get_by_id(collection_id)

            updates.append('updated_at = NOW()')

            try:
                row = await conn.fetchrow(
                    f"""
                    UPDATE knowledge_collections
                    SET {', '.join(updates)}
                    WHERE id = $1
                    RETURNING id, name, description, created_at, updated_at
                    """,  # nosec B608
                    *params,
                )

                if row:
                    logger.info(
                        f'Updated knowledge collection: {row["name"]} (id: {collection_id})'
                    )
                    return dict(row)

                return None

            except Exception as e:
                if 'unique constraint' in str(e).lower():
                    raise ValueError(
                        f'Collection with name "{name}" already exists'
                    ) from e
                raise

    async def delete(self, collection_id: UUID, delete_documents: bool = False) -> bool:
        """
        Delete collection.

        Args:
            collection_id: Collection UUID
            delete_documents: If True, also delete documents in collection.
                            If False, documents remain but collection_id set to NULL

        Returns:
            True if deleted, False if not found
        """
        async with self.db.acquire() as conn:
            if delete_documents:
                # Delete documents (CASCADE will handle document_chunks)
                await conn.execute(
                    """
                    DELETE FROM processed_papers
                    WHERE paper_id IN (
                        SELECT id FROM paper_metadata WHERE collection_id = $1
                    )
                    """,
                    collection_id,
                )

                await conn.execute(
                    """
                    DELETE FROM paper_metadata
                    WHERE collection_id = $1
                    """,
                    collection_id,
                )

                logger.info(
                    f'Deleted documents in collection {collection_id} before deleting collection'
                )

            result = await conn.execute(
                'DELETE FROM knowledge_collections WHERE id = $1', collection_id
            )

            deleted = result.split()[-1] == '1'

            if deleted:
                logger.info(f'Deleted knowledge collection: {collection_id}')

            return deleted

    async def get_document_count(self, collection_id: UUID) -> int:
        """
        Get count of documents in collection.

        Args:
            collection_id: Collection UUID

        Returns:
            Number of documents
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM paper_metadata
                WHERE collection_id = $1
                """,
                collection_id,
            )

            return row['count'] if row else 0

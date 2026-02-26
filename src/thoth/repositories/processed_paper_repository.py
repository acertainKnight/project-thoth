"""
Repository for processed_papers table - papers user has read.

NOTE: After 2026-01 schema migration:
- processed_papers table tracks papers user has read (with file paths)
- References paper_metadata.id via paper_id foreign key
- Contains file paths (pdf_path, markdown_path, note_path)
- Contains user interaction data (rating, tags, notes)
"""

from typing import Any
from uuid import UUID

from thoth.repositories.base import BaseRepository


class ProcessedPaperRepository(BaseRepository[dict[str, Any]]):
    """Repository for processed_papers table - papers user has read."""

    def __init__(self, postgres_service, **kwargs):
        super().__init__(postgres_service, table_name='processed_papers', **kwargs)

    async def get_by_paper_id(
        self, paper_id: UUID, user_id: str | None = None
    ) -> dict | None:
        """Get processed paper entry by paper_metadata ID."""
        user_id = self._resolve_user_id(user_id, 'get_by_paper_id')
        if user_id is not None:
            query = (
                'SELECT * FROM processed_papers WHERE paper_id = $1 AND user_id = $2'
            )
            return await self.postgres.fetchrow(query, paper_id, user_id)
        query = 'SELECT * FROM processed_papers WHERE paper_id = $1'
        return await self.postgres.fetchrow(query, paper_id)

    async def get_with_metadata(
        self, processed_paper_id: UUID, user_id: str | None = None
    ) -> dict | None:
        """Get processed paper with full paper metadata."""
        user_id = self._resolve_user_id(user_id, 'get_with_metadata')
        query = """
            SELECT
                pp.*,
                pm.doi, pm.arxiv_id, pm.title, pm.authors, pm.abstract,
                pm.publication_date, pm.year, pm.journal, pm.url, pm.pdf_url
            FROM processed_papers pp
            JOIN paper_metadata pm ON pm.id = pp.paper_id
            WHERE pp.id = $1
            {user_filter}
        """
        if user_id is not None:
            return await self.postgres.fetchrow(
                query.format(user_filter='AND pp.user_id = $2'),
                processed_paper_id,
                user_id,
            )
        return await self.postgres.fetchrow(
            query.format(user_filter=''), processed_paper_id
        )

    async def get_all_with_metadata(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = 'updated_at',
        order_dir: str = 'DESC',
        user_id: str | None = None,
    ) -> list[dict]:
        """Get all processed papers with metadata."""
        user_id = self._resolve_user_id(user_id, 'get_all_with_metadata')
        query = f"""
            SELECT
                pp.*,
                pm.doi, pm.arxiv_id, pm.title, pm.authors, pm.abstract,
                pm.publication_date, pm.year, pm.journal, pm.url, pm.pdf_url
            FROM processed_papers pp
            JOIN paper_metadata pm ON pm.id = pp.paper_id
            {'WHERE pp.user_id = $3' if user_id is not None else ''}
            ORDER BY pp.{order_by} {order_dir}
            LIMIT $1 OFFSET $2
        """
        if user_id is not None:
            return await self.postgres.fetch(query, limit, offset, user_id)
        return await self.postgres.fetch(query, limit, offset)

    async def create(
        self,
        paper_id: UUID,
        pdf_path: str | None = None,
        markdown_path: str | None = None,
        note_path: str | None = None,
        obsidian_uri: str | None = None,
        processing_status: str = 'pending',
        user_id: str | None = None,
        **kwargs,
    ) -> UUID:
        """Create new processed paper entry."""
        user_id = self._resolve_user_id(user_id, 'create')
        query = """
            INSERT INTO processed_papers (
                paper_id, pdf_path, markdown_path, note_path, obsidian_uri,
                processing_status, processed_at, user_notes, user_tags, user_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (paper_id, user_id) DO UPDATE SET
                pdf_path = COALESCE(EXCLUDED.pdf_path, processed_papers.pdf_path),
                markdown_path = COALESCE(EXCLUDED.markdown_path, processed_papers.markdown_path),
                note_path = COALESCE(EXCLUDED.note_path, processed_papers.note_path),
                obsidian_uri = COALESCE(EXCLUDED.obsidian_uri, processed_papers.obsidian_uri),
                processing_status = EXCLUDED.processing_status,
                updated_at = NOW()
            RETURNING id
        """

        return await self.postgres.fetchval(
            query,
            paper_id,
            pdf_path,
            markdown_path,
            note_path,
            obsidian_uri,
            processing_status,
            kwargs.get('processed_at'),
            kwargs.get('user_notes'),
            kwargs.get('user_tags'),
            user_id,
        )

    async def update_paths(
        self,
        paper_id: UUID,
        pdf_path: str | None = None,
        markdown_path: str | None = None,
        note_path: str | None = None,
        obsidian_uri: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        """Update file paths for a processed paper."""
        user_id = self._resolve_user_id(user_id, 'update_paths')
        query = """
            UPDATE processed_papers
            SET
                pdf_path = COALESCE($2, pdf_path),
                markdown_path = COALESCE($3, markdown_path),
                note_path = COALESCE($4, note_path),
                obsidian_uri = COALESCE($5, obsidian_uri),
                updated_at = NOW()
            WHERE paper_id = $1
            {user_filter}
        """
        if user_id is not None:
            result = await self.postgres.execute(
                query.format(user_filter='AND user_id = $6'),
                paper_id,
                pdf_path,
                markdown_path,
                note_path,
                obsidian_uri,
                user_id,
            )
        else:
            result = await self.postgres.execute(
                query.format(user_filter=''),
                paper_id,
                pdf_path,
                markdown_path,
                note_path,
                obsidian_uri,
            )

        return result == 'UPDATE 1'

    async def update_status(
        self,
        paper_id: UUID,
        processing_status: str,
        processed_at=None,
        user_id: str | None = None,
    ) -> bool:
        """Update processing status."""
        user_id = self._resolve_user_id(user_id, 'update_status')
        query = """
            UPDATE processed_papers
            SET
                processing_status = $2,
                processed_at = COALESCE($3, processed_at),
                updated_at = NOW()
            WHERE paper_id = $1
            {user_filter}
        """
        if user_id is not None:
            result = await self.postgres.execute(
                query.format(user_filter='AND user_id = $4'),
                paper_id,
                processing_status,
                processed_at,
                user_id,
            )
        else:
            result = await self.postgres.execute(
                query.format(user_filter=''),
                paper_id,
                processing_status,
                processed_at,
            )
        return result == 'UPDATE 1'

    async def update_user_data(
        self,
        paper_id: UUID,
        user_rating: int | None = None,
        user_notes: str | None = None,
        user_tags: dict | None = None,
        user_id: str | None = None,
    ) -> bool:
        """Update user interaction data."""
        user_id = self._resolve_user_id(user_id, 'update_user_data')
        query = """
            UPDATE processed_papers
            SET
                user_rating = COALESCE($2, user_rating),
                user_notes = COALESCE($3, user_notes),
                user_tags = COALESCE($4, user_tags),
                updated_at = NOW()
            WHERE paper_id = $1
            {user_filter}
        """
        if user_id is not None:
            result = await self.postgres.execute(
                query.format(user_filter='AND user_id = $5'),
                paper_id,
                user_rating,
                user_notes,
                user_tags,
                user_id,
            )
        else:
            result = await self.postgres.execute(
                query.format(user_filter=''),
                paper_id,
                user_rating,
                user_notes,
                user_tags,
            )
        return result == 'UPDATE 1'

    async def get_by_status(
        self, processing_status: str, limit: int = 100, user_id: str | None = None
    ) -> list[dict]:
        """Get processed papers by status with metadata."""
        user_id = self._resolve_user_id(user_id, 'get_by_status')
        query = """
            SELECT
                pp.*,
                pm.doi, pm.arxiv_id, pm.title, pm.authors, pm.abstract,
                pm.publication_date, pm.year, pm.journal, pm.url, pm.pdf_url
            FROM processed_papers pp
            JOIN paper_metadata pm ON pm.id = pp.paper_id
            WHERE pp.processing_status = $1
            {user_filter}
            ORDER BY pp.updated_at DESC
            LIMIT $2
        """
        if user_id is not None:
            return await self.postgres.fetch(
                query.format(user_filter='AND pp.user_id = $3'),
                processing_status,
                limit,
                user_id,
            )
        return await self.postgres.fetch(
            query.format(user_filter=''),
            processing_status,
            limit,
        )

    async def get_recently_accessed(
        self, limit: int = 20, user_id: str | None = None
    ) -> list[dict]:
        """Get recently accessed papers."""
        user_id = self._resolve_user_id(user_id, 'get_recently_accessed')
        query = """
            SELECT
                pp.*,
                pm.doi, pm.arxiv_id, pm.title, pm.authors, pm.abstract,
                pm.publication_date, pm.year, pm.journal, pm.url, pm.pdf_url
            FROM processed_papers pp
            JOIN paper_metadata pm ON pm.id = pp.paper_id
            WHERE pp.last_accessed IS NOT NULL
            {user_filter}
            ORDER BY pp.last_accessed DESC
            LIMIT $1
        """
        if user_id is not None:
            return await self.postgres.fetch(
                query.format(user_filter='AND pp.user_id = $2'),
                limit,
                user_id,
            )
        return await self.postgres.fetch(query.format(user_filter=''), limit)

    async def get_by_rating(
        self, min_rating: int, limit: int = 100, user_id: str | None = None
    ) -> list[dict]:
        """Get papers with minimum rating."""
        user_id = self._resolve_user_id(user_id, 'get_by_rating')
        query = """
            SELECT
                pp.*,
                pm.doi, pm.arxiv_id, pm.title, pm.authors, pm.abstract,
                pm.publication_date, pm.year, pm.journal, pm.url, pm.pdf_url
            FROM processed_papers pp
            JOIN paper_metadata pm ON pm.id = pp.paper_id
            WHERE pp.user_rating >= $1
            {user_filter}
            ORDER BY pp.user_rating DESC, pp.updated_at DESC
            LIMIT $2
        """
        if user_id is not None:
            return await self.postgres.fetch(
                query.format(user_filter='AND pp.user_id = $3'),
                min_rating,
                limit,
                user_id,
            )
        return await self.postgres.fetch(
            query.format(user_filter=''), min_rating, limit
        )

    async def count_by_status(self, user_id: str | None = None) -> dict[str, int]:
        """Get count of papers by processing status."""
        user_id = self._resolve_user_id(user_id, 'count_by_status')
        query = """
            SELECT processing_status, COUNT(*) as count
            FROM processed_papers
            {user_filter}
            GROUP BY processing_status
        """
        if user_id is not None:
            rows = await self.postgres.fetch(
                query.format(user_filter='WHERE user_id = $1'),
                user_id,
            )
        else:
            rows = await self.postgres.fetch(query.format(user_filter=''))
        return {row['processing_status']: row['count'] for row in rows}

    async def has_processed_paper(
        self, paper_id: UUID, user_id: str | None = None
    ) -> bool:
        """Check if paper has been processed."""
        user_id = self._resolve_user_id(user_id, 'has_processed_paper')
        if user_id is not None:
            query = 'SELECT EXISTS(SELECT 1 FROM processed_papers WHERE paper_id = $1 AND user_id = $2)'
            return await self.postgres.fetchval(query, paper_id, user_id)
        query = 'SELECT EXISTS(SELECT 1 FROM processed_papers WHERE paper_id = $1)'
        return await self.postgres.fetchval(query, paper_id)

    async def delete_by_paper_id(
        self, paper_id: UUID, user_id: str | None = None
    ) -> bool:
        """Delete processed paper entry (paper_metadata remains)."""
        user_id = self._resolve_user_id(user_id, 'delete_by_paper_id')
        if user_id is not None:
            query = 'DELETE FROM processed_papers WHERE paper_id = $1 AND user_id = $2'
            result = await self.postgres.execute(query, paper_id, user_id)
        else:
            query = 'DELETE FROM processed_papers WHERE paper_id = $1'
            result = await self.postgres.execute(query, paper_id)
        return result == 'DELETE 1'

    async def get_statistics(self, user_id: str | None = None) -> dict:
        """Get statistics about processed papers."""
        user_id = self._resolve_user_id(user_id, 'get_statistics')
        query = """
            SELECT
                COUNT(*) as total_processed,
                COUNT(*) FILTER (WHERE pdf_path IS NOT NULL) as with_pdf,
                COUNT(*) FILTER (WHERE markdown_path IS NOT NULL) as with_markdown,
                COUNT(*) FILTER (WHERE note_path IS NOT NULL) as with_note,
                COUNT(*) FILTER (WHERE user_rating IS NOT NULL) as with_rating,
                ROUND(AVG(user_rating)::numeric, 2) as avg_rating,
                COUNT(DISTINCT processing_status) as status_count
            FROM processed_papers
            {user_filter}
        """
        if user_id is not None:
            row = await self.postgres.fetchrow(
                query.format(user_filter='WHERE user_id = $1'),
                user_id,
            )
        else:
            row = await self.postgres.fetchrow(query.format(user_filter=''))
        return dict(row) if row else {}

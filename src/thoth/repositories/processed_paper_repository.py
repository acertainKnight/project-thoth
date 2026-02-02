"""
Repository for processed_papers table - papers user has read.

NOTE: After 2026-01 schema migration:
- processed_papers table tracks papers user has read (with file paths)
- References paper_metadata.id via paper_id foreign key
- Contains file paths (pdf_path, markdown_path, note_path)
- Contains user interaction data (rating, tags, notes)
"""

from typing import Any, Optional
from uuid import UUID

from loguru import logger

from thoth.repositories.base import BaseRepository


class ProcessedPaperRepository(BaseRepository[dict[str, Any]]):
    """Repository for processed_papers table - papers user has read."""

    def __init__(self, postgres_service, **kwargs):
        super().__init__(postgres_service, table_name='processed_papers', **kwargs)

    async def get_by_paper_id(self, paper_id: UUID) -> Optional[dict]:
        """Get processed paper entry by paper_metadata ID."""
        query = "SELECT * FROM processed_papers WHERE paper_id = $1"
        return await self.postgres.fetchrow(query, paper_id)

    async def get_with_metadata(self, processed_paper_id: UUID) -> Optional[dict]:
        """Get processed paper with full paper metadata."""
        query = """
            SELECT
                pp.*,
                pm.doi, pm.arxiv_id, pm.title, pm.authors, pm.abstract,
                pm.publication_date, pm.year, pm.journal, pm.url, pm.pdf_url
            FROM processed_papers pp
            JOIN paper_metadata pm ON pm.id = pp.paper_id
            WHERE pp.id = $1
        """
        return await self.postgres.fetchrow(query, processed_paper_id)

    async def get_all_with_metadata(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = 'updated_at',
        order_dir: str = 'DESC',
    ) -> list[dict]:
        """Get all processed papers with metadata."""
        query = f"""
            SELECT
                pp.*,
                pm.doi, pm.arxiv_id, pm.title, pm.authors, pm.abstract,
                pm.publication_date, pm.year, pm.journal, pm.url, pm.pdf_url
            FROM processed_papers pp
            JOIN paper_metadata pm ON pm.id = pp.paper_id
            ORDER BY pp.{order_by} {order_dir}
            LIMIT $1 OFFSET $2
        """
        return await self.postgres.fetch(query, limit, offset)

    async def create(
        self,
        paper_id: UUID,
        pdf_path: Optional[str] = None,
        markdown_path: Optional[str] = None,
        note_path: Optional[str] = None,
        obsidian_uri: Optional[str] = None,
        processing_status: str = 'pending',
        **kwargs,
    ) -> UUID:
        """Create new processed paper entry."""
        query = """
            INSERT INTO processed_papers (
                paper_id, pdf_path, markdown_path, note_path, obsidian_uri,
                processing_status, processed_at, user_notes, user_tags
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (paper_id) DO UPDATE SET
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
        )

    async def update_paths(
        self,
        paper_id: UUID,
        pdf_path: Optional[str] = None,
        markdown_path: Optional[str] = None,
        note_path: Optional[str] = None,
        obsidian_uri: Optional[str] = None,
    ) -> bool:
        """Update file paths for a processed paper."""
        query = """
            UPDATE processed_papers
            SET
                pdf_path = COALESCE($2, pdf_path),
                markdown_path = COALESCE($3, markdown_path),
                note_path = COALESCE($4, note_path),
                obsidian_uri = COALESCE($5, obsidian_uri),
                updated_at = NOW()
            WHERE paper_id = $1
        """

        result = await self.postgres.execute(
            query, paper_id, pdf_path, markdown_path, note_path, obsidian_uri
        )

        return result == 'UPDATE 1'

    async def update_status(
        self, paper_id: UUID, processing_status: str, processed_at=None
    ) -> bool:
        """Update processing status."""
        query = """
            UPDATE processed_papers
            SET
                processing_status = $2,
                processed_at = COALESCE($3, processed_at),
                updated_at = NOW()
            WHERE paper_id = $1
        """

        result = await self.postgres.execute(query, paper_id, processing_status, processed_at)
        return result == 'UPDATE 1'

    async def update_user_data(
        self,
        paper_id: UUID,
        user_rating: Optional[int] = None,
        user_notes: Optional[str] = None,
        user_tags: Optional[dict] = None,
    ) -> bool:
        """Update user interaction data."""
        query = """
            UPDATE processed_papers
            SET
                user_rating = COALESCE($2, user_rating),
                user_notes = COALESCE($3, user_notes),
                user_tags = COALESCE($4, user_tags),
                updated_at = NOW()
            WHERE paper_id = $1
        """

        result = await self.postgres.execute(query, paper_id, user_rating, user_notes, user_tags)
        return result == 'UPDATE 1'

    async def get_by_status(self, processing_status: str, limit: int = 100) -> list[dict]:
        """Get processed papers by status with metadata."""
        query = """
            SELECT
                pp.*,
                pm.doi, pm.arxiv_id, pm.title, pm.authors, pm.abstract,
                pm.publication_date, pm.year, pm.journal, pm.url, pm.pdf_url
            FROM processed_papers pp
            JOIN paper_metadata pm ON pm.id = pp.paper_id
            WHERE pp.processing_status = $1
            ORDER BY pp.updated_at DESC
            LIMIT $2
        """
        return await self.postgres.fetch(query, processing_status, limit)

    async def get_recently_accessed(self, limit: int = 20) -> list[dict]:
        """Get recently accessed papers."""
        query = """
            SELECT
                pp.*,
                pm.doi, pm.arxiv_id, pm.title, pm.authors, pm.abstract,
                pm.publication_date, pm.year, pm.journal, pm.url, pm.pdf_url
            FROM processed_papers pp
            JOIN paper_metadata pm ON pm.id = pp.paper_id
            WHERE pp.last_accessed IS NOT NULL
            ORDER BY pp.last_accessed DESC
            LIMIT $1
        """
        return await self.postgres.fetch(query, limit)

    async def get_by_rating(self, min_rating: int, limit: int = 100) -> list[dict]:
        """Get papers with minimum rating."""
        query = """
            SELECT
                pp.*,
                pm.doi, pm.arxiv_id, pm.title, pm.authors, pm.abstract,
                pm.publication_date, pm.year, pm.journal, pm.url, pm.pdf_url
            FROM processed_papers pp
            JOIN paper_metadata pm ON pm.id = pp.paper_id
            WHERE pp.user_rating >= $1
            ORDER BY pp.user_rating DESC, pp.updated_at DESC
            LIMIT $2
        """
        return await self.postgres.fetch(query, min_rating, limit)

    async def count_by_status(self) -> dict[str, int]:
        """Get count of papers by processing status."""
        query = """
            SELECT processing_status, COUNT(*) as count
            FROM processed_papers
            GROUP BY processing_status
        """
        rows = await self.postgres.fetch(query)
        return {row['processing_status']: row['count'] for row in rows}

    async def has_processed_paper(self, paper_id: UUID) -> bool:
        """Check if paper has been processed."""
        query = "SELECT EXISTS(SELECT 1 FROM processed_papers WHERE paper_id = $1)"
        return await self.postgres.fetchval(query, paper_id)

    async def delete_by_paper_id(self, paper_id: UUID) -> bool:
        """Delete processed paper entry (paper_metadata remains)."""
        query = "DELETE FROM processed_papers WHERE paper_id = $1"
        result = await self.postgres.execute(query, paper_id)
        return result == 'DELETE 1'

    async def get_statistics(self) -> dict:
        """Get statistics about processed papers."""
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
        """
        row = await self.postgres.fetchrow(query)
        return dict(row) if row else {}

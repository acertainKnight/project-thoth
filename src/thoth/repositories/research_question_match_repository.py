"""
Repository for research_question_matches - papers matched to research questions.

NOTE: After 2026-01 schema migration:
- Renamed from ArticleRepository (discovered_articles → research_question_matches)
- Uses paper_metadata table via paper_id foreign key
- Matches link papers to research questions with relevance scoring
- Deduplication handled at paper_metadata level
"""

import json
from typing import Any
from uuid import UUID

from dateutil import parser as dateutil_parser
from loguru import logger

from thoth.repositories.base import BaseRepository


class ResearchQuestionMatchRepository(BaseRepository[dict[str, Any]]):
    """Repository for research_question_matches - papers matched to research questions."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize research question match repository."""
        super().__init__(
            postgres_service, table_name='research_question_matches', **kwargs
        )

    async def find_or_create_paper(
        self,
        doi: str | None = None,
        arxiv_id: str | None = None,
        title: str = '',
        **paper_data,
    ) -> tuple[UUID, bool]:
        """
        Find existing paper or create in paper_metadata with deduplication.

        Args:
            doi: Digital Object Identifier
            arxiv_id: arXiv identifier
            title: Paper title
            **paper_data: Additional paper metadata (authors, abstract, url, pdf_url, etc.)

        Returns:
            tuple[UUID, bool]: (paper_id, created) where created=True if new paper
        """
        try:
            # Use database function to find duplicate
            existing_id = await self.postgres.fetchval(
                'SELECT find_duplicate_paper($1, $2, $3)',
                doi,
                arxiv_id,
                title,
            )

            if existing_id:
                return existing_id, False

            # Create new paper in paper_metadata
            title_normalized = self._normalize_title_python(title)

            # Convert authors list to JSON string if it's a list
            authors = paper_data.get('authors')
            if isinstance(authors, list):
                authors = json.dumps(authors)

            # Convert publication_date string to datetime if needed
            publication_date = paper_data.get('publication_date')
            if isinstance(publication_date, str):
                try:
                    publication_date = dateutil_parser.parse(publication_date)
                except (ValueError, TypeError):
                    publication_date = None

            insert_data = {
                'doi': doi,
                'arxiv_id': arxiv_id,
                'title': title,
                'title_normalized': title_normalized,
                'source_of_truth': 'discovered',
                'authors': authors,
                'abstract': paper_data.get('abstract'),
                'publication_date': publication_date,
                'year': paper_data.get('year'),
                'journal': paper_data.get('journal'),
                'url': paper_data.get('url'),
                'pdf_url': paper_data.get('pdf_url'),
            }

            # Insert into paper_metadata
            query = """
                INSERT INTO paper_metadata (
                    doi, arxiv_id, title, title_normalized, authors, abstract,
                    publication_date, year, journal, url, pdf_url, source_of_truth
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
            """

            paper_id = await self.postgres.fetchval(
                query,
                insert_data['doi'],
                insert_data['arxiv_id'],
                insert_data['title'],
                insert_data['title_normalized'],
                insert_data['authors'],
                insert_data['abstract'],
                insert_data['publication_date'],
                insert_data['year'],
                insert_data['journal'],
                insert_data['url'],
                insert_data['pdf_url'],
                insert_data['source_of_truth'],
            )

            return paper_id, True

        except Exception as e:
            logger.error(f'Failed to find or create paper: {e}', exc_info=True)
            raise

    async def create_match(
        self,
        paper_id: UUID,
        question_id: UUID,
        relevance_score: float,
        matched_keywords: list[str] | None = None,
        matched_topics: list[str] | None = None,
        matched_authors: list[str] | None = None,
        discovered_via_source: str | None = None,
    ) -> UUID:
        """
        Create a research question match.

        Args:
            paper_id: Paper UUID from paper_metadata
            question_id: Research question UUID
            relevance_score: Relevance score (0-1)
            matched_keywords: Keywords that matched
            matched_topics: Topics that matched
            matched_authors: Authors that matched
            discovered_via_source: Source name that found this match

        Returns:
            UUID: Match ID
        """
        query = """
            INSERT INTO research_question_matches (
                paper_id, question_id, relevance_score,
                matched_keywords, matched_topics, matched_authors,
                discovered_via_source
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (paper_id, question_id) DO UPDATE SET
                relevance_score = GREATEST(
                    research_question_matches.relevance_score,
                    EXCLUDED.relevance_score
                ),
                matched_keywords = EXCLUDED.matched_keywords,
                matched_topics = EXCLUDED.matched_topics,
                matched_authors = EXCLUDED.matched_authors,
                updated_at = NOW()
            RETURNING id
        """

        return await self.postgres.fetchval(
            query,
            paper_id,
            question_id,
            relevance_score,
            matched_keywords or [],
            matched_topics or [],
            matched_authors or [],
            discovered_via_source,
        )

    async def get_matches_for_question(
        self,
        question_id: UUID,
        limit: int = 100,
        min_relevance: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Get all papers matched to a research question with paper metadata.

        Args:
            question_id: Research question UUID
            limit: Maximum results
            min_relevance: Minimum relevance score

        Returns:
            list[dict]: Matches with full paper metadata
        """
        query = """
            SELECT
                rqm.id as match_id,
                rqm.paper_id,
                rqm.question_id,
                rqm.relevance_score,
                rqm.matched_keywords,
                rqm.matched_topics,
                rqm.matched_authors,
                rqm.discovered_via_source,
                rqm.is_viewed,
                rqm.is_bookmarked,
                rqm.user_sentiment,
                rqm.matched_at,
                pm.doi,
                pm.arxiv_id,
                pm.title,
                pm.authors,
                pm.abstract,
                pm.publication_date,
                pm.year,
                pm.journal,
                pm.url,
                pm.pdf_url
            FROM research_question_matches rqm
            JOIN paper_metadata pm ON pm.id = rqm.paper_id
            WHERE rqm.question_id = $1
              AND rqm.relevance_score >= $2
            ORDER BY rqm.relevance_score DESC, rqm.matched_at DESC
            LIMIT $3
        """

        results = await self.postgres.fetch(query, question_id, min_relevance, limit)
        return [dict(row) for row in results]

    async def get_matches_for_paper(self, paper_id: UUID) -> list[dict[str, Any]]:
        """
        Get all research questions matched to a paper.

        Args:
            paper_id: Paper UUID from paper_metadata

        Returns:
            list[dict]: Matches with research question details
        """
        query = """
            SELECT
                rqm.*,
                rq.title as question_title,
                rq.description as question_description
            FROM research_question_matches rqm
            JOIN research_questions rq ON rq.id = rqm.question_id
            WHERE rqm.paper_id = $1
            ORDER BY rqm.relevance_score DESC
        """

        results = await self.postgres.fetch(query, paper_id)
        return [dict(row) for row in results]

    async def update_user_interaction(
        self,
        match_id: UUID,
        is_viewed: bool | None = None,
        is_bookmarked: bool | None = None,
        user_sentiment: str | None = None,
    ) -> bool:
        """
        Update user interaction flags for a match.

        Args:
            match_id: Match UUID
            is_viewed: Mark as viewed
            is_bookmarked: Mark as bookmarked
            user_sentiment: User sentiment ('like', 'dislike', 'neutral')

        Returns:
            bool: Success
        """
        updates = []
        values = []
        param_count = 1

        if is_viewed is not None:
            updates.append(f'is_viewed = ${param_count}')
            values.append(is_viewed)
            param_count += 1

        if is_bookmarked is not None:
            updates.append(f'is_bookmarked = ${param_count}')
            values.append(is_bookmarked)
            param_count += 1

        if user_sentiment is not None:
            updates.append(f'user_sentiment = ${param_count}')
            values.append(user_sentiment)
            param_count += 1
            updates.append('sentiment_recorded_at = NOW()')

        if not updates:
            return False

        updates.append('updated_at = NOW()')

        query = f"""
            UPDATE research_question_matches
            SET {', '.join(updates)}
            WHERE id = ${param_count}
        """

        values.append(match_id)
        result = await self.postgres.execute(query, *values)
        return result == 'UPDATE 1'

    async def get_unviewed_matches(
        self, question_id: UUID, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get unviewed matches for a question."""
        query = """
            SELECT
                rqm.*,
                pm.title, pm.authors, pm.abstract, pm.publication_date,
                pm.journal, pm.url, pm.pdf_url
            FROM research_question_matches rqm
            JOIN paper_metadata pm ON pm.id = rqm.paper_id
            WHERE rqm.question_id = $1
              AND rqm.is_viewed = false
            ORDER BY rqm.relevance_score DESC, rqm.matched_at DESC
            LIMIT $2
        """

        results = await self.postgres.fetch(query, question_id, limit)
        return [dict(row) for row in results]

    async def get_bookmarked_matches(
        self, question_id: UUID | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get bookmarked matches, optionally filtered by question."""
        if question_id:
            query = """
                SELECT
                    rqm.*,
                    pm.title, pm.authors, pm.abstract, pm.publication_date,
                    pm.journal, pm.url, pm.pdf_url
                FROM research_question_matches rqm
                JOIN paper_metadata pm ON pm.id = rqm.paper_id
                WHERE rqm.question_id = $1
                  AND rqm.is_bookmarked = true
                ORDER BY rqm.updated_at DESC
                LIMIT $2
            """
            results = await self.postgres.fetch(query, question_id, limit)
        else:
            query = """
                SELECT
                    rqm.*,
                    pm.title, pm.authors, pm.abstract, pm.publication_date,
                    pm.journal, pm.url, pm.pdf_url,
                    rq.title as question_title
                FROM research_question_matches rqm
                JOIN paper_metadata pm ON pm.id = rqm.paper_id
                JOIN research_questions rq ON rq.id = rqm.question_id
                WHERE rqm.is_bookmarked = true
                ORDER BY rqm.updated_at DESC
                LIMIT $1
            """
            results = await self.postgres.fetch(query, limit)

        return [dict(row) for row in results]

    async def get_statistics_for_question(self, question_id: UUID) -> dict[str, Any]:
        """Get statistics for matches to a research question."""
        query = """
            SELECT
                COUNT(*) as total_matches,
                COUNT(*) FILTER (WHERE is_viewed) as viewed_matches,
                COUNT(*) FILTER (WHERE is_bookmarked) as bookmarked_matches,
                COUNT(*) FILTER (WHERE user_sentiment = 'like') as liked_matches,
                COUNT(*) FILTER (WHERE user_sentiment = 'dislike') as disliked_matches,
                ROUND(AVG(relevance_score)::numeric, 3) as avg_relevance,
                MAX(relevance_score) as max_relevance,
                MAX(matched_at) as latest_match
            FROM research_question_matches
            WHERE question_id = $1
        """

        row = await self.postgres.fetchrow(query, question_id)
        return dict(row) if row else {}

    async def delete_match(self, match_id: UUID) -> bool:
        """Delete a specific match."""
        query = 'DELETE FROM research_question_matches WHERE id = $1'
        result = await self.postgres.execute(query, match_id)
        return result == 'DELETE 1'

    async def delete_matches_for_question(self, question_id: UUID) -> int:
        """Delete all matches for a research question."""
        query = 'DELETE FROM research_question_matches WHERE question_id = $1'
        result = await self.postgres.execute(query, question_id)
        # Parse "DELETE N" response
        count = int(result.split()[-1]) if result.startswith('DELETE') else 0
        return count

    async def get_paper_by_doi(self, doi: str) -> UUID | None:
        """Get paper_id by DOI from paper_metadata."""
        query = 'SELECT id FROM paper_metadata WHERE doi = $1'
        return await self.postgres.fetchval(query, doi)

    async def get_paper_by_arxiv_id(self, arxiv_id: str) -> UUID | None:
        """Get paper_id by arXiv ID from paper_metadata."""
        query = 'SELECT id FROM paper_metadata WHERE arxiv_id = $1'
        return await self.postgres.fetchval(query, arxiv_id)

    def _normalize_title_python(self, title: str) -> str:
        """
        Normalize title using Python (fallback).

        Args:
            title: Original title

        Returns:
            str: Normalized title
        """
        import re

        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()

    # Legacy method names for backward compatibility during transition
    async def get_or_create_article(self, *args, **kwargs):
        """DEPRECATED: Use find_or_create_paper() instead."""
        logger.warning(
            'get_or_create_article() is deprecated, use find_or_create_paper()'
        )
        return await self.find_or_create_paper(*args, **kwargs)

"""
Article Research Match repository for managing article-to-question relevance mappings.

This module provides methods for creating, querying, and managing matches between
discovered articles and research questions with relevance scoring.
"""

from datetime import datetime
from typing import Any, List, Optional  # noqa: UP035
from uuid import UUID

from loguru import logger

from thoth.repositories.base import BaseRepository


class ArticleResearchMatchRepository(BaseRepository[dict[str, Any]]):
    """Repository for managing article-research question matches with relevance."""

    def __init__(self, postgres_service, **kwargs):
        """
        Initialize article research match repository.

        NOTE: After migration, uses research_question_matches table.
        Kept for backward compatibility during transition.
        """
        super().__init__(
            postgres_service, table_name='research_question_matches', **kwargs
        )

    async def create_match(
        self,
        article_id: UUID,
        question_id: UUID,
        relevance_score: float,
        matched_keywords: Optional[List[str]] = None,  # noqa: UP006, UP007
        matched_topics: Optional[List[str]] = None,  # noqa: UP006, UP007
        matched_authors: Optional[List[str]] = None,  # noqa: UP006, UP007
        discovered_via_source: Optional[str] = None,  # noqa: UP007
        discovery_run_id: Optional[UUID] = None,  # noqa: UP007
    ) -> Optional[UUID]:  # noqa: UP007
        """
        Create a new article-question match.

        Args:
            article_id: Article UUID
            question_id: Research question UUID
            relevance_score: Calculated relevance (0.0 to 1.0)
            matched_keywords: Keywords that matched
            matched_topics: Topics that matched
            matched_authors: Authors that matched
            discovered_via_source: Source that found the article
            discovery_run_id: ID of the discovery run

        Returns:
            Optional[UUID]: Match ID or None
        """
        try:
            data = {  # noqa: F841
                'article_id': article_id,
                'question_id': question_id,
                'relevance_score': relevance_score,
                'matched_keywords': matched_keywords or [],
                'matched_topics': matched_topics or [],
                'matched_authors': matched_authors or [],
                'discovered_via_source': discovered_via_source,
                'discovery_run_id': discovery_run_id,
            }

            # Use ON CONFLICT to handle duplicates (after migration: paper_id, question_id)
            query = """
                INSERT INTO research_question_matches (
                    paper_id, question_id, relevance_score,
                    matched_keywords, matched_topics, matched_authors,
                    discovered_via_source
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (paper_id, question_id) DO UPDATE SET
                    relevance_score = GREATEST(
                        research_question_matches.relevance_score,
                        EXCLUDED.relevance_score
                    ),
                    matched_keywords = EXCLUDED.matched_keywords,
                    matched_topics = EXCLUDED.matched_topics,
                    matched_authors = EXCLUDED.matched_authors,
                    discovered_via_source = EXCLUDED.discovered_via_source,
                    updated_at = NOW()
                RETURNING id
            """

            match_id = await self.postgres.fetchval(
                query,
                article_id,  # Now paper_id in new schema
                question_id,
                relevance_score,
                matched_keywords or [],
                matched_topics or [],
                matched_authors or [],
                discovered_via_source,
            )

            # Invalidate cache
            self._invalidate_cache()

            return match_id

        except Exception as e:
            logger.error(f'Failed to create article-question match: {e}')
            return None

    async def get_by_article_and_question(
        self,
        article_id: str,
        question_id: str,
    ) -> Optional[dict[str, Any]]:  # noqa: UP007
        """
        Check if a paper is already matched to a research question.

        Args:
            article_id: Paper UUID (kept as article_id for backward compatibility)
            question_id: Research question UUID

        Returns:
            Match record if exists, None otherwise
        """
        try:
            # After migration: use research_question_matches with paper_id
            query = """
                SELECT * FROM research_question_matches
                WHERE paper_id = $1 AND question_id = $2
            """

            result = await self.postgres.fetchrow(query, article_id, question_id)

            if result:
                return dict(result)

            return None

        except Exception as e:
            logger.error(
                f'Failed to check paper-question match {article_id}/{question_id}: {e}'
            )
            return None

    async def get_matches_by_question(
        self,
        question_id: UUID,
        min_relevance: Optional[float] = None,  # noqa: UP007
        is_viewed: Optional[bool] = None,  # noqa: UP007
        is_bookmarked: Optional[bool] = None,  # noqa: UP007
        limit: Optional[int] = None,  # noqa: UP007
        offset: Optional[int] = None,  # noqa: UP007
    ) -> List[dict[str, Any]]:  # noqa: UP006
        """
        Get all article matches for a research question.

        Args:
            question_id: Research question UUID
            min_relevance: Minimum relevance score filter
            is_viewed: Filter by viewed status
            is_bookmarked: Filter by bookmarked status
            limit: Maximum number of results
            offset: Number of records to skip

        Returns:
            List[dict[str, Any]]: List of matches with article data
        """
        cache_key = self._cache_key(
            'question',
            question_id,
            min_relevance,
            is_viewed,
            is_bookmarked,
            limit,
            offset,
        )
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            # After migration: use research_question_matches + paper_metadata
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
                    rqm.sentiment_recorded_at,
                    rqm.matched_at,
                    pm.doi,
                    pm.title,
                    pm.authors,
                    pm.abstract,
                    pm.publication_date,
                    pm.journal,
                    pm.url,
                    pm.pdf_url
                FROM research_question_matches rqm
                JOIN paper_metadata pm ON rqm.paper_id = pm.id
                WHERE rqm.question_id = $1
            """
            params = [question_id]

            if min_relevance is not None:
                query += f' AND rqm.relevance_score >= ${len(params) + 1}'
                params.append(min_relevance)

            if is_viewed is not None:
                query += f' AND rqm.is_viewed = ${len(params) + 1}'
                params.append(is_viewed)

            if is_bookmarked is not None:
                query += f' AND rqm.is_bookmarked = ${len(params) + 1}'
                params.append(is_bookmarked)

            query += ' ORDER BY rqm.relevance_score DESC, rqm.matched_at DESC'

            if limit is not None:
                query += f' LIMIT ${len(params) + 1}'
                params.append(limit)

            if offset is not None:
                query += f' OFFSET ${len(params) + 1}'
                params.append(offset)

            results = await self.postgres.fetch(query, *params)
            data = []
            for row in results:
                row_dict = dict(row)
                # Authors is already JSONB from paper_metadata, no parsing needed
                # But keep backward compatibility check
                if isinstance(row_dict.get('authors'), str):
                    import json
                    try:
                        row_dict['authors'] = json.loads(row_dict['authors'])
                    except (json.JSONDecodeError, TypeError):
                        row_dict['authors'] = []
                data.append(row_dict)

            self._set_in_cache(cache_key, data)
            return data

        except Exception as e:
            logger.error(f'Failed to get matches for question {question_id}: {e}')
            return []

    async def get_matches_by_article(self, article_id: UUID) -> List[dict[str, Any]]:  # noqa: UP006
        """
        Get all question matches for an article.

        Args:
            article_id: Article UUID

        Returns:
            List[dict[str, Any]]: List of matches with question data
        """
        cache_key = self._cache_key('article', article_id)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT
                    rqm.*,
                    rq.name as question_name,
                    rq.user_id,
                    rq.keywords,
                    rq.topics
                FROM research_question_matches rqm
                JOIN research_questions rq ON rqm.question_id = rq.id
                WHERE rqm.paper_id = $1
                ORDER BY rqm.relevance_score DESC
            """

            results = await self.postgres.fetch(query, article_id)
            data = [dict(row) for row in results]

            self._set_in_cache(cache_key, data)
            return data

        except Exception as e:
            logger.error(f'Failed to get matches for article {article_id}: {e}')
            return []

    async def get_high_relevance_matches(
        self,
        min_score: float = 0.7,
        is_viewed: bool = False,
        limit: int = 50,
    ) -> List[dict[str, Any]]:  # noqa: UP006
        """
        Get high-relevance unviewed matches across all questions.

        Args:
            min_score: Minimum relevance score
            is_viewed: Filter by viewed status
            limit: Maximum number of results

        Returns:
            List[dict[str, Any]]: List of high-relevance matches
        """
        try:
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
                    rqm.sentiment_recorded_at,
                    rqm.matched_at,
                    pm.doi,
                    pm.title,
                    pm.authors,
                    pm.abstract,
                    pm.publication_date,
                    pm.journal,
                    pm.url,
                    pm.pdf_url,
                    rq.name as question_name,
                    rq.user_id
                FROM research_question_matches rqm
                JOIN paper_metadata pm ON rqm.paper_id = pm.id
                JOIN research_questions rq ON rqm.question_id = rq.id
                WHERE rqm.relevance_score >= $1
                AND rqm.is_viewed = $2
                ORDER BY rqm.relevance_score DESC, rqm.matched_at DESC
                LIMIT $3
            """

            results = await self.postgres.fetch(query, min_score, is_viewed, limit)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get high relevance matches: {e}')
            return []

    async def mark_as_viewed(
        self,
        match_id: UUID,
        viewed_at: Optional[datetime] = None,  # noqa: UP007
    ) -> bool:
        """
        Mark a match as viewed by the user.

        Args:
            match_id: Match UUID
            viewed_at: Timestamp (default: now)

        Returns:
            bool: True if successful
        """
        try:
            data = {
                'is_viewed': True,
                'viewed_at': viewed_at or datetime.now(),
            }

            return await self.update(match_id, data)

        except Exception as e:
            logger.error(f'Failed to mark match {match_id} as viewed: {e}')
            return False

    async def set_bookmark(self, match_id: UUID, is_bookmarked: bool) -> bool:
        """
        Set bookmark status for a match.

        Args:
            match_id: Match UUID
            is_bookmarked: Bookmark status

        Returns:
            bool: True if successful
        """
        try:
            return await self.update(match_id, {'is_bookmarked': is_bookmarked})

        except Exception as e:
            logger.error(f'Failed to set bookmark for match {match_id}: {e}')
            return False

    async def set_user_rating(
        self,
        match_id: UUID,
        rating: int,
        notes: Optional[str] = None,  # noqa: UP007
    ) -> bool:
        """
        Set user rating and notes for a match.

        Args:
            match_id: Match UUID
            rating: Rating (1-5)
            notes: Optional user notes

        Returns:
            bool: True if successful
        """
        try:
            if rating < 1 or rating > 5:
                logger.warning(f'Invalid rating {rating}, must be 1-5')
                return False

            data = {'user_rating': rating}
            if notes is not None:
                data['user_notes'] = notes

            return await self.update(match_id, data)

        except Exception as e:
            logger.error(f'Failed to set rating for match {match_id}: {e}')
            return False

    async def set_user_sentiment(self, match_id: UUID, sentiment: str) -> bool:
        """
        Set user sentiment for a match.

        Args:
            match_id: Match UUID
            sentiment: Sentiment value ('like', 'dislike', 'skip')

        Returns:
            bool: True if successful
        """
        try:
            # Validate sentiment
            valid_sentiments = {'like', 'dislike', 'skip'}
            if sentiment not in valid_sentiments:
                logger.warning(
                    f'Invalid sentiment "{sentiment}", must be one of: {valid_sentiments}'
                )
                return False

            data = {
                'user_sentiment': sentiment,
                'sentiment_recorded_at': datetime.now(),
            }

            success = await self.update(match_id, data)

            if success:
                # Clear cache after update
                self._invalidate_cache()

            return success

        except Exception as e:
            logger.error(f'Failed to set sentiment for match {match_id}: {e}')
            return False

    async def get_sentiment_summary(self, question_id: UUID) -> dict[str, int]:
        """
        Get sentiment summary counts for a research question.

        Args:
            question_id: Research question UUID

        Returns:
            dict[str, int]: Counts for liked, disliked, skipped, and pending
        """
        try:
            query = """
                SELECT
                    COUNT(*) FILTER (WHERE user_sentiment = 'like') as liked,
                    COUNT(*) FILTER (WHERE user_sentiment = 'dislike') as disliked,
                    COUNT(*) FILTER (WHERE user_sentiment = 'skip') as skipped,
                    COUNT(*) FILTER (WHERE user_sentiment IS NULL) as pending
                FROM research_question_matches
                WHERE question_id = $1
            """

            result = await self.postgres.fetchrow(query, question_id)
            return (
                dict(result)
                if result
                else {
                    'liked': 0,
                    'disliked': 0,
                    'skipped': 0,
                    'pending': 0,
                }
            )

        except Exception as e:
            logger.error(
                f'Failed to get sentiment summary for question {question_id}: {e}'
            )
            return {'liked': 0, 'disliked': 0, 'skipped': 0, 'pending': 0}

    async def get_statistics_by_question(self, question_id: UUID) -> dict[str, Any]:
        """
        Get match statistics for a research question.

        Args:
            question_id: Research question UUID

        Returns:
            dict[str, Any]: Statistics including counts, averages, etc.
        """
        try:
            query = """
                SELECT
                    COUNT(*) as total_matches,
                    COUNT(*) FILTER (WHERE relevance_score >= 0.7) as high_relevance,
                    COUNT(*) FILTER (WHERE relevance_score >= 0.5) as medium_relevance,
                    COUNT(*) FILTER (WHERE is_viewed = true) as viewed,
                    COUNT(*) FILTER (WHERE is_bookmarked = true) as bookmarked,
                    AVG(relevance_score) as avg_relevance,
                    MAX(relevance_score) as max_relevance,
                    COUNT(DISTINCT discovered_via_source) as source_count
                FROM research_question_matches
                WHERE question_id = $1
            """

            result = await self.postgres.fetchrow(query, question_id)
            return dict(result) if result else {}

        except Exception as e:
            logger.error(f'Failed to get statistics for question {question_id}: {e}')
            return {}

    async def get_matches_by_source(
        self, question_id: UUID, source_name: str, limit: int = 50
    ) -> List[dict[str, Any]]:  # noqa: UP006
        """
        Get matches discovered by a specific source.

        Args:
            question_id: Research question UUID
            source_name: Source name (e.g., 'arxiv', 'pubmed')
            limit: Maximum number of results

        Returns:
            List[dict[str, Any]]: List of matches from that source
        """
        try:
            query = """
                SELECT
                    rqm.*,
                    pm.doi, pm.title, pm.authors
                FROM research_question_matches rqm
                JOIN paper_metadata pm ON rqm.paper_id = pm.id
                WHERE rqm.question_id = $1
                AND rqm.discovered_via_source = $2
                ORDER BY rqm.relevance_score DESC, rqm.matched_at DESC
                LIMIT $3
            """

            results = await self.postgres.fetch(query, question_id, source_name, limit)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get matches by source {source_name}: {e}')
            return []

    async def delete_matches_for_question(self, question_id: UUID) -> int:
        """
        Delete all matches for a research question.

        Args:
            question_id: Research question UUID

        Returns:
            int: Number of matches deleted
        """
        try:
            query = """
                DELETE FROM research_question_matches
                WHERE question_id = $1
            """

            result = await self.postgres.execute(query, question_id)

            # Invalidate cache
            self._invalidate_cache(str(question_id))

            # Extract count from result (e.g., "DELETE 10")
            count = int(result.split()[-1]) if result else 0
            logger.info(f'Deleted {count} matches for question {question_id}')

            return count

        except Exception as e:
            logger.error(f'Failed to delete matches for question {question_id}: {e}')
            return 0

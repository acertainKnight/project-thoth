"""
Research Question repository for managing user-defined research questions.

This module provides methods for CRUD operations, scheduling management,
and querying research questions with source selections.
"""

from datetime import datetime, time
from typing import Any, List, Optional  # noqa: UP035
from uuid import UUID

from loguru import logger

from thoth.repositories.base import BaseRepository


class ResearchQuestionRepository(BaseRepository[dict[str, Any]]):
    """Repository for managing research question records."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize research question repository."""
        super().__init__(postgres_service, table_name='research_questions', **kwargs)

    async def get_by_user(
        self,
        user_id: str,
        is_active: Optional[bool] = None,  # noqa: UP007
        limit: Optional[int] = None,  # noqa: UP007
        offset: Optional[int] = None,  # noqa: UP007
    ) -> List[dict[str, Any]]:  # noqa: UP006
        """
        Get research questions for a specific user.

        Args:
            user_id: User identifier
            is_active: Filter by active status (None = all)
            limit: Maximum number of results
            offset: Number of records to skip

        Returns:
            List[dict[str, Any]]: List of research questions
        """
        cache_key = self._cache_key('user', user_id, is_active, limit, offset)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = 'SELECT * FROM research_questions WHERE user_id = $1'
            params = [user_id]

            if is_active is not None:
                query += f' AND is_active = ${len(params) + 1}'
                params.append(is_active)

            query += ' ORDER BY created_at DESC'

            if limit is not None:
                query += f' LIMIT ${len(params) + 1}'
                params.append(limit)

            if offset is not None:
                query += f' OFFSET ${len(params) + 1}'
                params.append(offset)

            results = await self.postgres.fetch(query, *params)
            data = [dict(row) for row in results]

            self._set_in_cache(cache_key, data)
            return data

        except Exception as e:
            logger.error(f'Failed to get research questions for user {user_id}: {e}')
            return []

    async def get_active_questions(
        self,
        limit: Optional[int] = None,  # noqa: UP007
    ) -> List[dict[str, Any]]:  # noqa: UP006
        """
        Get all active research questions across all users.

        Args:
            limit: Maximum number of results

        Returns:
            List[dict[str, Any]]: List of active research questions
        """
        cache_key = self._cache_key('active', limit)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT * FROM research_questions
                WHERE is_active = true
                ORDER BY next_run_at ASC NULLS LAST, created_at DESC
            """
            params = []

            if limit is not None:
                query += f' LIMIT ${len(params) + 1}'
                params.append(limit)

            results = await self.postgres.fetch(query, *params)
            data = [dict(row) for row in results]

            self._set_in_cache(cache_key, data)
            return data

        except Exception as e:
            logger.error(f'Failed to get active research questions: {e}')
            return []

    async def get_questions_due_for_run(
        self,
        as_of: Optional[datetime] = None,  # noqa: UP007
    ) -> List[dict[str, Any]]:  # noqa: UP006
        """
        Get research questions that are due for discovery runs.

        Args:
            as_of: Timestamp to check against (default: now)

        Returns:
            List[dict[str, Any]]: List of questions due for runs
        """
        if as_of is None:
            as_of = datetime.now()

        # Remove timezone to match database column (TIMESTAMP WITHOUT TIME ZONE)
        if as_of.tzinfo is not None:
            as_of = as_of.replace(tzinfo=None)

        try:
            query = """
                SELECT * FROM research_questions
                WHERE is_active = true
                AND (next_run_at IS NULL OR next_run_at <= $1)
                ORDER BY next_run_at ASC NULLS FIRST
            """

            results = await self.postgres.fetch(query, as_of)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get questions due for run: {e}')
            return []

    async def update_last_run(
        self,
        question_id: UUID,
        next_run_at: Optional[datetime] = None,  # noqa: UP007
    ) -> bool:
        """
        Update last run timestamp and optionally set next run.

        Args:
            question_id: Research question UUID
            next_run_at: Optional next scheduled run time

        Returns:
            bool: True if successful
        """
        try:
            data = {
                'last_run_at': datetime.now(),
            }

            if next_run_at is not None:
                data['next_run_at'] = next_run_at

            return await self.update(question_id, data)

        except Exception as e:
            logger.error(f'Failed to update last run for question {question_id}: {e}')
            return False

    async def get_by_name(self, user_id: str, name: str) -> Optional[dict[str, Any]]:  # noqa: UP007
        """
        Get research question by user and name.

        Args:
            user_id: User identifier
            name: Research question name

        Returns:
            Optional[dict[str, Any]]: Research question data or None
        """
        cache_key = self._cache_key('user_name', user_id, name)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT * FROM research_questions
                WHERE user_id = $1 AND name = $2
            """

            result = await self.postgres.fetchrow(query, user_id, name)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(
                f'Failed to get research question by name {name} for user {user_id}: {e}'
            )
            return None

    async def create_question(
        self,
        user_id: str,
        name: str,
        keywords: List[str],  # noqa: UP006
        topics: List[str],  # noqa: UP006
        authors: List[str],  # noqa: UP006
        selected_sources: List[str],  # noqa: UP006
        description: Optional[str] = None,  # noqa: UP007
        schedule_frequency: str = 'daily',
        schedule_time: time = time(2, 0, 0),
        min_relevance_score: float = 0.5,
        auto_download_enabled: bool = False,
        auto_download_min_score: float = 0.7,
    ) -> Optional[UUID]:  # noqa: UP007
        """
        Create a new research question.

        Args:
            user_id: User identifier
            name: Question name
            keywords: List of keywords to search for
            topics: List of topics
            authors: List of authors to match
            selected_sources: List of source names or ['*'] for ALL
            description: Optional description
            schedule_frequency: Frequency (daily, weekly, monthly)
            schedule_time: Time of day to run (default: 2 AM)
            min_relevance_score: Minimum relevance threshold
            auto_download_enabled: Enable auto-download
            auto_download_min_score: Min score for auto-download

        Returns:
            Optional[UUID]: Created question ID or None
        """
        try:
            # Check if question name already exists for user
            existing = await self.get_by_name(user_id, name)
            if existing:
                logger.warning(
                    f'Research question "{name}" already exists for user {user_id}'
                )
                return None

            data = {
                'user_id': user_id,
                'name': name,
                'description': description,
                'keywords': keywords,
                'topics': topics,
                'authors': authors,
                'selected_sources': selected_sources,
                'schedule_frequency': schedule_frequency,
                'schedule_time': schedule_time,
                'min_relevance_score': min_relevance_score,
                'auto_download_enabled': auto_download_enabled,
                'auto_download_min_score': auto_download_min_score,
                'is_active': True,
            }

            question_id = await self.create(data)

            if question_id:
                logger.info(f'Created research question: {name} ({question_id})')

            return question_id

        except Exception as e:
            logger.error(f'Failed to create research question: {e}')
            return None

    async def update_question(
        self,
        question_id: UUID,
        name: Optional[str] = None,  # noqa: UP007
        description: Optional[str] = None,  # noqa: UP007
        keywords: Optional[List[str]] = None,  # noqa: UP006, UP007
        topics: Optional[List[str]] = None,  # noqa: UP006, UP007
        authors: Optional[List[str]] = None,  # noqa: UP006, UP007
        selected_sources: Optional[List[str]] = None,  # noqa: UP006, UP007
        schedule_frequency: Optional[str] = None,  # noqa: UP007
        min_relevance_score: Optional[float] = None,  # noqa: UP007
        is_active: Optional[bool] = None,  # noqa: UP007
        last_run_at: Optional[datetime] = None,  # noqa: UP007
        next_run_at: Optional[datetime] = None,  # noqa: UP007
    ) -> bool:
        """
        Update research question fields.

        Args:
            question_id: Question UUID
            name: New name
            description: New description
            keywords: New keywords list
            topics: New topics list
            authors: New authors list
            selected_sources: New sources list
            schedule_frequency: New frequency
            min_relevance_score: New relevance threshold
            is_active: New active status
            last_run_at: Last discovery run timestamp
            next_run_at: Next scheduled run timestamp

        Returns:
            bool: True if successful
        """
        try:
            data = {}

            if name is not None:
                data['name'] = name
            if description is not None:
                data['description'] = description
            if keywords is not None:
                data['keywords'] = keywords
            if topics is not None:
                data['topics'] = topics
            if authors is not None:
                data['authors'] = authors
            if selected_sources is not None:
                data['selected_sources'] = selected_sources
            if schedule_frequency is not None:
                data['schedule_frequency'] = schedule_frequency
            if min_relevance_score is not None:
                data['min_relevance_score'] = min_relevance_score
            if is_active is not None:
                data['is_active'] = is_active
            if last_run_at is not None:
                data['last_run_at'] = last_run_at
            if next_run_at is not None:
                data['next_run_at'] = next_run_at

            if not data:
                return True

            return await self.update(question_id, data)

        except Exception as e:
            logger.error(f'Failed to update research question {question_id}: {e}')
            return False

    async def get_statistics(
        self,
        question_id: Optional[UUID] = None,  # noqa: UP007
    ) -> dict[str, Any]:
        """
        Get statistics for research questions.

        Args:
            question_id: Optional specific question ID

        Returns:
            dict[str, Any]: Statistics including match counts, run history, etc.
        """
        try:
            if question_id:
                query = """
                    SELECT
                        rq.*,
                        COUNT(DISTINCT rqm.paper_id) as total_matches,
                        COUNT(DISTINCT rqm.paper_id) FILTER (
                            WHERE rqm.relevance_score > 0.7
                        ) as high_relevance_matches,
                        COUNT(DISTINCT rqm.paper_id) FILTER (
                            WHERE rqm.is_viewed = false
                        ) as unviewed_matches,
                        MAX(rqm.matched_at) as last_match_at,
                        COUNT(DISTINCT del.id) as total_runs,
                        COUNT(DISTINCT del.id) FILTER (
                            WHERE del.status = 'completed'
                        ) as successful_runs
                    FROM research_questions rq
                    LEFT JOIN research_question_matches rqm ON rq.id = rqm.question_id
                    LEFT JOIN discovery_execution_log del ON rq.id = del.question_id
                    WHERE rq.id = $1
                    GROUP BY rq.id
                """
                result = await self.postgres.fetchrow(query, question_id)
                return dict(result) if result else {}
            else:
                query = """
                    SELECT
                        COUNT(*) as total_questions,
                        COUNT(*) FILTER (WHERE is_active = true) as active_questions,
                        COUNT(DISTINCT rqm.paper_id) as total_matches,
                        AVG(rqm.relevance_score) as avg_relevance_score
                    FROM research_questions rq
                    LEFT JOIN research_question_matches rqm ON rq.id = rqm.question_id
                """
                result = await self.postgres.fetchrow(query)
                return dict(result) if result else {}

        except Exception as e:
            logger.error(f'Failed to get research question statistics: {e}')
            return {}

    async def deactivate(self, question_id: UUID) -> bool:
        """
        Deactivate a research question (soft delete).

        Args:
            question_id: Question UUID

        Returns:
            bool: True if successful
        """
        return await self.update_question(question_id, is_active=False)

    async def activate(self, question_id: UUID) -> bool:
        """
        Activate a research question.

        Args:
            question_id: Question UUID

        Returns:
            bool: True if successful
        """
        return await self.update_question(question_id, is_active=True)

"""Research Question Service for managing user-defined research interests.

This service provides business logic for creating, updating, and managing
research questions that drive the discovery system.
"""

from datetime import datetime, time, timedelta
from typing import Any
from uuid import UUID

from thoth.config import Config
from thoth.repositories.research_question_repository import ResearchQuestionRepository
from thoth.services.base import BaseService


class ResearchQuestionService(BaseService):
    """
    Service for managing research questions and their lifecycle.

    This service wraps the ResearchQuestionRepository and provides:
    - Business logic for research question validation
    - Scheduling calculations
    - Access control and user isolation
    - Integration with discovery orchestration
    """

    def __init__(self, config: Config, postgres_service=None):
        """
        Initialize the Research Question Service.

        Args:
            config: Application configuration
            postgres_service: PostgreSQL service for database operations
        """
        super().__init__(config)
        self.postgres_service = postgres_service
        self.repository = ResearchQuestionRepository(postgres_service or config)
        self.logger.info('ResearchQuestionService initialized')

    async def create_research_question(
        self,
        user_id: str,
        name: str,
        keywords: list[str],
        topics: list[str],
        authors: list[str],
        selected_sources: list[str],
        description: str | None = None,
        schedule_frequency: str = 'daily',
        schedule_time: str | None = None,
        schedule_days_of_week: list[int] | None = None,
        min_relevance_score: float = 0.5,
        auto_download_enabled: bool = False,
        auto_download_min_score: float = 0.7,
        max_articles_per_run: int = 50,  # noqa: ARG002
        publication_date_range: dict[str, str] | None = None,
    ) -> UUID | None:
        """
        Create a new research question with validation.

        Args:
            user_id: User identifier
            name: Descriptive name for the research question
            keywords: Keywords to match
            topics: Research topics
            authors: Preferred authors
            selected_sources: Source selection (['arxiv', 'pubmed'] or ['*'])
            description: Optional detailed description of the research question
            schedule_frequency: 'daily', 'weekly', or 'monthly'
            schedule_time: Preferred run time (HH:MM format)
            schedule_days_of_week: Days for weekly schedule (ISO 8601: 1=Mon, 7=Sun)
            min_relevance_score: Minimum relevance threshold (0.0-1.0)
            auto_download_enabled: Automatically download matching PDFs
            auto_download_min_score: Minimum score threshold for auto-download
            max_articles_per_run: Maximum articles per discovery run
            publication_date_range: Date range for filtering publications

        Returns:
            UUID of created question, or None if creation failed

        Raises:
            ValueError: If validation fails
        """
        # Validate inputs
        self._validate_research_question_inputs(
            name=name,
            keywords=keywords,
            topics=topics,
            selected_sources=selected_sources,
            schedule_frequency=schedule_frequency,
            min_relevance_score=min_relevance_score,
        )

        # Check for duplicate names (unique per user)
        existing = await self.repository.get_by_name(user_id=user_id, name=name)
        if existing:
            raise ValueError(
                f"Research question '{name}' already exists for user {user_id}"
            )

        # Calculate next run time
        next_run_at = self._calculate_next_run(  # noqa: F841
            frequency=schedule_frequency,
            schedule_time=schedule_time,
            schedule_days_of_week=schedule_days_of_week,
        )

        # Convert schedule_time string (HH:MM) to time object
        time_obj = None
        if schedule_time:
            if isinstance(schedule_time, str):
                hour, minute = map(int, schedule_time.split(':'))
                time_obj = time(hour, minute)
            else:
                time_obj = schedule_time
        else:
            time_obj = time(3, 0, 0)  # Default to 3am

        question_id = await self.repository.create_question(
            user_id=user_id,
            name=name,
            description=description,
            keywords=keywords,
            topics=topics,
            authors=authors,
            selected_sources=selected_sources,
            schedule_frequency=schedule_frequency,
            schedule_time=time_obj,
            min_relevance_score=min_relevance_score,
            auto_download_enabled=auto_download_enabled,
            auto_download_min_score=auto_download_min_score,
            publication_date_range=publication_date_range,
        )

        if question_id:
            self.logger.info(
                f"Created research question '{name}' for user {user_id}: {question_id}"
            )
        else:
            self.logger.error(
                f"Failed to create research question '{name}' for user {user_id}"
            )

        return question_id

    async def update_research_question(
        self,
        question_id: UUID,
        user_id: str,
        **updates: Any,
    ) -> bool:
        """
        Update a research question with validation and user isolation.

        Args:
            question_id: Question UUID
            user_id: User identifier (for access control)
            **updates: Fields to update

        Returns:
            True if update succeeded, False otherwise

        Raises:
            PermissionError: If user doesn't own the question
            ValueError: If validation fails
        """
        # Verify ownership
        question = await self.repository.get_by_id(question_id)
        if not question:
            raise ValueError(f'Research question {question_id} not found')

        if question['user_id'] != user_id:
            raise PermissionError(
                f'User {user_id} does not have permission to update question {question_id}'
            )

        # Validate if critical fields are being updated
        if 'selected_sources' in updates:
            self._validate_source_selection(updates['selected_sources'])

        if 'min_relevance_score' in updates:
            self._validate_relevance_score(updates['min_relevance_score'])

        if 'schedule_frequency' in updates:
            self._validate_schedule_frequency(updates['schedule_frequency'])

        # Recalculate next_run_at if schedule changed
        if any(
            k in updates
            for k in ['schedule_frequency', 'schedule_time', 'schedule_days_of_week']
        ):
            updates['next_run_at'] = self._calculate_next_run(
                frequency=updates.get(
                    'schedule_frequency', question['schedule_frequency']
                ),
                schedule_time=updates.get(
                    'schedule_time', question.get('schedule_time')
                ),
                schedule_days_of_week=updates.get(
                    'schedule_days_of_week', question.get('schedule_days_of_week')
                ),
            )

        # Perform update
        success = await self.repository.update_question(question_id, **updates)

        if success:
            self.logger.info(
                f'Updated research question {question_id}: {list(updates.keys())}'
            )
        else:
            self.logger.error(f'Failed to update research question {question_id}')

        return success

    async def delete_research_question(
        self,
        question_id: UUID,
        user_id: str,
        hard_delete: bool = False,
    ) -> bool:
        """
        Delete or deactivate a research question.

        Args:
            question_id: Question UUID
            user_id: User identifier (for access control)
            hard_delete: If True, permanently delete; if False, soft delete

        Returns:
            True if deletion succeeded, False otherwise

        Raises:
            PermissionError: If user doesn't own the question
        """
        # Verify ownership
        question = await self.repository.get_by_id(question_id)
        if not question:
            self.logger.warning(
                f'Research question {question_id} not found for deletion'
            )
            return False

        if question['user_id'] != user_id:
            raise PermissionError(
                f'User {user_id} does not have permission to delete question {question_id}'
            )

        # Perform deletion
        if hard_delete:
            success = await self.repository.delete_question(question_id)
            action = 'deleted'
        else:
            success = await self.repository.deactivate_question(question_id)
            action = 'deactivated'

        if success:
            self.logger.info(f'{action.capitalize()} research question {question_id}')
        else:
            self.logger.error(f'Failed to {action} research question {question_id}')

        return success

    async def get_user_questions(
        self,
        user_id: str,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get all research questions for a user.

        Args:
            user_id: User identifier
            active_only: If True, only return active questions

        Returns:
            List of research question records
        """
        questions = await self.repository.get_by_user(
            user_id=user_id,
            is_active=active_only if active_only else None,
        )

        self.logger.debug(
            f'Retrieved {len(questions)} research questions for user {user_id} '
            f'(active_only={active_only})'
        )

        return questions

    async def get_questions_due_for_discovery(
        self,
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all research questions that are due for discovery runs.

        This is used by the scheduler to determine which questions need processing.

        Args:
            as_of: Check as of this datetime (defaults to now)

        Returns:
            List of research questions due for discovery
        """
        questions = await self.repository.get_questions_due_for_run(as_of=as_of)

        self.logger.info(
            f'Found {len(questions)} research questions due for discovery '
            f'(as_of={as_of or "now"})'
        )

        return questions

    async def mark_discovery_completed(
        self,
        question_id: UUID,
        articles_found: int,
        articles_matched: int,
        execution_time: float,
        errors: list[str] | None = None,  # noqa: ARG002
    ) -> bool:
        """
        Mark a discovery run as completed and update statistics.

        Args:
            question_id: Question UUID
            articles_found: Total articles discovered
            articles_matched: Articles that matched relevance criteria
            execution_time: Execution time in seconds
            errors: List of error messages if any

        Returns:
            True if update succeeded, False otherwise
        """
        question = await self.repository.get_by_id(question_id)
        if not question:
            self.logger.error(
                f'Cannot mark completion for non-existent question {question_id}'
            )
            return False

        # Calculate next run time
        next_run_at = self._calculate_next_run(
            frequency=question['schedule_frequency'],
            schedule_time=question.get('schedule_time'),
            schedule_days_of_week=question.get('schedule_days_of_week'),
        )

        # Update statistics and schedule
        success = await self.repository.update_question(
            question_id=question_id,
            last_run_at=datetime.now(),
            next_run_at=next_run_at,
            articles_found_count=question.get('articles_found_count', 0)
            + articles_found,
            articles_matched_count=question.get('articles_matched_count', 0)
            + articles_matched,
        )

        if success:
            self.logger.info(
                f'Marked discovery completed for question {question_id}: '
                f'{articles_found} found, {articles_matched} matched, '
                f'{execution_time:.2f}s, next run: {next_run_at}'
            )
        else:
            self.logger.error(
                f'Failed to mark discovery completed for question {question_id}'
            )

        return success

    async def get_question_statistics(
        self,
        question_id: UUID,
        user_id: str,
    ) -> dict[str, Any] | None:
        """
        Get statistics for a research question.

        Args:
            question_id: Question UUID
            user_id: User identifier (for access control)

        Returns:
            Statistics dictionary, or None if not found

        Raises:
            PermissionError: If user doesn't own the question
        """
        # Verify ownership
        question = await self.repository.get_by_id(question_id)
        if not question:
            return None

        if question['user_id'] != user_id:
            raise PermissionError(
                f'User {user_id} does not have permission to view statistics for question {question_id}'
            )

        stats = await self.repository.get_statistics(question_id)

        self.logger.debug(f'Retrieved statistics for question {question_id}')

        return stats

    # ==================== Validation Methods ====================

    def _validate_research_question_inputs(
        self,
        name: str,
        keywords: list[str],
        topics: list[str],
        selected_sources: list[str],
        schedule_frequency: str,
        min_relevance_score: float,
    ) -> None:
        """Validate research question inputs."""
        if not name or len(name.strip()) == 0:
            raise ValueError('Research question name cannot be empty')

        if len(name) > 255:
            raise ValueError('Research question name must be 255 characters or less')

        if not keywords and not topics:
            raise ValueError('At least one keyword or topic must be provided')

        self._validate_source_selection(selected_sources)
        self._validate_schedule_frequency(schedule_frequency)
        self._validate_relevance_score(min_relevance_score)

    def _validate_source_selection(self, selected_sources: list[str]) -> None:
        """Validate source selection array."""
        if not selected_sources or len(selected_sources) == 0:
            raise ValueError('At least one source must be selected')

        # Check for valid format: either ['*'] or specific source names
        if len(selected_sources) == 1 and selected_sources[0] == '*':
            return  # Valid: ALL sources

        # Validate specific source names (basic validation, actual availability checked at runtime)  # noqa: W505
        valid_source_pattern = r'^[a-z0-9_-]+$'  # noqa: F841
        for source in selected_sources:
            if not source or len(source.strip()) == 0:
                raise ValueError('Source name cannot be empty')
            # Additional validation could check against available_sources table

    def _validate_schedule_frequency(self, frequency: str) -> None:
        """Validate schedule frequency."""
        valid_frequencies = ['daily', 'weekly', 'monthly', 'on-demand']
        if frequency not in valid_frequencies:
            raise ValueError(
                f"Invalid schedule frequency '{frequency}'. "
                f'Must be one of: {", ".join(valid_frequencies)}'
            )

    def _validate_relevance_score(self, score: float) -> None:
        """Validate relevance score threshold."""
        if not 0.0 <= score <= 1.0:
            raise ValueError(
                f'Relevance score must be between 0.0 and 1.0, got {score}'
            )

    # ==================== Scheduling Methods ====================

    def _calculate_next_run(
        self,
        frequency: str,
        schedule_time: str | None = None,
        schedule_days_of_week: list[int] | None = None,
    ) -> datetime:
        """
        Calculate the next scheduled run time.

        Args:
            frequency: 'daily', 'weekly', 'monthly', or 'on-demand'
            schedule_time: Preferred time in HH:MM format
            schedule_days_of_week: ISO 8601 days (1=Monday, 7=Sunday)

        Returns:
            Next run datetime
        """
        now = datetime.now()

        # Parse schedule time or default to current time
        if schedule_time:
            try:
                hour, minute = map(int, schedule_time.split(':'))
                scheduled_time = now.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
            except (ValueError, AttributeError):
                self.logger.warning(
                    f"Invalid schedule_time '{schedule_time}', using current time"
                )
                scheduled_time = now
        else:
            scheduled_time = now

        if frequency == 'daily':
            next_run = scheduled_time
            if next_run <= now:
                next_run += timedelta(days=1)

        elif frequency == 'weekly':
            # Default to current weekday if not specified
            if not schedule_days_of_week:
                next_run = scheduled_time + timedelta(days=7)
            else:
                # Convert ISO 8601 days (1=Mon, 7=Sun) to Python weekdays (0=Mon, 6=Sun)
                target_days = [
                    (day - 1) % 7 for day in schedule_days_of_week if 1 <= day <= 7
                ]

                if not target_days:
                    next_run = scheduled_time + timedelta(days=7)
                else:
                    current_weekday = now.weekday()
                    days_ahead = min(
                        (d - current_weekday) % 7 or 7 for d in target_days
                    )
                    next_run = scheduled_time + timedelta(days=days_ahead)

        elif frequency == 'monthly':
            # Schedule for same day next month
            next_month = now.month + 1
            next_year = now.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            next_run = scheduled_time.replace(year=next_year, month=next_month)

        elif frequency == 'on-demand':
            # Far future date for on-demand (won't be scheduled)
            next_run = datetime(2099, 12, 31)

        else:
            self.logger.warning(f"Unknown frequency '{frequency}', defaulting to daily")
            next_run = scheduled_time + timedelta(days=1)

        self.logger.debug(
            f"Calculated next run for frequency '{frequency}': {next_run} "
            f'(schedule_time={schedule_time}, days={schedule_days_of_week})'
        )

        return next_run

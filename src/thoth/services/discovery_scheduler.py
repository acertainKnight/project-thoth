"""Research Question Discovery Scheduler Service.

This service runs a background scheduler that periodically checks for
research questions due for discovery runs and executes them automatically.

The scheduler:
- Runs every 5 minutes to check for due questions
- Executes discoveries in parallel for multiple questions
- Logs all executions to discovery_execution_log table
- Updates next_run_at after each successful run
- Handles errors gracefully without crashing the loop
"""

import asyncio
import time
from datetime import datetime
from typing import Any
from uuid import UUID

from loguru import logger

from thoth.config import Config
from thoth.repositories.base import BaseRepository
from thoth.services.base import BaseService
from thoth.services.discovery_orchestrator import DiscoveryOrchestrator
from thoth.services.research_question_service import ResearchQuestionService


class DiscoveryExecutionLogRepository(BaseRepository[dict[str, Any]]):
    """Repository for managing discovery execution log records."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize discovery execution log repository."""
        super().__init__(
            postgres_service, table_name='discovery_execution_log', **kwargs
        )

    async def create_execution(
        self,
        question_id: UUID,
        user_id: str | None = None,
        triggered_by: str = 'scheduler',
    ) -> UUID | None:
        """
        Create a new execution log entry with 'running' status.

        Args:
            question_id: Research question UUID
            triggered_by: Source that triggered this execution

        Returns:
            UUID of the created execution log entry, or None if creation failed
        """
        try:
            query = """
                INSERT INTO discovery_execution_log (
                    question_id, user_id, status, started_at, triggered_by
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """
            result = await self.postgres.fetchrow(
                query,
                question_id,
                user_id or 'default_user',
                'running',
                datetime.now(),
                triggered_by,
            )

            if result:
                execution_id = result['id']
                logger.debug(
                    f'Created execution log entry {execution_id} for question {question_id}'
                )
                return execution_id

            return None

        except Exception as e:
            logger.error(f'Failed to create execution log entry: {e}', exc_info=True)
            return None

    async def complete_execution(
        self,
        execution_id: UUID,
        status: str,
        sources_queried: list[str],
        total_articles_found: int,
        new_articles: int,
        duplicate_articles: int,
        relevant_articles: int,
        high_relevance_articles: int,
        error_message: str | None = None,
        error_details: dict[str, Any] | None = None,
    ) -> bool:
        """
        Mark an execution as completed with results.

        Args:
            execution_id: Execution log UUID
            status: Final status ('completed', 'failed', 'cancelled')
            sources_queried: List of source names queried
            total_articles_found: Total articles discovered
            new_articles: New articles added
            duplicate_articles: Duplicate articles found
            relevant_articles: Articles above min_relevance_score
            high_relevance_articles: Articles with score > 0.7
            error_message: Error message if failed
            error_details: Additional error details as JSON

        Returns:
            True if update succeeded, False otherwise
        """
        try:
            # Calculate duration
            query_duration = """
                SELECT started_at FROM discovery_execution_log WHERE id = $1
            """
            result = await self.postgres.fetchrow(query_duration, execution_id)

            if not result:
                logger.error(f'Execution log {execution_id} not found for completion')
                return False

            started_at = result['started_at']
            duration_seconds = (datetime.now() - started_at).total_seconds()

            # Update with final results
            query = """
                UPDATE discovery_execution_log SET
                    status = $2,
                    completed_at = $3,
                    duration_seconds = $4,
                    sources_queried = $5,
                    total_articles_found = $6,
                    new_articles = $7,
                    duplicate_articles = $8,
                    relevant_articles = $9,
                    high_relevance_articles = $10,
                    error_message = $11,
                    error_details = $12
                WHERE id = $1
            """

            await self.postgres.execute(
                query,
                execution_id,
                status,
                datetime.now(),
                duration_seconds,
                sources_queried,
                total_articles_found,
                new_articles,
                duplicate_articles,
                relevant_articles,
                high_relevance_articles,
                error_message,
                error_details,
            )

            logger.debug(
                f"Completed execution log {execution_id} with status '{status}' "
                f'in {duration_seconds:.2f}s'
            )
            return True

        except Exception as e:
            logger.error(
                f'Failed to complete execution log {execution_id}: {e}', exc_info=True
            )
            return False


class ResearchQuestionScheduler(BaseService):
    """
    Background scheduler for research question discovery runs.

    This service manages the automatic execution of scheduled discovery
    runs for research questions. It runs a background loop that checks
    for due questions every 5 minutes and executes their discoveries.

    Architecture:
    - Uses asyncio.create_task() for background execution
    - Gracefully handles errors without crashing the loop
    - Logs all executions to discovery_execution_log table
    - Updates question schedules after each run
    """

    def __init__(
        self,
        config: Config,
        research_question_service: ResearchQuestionService,
        discovery_orchestrator: DiscoveryOrchestrator,
        postgres_service=None,
    ):
        """
        Initialize the Research Question Scheduler.

        Args:
            config: Application configuration
            research_question_service: Service for managing research questions
            discovery_orchestrator: Service for executing discoveries
            postgres_service: PostgreSQL service for database operations
        """
        super().__init__(config)
        self.research_question_service = research_question_service
        self.discovery_orchestrator = discovery_orchestrator
        self.postgres_service = postgres_service

        # Initialize execution log repository
        self.execution_log = DiscoveryExecutionLogRepository(postgres_service or config)

        # Scheduler state
        self._running = False
        self._task: asyncio.Task | None = None
        self._check_interval = 300  # 5 minutes in seconds

        self.logger.info('ResearchQuestionScheduler initialized')

    async def start(self) -> None:
        """
        Start the background scheduler loop.

        Creates a background task that runs the scheduler loop.
        This method returns immediately while the loop continues in the background.
        """
        if self._running:
            self.logger.warning('Scheduler is already running')
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())

        self.logger.info(
            f'Research question scheduler started (check interval: {self._check_interval}s)'
        )

    async def stop(self) -> None:
        """
        Stop the scheduler gracefully.

        Cancels the background task and waits for it to complete.
        """
        if not self._running:
            self.logger.warning('Scheduler is not running')
            return

        self.logger.info('Stopping research question scheduler...')

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                self.logger.debug('Scheduler task cancelled successfully')

        self.logger.info('Research question scheduler stopped')

    async def _scheduler_loop(self) -> None:
        """
        Main scheduler loop that runs in the background.

        Fetches ALL users' due questions in one query so that the
        consolidated pipeline can merge shared sources across users,
        query each source once, deduplicate globally, and then fan
        results to the correct user via the user_id on each question.
        """
        self.logger.info('Scheduler loop started')

        while self._running:
            try:
                loop_start = time.time()

                due_questions = await self._get_all_due_questions()

                if due_questions:
                    self.logger.info(
                        f'Found {len(due_questions)} research questions due for '
                        f'discovery across all users'
                    )
                    await self._run_due_discoveries(due_questions)
                else:
                    self.logger.debug('No research questions due for discovery')

                loop_duration = time.time() - loop_start
                self.logger.debug(f'Scheduler loop completed in {loop_duration:.2f}s')

            except Exception as e:
                self.logger.error(
                    f'Error in scheduler loop (continuing): {e}', exc_info=True
                )

            try:
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                self.logger.info('Scheduler loop cancelled during sleep')
                break

        self.logger.info('Scheduler loop stopped')

    async def _get_all_due_questions(self) -> list[dict[str, Any]]:
        """Fetch all due research questions across every user.

        Queries the database directly without tenant scoping so that the
        consolidated pipeline receives questions from all users in one
        batch.  Each question row already carries its own ``user_id``
        which the orchestrator uses when storing matches and papers.

        Returns:
            List of research question dicts (with user_id) due for runs.
        """
        try:
            query = """
                SELECT * FROM research_questions
                WHERE is_active = true
                  AND (next_run_at IS NULL OR next_run_at <= NOW())
                ORDER BY next_run_at ASC NULLS FIRST
            """
            rows = await self.postgres_service.fetch(query)
            return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f'Failed to fetch all due questions: {e}')
            return []

    async def _run_due_discoveries(self, due_questions: list[dict[str, Any]]) -> None:
        """
        Execute discoveries for all due questions using consolidated pipeline.

        Uses the new consolidated discovery approach that:
        - Merges queries for shared sources
        - Globally deduplicates articles
        - Reduces LLM token usage

        Args:
            due_questions: List of research question records due for discovery
        """
        self.logger.info(
            f'Starting consolidated discovery for {len(due_questions)} questions'
        )

        # Create execution log entries for all questions
        execution_ids = {}
        for question in due_questions:
            execution_id = await self.execution_log.create_execution(
                question_id=question['id'],
                user_id=question.get('user_id'),
                triggered_by='scheduler',
            )
            if execution_id:
                execution_ids[question['id']] = execution_id
            else:
                self.logger.error(
                    f'Failed to create execution log for question {question["id"]}'
                )

        try:
            # Run consolidated discovery
            result = await self.discovery_orchestrator.run_consolidated_discovery(
                questions=due_questions
            )

            if result.get('success'):
                # Process each question's individual result
                question_results = result.get('question_results', {})

                for question in due_questions:
                    question_id = question['id']
                    execution_id = execution_ids.get(question_id)

                    if not execution_id:
                        continue

                    # Get this question's specific results
                    q_result = question_results.get(str(question_id), {})
                    processed = q_result.get('articles_processed', 0)
                    matched = q_result.get('articles_matched', 0)

                    # Update question schedule
                    await self._update_question_schedule(question)

                    # Calculate metrics for logging
                    # In consolidated mode, we don't have per-question "found" counts
                    # Use processed as a proxy for new articles
                    new_articles = processed
                    duplicate_articles = 0  # Already handled globally
                    relevant_articles = matched
                    high_relevance_articles = int(matched * 0.7)  # Estimate

                    # Determine sources this question contributed to
                    # (can't easily reconstruct, use empty list)
                    sources_queried = []

                    # Mark execution as completed
                    await self.execution_log.complete_execution(
                        execution_id=execution_id,
                        status='completed',
                        sources_queried=sources_queried,
                        total_articles_found=processed,
                        new_articles=new_articles,
                        duplicate_articles=duplicate_articles,
                        relevant_articles=relevant_articles,
                        high_relevance_articles=high_relevance_articles,
                    )

                    self.logger.info(
                        f"Discovery completed for '{question['name']}': "
                        f'{processed} processed, {matched} matched'
                    )

                self.logger.info(
                    f'Consolidated discovery completed: {result.get("total_sources_queried", 0)} sources, '
                    f'{result.get("total_unique_articles", 0)} unique articles, '
                    f'{result.get("total_articles_matched", 0)} total matches'
                )

            else:
                # Consolidated discovery failed - mark all as failed
                error_msg = result.get('error', 'Unknown error')
                self.logger.error(f'Consolidated discovery failed: {error_msg}')

                for question in due_questions:
                    execution_id = execution_ids.get(question['id'])
                    if execution_id:
                        await self.execution_log.complete_execution(
                            execution_id=execution_id,
                            status='failed',
                            sources_queried=[],
                            total_articles_found=0,
                            new_articles=0,
                            duplicate_articles=0,
                            relevant_articles=0,
                            high_relevance_articles=0,
                            error_message=error_msg,
                        )

        except Exception as e:
            self.logger.error(
                f'Exception during consolidated discovery: {e}',
                exc_info=True,
            )

            # Mark all executions as failed
            for question in due_questions:
                execution_id = execution_ids.get(question['id'])
                if execution_id:
                    await self.execution_log.complete_execution(
                        execution_id=execution_id,
                        status='failed',
                        sources_queried=[],
                        total_articles_found=0,
                        new_articles=0,
                        duplicate_articles=0,
                        relevant_articles=0,
                        high_relevance_articles=0,
                        error_message=str(e),
                        error_details={'exception_type': type(e).__name__},
                    )

    async def _run_single_discovery(self, question: dict[str, Any]) -> bool:
        """
        Execute discovery for a single research question.

        Creates execution log entry, runs discovery, updates schedule,
        and marks execution as completed.

        Args:
            question: Research question record

        Returns:
            True if discovery succeeded, False otherwise
        """
        question_id = question['id']
        question_name = question['name']

        self.logger.info(
            f"Starting discovery for question '{question_name}' ({question_id})"
        )

        # Create execution log entry
        execution_id = await self.execution_log.create_execution(
            question_id=question_id,
            user_id=question.get('user_id'),
            triggered_by='scheduler',
        )

        if not execution_id:
            self.logger.error(
                f'Failed to create execution log for question {question_id}, skipping'
            )
            return False

        try:
            # Run discovery
            result = await self.discovery_orchestrator.run_discovery_for_question(
                question_id=question_id,
                max_articles=question.get('max_articles_per_run'),
            )

            if result.get('success'):
                # Update question schedule
                await self._update_question_schedule(question)

                # Calculate metrics for logging
                total_found = result.get('articles_found', 0)
                processed = result.get('articles_processed', 0)
                matched = result.get('articles_matched', 0)

                # Estimate new vs duplicate (all processed are either new or duplicate)
                # We consider matched articles as "relevant"
                new_articles = processed
                duplicate_articles = (
                    total_found - processed if total_found > processed else 0
                )
                relevant_articles = matched
                # Estimate high relevance (assume 70% of matched articles are high relevance)  # noqa: W505
                high_relevance_articles = int(matched * 0.7)

                # Mark execution as completed
                await self.execution_log.complete_execution(
                    execution_id=execution_id,
                    status='completed',
                    sources_queried=result.get('sources_queried', []),
                    total_articles_found=total_found,
                    new_articles=new_articles,
                    duplicate_articles=duplicate_articles,
                    relevant_articles=relevant_articles,
                    high_relevance_articles=high_relevance_articles,
                )

                self.logger.info(
                    f"Discovery completed for '{question_name}': "
                    f'{total_found} found, {matched} matched'
                )

                return True

            else:
                # Discovery failed
                error_msg = result.get('error', 'Unknown error')

                # Mark execution as failed
                await self.execution_log.complete_execution(
                    execution_id=execution_id,
                    status='failed',
                    sources_queried=[],
                    total_articles_found=0,
                    new_articles=0,
                    duplicate_articles=0,
                    relevant_articles=0,
                    high_relevance_articles=0,
                    error_message=error_msg,
                )

                self.logger.error(
                    f'Discovery failed for question {question_id}: {error_msg}'
                )

                return False

        except Exception as e:
            self.logger.error(
                f'Exception during discovery for question {question_id}: {e}',
                exc_info=True,
            )

            # Mark execution as failed
            await self.execution_log.complete_execution(
                execution_id=execution_id,
                status='failed',
                sources_queried=[],
                total_articles_found=0,
                new_articles=0,
                duplicate_articles=0,
                relevant_articles=0,
                high_relevance_articles=0,
                error_message=str(e),
                error_details={'exception_type': type(e).__name__},
            )

            return False

    async def _update_question_schedule(self, question: dict[str, Any]) -> None:
        """
        Update the next_run_at timestamp for a research question after execution.

        Uses the ResearchQuestionService to recalculate the next run time
        based on the question's schedule configuration.

        Args:
            question: Research question record
        """
        question_id = question['id']

        try:
            # Use service method to update statistics and schedule
            success = await self.research_question_service.mark_discovery_completed(
                question_id=question_id,
                articles_found=0,  # Already tracked in execution log
                articles_matched=0,  # Already tracked in execution log
                execution_time=0.0,  # Already tracked in execution log
            )

            if success:
                self.logger.debug(f'Updated schedule for question {question_id}')
            else:
                self.logger.warning(
                    f'Failed to update schedule for question {question_id}'
                )

        except Exception as e:
            self.logger.error(
                f'Error updating schedule for question {question_id}: {e}',
                exc_info=True,
            )

    def is_running(self) -> bool:
        """
        Check if the scheduler is currently running.

        Returns:
            True if scheduler is running, False otherwise
        """
        return self._running

    async def trigger_immediate_run(self, question_id: UUID) -> dict[str, Any]:
        """
        Trigger an immediate discovery run for a specific question.

        This bypasses the schedule and runs the discovery immediately.
        Useful for manual triggers or API endpoints.

        Args:
            question_id: Research question UUID

        Returns:
            Discovery result dictionary
        """
        self.logger.info(f'Triggering immediate discovery for question {question_id}')

        # Load question
        question = await self.research_question_service.repository.get_by_id(
            question_id
        )

        if not question:
            self.logger.error(f'Question {question_id} not found')
            return {
                'success': False,
                'error': 'Research question not found',
            }

        # Create execution log entry
        execution_id = await self.execution_log.create_execution(
            question_id=question_id,
            user_id=question.get('user_id'),
            triggered_by='manual',
        )

        if not execution_id:
            self.logger.error(
                f'Failed to create execution log for question {question_id}'
            )
            return {
                'success': False,
                'error': 'Failed to create execution log',
            }

        # Run discovery
        try:
            result = await self.discovery_orchestrator.run_discovery_for_question(
                question_id=question_id,
                max_articles=question.get('max_articles_per_run'),
            )

            # Log execution
            if result.get('success'):
                total_found = result.get('articles_found', 0)
                processed = result.get('articles_processed', 0)
                matched = result.get('articles_matched', 0)

                await self.execution_log.complete_execution(
                    execution_id=execution_id,
                    status='completed',
                    sources_queried=result.get('sources_queried', []),
                    total_articles_found=total_found,
                    new_articles=processed,
                    duplicate_articles=total_found - processed
                    if total_found > processed
                    else 0,
                    relevant_articles=matched,
                    high_relevance_articles=int(matched * 0.7),
                )
            else:
                await self.execution_log.complete_execution(
                    execution_id=execution_id,
                    status='failed',
                    sources_queried=[],
                    total_articles_found=0,
                    new_articles=0,
                    duplicate_articles=0,
                    relevant_articles=0,
                    high_relevance_articles=0,
                    error_message=result.get('error', 'Unknown error'),
                )

            return result

        except Exception as e:
            self.logger.error(
                f'Exception during immediate discovery: {e}', exc_info=True
            )

            await self.execution_log.complete_execution(
                execution_id=execution_id,
                status='failed',
                sources_queried=[],
                total_articles_found=0,
                new_articles=0,
                duplicate_articles=0,
                relevant_articles=0,
                high_relevance_articles=0,
                error_message=str(e),
                error_details={'exception_type': type(e).__name__},
            )

            return {
                'success': False,
                'error': str(e),
            }

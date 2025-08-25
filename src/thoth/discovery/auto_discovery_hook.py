"""
Auto-Discovery Hook for Agent Integration

This module provides hooks that automatically analyze conversations for research
topics and proactively suggest discovery sources to users.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from loguru import logger

from thoth.discovery.context_analyzer import ChatContextAnalyzer

if TYPE_CHECKING:
    from thoth.services.service_manager import ServiceManager


class AutoDiscoveryHook:
    """
    Hook that automatically analyzes conversations for research topics.

    This hook integrates with the agent system to provide proactive discovery source
    suggestions based on user conversations and research interests.
    """

    def __init__(self, service_manager: ServiceManager):
        """
        Initialize the auto-discovery hook.

        Args:
            service_manager: ServiceManager instance for accessing services
        """
        self.service_manager = service_manager
        self.analyzer = ChatContextAnalyzer(service_manager)

        # Configuration for hook behavior
        self.config = {
            'enabled': True,
            'min_messages_for_analysis': 3,  # Minimum messages before analyzing
            'analysis_interval_hours': 6,  # How often to analyze per user
            'suggestion_threshold': 0.7,  # Confidence threshold for suggestions
            'auto_create_threshold': 0.85,  # Threshold for automatic creation
            'max_suggestions_per_analysis': 3,  # Limit suggestions to avoid spam
            'proactive_notification': True,  # Whether to proactively notify users
        }

        # Track analysis history to avoid over-analyzing
        self.analysis_history: dict[str, datetime] = {}
        self.user_message_counts: dict[str, int] = {}

        logger.info('Auto-discovery hook initialized')

    async def process_conversation_hook(
        self,
        user_id: str,
        session_id: str | None,
        message: str,
        response: str,  # noqa: ARG002
        message_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Process conversation and analyze for discovery opportunities.

        This hook is called after each conversation turn to analyze research
        topics and suggest discovery sources when appropriate.

        Args:
            user_id: User identifier
            session_id: Session identifier (optional)
            message: User's message
            response: Agent's response
            message_history: Full conversation history (optional)

        Returns:
            Dict with analysis results and any actions taken
        """
        if not self.config['enabled']:
            return {'status': 'disabled', 'actions': []}

        try:
            # Track message count for this user
            self.user_message_counts[user_id] = (
                self.user_message_counts.get(user_id, 0) + 1
            )

            # Check if we should analyze this conversation
            should_analyze = self._should_analyze_conversation(user_id, message)

            if not should_analyze:
                return {
                    'status': 'skipped',
                    'reason': 'analysis_not_needed',
                    'actions': [],
                }

            # Perform analysis
            analysis_result = await self._analyze_conversation_async(
                user_id, session_id, message_history
            )

            if analysis_result.get('status') == 'success':
                # Update analysis history
                self.analysis_history[user_id] = datetime.now()

                return {
                    'status': 'completed',
                    'analysis_result': analysis_result,
                    'actions': analysis_result.get('actions', []),
                }
            else:
                return {
                    'status': 'failed',
                    'error': analysis_result.get('message', 'Analysis failed'),
                    'actions': [],
                }

        except Exception as e:
            logger.error(f'Error in auto-discovery hook: {e}')
            return {'status': 'error', 'error': str(e), 'actions': []}

    async def proactive_discovery_check(
        self, user_id: str, session_id: str | None = None
    ) -> dict[str, Any]:
        """
        Proactively check for discovery opportunities for a user.

        This method can be called periodically or triggered by external events
        to check if a user might benefit from new discovery sources.

        Args:
            user_id: User identifier
            session_id: Session identifier (optional)

        Returns:
            Dict with check results and recommendations
        """
        try:
            logger.info(f'Running proactive discovery check for user {user_id}')

            # Get contextual recommendations
            recommendations = self.analyzer.get_contextual_discovery_recommendations(
                user_id=user_id,
                session_id=session_id,
                include_auto_create=False,  # Don't auto-create in proactive mode
            )

            if recommendations.get('status') != 'success':
                return recommendations

            suggestions = recommendations.get('suggestions', [])
            high_confidence_suggestions = [
                s
                for s in suggestions
                if s['confidence'] >= self.config['suggestion_threshold']
            ]

            actions = []
            notifications = []

            if high_confidence_suggestions:
                # Limit suggestions to avoid overwhelming the user
                limited_suggestions = high_confidence_suggestions[
                    : self.config['max_suggestions_per_analysis']
                ]

                # Check if any suggestions meet auto-creation threshold
                auto_create_candidates = [
                    s
                    for s in limited_suggestions
                    if s['confidence'] >= self.config['auto_create_threshold']
                ]

                if auto_create_candidates and self.config.get(
                    'auto_create_enabled', False
                ):
                    # Auto-create high-confidence sources
                    creation_results = self.analyzer.auto_create_discovery_sources(
                        auto_create_candidates,
                        auto_create_threshold=self.config['auto_create_threshold'],
                        user_id=user_id,
                    )
                    actions.extend(creation_results)

                    successful_creates = [
                        r for r in creation_results if r.get('created', False)
                    ]
                    if successful_creates:
                        notifications.append(
                            {
                                'type': 'auto_created_sources',
                                'count': len(successful_creates),
                                'sources': [
                                    r['source_name'] for r in successful_creates
                                ],
                            }
                        )

                # Generate suggestion notification
                if self.config['proactive_notification']:
                    notifications.append(
                        {
                            'type': 'discovery_suggestions',
                            'count': len(limited_suggestions),
                            'suggestions': [
                                {
                                    'source_name': s['source_name'],
                                    'source_type': s['source_type'],
                                    'confidence': s['confidence'],
                                    'reasoning': s['reasoning'][
                                        :100
                                    ],  # Truncate for notification
                                }
                                for s in limited_suggestions
                            ],
                        }
                    )

            return {
                'status': 'success',
                'user_id': user_id,
                'session_id': session_id,
                'topics_identified': len(recommendations.get('topics', [])),
                'suggestions_generated': len(suggestions),
                'high_confidence_suggestions': len(high_confidence_suggestions),
                'actions': actions,
                'notifications': notifications,
                'timestamp': datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f'Error in proactive discovery check: {e}')
            return {
                'status': 'error',
                'error': str(e),
                'actions': [],
                'notifications': [],
            }

    def _should_analyze_conversation(self, user_id: str, message: str) -> bool:
        """Determine if we should analyze this conversation for opportunities."""
        # Check if user has enough messages
        message_count = self.user_message_counts.get(user_id, 0)
        if message_count < self.config['min_messages_for_analysis']:
            return False

        # Check if we've analyzed recently
        last_analysis = self.analysis_history.get(user_id)
        if last_analysis:
            time_since_last = datetime.now() - last_analysis
            if time_since_last < timedelta(
                hours=self.config['analysis_interval_hours']
            ):
                return False

        # Check if message contains research-related keywords
        research_indicators = [
            'research',
            'paper',
            'study',
            'analysis',
            'method',
            'algorithm',
            'model',
            'experiment',
            'data',
            'results',
            'findings',
            'approach',
            'technique',
            'framework',
            'system',
            'learn about',
            'interested in',
            'working on',
            'project',
            'thesis',
            'dissertation',
        ]

        message_lower = message.lower()
        has_research_indicators = any(
            indicator in message_lower for indicator in research_indicators
        )

        return has_research_indicators

    async def _analyze_conversation_async(
        self,
        user_id: str,
        session_id: str | None,
        message_history: list[dict[str, Any]] | None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Asynchronously analyze conversation for discovery opportunities."""
        try:
            # Run analysis in background to avoid blocking conversation
            loop = asyncio.get_event_loop()
            analysis_result = await loop.run_in_executor(
                None, self._run_discovery_analysis, user_id, session_id
            )

            return analysis_result

        except Exception as e:
            logger.error(f'Error in async conversation analysis: {e}')
            return {'status': 'error', 'message': str(e), 'actions': []}

    def _run_discovery_analysis(
        self, user_id: str, session_id: str | None
    ) -> dict[str, Any]:
        """Run the actual discovery analysis (blocking operation)."""
        try:
            # Get recommendations without auto-creation in hook mode
            recommendations = self.analyzer.get_contextual_discovery_recommendations(
                user_id=user_id, session_id=session_id, include_auto_create=False
            )

            if recommendations.get('status') != 'success':
                return recommendations

            suggestions = recommendations.get('suggestions', [])
            topics = recommendations.get('topics', [])

            # Filter suggestions by confidence threshold
            filtered_suggestions = [
                s
                for s in suggestions
                if s['confidence'] >= self.config['suggestion_threshold']
            ]

            actions = []

            if filtered_suggestions:
                # Log the suggestions for potential user notification
                logger.info(
                    f'Found {len(filtered_suggestions)} discovery suggestions for user {user_id}'
                )

                actions.append(
                    {
                        'type': 'suggestions_available',
                        'count': len(filtered_suggestions),
                        'user_id': user_id,
                        'session_id': session_id,
                        'suggestions': filtered_suggestions[
                            :3
                        ],  # Limit for performance
                    }
                )

                # Check for auto-creation candidates
                auto_create_candidates = [
                    s
                    for s in filtered_suggestions
                    if s['confidence'] >= self.config['auto_create_threshold']
                ]

                if auto_create_candidates:
                    actions.append(
                        {
                            'type': 'auto_create_candidates',
                            'count': len(auto_create_candidates),
                            'candidates': auto_create_candidates,
                        }
                    )

            return {
                'status': 'success',
                'user_id': user_id,
                'session_id': session_id,
                'topics_identified': len(topics),
                'suggestions_generated': len(suggestions),
                'filtered_suggestions': len(filtered_suggestions),
                'actions': actions,
                'timestamp': datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f'Error running discovery analysis: {e}')
            return {'status': 'error', 'message': str(e), 'actions': []}

    def update_config(self, config_updates: dict[str, Any]) -> None:
        """Update hook configuration."""
        self.config.update(config_updates)
        logger.info(f'Updated auto-discovery hook config: {config_updates}')

    def get_config(self) -> dict[str, Any]:
        """Get current hook configuration."""
        return self.config.copy()

    def reset_user_history(self, user_id: str | None = None) -> None:
        """Reset analysis history for a user or all users."""
        if user_id:
            self.analysis_history.pop(user_id, None)
            self.user_message_counts.pop(user_id, None)
            logger.info(f'Reset auto-discovery history for user {user_id}')
        else:
            self.analysis_history.clear()
            self.user_message_counts.clear()
            logger.info('Reset auto-discovery history for all users')

    def get_user_stats(self, user_id: str) -> dict[str, Any]:
        """Get statistics about a user's auto-discovery activity."""
        return {
            'user_id': user_id,
            'message_count': self.user_message_counts.get(user_id, 0),
            'last_analysis': self.analysis_history.get(user_id),
            'analyses_performed': 1 if user_id in self.analysis_history else 0,
        }


class AutoDiscoveryManager:
    """
    Manager for coordinating auto-discovery hooks and background processes.

    This class provides a higher-level interface for managing auto-discovery
    functionality across the system.
    """

    def __init__(self, service_manager: ServiceManager):
        """
        Initialize the auto-discovery manager.

        Args:
            service_manager: ServiceManager instance
        """
        self.service_manager = service_manager
        self.hook = AutoDiscoveryHook(service_manager)
        self.background_task: asyncio.Task | None = None

        logger.info('Auto-discovery manager initialized')

    async def start_background_processing(
        self, check_interval_minutes: int = 30
    ) -> None:
        """
        Start background processing for proactive discovery checks.

        Args:
            check_interval_minutes: Interval between background checks
        """
        if self.background_task and not self.background_task.done():
            logger.warning('Background processing already running')
            return

        self.background_task = asyncio.create_task(
            self._background_processing_loop(check_interval_minutes)
        )
        logger.info(
            f'Started auto-discovery background processing (interval: {check_interval_minutes}min)'
        )

    async def stop_background_processing(self) -> None:
        """Stop background processing."""
        if self.background_task:
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
            self.background_task = None
            logger.info('Stopped auto-discovery background processing')

    async def _background_processing_loop(self, interval_minutes: int) -> None:
        """Background loop for proactive discovery checks."""
        while True:
            try:
                await asyncio.sleep(interval_minutes * 60)

                # This would typically get active user IDs from the memory system
                # For now, we'll skip background processing to avoid complexity
                logger.debug('Background discovery check cycle completed')

            except asyncio.CancelledError:
                logger.info('Background discovery processing cancelled')
                break
            except Exception as e:
                logger.error(f'Error in background discovery processing: {e}')
                # Continue processing despite errors
                await asyncio.sleep(60)  # Wait a minute before retrying

    def get_hook(self) -> AutoDiscoveryHook:
        """Get the auto-discovery hook instance."""
        return self.hook

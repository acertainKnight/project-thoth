"""
MCP-compliant tag management tools.

This module provides tools for managing tags, consolidating similar tags,
and suggesting new tags for articles.
"""

from typing import Any  # noqa: I001

from ..base_tools import MCPTool, MCPToolCallResult, NoInputTool
from ...services.background_tasks import (
    BackgroundTask,
    BackgroundTaskManager,
    TaskStatus,
)
from datetime import UTC


class ConsolidateTagsMCPTool(NoInputTool):
    """MCP tool for consolidating similar tags into canonical forms."""

    @property
    def name(self) -> str:
        return 'consolidate_tags'

    @property
    def description(self) -> str:
        return 'Consolidate similar tags into canonical forms using AI analysis to reduce tag duplication and improve organization'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Consolidate tags across the collection."""
        try:
            # Use the tag service to consolidate tags
            result = self.service_manager.tag.consolidate_only()

            response_text = '**Tag Consolidation Complete**\n\n'
            response_text += '**Summary:**\n'
            response_text += f'  - Articles processed: {result["articles_processed"]}\n'
            response_text += f'  - Articles updated: {result["articles_updated"]}\n'
            response_text += f'  - Tags consolidated: {result["tags_consolidated"]}\n'
            response_text += f'  - Original tag count: {result["original_tag_count"]}\n'
            response_text += f'  - Final tag count: {result["final_tag_count"]}\n\n'

            # Show consolidation mappings if available
            if result.get('consolidation_mappings'):
                mappings = result['consolidation_mappings']
                if mappings:
                    response_text += '**Tag Mappings Applied:**\n'
                    for old_tag, new_tag in list(mappings.items())[
                        :10
                    ]:  # Show first 10
                        response_text += f"  - '{old_tag}' → '{new_tag}'\n"

                    if len(mappings) > 10:
                        response_text += (
                            f'  ... and {len(mappings) - 10} more mappings\n'
                        )
                    response_text += '\n'

            response_text += 'Tag consolidation completed. Similar tags have been merged using AI analysis.'

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            return self.handle_error(e)


class SuggestTagsMCPTool(MCPTool):
    """
    MCP tool for suggesting additional tags for articles.

    **DEPRECATED**: This tool is deprecated. Tag suggestion provides low value
    and is rarely used. Use manual tagging or consolidation tools instead. This
    tool is no longer registered in the MCP tool registry.
    """

    @property
    def name(self) -> str:
        return 'suggest_tags'

    @property
    def description(self) -> str:
        return 'Suggest additional relevant tags for articles based on content analysis and existing tag vocabulary'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_identifier': {
                    'type': 'string',
                    'description': 'Article title, DOI, or arXiv ID to suggest tags for. If not provided, suggests tags for all articles.',
                },
                'force_all': {
                    'type': 'boolean',
                    'description': 'Force tag suggestions for all articles in the collection',
                    'default': False,
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Suggest tags for articles."""
        try:
            article_identifier = arguments.get('article_identifier')
            force_all = arguments.get('force_all', False)

            if article_identifier and not force_all:
                # Suggest tags for a specific article
                # First find the article
                search_results = await self.service_manager.rag.search_async(
                    query=article_identifier, k=1
                )

                if not search_results:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f'Article not found: {article_identifier}',
                            }
                        ],
                        isError=True,
                    )

                article = search_results[0]
                title = article.get('title', 'Unknown')
                content = article.get('content', '')
                metadata = article.get('metadata', {})
                current_tags = metadata.get('tags', [])

                # Get available tag vocabulary
                available_tags = self.service_manager.tag.extract_all_tags()

                if not available_tags:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': 'No existing tag vocabulary found. Process some articles first to build a tag vocabulary.',
                            }
                        ],
                        isError=True,
                    )

                # Get tag suggestions
                suggestion_result = self.service_manager.tag.suggest_tags(
                    title=title,
                    abstract=content[:1000],  # Use first 1000 chars as abstract
                    current_tags=current_tags,
                    available_tags=available_tags,
                )

                suggested_tags = suggestion_result.get('suggested_tags', [])
                reasoning = suggestion_result.get('reasoning', '')

                response_text = f'**Tag Suggestions for:** {title}\n\n'
                response_text += f'**Current Tags:** {", ".join(current_tags) if current_tags else "None"}\n\n'

                if suggested_tags:
                    response_text += (
                        f'**Suggested Tags:** {", ".join(suggested_tags)}\n\n'
                    )
                    response_text += f'**Reasoning:** {reasoning}\n\n'
                    response_text += '**Note:** Use `update_article_metadata` to apply these suggestions.'
                else:
                    response_text += 'No additional tags suggested. Current tags appear comprehensive.'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text}]
                )

            else:
                # Suggest tags for all articles
                result = self.service_manager.tag.suggest_additional()

                response_text = '**Tag Suggestions Complete**\n\n'
                response_text += '**Summary:**\n'
                response_text += (
                    f'  - Articles processed: {result["articles_processed"]}\n'
                )
                response_text += f'  - Articles updated: {result["articles_updated"]}\n'
                response_text += f'  - Tags added: {result["tags_added"]}\n'
                response_text += (
                    f'  - Vocabulary size: {result.get("vocabulary_size", 0)}\n\n'
                )

                if result['articles_updated'] > 0:
                    response_text += 'Additional tags have been suggested and applied to articles that could benefit from better tagging.'
                else:
                    response_text += 'All articles already have comprehensive tags. No additional suggestions needed.'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text}]
                )

        except Exception as e:
            return self.handle_error(e)


class ManageTagVocabularyMCPTool(NoInputTool):
    """MCP tool for viewing and managing the tag vocabulary."""

    @property
    def name(self) -> str:
        return 'manage_tag_vocabulary'

    @property
    def description(self) -> str:
        return 'View and analyze the current tag vocabulary, including usage statistics and tag distribution'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Get tag vocabulary and statistics."""
        try:
            # Extract all tags from the collection
            all_tags = self.service_manager.tag.extract_all_tags()

            if not all_tags:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'No tags found in the collection. Process some articles first to build a tag vocabulary.',
                        }
                    ]
                )

            # Get tag usage statistics by sampling articles
            tag_usage = {}
            sample_results = await self.service_manager.rag.search_async(
                query='', k=100
            )

            for result in sample_results:
                metadata = result.get('metadata', {})
                article_tags = metadata.get('tags', [])

                for tag in article_tags:
                    tag_usage[tag] = tag_usage.get(tag, 0) + 1

            # Sort tags by usage
            sorted_tags = sorted(tag_usage.items(), key=lambda x: x[1], reverse=True)

            response_text = '**Tag Vocabulary Management**\n\n'
            response_text += '**Overview:**\n'
            response_text += f'  - Total unique tags: {len(all_tags)}\n'
            response_text += f'  - Tags in use: {len(tag_usage)}\n'
            response_text += f'  - Unused tags: {len(all_tags) - len(tag_usage)}\n\n'

            # Show most popular tags
            if sorted_tags:
                response_text += '🔥 **Most Popular Tags:**\n'
                for i, (tag, count) in enumerate(sorted_tags[:15], 1):
                    response_text += f'  {i:2d}. {tag} ({count} articles)\n'

                if len(sorted_tags) > 15:
                    response_text += f'  ... and {len(sorted_tags) - 15} more tags\n'
                response_text += '\n'

            # Show tags that might need consolidation (similar names)
            potentially_similar = []
            for i, tag1 in enumerate(all_tags):
                for _j, tag2 in enumerate(all_tags[i + 1 :], i + 1):
                    # Simple similarity check - contains one in the other
                    if (
                        tag1.lower() in tag2.lower()
                        or tag2.lower() in tag1.lower()
                        or (
                            abs(len(tag1) - len(tag2)) <= 2
                            and sum(
                                a != b
                                for a, b in zip(
                                    tag1.lower(), tag2.lower(), strict=False
                                )
                            )
                            <= 2
                        )
                    ):
                        potentially_similar.append((tag1, tag2))
                        if len(potentially_similar) >= 10:  # Limit to avoid spam
                            break
                if len(potentially_similar) >= 10:
                    break

            if potentially_similar:
                response_text += (
                    '**Potentially Similar Tags (may need consolidation):**\n'
                )
                for tag1, tag2 in potentially_similar[:10]:
                    usage1 = tag_usage.get(tag1, 0)
                    usage2 = tag_usage.get(tag2, 0)
                    response_text += f"  - '{tag1}' ({usage1}) ↔ '{tag2}' ({usage2})\n"
                response_text += (
                    '\nUse `consolidate_tags` to merge similar tags automatically.\n\n'
                )

            response_text += '🛠 **Available Actions:**\n'
            response_text += '  - `consolidate_tags` - Merge similar tags using AI\n'
            response_text += '  - `suggest_tags` - Add missing tags to articles\n'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class ConsolidateAndRetagMCPTool(NoInputTool):
    """MCP tool for comprehensive tag consolidation and retagging."""

    @property
    def name(self) -> str:
        return 'consolidate_and_retag'

    @property
    def description(self) -> str:
        return 'Trigger comprehensive tag consolidation and retagging as a background operation. This operation may take several minutes for large collections. Returns immediately with a task ID to track progress.'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Trigger tag consolidation and retagging in the background."""
        try:
            # Get or create background task manager
            if not hasattr(self.service_manager, 'background_tasks'):
                self.service_manager.background_tasks = BackgroundTaskManager()

            # Create a background task that calls the tag service
            task_id = self.service_manager.background_tasks.create_task(
                name='consolidate_and_retag',
                func=self.service_manager.tag.consolidate_and_retag,
            )

            response_text = '**Tag Consolidation and Retagging Triggered**\n\n'
            response_text += f'**Task ID:** `{task_id}`\n\n'
            response_text += '**What happens next:**\n'
            response_text += '  1. Analyzing all tags in your collection\n'
            response_text += '  2. Identifying similar tags for consolidation\n'
            response_text += '  3. Suggesting additional relevant tags\n'
            response_text += '  4. Updating all affected articles\n\n'
            response_text += '**This operation is running in the background.**\n'
            response_text += (
                'Use `get_task_status` tool with this task ID to check progress.\n\n'
            )
            response_text += '**Note:** Depending on your collection size, this may take several minutes.'

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            return self.handle_error(e)


class GetTaskStatusMCPTool(MCPTool):
    """MCP tool for checking the status of background tasks."""

    @property
    def name(self) -> str:
        return 'get_task_status'

    @property
    def description(self) -> str:
        return (
            'Check the status of background tasks (tagging, reindexing, PDF processing, discovery). '
            'Provide a task_id for specific task, or use task_type to see recent tasks of that type. '
            'If neither provided, shows all recent tasks.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'task_id': {
                    'type': 'string',
                    'description': 'Specific task ID to check (optional)',
                },
                'task_type': {
                    'type': 'string',
                    'description': 'Filter by task type: tagging, reindex, processing, discovery, all',
                    'enum': ['tagging', 'reindex', 'processing', 'discovery', 'all'],
                    'default': 'all',
                },
                'status_filter': {
                    'type': 'string',
                    'description': 'Filter by status: running, completed, failed, pending, all',
                    'enum': ['running', 'completed', 'failed', 'pending', 'all'],
                    'default': 'all',
                },
                'limit': {
                    'type': 'integer',
                    'description': 'Maximum number of tasks to show',
                    'default': 10,
                    'minimum': 1,
                    'maximum': 50,
                },
            },
            'required': [],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Get the status of background tasks."""
        try:
            task_id = arguments.get('task_id')
            task_type = arguments.get('task_type', 'all')
            status_filter = arguments.get('status_filter', 'all')
            limit = arguments.get('limit', 10)

            # Get or create background task manager
            if not hasattr(self.service_manager, 'background_tasks'):
                self.service_manager.background_tasks = BackgroundTaskManager()

            task_manager = self.service_manager.background_tasks

            # If specific task_id provided, get that task
            if task_id:
                task = task_manager.get_task_status(task_id)

                if not task:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f'Task not found: {task_id}\n\nThis task may have expired or the task ID is invalid.',
                            }
                        ],
                        isError=True,
                    )

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': self._format_task_detail(task)}]
                )

            # List tasks with filters
            status_enum = None
            if status_filter and status_filter != 'all':
                status_enum = TaskStatus(status_filter)

            all_tasks = task_manager.list_tasks(status=status_enum, limit=50)

            # Filter by task type if specified
            if task_type and task_type != 'all':
                type_keywords = {
                    'tagging': ['tag', 'consolidat', 'retag'],
                    'reindex': ['reindex', 'index', 'rag'],
                    'processing': ['process', 'pdf', 'extract'],
                    'discovery': ['discover', 'search', 'fetch'],
                }
                keywords = type_keywords.get(task_type, [])
                filtered_tasks = [
                    t for t in all_tasks if any(kw in t.name.lower() for kw in keywords)
                ]
                all_tasks = filtered_tasks

            # Apply limit
            all_tasks = all_tasks[:limit]

            if not all_tasks:
                filter_desc = []
                if task_type and task_type != 'all':
                    filter_desc.append(f'type: {task_type}')
                if status_filter and status_filter != 'all':
                    filter_desc.append(f'status: {status_filter}')
                filter_str = f' ({", ".join(filter_desc)})' if filter_desc else ''

                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'No background tasks found{filter_str}.\n\n'
                            'Tasks are created when you run operations like:\n'
                            '- Tag consolidation and retagging\n'
                            '- Collection reindexing\n'
                            '- Bulk PDF processing\n'
                            '- Discovery searches',
                        }
                    ]
                )

            # Build summary response
            response_text = '**Background Tasks**\n\n'

            # Group by status
            running = [t for t in all_tasks if t.status == TaskStatus.RUNNING]
            pending = [t for t in all_tasks if t.status == TaskStatus.PENDING]
            completed = [t for t in all_tasks if t.status == TaskStatus.COMPLETED]
            failed = [t for t in all_tasks if t.status == TaskStatus.FAILED]

            if running:
                response_text += '**Currently Running:**\n'
                for task in running:
                    elapsed = ''
                    if task.started_at:
                        from datetime import datetime

                        now = datetime.now(UTC)
                        elapsed_sec = (now - task.started_at).total_seconds()
                        elapsed = f' ({elapsed_sec:.0f}s)'
                    response_text += f'  - {task.name}{elapsed}\n'
                    response_text += f'    ID: `{task.task_id[:8]}...`\n'
                response_text += '\n'

            if pending:
                response_text += '**Pending:**\n'
                for task in pending:
                    response_text += f'  - {task.name}\n'
                    response_text += f'    ID: `{task.task_id[:8]}...`\n'
                response_text += '\n'

            if completed:
                response_text += '**Recently Completed:**\n'
                for task in completed[:5]:  # Show last 5 completed
                    duration = ''
                    if task.completed_at and task.started_at:
                        dur_sec = (task.completed_at - task.started_at).total_seconds()
                        duration = f' ({dur_sec:.1f}s)'
                    response_text += f'  - {task.name}{duration}\n'
                if len(completed) > 5:
                    response_text += f'  ... and {len(completed) - 5} more\n'
                response_text += '\n'

            if failed:
                response_text += '**Failed:**\n'
                for task in failed[:3]:  # Show last 3 failed
                    response_text += f'  - {task.name}\n'
                    if task.error:
                        error_preview = (
                            task.error[:50] + '...'
                            if len(task.error) > 50
                            else task.error
                        )
                        response_text += f'    Error: {error_preview}\n'
                response_text += '\n'

            response_text += f'Showing {len(all_tasks)} tasks. '
            response_text += (
                'Use `task_id` parameter to get detailed info on a specific task.'
            )

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            return self.handle_error(e)

    def _format_task_detail(self, task: BackgroundTask) -> str:
        """Format detailed view for a single task."""
        response_text = f'**Task Status: {task.name}**\n\n'
        response_text += f'**Task ID:** `{task.task_id}`\n'
        response_text += f'**Status:** {task.status.value.upper()}\n'
        response_text += (
            f'**Created:** {task.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}\n'
        )

        if task.started_at:
            response_text += (
                f'**Started:** {task.started_at.strftime("%Y-%m-%d %H:%M:%S UTC")}\n'
            )

        if task.status == TaskStatus.RUNNING:
            # Show running status
            if task.started_at:
                from datetime import datetime

                now = datetime.now(UTC)
                elapsed = (now - task.started_at).total_seconds()
                response_text += f'**Running for:** {elapsed:.1f} seconds\n\n'
            response_text += 'The task is currently running...\n'
            response_text += 'Check again in a few moments for completion status.'

        elif task.status == TaskStatus.COMPLETED:
            # Show completion with results
            if task.completed_at and task.started_at:
                duration = task.completed_at.timestamp() - task.started_at.timestamp()
                response_text += f'**Completed:** {task.completed_at.strftime("%Y-%m-%d %H:%M:%S UTC")}\n'
                response_text += f'**Duration:** {duration:.2f} seconds\n\n'

            response_text += 'Task completed successfully!\n\n'

            # Show results if available
            if task.result:
                result = task.result
                response_text += '**Results:**\n'

                # Generic result display
                for key, value in result.items():
                    if key == 'consolidation_mappings' and isinstance(value, dict):
                        if value:
                            response_text += f'  - {key}: {len(value)} mappings\n'
                    elif isinstance(value, (int, float, str, bool)):
                        response_text += f'  - {key}: {value}\n'
                    elif isinstance(value, list):
                        response_text += f'  - {key}: {len(value)} items\n'

                # Show consolidation mappings sample
                if result.get('consolidation_mappings'):
                    mappings = result['consolidation_mappings']
                    if mappings:
                        response_text += '\n**Sample Tag Consolidations:**\n'
                        for old_tag, new_tag in list(mappings.items())[:5]:
                            response_text += f"  - '{old_tag}' -> '{new_tag}'\n"

                        if len(mappings) > 5:
                            response_text += (
                                f'  ... and {len(mappings) - 5} more consolidations\n'
                            )

        elif task.status == TaskStatus.FAILED:
            # Show failure with error
            if task.completed_at:
                response_text += f'**Failed at:** {task.completed_at.strftime("%Y-%m-%d %H:%M:%S UTC")}\n'

            response_text += f'\n**Task failed with error:**\n```\n{task.error}\n```\n'

        elif task.status == TaskStatus.PENDING:
            response_text += '\n**Task is pending and has not started yet.**'

        return response_text

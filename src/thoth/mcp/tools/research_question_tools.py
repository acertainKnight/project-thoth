"""
MCP-compliant research question management tools.

This module provides MCP-compliant tools for managing research questions
that drive the discovery system. Research questions define WHAT to search for
(keywords, topics, authors) and WHICH sources to query (arxiv, pubmed, etc.).
"""

from typing import Any
from uuid import UUID

from loguru import logger

from ..base_tools import MCPTool, MCPToolCallResult, NoInputTool


class ListAvailableSourcesMCPTool(NoInputTool):
    """MCP tool for listing all available discovery sources."""

    @property
    def name(self) -> str:
        return 'list_available_sources'

    @property
    def description(self) -> str:
        return 'List all available discovery sources including built-in APIs and custom workflows'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """List available sources."""
        try:
            from thoth.discovery.plugins import plugin_registry

            content_parts = []

            # Get all registered plugins dynamically
            registered_plugins = plugin_registry.list_plugins()

            if registered_plugins:
                content_parts.append(
                    {
                        'type': 'text',
                        'text': '**Built-in API Sources:**\n',
                    }
                )

                for source_id in sorted(registered_plugins):
                    # Get plugin description if available
                    plugin_cls = plugin_registry.get(source_id)
                    if (
                        plugin_cls
                        and hasattr(plugin_cls, '__doc__')
                        and plugin_cls.__doc__
                    ):
                        description = plugin_cls.__doc__.strip().split('\n')[0]
                    else:
                        description = f'{source_id.replace("_", " ").title()} source'

                    content_parts.append(
                        {
                            'type': 'text',
                            'text': f'  - `{source_id}`: {description}\n',
                        }
                    )

            # Query custom sources (browser workflows)
            try:
                from thoth.repositories.browser_workflow_repository import (
                    BrowserWorkflowRepository,
                )

                postgres_service = self.service_manager.postgres
                workflow_repo = BrowserWorkflowRepository(postgres_service)
                workflows = await workflow_repo.get_active_workflows()

                if workflows:
                    content_parts.append(
                        {
                            'type': 'text',
                            'text': '\n**Custom Sources (Browser Workflows):**\n',
                        }
                    )
                    for workflow in workflows:
                        content_parts.append(
                            {
                                'type': 'text',
                                'text': f'  - `{workflow["name"]}`: {workflow.get("description", "Custom workflow")}\n',
                            }
                        )
            except Exception as e:
                logger.warning(f'Could not load browser workflows: {e}')

            # Add special options
            content_parts.append(
                {
                    'type': 'text',
                    'text': '\n**Special Options:**\n  - `*`: Query all available sources\n',
                }
            )

            return MCPToolCallResult(content=content_parts)

        except Exception as e:
            return self.handle_error(e)


class CreateResearchQuestionMCPTool(MCPTool):
    """MCP tool for creating a new research question."""

    @property
    def name(self) -> str:
        return 'create_research_question'

    @property
    def description(self) -> str:
        return 'Create a new research question for automated paper discovery'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'user_id': {
                    'type': 'string',
                    'description': 'User identifier',
                    'default': 'default_user',
                },
                'name': {
                    'type': 'string',
                    'description': 'Unique name for the research question',
                },
                'description': {
                    'type': 'string',
                    'description': 'Optional detailed description of the research question',
                },
                'keywords': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Keywords to search for in papers',
                },
                'topics': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Research topics/categories (e.g., cs.AI, cs.LG)',
                    'default': [],
                },
                'authors': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Preferred authors (optional)',
                    'default': [],
                },
                'selected_sources': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Which sources to query (required, no default). Use list_available_sources to see options.',
                },
                'schedule_frequency': {
                    'type': 'string',
                    'description': 'How often to run discovery',
                    'enum': ['daily', 'weekly', 'monthly', 'on-demand'],
                    'default': 'daily',
                },
                'schedule_time': {
                    'type': 'string',
                    'description': 'Time to run discovery (HH:MM format, 24-hour)',
                    'default': '03:00',
                },
                'schedule_days_of_week': {
                    'type': 'array',
                    'items': {'type': 'integer', 'minimum': 1, 'maximum': 7},
                    'description': 'Days of week for weekly schedule (ISO 8601: 1=Monday, 7=Sunday)',
                },
                'min_relevance_score': {
                    'type': 'number',
                    'description': 'Minimum relevance threshold (0.0-1.0)',
                    'default': 0.7,
                    'minimum': 0.0,
                    'maximum': 1.0,
                },
                'max_articles_per_run': {
                    'type': 'integer',
                    'description': 'Maximum articles to fetch per run',
                    'default': 50,
                    'minimum': 1,
                    'maximum': 500,
                },
                'auto_download_enabled': {
                    'type': 'boolean',
                    'description': 'Automatically download matching PDFs',
                    'default': False,
                },
                'auto_download_min_score': {
                    'type': 'number',
                    'description': 'Minimum score threshold for auto-download',
                    'default': 0.7,
                    'minimum': 0.0,
                    'maximum': 1.0,
                },
                'publication_date_range': {
                    'type': 'object',
                    'description': 'Date range for filtering publications',
                    'properties': {
                        'start': {
                            'type': 'string',
                            'description': 'Start date (YYYY-MM-DD format or relative like "2023-01-01")',
                        },
                        'end': {
                            'type': 'string',
                            'description': 'End date (YYYY-MM-DD format or "present")',
                        },
                    },
                },
            },
            'required': ['name', 'keywords', 'selected_sources'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create a new research question."""
        try:
            research_question_service = self.service_manager.research_question

            question_id = await research_question_service.create_research_question(
                user_id=arguments.get('user_id', 'default_user'),
                name=arguments['name'],
                description=arguments.get('description'),
                keywords=arguments['keywords'],
                topics=arguments.get('topics', []),
                authors=arguments.get('authors', []),
                selected_sources=arguments['selected_sources'],
                schedule_frequency=arguments.get('schedule_frequency', 'daily'),
                schedule_time=arguments.get('schedule_time'),
                schedule_days_of_week=arguments.get('schedule_days_of_week'),
                min_relevance_score=arguments.get('min_relevance_score', 0.7),
                auto_download_enabled=arguments.get('auto_download_enabled', False),
                auto_download_min_score=arguments.get('auto_download_min_score', 0.7),
                max_articles_per_run=arguments.get('max_articles_per_run', 50),
                publication_date_range=arguments.get('publication_date_range'),
            )

            if question_id:
                sources_str = ', '.join(arguments['selected_sources'])
                description_text = (
                    f'\n**Description:** {arguments["description"]}'
                    if arguments.get('description')
                    else ''
                )
                schedule_days = (
                    f' on days {arguments["schedule_days_of_week"]}'
                    if arguments.get('schedule_days_of_week')
                    else ''
                )
                date_range_text = ''
                if arguments.get('publication_date_range'):
                    dr = arguments['publication_date_range']
                    date_range_text = f'\n**Date Range:** {dr.get("start", "start")} to {dr.get("end", "present")}'

                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"""✓ Research question created successfully!

**Question ID:** {question_id}
**Name:** {arguments['name']}{description_text}
**Keywords:** {', '.join(arguments['keywords'])}
**Topics:** {', '.join(arguments.get('topics', []))}
**Sources:** {sources_str}
**Schedule:** {arguments.get('schedule_frequency', 'daily')} at {arguments.get('schedule_time', '03:00')}{schedule_days}
**Min Relevance:** {arguments.get('min_relevance_score', 0.7)}
**Auto Download:** {arguments.get('auto_download_enabled', False)} (min score: {arguments.get('auto_download_min_score', 0.7)})
**Max Articles/Run:** {arguments.get('max_articles_per_run', 50)}{date_range_text}

The scheduler will automatically run discovery based on the schedule. You can also manually trigger discovery using `run_discovery_for_question`.
""",
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Failed to create research question '{arguments['name']}'",
                        }
                    ],
                    isError=True,
                )

        except ValueError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Validation error: {e}'}],
                isError=True,
            )
        except Exception as e:
            return self.handle_error(e)


class ListResearchQuestionsMCPTool(MCPTool):
    """MCP tool for listing research questions."""

    @property
    def name(self) -> str:
        return 'list_research_questions'

    @property
    def description(self) -> str:
        return 'List all research questions for a user'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'user_id': {
                    'type': 'string',
                    'description': 'User identifier',
                    'default': 'default_user',
                },
                'active_only': {
                    'type': 'boolean',
                    'description': 'Only return active questions',
                    'default': True,
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """List research questions."""
        try:
            research_question_service = self.service_manager.research_question

            questions = await research_question_service.get_user_questions(
                user_id=arguments.get('user_id', 'default_user'),
                active_only=arguments.get('active_only', True),
            )

            if not questions:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'No research questions found. Create one with create_research_question!',
                        }
                    ]
                )

            content_parts = []
            content_parts.append(
                {
                    'type': 'text',
                    'text': f'**Found {len(questions)} Research Questions:**\n\n',
                }
            )

            for question in questions:
                question_text = f'**{question["name"]}**\n'
                if question.get('description'):
                    question_text += f'  - Description: {question["description"]}\n'
                question_text += f'  - ID: {question["id"]}\n'
                question_text += f'  - Keywords: {", ".join(question["keywords"])}\n'
                question_text += (
                    f'  - Topics: {", ".join(question.get("topics", []))}\n'
                )
                question_text += (
                    f'  - Sources: {", ".join(question["selected_sources"])}\n'
                )
                question_text += f'  - Schedule: {question["schedule_frequency"]}'
                if question.get('schedule_time'):
                    question_text += f' at {question["schedule_time"]}'
                if question.get('schedule_days_of_week'):
                    question_text += f' (days: {question["schedule_days_of_week"]})'
                question_text += '\n'
                question_text += f'  - Created: {question["created_at"]}\n\n'

                content_parts.append({'type': 'text', 'text': question_text})

            return MCPToolCallResult(content=content_parts)

        except Exception as e:
            return self.handle_error(e)


class GetResearchQuestionMCPTool(MCPTool):
    """MCP tool for getting details of a specific research question."""

    @property
    def name(self) -> str:
        return 'get_research_question'

    @property
    def description(self) -> str:
        return 'Get detailed information about a specific research question'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'question_id': {
                    'type': 'string',
                    'description': 'UUID of the research question',
                },
                'user_id': {
                    'type': 'string',
                    'description': 'User identifier',
                    'default': 'default_user',
                },
            },
            'required': ['question_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Get research question details."""
        try:
            question_id = UUID(arguments['question_id'])

            # Get question from repository
            from thoth.repositories.research_question_repository import (
                ResearchQuestionRepository,
            )

            postgres_service = self.service_manager.postgres
            repo = ResearchQuestionRepository(postgres_service)
            question = await repo.get_by_id(question_id)

            if not question:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Research question {question_id} not found',
                        }
                    ],
                    isError=True,
                )

            # Verify user ownership
            user_id = arguments.get('user_id', 'default_user')
            if question.get('user_id') != user_id:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'User {user_id} does not have access to question {question_id}',
                        }
                    ],
                    isError=True,
                )

            # Normalize list fields (asyncpg can return None for empty arrays)
            keywords = question.get('keywords') or []
            topics = question.get('topics') or []
            authors = question.get('authors') or []
            selected_sources = question.get('selected_sources') or []
            schedule_days_of_week = question.get('schedule_days_of_week')

            # Format scalars for display (datetime/time from DB may be non-string)
            def _str_val(v: Any, default: str = 'N/A') -> str:
                if v is None:
                    return default
                return str(v)

            schedule_time_str = _str_val(question.get('schedule_time'), 'Not set')
            next_run_str = _str_val(question.get('next_run_at'), 'Not scheduled')
            created_str = _str_val(question.get('created_at'), 'N/A')
            updated_str = _str_val(question.get('updated_at'), 'N/A')
            last_run_str = _str_val(question.get('last_run_at'), 'Never')

            description_text = (
                f'\n**Description:** {question.get("description")}\n'
                if question.get('description')
                else ''
            )
            schedule_days = (
                f'\n  - Days of Week: {schedule_days_of_week}'
                if schedule_days_of_week
                else ''
            )

            details = f"""**Research Question: {question.get('name', '')}**
{description_text}
**ID:** {question.get('id')}
**User:** {question.get('user_id', '')}
**Status:** {'Active' if question.get('is_active', True) else 'Inactive'}

**Search Criteria:**
  - Keywords: {', '.join(str(k) for k in keywords)}
  - Topics: {', '.join(str(t) for t in topics)}
  - Authors: {', '.join(str(a) for a in authors)}
  - Min Relevance: {question.get('min_relevance_score', 0.7)}

**Sources:**
  {', '.join(str(s) for s in selected_sources)}

**Schedule:**
  - Frequency: {question.get('schedule_frequency', '')}
  - Time: {schedule_time_str}{schedule_days}
  - Next Run: {next_run_str}

**Options:**
  - Auto Download PDFs: {question.get('auto_download_enabled', False)} (min score: {question.get('auto_download_min_score', 0.7)})
  - Max Articles per Run: {question.get('max_articles_per_run', 50)}

**Timestamps:**
  - Created: {created_str}
  - Updated: {updated_str}
  - Last Run: {last_run_str}
"""

            return MCPToolCallResult(content=[{'type': 'text', 'text': details}])

        except ValueError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Invalid question ID: {e}'}],
                isError=True,
            )
        except Exception as e:
            return self.handle_error(e)


class UpdateResearchQuestionMCPTool(MCPTool):
    """MCP tool for updating a research question."""

    @property
    def name(self) -> str:
        return 'update_research_question'

    @property
    def description(self) -> str:
        return 'Update an existing research question'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'question_id': {
                    'type': 'string',
                    'description': 'UUID of the research question',
                },
                'user_id': {
                    'type': 'string',
                    'description': 'User identifier',
                    'default': 'default_user',
                },
                'name': {
                    'type': 'string',
                    'description': 'Updated name for the research question',
                },
                'description': {
                    'type': 'string',
                    'description': 'Updated detailed description',
                },
                'keywords': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Updated keywords',
                },
                'topics': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Updated topics',
                },
                'authors': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Updated preferred authors',
                },
                'selected_sources': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Updated sources',
                },
                'schedule_frequency': {
                    'type': 'string',
                    'enum': ['daily', 'weekly', 'monthly', 'on-demand'],
                    'description': 'Updated schedule frequency',
                },
                'schedule_time': {
                    'type': 'string',
                    'description': 'Updated time to run discovery (HH:MM format, 24-hour)',
                },
                'schedule_days_of_week': {
                    'type': 'array',
                    'items': {'type': 'integer', 'minimum': 1, 'maximum': 7},
                    'description': 'Updated days of week for weekly schedule (ISO 8601: 1=Monday, 7=Sunday)',
                },
                'min_relevance_score': {
                    'type': 'number',
                    'description': 'Updated relevance threshold',
                    'minimum': 0.0,
                    'maximum': 1.0,
                },
                'auto_download_enabled': {
                    'type': 'boolean',
                    'description': 'Enable/disable automatic PDF downloads',
                },
                'auto_download_min_score': {
                    'type': 'number',
                    'description': 'Updated minimum score for auto-download',
                    'minimum': 0.0,
                    'maximum': 1.0,
                },
                'max_articles_per_run': {
                    'type': 'integer',
                    'description': 'Updated maximum articles per run',
                    'minimum': 1,
                    'maximum': 500,
                },
                'is_active': {
                    'type': 'boolean',
                    'description': 'Activate or deactivate the question',
                },
                'publication_date_range': {
                    'type': 'object',
                    'description': 'Date range for filtering publications',
                    'properties': {
                        'start': {
                            'type': 'string',
                            'description': 'Start date (YYYY-MM-DD format or relative like "2023-01-01")',
                        },
                        'end': {
                            'type': 'string',
                            'description': 'End date (YYYY-MM-DD format or "present")',
                        },
                    },
                },
            },
            'required': ['question_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Update research question."""
        try:
            research_question_service = self.service_manager.research_question
            question_id = UUID(arguments['question_id'])
            user_id = arguments.get('user_id', 'default_user')

            # Build updates dict (only include fields that were provided)
            updates = {}
            for field in [
                'name',
                'description',
                'keywords',
                'topics',
                'authors',
                'selected_sources',
                'schedule_frequency',
                'schedule_time',
                'schedule_days_of_week',
                'min_relevance_score',
                'auto_download_enabled',
                'auto_download_min_score',
                'max_articles_per_run',
                'is_active',
                'publication_date_range',
            ]:
                if field in arguments:
                    updates[field] = arguments[field]

            if not updates:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'No updates provided. Specify at least one field to update.',
                        }
                    ],
                    isError=True,
                )

            success = await research_question_service.update_research_question(
                question_id=question_id,
                user_id=user_id,
                **updates,
            )

            if success:
                updated_fields = ', '.join(updates.keys())
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'✓ Successfully updated research question {question_id}\nUpdated fields: {updated_fields}',
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Failed to update research question {question_id}',
                        }
                    ],
                    isError=True,
                )

        except PermissionError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Permission denied: {e}'}],
                isError=True,
            )
        except ValueError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Validation error: {e}'}],
                isError=True,
            )
        except Exception as e:
            return self.handle_error(e)


class DeleteResearchQuestionMCPTool(MCPTool):
    """MCP tool for deleting a research question."""

    @property
    def name(self) -> str:
        return 'delete_research_question'

    @property
    def description(self) -> str:
        return 'Delete a research question (soft delete by default)'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'question_id': {
                    'type': 'string',
                    'description': 'UUID of the research question',
                },
                'user_id': {
                    'type': 'string',
                    'description': 'User identifier',
                    'default': 'default_user',
                },
                'hard_delete': {
                    'type': 'boolean',
                    'description': 'Permanently delete (default: soft delete)',
                    'default': False,
                },
            },
            'required': ['question_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Delete research question."""
        try:
            research_question_service = self.service_manager.research_question
            question_id = UUID(arguments['question_id'])
            user_id = arguments.get('user_id', 'default_user')
            hard_delete = arguments.get('hard_delete', False)

            success = await research_question_service.delete_research_question(
                question_id=question_id,
                user_id=user_id,
                hard_delete=hard_delete,
            )

            if success:
                action = 'deleted' if hard_delete else 'deactivated'
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'✓ Successfully {action} research question {question_id}',
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Failed to delete research question {question_id}',
                        }
                    ],
                    isError=True,
                )

        except PermissionError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Permission denied: {e}'}],
                isError=True,
            )
        except ValueError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Invalid question ID: {e}'}],
                isError=True,
            )
        except Exception as e:
            return self.handle_error(e)


class RunDiscoveryForQuestionMCPTool(MCPTool):
    """MCP tool for manually triggering discovery for a research question."""

    @property
    def name(self) -> str:
        return 'run_discovery_for_question'

    @property
    def description(self) -> str:
        return 'Manually trigger discovery for a specific research question'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'question_id': {
                    'type': 'string',
                    'description': 'UUID of the research question',
                },
                'user_id': {
                    'type': 'string',
                    'description': 'User identifier',
                    'default': 'default_user',
                },
                'max_articles': {
                    'type': 'integer',
                    'description': 'Override max articles for this run',
                    'minimum': 1,
                    'maximum': 500,
                },
                'force_run': {
                    'type': 'boolean',
                    'description': 'Force run even if recently executed',
                    'default': False,
                },
            },
            'required': ['question_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Run discovery for question."""
        try:
            question_id = UUID(arguments['question_id'])
            max_articles = arguments.get('max_articles')
            force_run = arguments.get('force_run', False)

            # Get the discovery orchestrator service
            discovery_orchestrator = self.service_manager.discovery_orchestrator

            if not discovery_orchestrator:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Discovery orchestrator service not available',
                        }
                    ],
                    isError=True,
                )

            # Trigger discovery for this question
            result = await discovery_orchestrator.run_discovery_for_question(
                question_id=question_id,
                max_articles=max_articles,
                _force_run=force_run,
            )

            if result.get('success'):
                articles_found = result.get('articles_found', 0)
                articles_downloaded = result.get('articles_downloaded', 0)
                sources_used = result.get('sources_used', [])

                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"""✓ Discovery completed for question {question_id}

**Results:**
  - Articles found: {articles_found}
  - Articles downloaded: {articles_downloaded}
  - Sources queried: {', '.join(sources_used)}

{'Errors encountered:' + chr(10) + chr(10).join(result.get('errors', [])) if result.get('errors') else ''}
""",
                        }
                    ]
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Discovery failed for question {question_id}: {error_msg}',
                        }
                    ],
                    isError=True,
                )

        except ValueError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Invalid question ID: {e}'}],
                isError=True,
            )
        except Exception as e:
            return self.handle_error(e)

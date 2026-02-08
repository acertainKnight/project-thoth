"""
MCP-compliant workflow builder tools for LLM-powered article source auto-detection.

This module provides tools for the chat agent to analyze any URL, auto-detect
article listing structure, refine selectors based on feedback, and confirm
workflows as new discovery sources.
"""

from typing import Any
from urllib.parse import urlparse

from loguru import logger

from ..base_tools import MCPTool, MCPToolCallResult


class AnalyzeSourceUrlMCPTool(MCPTool):
    """MCP tool for analyzing a URL to auto-detect article extraction selectors."""

    @property
    def name(self) -> str:
        return 'analyze_source_url'

    @property
    def description(self) -> str:
        return (
            'Analyze a URL to automatically detect how to extract article/paper listings. '
            'Returns page type, confidence score, proposed selectors, sample articles, '
            'and detected search filters. Use when user wants to add a custom source.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'url': {
                    'type': 'string',
                    'description': 'The URL to analyze (should be a page with article listings)',
                },
            },
            'required': ['url'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Analyze a URL to detect article structure."""
        try:
            from thoth.discovery.browser.workflow_builder import WorkflowBuilder

            url = arguments['url']

            # Create WorkflowBuilder instance
            workflow_builder = WorkflowBuilder()
            await workflow_builder.initialize()

            logger.info(f'Analyzing URL via MCP tool: {url}')

            # Analyze the URL (no screenshot for agent context)
            result = await workflow_builder.analyze_url(
                url=url,
                include_screenshot=False,
            )

            # Format sample articles for agent (limit to 3 for context efficiency)
            samples_text = []
            for i, article in enumerate(result.sample_articles[:3], 1):
                sample = [f'**Sample {i}:**']
                if article.title:
                    sample.append(f'  Title: {article.title[:100]}')
                if article.authors:
                    authors = (
                        article.authors
                        if isinstance(article.authors, list)
                        else [article.authors]
                    )
                    sample.append(f'  Authors: {", ".join(authors[:3])}')
                if article.url:
                    sample.append(f'  URL: {article.url[:80]}')
                if article.publication_date:
                    sample.append(f'  Date: {article.publication_date}')
                samples_text.append('\n'.join(sample))

            # Format search filters
            filters_text = []
            for sf in result.search_filters:
                filters_text.append(
                    f'  - {sf["element_type"]}: {sf.get("description", "detected")}'
                )

            # Build confidence rating
            if result.confidence >= 0.8:
                conf_rating = '🟢 HIGH'
            elif result.confidence >= 0.6:
                conf_rating = '🟡 MEDIUM'
            else:
                conf_rating = '🔴 LOW'

            response_text = f"""✓ URL Analysis Complete

**Page**: {result.page_title}
**Type**: {result.page_type}
**Articles Found**: {result.total_articles_found}
**Confidence**: {conf_rating} ({result.confidence:.2f})

**Detected Selectors**:
- Container: `{result.article_container_selector}`
- Fields: {', '.join(result.selectors.keys())}
- Pagination: {'Yes' if result.pagination_selector else 'No'}

**Search Filters Detected**: {len(result.search_filters)}
{chr(10).join(filters_text) if filters_text else '  (none)'}

**Sample Articles**:
{chr(10).join(samples_text)}

**Notes**: {result.notes[:200]}

---
**Next Steps**:
- If this looks correct, confirm by calling `confirm_source_workflow` with a name
- If something is wrong, call `refine_source_selectors` with feedback describing what's incorrect
- Low confidence (<0.6) may indicate the page structure is unusual - consider trying a different page on the site"""

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            logger.error(f'Error analyzing URL: {e}', exc_info=True)
            return self.handle_error(e)


class RefineSourceSelectorsMCPTool(MCPTool):
    """MCP tool for refining selectors based on user feedback."""

    @property
    def name(self) -> str:
        return 'refine_source_selectors'

    @property
    def description(self) -> str:
        return (
            'Refine article extraction selectors based on user feedback. '
            'Use after analyze_source_url if the auto-detected selectors are wrong. '
            'Provide natural language feedback describing what is incorrect.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'url': {
                    'type': 'string',
                    'description': 'The URL being analyzed',
                },
                'current_selectors': {
                    'type': 'string',
                    'description': 'Current selector configuration as JSON string (from analyze_source_url)',
                },
                'user_feedback': {
                    'type': 'string',
                    'description': "User's description of what's wrong (e.g., 'The titles are in h2 tags, not h3')",
                },
            },
            'required': ['url', 'current_selectors', 'user_feedback'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Refine selectors based on feedback."""
        try:
            import json

            from thoth.discovery.browser.workflow_builder import WorkflowBuilder

            url = arguments['url']
            current_selectors_str = arguments['current_selectors']
            user_feedback = arguments['user_feedback']

            # Parse JSON string to dict
            try:
                current_selectors = (
                    json.loads(current_selectors_str)
                    if isinstance(current_selectors_str, str)
                    else current_selectors_str
                )
            except json.JSONDecodeError as e:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Error: Invalid JSON in current_selectors: {e}',
                        }
                    ],
                    isError=True,
                )

            # Create WorkflowBuilder instance
            workflow_builder = WorkflowBuilder()
            await workflow_builder.initialize()

            logger.info(f'Refining selectors for {url}: {user_feedback[:100]}')

            # Refine selectors
            result = await workflow_builder.refine_selectors(
                url=url,
                current_selectors=current_selectors,
                user_feedback=user_feedback,
                include_screenshot=False,
            )

            # Format samples
            samples_text = []
            for i, article in enumerate(result.sample_articles[:3], 1):
                sample = [f'**Sample {i}:**']
                if article.title:
                    sample.append(f'  Title: {article.title[:100]}')
                if article.authors:
                    authors = (
                        article.authors
                        if isinstance(article.authors, list)
                        else [article.authors]
                    )
                    sample.append(f'  Authors: {", ".join(authors[:3])}')
                if article.url:
                    sample.append(f'  URL: {article.url[:80]}')
                samples_text.append('\n'.join(sample))

            # Confidence rating
            if result.confidence >= 0.8:
                conf_rating = '🟢 HIGH'
            elif result.confidence >= 0.6:
                conf_rating = '🟡 MEDIUM'
            else:
                conf_rating = '🔴 LOW'

            response_text = f"""✓ Selectors Refined

**Articles Found**: {result.total_articles_found}
**Confidence**: {conf_rating} ({result.confidence:.2f})

**Updated Selectors**:
- Container: `{result.article_container_selector}`
- Fields: {', '.join(result.selectors.keys())}

**Sample Articles**:
{chr(10).join(samples_text)}

**Notes**: {result.notes[:200]}

---
If this looks better, call `confirm_source_workflow`. Otherwise provide more feedback to refine further."""

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            logger.error(f'Error refining selectors: {e}', exc_info=True)
            return self.handle_error(e)


class ConfirmSourceWorkflowMCPTool(MCPTool):
    """MCP tool for confirming and saving a workflow as a discovery source."""

    @property
    def name(self) -> str:
        return 'confirm_source_workflow'

    @property
    def description(self) -> str:
        return (
            'Confirm and save an analyzed URL as a persistent discovery source. '
            'After analyze_source_url (or refine_source_selectors) shows good results, '
            'use this to save the workflow so it can be queried during discovery runs.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'url': {
                    'type': 'string',
                    'description': 'The analyzed URL',
                },
                'name': {
                    'type': 'string',
                    'description': 'Unique name for the workflow (e.g., "nber_working_papers")',
                },
                'description': {
                    'type': 'string',
                    'description': 'Optional description of what this source provides',
                },
                'article_container_selector': {
                    'type': 'string',
                    'description': 'CSS selector for article containers (from analyze output)',
                },
                'selectors': {
                    'type': 'string',
                    'description': 'Field selectors as JSON string (from analyze output)',
                },
                'pagination_selector': {
                    'type': 'string',
                    'description': 'Pagination selector (optional, from analyze output)',
                },
                'search_filters': {
                    'type': 'string',
                    'description': 'Search/filter UI elements as JSON string (optional, from analyze output)',
                },
                'max_articles_per_run': {
                    'type': 'integer',
                    'description': 'Maximum articles to extract per run',
                    'default': 100,
                    'minimum': 1,
                },
                'requires_authentication': {
                    'type': 'boolean',
                    'description': 'Whether this source requires login',
                    'default': False,
                },
            },
            'required': ['url', 'name', 'article_container_selector', 'selectors'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Confirm and save workflow as a discovery source."""
        try:
            import json

            from thoth.repositories.browser_workflow_repository import (
                BrowserWorkflowRepository,
            )

            postgres_service = self.service_manager.postgres
            workflow_repo = BrowserWorkflowRepository(postgres_service)

            url = arguments['url']
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.hostname or url

            # Parse JSON strings to dicts/lists
            try:
                selectors = (
                    json.loads(arguments['selectors'])
                    if isinstance(arguments['selectors'], str)
                    else arguments['selectors']
                )
                search_filters = (
                    json.loads(arguments.get('search_filters', '[]'))
                    if isinstance(arguments.get('search_filters'), str)
                    else arguments.get('search_filters', [])
                )
            except json.JSONDecodeError as e:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Error: Invalid JSON in parameters: {e}',
                        }
                    ],
                    isError=True,
                )

            # Build extraction rules
            extraction_rules = {
                'article_container': arguments['article_container_selector'],
                'fields': selectors,
            }

            # Build pagination config
            pagination_config = None
            if arguments.get('pagination_selector'):
                pagination_config = {
                    'type': 'button',
                    'selector': arguments['pagination_selector'],
                    'next_page_selector': arguments['pagination_selector'],
                }
            extraction_rules['pagination'] = pagination_config

            # Build search config from detected filters
            search_config: dict[str, Any] | None = None
            if search_filters:
                filters = []
                search_input_selector = None
                search_button_selector = None

                for sf in search_filters:
                    if sf.get('element_type') in ('search_input', 'keyword_input'):
                        search_input_selector = sf.get('css_selector')
                        search_button_selector = sf.get('submit_selector')
                    else:
                        param_name = {
                            'date_filter': 'date_range',
                            'subject_filter': 'subject',
                            'sort_dropdown': 'sort_order',
                        }.get(sf.get('element_type', ''), sf.get('element_type', ''))

                        filters.append(
                            {
                                'name': sf.get(
                                    'description', sf.get('element_type', '')
                                ),
                                'parameter_name': param_name,
                                'selector': {'css': sf.get('css_selector', '')},
                                'filter_type': sf.get('filter_type', 'text_input'),
                                'optional': True,
                            }
                        )

                search_config = {
                    'search_input_selector': (
                        {'css': search_input_selector}
                        if search_input_selector
                        else None
                    ),
                    'search_button_selector': (
                        {'css': search_button_selector}
                        if search_button_selector
                        else None
                    ),
                    'keywords_format': 'space_separated',
                    'filters': filters,
                }

            if search_config:
                extraction_rules['search_config'] = search_config

            # Create workflow
            workflow_data = {
                'name': arguments['name'],
                'description': arguments.get('description')
                or f'Auto-detected workflow for {domain}',
                'website_domain': domain,
                'start_url': url,
                'extraction_rules': extraction_rules,
                'requires_authentication': arguments.get(
                    'requires_authentication', False
                ),
                'authentication_type': None,
                'pagination_config': pagination_config,
                'max_articles_per_run': arguments.get('max_articles_per_run', 100),
                'timeout_seconds': 60,
                'is_active': True,
                'health_status': 'healthy',
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'total_articles_extracted': 0,
            }

            workflow_id = await workflow_repo.create(workflow_data)

            if not workflow_id:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: Failed to save workflow to database.',
                        }
                    ],
                    isError=True,
                )

            logger.info(
                f'Created workflow via MCP tool: {workflow_id} ({arguments["name"]})'
            )

            response_text = f"""✓ Custom Source Created Successfully!

**Workflow ID**: {workflow_id}
**Name**: {arguments['name']}
**Domain**: {domain}
**Max Articles**: {arguments.get('max_articles_per_run', 100)}

**What Happens Next**:
- This source is now active and will be included in discovery runs
- When a research question runs discovery, keywords from the question will be typed into the search box (if detected)
- The system will extract articles, follow pagination, and stop when it hits already-discovered papers
- Articles from this source will be deduplicated with other sources

**To use this source in a research question**:
- Add `"{arguments['name']}"` to the `selected_sources` list when creating/updating a research question
- Or use `["*"]` to query all sources including this one"""

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            logger.error(f'Error confirming workflow: {e}', exc_info=True)
            return self.handle_error(e)


__all__ = [
    'AnalyzeSourceUrlMCPTool',
    'ConfirmSourceWorkflowMCPTool',
    'RefineSourceSelectorsMCPTool',
]

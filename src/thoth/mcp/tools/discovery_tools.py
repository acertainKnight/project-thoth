"""
MCP-compliant discovery source management tools.

This module provides MCP-compliant tools for managing discovery sources
(ArXiv, PubMed, scrapers) that automatically find and filter research articles.
"""

from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult, NoInputTool, SourceNameTool


class ListDiscoverySourcesMCPTool(NoInputTool):
    """MCP tool for listing all configured discovery sources."""

    @property
    def name(self) -> str:
        return 'list_discovery_sources'

    @property
    def description(self) -> str:
        return 'List all configured discovery sources with their status and configuration details'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """List discovery sources."""
        try:
            sources = self.service_manager.discovery.list_sources()

            if not sources:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': "No discovery sources configured. Use 'create_arxiv_source' or 'create_pubmed_source' to add one.",
                        }
                    ]
                )

            content_parts = []

            # Add summary
            content_parts.append(
                {
                    'type': 'text',
                    'text': f'**Found {len(sources)} Discovery Sources:**\n',
                }
            )

            # Add each source as structured content
            for source in sources:
                status = '🟢 Active' if source.is_active else '🔴 Inactive'
                source_text = f'**{source.name}** ({source.source_type}) - {status}\n'
                source_text += f'  Description: {source.description}\n'

                if source.last_run:
                    source_text += f'  Last run: {source.last_run}\n'

                if source.schedule_config:
                    source_text += f'  Schedule: Every {source.schedule_config.interval_minutes} minutes\n'
                    source_text += f'  Max articles: {source.schedule_config.max_articles_per_run}\n'

                # Add API config details if available
                if hasattr(source, 'api_config') and source.api_config:
                    if 'keywords' in source.api_config:
                        source_text += (
                            f'  Keywords: {", ".join(source.api_config["keywords"])}\n'
                        )
                    if 'categories' in source.api_config:
                        source_text += f'  Categories: {", ".join(source.api_config["categories"])}\n'

                content_parts.append({'type': 'text', 'text': source_text})

            return MCPToolCallResult(content=content_parts)

        except Exception as e:
            return self.handle_error(e)


class CreateArxivSourceMCPTool(MCPTool):
    """MCP tool for creating an ArXiv discovery source."""

    @property
    def name(self) -> str:
        return 'create_arxiv_source'

    @property
    def description(self) -> str:
        return 'Create an ArXiv discovery source to automatically find and download academic papers'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': "Unique name for the discovery source (e.g., 'arxiv_ml_papers')",
                },
                'keywords': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Keywords to search for in paper titles and abstracts',
                },
                'categories': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': "ArXiv categories to search (e.g., ['cs.LG', 'cs.AI'])",
                    'default': ['cs.LG', 'cs.AI'],
                },
                'max_articles': {
                    'type': 'integer',
                    'description': 'Maximum number of articles to fetch per run',
                    'default': 50,
                    'minimum': 1,
                    'maximum': 500,
                },
                'schedule_hours': {
                    'type': 'integer',
                    'description': 'How often to run discovery (in hours)',
                    'default': 24,
                    'minimum': 1,
                    'maximum': 168,
                },
            },
            'required': ['name', 'keywords'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create ArXiv source."""
        try:
            name = arguments['name']
            keywords = arguments['keywords']
            categories = arguments.get('categories', ['cs.LG', 'cs.AI'])
            max_articles = arguments.get('max_articles', 50)
            schedule_hours = arguments.get('schedule_hours', 24)

            source_config = {
                'name': name,
                'source_type': 'api',
                'description': f'ArXiv source for {", ".join(categories)} papers',
                'is_active': True,
                'api_config': {
                    'source': 'arxiv',
                    'categories': categories,
                    'keywords': keywords,
                    'sort_by': 'lastUpdatedDate',
                    'sort_order': 'descending',
                },
                'schedule_config': {
                    'interval_minutes': schedule_hours * 60,
                    'max_articles_per_run': max_articles,
                },
            }

            success = self.service_manager.discovery.create_source(source_config)

            if success:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Successfully created ArXiv source '{name}' with categories {categories} and keywords {keywords}",
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Failed to create ArXiv source '{name}' - it may already exist",
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class CreatePubmedSourceMCPTool(MCPTool):
    """MCP tool for creating a PubMed discovery source."""

    @property
    def name(self) -> str:
        return 'create_pubmed_source'

    @property
    def description(self) -> str:
        return 'Create a PubMed discovery source to automatically find and download medical/biological research papers'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': "Unique name for the discovery source (e.g., 'pubmed_cancer_research')",
                },
                'keywords': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Keywords to search for in paper titles and abstracts',
                },
                'max_articles': {
                    'type': 'integer',
                    'description': 'Maximum number of articles to fetch per run',
                    'default': 50,
                    'minimum': 1,
                    'maximum': 500,
                },
                'schedule_hours': {
                    'type': 'integer',
                    'description': 'How often to run discovery (in hours)',
                    'default': 24,
                    'minimum': 1,
                    'maximum': 168,
                },
                'date_filter': {
                    'type': 'string',
                    'description': "Date filter for papers (e.g., '2023/01/01:2024/12/31')",
                    'default': None,
                },
            },
            'required': ['name', 'keywords'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create PubMed source."""
        try:
            name = arguments['name']
            keywords = arguments['keywords']
            max_articles = arguments.get('max_articles', 50)
            schedule_hours = arguments.get('schedule_hours', 24)
            date_filter = arguments.get('date_filter')

            api_config = {
                'source': 'pubmed',
                'keywords': keywords,
                'sort_by': 'pub_date',
                'sort_order': 'desc',
            }

            if date_filter:
                api_config['date_filter'] = date_filter

            source_config = {
                'name': name,
                'source_type': 'api',
                'description': 'PubMed source for biomedical papers',
                'is_active': True,
                'api_config': api_config,
                'schedule_config': {
                    'interval_minutes': schedule_hours * 60,
                    'max_articles_per_run': max_articles,
                },
            }

            success = self.service_manager.discovery.create_source(source_config)

            if success:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Successfully created PubMed source '{name}' with keywords {keywords}",
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Failed to create PubMed source '{name}' - it may already exist",
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class GetDiscoverySourceMCPTool(SourceNameTool):
    """MCP tool for getting details of a specific discovery source."""

    @property
    def name(self) -> str:
        return 'get_discovery_source'

    @property
    def description(self) -> str:
        return 'Get detailed configuration and status information for a specific discovery source'

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Get discovery source details."""
        try:
            source_name = arguments['source_name']
            source = self.service_manager.discovery.get_source(source_name)

            if not source:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Discovery source '{source_name}' not found",
                        }
                    ],
                    isError=True,
                )

            # Format source details
            status = '🟢 Active' if source.is_active else '🔴 Inactive'
            source_details = f'**Discovery Source: {source.name}**\n\n'
            source_details += f'**Type:** {source.source_type}\n'
            source_details += f'**Status:** {status}\n'
            source_details += f'**Description:** {source.description}\n'

            if source.created_at:
                source_details += f'**Created:** {source.created_at}\n'
            if source.last_run:
                source_details += f'**Last Run:** {source.last_run}\n'

            # Add schedule configuration
            if source.schedule_config:
                source_details += '\n**Schedule Configuration:**\n'
                source_details += f'  - Interval: Every {source.schedule_config.interval_minutes} minutes\n'
                source_details += (
                    f'  - Max Articles: {source.schedule_config.max_articles_per_run}\n'
                )

            # Add API configuration
            if hasattr(source, 'api_config') and source.api_config:
                source_details += '\n**API Configuration:**\n'
                for key, value in source.api_config.items():
                    if isinstance(value, list):
                        value = ', '.join(value)
                    source_details += f'  - {key}: {value}\n'

            return MCPToolCallResult(content=[{'type': 'text', 'text': source_details}])

        except Exception as e:
            return self.handle_error(e)


class RunDiscoveryMCPTool(MCPTool):
    """MCP tool for running discovery on a specific source."""

    @property
    def name(self) -> str:
        return 'run_discovery'

    @property
    def description(self) -> str:
        return 'Execute discovery process for a specific source to find and download new articles'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'source_name': {
                    'type': 'string',
                    'description': 'Name of the discovery source to run (optional - runs all active sources if not specified)',
                },
                'max_articles': {
                    'type': 'integer',
                    'description': 'Override maximum articles for this run',
                    'minimum': 1,
                    'maximum': 500,
                },
                'force_run': {
                    'type': 'boolean',
                    'description': 'Force run even if source was recently executed',
                    'default': False,
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Run discovery process."""
        try:
            source_name = arguments.get('source_name')
            max_articles = arguments.get('max_articles')
            force_run = arguments.get('force_run', False)

            # Build run configuration
            run_config = {}
            if max_articles:
                run_config['max_articles'] = max_articles
            if force_run:
                run_config['force_run'] = force_run

            if source_name:
                # Run specific source
                result = self.service_manager.discovery.run_source(
                    source_name, run_config
                )
                if result.get('success'):
                    articles_found = result.get('articles_found', 0)
                    articles_processed = result.get('articles_processed', 0)

                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f"Discovery completed for '{source_name}':\n  - Articles found: {articles_found}\n  - Articles processed: {articles_processed}",
                            }
                        ]
                    )
                else:
                    error_msg = result.get('error', 'Unknown error occurred')
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f"Discovery failed for '{source_name}': {error_msg}",
                            }
                        ],
                        isError=True,
                    )
            else:
                # Run all active sources
                results = self.service_manager.discovery.run_all_sources(run_config)

                if results:
                    total_found = sum(
                        r.get('articles_found', 0) for r in results.values()
                    )
                    total_processed = sum(
                        r.get('articles_processed', 0) for r in results.values()
                    )
                    successful_sources = [
                        name for name, r in results.items() if r.get('success')
                    ]

                    result_text = (
                        f'Discovery completed for {len(successful_sources)} sources:\n'
                    )
                    result_text += f'  - Total articles found: {total_found}\n'
                    result_text += f'  - Total articles processed: {total_processed}\n'
                    result_text += f'  - Sources run: {", ".join(successful_sources)}'

                    return MCPToolCallResult(
                        content=[{'type': 'text', 'text': result_text}]
                    )
                else:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': 'No active discovery sources found to run',
                            }
                        ],
                        isError=True,
                    )

        except Exception as e:
            return self.handle_error(e)


class CreateCrossrefSourceMCPTool(MCPTool):
    """MCP tool for creating a CrossRef discovery source."""

    @property
    def name(self) -> str:
        return 'create_crossref_source'

    @property
    def description(self) -> str:
        return 'Create a CrossRef discovery source to automatically find and download academic papers'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': 'Unique name for the CrossRef source',
                },
                'keywords': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Keywords to search for in CrossRef database',
                },
                'max_articles': {
                    'type': 'integer',
                    'description': 'Maximum articles to fetch per run',
                    'default': 50,
                    'minimum': 1,
                    'maximum': 500,
                },
                'schedule_hours': {
                    'type': 'integer',
                    'description': 'Schedule interval in hours',
                    'default': 24,
                    'minimum': 1,
                    'maximum': 168,
                },
            },
            'required': ['name', 'keywords'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create CrossRef discovery source."""
        try:
            name = arguments['name']
            keywords = arguments['keywords']
            max_articles = arguments.get('max_articles', 50)
            schedule_hours = arguments.get('schedule_hours', 24)

            # Create source configuration
            source_config = {
                'name': name,
                'source_type': 'api',
                'description': f'CrossRef source for {", ".join(keywords)} research',
                'is_active': True,
                'api_config': {
                    'source': 'crossref',
                    'keywords': keywords,
                    'sort_by': 'relevance',
                    'sort_order': 'desc',
                },
                'schedule_config': {
                    'interval_minutes': schedule_hours * 60,
                    'max_articles_per_run': max_articles,
                    'enabled': True,
                },
                'query_filters': [],
            }

            # Create the discovery source
            success = self.service_manager.discovery.create_source(source_config)

            if success:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'**CrossRef Discovery Source Created Successfully!**\n\n'
                            f'**Source Details:**\n'
                            f'- Name: `{name}`\n'
                            f'- Type: CrossRef API\n'
                            f'- Keywords: {", ".join(keywords)}\n'
                            f'- Schedule: Every {schedule_hours} hours, max {max_articles} articles\n\n'
                            f'**Ready to use!** Run discovery with `run_discovery` tool.',
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Failed to create CrossRef source '{name}'. Check if name already exists.",
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class CreateOpenalexSourceMCPTool(MCPTool):
    """MCP tool for creating an OpenAlex discovery source."""

    @property
    def name(self) -> str:
        return 'create_openalex_source'

    @property
    def description(self) -> str:
        return 'Create an OpenAlex discovery source to automatically find and download academic papers from the comprehensive OpenAlex database'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': 'Unique name for the OpenAlex source',
                },
                'keywords': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Keywords to search for in OpenAlex database',
                },
                'max_articles': {
                    'type': 'integer',
                    'description': 'Maximum articles to fetch per run',
                    'default': 50,
                    'minimum': 1,
                    'maximum': 500,
                },
                'schedule_hours': {
                    'type': 'integer',
                    'description': 'Schedule interval in hours',
                    'default': 24,
                    'minimum': 1,
                    'maximum': 168,
                },
            },
            'required': ['name', 'keywords'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create OpenAlex discovery source."""
        try:
            name = arguments['name']
            keywords = arguments['keywords']
            max_articles = arguments.get('max_articles', 50)
            schedule_hours = arguments.get('schedule_hours', 24)

            # Create source configuration
            source_config = {
                'name': name,
                'source_type': 'api',
                'description': f'OpenAlex source for {", ".join(keywords)} research',
                'is_active': True,
                'api_config': {
                    'source': 'openalex',
                    'keywords': keywords,
                    'sort_by': 'relevance',
                },
                'schedule_config': {
                    'interval_minutes': schedule_hours * 60,
                    'max_articles_per_run': max_articles,
                    'enabled': True,
                },
                'query_filters': [],
            }

            # Create the discovery source
            success = self.service_manager.discovery.create_source(source_config)

            if success:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'**OpenAlex Discovery Source Created Successfully!**\n\n'
                            f'**Source Details:**\n'
                            f'- Name: `{name}`\n'
                            f'- Type: OpenAlex API\n'
                            f'- Keywords: {", ".join(keywords)}\n'
                            f'- Schedule: Every {schedule_hours} hours, max {max_articles} articles\n\n'
                            f'**Ready to use!** OpenAlex provides comprehensive metadata and is free to use.',
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Failed to create OpenAlex source '{name}'. Check if name already exists.",
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class CreateBiorxivSourceMCPTool(MCPTool):
    """MCP tool for creating a bioRxiv discovery source."""

    @property
    def name(self) -> str:
        return 'create_biorxiv_source'

    @property
    def description(self) -> str:
        return 'Create a bioRxiv discovery source to automatically find and download preprint papers from bioRxiv'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': 'Unique name for the bioRxiv source',
                },
                'start_date': {
                    'type': 'string',
                    'description': 'Start date for paper search (YYYY-MM-DD format)',
                },
                'end_date': {
                    'type': 'string',
                    'description': 'End date for paper search (YYYY-MM-DD format)',
                },
                'max_articles': {
                    'type': 'integer',
                    'description': 'Maximum articles to fetch per run',
                    'default': 50,
                    'minimum': 1,
                    'maximum': 500,
                },
                'schedule_hours': {
                    'type': 'integer',
                    'description': 'Schedule interval in hours',
                    'default': 24,
                    'minimum': 1,
                    'maximum': 168,
                },
            },
            'required': ['name'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create bioRxiv discovery source."""
        try:
            name = arguments['name']
            start_date = arguments.get('start_date')
            end_date = arguments.get('end_date')
            max_articles = arguments.get('max_articles', 50)
            schedule_hours = arguments.get('schedule_hours', 24)

            # Create API configuration
            api_config = {
                'source': 'biorxiv',
            }
            if start_date:
                api_config['start_date'] = start_date
            if end_date:
                api_config['end_date'] = end_date

            # Create source configuration
            source_config = {
                'name': name,
                'source_type': 'api',
                'description': 'bioRxiv preprint source',
                'is_active': True,
                'api_config': api_config,
                'schedule_config': {
                    'interval_minutes': schedule_hours * 60,
                    'max_articles_per_run': max_articles,
                    'enabled': True,
                },
                'query_filters': [],
            }

            # Create the discovery source
            success = self.service_manager.discovery.create_source(source_config)

            if success:
                date_range = ''
                if start_date or end_date:
                    date_range = f'\n- Date Range: {start_date or "earliest"} to {end_date or "latest"}'

                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'**bioRxiv Discovery Source Created Successfully!**\n\n'
                            f'**Source Details:**\n'
                            f'- Name: `{name}`\n'
                            f'- Type: bioRxiv API{date_range}\n'
                            f'- Schedule: Every {schedule_hours} hours, max {max_articles} articles\n\n'
                            f'🧬 **Ready to use!** bioRxiv provides access to biological sciences preprints.',
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Failed to create bioRxiv source '{name}'. Check if name already exists.",
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class DeleteDiscoverySourceMCPTool(SourceNameTool):
    """MCP tool for deleting a discovery source."""

    @property
    def name(self) -> str:
        return 'delete_discovery_source'

    @property
    def description(self) -> str:
        return 'Delete a discovery source permanently'

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Delete a discovery source."""
        try:
            source_name = arguments['source_name']
            success = self.service_manager.discovery.delete_source(source_name)

            if success:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Successfully deleted discovery source '{source_name}'",
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Failed to delete discovery source '{source_name}' - it may not exist",
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)

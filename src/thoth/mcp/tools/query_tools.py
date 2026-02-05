"""
MCP-compliant query management tools.

This module provides MCP-compliant tools for managing research queries,
converted from the original LangChain-based tools.

**DEPRECATED MODULE**: All legacy query tools are deprecated. Use the 
research_question tools instead, which provide better separation of concerns 
(research questions define WHAT to search for, sources define WHERE to search). 
These tools are no longer registered in the MCP tool registry.
"""

from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult, NoInputTool, QueryNameTool


class ListQueriesMCPTool(NoInputTool):
    """MCP tool for listing all research queries."""

    @property
    def name(self) -> str:
        return 'list_queries'

    @property
    def description(self) -> str:
        return 'List all research queries with their details and configurations'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """List all queries."""
        try:
            queries = self.service_manager.query.get_all_queries()
            if not queries:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'No research queries found. Create one with create_query!',
                        }
                    ]
                )

            # Format queries as structured content
            content_parts = []

            # Add summary
            content_parts.append(
                {
                    'type': 'text',
                    'text': f'**Found {len(queries)} Research Queries:**\n',
                }
            )

            # Add each query as structured content
            for query in queries:
                query_text = f'**{query.name}**\n'
                query_text += f'  - Description: {query.description}\n'
                query_text += f'  - Created: {query.created_at}\n'

                if query.keywords:
                    query_text += f'  - Keywords: {", ".join(query.keywords)}\n'
                if query.required_topics:
                    query_text += (
                        f'  - Required Topics: {", ".join(query.required_topics)}\n'
                    )
                if query.preferred_topics:
                    query_text += (
                        f'  - Preferred Topics: {", ".join(query.preferred_topics)}\n'
                    )
                if query.excluded_topics:
                    query_text += (
                        f'  - Excluded Topics: {", ".join(query.excluded_topics)}\n'
                    )

                content_parts.append({'type': 'text', 'text': query_text})

            return MCPToolCallResult(content=content_parts)

        except Exception as e:
            return self.handle_error(e)


class CreateQueryMCPTool(MCPTool):
    """MCP tool for creating a new research query."""

    @property
    def name(self) -> str:
        return 'create_query'

    @property
    def description(self) -> str:
        return (
            'Create a new research query to filter articles based on specific criteria'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'description': 'Unique name for the query'},
                'description': {
                    'type': 'string',
                    'description': 'Description of what this query searches for',
                },
                'research_question': {
                    'type': 'string',
                    'description': 'Main research question this query addresses',
                },
                'keywords': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Keywords to search for',
                    'default': [],
                },
                'required_topics': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Topics that must be present',
                    'default': [],
                },
                'preferred_topics': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Topics that are preferred but not required',
                    'default': [],
                },
                'excluded_topics': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Topics that should exclude the article',
                    'default': [],
                },
            },
            'required': ['name', 'description', 'research_question'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create a new research query."""
        try:
            from thoth.utilities.schemas import ResearchQuery

            query = ResearchQuery(
                name=arguments['name'],
                description=arguments['description'],
                research_question=arguments['research_question'],
                keywords=arguments.get('keywords', []),
                required_topics=arguments.get('required_topics', []),
                preferred_topics=arguments.get('preferred_topics', []),
                excluded_topics=arguments.get('excluded_topics', []),
            )

            success = self.service_manager.query.create_query(query)

            if success:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Successfully created query '{arguments['name']}'",
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Failed to create query '{arguments['name']}' - it may already exist",
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class GetQueryMCPTool(QueryNameTool):
    """MCP tool for getting details of a specific query."""

    @property
    def name(self) -> str:
        return 'get_query'

    @property
    def description(self) -> str:
        return 'Get detailed information about a specific research query'

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Get query details."""
        try:
            query_name = arguments['query_name']
            query = self.service_manager.query.get_query(query_name)

            if not query:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': f"Query '{query_name}' not found"}
                    ],
                    isError=True,
                )

            # Format query details as structured content
            query_details = f'**Query: {query.name}**\n\n'
            query_details += f'**Description:** {query.description}\n'
            query_details += f'**Research Question:** {query.research_question}\n'
            query_details += f'**Created:** {query.created_at}\n'

            if query.keywords:
                query_details += f'**Keywords:** {", ".join(query.keywords)}\n'
            if query.required_topics:
                query_details += (
                    f'**Required Topics:** {", ".join(query.required_topics)}\n'
                )
            if query.preferred_topics:
                query_details += (
                    f'**Preferred Topics:** {", ".join(query.preferred_topics)}\n'
                )
            if query.excluded_topics:
                query_details += (
                    f'**Excluded Topics:** {", ".join(query.excluded_topics)}\n'
                )

            return MCPToolCallResult(content=[{'type': 'text', 'text': query_details}])

        except Exception as e:
            return self.handle_error(e)


class UpdateQueryMCPTool(MCPTool):
    """MCP tool for updating an existing research query."""

    @property
    def name(self) -> str:
        return 'update_query'

    @property
    def description(self) -> str:
        return 'Update an existing research query with new parameters'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'query_name': {
                    'type': 'string',
                    'description': 'Name of the query to update',
                },
                'description': {
                    'type': 'string',
                    'description': 'New description (optional)',
                },
                'research_question': {
                    'type': 'string',
                    'description': 'New research question (optional)',
                },
                'keywords': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'New keywords list (optional)',
                },
                'required_topics': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'New required topics list (optional)',
                },
                'preferred_topics': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'New preferred topics list (optional)',
                },
                'excluded_topics': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'New excluded topics list (optional)',
                },
            },
            'required': ['query_name'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Update a query."""
        try:
            query_name = arguments['query_name']

            # Build updates dict from provided arguments
            updates = {}
            for field in [
                'description',
                'research_question',
                'keywords',
                'required_topics',
                'preferred_topics',
                'excluded_topics',
            ]:
                if field in arguments:
                    updates[field] = arguments[field]

            if not updates:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'No updates provided'}],
                    isError=True,
                )

            success = self.service_manager.query.update_query(query_name, updates)

            if success:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Successfully updated query '{query_name}'",
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Failed to update query '{query_name}' - it may not exist",
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class DeleteQueryMCPTool(QueryNameTool):
    """MCP tool for deleting a research query."""

    @property
    def name(self) -> str:
        return 'delete_query'

    @property
    def description(self) -> str:
        return 'Delete a research query permanently'

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Delete a query."""
        try:
            query_name = arguments['query_name']
            success = self.service_manager.query.delete_query(query_name)

            if success:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Successfully deleted query '{query_name}'",
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Failed to delete query '{query_name}' - it may not exist",
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)

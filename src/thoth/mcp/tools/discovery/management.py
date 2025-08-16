"""Discovery source management tools."""

from typing import Any

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult, SourceNameTool


class GetDiscoverySourceMCPTool(SourceNameTool):
    """MCP tool for getting details about a specific discovery source."""

    name = 'get_discovery_source'
    description = 'Get detailed information about a specific discovery source configuration.'

    def run_with_source_name(self, source_name: str) -> MCPToolCallResult:
        """Get details about a discovery source."""
        try:
            source = self.service_manager.discovery.get_source(source_name)

            if not source:
                return MCPToolCallResult(
                    content=f'Discovery source "{source_name}" not found.', is_error=True
                )

            # Format source details
            source_type = source.get('type', 'unknown')
            type_emoji = {
                'arxiv': '📄',
                'pubmed': '🧬',
                'crossref': '🔗',
                'openalex': '📖',
                'biorxiv': '🧪',
                'scraper': '🌐',
            }.get(source_type, '📝')

            response = f'{type_emoji} **Discovery Source: {source_name}**\n\n'
            response += f'**Type:** {source_type.upper()}\n'
            response += f"**Status:** {'✅ Active' if source.get('enabled', True) else '❌ Disabled'}\n\n"

            # Configuration details
            response += '**Configuration:**\n'

            # Type-specific details
            if source_type == 'arxiv' and 'categories' in source:
                response += f"- Categories: {', '.join(source['categories'])}\n"
            elif source_type == 'pubmed' and 'query' in source:
                response += f"- Query: {source['query']}\n"
            elif source_type == 'crossref' and 'query' in source:
                response += f"- Query: {source['query']}\n"

            # Common fields
            if 'keywords' in source and source['keywords']:
                response += f"- Keywords: {', '.join(source['keywords'][:10])}"
                if len(source['keywords']) > 10:
                    response += f' (+{len(source["keywords"])-10} more)'
                response += '\n'

            if 'max_results' in source:
                response += f"- Max Results: {source['max_results']}\n"

            if 'min_quality_score' in source:
                response += f"- Min Quality Score: {source['min_quality_score']}\n"

            # Recent activity
            if 'last_run' in source:
                response += f"\n**Last Run:** {source['last_run']}\n"
            if 'articles_found' in source:
                response += f"**Articles Found:** {source['articles_found']}\n"

            return MCPToolCallResult(content=response, is_error=False)

        except Exception as e:
            return MCPToolCallResult(
                content=f'Error getting discovery source: {str(e)}', is_error=True
            )


class RunDiscoveryMCPTool(MCPTool):
    """MCP tool for manually triggering a discovery source."""

    name = 'run_discovery'
    description = (
        'Manually trigger a discovery source to search for new articles. '
        'Normally sources run automatically, but this allows immediate execution.'
    )

    input_schema = {
        'type': 'object',
        'properties': {
            'source_name': {
                'type': 'string',
                'description': 'Name of the discovery source to run',
            },
            'test_mode': {
                'type': 'boolean',
                'description': 'Run in test mode (preview results without saving)',
                'default': False,
            },
            'limit': {
                'type': 'integer',
                'description': 'Override the max results for this run',
            },
        },
        'required': ['source_name'],
    }

    def run(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Run a discovery source."""
        try:
            source_name = arguments['source_name']
            test_mode = arguments.get('test_mode', False)
            limit = arguments.get('limit')

            # Get the source
            source = self.service_manager.discovery.get_source(source_name)
            if not source:
                return MCPToolCallResult(
                    content=f'Discovery source "{source_name}" not found.', is_error=True
                )

            # Override limit if specified
            if limit:
                source = source.copy()
                source['max_results'] = limit

            # Run discovery
            if test_mode:
                response = f"🔍 **Test Run: {source_name}**\n\n"
                response += "Running in test mode - results will NOT be saved.\n\n"
            else:
                response = f"🚀 **Running Discovery: {source_name}**\n\n"

            try:
                articles = self.service_manager.discovery.run_discovery(
                    source, save_results=not test_mode
                )

                if not articles:
                    response += "No new articles found matching the criteria."
                else:
                    response += f"Found {len(articles)} articles:\n\n"
                    
                    # Show first 5 articles
                    for i, article in enumerate(articles[:5]):
                        response += f"{i+1}. **{article.get('title', 'Untitled')}**\n"
                        if article.get('authors'):
                            authors = article['authors'][:3]
                            response += f"   By: {', '.join(authors)}"
                            if len(article['authors']) > 3:
                                response += f" et al."
                            response += "\n"
                        if article.get('publication_date'):
                            response += f"   Date: {article['publication_date']}\n"
                        response += "\n"

                    if len(articles) > 5:
                        response += f"... and {len(articles) - 5} more articles.\n"

                    if not test_mode:
                        response += "\n✅ Articles have been saved to the knowledge base."

                return MCPToolCallResult(content=response, is_error=False)

            except Exception as e:
                return MCPToolCallResult(
                    content=f'Error running discovery: {str(e)}', is_error=True
                )

        except Exception as e:
            return MCPToolCallResult(
                content=f'Error in run_discovery: {str(e)}', is_error=True
            )


class DeleteDiscoverySourceMCPTool(SourceNameTool):
    """MCP tool for deleting a discovery source."""

    name = 'delete_discovery_source'
    description = 'Delete a discovery source configuration. This action cannot be undone.'

    def run_with_source_name(self, source_name: str) -> MCPToolCallResult:
        """Delete a discovery source."""
        try:
            # Check if source exists
            source = self.service_manager.discovery.get_source(source_name)
            if not source:
                return MCPToolCallResult(
                    content=f'Discovery source "{source_name}" not found.', is_error=True
                )

            # Delete the source
            self.service_manager.discovery.delete_source(source_name)

            response = f"🗑️ **Discovery Source Deleted**\n\n"
            response += f"Successfully deleted discovery source: **{source_name}**\n"
            response += f"Type: {source.get('type', 'unknown').upper()}\n\n"
            response += "The source configuration has been permanently removed."

            return MCPToolCallResult(content=response, is_error=False)

        except Exception as e:
            return MCPToolCallResult(
                content=f'Error deleting discovery source: {str(e)}', is_error=True
            )
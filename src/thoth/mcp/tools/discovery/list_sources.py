"""List discovery sources tool."""

from typing import Any

from thoth.mcp.base_tools import MCPToolCallResult, NoInputTool


class ListDiscoverySourcesMCPTool(NoInputTool):
    """MCP tool for listing all discovery sources."""

    name = 'list_discovery_sources'
    description = (
        'List all configured automatic discovery sources and their status. '
        'Returns a comprehensive overview of all active discovery configurations.'
    )

    def run_without_input(self) -> MCPToolCallResult:
        """List all discovery sources without requiring input."""
        try:
            sources = self.service_manager.discovery.list_sources()

            if not sources:
                return MCPToolCallResult(
                    content='No discovery sources configured yet.\n\n'
                    'You can create sources using:\n'
                    '- `create_arxiv_source` for ArXiv preprint discovery\n'
                    '- `create_pubmed_source` for biomedical literature\n'
                    '- `create_crossref_source` for DOI-based discovery\n'
                    '- `create_openalex_source` for open access papers\n'
                    '- `create_biorxiv_source` for biology preprints',
                    is_error=False,
                )

            # Format sources into readable text
            response = '📚 **Active Discovery Sources**\n\n'

            # Group by source type
            by_type = {}
            for source in sources:
                source_type = source.get('type', 'unknown')
                if source_type not in by_type:
                    by_type[source_type] = []
                by_type[source_type].append(source)

            # Display each type
            for source_type, type_sources in sorted(by_type.items()):
                type_emoji = {
                    'arxiv': '📄',
                    'pubmed': '🧬',
                    'crossref': '🔗',
                    'openalex': '📖',
                    'biorxiv': '🧪',
                    'scraper': '🌐',
                }.get(source_type, '📝')

                response += f'{type_emoji} **{source_type.upper()} Sources**\n'

                for source in type_sources:
                    response += f"\n**Name:** {source.get('name', 'Unnamed')}\n"

                    # Show configuration details
                    if 'categories' in source:
                        cats = source['categories']
                        if isinstance(cats, list):
                            response += f"- Categories: {', '.join(cats)}\n"

                    if 'keywords' in source:
                        kw = source['keywords']
                        if isinstance(kw, list) and kw:
                            response += f"- Keywords: {', '.join(kw[:5])}"
                            if len(kw) > 5:
                                response += f' (+{len(kw)-5} more)'
                            response += '\n'

                    if 'query' in source:
                        response += f"- Query: {source['query']}\n"

                    # Show status
                    enabled = source.get('enabled', True)
                    status = '✅ Active' if enabled else '❌ Disabled'
                    response += f"- Status: {status}\n"

                response += '\n'

            # Add summary
            total = len(sources)
            active = sum(1 for s in sources if s.get('enabled', True))
            response += f'**Summary:** {total} sources configured ({active} active)'

            return MCPToolCallResult(content=response, is_error=False)

        except Exception as e:
            return MCPToolCallResult(
                content=f'Error listing discovery sources: {str(e)}', is_error=True
            )
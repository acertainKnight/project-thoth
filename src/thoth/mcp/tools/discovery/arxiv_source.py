"""ArXiv discovery source tool."""

from typing import Any

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult


class CreateArxivSourceMCPTool(MCPTool):
    """MCP tool for creating an ArXiv discovery source."""

    name = 'create_arxiv_source'
    description = (
        'Create an automated ArXiv paper discovery source. '
        'The system will periodically search ArXiv for new papers matching your criteria.'
    )

    input_schema = {
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'description': 'Unique name for this discovery source',
            },
            'categories': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'ArXiv categories to monitor (e.g., cs.AI, cs.LG, math.PR)',
            },
            'keywords': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Keywords to search for in paper titles/abstracts',
            },
            'authors': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Author names to track (optional)',
            },
            'max_results': {
                'type': 'integer',
                'description': 'Maximum papers to retrieve per search (default: 50)',
                'default': 50,
            },
            'min_quality_score': {
                'type': 'number',
                'description': 'Minimum relevance score (0-1) to include papers',
                'default': 0.5,
            },
            'enabled': {
                'type': 'boolean',
                'description': 'Whether to enable this source immediately',
                'default': True,
            },
        },
        'required': ['name', 'categories'],
    }

    def run(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create an ArXiv discovery source."""
        try:
            # Validate categories
            categories = arguments['categories']
            valid_prefixes = [
                'astro-ph', 'cond-mat', 'cs', 'econ', 'eess', 'gr-qc',
                'hep-ex', 'hep-lat', 'hep-ph', 'hep-th', 'math', 'math-ph',
                'nlin', 'nucl-ex', 'nucl-th', 'physics', 'q-bio', 'q-fin',
                'quant-ph', 'stat'
            ]
            
            for cat in categories:
                if not any(cat.startswith(prefix) for prefix in valid_prefixes):
                    return MCPToolCallResult(
                        content=f'Invalid ArXiv category: {cat}. '
                        f'Must start with one of: {", ".join(valid_prefixes)}',
                        is_error=True,
                    )

            # Create the discovery source
            config = {
                'type': 'arxiv',
                'name': arguments['name'],
                'categories': categories,
                'keywords': arguments.get('keywords', []),
                'authors': arguments.get('authors', []),
                'max_results': arguments.get('max_results', 50),
                'min_quality_score': arguments.get('min_quality_score', 0.5),
                'enabled': arguments.get('enabled', True),
            }

            # Save the source
            self.service_manager.discovery.create_source(config)

            # Format response
            response = f"✅ **ArXiv Discovery Source Created**\n\n"
            response += f"**Name:** {config['name']}\n"
            response += f"**Categories:** {', '.join(config['categories'])}\n"
            
            if config['keywords']:
                response += f"**Keywords:** {', '.join(config['keywords'])}\n"
            
            if config['authors']:
                response += f"**Authors:** {', '.join(config['authors'])}\n"
            
            response += f"**Max Results:** {config['max_results']}\n"
            response += f"**Min Quality Score:** {config['min_quality_score']}\n"
            response += f"**Status:** {'✅ Active' if config['enabled'] else '❌ Disabled'}\n\n"
            
            response += "The system will now periodically check ArXiv for new papers matching these criteria."

            return MCPToolCallResult(content=response, is_error=False)

        except ValueError as e:
            return MCPToolCallResult(
                content=f'Invalid configuration: {str(e)}', is_error=True
            )
        except Exception as e:
            return MCPToolCallResult(
                content=f'Error creating ArXiv source: {str(e)}', is_error=True
            )
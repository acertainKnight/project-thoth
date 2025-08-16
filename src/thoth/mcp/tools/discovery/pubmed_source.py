"""PubMed discovery source tool."""

from typing import Any

from thoth.mcp.base_tools import MCPToolCallResult
from thoth.mcp.tools.discovery.base import CreateSourceBaseTool


class CreatePubmedSourceMCPTool(CreateSourceBaseTool):
    """MCP tool for creating a PubMed discovery source."""

    name = 'create_pubmed_source'
    description = (
        'Create an automated PubMed/biomedical literature discovery source. '
        'The system will periodically search PubMed for new papers matching your criteria.'
    )
    
    source_type = 'pubmed'
    source_emoji = '🧬'

    input_schema = {
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'description': 'Unique name for this discovery source',
            },
            'query': {
                'type': 'string',
                'description': 'PubMed search query (uses standard PubMed search syntax)',
            },
            'keywords': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Additional keywords to filter results',
            },
            'mesh_terms': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'MeSH (Medical Subject Headings) terms to include',
            },
            'publication_types': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Publication types to include (e.g., "Clinical Trial", "Review")',
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
        'required': ['name', 'query'],
    }

    def run(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create a PubMed discovery source."""
        # Build configuration
        config = {
            'type': 'pubmed',
            'name': arguments['name'],
            'query': arguments['query'],
            'keywords': arguments.get('keywords', []),
            'mesh_terms': arguments.get('mesh_terms', []),
            'publication_types': arguments.get('publication_types', []),
            'max_results': arguments.get('max_results', 50),
            'min_quality_score': arguments.get('min_quality_score', 0.5),
            'enabled': arguments.get('enabled', True),
        }

        return self.create_source(config)
    
    def format_source_details(self, config: dict[str, Any]) -> str:
        """Format PubMed-specific details."""
        details = f"**Query:** {config['query']}\n"
        
        if config.get('keywords'):
            details += f"**Keywords:** {', '.join(config['keywords'])}\n"
        
        if config.get('mesh_terms'):
            details += f"**MeSH Terms:** {', '.join(config['mesh_terms'])}\n"
        
        if config.get('publication_types'):
            details += f"**Publication Types:** {', '.join(config['publication_types'])}\n"
        
        return details
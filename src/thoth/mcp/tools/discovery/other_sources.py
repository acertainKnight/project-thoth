"""Other discovery source creation tools."""

from typing import Any

from thoth.mcp.base_tools import MCPToolCallResult
from thoth.mcp.tools.discovery.base import CreateSourceBaseTool


class CreateCrossrefSourceMCPTool(CreateSourceBaseTool):
    """MCP tool for creating a Crossref discovery source."""

    name = 'create_crossref_source'
    description = (
        'Create a Crossref discovery source for finding papers by DOI metadata. '
        'Searches across publishers using Crossref\'s comprehensive database.'
    )
    
    source_type = 'crossref'
    source_emoji = '🔗'

    input_schema = {
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'description': 'Unique name for this discovery source',
            },
            'query': {
                'type': 'string',
                'description': 'General search query for Crossref',
            },
            'filters': {
                'type': 'object',
                'description': 'Crossref-specific filters',
                'properties': {
                    'from_pub_date': {'type': 'string', 'description': 'Start date (YYYY-MM-DD)'},
                    'until_pub_date': {'type': 'string', 'description': 'End date (YYYY-MM-DD)'},
                    'has_full_text': {'type': 'boolean', 'description': 'Only papers with full text'},
                    'type': {'type': 'string', 'description': 'Publication type (e.g., journal-article)'},
                },
            },
            'max_results': {
                'type': 'integer',
                'description': 'Maximum papers to retrieve per search',
                'default': 50,
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
        """Create a Crossref discovery source."""
        config = {
            'type': 'crossref',
            'name': arguments['name'],
            'query': arguments['query'],
            'filters': arguments.get('filters', {}),
            'max_results': arguments.get('max_results', 50),
            'enabled': arguments.get('enabled', True),
        }
        return self.create_source(config)
    
    def format_source_details(self, config: dict[str, Any]) -> str:
        """Format Crossref-specific details."""
        details = f"**Query:** {config['query']}\n"
        
        if config.get('filters'):
            filters = config['filters']
            if filters.get('from_pub_date'):
                details += f"**From Date:** {filters['from_pub_date']}\n"
            if filters.get('until_pub_date'):
                details += f"**Until Date:** {filters['until_pub_date']}\n"
            if filters.get('has_full_text'):
                details += "**Full Text Only:** Yes\n"
            if filters.get('type'):
                details += f"**Publication Type:** {filters['type']}\n"
        
        return details


class CreateOpenalexSourceMCPTool(CreateSourceBaseTool):
    """MCP tool for creating an OpenAlex discovery source."""

    name = 'create_openalex_source'
    description = (
        'Create an OpenAlex discovery source for open access papers. '
        'OpenAlex provides free access to a comprehensive catalog of scholarly works.'
    )
    
    source_type = 'openalex'
    source_emoji = '📖'

    input_schema = {
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'description': 'Unique name for this discovery source',
            },
            'search_filter': {
                'type': 'string',
                'description': 'OpenAlex filter string (e.g., "display_name.search:machine learning")',
            },
            'keywords': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Keywords to search for',
            },
            'institutions': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Filter by institution names',
            },
            'open_access_only': {
                'type': 'boolean',
                'description': 'Only include open access papers',
                'default': False,
            },
            'max_results': {
                'type': 'integer',
                'description': 'Maximum papers to retrieve per search',
                'default': 50,
            },
            'enabled': {
                'type': 'boolean',
                'description': 'Whether to enable this source immediately',
                'default': True,
            },
        },
        'required': ['name'],
    }

    def run(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create an OpenAlex discovery source."""
        config = {
            'type': 'openalex',
            'name': arguments['name'],
            'search_filter': arguments.get('search_filter', ''),
            'keywords': arguments.get('keywords', []),
            'institutions': arguments.get('institutions', []),
            'open_access_only': arguments.get('open_access_only', False),
            'max_results': arguments.get('max_results', 50),
            'enabled': arguments.get('enabled', True),
        }
        return self.create_source(config)
    
    def format_source_details(self, config: dict[str, Any]) -> str:
        """Format OpenAlex-specific details."""
        details = ""
        
        if config.get('search_filter'):
            details += f"**Filter:** {config['search_filter']}\n"
        
        if config.get('keywords'):
            details += f"**Keywords:** {', '.join(config['keywords'])}\n"
        
        if config.get('institutions'):
            details += f"**Institutions:** {', '.join(config['institutions'])}\n"
        
        if config.get('open_access_only'):
            details += "**Open Access Only:** Yes\n"
        
        return details


class CreateBiorxivSourceMCPTool(CreateSourceBaseTool):
    """MCP tool for creating a BioRxiv discovery source."""

    name = 'create_biorxiv_source'
    description = (
        'Create a BioRxiv discovery source for biology preprints. '
        'BioRxiv hosts preprints in the life sciences before peer review.'
    )
    
    source_type = 'biorxiv'
    source_emoji = '🧪'

    input_schema = {
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
                'description': 'Unique name for this discovery source',
            },
            'server': {
                'type': 'string',
                'enum': ['biorxiv', 'medrxiv'],
                'description': 'Which server to search (biorxiv or medrxiv)',
                'default': 'biorxiv',
            },
            'category': {
                'type': 'string',
                'description': 'Subject category (e.g., neuroscience, genomics)',
            },
            'keywords': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Keywords to search for',
            },
            'from_date': {
                'type': 'string',
                'description': 'Start date for search (YYYY-MM-DD)',
            },
            'max_results': {
                'type': 'integer',
                'description': 'Maximum papers to retrieve per search',
                'default': 50,
            },
            'enabled': {
                'type': 'boolean',
                'description': 'Whether to enable this source immediately',
                'default': True,
            },
        },
        'required': ['name'],
    }

    def run(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create a BioRxiv discovery source."""
        config = {
            'type': 'biorxiv',
            'name': arguments['name'],
            'server': arguments.get('server', 'biorxiv'),
            'category': arguments.get('category', ''),
            'keywords': arguments.get('keywords', []),
            'from_date': arguments.get('from_date', ''),
            'max_results': arguments.get('max_results', 50),
            'enabled': arguments.get('enabled', True),
        }
        return self.create_source(config)
    
    def format_source_details(self, config: dict[str, Any]) -> str:
        """Format BioRxiv-specific details."""
        details = f"**Server:** {config.get('server', 'biorxiv').upper()}\n"
        
        if config.get('category'):
            details += f"**Category:** {config['category']}\n"
        
        if config.get('keywords'):
            details += f"**Keywords:** {', '.join(config['keywords'])}\n"
        
        if config.get('from_date'):
            details += f"**From Date:** {config['from_date']}\n"
        
        return details
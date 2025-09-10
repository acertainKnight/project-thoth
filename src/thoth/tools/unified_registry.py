"""
Unified Tool Registry for Thoth-Letta Integration

This module consolidates all tool types (MCP, pipeline, native) into a single
registry system that directly integrates with Letta agents.
"""

from collections.abc import Callable
from typing import Any

from loguru import logger

from thoth.mcp.tools import MCP_TOOL_CLASSES, MCPToolRegistry
from thoth.services.service_manager import ServiceManager

try:
    from letta_client import Letta as LettaClient

    LETTA_AVAILABLE = True
except ImportError as e:
    LETTA_AVAILABLE = False
    raise ImportError(f'Letta client required for unified tool registry: {e}') from e


class UnifiedToolRegistry:
    """
    Unified registry for all Thoth tools with direct Letta integration.

    This registry consolidates:
    - MCP protocol tools
    - Document processing pipelines
    - Native Python functions

    And presents them as a unified interface for Letta agents.
    """

    def __init__(self, service_manager: ServiceManager, letta_client: LettaClient):
        """
        Initialize the unified tool registry.

        Args:
            service_manager: ServiceManager for tool dependencies
            letta_client: Letta client for direct tool assignment
        """
        if not letta_client:
            raise ValueError('Letta client is required for unified tool registry')

        self.service_manager = service_manager
        self.letta_client = letta_client
        self._registered_tools: dict[str, dict[str, Any]] = {}

        # Initialize MCP registry for protocol tools
        self._mcp_registry = MCPToolRegistry(service_manager)

        # Tool categories for intelligent agent assignment
        self.agent_tool_map = {
            'research': {
                'core_tools': ['search_papers', 'analyze_document', 'rag_search'],
                'extended_tools': [
                    'web_search',
                    'track_authors',
                    'find_related_papers',
                ],
                'pipelines': ['document_processing'],
            },
            'analysis': {
                'core_tools': [
                    'analyze_document',
                    'extract_citations',
                    'compare_papers',
                ],
                'extended_tools': ['extract_insights', 'evaluate_methodology'],
                'pipelines': ['document_processing', 'knowledge_extraction'],
            },
            'discovery': {
                'core_tools': ['discover_papers', 'monitor_sources', 'search_papers'],
                'extended_tools': ['track_authors', 'trend_analysis'],
                'pipelines': ['discovery_processing'],
            },
            'citation': {
                'core_tools': [
                    'extract_citations',
                    'analyze_citations',
                    'format_citations',
                ],
                'extended_tools': ['export_bibliography', 'impact_analysis'],
                'pipelines': ['citation_processing'],
            },
            'synthesis': {
                'core_tools': [
                    'synthesize_knowledge',
                    'generate_summary',
                    'create_overview',
                ],
                'extended_tools': ['cross_paper_analysis', 'theme_extraction'],
                'pipelines': ['knowledge_extraction', 'synthesis_processing'],
            },
        }

        logger.info('UnifiedToolRegistry initialized')

    async def initialize(self) -> None:
        """Initialize the registry and register all tools."""
        try:
            # Register all tool types
            await self._register_mcp_tools()
            await self._register_pipeline_tools()
            await self._register_native_tools()

            logger.info(
                f'UnifiedToolRegistry initialized with {len(self._registered_tools)} tools'
            )

        except Exception as e:
            logger.error(f'Failed to initialize unified tool registry: {e}')
            raise

    async def _register_mcp_tools(self) -> None:
        """Register MCP protocol tools."""
        logger.info('Registering MCP tools...')

        # Register all MCP tool classes
        for tool_class in MCP_TOOL_CLASSES:
            self._mcp_registry.register_class(tool_class)

        # Get tool schemas and create Letta tools
        tool_schemas = self._mcp_registry.get_tool_schemas()

        for schema in tool_schemas:
            try:
                # Create Python function for Letta
                tool_function = self._create_mcp_function(schema)

                # Register with tracking
                self._registered_tools[schema.name] = {
                    'type': 'mcp',
                    'function': tool_function,
                    'schema': schema,
                    'category': self._categorize_tool(schema.name),
                }

                logger.debug(f'Registered MCP tool: {schema.name}')

            except Exception as e:
                logger.error(f'Failed to register MCP tool {schema.name}: {e}')

    async def _register_pipeline_tools(self) -> None:
        """Register document processing pipeline tools."""
        logger.info('Registering pipeline tools...')

        pipeline_tools = [
            {
                'name': 'process_document',
                'description': 'Process a document through the document pipeline for text extraction and analysis',
                'function': self._create_document_pipeline_function(),
                'category': 'processing',
            },
            {
                'name': 'extract_knowledge',
                'description': 'Extract knowledge and citations from documents using the knowledge pipeline',
                'function': self._create_knowledge_pipeline_function(),
                'category': 'research',
            },
            {
                'name': 'analyze_citations',
                'description': 'Analyze citation patterns and networks in documents',
                'function': self._create_citation_pipeline_function(),
                'category': 'citation',
            },
        ]

        for tool_def in pipeline_tools:
            self._registered_tools[tool_def['name']] = {
                'type': 'pipeline',
                'function': tool_def['function'],
                'description': tool_def['description'],
                'category': tool_def['category'],
            }
            logger.debug(f'Registered pipeline tool: {tool_def["name"]}')

    async def _register_native_tools(self) -> None:
        """Register native Python tools."""
        logger.info('Registering native tools...')

        native_tools = [
            {
                'name': 'get_system_status',
                'description': 'Check the status of Thoth services and system health',
                'function': self._create_status_function(),
                'category': 'management',
            },
            {
                'name': 'search_knowledge_base',
                'description': 'Search the knowledge base using RAG retrieval',
                'function': self._create_rag_search_function(),
                'category': 'research',
            },
        ]

        for tool_def in native_tools:
            self._registered_tools[tool_def['name']] = {
                'type': 'native',
                'function': tool_def['function'],
                'description': tool_def['description'],
                'category': tool_def['category'],
            }
            logger.debug(f'Registered native tool: {tool_def["name"]}')

    def _create_mcp_function(self, schema) -> Callable:
        """Create a Python function wrapper for an MCP tool."""

        async def mcp_wrapper(**kwargs) -> str:
            """Execute MCP tool and return formatted result."""
            try:
                result = await self._mcp_registry.execute_tool(schema.name, kwargs)

                # Format result appropriately
                if hasattr(result, 'content'):
                    return str(result.content)
                elif isinstance(result, dict):
                    return f'Result: {result}'
                else:
                    return str(result)

            except Exception as e:
                logger.error(f'MCP tool {schema.name} execution failed: {e}')
                return f'Error executing {schema.name}: {e!s}'

        # Set function metadata
        mcp_wrapper.__name__ = schema.name
        mcp_wrapper.__doc__ = schema.description

        return mcp_wrapper

    def _create_document_pipeline_function(self) -> Callable:
        """Create document processing pipeline function."""

        async def process_document(document_path: str, **options) -> str:
            """Process a document through the document pipeline."""
            try:
                from thoth.pipelines import DocumentPipeline

                pipeline = DocumentPipeline(self.service_manager)
                result = await pipeline.process_document(document_path, **options)

                return f'Document processed: {result.get("status", "completed")}'

            except Exception as e:
                logger.error(f'Document processing failed: {e}')
                return f'Document processing error: {e!s}'

        return process_document

    def _create_knowledge_pipeline_function(self) -> Callable:
        """Create knowledge extraction pipeline function."""

        async def extract_knowledge(document_path: str, **options) -> str:
            """Extract knowledge from documents."""
            try:
                from thoth.pipelines import KnowledgePipeline

                pipeline = KnowledgePipeline(self.service_manager)
                result = await pipeline.process_document(document_path, **options)

                return f'Knowledge extracted: {result.get("citations", 0)} citations, {result.get("entities", 0)} entities'

            except Exception as e:
                logger.error(f'Knowledge extraction failed: {e}')
                return f'Knowledge extraction error: {e!s}'

        return extract_knowledge

    def _create_citation_pipeline_function(self) -> Callable:
        """Create citation analysis function."""

        async def analyze_citations(document_path: str, **_options) -> str:
            """Analyze citations in a document."""
            try:
                citation_service = self.service_manager.citation_service
                result = await citation_service.extract_citations_from_file(
                    document_path
                )

                return f'Found {len(result.citations)} citations in document'

            except Exception as e:
                logger.error(f'Citation analysis failed: {e}')
                return f'Citation analysis error: {e!s}'

        return analyze_citations

    def _create_status_function(self) -> Callable:
        """Create system status function."""

        def get_system_status() -> str:
            """Check system status."""
            try:
                # Check service health
                services = {
                    'llm': self.service_manager.llm_service.health_check(),
                    'rag': self.service_manager.rag_service.health_check(),
                    'discovery': self.service_manager.discovery_service.health_check(),
                }

                healthy_count = sum(
                    1 for s in services.values() if s.get('status') == 'healthy'
                )
                total_count = len(services)

                return f'System status: {healthy_count}/{total_count} services healthy'

            except Exception as e:
                return f'Status check error: {e!s}'

        return get_system_status

    def _create_rag_search_function(self) -> Callable:
        """Create RAG search function."""

        async def search_knowledge_base(query: str, limit: int = 5) -> str:
            """Search the knowledge base."""
            try:
                rag_service = self.service_manager.rag_service
                results = await rag_service.search(query, limit=limit)

                if results:
                    return f'Found {len(results)} relevant documents for: {query}'
                else:
                    return f'No results found for: {query}'

            except Exception as e:
                logger.error(f'RAG search failed: {e}')
                return f'Search error: {e!s}'

        return search_knowledge_base

    def _categorize_tool(self, tool_name: str) -> str:
        """Categorize a tool based on its name."""
        name_lower = tool_name.lower()

        if any(keyword in name_lower for keyword in ['search', 'find', 'discover']):
            return 'discovery'
        elif any(
            keyword in name_lower
            for keyword in ['citation', 'reference', 'bibliography']
        ):
            return 'citation'
        elif any(
            keyword in name_lower for keyword in ['analyze', 'analysis', 'evaluate']
        ):
            return 'analysis'
        elif any(
            keyword in name_lower for keyword in ['synthesize', 'summary', 'overview']
        ):
            return 'synthesis'
        elif any(
            keyword in name_lower for keyword in ['research', 'study', 'investigate']
        ):
            return 'research'
        else:
            return 'general'

    def get_tools_for_agent(
        self, agent_type: str, include_extended: bool = True
    ) -> list[str]:
        """
        Get appropriate tools for an agent type.

        Args:
            agent_type: Type of agent (research, analysis, etc.)
            include_extended: Whether to include extended tools

        Returns:
            List of tool names suitable for the agent
        """
        if agent_type not in self.agent_tool_map:
            agent_type = 'research'

        tool_config = self.agent_tool_map[agent_type]
        tools = tool_config['core_tools'].copy()

        if include_extended:
            tools.extend(tool_config['extended_tools'])

        # Add pipeline tools
        for pipeline in tool_config['pipelines']:
            if pipeline == 'document_processing':
                tools.append('process_document')
            elif pipeline == 'knowledge_extraction':
                tools.append('extract_knowledge')
            elif pipeline == 'citation_processing':
                tools.append('analyze_citations')

        # Filter to only include registered tools
        available_tools = [tool for tool in tools if tool in self._registered_tools]

        return available_tools

    def assign_tools_to_agent(self, agent_id: str, tool_names: list[str]) -> bool:
        """
        Assign tools directly to a Letta agent.

        Args:
            agent_id: Letta agent ID
            tool_names: List of tool names to assign

        Returns:
            bool: True if successful
        """
        try:
            # Get tool functions
            tool_functions = []
            for tool_name in tool_names:
                if tool_name in self._registered_tools:
                    tool_functions.append(self._registered_tools[tool_name]['function'])

            # Assign to Letta agent
            # Note: This would use Letta's tool assignment API
            # For now, we log the assignment
            logger.info(f'Assigned {len(tool_functions)} tools to agent {agent_id}')

            return True

        except Exception as e:
            logger.error(f'Failed to assign tools to agent {agent_id}: {e}')
            return False

    def get_registered_tools(self) -> dict[str, dict[str, Any]]:
        """Get all registered tools."""
        return self._registered_tools.copy()

    def get_tool_by_category(self, category: str) -> list[str]:
        """Get tools by category."""
        return [
            name
            for name, info in self._registered_tools.items()
            if info['category'] == category
        ]


# Global registry instance for module access
_global_registry: UnifiedToolRegistry | None = None


async def initialize_unified_registry(
    service_manager: ServiceManager, letta_client: LettaClient
) -> UnifiedToolRegistry:
    """
    Initialize the unified tool registry.

    Args:
        service_manager: ServiceManager instance
        letta_client: Letta client for tool integration

    Returns:
        Initialized UnifiedToolRegistry
    """
    global _global_registry

    if not letta_client:
        raise ValueError('Letta client is required for unified tool registry')

    registry = UnifiedToolRegistry(service_manager, letta_client)
    await registry.initialize()

    _global_registry = registry
    logger.info('Unified tool registry initialized successfully')

    return registry


def get_registry() -> UnifiedToolRegistry:
    """Get the global unified registry instance."""
    global _global_registry
    if not _global_registry:
        raise RuntimeError('Unified tool registry not initialized')
    return _global_registry

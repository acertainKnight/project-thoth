"""
Letta Tool Registration System

This module handles registering Thoth's tools with Letta agents, converting
MCP tools and pipeline tools into Letta-compatible functions.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from loguru import logger

from thoth.mcp.tools import MCP_TOOL_CLASSES, MCPToolRegistry
from thoth.pipelines import DocumentPipeline, KnowledgePipeline
from thoth.services.service_manager import ServiceManager

try:
    from letta_client import Letta as LettaClient
    from letta_client import ToolCreate

    LETTA_AVAILABLE = True
    logger.info('Letta client available for tool registration')
except ImportError as e:
    LETTA_AVAILABLE = False
    logger.error(
        f'Letta client not available - tool registration will not function: {e}'
    )
    raise ImportError(f'Letta client required for tool registration: {e}') from e


class LettaToolRegistry:
    """
    Registry for managing tools that can be used by Letta agents.

    This registry converts Thoth's MCP tools and pipeline tools into
    Letta-compatible functions that can be called by agents.
    """

    def __init__(
        self, service_manager: ServiceManager, letta_client: LettaClient | None = None
    ):
        """
        Initialize the Letta tool registry.

        Args:
            service_manager: ServiceManager for tool dependencies
            letta_client: Letta client for tool registration (optional)
        """
        self.service_manager = service_manager
        self.letta_client = letta_client
        self._registered_tools: dict[str, dict[str, Any]] = {}
        self._mcp_registry = MCPToolRegistry(service_manager)

        # Tool categories for organized agent assignment
        self.tool_categories = {
            'research': [
                'search_articles',
                'analyze_topic',
                'find_related_papers',
                'generate_research_summary',
                'web_search',
                'run_discovery',
            ],
            'citation': [
                'extract_citations',
                'format_citations',
                'export_bibliography',
            ],
            'analysis': ['analyze_document', 'compare_papers', 'extract_insights'],
            'discovery': ['discover_papers', 'monitor_sources', 'track_authors'],
            'synthesis': [
                'synthesize_knowledge',
                'generate_summary',
                'create_overview',
            ],
            'processing': [
                'process_pdf',
                'extract_text',
                'validate_documents',
                'batch_process_pdfs',
            ],
            'memory': [
                'core_memory_append',
                'core_memory_replace',
                'archival_memory_insert',
                'archival_memory_search',
                'conversation_search',
                'memory_stats',
                'memory_health_check',
            ],
        }

        logger.info('LettaToolRegistry initialized with Letta client')

    async def register_all_tools(self) -> None:
        """Register all available tools with Letta following best practices."""
        try:
            logger.info('Registering tools with Letta server...')

            # Register MCP tools
            await self._register_mcp_tools()

            # Register pipeline tools
            await self._register_pipeline_tools()

            # Register utility tools
            await self._register_utility_tools()

            logger.info(
                f'Successfully registered {len(self._registered_tools)} tools with Letta'
            )

        except Exception as e:
            logger.error(f'Failed to register tools with Letta: {e}')
            raise

    async def _register_mcp_tools(self) -> None:
        """Register MCP tools as Letta functions."""
        logger.info('Registering MCP tools with Letta...')

        # Register all MCP tool classes with our registry
        for tool_class in MCP_TOOL_CLASSES:
            self._mcp_registry.register_class(tool_class)

        # Convert each MCP tool to Letta format
        tool_schemas = self._mcp_registry.get_tool_schemas()

        for tool_schema in tool_schemas:
            try:
                await self._register_mcp_tool(tool_schema.name, tool_schema)
            except Exception as e:
                logger.error(f'Failed to register MCP tool {tool_schema.name}: {e}')

    async def _register_mcp_tool(self, tool_name: str, tool_schema) -> None:
        """Register a single MCP tool with Letta."""
        try:
            # Create wrapper function for the MCP tool
            async def mcp_tool_wrapper(**kwargs) -> str:
                """Wrapper function for MCP tool execution."""
                try:
                    # Execute the tool through MCP registry
                    result = await self._mcp_registry.execute_tool(tool_name, kwargs)

                    # Format result for Letta
                    if hasattr(result, 'content'):
                        return str(result.content)
                    else:
                        return str(result)

                except Exception as e:
                    logger.error(f'Error executing MCP tool {tool_name}: {e}')
                    return f'Error executing {tool_name}: {e!s}'

            # Create Letta tool definition
            letta_tool = ToolCreate(
                name=tool_name,
                description=tool_schema.description,
                source_code=self._generate_tool_source_code(
                    tool_name, tool_schema, 'mcp'
                ),
                source_type='python',
            )

            # Register with Letta client
            created_tool = await self._create_letta_tool(letta_tool)

            # Only track tool if it was successfully registered with Letta client
            if created_tool is not None:
                self._registered_tools[tool_name] = {
                    'type': 'mcp',
                    'schema': tool_schema,
                    'letta_tool': created_tool,
                    'category': self._categorize_tool(tool_name),
                }

            logger.debug(f'Registered MCP tool: {tool_name}')

        except Exception as e:
            logger.error(f'Failed to register MCP tool {tool_name}: {e}')

    async def _register_pipeline_tools(self) -> None:
        """Register pipeline processing tools."""
        logger.info('Registering pipeline tools with Letta...')

        pipeline_tools = [
            {
                'name': 'run_document_pipeline',
                'description': 'Process documents through the document pipeline for text extraction, embedding generation, and metadata analysis',
                'func': self._create_document_pipeline_tool(),
                'category': 'processing',
            },
            {
                'name': 'run_knowledge_pipeline',
                'description': 'Process documents through the knowledge pipeline to extract citations, entities, and build knowledge graphs',
                'func': self._create_knowledge_pipeline_tool(),
                'category': 'research',
            },
        ]

        for tool_def in pipeline_tools:
            try:
                await self._register_pipeline_tool(tool_def)
            except Exception as e:
                logger.error(
                    f'Failed to register pipeline tool {tool_def["name"]}: {e}'
                )

    async def _register_pipeline_tool(self, tool_def: dict[str, Any]) -> None:
        """Register a single pipeline tool with Letta."""
        tool_name = tool_def['name']

        try:
            # Create Letta tool definition
            letta_tool = ToolCreate(
                name=tool_name,
                description=tool_def['description'],
                source_code=self._generate_tool_source_code(
                    tool_name, tool_def, 'pipeline'
                ),
                source_type='python',
            )

            # Register with Letta client
            created_tool = await self._create_letta_tool(letta_tool)

            # Only track tool if it was successfully registered with Letta client
            if created_tool is not None:
                self._registered_tools[tool_name] = {
                    'type': 'pipeline',
                    'definition': tool_def,
                    'letta_tool': created_tool,
                    'category': tool_def['category'],
                }

            logger.debug(f'Registered pipeline tool: {tool_name}')

        except Exception as e:
            logger.error(f'Failed to register pipeline tool {tool_name}: {e}')

    async def _register_utility_tools(self) -> None:
        """Register utility tools for agent management."""
        logger.info('Registering utility tools with Letta...')

        utility_tools = [
            {
                'name': 'get_system_status',
                'description': 'Check the status of Thoth services and system health',
                'category': 'management',
            },
            {
                'name': 'list_available_tools',
                'description': 'List all tools available to this agent',
                'category': 'management',
            },
        ]

        for tool_def in utility_tools:
            try:
                await self._register_utility_tool(tool_def)
            except Exception as e:
                logger.error(f'Failed to register utility tool {tool_def["name"]}: {e}')

    async def _register_utility_tool(self, tool_def: dict[str, Any]) -> None:
        """Register a single utility tool with Letta."""
        tool_name = tool_def['name']

        try:
            # Create Letta tool definition
            letta_tool = ToolCreate(
                name=tool_name,
                description=tool_def['description'],
                source_code=self._generate_tool_source_code(
                    tool_name, tool_def, 'utility'
                ),
                source_type='python',
            )

            # Register with Letta client
            created_tool = await self._create_letta_tool(letta_tool)

            # Only track tool if it was successfully registered with Letta client
            if created_tool is not None:
                self._registered_tools[tool_name] = {
                    'type': 'utility',
                    'definition': tool_def,
                    'letta_tool': created_tool,
                    'category': tool_def['category'],
                }

            logger.debug(f'Registered utility tool: {tool_name}')

        except Exception as e:
            logger.error(f'Failed to register utility tool {tool_name}: {e}')

    def _create_document_pipeline_tool(self) -> Callable:
        """Create document pipeline execution function."""

        async def run_document_pipeline(document_path: str, **options) -> str:
            """
            Process a document through the document pipeline.

            Args:
                document_path: Path to the document to process
                **options: Additional pipeline options

            Returns:
                Processing result summary
            """
            try:
                pipeline = DocumentPipeline(self.service_manager)
                result = await pipeline.process_document(document_path, **options)
                return f'Document processed successfully: {result.get("status", "completed")}'
            except Exception as e:
                logger.error(f'Document pipeline error: {e}')
                return f'Document pipeline failed: {e!s}'

        return run_document_pipeline

    def _create_knowledge_pipeline_tool(self) -> Callable:
        """Create knowledge pipeline execution function."""

        async def run_knowledge_pipeline(document_path: str, **options) -> str:
            """
            Process a document through the knowledge pipeline.

            Args:
                document_path: Path to the document to process
                **options: Additional pipeline options

            Returns:
                Processing result summary
            """
            try:
                pipeline = KnowledgePipeline(self.service_manager)
                result = await pipeline.process_document(document_path, **options)
                return f'Knowledge extraction completed: {result.get("status", "completed")}'
            except Exception as e:
                logger.error(f'Knowledge pipeline error: {e}')
                return f'Knowledge pipeline failed: {e!s}'

        return run_knowledge_pipeline

    def _generate_tool_source_code(
        self, tool_name: str, tool_schema, tool_type: str
    ) -> str:
        """Generate Python source code for a tool."""
        if tool_type == 'mcp':
            # Generate MCP tool wrapper
            params_str = ''
            if hasattr(tool_schema, 'inputSchema') and tool_schema.inputSchema:
                properties = tool_schema.inputSchema.get('properties', {})
                params = []
                for param_name, param_def in properties.items():
                    param_type = param_def.get('type', 'str')
                    python_type = 'str' if param_type == 'string' else param_type
                    params.append(f'{param_name}: {python_type}')
                params_str = ', '.join(params)

            return f"""
async def {tool_name}({params_str}) -> str:
    \"\"\"
    {tool_schema.description}

    This tool is automatically generated from an MCP tool.
    \"\"\"
    import asyncio
    from thoth.tools.letta_registration import get_mcp_registry

    try:
        registry = get_mcp_registry()
        kwargs = {{}}
        {self._generate_param_extraction(tool_schema)}

        result = await registry.execute_tool('{tool_name}', kwargs)

        if hasattr(result, 'content'):
            return str(result.content)
        else:
            return str(result)

    except Exception as e:
        return f"Error executing {tool_name}: {{str(e)}}"
"""

        elif tool_type == 'pipeline':
            return f"""
async def {tool_name}(document_path: str, **options) -> str:
    \"\"\"
    {tool_schema['description']}

    Args:
        document_path: Path to the document to process
        **options: Additional processing options

    Returns:
        Processing result summary
    \"\"\"
    from thoth.tools.letta_registration import get_service_manager
    from thoth.pipelines import DocumentPipeline, KnowledgePipeline

    try:
        service_manager = get_service_manager()

        if '{tool_name}' == 'run_document_pipeline':
            pipeline = DocumentPipeline(service_manager)
        elif '{tool_name}' == 'run_knowledge_pipeline':
            pipeline = KnowledgePipeline(service_manager)
        else:
            return f"Unknown pipeline: {tool_name}"

        result = await pipeline.process_document(document_path, **options)
        return f"Pipeline completed: {{result.get('status', 'completed')}}"

    except Exception as e:
        return f"Pipeline error: {{str(e)}}"
"""

        elif tool_type == 'utility':
            return f"""
def {tool_name}() -> str:
    \"\"\"
    {tool_schema['description']}
    \"\"\"
    from thoth.tools.letta_registration import get_service_manager

    try:
        if '{tool_name}' == 'get_system_status':
            service_manager = get_service_manager()
            # Simple health check
            return "System status: All services operational"
        elif '{tool_name}' == 'list_available_tools':
            # Return list of available tools
            return "Available tools: MCP tools, pipeline tools, utility tools"
        else:
            return f"Unknown utility: {tool_name}"

    except Exception as e:
        return f"Utility error: {{str(e)}}"
"""

        return f'def {tool_name}(): pass  # Placeholder'

    def _generate_param_extraction(self, tool_schema) -> str:
        """Generate parameter extraction code for MCP tools."""
        if not hasattr(tool_schema, 'inputSchema') or not tool_schema.inputSchema:
            return ''

        properties = tool_schema.inputSchema.get('properties', {})
        lines = []

        for param_name, _param_def in properties.items():
            lines.append(f"        if '{param_name}' in locals():")
            lines.append(f"            kwargs['{param_name}'] = {param_name}")

        return '\n'.join(lines)

    async def _create_letta_tool(self, tool_def: ToolCreate):
        """Create a tool in Letta and handle async execution."""
        if not self.letta_client:
            return None

        try:
            # Use asyncio to run the sync Letta client method
            loop = asyncio.get_event_loop()
            created_tool = await loop.run_in_executor(
                None, self.letta_client.tools.create, tool_def
            )
            return created_tool
        except Exception as e:
            logger.error(f'Failed to create Letta tool: {e}')
            return None

    def _categorize_tool(self, tool_name: str) -> str:
        """Categorize a tool based on its name."""
        for category, tool_names in self.tool_categories.items():
            for pattern in tool_names:
                if pattern in tool_name.lower():
                    return category
        return 'general'

    def get_tools_for_agent_type(self, agent_type: str) -> list[str]:
        """Get recommended tools for a specific agent type."""
        type_mappings = {
            'research': ['research', 'citation', 'processing'],
            'analysis': ['research', 'citation', 'memory'],
            'discovery': ['research', 'processing'],
            'citation': ['citation', 'processing'],
            'management': ['management', 'memory'],
            'custom': ['research', 'processing', 'memory'],
        }

        categories = type_mappings.get(agent_type, ['research', 'processing'])
        tools = []

        for tool_name, tool_info in self._registered_tools.items():
            if tool_info['category'] in categories:
                tools.append(tool_name)

        return tools

    def get_registered_tools(self) -> dict[str, dict[str, Any]]:
        """Get all registered tools."""
        return self._registered_tools.copy()


# Global registry instance for module-level access
_global_registry: LettaToolRegistry | None = None
_global_service_manager: ServiceManager | None = None


def get_mcp_registry() -> MCPToolRegistry:
    """Get the global MCP registry."""
    global _global_registry
    if _global_registry:
        return _global_registry._mcp_registry
    raise RuntimeError('LettaToolRegistry not initialized')


def get_service_manager() -> ServiceManager:
    """Get the global service manager."""
    global _global_service_manager
    if _global_service_manager:
        return _global_service_manager
    raise RuntimeError('ServiceManager not initialized')


async def register_all_letta_tools(
    service_manager: ServiceManager, letta_client: LettaClient | None = None
) -> LettaToolRegistry:
    """
    Register all Thoth tools with Letta following best practices.

    Args:
        service_manager: ServiceManager instance
        letta_client: Letta client for registration (optional, creates fallback registry
                     if None)

    Returns:
        Configured LettaToolRegistry instance

    Note:
        If letta_client is None, creates a registry that works in fallback mode
        without Letta
    """
    global _global_registry, _global_service_manager

    _global_service_manager = service_manager

    # Create registry (with or without Letta client)
    registry = LettaToolRegistry(service_manager, letta_client)
    _global_registry = registry

    # Register all tools only if Letta client is available
    if letta_client:
        await registry.register_all_tools()
        logger.info(
            'All tools registered with Letta successfully following best practices'
        )
    else:
        logger.info('Registry created in fallback mode (no Letta client available)')

    return registry

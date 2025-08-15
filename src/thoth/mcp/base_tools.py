"""
MCP Tool Implementation

This module provides MCP-compliant tool definitions and registry.
"""

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from thoth.services.service_manager import ServiceManager

from .protocol import MCPToolCallResult, MCPToolSchema


class MCPTool(ABC):
    """
    Base class for MCP-compliant tools.

    This replaces the LangChain BaseTool with proper MCP schema support.
    """

    def __init__(self, service_manager: ServiceManager | None = None):
        self.service_manager = service_manager

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (must be unique)."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for the LLM."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema for tool input validation."""
        pass

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """
        Execute the tool with given arguments.

        Args:
            arguments: Tool arguments matching the input schema

        Returns:
            MCPToolCallResult with content and error status
        """
        pass

    def to_schema(self) -> MCPToolSchema:
        """Convert tool to MCP schema format."""
        return MCPToolSchema(
            name=self.name, description=self.description, inputSchema=self.input_schema
        )

    def validate_arguments(self, arguments: dict[str, Any]) -> bool:
        """Validate arguments against the input schema."""
        try:
            # Basic validation - check required fields exist
            # Full JSON Schema validation can be added when needed
            schema = self.input_schema
            if 'required' in schema:
                for field in schema['required']:
                    if field not in arguments:
                        return False
            return True
        except Exception as e:
            logger.error(f'Error validating arguments for {self.name}: {e}')
            return False

    def handle_error(self, error: Exception) -> MCPToolCallResult:
        """Standard error handling for tools."""
        import traceback

        # Get full traceback for debugging
        tb_str = traceback.format_exc()
        logger.error(f'Tool error in {self.name}: {error}')
        logger.error(f'Full traceback for {self.name}:\n{tb_str}')

        return MCPToolCallResult(
            content=[
                {
                    'type': 'text',
                    'text': f'❌ Error in {self.name}: {error!s}\n\n🔍 Debug info: {type(error).__name__}',
                }
            ],
            isError=True,
        )


class MCPToolRegistry:
    """
    Registry for managing MCP-compliant tools.

    This replaces the old ToolRegistry with proper MCP support.
    """

    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self._tools: dict[str, MCPTool] = {}
        self._tool_classes: dict[str, type[MCPTool]] = {}

    def register_class(self, tool_class: type[MCPTool]) -> None:
        """Register a tool class for lazy instantiation."""
        # Create temporary instance to get name
        temp_instance = tool_class(self.service_manager)
        name = temp_instance.name
        self._tool_classes[name] = tool_class
        logger.debug(f'Registered MCP tool class: {name}')

    def register_instance(self, tool: MCPTool) -> None:
        """Register a tool instance directly."""
        self._tools[tool.name] = tool
        logger.debug(f'Registered MCP tool instance: {tool.name}')

    def get_tool(self, name: str) -> MCPTool | None:
        """Get a tool instance by name."""
        # Check instances first
        if name in self._tools:
            return self._tools[name]

        # Check classes and instantiate if found
        if name in self._tool_classes:
            tool_class = self._tool_classes[name]
            tool = tool_class(self.service_manager)
            self._tools[name] = tool  # Cache the instance
            return tool

        return None

    def get_all_tools(self) -> list[MCPTool]:
        """Get all registered tools (instantiate classes as needed)."""
        tools = []

        # Add existing instances
        tools.extend(self._tools.values())

        # Instantiate classes not yet instantiated
        for name, tool_class in self._tool_classes.items():
            if name not in self._tools:
                tool = tool_class(self.service_manager)
                self._tools[name] = tool
                tools.append(tool)

        return tools

    def get_tool_schemas(self) -> list[MCPToolSchema]:
        """Get MCP schemas for all registered tools."""
        return [tool.to_schema() for tool in self.get_all_tools()]

    def get_tool_names(self) -> list[str]:
        """Get names of all registered tools."""
        names = set(self._tools.keys())
        names.update(self._tool_classes.keys())
        return list(names)

    async def execute_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> MCPToolCallResult:
        """Execute a tool by name with given arguments."""
        tool = self.get_tool(name)
        if not tool:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f"❌ Tool '{name}' not found"}],
                isError=True,
            )

        # Validate arguments
        if not tool.validate_arguments(arguments):
            return MCPToolCallResult(
                content=[
                    {'type': 'text', 'text': f"❌ Invalid arguments for tool '{name}'"}
                ],
                isError=True,
            )

        try:
            logger.debug(f"Executing tool '{name}' with arguments: {arguments}")
            result = await tool.execute(arguments)
            logger.debug(f"Tool '{name}' completed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool execution failed for '{name}': {e}")
            return tool.handle_error(e)


# Decorator for automatic tool registration
def mcp_tool(registry: MCPToolRegistry):
    """Decorator to automatically register MCP tools."""

    def decorator(tool_class: type[MCPTool]):
        registry.register_class(tool_class)
        return tool_class

    return decorator


# Base tool implementations for common patterns
class QueryNameTool(MCPTool):
    """Base class for tools that require a query name."""

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'query_name': {
                    'type': 'string',
                    'description': 'Name of the research query',
                }
            },
            'required': ['query_name'],
        }


class SourceNameTool(MCPTool):
    """Base class for tools that require a source name."""

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'source_name': {
                    'type': 'string',
                    'description': 'Name of the discovery source',
                }
            },
            'required': ['source_name'],
        }


class SearchTool(MCPTool):
    """Base class for search/RAG tools."""

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Search query or question'},
                'k': {
                    'type': 'integer',
                    'description': 'Number of results to return',
                    'default': 4,
                    'minimum': 1,
                    'maximum': 20,
                },
                'filter': {
                    'type': 'object',
                    'description': 'Optional metadata filter',
                    'additionalProperties': True,
                },
            },
            'required': ['query'],
        }


class NoInputTool(MCPTool):
    """Base class for tools that don't require input."""

    @property
    def input_schema(self) -> dict[str, Any]:
        return {'type': 'object', 'properties': {}, 'additionalProperties': False}

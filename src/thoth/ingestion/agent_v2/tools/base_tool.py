"""
Base tool class for Thoth research assistant tools.

This module provides the base class and utilities for creating tools
that integrate with the LangChain/LangGraph MCP framework.
"""

from abc import ABC, abstractmethod
from typing import Any

from langchain.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field

from thoth.services.service_manager import ServiceManager


class BaseThothTool(BaseTool, ABC):
    """
    Base class for all Thoth research assistant tools.

    This provides common functionality and structure for tools that integrate
    with the research assistant agent.
    """

    # Common attributes that all tools might need
    service_manager: ServiceManager = Field(default=None, exclude=True)
    config: Any = Field(default=None, exclude=True)

    def __init__(self, **kwargs):
        """Initialize the tool with optional service_manager and config."""
        super().__init__(**kwargs)

    @abstractmethod
    def _run(self, *args: Any, **kwargs: Any) -> str:
        """
        Execute the tool's main functionality.

        This method must be implemented by all subclasses.
        """
        pass

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        """
        Async version of run. Default implementation calls sync version.

        Override this in subclasses if async functionality is needed.
        """
        return self._run(*args, **kwargs)

    def handle_error(self, error: Exception, context: str = '') -> str:
        """
        Standard error handling for tools.

        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred

        Returns:
            str: User-friendly error message
        """
        logger.error(
            f'Tool error in {self.name}{f" ({context})" if context else ""}: {error}'
        )
        return f'❌ Error: {error!s}'


class ToolRegistry:
    """
    Registry for managing and creating tool instances.

    This helps organize tools and provides a central place to instantiate them
    with the required dependencies.
    """

    def __init__(self, service_manager: ServiceManager, config=None):
        """
        Initialize the tool registry.

        Args:
            service_manager: ServiceManager instance for accessing services
            config: Configuration object
        """
        self.service_manager = service_manager
        self.config = config
        self._tools: dict[str, type[BaseThothTool]] = {}

    def register(self, name: str, tool_class: type[BaseThothTool]) -> None:
        """Register a tool class with the registry."""
        self._tools[name] = tool_class
        logger.debug(f'Registered tool: {name}')

    def create_tool(self, name: str, **kwargs) -> BaseThothTool:
        """
        Create an instance of a registered tool.

        Args:
            name: Name of the tool to create
            **kwargs: Additional arguments to pass to the tool constructor

        Returns:
            BaseThothTool: Instantiated tool

        Raises:
            ValueError: If tool is not registered
        """
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not registered")

        tool_class = self._tools[name]
        return tool_class(
            service_manager=self.service_manager, config=self.config, **kwargs
        )

    def create_all_tools(self) -> list[BaseThothTool]:
        """
        Create instances of all registered tools.

        Returns:
            list[BaseThothTool]: List of instantiated tools
        """
        tools = []
        for name in self._tools:
            try:
                tool = self.create_tool(name)
                tools.append(tool)
            except Exception as e:
                logger.error(f"Failed to create tool '{name}': {e}")
        return tools

    def get_tool_names(self) -> list[str]:
        """Get list of all registered tool names."""
        return list(self._tools.keys())


# Tool input/output schemas using Pydantic for validation
class JsonToolInput(BaseModel):
    """Base schema for tools that accept JSON input."""

    pass


class QueryNameInput(BaseModel):
    """Schema for tools that require a query name."""

    query_name: str = Field(description='Name of the research query')


class SourceNameInput(BaseModel):
    """Schema for tools that require a source name."""

    source_name: str = Field(description='Name of the discovery source')


class SearchInput(BaseModel):
    """Schema for search/RAG tools."""

    query: str = Field(description='Search query or question')
    k: int = Field(default=4, description='Number of results to return')
    filter: dict[str, Any] | None = Field(
        default=None, description='Optional metadata filter'
    )

"""
MCP Server Implementation

This module provides the main MCP server that handles protocol messages,
manages tools and resources, and coordinates transport layers.
"""

import sys
from typing import Any

from loguru import logger

from thoth.services.service_manager import ServiceManager

from .protocol import (
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    MCPCapabilities,
    MCPErrorCodes,
    MCPProtocolHandler,
    MCPServerInfo,
)
from .resources import MCPResourceManager
from .tools import MCPToolRegistry
from .transports import HTTPTransport, SSETransport, StdioTransport, TransportManager


class MCPServer:
    """
    Main MCP server implementation.

    This server handles the complete MCP protocol including initialization,
    tool calling, resource management, and multiple transport support.
    """

    def __init__(
        self,
        service_manager: ServiceManager,
        server_name: str = 'Thoth Research Assistant',
        server_version: str = '1.0.0',
    ):
        """
        Initialize the MCP server.

        Args:
            service_manager: ServiceManager for accessing Thoth services
            server_name: Name of the MCP server
            server_version: Version of the MCP server
        """
        self.service_manager = service_manager
        self.server_info = MCPServerInfo(name=server_name, version=server_version)

        # Initialize protocol handler
        self.protocol_handler = MCPProtocolHandler()

        # Initialize tool registry and resource manager
        self.tool_registry = MCPToolRegistry(service_manager)
        self.resource_manager = MCPResourceManager()

        # Initialize transport manager
        self.transport_manager = TransportManager(self.protocol_handler)

        # Server capabilities
        self.capabilities = MCPCapabilities(
            tools={'listChanged': True},
            resources={'subscribe': True, 'listChanged': True},
            prompts={'listChanged': True},
            logging={},
        )

        # Setup message handler
        self.transport_manager._handle_message = self._handle_message

        logger.info(f'Initialized MCP Server: {server_name} v{server_version}')

    def add_stdio_transport(self) -> None:
        """Add stdio transport for CLI integration."""
        transport = StdioTransport(self.protocol_handler)
        self.transport_manager.add_transport('stdio', transport)

    def add_http_transport(self, host: str = 'localhost', port: int = 8000) -> None:
        """Add HTTP transport for web integration."""
        transport = HTTPTransport(self.protocol_handler, host, port)
        self.transport_manager.add_transport('http', transport)

    def add_sse_transport(self, host: str = 'localhost', port: int = 8001) -> None:
        """Add SSE transport for streaming."""
        transport = SSETransport(self.protocol_handler, host, port)
        self.transport_manager.add_transport('sse', transport)

    async def start(self) -> None:
        """Start the MCP server with all configured transports."""
        logger.info('Starting MCP server...')
        await self.transport_manager.start_all()
        logger.info('MCP server started successfully')

    async def stop(self) -> None:
        """Stop the MCP server."""
        logger.info('Stopping MCP server...')
        await self.transport_manager.stop_all()
        logger.info('MCP server stopped')

    async def _handle_message(
        self, message: JSONRPCRequest | JSONRPCNotification
    ) -> JSONRPCResponse | None:
        """
        Handle incoming MCP messages.

        This is the main message router that dispatches to appropriate handlers
        based on the method name.
        """
        try:
            method = message.method
            params = message.params or {}

            logger.debug(f'Handling MCP method: {method}')

            # Check if this is a notification (no response expected)
            is_notification = isinstance(message, JSONRPCNotification)
            message_id = getattr(message, 'id', None)

            # Route to appropriate handler
            if method == 'initialize':
                return await self._handle_initialize(message_id, params)
            elif method == 'initialized':
                # This is a notification - no response expected
                await self._handle_initialized_notification()
                return None  # No response for notifications
            elif method == 'tools/list':
                return await self._handle_tools_list(message_id)
            elif method == 'tools/call':
                return await self._handle_tools_call(message_id, params)
            elif method == 'resources/list':
                return await self._handle_resources_list(message_id)
            elif method == 'resources/read':
                return await self._handle_resources_read(message_id, params)
            elif method == 'resources/templates':
                return await self._handle_resources_templates(message_id)
            elif method == 'prompts/list':
                return await self._handle_prompts_list(message_id)
            elif method == 'prompts/get':
                return await self._handle_prompts_get(message_id, params)
            elif method == 'logging/setLevel':
                return await self._handle_logging_set_level(message_id, params)
            else:
                if is_notification:
                    # Unknown notification - just log and ignore
                    logger.warning(f'Unknown notification method: {method}')
                    return None
                else:
                    return self.protocol_handler.create_error_response(
                        message_id,
                        MCPErrorCodes.METHOD_NOT_FOUND,
                        f'Method not found: {method}',
                    )

        except Exception as e:
            logger.error(f'Error handling message: {e}')
            # Only return error response for requests, not notifications
            if not isinstance(message, JSONRPCNotification):
                return self.protocol_handler.create_error_response(
                    getattr(message, 'id', None),
                    MCPErrorCodes.INTERNAL_ERROR,
                    f'Internal error: {e}',
                )
            return None

    async def _handle_initialize(
        self, request_id: Any, params: dict[str, Any]
    ) -> JSONRPCResponse:
        """Handle MCP initialize request."""
        try:
            init_params = self.protocol_handler.validate_initialize_request(params)
            result = self.protocol_handler.handle_initialize(
                init_params, self.server_info, self.capabilities
            )

            logger.info(f'MCP client initialized: {init_params.clientInfo.name}')
            return self.protocol_handler.create_response(
                request_id, result.model_dump()
            )

        except ValueError as e:
            return self.protocol_handler.create_error_response(
                request_id, MCPErrorCodes.INVALID_PARAMS, str(e)
            )

    async def _handle_initialized_notification(self) -> None:
        """Handle MCP initialized notification (no response expected)."""
        try:
            self.protocol_handler.initialized = True
            logger.debug('MCP protocol marked as initialized')
        except Exception as e:
            logger.error(f'Error handling initialized notification: {e}')

    async def _handle_tools_list(self, request_id: Any) -> JSONRPCResponse:
        """Handle tools/list request."""
        try:
            tools = self.tool_registry.get_tool_schemas()
            result = {'tools': [tool.model_dump() for tool in tools]}
            return self.protocol_handler.create_response(request_id, result)
        except Exception as e:
            return self.protocol_handler.create_error_response(
                request_id, MCPErrorCodes.INTERNAL_ERROR, f'Error listing tools: {e}'
            )

    async def _handle_tools_call(
        self, request_id: Any, params: dict[str, Any]
    ) -> JSONRPCResponse:
        """Handle tools/call request."""
        try:
            tool_params = self.protocol_handler.validate_tool_call_params(params)
            result = await self.tool_registry.execute_tool(
                tool_params.name, tool_params.arguments
            )
            return self.protocol_handler.create_response(
                request_id, result.model_dump()
            )

        except ValueError as e:
            return self.protocol_handler.create_error_response(
                request_id, MCPErrorCodes.INVALID_PARAMS, str(e)
            )
        except Exception as e:
            return self.protocol_handler.create_error_response(
                request_id, MCPErrorCodes.INTERNAL_ERROR, f'Error executing tool: {e}'
            )

    async def _handle_resources_list(self, request_id: Any) -> JSONRPCResponse:
        """Handle resources/list request."""
        try:
            resources = await self.resource_manager.list_all_resources()
            result = {'resources': [resource.model_dump() for resource in resources]}
            return self.protocol_handler.create_response(request_id, result)
        except Exception as e:
            return self.protocol_handler.create_error_response(
                request_id,
                MCPErrorCodes.INTERNAL_ERROR,
                f'Error listing resources: {e}',
            )

    async def _handle_resources_read(
        self, request_id: Any, params: dict[str, Any]
    ) -> JSONRPCResponse:
        """Handle resources/read request."""
        try:
            uri = params.get('uri')
            if not uri:
                return self.protocol_handler.create_error_response(
                    request_id,
                    MCPErrorCodes.INVALID_PARAMS,
                    'Missing required parameter: uri',
                )

            contents = await self.resource_manager.get_resource(uri)
            if not contents:
                return self.protocol_handler.create_error_response(
                    request_id,
                    MCPErrorCodes.RESOURCE_NOT_FOUND,
                    f'Resource not found: {uri}',
                )

            result = {'contents': [contents.model_dump()]}
            return self.protocol_handler.create_response(request_id, result)

        except Exception as e:
            return self.protocol_handler.create_error_response(
                request_id, MCPErrorCodes.INTERNAL_ERROR, f'Error reading resource: {e}'
            )

    async def _handle_resources_templates(self, request_id: Any) -> JSONRPCResponse:
        """Handle resources/templates request."""
        try:
            templates = self.resource_manager.get_all_resource_templates()
            result = {
                'resourceTemplates': [template.model_dump() for template in templates]
            }
            return self.protocol_handler.create_response(request_id, result)
        except Exception as e:
            return self.protocol_handler.create_error_response(
                request_id,
                MCPErrorCodes.INTERNAL_ERROR,
                f'Error getting resource templates: {e}',
            )

    async def _handle_prompts_list(self, request_id: Any) -> JSONRPCResponse:
        """Handle prompts/list request."""
        # TODO: Implement prompt templates
        result = {'prompts': []}
        return self.protocol_handler.create_response(request_id, result)

    async def _handle_prompts_get(
        self, request_id: Any, _params: dict[str, Any]
    ) -> JSONRPCResponse:
        """Handle prompts/get request."""
        # TODO: Implement prompt template retrieval
        return self.protocol_handler.create_error_response(
            request_id, MCPErrorCodes.PROMPT_NOT_FOUND, 'Prompts not yet implemented'
        )

    async def _handle_logging_set_level(
        self, request_id: Any, params: dict[str, Any]
    ) -> JSONRPCResponse:
        """Handle logging/setLevel request."""
        try:
            level = params.get('level', 'info').upper()
            logger.remove()
            logger.add(sys.stderr, level=level)
            logger.info(f'Log level set to: {level}')
            return self.protocol_handler.create_response(request_id, {})
        except Exception as e:
            return self.protocol_handler.create_error_response(
                request_id,
                MCPErrorCodes.INTERNAL_ERROR,
                f'Error setting log level: {e}',
            )

    def register_tool_class(self, tool_class):
        """Register a tool class with the server."""
        self.tool_registry.register_class(tool_class)

    def register_tool_instance(self, tool):
        """Register a tool instance with the server."""
        self.tool_registry.register_instance(tool)

    def add_resource_provider(self, provider):
        """Add a resource provider to the server."""
        self.resource_manager.add_provider(provider)


# Factory function for easy server creation
def create_mcp_server(
    service_manager: ServiceManager,
    enable_stdio: bool = True,
    enable_http: bool = True,
    http_host: str = 'localhost',
    http_port: int = 8000,
    enable_sse: bool = False,
    sse_host: str = 'localhost',
    sse_port: int = 8001,
) -> MCPServer:
    """
    Create and configure an MCP server with transports.

    Args:
        service_manager: ServiceManager instance
        enable_stdio: Enable stdio transport for CLI
        enable_http: Enable HTTP transport for web APIs
        http_host: HTTP server host
        http_port: HTTP server port
        enable_sse: Enable Server-Sent Events transport
        sse_host: SSE server host
        sse_port: SSE server port

    Returns:
        Configured MCPServer instance
    """
    server = MCPServer(service_manager)

    if enable_stdio:
        server.add_stdio_transport()

    if enable_http:
        server.add_http_transport(http_host, http_port)

    if enable_sse:
        server.add_sse_transport(sse_host, sse_port)

    return server

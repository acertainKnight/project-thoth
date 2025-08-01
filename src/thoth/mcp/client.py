"""
MCP Client Implementation

This module provides an MCP client for connecting to MCP servers
and using their tools and resources.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

from loguru import logger

from .protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    MCPCapabilities,
    MCPInitializeParams,
    MCPProtocolHandler,
    MCPResource,
    MCPResourceContents,
    MCPServerInfo,
    MCPToolCallParams,
    MCPToolSchema,
)


class MCPClient:
    """
    MCP client for connecting to and communicating with MCP servers.

    Supports stdio, HTTP, and other transport mechanisms for connecting
    to MCP-compliant servers.
    """

    def __init__(
        self, client_name: str = 'Thoth MCP Client', client_version: str = '1.0.0'
    ):
        """
        Initialize MCP client.

        Args:
            client_name: Name of the MCP client
            client_version: Version of the MCP client
        """
        self.client_info = MCPServerInfo(name=client_name, version=client_version)
        self.capabilities = MCPCapabilities(
            tools={}, resources={}, prompts={}, logging={}
        )

        self.protocol_handler = MCPProtocolHandler()
        self.connected = False
        self.initialized = False

        # Server information (populated after connection)
        self.server_info: MCPServerInfo | None = None
        self.server_capabilities: MCPCapabilities | None = None

        # Available tools and resources (cached)
        self._tools: list[MCPToolSchema] = []
        self._resources: list[MCPResource] = []

        # Transport connection
        self._send_message: Callable | None = None
        self._close_connection: Callable | None = None

    async def connect_stdio(self, command: list[str]) -> None:
        """
        Connect to an MCP server via stdio transport.

        Args:
            command: Command to start the MCP server process
        """
        try:
            # Start the server process
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Set up message sending
            async def send_message(message: JSONRPCRequest):
                if process.stdin:
                    message_str = self.protocol_handler.serialize_message(message)
                    process.stdin.write(message_str.encode() + b'\n')
                    await process.stdin.drain()

            async def close_connection():
                if process.stdin:
                    process.stdin.close()
                await process.wait()

            self._send_message = send_message
            self._close_connection = close_connection
            self.connected = True

            # Start message receiving loop
            task = asyncio.create_task(self._stdio_receive_loop(process))
            # Store task reference to prevent garbage collection
            self._receive_task = task

            logger.info(f'Connected to MCP server via stdio: {" ".join(command)}')

        except Exception as e:
            logger.error(f'Failed to connect via stdio: {e}')
            raise

    async def connect_http(self, base_url: str) -> None:
        """
        Connect to an MCP server via HTTP transport.

        Args:
            base_url: Base URL of the MCP server
        """
        import aiohttp

        try:
            self.session = aiohttp.ClientSession()
            self.base_url = base_url.rstrip('/')

            # Set up message sending
            async def send_message(message: JSONRPCRequest):
                message_data = json.loads(
                    self.protocol_handler.serialize_message(message)
                )
                async with self.session.post(
                    f'{self.base_url}/mcp', json=message_data
                ) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        return self.protocol_handler.parse_message(
                            json.dumps(response_data)
                        )
                    else:
                        raise Exception(f'HTTP error: {response.status}')

            async def close_connection():
                await self.session.close()

            self._send_message = send_message
            self._close_connection = close_connection
            self.connected = True

            logger.info(f'Connected to MCP server via HTTP: {base_url}')

        except Exception as e:
            logger.error(f'Failed to connect via HTTP: {e}')
            raise

    async def initialize(self) -> None:
        """Initialize the MCP connection with handshake."""
        if not self.connected:
            raise RuntimeError('Not connected to server')

        if self.initialized:
            return

        try:
            # Send initialize request
            init_params = MCPInitializeParams(
                protocolVersion='2025-06-18',
                capabilities=self.capabilities,
                clientInfo=self.client_info,
            )

            request = JSONRPCRequest(
                id=self.protocol_handler.generate_request_id(),
                method='initialize',
                params=init_params.model_dump(),
            )

            response = await self._send_request(request)

            if response.error:
                raise Exception(f'Initialize failed: {response.error.message}')

            # Parse initialize result
            result = response.result
            self.server_info = MCPServerInfo(**result['serverInfo'])
            self.server_capabilities = MCPCapabilities(**result['capabilities'])

            # Send initialized notification
            notification = self.protocol_handler.create_notification('initialized')
            await self._send_message(notification)

            self.initialized = True
            logger.info(f'Initialized MCP connection with {self.server_info.name}')

        except Exception as e:
            logger.error(f'Failed to initialize MCP connection: {e}')
            raise

    async def list_tools(self) -> list[MCPToolSchema]:
        """List available tools from the server."""
        if not self.initialized:
            raise RuntimeError('Not initialized')

        request = JSONRPCRequest(
            id=self.protocol_handler.generate_request_id(), method='tools/list'
        )

        response = await self._send_request(request)

        if response.error:
            raise Exception(f'Failed to list tools: {response.error.message}')

        tools_data = response.result.get('tools', [])
        self._tools = [MCPToolSchema(**tool) for tool in tools_data]
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Call a tool on the server.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        if not self.initialized:
            raise RuntimeError('Not initialized')

        tool_params = MCPToolCallParams(name=name, arguments=arguments)
        request = JSONRPCRequest(
            id=self.protocol_handler.generate_request_id(),
            method='tools/call',
            params=tool_params.model_dump(),
        )

        response = await self._send_request(request)

        if response.error:
            raise Exception(f'Tool call failed: {response.error.message}')

        return response.result

    async def list_resources(self) -> list[MCPResource]:
        """List available resources from the server."""
        if not self.initialized:
            raise RuntimeError('Not initialized')

        request = JSONRPCRequest(
            id=self.protocol_handler.generate_request_id(), method='resources/list'
        )

        response = await self._send_request(request)

        if response.error:
            raise Exception(f'Failed to list resources: {response.error.message}')

        resources_data = response.result.get('resources', [])
        self._resources = [MCPResource(**resource) for resource in resources_data]
        return self._resources

    async def read_resource(self, uri: str) -> MCPResourceContents:
        """
        Read resource contents from the server.

        Args:
            uri: Resource URI

        Returns:
            Resource contents
        """
        if not self.initialized:
            raise RuntimeError('Not initialized')

        request = JSONRPCRequest(
            id=self.protocol_handler.generate_request_id(),
            method='resources/read',
            params={'uri': uri},
        )

        response = await self._send_request(request)

        if response.error:
            raise Exception(f'Failed to read resource: {response.error.message}')

        contents_data = response.result.get('contents', [])
        if not contents_data:
            raise Exception('No resource contents returned')

        return MCPResourceContents(**contents_data[0])

    async def close(self) -> None:
        """Close the MCP connection."""
        if self._close_connection:
            await self._close_connection()

        self.connected = False
        self.initialized = False
        logger.info('Closed MCP connection')

    async def _send_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Send a request and return the response."""
        if not self._send_message:
            raise RuntimeError('No transport connection')

        # For HTTP, _send_message returns the response directly
        if hasattr(self, 'session'):  # HTTP transport
            return await self._send_message(request)
        else:
            # For stdio, we need to implement request-response matching
            # This is a simplified version - full implementation would need
            # proper request tracking and timeout handling
            await self._send_message(request)
            # TODO: Implement response waiting for stdio transport
            raise NotImplementedError('Stdio request-response not fully implemented')

    async def _stdio_receive_loop(self, process):
        """Message receiving loop for stdio transport."""
        try:
            while process.stdout and not process.stdout.at_eof():
                line = await process.stdout.readline()
                if not line:
                    break

                message_str = line.decode().strip()
                if not message_str:
                    continue

                try:
                    message = self.protocol_handler.parse_message(message_str)
                    await self._handle_server_message(message)
                except Exception as e:
                    logger.error(f'Error processing server message: {e}')

        except Exception as e:
            logger.error(f'Error in stdio receive loop: {e}')

    async def _handle_server_message(self, message):
        """Handle messages received from the server."""
        # TODO: Implement proper message handling for notifications
        # and response matching for requests
        logger.debug(f'Received server message: {message}')

    def get_cached_tools(self) -> list[MCPToolSchema]:
        """Get cached tools list."""
        return self._tools

    def get_cached_resources(self) -> list[MCPResource]:
        """Get cached resources list."""
        return self._resources

    def get_tool_by_name(self, name: str) -> MCPToolSchema | None:
        """Get a specific tool by name from cache."""
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None


# Context manager for easy client usage
class MCPClientContext:
    """Context manager for MCP client connections."""

    def __init__(self, client: MCPClient):
        self.client = client

    async def __aenter__(self):
        await self.client.initialize()
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()


# Convenience functions
async def connect_stdio_client(
    command: list[str], client_name: str = 'Thoth MCP Client'
) -> MCPClient:
    """Create and connect an MCP client via stdio."""
    client = MCPClient(client_name=client_name)
    await client.connect_stdio(command)
    await client.initialize()
    return client


async def connect_http_client(
    base_url: str, client_name: str = 'Thoth MCP Client'
) -> MCPClient:
    """Create and connect an MCP client via HTTP."""
    client = MCPClient(client_name=client_name)
    await client.connect_http(base_url)
    await client.initialize()
    return client

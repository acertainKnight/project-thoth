"""
MCP Transport Layer Implementation

This module provides transport implementations for MCP including stdio, HTTP, and SSE.
"""

import asyncio
import json
import sys
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from .protocol import (
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    MCPProtocolHandler,
)


class MCPTransport(ABC):
    """Abstract base class for MCP transport implementations."""

    def __init__(self, protocol_handler: MCPProtocolHandler):
        self.protocol_handler = protocol_handler
        self.message_handler: Callable | None = None

    def set_message_handler(self, handler: Callable[[JSONRPCRequest], JSONRPCResponse]):
        """Set the handler function for incoming messages."""
        self.message_handler = handler

    @abstractmethod
    async def start(self):
        """Start the transport."""
        pass

    @abstractmethod
    async def stop(self):
        """Stop the transport."""
        pass

    @abstractmethod
    async def send_message(self, message: JSONRPCResponse):
        """Send a message through the transport."""
        pass


class StdioTransport(MCPTransport):
    """
    Standard input/output transport for MCP.

    This transport communicates via stdin/stdout, making it suitable
    for CLI applications and process-based integrations.
    """

    def __init__(self, protocol_handler: MCPProtocolHandler):
        super().__init__(protocol_handler)
        self.running = False
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def start(self):
        """Start reading from stdin and writing to stdout."""
        self.running = True

        # Set up stdin/stdout streams
        loop = asyncio.get_event_loop()
        self.reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self.reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        transport, protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        self.writer = asyncio.StreamWriter(transport, protocol, self.reader, loop)

        # Start message processing loop
        await self._message_loop()

    async def stop(self):
        """Stop the stdio transport."""
        self.running = False
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

    async def send_message(self, message: JSONRPCResponse):
        """Send a message via stdout."""
        if not self.writer:
            raise RuntimeError('Transport not started')

        message_str = self.protocol_handler.serialize_message(message)
        self.writer.write(message_str.encode() + b'\n')
        await self.writer.drain()

    async def _message_loop(self):
        """Main message processing loop."""
        while self.running and self.reader:
            try:
                line = await self.reader.readline()
                if not line:
                    break

                message_str = line.decode().strip()
                if not message_str:
                    continue

                # Parse and handle message
                try:
                    message = self.protocol_handler.parse_message(message_str)
                    if isinstance(message, JSONRPCRequest) and self.message_handler:
                        response = await self.message_handler(message)
                        await self.send_message(response)
                    elif isinstance(message, JSONRPCNotification):
                        # Handle notifications (no response expected)
                        if self.message_handler:
                            await self.message_handler(message)

                except Exception as e:
                    logger.error(f'Error processing message: {e}')
                    if isinstance(message, JSONRPCRequest):
                        error_response = self.protocol_handler.create_error_response(
                            message.id, -32603, f'Internal error: {e}'
                        )
                        await self.send_message(error_response)

            except Exception as e:
                logger.error(f'Error in message loop: {e}')
                break


class HTTPTransport(MCPTransport):
    """
    HTTP transport for MCP using FastAPI.

    Provides traditional HTTP endpoints for MCP communication.
    """

    def __init__(
        self,
        protocol_handler: MCPProtocolHandler,
        host: str = 'localhost',
        port: int = 8000,
    ):
        super().__init__(protocol_handler)
        self.host = host
        self.port = port
        self.app = FastAPI(
            title='Thoth MCP Server',
            description='Model Context Protocol server for Thoth research assistant',
            version='1.0.0',
        )
        self.server: uvicorn.Server | None = None
        self._setup_routes()

    def _setup_routes(self):
        """Set up HTTP routes for MCP."""

        @self.app.post('/mcp')
        async def handle_mcp_request(request: Request) -> dict[str, Any]:
            """Handle MCP JSON-RPC requests."""
            try:
                body = await request.json()
                message = self.protocol_handler.parse_message(json.dumps(body))

                if isinstance(message, JSONRPCRequest) and self.message_handler:
                    response = await self.message_handler(message)
                    return json.loads(self.protocol_handler.serialize_message(response))
                else:
                    error_response = self.protocol_handler.create_error_response(
                        None, -32600, 'Invalid request'
                    )
                    return json.loads(
                        self.protocol_handler.serialize_message(error_response)
                    )

            except Exception as e:
                logger.error(f'Error handling HTTP request: {e}')
                error_response = self.protocol_handler.create_error_response(
                    None, -32603, f'Internal error: {e}'
                )
                return json.loads(
                    self.protocol_handler.serialize_message(error_response)
                )

        @self.app.get('/health')
        async def health_check():
            """Health check endpoint."""
            return {'status': 'ok', 'protocol': 'MCP', 'version': '2025-06-18'}

    async def start(self):
        """Start the HTTP server."""
        config = uvicorn.Config(
            app=self.app, host=self.host, port=self.port, log_level='info'
        )
        self.server = uvicorn.Server(config)
        await self.server.serve()

    async def stop(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.should_exit = True

    async def send_message(self, message: JSONRPCResponse):
        """HTTP transport doesn't send unsolicited messages."""
        pass  # HTTP is request-response only


class SSETransport(MCPTransport):
    """
    Server-Sent Events transport for MCP.

    Provides streaming communication with real-time updates.
    """

    def __init__(
        self,
        protocol_handler: MCPProtocolHandler,
        host: str = 'localhost',
        port: int = 8001,
    ):
        super().__init__(protocol_handler)
        self.host = host
        self.port = port
        self.app = FastAPI(
            title='Thoth MCP SSE Server',
            description='MCP Server with Server-Sent Events support',
            version='1.0.0',
        )
        self.clients: dict[str, asyncio.Queue] = {}
        self.server: uvicorn.Server | None = None
        self._setup_routes()

    def _setup_routes(self):
        """Set up SSE routes for MCP."""

        @self.app.post('/mcp')
        async def handle_mcp_request(request: Request) -> dict[str, Any]:
            """Handle MCP JSON-RPC requests."""
            try:
                body = await request.json()
                message = self.protocol_handler.parse_message(json.dumps(body))

                if isinstance(message, JSONRPCRequest) and self.message_handler:
                    response = await self.message_handler(message)
                    return json.loads(self.protocol_handler.serialize_message(response))
                else:
                    error_response = self.protocol_handler.create_error_response(
                        None, -32600, 'Invalid request'
                    )
                    return json.loads(
                        self.protocol_handler.serialize_message(error_response)
                    )

            except Exception as e:
                logger.error(f'Error handling SSE request: {e}')
                error_response = self.protocol_handler.create_error_response(
                    None, -32603, f'Internal error: {e}'
                )
                return json.loads(
                    self.protocol_handler.serialize_message(error_response)
                )

        @self.app.get('/events/{client_id}')
        async def sse_endpoint(client_id: str):
            """Server-Sent Events endpoint for real-time communication."""
            return StreamingResponse(
                self._event_stream(client_id),
                media_type='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'Access-Control-Allow-Origin': '*',
                },
            )

        @self.app.get('/health')
        async def health_check():
            """Health check endpoint."""
            return {'status': 'ok', 'protocol': 'MCP-SSE', 'version': '2025-06-18'}

    async def _event_stream(self, client_id: str) -> AsyncIterator[str]:
        """Generate Server-Sent Events stream for a client."""
        # Create a queue for this client
        queue = asyncio.Queue()
        self.clients[client_id] = queue

        try:
            while True:
                # Wait for messages to send to this client
                message = await queue.get()
                yield f'data: {message}\n\n'
        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            # Clean up client queue
            if client_id in self.clients:
                del self.clients[client_id]

    async def start(self):
        """Start the SSE server."""
        config = uvicorn.Config(
            app=self.app, host=self.host, port=self.port, log_level='info'
        )
        self.server = uvicorn.Server(config)
        await self.server.serve()

    async def stop(self):
        """Stop the SSE server."""
        if self.server:
            self.server.should_exit = True
        # Clear all client queues
        self.clients.clear()

    async def send_message(
        self, message: JSONRPCResponse, client_id: str | None = None
    ):
        """Send a message via SSE to specific client or all clients."""
        message_str = self.protocol_handler.serialize_message(message)

        if client_id and client_id in self.clients:
            await self.clients[client_id].put(message_str)
        else:
            # Broadcast to all clients
            for queue in self.clients.values():
                try:
                    await queue.put(message_str)
                except Exception as e:
                    logger.error(f'Error sending message to client: {e}')


class TransportManager:
    """
    Manager for multiple MCP transports.

    Allows running multiple transport types simultaneously.
    """

    def __init__(self, protocol_handler: MCPProtocolHandler):
        self.protocol_handler = protocol_handler
        self.transports: dict[str, MCPTransport] = {}
        self.running = False

    def add_transport(self, name: str, transport: MCPTransport):
        """Add a transport to the manager."""
        transport.set_message_handler(self._handle_message)
        self.transports[name] = transport

    async def start_all(self):
        """Start all registered transports."""
        self.running = True
        tasks = []

        for name, transport in self.transports.items():
            logger.info(f'Starting transport: {name}')
            task = asyncio.create_task(transport.start())
            tasks.append(task)

        # Wait for all transports to start
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self):
        """Stop all registered transports."""
        self.running = False
        tasks = []

        for name, transport in self.transports.items():
            logger.info(f'Stopping transport: {name}')
            task = asyncio.create_task(transport.stop())
            tasks.append(task)

        # Wait for all transports to stop
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_message(self, message: JSONRPCRequest) -> JSONRPCResponse:
        """Handle incoming messages from any transport."""
        # This will be implemented by the MCP server
        # For now, return a method not found error
        return self.protocol_handler.create_error_response(
            message.id, -32601, 'Method not found'
        )

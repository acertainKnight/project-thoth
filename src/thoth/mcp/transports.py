"""
MCP Transport implementations with per-user identity resolution.

This module provides transport implementations for the Model Context Protocol
including stdio, HTTP, and Server-Sent Events transports.

In multi-user mode the HTTP and SSE transports resolve bearer tokens to a
UserContext via AuthService.  The resolved identity is propagated through
ContextVars so all downstream services/repositories operate in the correct
user scope.  Stdio transport relies on the THOTH_MCP_USER_ID environment
variable per the MCP spec recommendation for local transports.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from loguru import logger

from thoth.mcp.auth import (
    is_multi_user_mode,
    reset_current_user_context,
    set_current_user_context,
)
from thoth.mcp.protocol import (
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    MCPProtocolHandler,
)

if TYPE_CHECKING:
    from pathlib import Path

    from thoth.auth.context import UserContext
    from thoth.services.service_manager import ServiceManager


class MCPTransport:
    """Base class for MCP transports."""

    def __init__(self, protocol_handler: MCPProtocolHandler):
        self.protocol_handler = protocol_handler
        self.message_handler: Callable[[JSONRPCRequest], JSONRPCResponse] | None = None
        self.running = False

    def set_message_handler(self, handler: Callable[[JSONRPCRequest], JSONRPCResponse]):
        """Set the message handler for this transport."""
        self.message_handler = handler

    async def start(self):
        """Start the transport."""
        self.running = True

    async def stop(self):
        """Stop the transport."""
        self.running = False

    async def send_message(self, message: JSONRPCResponse):
        """Send a message through the transport."""
        raise NotImplementedError


async def _resolve_bearer_user(
    request: Request,
    service_manager: ServiceManager | None,
    vaults_root: Path | None,
) -> UserContext | None:
    """Resolve a bearer token from an HTTP request to a UserContext.

    Args:
        request: FastAPI request with Authorization header.
        service_manager: ServiceManager holding AuthService.
        vaults_root: Root directory for per-user vaults.

    Returns:
        UserContext if the token is valid, None otherwise.
    """
    if not service_manager or not vaults_root:
        return None

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]
    if not token:
        return None

    try:
        auth_service = getattr(service_manager, 'auth', None)
        if auth_service is None:
            return None
        return await auth_service.get_user_context_from_token(token, vaults_root)
    except Exception as e:
        logger.debug(f'MCP transport token resolution failed: {e}')
        return None


class StdioTransport(MCPTransport):
    """
    Stdio transport for MCP.

    Uses stdin/stdout for communication.  In multi-user mode the user
    identity is read from THOTH_MCP_USER_ID and THOTH_MCP_USERNAME
    environment variables set by the spawning process.
    """

    def __init__(self, protocol_handler: MCPProtocolHandler):
        super().__init__(protocol_handler)
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._ctx_tokens: list | None = None

    async def start(self):
        """Start the stdio transport."""
        await super().start()

        if is_multi_user_mode():
            self._set_user_from_env()

        self.reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self.reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        transport, protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        self.writer = asyncio.StreamWriter(
            transport, protocol, self.reader, asyncio.get_event_loop()
        )

        self.message_loop_task = asyncio.create_task(self._message_loop())

    async def stop(self):
        """Stop the transport and clean up user context."""
        if self._ctx_tokens:
            reset_current_user_context(self._ctx_tokens)
            self._ctx_tokens = None
        await super().stop()

    def _set_user_from_env(self) -> None:
        """Populate ContextVars from environment for the stdio session."""
        from thoth.config import config

        user_id = os.environ.get('THOTH_MCP_USER_ID', '')
        username = os.environ.get('THOTH_MCP_USERNAME', '')
        vaults_root = getattr(config, 'vaults_root', None)

        if user_id and username and vaults_root:
            vault_path = vaults_root / username
            self._ctx_tokens = set_current_user_context(user_id, username, vault_path)
            logger.info(f'Stdio transport bound to user {username}')

    async def send_message(self, message: JSONRPCResponse):
        """Send a JSON-RPC message via stdout."""
        if not self.writer:
            return

        message_str = self.protocol_handler.serialize_message(message)
        self.writer.write(f'{message_str}\n'.encode())
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

                try:
                    message = self.protocol_handler.parse_message(message_str)
                    if isinstance(message, JSONRPCRequest) and self.message_handler:
                        response = await self.message_handler(message)
                        await self.send_message(response)
                    elif isinstance(message, JSONRPCNotification):
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

    Provides HTTP endpoints for MCP communication.  In multi-user mode,
    bearer tokens are resolved to a UserContext via AuthService so that
    every tool call runs in the correct user scope.  In single-user mode
    a static auth_token gate is supported for backward compatibility.
    """

    def __init__(
        self,
        protocol_handler: MCPProtocolHandler,
        host: str = 'localhost',
        port: int = 8000,
        auth_token: str | None = None,
        service_manager: ServiceManager | None = None,
    ):
        super().__init__(protocol_handler)
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.service_manager = service_manager
        self.app = FastAPI(
            title='Thoth MCP Server',
            description='Model Context Protocol server for Thoth research assistant',
            version='1.0.0',
        )
        self.server: uvicorn.Server | None = None
        self._setup_routes()

    @property
    def _vaults_root(self) -> Path | None:
        from thoth.config import config

        return getattr(config, 'vaults_root', None)

    async def _authenticate(self, request: Request) -> tuple[bool, UserContext | None]:
        """Authenticate the request and optionally resolve user identity.

        Returns:
            (allowed, user_context) -- allowed is True when the request may
            proceed.  user_context is non-None in multi-user mode when the
            bearer token maps to a valid user.
        """
        if is_multi_user_mode():
            user_ctx = await _resolve_bearer_user(
                request, self.service_manager, self._vaults_root
            )
            return (user_ctx is not None, user_ctx)

        if not self.auth_token:
            return (True, None)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return (False, None)
        return (auth_header[7:] == self.auth_token, None)

    def _setup_routes(self):
        """Set up HTTP routes for MCP."""

        @self.app.post('/mcp')
        async def handle_mcp_request(request: Request):
            """Handle MCP JSON-RPC requests and notifications."""
            allowed, user_ctx = await self._authenticate(request)
            if not allowed:
                return Response(
                    status_code=401,
                    content=json.dumps(
                        {
                            'jsonrpc': '2.0',
                            'error': {
                                'code': -32001,
                                'message': 'Unauthorized - invalid or missing bearer token',
                            },
                            'id': None,
                        }
                    ),
                    media_type='application/json',
                )

            ctx_tokens = None
            if user_ctx:
                ctx_tokens = set_current_user_context(
                    user_ctx.user_id, user_ctx.username, user_ctx.vault_path
                )

            try:
                body = await request.json()
                message = self.protocol_handler.parse_message(json.dumps(body))

                if isinstance(message, JSONRPCRequest) and self.message_handler:
                    response = await self.message_handler(message)
                    return json.loads(self.protocol_handler.serialize_message(response))
                elif isinstance(message, JSONRPCNotification) and self.message_handler:
                    await self._handle_notification(message)
                    return Response(status_code=204)
                else:
                    error_response = self.protocol_handler.create_error_response(
                        None, -32600, 'Invalid request'
                    )
                    return json.loads(
                        self.protocol_handler.serialize_message(error_response)
                    )

            except Exception as e:
                logger.exception('Error handling HTTP request: %s', e)
                error_response = self.protocol_handler.create_error_response(
                    None, -32603, f'Internal error: {e}'
                )
                serialized = self.protocol_handler.serialize_message(error_response)
                logger.debug(f'MCP Exception Response: {serialized}')
                return json.loads(serialized)
            finally:
                if ctx_tokens:
                    reset_current_user_context(ctx_tokens)

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
        # Create background task instead of blocking
        self._server_task = asyncio.create_task(self.server.serve())
        # Wait a moment for server to start
        await asyncio.sleep(0.5)

    async def stop(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.should_exit = True
            if hasattr(self, '_server_task'):
                await self._server_task

    async def send_message(self, message: JSONRPCResponse):
        """HTTP transport doesn't send unsolicited messages."""
        pass  # HTTP is request-response only

    async def _handle_notification(self, notification: JSONRPCNotification):
        """Handle JSON-RPC notifications that don't require responses."""
        try:
            method = notification.method
            logger.debug(f'Handling MCP notification: {method}')

            # Call the message handler but don't expect a response
            # Since it's a notification, we just execute the handler
            if method == 'initialized':
                # Handle the initialized notification specifically
                if hasattr(self.message_handler, '__self__'):
                    server = self.message_handler.__self__
                    if hasattr(server, 'protocol_handler'):
                        server.protocol_handler.initialized = True
                        logger.debug('MCP protocol marked as initialized')
            else:
                # For other notifications, we could handle them here if needed
                logger.debug(f'Received notification: {method}')

        except Exception as e:
            logger.error(f'Error handling notification {notification.method}: {e}')


class SSETransport(MCPTransport):
    """
    Server-Sent Events transport for MCP with per-session user binding.

    When a client opens an SSE connection with a bearer token the user
    identity is resolved once and stored for the lifetime of that session.
    Subsequent POST /mcp requests that arrive on behalf of the same
    session carry the same user context automatically.
    """

    def __init__(
        self,
        protocol_handler: MCPProtocolHandler,
        host: str = 'localhost',
        port: int = 8001,
        auth_token: str | None = None,
        service_manager: ServiceManager | None = None,
    ):
        super().__init__(protocol_handler)
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.service_manager = service_manager
        self.app = FastAPI(
            title='Thoth MCP SSE Server',
            description='MCP Server with Server-Sent Events support',
            version='1.0.0',
        )
        self.clients: dict[str, asyncio.Queue] = {}
        self._session_users: dict[str, UserContext] = {}
        self.server: uvicorn.Server | None = None
        self._setup_routes()

    @property
    def _vaults_root(self) -> Path | None:
        from thoth.config import config

        return getattr(config, 'vaults_root', None)

    async def _authenticate(self, request: Request) -> tuple[bool, UserContext | None]:
        """Authenticate and optionally resolve user from bearer token."""
        if is_multi_user_mode():
            user_ctx = await _resolve_bearer_user(
                request, self.service_manager, self._vaults_root
            )
            return (user_ctx is not None, user_ctx)

        if not self.auth_token:
            return (True, None)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return (False, None)
        return (auth_header[7:] == self.auth_token, None)

    def _setup_routes(self):
        """Set up SSE routes for MCP."""

        @self.app.post('/mcp')
        async def handle_mcp_request(request: Request):
            """Handle MCP JSON-RPC requests."""
            allowed, user_ctx = await self._authenticate(request)
            if not allowed:
                return Response(
                    status_code=401,
                    content=json.dumps(
                        {
                            'jsonrpc': '2.0',
                            'error': {
                                'code': -32001,
                                'message': 'Unauthorized - invalid or missing bearer token',
                            },
                            'id': None,
                        }
                    ),
                    media_type='application/json',
                )

            ctx_tokens = None
            if user_ctx:
                ctx_tokens = set_current_user_context(
                    user_ctx.user_id, user_ctx.username, user_ctx.vault_path
                )

            try:
                body = await request.json()
                message = self.protocol_handler.parse_message(json.dumps(body))

                if isinstance(message, JSONRPCRequest) and self.message_handler:
                    response = await self.message_handler(message)
                    return json.loads(self.protocol_handler.serialize_message(response))
                elif isinstance(message, JSONRPCNotification) and self.message_handler:
                    await self._handle_notification(message)
                    return Response(status_code=204)
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
            finally:
                if ctx_tokens:
                    reset_current_user_context(ctx_tokens)

        @self.app.get('/sse')
        async def sse_endpoint_standard(request: Request):
            """Standard SSE endpoint for MCP clients (Letta compatibility).

            The bearer token is resolved to a user at connect time and
            stored for the session lifetime so that POST /mcp calls
            within this session inherit the same identity.
            """
            allowed, user_ctx = await self._authenticate(request)
            if not allowed:
                return Response(
                    status_code=401,
                    content='Unauthorized - invalid or missing bearer token',
                    media_type='text/plain',
                )

            import uuid

            client_id = str(uuid.uuid4())
            if user_ctx:
                self._session_users[client_id] = user_ctx
                logger.info(
                    f'SSE session {client_id} bound to user {user_ctx.username}'
                )

            async def event_stream():
                queue: asyncio.Queue = asyncio.Queue()
                self.clients[client_id] = queue

                try:
                    while True:
                        message = await queue.get()
                        yield f'data: {json.dumps(message)}\n\n'
                except asyncio.CancelledError:
                    pass
                finally:
                    self.clients.pop(client_id, None)
                    self._session_users.pop(client_id, None)

            return StreamingResponse(
                event_stream(),
                media_type='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Cache-Control, Authorization',
                },
            )

        @self.app.get('/events/{client_id}')
        async def sse_endpoint(client_id: str, request: Request):
            """Per-client SSE endpoint for real-time updates."""
            allowed, user_ctx = await self._authenticate(request)
            if not allowed:
                return Response(
                    status_code=401,
                    content='Unauthorized - invalid or missing bearer token',
                    media_type='text/plain',
                )

            if user_ctx:
                self._session_users[client_id] = user_ctx

            async def event_stream():
                queue: asyncio.Queue = asyncio.Queue()
                self.clients[client_id] = queue

                try:
                    while True:
                        message = await queue.get()
                        yield f'data: {json.dumps(message)}\n\n'
                except asyncio.CancelledError:
                    pass
                finally:
                    self.clients.pop(client_id, None)
                    self._session_users.pop(client_id, None)

            return StreamingResponse(
                event_stream(),
                media_type='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Cache-Control, Authorization',
                },
            )

        @self.app.get('/health')
        async def health_check():
            """Health check endpoint."""
            return {'status': 'ok', 'protocol': 'MCP-SSE', 'version': '2025-06-18'}

    async def start(self):
        """Start the SSE server."""
        config = uvicorn.Config(
            app=self.app, host=self.host, port=self.port, log_level='info'
        )
        self.server = uvicorn.Server(config)
        # Create background task instead of blocking
        self._server_task = asyncio.create_task(self.server.serve())
        # Wait a moment for server to start
        await asyncio.sleep(0.5)

    async def stop(self):
        """Stop the SSE server."""
        if self.server:
            self.server.should_exit = True
            if hasattr(self, '_server_task'):
                await self._server_task

    async def send_message(
        self, message: JSONRPCResponse, client_id: str | None = None
    ):
        """Send a message via SSE to specific client or all clients."""
        message_data = json.loads(self.protocol_handler.serialize_message(message))

        if client_id and client_id in self.clients:
            # Send to specific client
            await self.clients[client_id].put(message_data)
        else:
            # Broadcast to all clients
            for queue in self.clients.values():
                try:
                    await queue.put(message_data)
                except Exception as e:
                    logger.error(f'Error sending SSE message: {e}')

    async def _handle_notification(self, notification: JSONRPCNotification):
        """Handle JSON-RPC notifications for SSE transport."""
        try:
            method = notification.method
            logger.debug(f'Handling SSE notification: {method}')

            # For SSE, we might want to broadcast notifications to connected clients
            notification_data = {
                'type': 'notification',
                'method': method,
                'params': notification.params,
            }

            # Broadcast to all connected clients
            for queue in self.clients.values():
                try:
                    await queue.put(notification_data)
                except Exception as e:
                    logger.error(f'Error broadcasting notification: {e}')

        except Exception as e:
            logger.error(f'Error handling SSE notification {notification.method}: {e}')


class TransportManager:
    """Manages multiple MCP transports."""

    def __init__(self, protocol_handler: MCPProtocolHandler):
        self.protocol_handler = protocol_handler
        self.transports: dict[str, MCPTransport] = {}
        self._handle_message: Callable[[JSONRPCRequest], JSONRPCResponse] | None = None

    def add_transport(self, name: str, transport: MCPTransport):
        """Add a transport to the manager."""
        transport.set_message_handler(self._handle_message)
        self.transports[name] = transport

    def set_message_handler(self, handler: Callable[[JSONRPCRequest], JSONRPCResponse]):
        """Set the message handler for all transports."""
        self._handle_message = handler
        for transport in self.transports.values():
            transport.set_message_handler(handler)

    async def start_transport(self, name: str):
        """Start a specific transport."""
        if name in self.transports:
            await self.transports[name].start()

    async def stop_transport(self, name: str):
        """Stop a specific transport."""
        if name in self.transports:
            await self.transports[name].stop()

    async def start_all(self):
        """Start all transports."""
        from loguru import logger

        failed_transports = []
        for name, transport in self.transports.items():
            try:
                await transport.start()
                logger.info(f'Started MCP transport: {name}')
            except OSError as e:
                if e.errno == 98:  # Address already in use
                    logger.warning(
                        f"MCP transport '{name}' failed to start - port already in use: {e}"
                    )
                    logger.info(
                        f'Consider changing the port for {name} transport in configuration'
                    )
                    failed_transports.append(name)
                else:
                    logger.error(
                        f"MCP transport '{name}' failed to start with OS error: {e}"
                    )
                    failed_transports.append(name)
            except Exception as e:
                logger.error(f"MCP transport '{name}' failed to start: {e}")
                failed_transports.append(name)

        if failed_transports and len(failed_transports) == len(self.transports):
            # All transports failed to start
            raise RuntimeError(
                f'All MCP transports failed to start: {", ".join(failed_transports)}'
            )
        elif failed_transports:
            # Some transports failed, but at least one succeeded
            logger.warning(
                f'Some MCP transports failed to start: {", ".join(failed_transports)}'
            )
            logger.info(
                f'MCP server will continue with {len(self.transports) - len(failed_transports)} working transports'
            )

    async def stop_all(self):
        """Stop all transports."""
        for transport in self.transports.values():
            await transport.stop()

"""
Fixtures for MCP server testing.

Provides reusable test fixtures for server lifecycle, transport mocking,
and test data generation.
"""

import asyncio
import json  # noqa: F401
import random
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock  # noqa: F401

import pytest

from thoth.config import Config
from thoth.mcp.protocol import (
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    MCPCapabilities,
    MCPProtocolHandler,
    MCPServerInfo,
)
from thoth.mcp.server import MCPServer
from thoth.mcp.transports import (
    HTTPTransport,
    SSETransport,
    StdioTransport,
    TransportManager,
)
from thoth.services.service_manager import ServiceManager


@pytest.fixture
def test_config():
    """Create test configuration."""
    config = Config()
    config.database.url = 'sqlite:///:memory:'
    config.api.openai_api_key = 'test-key-for-integration'
    return config


@pytest.fixture
def mock_service_manager():
    """Create mock service manager for testing."""
    manager = Mock(spec=ServiceManager)
    manager.config = Config()

    # Mock LLM service
    manager.llm = Mock()
    manager.llm.generate_chat_completion = AsyncMock(
        return_value={'content': 'Test response'}
    )

    # Mock article service
    manager.article = Mock()
    manager.article.search_articles = AsyncMock(return_value=[])
    manager.article.get_article = AsyncMock(return_value=None)

    # Mock discovery service
    manager.discovery = Mock()
    manager.discovery.search_papers = AsyncMock(return_value=[])

    return manager


@pytest.fixture
def protocol_handler():
    """Create protocol handler instance."""
    return MCPProtocolHandler()


@pytest.fixture
def server_info():
    """Create server info for testing."""
    return MCPServerInfo(name='Test MCP Server', version='1.0.0-test')


@pytest.fixture
def capabilities():
    """Create server capabilities."""
    return MCPCapabilities(
        tools={'listChanged': True},
        resources={'subscribe': True, 'listChanged': True},
        prompts={'listChanged': True},
        logging={},
    )


@pytest.fixture
async def mcp_server(mock_service_manager, server_info):
    """Create MCP server instance for testing."""
    server = MCPServer(
        service_manager=mock_service_manager,
        server_name=server_info.name,
        server_version=server_info.version,
    )

    yield server

    # Cleanup
    try:
        await server.stop()
    except Exception:
        pass


@pytest.fixture
async def mcp_server_with_transports(mcp_server):
    """Create MCP server with all transports configured."""
    # Use random ports to avoid conflicts in parallel tests
    http_port = random.randint(9000, 9500)
    sse_port = random.randint(9501, 9999)

    mcp_server.add_http_transport('127.0.0.1', http_port)
    mcp_server.add_sse_transport('127.0.0.1', sse_port)
    mcp_server.add_stdio_transport()

    yield mcp_server

    # Cleanup
    await mcp_server.stop()


@pytest.fixture
def mock_stdio_transport():
    """Create mock stdio transport."""
    transport = Mock(spec=StdioTransport)
    transport.start = AsyncMock()
    transport.stop = AsyncMock()
    transport.send_message = AsyncMock()
    transport.receive_message = AsyncMock()
    return transport


@pytest.fixture
def mock_http_transport():
    """Create mock HTTP transport."""
    transport = Mock(spec=HTTPTransport)
    transport.start = AsyncMock()
    transport.stop = AsyncMock()
    transport.handle_request = AsyncMock()
    transport.host = 'localhost'
    transport.port = 8000
    return transport


@pytest.fixture
def mock_sse_transport():
    """Create mock SSE transport."""
    transport = Mock(spec=SSETransport)
    transport.start = AsyncMock()
    transport.stop = AsyncMock()
    transport.send_event = AsyncMock()
    transport.host = 'localhost'
    transport.port = 8001
    return transport


@pytest.fixture
def transport_manager(protocol_handler):
    """Create transport manager for testing."""
    manager = TransportManager(protocol_handler)
    return manager


class MockTransport:
    """Mock transport implementation for testing."""

    def __init__(self, name: str):
        self.name = name
        self.started = False
        self.stopped = False
        self.messages_sent = []
        self.messages_received = []

    async def start(self):
        """Start the transport."""
        self.started = True

    async def stop(self):
        """Stop the transport."""
        self.stopped = True

    async def send_message(self, message: dict[str, Any]):
        """Send a message."""
        self.messages_sent.append(message)

    async def receive_message(self) -> dict[str, Any] | None:
        """Receive a message."""
        if self.messages_received:
            return self.messages_received.pop(0)
        return None


@pytest.fixture
def mock_transports():
    """Create multiple mock transports."""
    return {
        'stdio': MockTransport('stdio'),
        'http': MockTransport('http'),
        'sse': MockTransport('sse'),
    }


def create_jsonrpc_request(
    method: str, params: dict[str, Any] | None = None, request_id: int | str = 1
) -> JSONRPCRequest:
    """Helper to create JSONRPC request."""
    return JSONRPCRequest(
        jsonrpc='2.0', id=request_id, method=method, params=params or {}
    )


def create_jsonrpc_notification(
    method: str, params: dict[str, Any] | None = None
) -> JSONRPCNotification:
    """Helper to create JSONRPC notification."""
    return JSONRPCNotification(jsonrpc='2.0', method=method, params=params or {})


def create_initialize_request(
    client_name: str = 'Test Client', client_version: str = '1.0.0'
) -> JSONRPCRequest:
    """Create initialize request."""
    return create_jsonrpc_request(
        method='initialize',
        params={
            'protocolVersion': '2024-11-05',
            'clientInfo': {'name': client_name, 'version': client_version},
            'capabilities': {},
        },
    )


def create_tools_list_request() -> JSONRPCRequest:
    """Create tools/list request."""
    return create_jsonrpc_request(method='tools/list')


def create_tools_call_request(
    tool_name: str, arguments: dict[str, Any] | None = None
) -> JSONRPCRequest:
    """Create tools/call request."""
    return create_jsonrpc_request(
        method='tools/call', params={'name': tool_name, 'arguments': arguments or {}}
    )


@pytest.fixture
def sample_requests():
    """Generate sample MCP requests."""
    return {
        'initialize': create_initialize_request(),
        'initialized': create_jsonrpc_notification('initialized'),
        'tools_list': create_tools_list_request(),
        'tools_call': create_tools_call_request('search_papers', {'query': 'test'}),
        'health': create_jsonrpc_request('health'),
    }


class ServerLifecycleHelper:
    """Helper class for server lifecycle testing."""

    def __init__(self):
        self.servers = []
        self.cleanup_tasks = []

    async def create_server(
        self,
        service_manager: ServiceManager,
        enable_stdio: bool = False,
        enable_http: bool = False,
        enable_sse: bool = False,
    ) -> MCPServer:
        """Create and configure a server."""
        server = MCPServer(service_manager)

        if enable_stdio:
            server.add_stdio_transport()
        if enable_http:
            http_port = random.randint(9000, 9500)
            server.add_http_transport('127.0.0.1', http_port)
        if enable_sse:
            sse_port = random.randint(9501, 9999)
            server.add_sse_transport('127.0.0.1', sse_port)

        self.servers.append(server)
        return server

    async def cleanup_all(self):
        """Clean up all created servers."""
        for server in self.servers:
            try:
                await server.stop()
            except Exception:
                pass

        for task in self.cleanup_tasks:
            try:
                task.cancel()
                await task
            except asyncio.CancelledError:
                pass

        self.servers.clear()
        self.cleanup_tasks.clear()


@pytest.fixture
async def server_lifecycle_helper():
    """Provide server lifecycle helper."""
    helper = ServerLifecycleHelper()
    yield helper
    await helper.cleanup_all()


class MessageCollector:
    """Collect messages for testing."""

    def __init__(self):
        self.requests = []
        self.responses = []
        self.notifications = []

    def add_request(self, request: JSONRPCRequest):
        """Add a request."""
        self.requests.append(request)

    def add_response(self, response: JSONRPCResponse):
        """Add a response."""
        self.responses.append(response)

    def add_notification(self, notification: JSONRPCNotification):
        """Add a notification."""
        self.notifications.append(notification)

    def get_request_by_id(self, request_id: int | str) -> JSONRPCRequest | None:
        """Get request by ID."""
        for req in self.requests:
            if req.id == request_id:
                return req
        return None

    def get_response_by_id(self, request_id: int | str) -> JSONRPCResponse | None:
        """Get response by ID."""
        for resp in self.responses:
            if resp.id == request_id:
                return resp
        return None

    def clear(self):
        """Clear all messages."""
        self.requests.clear()
        self.responses.clear()
        self.notifications.clear()


@pytest.fixture
def message_collector():
    """Provide message collector."""
    return MessageCollector()


class HealthCheckSimulator:
    """Simulate health check cycles."""

    def __init__(self, server: MCPServer):
        self.server = server
        self.check_count = 0
        self.results = []

    async def run_check(self) -> dict[str, Any]:
        """Run a single health check."""
        self.check_count += 1

        # Create health check request
        request = create_jsonrpc_request(
            'health', request_id=f'health-{self.check_count}'
        )

        # Send to server
        response = await self.server._handle_message(request)

        result = {
            'check_id': self.check_count,
            'timestamp': time.time(),
            'response': response,
            'healthy': response and not hasattr(response, 'error'),
        }

        self.results.append(result)
        return result

    async def run_multiple_checks(self, count: int, interval: float = 0.1):
        """Run multiple health checks with interval."""
        for _ in range(count):
            await self.run_check()
            await asyncio.sleep(interval)

    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if not self.results:
            return 0.0
        successful = sum(1 for r in self.results if r['healthy'])
        return successful / len(self.results)


@pytest.fixture
def health_check_simulator(mcp_server):
    """Provide health check simulator."""
    return HealthCheckSimulator(mcp_server)


class ErrorInjector:
    """Inject errors for testing recovery."""

    def __init__(self):
        self.error_handlers = {}

    def inject_transport_error(self, transport: Any, error_type: str = 'connection'):
        """Inject transport error."""
        if error_type == 'connection':
            transport.start = AsyncMock(
                side_effect=ConnectionError('Connection failed')
            )
        elif error_type == 'timeout':

            async def timeout_error():
                await asyncio.sleep(10)

            transport.start = timeout_error
        elif error_type == 'crash':
            transport.start = AsyncMock(side_effect=RuntimeError('Transport crashed'))

    def inject_tool_error(
        self,
        tool_registry: Any,
        tool_name: str,
        error_message: str = 'Tool execution failed',
    ):
        """Inject tool execution error."""
        original_execute = tool_registry.execute_tool

        async def error_execute(name, args):
            if name == tool_name:
                raise RuntimeError(error_message)
            return await original_execute(name, args)

        tool_registry.execute_tool = error_execute

    def inject_protocol_error(self, protocol_handler: Any, error_code: int = -32603):
        """Inject protocol error."""
        protocol_handler.create_response = Mock(
            return_value=JSONRPCResponse(
                jsonrpc='2.0',
                id=1,
                error={'code': error_code, 'message': 'Protocol error'},
            )
        )


@pytest.fixture
def error_injector():
    """Provide error injector."""
    return ErrorInjector()

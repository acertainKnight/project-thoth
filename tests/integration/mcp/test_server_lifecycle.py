"""
Integration tests for MCP server lifecycle.

Tests server initialization, transport management, startup/shutdown,
and protocol message handling throughout the server lifecycle.
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock

import pytest

from thoth.mcp.protocol import JSONRPCRequest, MCPErrorCodes
from thoth.mcp.server import MCPServer
from thoth.services.service_manager import ServiceManager


class TestServerInitialization:
    """Test server initialization with ServiceManager."""

    @pytest.mark.asyncio
    async def test_basic_initialization(self, mock_service_manager):
        """Test basic server initialization."""
        server = MCPServer(
            service_manager=mock_service_manager,
            server_name='Test Server',
            server_version='1.0.0'
        )

        assert server.server_info.name == 'Test Server'
        assert server.server_info.version == '1.0.0'
        assert server.service_manager is mock_service_manager
        assert server.protocol_handler is not None
        assert server.tool_registry is not None
        assert server.resource_manager is not None
        assert server.transport_manager is not None

    @pytest.mark.asyncio
    async def test_initialization_with_custom_capabilities(self, mock_service_manager):
        """Test initialization with custom capabilities."""
        server = MCPServer(mock_service_manager)

        # Verify default capabilities
        assert server.capabilities.tools is not None
        assert server.capabilities.resources is not None
        assert server.capabilities.prompts is not None
        assert server.capabilities.logging is not None

    @pytest.mark.asyncio
    async def test_multiple_server_instances(self, mock_service_manager):
        """Test creating multiple server instances."""
        servers = []

        for i in range(3):
            server = MCPServer(
                service_manager=mock_service_manager,
                server_name=f'Server {i}',
                server_version=f'1.0.{i}'
            )
            servers.append(server)

        # Verify each server is independent
        for i, server in enumerate(servers):
            assert server.server_info.name == f'Server {i}'
            assert server.server_info.version == f'1.0.{i}'

        # Cleanup
        for server in servers:
            await server.stop()


class TestTransportManagement:
    """Test transport addition and management."""

    @pytest.mark.asyncio
    async def test_add_stdio_transport(self, mcp_server):
        """Test adding stdio transport."""
        mcp_server.add_stdio_transport()

        assert 'stdio' in mcp_server.transport_manager.transports

    @pytest.mark.asyncio
    async def test_add_http_transport(self, mcp_server):
        """Test adding HTTP transport."""
        mcp_server.add_http_transport('127.0.0.1', 9001)

        assert 'http' in mcp_server.transport_manager.transports
        transport = mcp_server.transport_manager.transports['http']
        assert transport.host == '127.0.0.1'
        assert transport.port == 9001

    @pytest.mark.asyncio
    async def test_add_sse_transport(self, mcp_server):
        """Test adding SSE transport."""
        mcp_server.add_sse_transport('127.0.0.1', 9002)

        assert 'sse' in mcp_server.transport_manager.transports
        transport = mcp_server.transport_manager.transports['sse']
        assert transport.host == '127.0.0.1'
        assert transport.port == 9002

    @pytest.mark.asyncio
    async def test_add_multiple_transports(self, mcp_server):
        """Test adding multiple transports."""
        mcp_server.add_stdio_transport()
        mcp_server.add_http_transport('127.0.0.1', 9003)
        mcp_server.add_sse_transport('127.0.0.1', 9004)

        transports = mcp_server.transport_manager.transports
        assert len(transports) == 3
        assert 'stdio' in transports
        assert 'http' in transports
        assert 'sse' in transports

    @pytest.mark.asyncio
    async def test_transport_registration_order(self, mcp_server):
        """Test that transport order doesn't affect functionality."""
        # Add in different order
        mcp_server.add_sse_transport('127.0.0.1', 9005)
        mcp_server.add_stdio_transport()
        mcp_server.add_http_transport('127.0.0.1', 9006)

        # All should be registered
        assert len(mcp_server.transport_manager.transports) == 3


class TestServerStartStop:
    """Test server start and stop operations."""

    @pytest.mark.asyncio
    async def test_start_server_with_stdio(self, mcp_server, mock_stdio_transport):
        """Test starting server with stdio transport."""
        # Replace with mock transport
        mcp_server.transport_manager.transports['stdio'] = mock_stdio_transport

        await mcp_server.start()

        mock_stdio_transport.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_server_with_all_transports(
        self,
        mcp_server,
        mock_stdio_transport,
        mock_http_transport,
        mock_sse_transport
    ):
        """Test starting server with all transports."""
        mcp_server.transport_manager.transports = {
            'stdio': mock_stdio_transport,
            'http': mock_http_transport,
            'sse': mock_sse_transport
        }

        await mcp_server.start()

        mock_stdio_transport.start.assert_called_once()
        mock_http_transport.start.assert_called_once()
        mock_sse_transport.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_server(self, mcp_server, mock_stdio_transport):
        """Test stopping server."""
        mcp_server.transport_manager.transports['stdio'] = mock_stdio_transport

        await mcp_server.start()
        await mcp_server.stop()

        mock_stdio_transport.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_stop_multiple_times(self, mcp_server, mock_stdio_transport):
        """Test starting and stopping server multiple times."""
        mcp_server.transport_manager.transports['stdio'] = mock_stdio_transport

        # Start and stop 3 times
        for _ in range(3):
            await mcp_server.start()
            await mcp_server.stop()

        # Should have been called 3 times each
        assert mock_stdio_transport.start.call_count == 3
        assert mock_stdio_transport.stop.call_count == 3

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, mcp_server):
        """Test graceful shutdown with cleanup."""
        mcp_server.add_http_transport('127.0.0.1', 9007)

        start_time = time.time()
        await mcp_server.start()

        # Ensure server had time to start
        await asyncio.sleep(0.1)

        await mcp_server.stop()
        elapsed = time.time() - start_time

        # Should complete quickly (< 5 seconds)
        assert elapsed < 5.0


class TestProtocolMessageHandling:
    """Test protocol message handling."""

    @pytest.mark.asyncio
    async def test_handle_initialize_request(self, mcp_server, sample_requests):
        """Test handling initialize request."""
        request = sample_requests['initialize']

        response = await mcp_server._handle_message(request)

        assert response is not None
        assert response.id == request.id
        assert not hasattr(response, 'error')
        assert 'serverInfo' in response.result
        assert 'capabilities' in response.result

    @pytest.mark.asyncio
    async def test_handle_initialized_notification(self, mcp_server, sample_requests):
        """Test handling initialized notification."""
        notification = sample_requests['initialized']

        # Initialize first
        await mcp_server._handle_message(sample_requests['initialize'])

        # Then send initialized notification
        response = await mcp_server._handle_message(notification)

        # Should return None for notifications
        assert response is None
        assert mcp_server.protocol_handler.initialized is True

    @pytest.mark.asyncio
    async def test_handle_tools_list_request(self, mcp_server, sample_requests):
        """Test handling tools/list request."""
        request = sample_requests['tools_list']

        response = await mcp_server._handle_message(request)

        assert response is not None
        assert response.id == request.id
        assert 'tools' in response.result
        assert isinstance(response.result['tools'], list)

    @pytest.mark.asyncio
    async def test_handle_health_request(self, mcp_server, sample_requests):
        """Test handling health check request."""
        request = sample_requests['health']

        response = await mcp_server._handle_message(request)

        assert response is not None
        assert 'status' in response.result
        assert response.result['status'] == 'healthy'
        assert 'server' in response.result
        assert 'tools' in response.result
        assert 'transports' in response.result

    @pytest.mark.asyncio
    async def test_handle_unknown_method(self, mcp_server):
        """Test handling unknown method."""
        request = JSONRPCRequest(
            jsonrpc='2.0',
            id=1,
            method='unknown/method',
            params={}
        )

        response = await mcp_server._handle_message(request)

        assert response is not None
        assert hasattr(response, 'error')
        assert response.error['code'] == MCPErrorCodes.METHOD_NOT_FOUND

    @pytest.mark.asyncio
    async def test_handle_invalid_params(self, mcp_server):
        """Test handling request with invalid params."""
        request = JSONRPCRequest(
            jsonrpc='2.0',
            id=1,
            method='tools/call',
            params={'invalid': 'params'}  # Missing required 'name' field
        )

        response = await mcp_server._handle_message(request)

        assert response is not None
        assert hasattr(response, 'error')
        assert response.error['code'] == MCPErrorCodes.INVALID_PARAMS


class TestToolRegistryIntegration:
    """Test tool registry integration with server."""

    @pytest.mark.asyncio
    async def test_tool_execution_through_server(self, mcp_server):
        """Test executing tool through server message handler."""
        # Register a simple test tool
        from thoth.mcp.tools import MCPTool

        class TestTool(MCPTool):
            name = 'test_tool'
            description = 'A test tool'

            def get_json_schema(self):
                return {
                    'type': 'object',
                    'properties': {
                        'message': {'type': 'string'}
                    }
                }

            async def execute(self, message: str = 'default'):
                return {'result': f'Executed with: {message}'}

        mcp_server.tool_registry.register_instance(TestTool())

        # Create tool call request
        request = JSONRPCRequest(
            jsonrpc='2.0',
            id=1,
            method='tools/call',
            params={
                'name': 'test_tool',
                'arguments': {'message': 'test'}
            }
        )

        response = await mcp_server._handle_message(request)

        assert response is not None
        assert not hasattr(response, 'error')
        assert 'content' in response.result

    @pytest.mark.asyncio
    async def test_tool_list_reflects_registered_tools(self, mcp_server):
        """Test that tools/list shows all registered tools."""
        # Get initial count
        request = JSONRPCRequest(
            jsonrpc='2.0',
            id=1,
            method='tools/list'
        )

        response = await mcp_server._handle_message(request)
        initial_count = len(response.result['tools'])

        # Register new tool
        from thoth.mcp.tools import MCPTool

        class NewTool(MCPTool):
            name = 'new_tool'
            description = 'New tool'

            def get_json_schema(self):
                return {'type': 'object'}

            async def execute(self):
                return {}

        mcp_server.tool_registry.register_instance(NewTool())

        # Check again
        response = await mcp_server._handle_message(request)
        new_count = len(response.result['tools'])

        assert new_count == initial_count + 1


class TestResourceManagerIntegration:
    """Test resource manager integration."""

    @pytest.mark.asyncio
    async def test_list_resources(self, mcp_server):
        """Test listing resources through server."""
        request = JSONRPCRequest(
            jsonrpc='2.0',
            id=1,
            method='resources/list'
        )

        response = await mcp_server._handle_message(request)

        assert response is not None
        assert 'resources' in response.result
        assert isinstance(response.result['resources'], list)

    @pytest.mark.asyncio
    async def test_read_nonexistent_resource(self, mcp_server):
        """Test reading nonexistent resource."""
        request = JSONRPCRequest(
            jsonrpc='2.0',
            id=1,
            method='resources/read',
            params={'uri': 'nonexistent://resource'}
        )

        response = await mcp_server._handle_message(request)

        assert response is not None
        assert hasattr(response, 'error')
        assert response.error['code'] == MCPErrorCodes.RESOURCE_NOT_FOUND


class TestConcurrentOperations:
    """Test concurrent server operations."""

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, mcp_server, health_check_simulator):
        """Test multiple concurrent health checks."""
        tasks = [
            health_check_simulator.run_check()
            for _ in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 10
        assert all(r['healthy'] for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, mcp_server):
        """Test concurrent tool calls."""
        requests = []
        for i in range(5):
            request = JSONRPCRequest(
                jsonrpc='2.0',
                id=i,
                method='tools/list'
            )
            requests.append(request)

        tasks = [
            mcp_server._handle_message(req)
            for req in requests
        ]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert len(responses) == 5
        assert all(not hasattr(r, 'error') for r in responses)

    @pytest.mark.asyncio
    async def test_message_handling_under_load(self, mcp_server):
        """Test message handling under concurrent load."""
        # Mix of different request types
        request_types = [
            JSONRPCRequest(jsonrpc='2.0', id=i, method='health')
            for i in range(50)
        ]

        start_time = time.time()
        responses = await asyncio.gather(
            *[mcp_server._handle_message(req) for req in request_types]
        )
        elapsed = time.time() - start_time

        # All should complete successfully
        assert len(responses) == 50
        assert all(not hasattr(r, 'error') for r in responses)

        # Should complete reasonably fast (< 2 seconds)
        assert elapsed < 2.0


class TestErrorHandlingDuringLifecycle:
    """Test error handling throughout lifecycle."""

    @pytest.mark.asyncio
    async def test_transport_failure_during_start(
        self,
        mcp_server,
        mock_stdio_transport,
        error_injector
    ):
        """Test handling transport failure during start."""
        error_injector.inject_transport_error(mock_stdio_transport, 'connection')
        mcp_server.transport_manager.transports['stdio'] = mock_stdio_transport

        with pytest.raises(ConnectionError):
            await mcp_server.start()

    @pytest.mark.asyncio
    async def test_recovery_after_failed_start(self, mcp_server):
        """Test recovery after failed start."""
        # Create transport that fails once then succeeds
        call_count = {'count': 0}

        mock_transport = Mock()

        async def start_once_fail():
            call_count['count'] += 1
            if call_count['count'] == 1:
                raise ConnectionError('First attempt failed')

        mock_transport.start = AsyncMock(side_effect=start_once_fail)
        mock_transport.stop = AsyncMock()

        mcp_server.transport_manager.transports['test'] = mock_transport

        # First attempt should fail
        with pytest.raises(ConnectionError):
            await mcp_server.start()

        # Second attempt should succeed
        await mcp_server.start()
        assert call_count['count'] == 2

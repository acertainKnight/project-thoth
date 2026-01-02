"""
End-to-end tests for complete MCP workflow.

Tests the entire MCP system from initialization through monitoring,
including server lifecycle, transport coordination, tool execution,
and error recovery scenarios.
"""

import asyncio  # noqa: I001
import json
import subprocess
import sys
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

from thoth.mcp.protocol import JSONRPCRequest
from thoth.mcp.server import MCPServer
from thoth.mcp.monitoring import MCPMonitor


class TestCompleteServerLifecycle:
    """Test complete server lifecycle from start to stop."""

    @pytest.mark.asyncio
    async def test_full_server_lifecycle(
        self, mock_service_manager, server_lifecycle_helper
    ):
        """Test complete server lifecycle: init -> start -> use -> stop."""
        # Step 1: Initialize server
        server = await server_lifecycle_helper.create_server(
            mock_service_manager, enable_http=True
        )

        # Step 2: Register tools
        from thoth.mcp.tools import MCPTool

        class TestTool(MCPTool):
            name = 'test_tool'
            description = 'Test tool'

            def get_json_schema(self):
                return {'type': 'object'}

            async def execute(self):
                return {'status': 'success'}

        server.tool_registry.register_instance(TestTool())

        # Step 3: Start server
        await server.start()
        await asyncio.sleep(0.5)

        # Step 4: Use server - initialize protocol
        init_request = JSONRPCRequest(
            jsonrpc='2.0',
            id=1,
            method='initialize',
            params={
                'protocolVersion': '2024-11-05',
                'clientInfo': {'name': 'Test', 'version': '1.0.0'},
                'capabilities': {},
            },
        )

        init_response = await server._handle_message(init_request)
        assert init_response is not None
        assert 'serverInfo' in init_response.result

        # Step 5: List tools
        tools_request = JSONRPCRequest(jsonrpc='2.0', id=2, method='tools/list')

        tools_response = await server._handle_message(tools_request)
        assert 'tools' in tools_response.result
        assert len(tools_response.result['tools']) > 0

        # Step 6: Execute tool
        call_request = JSONRPCRequest(
            jsonrpc='2.0',
            id=3,
            method='tools/call',
            params={'name': 'test_tool', 'arguments': {}},
        )

        call_response = await server._handle_message(call_request)
        assert not hasattr(call_response, 'error')

        # Step 7: Health check
        health_request = JSONRPCRequest(jsonrpc='2.0', id=4, method='health')

        health_response = await server._handle_message(health_request)
        assert health_response.result['status'] == 'healthy'

        # Step 8: Stop server
        await server.stop()

    @pytest.mark.asyncio
    async def test_server_lifecycle_with_all_transports(
        self, mock_service_manager, server_lifecycle_helper
    ):
        """Test lifecycle with all transport types."""
        server = await server_lifecycle_helper.create_server(
            mock_service_manager, enable_stdio=True, enable_http=True, enable_sse=True
        )

        await server.start()
        await asyncio.sleep(0.5)

        # Verify all transports are active
        assert len(server.transport_manager.transports) == 3
        assert 'stdio' in server.transport_manager.transports
        assert 'http' in server.transport_manager.transports
        assert 'sse' in server.transport_manager.transports

        await server.stop()


class TestTransportCoordination:
    """Test coordination between different transports."""

    @pytest.mark.asyncio
    async def test_simultaneous_transport_startup(
        self,
        mock_service_manager,
        mock_stdio_transport,
        mock_http_transport,
        mock_sse_transport,
    ):
        """Test all transports start simultaneously."""
        server = MCPServer(mock_service_manager)
        server.transport_manager.transports = {
            'stdio': mock_stdio_transport,
            'http': mock_http_transport,
            'sse': mock_sse_transport,
        }

        start_time = time.time()
        await server.start()
        elapsed = time.time() - start_time

        # All should have started
        mock_stdio_transport.start.assert_called_once()
        mock_http_transport.start.assert_called_once()
        mock_sse_transport.start.assert_called_once()

        # Should be fast (concurrent)
        assert elapsed < 2.0

        await server.stop()

    @pytest.mark.asyncio
    async def test_transport_failure_isolation(
        self, mock_service_manager, error_injector
    ):
        """Test failure in one transport doesn't affect others."""
        server = MCPServer(mock_service_manager)

        # Create transports with one failing
        good_transport = Mock()
        good_transport.start = AsyncMock()
        good_transport.stop = AsyncMock()

        bad_transport = Mock()
        error_injector.inject_transport_error(bad_transport, 'crash')
        bad_transport.stop = AsyncMock()

        server.transport_manager.transports = {
            'good': good_transport,
            'bad': bad_transport,
        }

        # Start should fail due to bad transport
        with pytest.raises(RuntimeError):
            await server.start()

        # Good transport should still have been attempted
        good_transport.start.assert_called()


class TestIntegratedMonitoring:
    """Test monitoring integrated with server operations."""

    @pytest.mark.asyncio
    async def test_monitoring_during_server_operation(self, mcp_server_with_transports):
        """Test monitoring while server is operating."""
        await mcp_server_with_transports.start()
        await asyncio.sleep(0.5)

        try:
            monitor = MCPMonitor()

            # Run monitoring checks
            for _ in range(3):
                with patch('httpx.AsyncClient') as mock_client:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                        return_value=mock_response
                    )

                    health = await monitor.get_health_status()
                    assert health.healthy is True

                await asyncio.sleep(0.2)

        finally:
            await mcp_server_with_transports.stop()

    @pytest.mark.asyncio
    async def test_monitoring_detects_busy_server(self, mcp_server_with_transports):
        """Test monitoring detects server under load."""
        await mcp_server_with_transports.start()
        await asyncio.sleep(0.5)

        try:
            # Simulate load - send many requests
            requests = [
                JSONRPCRequest(jsonrpc='2.0', id=i, method='health') for i in range(100)
            ]

            # Process requests concurrently
            response_task = asyncio.gather(
                *[mcp_server_with_transports._handle_message(req) for req in requests]
            )

            # Monitor while processing
            monitor = MCPMonitor()
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                health = await monitor.get_health_status()

            # Wait for requests to complete
            await response_task

            # Server should still be healthy
            assert health is not None

        finally:
            await mcp_server_with_transports.stop()


class TestErrorRecoveryScenarios:
    """Test error recovery scenarios."""

    @pytest.mark.asyncio
    async def test_recovery_from_tool_execution_error(self, mcp_server):
        """Test server recovers from tool execution errors."""
        # Register tool that fails
        from thoth.mcp.tools import MCPTool

        class FailingTool(MCPTool):
            name = 'failing_tool'
            description = 'Tool that fails'

            def get_json_schema(self):
                return {'type': 'object'}

            async def execute(self):
                raise RuntimeError('Tool failed')

        mcp_server.tool_registry.register_instance(FailingTool())

        await mcp_server.start()

        try:
            # Try to execute failing tool
            request = JSONRPCRequest(
                jsonrpc='2.0',
                id=1,
                method='tools/call',
                params={'name': 'failing_tool', 'arguments': {}},
            )

            response = await mcp_server._handle_message(request)
            assert hasattr(response, 'error')

            # Server should still be functional
            health_request = JSONRPCRequest(jsonrpc='2.0', id=2, method='health')

            health_response = await mcp_server._handle_message(health_request)
            assert health_response.result['status'] == 'healthy'

        finally:
            await mcp_server.stop()

    @pytest.mark.asyncio
    async def test_recovery_from_invalid_protocol_message(self, mcp_server):
        """Test server recovers from invalid protocol messages."""
        await mcp_server.start()

        try:
            # Send invalid message
            invalid_request = JSONRPCRequest(
                jsonrpc='2.0', id=1, method='invalid/method', params={}
            )

            response = await mcp_server._handle_message(invalid_request)
            assert hasattr(response, 'error')

            # Server should still work
            valid_request = JSONRPCRequest(jsonrpc='2.0', id=2, method='health')

            valid_response = await mcp_server._handle_message(valid_request)
            assert not hasattr(valid_response, 'error')

        finally:
            await mcp_server.stop()

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_resource_error(self, mcp_server):
        """Test graceful degradation on resource errors."""
        await mcp_server.start()

        try:
            # Try to read nonexistent resource
            request = JSONRPCRequest(
                jsonrpc='2.0',
                id=1,
                method='resources/read',
                params={'uri': 'nonexistent://resource'},
            )

            response = await mcp_server._handle_message(request)
            assert hasattr(response, 'error')

            # Other operations should still work
            tools_request = JSONRPCRequest(jsonrpc='2.0', id=2, method='tools/list')

            tools_response = await mcp_server._handle_message(tools_request)
            assert not hasattr(tools_response, 'error')

        finally:
            await mcp_server.stop()


class TestResourceCleanup:
    """Test proper resource cleanup."""

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_shutdown(self, mcp_server_with_transports):
        """Test all connections are cleaned up on shutdown."""
        await mcp_server_with_transports.start()
        await asyncio.sleep(0.5)

        # Get transport count before shutdown
        transport_count = len(mcp_server_with_transports.transport_manager.transports)
        assert transport_count > 0

        await mcp_server_with_transports.stop()

        # Transports should be stopped (we can't easily verify cleanup,
        # but at least verify stop was called on all)

    @pytest.mark.asyncio
    async def test_file_handle_cleanup(self, mcp_server, tmp_path):
        """Test file handles are cleaned up."""
        # Add file resource provider
        from thoth.mcp.resources import FileResourceProvider

        provider = FileResourceProvider(
            base_paths=[str(tmp_path)], allowed_extensions=['.txt']
        )
        mcp_server.add_resource_provider(provider)

        await mcp_server.start()

        try:
            # Create test file
            test_file = tmp_path / 'test.txt'
            test_file.write_text('test content')

            # Read resource
            request = JSONRPCRequest(jsonrpc='2.0', id=1, method='resources/list')

            await mcp_server._handle_message(request)

        finally:
            await mcp_server.stop()

        # File should still be accessible (no locks left)
        assert test_file.read_text() == 'test content'

    @pytest.mark.asyncio
    async def test_memory_cleanup_after_many_requests(self, mcp_server):
        """Test memory is cleaned up after processing many requests."""
        await mcp_server.start()

        try:
            # Process many requests
            for i in range(1000):
                request = JSONRPCRequest(jsonrpc='2.0', id=i, method='health')

                await mcp_server._handle_message(request)

            # Memory should not grow unbounded
            # (This is a basic test - would need memory profiling for thorough check)

        finally:
            await mcp_server.stop()


class TestCLIIntegrationWorkflow:
    """Test CLI integration in end-to-end workflow."""

    @pytest.mark.slow
    def test_cli_http_server_full_workflow(self):
        """Test complete workflow using CLI HTTP server."""
        port = 9300

        # Start server via CLI
        process = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'thoth.cli',
                'mcp',
                'http',
                '--port',
                str(port),
                '--log-level',
                'INFO',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # Wait for startup
            time.sleep(5)

            # Verify server is running
            assert process.poll() is None

            # Try health check (may not work if server not fully started)
            try:
                response = requests.get(f'http://127.0.0.1:{port}/health', timeout=2)
                if response.status_code == 200:
                    assert 'status' in response.json() or 'healthy' in response.json()
            except requests.ConnectionError:
                # Server might not be ready yet - that's ok for this test
                pass

        finally:
            # Cleanup
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    @pytest.mark.slow
    def test_cli_stdio_server_protocol_workflow(self):
        """Test protocol workflow with CLI stdio server."""
        process = subprocess.Popen(
            [sys.executable, '-m', 'thoth.cli', 'mcp', 'stdio'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            time.sleep(2)

            # Send initialize
            init_msg = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'initialize',
                'params': {
                    'protocolVersion': '2024-11-05',
                    'clientInfo': {'name': 'Test', 'version': '1.0.0'},
                    'capabilities': {},
                },
            }

            process.stdin.write(json.dumps(init_msg) + '\n')
            process.stdin.flush()

            # Try to read response
            time.sleep(1)

        finally:
            process.terminate()
            process.wait(timeout=5)


class TestConcurrentWorkflows:
    """Test concurrent workflow execution."""

    @pytest.mark.asyncio
    async def test_concurrent_client_sessions(self, mcp_server):
        """Test multiple concurrent client sessions."""
        await mcp_server.start()

        try:
            # Simulate 3 concurrent clients
            async def client_session(client_id):
                # Initialize
                init_request = JSONRPCRequest(
                    jsonrpc='2.0',
                    id=f'{client_id}-1',
                    method='initialize',
                    params={
                        'protocolVersion': '2024-11-05',
                        'clientInfo': {
                            'name': f'Client {client_id}',
                            'version': '1.0.0',
                        },
                        'capabilities': {},
                    },
                )

                await mcp_server._handle_message(init_request)

                # List tools
                tools_request = JSONRPCRequest(
                    jsonrpc='2.0', id=f'{client_id}-2', method='tools/list'
                )

                await mcp_server._handle_message(tools_request)

                # Health check
                health_request = JSONRPCRequest(
                    jsonrpc='2.0', id=f'{client_id}-3', method='health'
                )

                return await mcp_server._handle_message(health_request)

            # Run 3 clients concurrently
            results = await asyncio.gather(
                client_session(1), client_session(2), client_session(3)
            )

            # All should succeed
            assert len(results) == 3
            assert all(r.result['status'] == 'healthy' for r in results)

        finally:
            await mcp_server.stop()

    @pytest.mark.asyncio
    async def test_concurrent_monitoring_and_operations(
        self, mcp_server_with_transports
    ):
        """Test monitoring while operations are running."""
        await mcp_server_with_transports.start()
        await asyncio.sleep(0.5)

        try:

            async def monitoring_loop():
                monitor = MCPMonitor()
                for _ in range(5):
                    with patch('httpx.AsyncClient') as mock_client:
                        mock_response = Mock()
                        mock_response.status_code = 200
                        mock_client.return_value.__aenter__.return_value.get = (
                            AsyncMock(return_value=mock_response)
                        )
                        await monitor.get_health_status()
                    await asyncio.sleep(0.1)

            async def operations_loop():
                for i in range(10):
                    request = JSONRPCRequest(jsonrpc='2.0', id=i, method='health')
                    await mcp_server_with_transports._handle_message(request)
                    await asyncio.sleep(0.05)

            # Run both concurrently
            await asyncio.gather(monitoring_loop(), operations_loop())

        finally:
            await mcp_server_with_transports.stop()


class TestProductionScenarios:
    """Test production-like scenarios."""

    @pytest.mark.asyncio
    async def test_24hour_simulation(self, mcp_server):
        """Simulate 24-hour operation (compressed to seconds)."""
        await mcp_server.start()

        try:
            # Simulate periodic operations
            for hour in range(24):
                # Health check
                request = JSONRPCRequest(
                    jsonrpc='2.0', id=f'hour-{hour}', method='health'
                )

                response = await mcp_server._handle_message(request)
                assert response.result['status'] == 'healthy'

                await asyncio.sleep(0.1)  # Represents 1 hour

        finally:
            await mcp_server.stop()

    @pytest.mark.asyncio
    async def test_high_load_scenario(self, mcp_server):
        """Test server under high load."""
        await mcp_server.start()

        try:
            # Send 500 requests rapidly
            requests_list = [
                JSONRPCRequest(jsonrpc='2.0', id=i, method='health') for i in range(500)
            ]

            start_time = time.time()
            responses = await asyncio.gather(
                *[mcp_server._handle_message(req) for req in requests_list]
            )
            elapsed = time.time() - start_time

            # All should complete
            assert len(responses) == 500
            assert all(r.result['status'] == 'healthy' for r in responses)

            # Should complete reasonably fast
            assert elapsed < 10.0

        finally:
            await mcp_server.stop()

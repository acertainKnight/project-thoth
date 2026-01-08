# MCP Integration Tests

Comprehensive integration tests for the Model Context Protocol (MCP) server implementation.

## Test Organization

### 1. Server Lifecycle Tests (`test_server_lifecycle.py`)
**511 lines** - Tests server initialization, transport management, and lifecycle operations

**Test Classes:**
- `TestServerInitialization` - Server setup with ServiceManager
- `TestTransportManagement` - Adding and configuring transports
- `TestServerStartStop` - Start/stop operations and cleanup
- `TestProtocolMessageHandling` - MCP protocol message routing
- `TestToolRegistryIntegration` - Tool execution through server
- `TestResourceManagerIntegration` - Resource access
- `TestConcurrentOperations` - Parallel request handling
- `TestErrorHandlingDuringLifecycle` - Error recovery

**Key Test Areas:**
- ✅ Server initialization with custom capabilities
- ✅ Multiple server instances independence
- ✅ stdio, HTTP, and SSE transport addition
- ✅ Graceful startup and shutdown
- ✅ Protocol message handling (initialize, tools/list, tools/call, health)
- ✅ Unknown method handling
- ✅ Tool registry integration
- ✅ Resource manager integration
- ✅ Concurrent health checks and tool calls
- ✅ Transport failure handling
- ✅ Recovery after failed start

### 2. CLI Command Tests (`test_cli_commands.py`)
**583 lines** - Tests CLI interface using subprocess execution

**Test Classes:**
- `TestStdioServerCommand` - stdio server CLI testing
- `TestHTTPServerCommand` - HTTP server CLI testing
- `TestFullServerCommand` - Full server with all transports
- `TestCLIErrorHandling` - CLI error scenarios
- `TestCLIEnvironmentVariables` - Environment configuration
- `TestCLISubprocessManagement` - Process management
- `TestCLIOutputFormat` - Log formatting

**Key Test Areas:**
- ✅ Help command output for all modes
- ✅ stdio server startup with protocol messages
- ✅ HTTP server on custom ports
- ✅ Log level configuration (DEBUG, INFO, WARNING, ERROR)
- ✅ Graceful shutdown with SIGTERM
- ✅ Full server with multiple transports
- ✅ File access enable/disable
- ✅ Invalid parameter handling
- ✅ Port conflict detection
- ✅ Working directory respect
- ✅ Process cleanup on errors

### 3. Monitoring Pipeline Tests (`test_monitoring_pipeline.py`)
**634 lines** - Tests monitoring, health checks, and metrics

**Test Classes:**
- `TestHealthCheckWorkflow` - Basic health checking
- `TestMultipleHealthCheckCycles` - Repeated health checks
- `TestServerDetailsMonitoring` - Server statistics
- `TestAlertingMechanism` - Alert threshold violations
- `TestCacheRefreshOperations` - Cache management
- `TestPrometheusMetrics` - Metrics generation
- `TestEndToEndMonitoringWorkflow` - Complete monitoring workflows

**Key Test Areas:**
- ✅ Health status reporting
- ✅ Connection error handling
- ✅ Timeout handling
- ✅ Sequential and concurrent health checks
- ✅ Health check interval respect
- ✅ Server detail statistics
- ✅ Alert triggering on unhealthy status
- ✅ Alert triggering on low success rate
- ✅ Alert triggering on high response time
- ✅ Custom alert thresholds
- ✅ Cache refresh operations
- ✅ Prometheus metrics format
- ✅ Startup to monitoring workflow
- ✅ Continuous monitoring loop
- ✅ Server restart detection

### 4. Complete Workflow Tests (`test_complete_mcp_workflow.py`)
**727 lines** - End-to-end system tests

**Test Classes:**
- `TestCompleteServerLifecycle` - Full lifecycle workflows
- `TestTransportCoordination` - Multi-transport coordination
- `TestIntegratedMonitoring` - Monitoring during operations
- `TestErrorRecoveryScenarios` - Error handling and recovery
- `TestResourceCleanup` - Resource management
- `TestCLIIntegrationWorkflow` - CLI integration
- `TestConcurrentWorkflows` - Concurrent operations
- `TestProductionScenarios` - Production-like scenarios

**Key Test Areas:**
- ✅ Complete init → start → use → stop lifecycle
- ✅ All transports working together
- ✅ Simultaneous transport startup
- ✅ Transport failure isolation
- ✅ Monitoring during server operation
- ✅ Monitoring under load
- ✅ Recovery from tool execution errors
- ✅ Recovery from invalid protocol messages
- ✅ Graceful degradation on resource errors
- ✅ Connection cleanup on shutdown
- ✅ File handle cleanup
- ✅ Memory cleanup after many requests
- ✅ CLI HTTP server full workflow
- ✅ CLI stdio protocol workflow
- ✅ Concurrent client sessions
- ✅ Concurrent monitoring and operations
- ✅ 24-hour operation simulation
- ✅ High load scenarios (500+ requests)

## Fixtures (`tests/fixtures/mcp_server_fixtures.py`)
**492 lines** - Reusable test fixtures

**Fixtures Provided:**
- `test_config` - Test configuration
- `mock_service_manager` - Mock ServiceManager with all services
- `protocol_handler` - MCPProtocolHandler instance
- `server_info` - MCPServerInfo for testing
- `capabilities` - MCPCapabilities
- `mcp_server` - Basic MCP server instance
- `mcp_server_with_transports` - Server with all transports
- `mock_stdio_transport` - Mock stdio transport
- `mock_http_transport` - Mock HTTP transport
- `mock_sse_transport` - Mock SSE transport
- `transport_manager` - TransportManager instance
- `mock_transports` - Dictionary of MockTransport instances
- `sample_requests` - Pre-built sample requests
- `server_lifecycle_helper` - Helper for server lifecycle testing
- `message_collector` - Message collection for testing
- `health_check_simulator` - Simulate health check cycles
- `error_injector` - Inject errors for recovery testing

**Helper Classes:**
- `MockTransport` - Full mock transport implementation
- `ServerLifecycleHelper` - Manages multiple test servers
- `MessageCollector` - Collects and tracks messages
- `HealthCheckSimulator` - Simulates monitoring cycles
- `ErrorInjector` - Injects various error types

**Helper Functions:**
- `create_jsonrpc_request()` - Create JSONRPC requests
- `create_jsonrpc_notification()` - Create notifications
- `create_initialize_request()` - Create initialize requests
- `create_tools_list_request()` - Create tools/list requests
- `create_tools_call_request()` - Create tools/call requests

## Running Tests

### Run All Integration Tests
```bash
pytest tests/integration/mcp/ -v
```

### Run Specific Test Class
```bash
pytest tests/integration/mcp/test_server_lifecycle.py::TestServerInitialization -v
```

### Run E2E Tests
```bash
pytest tests/e2e/test_complete_mcp_workflow.py -v
```

### Run with Coverage
```bash
pytest tests/integration/mcp/ --cov=thoth.mcp --cov-report=html
```

### Run Slow Tests (CLI/subprocess tests)
```bash
pytest tests/integration/mcp/ -v -m slow
```

## Test Coverage

**Total Lines: 2,947**
- Fixtures: 492 lines
- Server Lifecycle: 511 lines
- CLI Commands: 583 lines
- Monitoring Pipeline: 634 lines
- E2E Workflows: 727 lines

**Areas Covered:**
1. ✅ Server initialization and configuration
2. ✅ Transport management (stdio, HTTP, SSE)
3. ✅ Protocol message handling
4. ✅ Tool registry integration
5. ✅ Resource manager integration
6. ✅ CLI command interface
7. ✅ Health checking and monitoring
8. ✅ Metrics collection (Prometheus format)
9. ✅ Alert triggering
10. ✅ Error recovery
11. ✅ Resource cleanup
12. ✅ Concurrent operations
13. ✅ High load scenarios
14. ✅ Production workflows

## Test Markers

- `@pytest.mark.asyncio` - Async test functions
- `@pytest.mark.slow` - Tests that take >5 seconds (CLI subprocess tests)

## Dependencies

Required packages:
- pytest
- pytest-asyncio
- pytest-mock
- httpx
- requests

## Notes

### CLI Tests
- CLI tests use subprocess execution for realistic testing
- Tests use random high ports (9000-9999) to avoid conflicts
- Marked with `@pytest.mark.slow` due to subprocess startup time
- Tests include proper cleanup and timeout handling

### Async Tests
- All async tests use `@pytest.mark.asyncio`
- Proper cleanup in try/finally blocks
- Concurrent test isolation with random ports

### Mock Usage
- ServiceManager is mocked to avoid database dependencies
- HTTP clients mocked for health check tests
- Transports can be mocked or real depending on test needs

### Error Testing
- `ErrorInjector` fixture for systematic error injection
- Tests cover connection errors, timeouts, crashes
- Recovery verification after each error scenario

## Best Practices Demonstrated

1. **Test Organization**: Clear class-based organization by feature
2. **Fixture Reuse**: Comprehensive fixtures reduce duplication
3. **Cleanup Handling**: All tests properly clean up resources
4. **Concurrent Testing**: Tests verify thread-safety
5. **Error Scenarios**: Thorough error handling coverage
6. **Production Simulation**: Realistic load and timing tests
7. **Documentation**: Each test has clear docstring
8. **Isolation**: Tests don't interfere with each other

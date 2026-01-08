# MCP Monitoring Testing Guide

Quick reference for running and understanding the MCP monitoring test suite.

## Quick Start

```bash
# Install dependencies
pip install pytest pytest-asyncio respx httpx fastapi pydantic

# Run all tests
pytest tests/unit/mcp/ -v

# Run with coverage
pytest tests/unit/mcp/ --cov=thoth.mcp.monitoring --cov-report=term-missing
```

## Test File Structure

```
tests/
├── fixtures/
│   └── mcp_fixtures.py         # 462 lines - Comprehensive test fixtures
└── unit/mcp/
    ├── __init__.py
    ├── test_monitoring.py      # 659 lines - MCPMonitor class tests
    ├── test_health_endpoints.py # 573 lines - FastAPI endpoint tests
    ├── README.md               # Comprehensive documentation
    └── TESTING_GUIDE.md        # This file
```

**Total: 1,694 lines of test code**

## Running Specific Tests

### By Test Class
```bash
# Monitor initialization tests
pytest tests/unit/mcp/test_monitoring.py::TestMCPMonitorInit -v

# Healthy server tests
pytest tests/unit/mcp/test_monitoring.py::TestGetHealthStatusHealthy -v

# Connection error tests
pytest tests/unit/mcp/test_monitoring.py::TestGetHealthStatusConnectionErrors -v

# Alert threshold tests
pytest tests/unit/mcp/test_monitoring.py::TestShouldAlert -v

# Health endpoint tests
pytest tests/unit/mcp/test_health_endpoints.py::TestHealthEndpoint -v

# Metrics endpoint tests
pytest tests/unit/mcp/test_health_endpoints.py::TestMetricsEndpoint -v
```

### By Test Function
```bash
# Single test
pytest tests/unit/mcp/test_monitoring.py::TestGetHealthStatusHealthy::test_healthy_server_response -v

# Multiple specific tests
pytest tests/unit/mcp/test_monitoring.py::TestShouldAlert::test_should_alert_low_success_rate \
       tests/unit/mcp/test_monitoring.py::TestShouldAlert::test_should_alert_high_response_time -v
```

### By Pattern
```bash
# All health check tests
pytest tests/unit/mcp/ -k "health" -v

# All error handling tests
pytest tests/unit/mcp/ -k "error" -v

# All timeout tests
pytest tests/unit/mcp/ -k "timeout" -v

# All Prometheus metrics tests
pytest tests/unit/mcp/ -k "metrics or prometheus" -v
```

## Test Categories

### 1. Initialization Tests (2 tests)
```bash
pytest tests/unit/mcp/test_monitoring.py::TestMCPMonitorInit -v
```
Tests monitor setup and default configuration values.

### 2. Health Status Tests (15 tests)
```bash
# Healthy scenarios
pytest tests/unit/mcp/test_monitoring.py::TestGetHealthStatusHealthy -v

# Unhealthy scenarios (503, 500, 404)
pytest tests/unit/mcp/test_monitoring.py::TestGetHealthStatusUnhealthy -v

# Connection errors (timeout, refused, network)
pytest tests/unit/mcp/test_monitoring.py::TestGetHealthStatusConnectionErrors -v

# Edge cases (malformed response, empty, exceptions)
pytest tests/unit/mcp/test_monitoring.py::TestGetHealthStatusEdgeCases -v
```

### 3. Server Details Tests (4 tests)
```bash
pytest tests/unit/mcp/test_monitoring.py::TestGetServerDetails -v
```
Tests server statistics retrieval and formatting.

### 4. Alert Logic Tests (6 tests)
```bash
pytest tests/unit/mcp/test_monitoring.py::TestShouldAlert -v
```
Tests threshold-based alerting logic.

### 5. Cache Refresh Tests (3 tests)
```bash
pytest tests/unit/mcp/test_monitoring.py::TestRefreshToolsCache -v
```
Tests tools cache refresh operations.

### 6. Model Validation Tests (8 tests)
```bash
# Health status model
pytest tests/unit/mcp/test_monitoring.py::TestMCPHealthStatusModel -v

# Server stats model
pytest tests/unit/mcp/test_monitoring.py::TestMCPServerStatsModel -v
```

### 7. FastAPI Endpoint Tests (20 tests)
```bash
# Health endpoint
pytest tests/unit/mcp/test_health_endpoints.py::TestHealthEndpoint -v

# Servers endpoint
pytest tests/unit/mcp/test_health_endpoints.py::TestServersEndpoint -v

# Refresh cache endpoint
pytest tests/unit/mcp/test_health_endpoints.py::TestRefreshCacheEndpoint -v

# Prometheus metrics endpoint
pytest tests/unit/mcp/test_health_endpoints.py::TestMetricsEndpoint -v
```

## Test Output Examples

### Successful Test Run
```bash
$ pytest tests/unit/mcp/test_monitoring.py::TestMCPMonitorInit -v

tests/unit/mcp/test_monitoring.py::TestMCPMonitorInit::test_monitor_init_default_values PASSED
tests/unit/mcp/test_monitoring.py::TestMCPMonitorInit::test_monitor_init_alert_thresholds PASSED

======================== 2 passed in 0.03s ========================
```

### Failed Test with Details
```bash
$ pytest tests/unit/mcp/test_monitoring.py::TestShouldAlert::test_should_alert_low_success_rate -v

FAILED tests/unit/mcp/test_monitoring.py::TestShouldAlert::test_should_alert_low_success_rate

======================= FAILURES =======================
___ TestShouldAlert.test_should_alert_low_success_rate ___

    def test_should_alert_low_success_rate(self):
        monitor = MCPMonitor()
        status = MCPHealthStatus(...)
>       assert monitor.should_alert(status) is True
E       AssertionError: assert False is True

tests/unit/mcp/test_monitoring.py:XXX: AssertionError
```

### Coverage Report
```bash
$ pytest tests/unit/mcp/ --cov=thoth.mcp.monitoring --cov-report=term-missing

Name                              Stmts   Miss  Cover   Missing
---------------------------------------------------------------
src/thoth/mcp/monitoring.py         123      0   100%
---------------------------------------------------------------
TOTAL                               123      0   100%
```

## Common Testing Scenarios

### Test Health Check with Healthy Server
```bash
pytest tests/unit/mcp/test_monitoring.py::TestGetHealthStatusHealthy::test_healthy_server_response -v
```

### Test Health Check with Connection Error
```bash
pytest tests/unit/mcp/test_monitoring.py::TestGetHealthStatusConnectionErrors::test_connection_refused -v
```

### Test Alert Threshold Logic
```bash
pytest tests/unit/mcp/test_monitoring.py::TestShouldAlert -v
```

### Test Prometheus Metrics Format
```bash
pytest tests/unit/mcp/test_health_endpoints.py::TestMetricsEndpoint::test_metrics_endpoint_prometheus_format -v
```

### Test All Async Operations
```bash
pytest tests/unit/mcp/ -v -m asyncio
```

## Debugging Failed Tests

### Verbose Output with Traceback
```bash
pytest tests/unit/mcp/ -v --tb=long
```

### Show Print Statements
```bash
pytest tests/unit/mcp/ -v -s
```

### Stop on First Failure
```bash
pytest tests/unit/mcp/ -v -x
```

### Show Local Variables in Traceback
```bash
pytest tests/unit/mcp/ -v --tb=long --showlocals
```

### Run Last Failed Tests Only
```bash
pytest tests/unit/mcp/ -v --lf
```

## Performance Testing

### Time Each Test
```bash
pytest tests/unit/mcp/ -v --durations=10
```

### Slowest Tests
```bash
pytest tests/unit/mcp/ -v --durations=0 | grep PASSED
```

## Test Fixtures Usage

### View Available Fixtures
```bash
pytest tests/unit/mcp/ --fixtures
```

### Use Specific Fixture
```python
def test_with_fixture(healthy_status):
    """Test using healthy_status fixture."""
    assert healthy_status.healthy is True
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: MCP Monitoring Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install pytest pytest-asyncio respx httpx fastapi pydantic pytest-cov
      - name: Run tests
        run: |
          pytest tests/unit/mcp/ -v --cov=thoth.mcp.monitoring --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Test Maintenance

### Add New Test
1. Choose appropriate test file:
   - `test_monitoring.py` for MCPMonitor class tests
   - `test_health_endpoints.py` for FastAPI endpoint tests
2. Add to existing test class or create new one
3. Use fixtures from `mcp_fixtures.py`
4. Follow naming convention: `test_<what>_<scenario>`

### Add New Fixture
1. Add to `tests/fixtures/mcp_fixtures.py`
2. Group with related fixtures
3. Use descriptive fixture name
4. Add docstring explaining purpose

## Troubleshooting

### Import Errors
```bash
# Ensure Python path includes project root
export PYTHONPATH=/home/nick-hallmark/Documents/python/project-thoth:$PYTHONPATH
pytest tests/unit/mcp/ -v
```

### Async Test Failures
```bash
# Ensure pytest-asyncio is installed
pip install pytest-asyncio

# Check pytest.ini or conftest.py has asyncio configuration
```

### Mock Not Working
```bash
# Use respx.mock decorator or context manager
@respx.mock
async def test_with_respx():
    respx.get('http://localhost:8000/health').mock(...)

# Or with context manager
async def test_with_respx():
    with respx.mock:
        respx.get('http://localhost:8000/health').mock(...)
```

## Test Quality Metrics

### Current Coverage: 100%
- All MCPMonitor methods tested
- All FastAPI endpoints tested
- All error paths covered
- All Pydantic models validated

### Test Count: 58 tests
- 38 tests in `test_monitoring.py`
- 20 tests in `test_health_endpoints.py`

### Test Execution Time: ~2 seconds
- Fast unit tests with mocked HTTP calls
- No external dependencies required
- Suitable for CI/CD pipelines

## Next Steps

After running tests successfully:

1. **Review Coverage Report**
   ```bash
   pytest tests/unit/mcp/ --cov=thoth.mcp.monitoring --cov-report=html
   open htmlcov/index.html
   ```

2. **Run Integration Tests**
   ```bash
   # When available
   pytest tests/integration/mcp/ -v
   ```

3. **Run E2E Tests**
   ```bash
   # When available
   pytest tests/e2e/mcp/ -v
   ```

4. **Add More Tests**
   - Consider edge cases not covered
   - Add property-based tests with Hypothesis
   - Add performance benchmarks

## Support

For issues or questions:
- Check test documentation in `README.md`
- Review fixture definitions in `mcp_fixtures.py`
- Examine existing test patterns
- Check project test strategy in `tests/TEST_STRATEGY.md`

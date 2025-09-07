# Thoth Test Suite

Production-grade test suite for the Thoth academic PDF processing system.

## Quick Start

```bash
# Run all tests
python tests/run_tests.py

# Run specific categories
uv run pytest tests/unit -v           # Unit tests
uv run pytest tests/integration -v    # Integration tests

# Interactive testing
jupyter lab notebooks/testing/test_runner.ipynb
```

## Structure

```
tests/
├── unit/                    # Business logic validation (70%)
├── integration/             # Service contracts and workflows (25%)
├── notebooks/testing/       # Interactive validation (5%)
├── conftest.py             # Test fixtures
├── pytest.ini             # Test configuration
└── run_tests.py            # Test runner
```

## Coverage

- **Citation Processing**: Data transformation, formatting, enhancement
- **Service Architecture**: 13 services, health monitoring, contracts
- **Pipeline Orchestration**: PDF→Markdown→Analysis→Note workflows
- **MCP Framework**: Tool system, protocol handling
- **Memory System**: Storage, retrieval, scoring
- **Discovery System**: API sources, scheduling
- **Error Handling**: Boundaries, recovery, resilience
- **Performance**: SLAs, resource monitoring
- **Security**: Input validation, attack prevention

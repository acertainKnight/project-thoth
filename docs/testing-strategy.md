# Testing Strategy

How we test Thoth, and what we prioritize.

---

## Current State

**840 passing unit tests** across services, repositories, citations, config, evaluation, MCP, monitoring, and performance modules. All green, no known flaky tests.

```bash
pytest tests/unit/     # ~840 tests, runs in under 2 minutes
pytest tests/          # full suite including integration and e2e
```

### Test Layout

```
tests/
├── unit/                         # fast, isolated tests
│   ├── citations/                # citation parsing and resolution
│   ├── config/                   # settings loading, hot-reload, vault detection
│   ├── discovery/                # multi-level extraction
│   ├── evaluation/               # ground truth, metrics, visualizations
│   ├── mcp/                      # MCP tools and health endpoints
│   ├── monitoring/               # health checks, caching, performance
│   ├── performance/              # workflow monitoring
│   ├── properties/               # property-based tests (Hypothesis)
│   ├── repositories/             # data access layer
│   ├── server/routers/           # FastAPI endpoint tests
│   ├── services/                 # service layer logic
│   ├── setup/                    # setup wizard config and validators
│   └── utilities/                # async utils, memory leak checks
├── integration/                  # service interaction tests
├── e2e/                          # end-to-end workflow tests
├── fixtures/                     # shared test data and mock factories
└── conftest.py                   # common fixtures
```

## Approach

### What we test

- **Services**: Each service in `src/thoth/services/` has corresponding tests. These cover initialization, core methods, error handling, and edge cases with mocked dependencies.
- **Configuration**: Settings loading from multiple paths, hot-reload callbacks, Pydantic validation, vault detection fallback chain.
- **Citations**: Parsing, formatting, fuzzy matching, resolution chain logic, and confidence scoring. Includes property-based tests with Hypothesis for robustness.
- **Repositories**: Data access patterns, transaction handling.
- **MCP tools**: Tool registration, parameter validation, health endpoints.
- **Server routers**: FastAPI endpoint response codes, input validation, error handling.

### What we don't test (yet)

Integration and e2e tests are thin. The earlier approach was to write aspirational tests for features that didn't exist yet, which predictably resulted in a pile of broken tests that hid real issues. We deleted those and are rebuilding integration coverage incrementally as features stabilize.

Specifically, we need better coverage for:
- Database transaction integration (with real PostgreSQL)
- MCP server lifecycle (startup, tool registration, shutdown)
- Full document processing pipeline (PDF in, Obsidian note out)
- Discovery workflow (query to filtered results)

These will be added as the corresponding code matures.

## Running Tests

```bash
# during development (fast feedback)
pytest tests/unit/ -v --tb=short

# before committing
pytest tests/ -v

# with coverage
pytest --cov=src/thoth --cov-report=term-missing tests/

# specific module
pytest tests/unit/services/test_rag_service.py

# matching a pattern
pytest -k "citation"
```

## Guidelines for New Tests

- Put unit tests in `tests/unit/` mirroring the `src/thoth/` directory structure
- Use fixtures from `tests/fixtures/` and `tests/conftest.py` for common setup
- Mock external dependencies (LLM calls, HTTP requests, database connections)
- Test actual behavior, not implementation details—if a refactor breaks a test but the feature still works, the test was too tightly coupled
- Use `@pytest.mark.asyncio` for async tests
- Use Hypothesis for anything involving string parsing, matching, or scoring

## Previous Cleanup

We deleted ~100 tests in January 2026 that were written before their corresponding features existed. They used broken fixtures, had fundamental async issues, and gave false confidence. The current 840-test baseline is clean and trustworthy.

Key fix found during cleanup: `BaseRepository.transaction()` was incorrectly defined as `async def` when it needed to return an async context manager directly. Would have broken any code path using database transactions.

---

*Last updated: February 2026*

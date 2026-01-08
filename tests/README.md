# Project Thoth Testing Suite

> **Comprehensive test strategy for citation resolution system with ML evaluation rigor**

## Quick Start

```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/unit/                    # Fast unit tests (~2 min)
pytest tests/integration/             # Integration tests (~10 min)
pytest tests/e2e/                     # End-to-end workflows (~15 min)

# Generate coverage report
pytest tests/ --cov=src/thoth --cov-report=html
open htmlcov/index.html
```

## Documentation

- **[TEST_STRATEGY.md](./TEST_STRATEGY.md)** - Comprehensive 29KB strategy document
- **[TESTING_OVERVIEW.txt](./TESTING_OVERVIEW.txt)** - Quick reference guide

## Test Architecture

```
tests/
├── unit/                      # 195 tests | ~30% coverage | < 2 min
│   ├── citations/            # Citation parsing & formatting
│   ├── evaluation/           # ML metrics calculation
│   ├── services/             # Service layer logic
│   └── repositories/         # Data access layer
│
├── integration/               # 205 tests | ~40% coverage | < 10 min
│   ├── pipelines/            # Citation resolution, RAG evaluation
│   ├── database/             # Async operations, transactions
│   ├── api/                  # REST endpoints, WebSocket
│   └── external/             # LLM providers, academic APIs
│
├── e2e/                       # 25 tests | ~15% coverage | < 15 min
│   ├── test_pdf_processing_workflow.py
│   ├── test_citation_resolution_workflow.py
│   └── test_rag_query_workflow.py
│
├── property_based/            # 40 tests | ~5% coverage | < 5 min
│   ├── test_citation_properties.py
│   ├── test_metric_properties.py
│   └── test_string_matching_properties.py
│
├── benchmarks/                # 50 tests | ~10% coverage | < 10 min
│   ├── test_citation_resolution_performance.py
│   ├── test_rag_retrieval_performance.py
│   └── test_embedding_generation_performance.py
│
├── fixtures/                  # Test data and mocks
│   ├── ground_truth/
│   ├── sample_papers/
│   └── mock_responses/
│
└── conftest.py               # Shared fixtures and configuration
```

## Coverage Targets by Priority

| Priority | Module | Target | Test Types |
|----------|--------|--------|------------|
| 🔴 Critical | `rag/evaluation/` | 90% | Unit + Integration + Property |
| 🔴 Critical | `analyze/citations/` | 85% | Unit + Property |
| 🔴 Critical | `services/article_service.py` | 80% | Unit + Integration |
| 🟡 High | `discovery/context_analyzer.py` | 75% | Unit + Integration |
| 🟡 High | `rag/vector_store.py` | 80% | Unit + Integration + Benchmark |
| 🟡 High | `repositories/` | 70% | Integration |
| 🟢 Medium | `server/routers/` | 60% | Integration + E2E |
| 🟢 Medium | `utilities/schemas/` | 85% | Unit |
| 🟢 Medium | `mcp/tools/` | 50% | Integration |

**Overall Target**: 50-55% strategic coverage

## Key Testing Principles

### 1. ML Evaluation Rigor
```python
# Statistical significance testing
ci_baseline = bootstrap_ci(baseline_scores, n=1000)
ci_current = bootstrap_ci(current_scores, n=1000)
assert ci_current[0] > ci_baseline[1], "Not statistically significant"

# Metric correctness validation
assert 0.0 <= ndcg <= 1.0, "NDCG must be bounded"
assert precision + recall > 0, "Degenerate metrics"
```

### 2. Research Reproducibility
```python
# Deterministic testing
@pytest.fixture
def deterministic_environment():
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    yield

# Dataset versioning
gt_pairs = load_ground_truth("v1.2.0")
assert compute_checksum(gt_pairs) == EXPECTED_CHECKSUM
```

### 3. Production Reliability
```python
# Async safety testing
tasks = [resolver.resolve(c) for c in citations]
results = await asyncio.gather(*tasks, return_exceptions=True)
assert all(not isinstance(r, Exception) for r in results)

# Resource limit enforcement
with monitor_memory() as tracker:
    results = await processor.process_batch(docs)
assert tracker.peak_usage_mb < 600
```

## Top 10 Critical Components

1. **RAG Evaluation Metrics** - ML evaluation correctness
2. **Ground Truth Generation** - Research reproducibility
3. **Citation Formatter** - Domain expertise
4. **Article Evaluation Service** - ML inference pipeline
5. **Context Analyzer** - Complex NLP logic
6. **Vector Store Operations** - Core retrieval
7. **Database Repositories** - Async concurrency
8. **Embedding Consistency** - Reproducibility
9. **API Endpoints** - Production reliability
10. **LLM Service** - External API integration

## Running Tests

### Development Workflow
```bash
# Fast feedback during development
pytest tests/unit/ -v --tb=short

# Before committing
pytest tests/integration/ -v

# Full suite with coverage
pytest tests/ --cov=src/thoth --cov-report=term-missing
```

### CI/CD Pipeline
```bash
# Stage 1: Fast tests (< 5 min)
pytest tests/unit/ --cov=src/thoth --cov-report=xml

# Stage 2: Integration (< 15 min)
pytest tests/integration/ --maxfail=5

# Stage 3: E2E + Benchmarks (< 30 min)
pytest tests/e2e/ tests/benchmarks/ --benchmark-only

# Stage 4: Property-based (nightly)
pytest tests/property_based/ --hypothesis-profile=ci
```

### Debugging Failed Tests
```bash
# Run with verbose output
pytest tests/unit/test_metrics.py -vv

# Run single test
pytest tests/unit/test_metrics.py::test_ndcg_at_k_edge_cases

# Drop into debugger on failure
pytest tests/unit/test_metrics.py --pdb

# Run with coverage for specific module
pytest tests/unit/test_metrics.py --cov=src/thoth/rag/evaluation/metrics
```

## Test Data and Fixtures

### Ground Truth Datasets
```python
# Load versioned ground truth
gt_pairs = await load_ground_truth("fixtures/ground_truth/rag_test_set_v1.2.0.json")

# Verify dataset quality
assert len(gt_pairs) >= 100
assert all(pair.ground_truth_answer for pair in gt_pairs)
assert balanced_difficulty_distribution(gt_pairs)
```

### Mock Services
```python
# Mock LLM client
@pytest.fixture
def mock_llm_client():
    class MockLLM:
        async def generate(self, prompt, **kwargs):
            return {"text": "Mocked response", "tokens": 50}
    return MockLLM()

# Test database
@pytest.fixture
async def test_database():
    db = PostgresService(database_url="postgresql://test_db")
    await db.initialize()
    yield db
    await db.drop_all()
```

## Performance Benchmarks

### Target SLAs
- **Citation Resolution**: p50 < 500ms, p99 < 2s
- **RAG Retrieval**: > 10 QPS throughput
- **Embedding Generation**: Linear scaling (O(n))
- **Database Operations**: < 100ms for writes

### Running Benchmarks
```bash
# Run all benchmarks
pytest tests/benchmarks/ --benchmark-only

# Compare against baseline
pytest tests/benchmarks/ --benchmark-compare=baseline

# Generate performance report
pytest tests/benchmarks/ --benchmark-autosave
```

## Success Metrics

### Coverage
- ✅ Overall: 50-55%
- ✅ Critical modules: 75-90%
- ✅ Execution time: < 30 min
- ✅ Flakiness: < 1%

### Quality
- ✅ Property tests: 5+ edge cases/month
- ✅ Benchmark stability: < 10% variance
- ✅ E2E success: > 95%
- ✅ Test isolation: 100%

### Research Credibility
- ✅ Metric correctness: 100%
- ✅ Reproducibility: 100%
- ✅ Ground truth IAA: > 0.8
- ✅ Statistical rigor: All claims tested

## Contributing

### Adding New Tests
1. **Determine test type** (unit, integration, e2e, property, benchmark)
2. **Follow naming convention**: `test_<component>_<behavior>.py`
3. **Use appropriate fixtures** from `conftest.py`
4. **Include docstrings** explaining what is being tested
5. **Add parametrized tests** for edge cases
6. **Update coverage targets** if testing new modules

### Test Quality Checklist
- [ ] Test is deterministic (no random failures)
- [ ] Test is isolated (no dependencies on other tests)
- [ ] Test is fast (< 1s for unit tests)
- [ ] Test has clear assertions with messages
- [ ] Test covers edge cases (empty, null, invalid inputs)
- [ ] Test includes docstring explaining purpose

## Troubleshooting

### Common Issues

**Import errors**
```bash
# Ensure package is installed in editable mode
pip install -e .
```

**Database connection errors**
```bash
# Start test database
docker-compose up -d test-db
```

**Slow tests**
```bash
# Identify slow tests
pytest tests/unit/ --durations=10

# Run only fast tests
pytest tests/unit/ -m "not slow"
```

**Flaky tests**
```bash
# Run test multiple times
pytest tests/unit/test_flaky.py --count=10

# Track flakiness
pytest tests/unit/ --flake-finder --flake-runs=10
```

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [hypothesis (Property-Based Testing)](https://hypothesis.readthedocs.io/)
- [pytest-benchmark](https://pytest-benchmark.readthedocs.io/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)

## Maintenance

### Quarterly Reviews
- [ ] Review coverage gaps
- [ ] Update ground truth datasets
- [ ] Refresh benchmark baselines
- [ ] Optimize slow tests

### Continuous Improvement
- [ ] Monitor and fix flaky tests
- [ ] Convert production bugs to test cases
- [ ] Expand property-based test generators
- [ ] Keep fixtures in sync with production

---

**Last Updated**: 2025-12-31
**Version**: 1.0
**Maintainer**: Project Thoth Development Team

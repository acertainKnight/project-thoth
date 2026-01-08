# Project Thoth Test Strategy

**Target Coverage**: 50%+ for Applied Scientist/Research Engineer Portfolio
**Focus**: ML Evaluation Rigor, Research Reproducibility, Production Reliability
**Codebase Size**: ~12,600 Python files
**Testing Philosophy**: Demonstrate understanding of ML systems, not just code coverage

---

## Executive Summary

This test strategy is designed for an **Applied Scientist/Research Engineer** portfolio, emphasizing ML evaluation best practices over traditional software testing metrics. The goal is to demonstrate:

1. **ML Evaluation Rigor**: Correct metric calculation, ground truth validation, statistical significance
2. **Research Reproducibility**: Deterministic tests, seed control, versioned datasets
3. **Production Reliability**: Async safety, race conditions, resource management
4. **System Understanding**: Edge cases, error modes, performance characteristics

**Why 50% coverage?** For research ML systems, 50%+ strategic coverage of critical paths demonstrates engineering rigor without over-testing experimental components that change frequently.

---

## Test Architecture

### 1. Unit Tests (30% of coverage, ~15% of total codebase)

**Purpose**: Validate core algorithms and data structures in isolation

#### Priority Components:
- **Citation parsing algorithms** (`src/thoth/analyze/citations/`)
- **String matching and confidence scoring** (`src/thoth/utilities/schemas/`)
- **Metric calculation** (`src/thoth/rag/evaluation/metrics.py`)
- **Ground truth generation** (`src/thoth/rag/evaluation/ground_truth.py`)
- **Pydantic schemas** (`src/thoth/utilities/schemas/`)

#### Testing Approach:
```python
# Property-based testing for citation formatters
@given(citation=citation_strategy())
def test_citation_formatter_idempotent(citation):
    """Citation formatting should be idempotent."""
    formatted_once = format_citation(citation, style='ieee')
    formatted_twice = format_citation(citation, style='ieee')
    assert formatted_once == formatted_twice

# Deterministic tests with fixed seeds
def test_ground_truth_generation_reproducible():
    """Ground truth generation must be reproducible."""
    seed = 42
    gt_gen = GroundTruthGenerator(seed=seed)
    pairs_1 = gt_gen.generate(n=10)

    gt_gen = GroundTruthGenerator(seed=seed)
    pairs_2 = gt_gen.generate(n=10)

    assert pairs_1 == pairs_2, "Ground truth generation not deterministic"

# Edge case testing for metrics
@pytest.mark.parametrize("retrieved,relevant,expected", [
    ([], [], 0.0),  # Empty input
    (["doc1"], [], 0.0),  # No relevant docs
    ([], ["doc1"], 0.0),  # No retrieved docs
    (["doc1", "doc2"], ["doc1"], 0.5),  # Partial match
    (["doc1"], ["doc1", "doc2"], 0.5),  # Missing relevant
])
def test_precision_at_k_edge_cases(retrieved, relevant, expected):
    """Precision@K must handle edge cases correctly."""
    result = calculate_precision_at_k(retrieved, relevant, k=2)
    assert result == expected
```

#### Files to Test:
```
tests/unit/citations/
├── test_citation_formatter.py          # 20 tests (5 styles × 4 edge cases)
├── test_citation_schema.py             # 15 tests (field validation, updates)
└── test_citation_extraction.py         # 10 tests (parsing robustness)

tests/unit/evaluation/
├── test_metrics_calculation.py         # 30 tests (each metric × edge cases)
├── test_ground_truth_generation.py     # 25 tests (reproducibility, sampling)
├── test_embedding_consistency.py       # 15 tests (cosine similarity, normalization)
└── test_retrieval_scoring.py           # 20 tests (ranking, relevance)

tests/unit/services/
├── test_article_service.py             # 25 tests (evaluation logic)
├── test_discovery_service.py           # 20 tests (API integration)
└── test_llm_service.py                 # 15 tests (prompt formatting, retries)
```

**Total Unit Tests**: ~195 tests covering critical algorithmic components

---

### 2. Integration Tests (40% of coverage, ~20% of total codebase)

**Purpose**: Validate component interactions and data pipelines

#### Priority Workflows:
- **Citation resolution pipeline** (parse → search → resolve → format)
- **RAG evaluation pipeline** (index → retrieve → generate → evaluate)
- **Article discovery workflow** (scrape → filter → download → extract)
- **Database operations** (async transactions, concurrent writes)

#### Testing Approach:
```python
# Pipeline integration testing
@pytest.mark.asyncio
async def test_citation_resolution_pipeline_e2e():
    """Test complete citation resolution workflow."""
    # Setup: Create test database with known papers
    async with TestDatabase() as db:
        await db.seed_papers(fixtures.SAMPLE_PAPERS)

        # Execute pipeline
        citation_text = "Smith et al. (2023) Machine Learning Review"
        resolver = CitationResolver(db)

        result = await resolver.resolve(citation_text)

        # Assertions with specific expectations
        assert result.confidence > 0.8, "Should resolve with high confidence"
        assert result.matched_paper_id == "paper_123"
        assert result.matching_strategy == "fuzzy_title_match"
        assert len(result.alternative_matches) >= 2

# Database concurrency testing
@pytest.mark.asyncio
async def test_concurrent_article_writes():
    """Verify database handles concurrent writes correctly."""
    async with TestDatabase() as db:
        articles = [create_test_article(i) for i in range(100)]

        # Write concurrently
        tasks = [db.save_article(article) for article in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no race conditions
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Race conditions detected: {errors}"

        # Verify all saved
        saved_count = await db.count_articles()
        assert saved_count == 100

# RAG pipeline integration
@pytest.mark.asyncio
async def test_rag_evaluation_pipeline():
    """Test RAG pipeline with ground truth validation."""
    # Load ground truth
    gt_pairs = await load_ground_truth("fixtures/rag_test_set.json")

    # Run evaluation
    evaluator = RAGEvaluator(vector_store, llm_client)
    results = await evaluator.evaluate(gt_pairs)

    # Metric validation
    assert results.retrieval.precision_at_5 > 0.7, "P@5 below threshold"
    assert results.retrieval.ndcg_at_10 > 0.6, "NDCG@10 below threshold"
    assert results.answer_quality.token_overlap_score > 0.5

    # Statistical significance
    assert results.total_queries >= 50, "Not enough samples for significance"
    ci_lower, ci_upper = bootstrap_confidence_interval(
        results.retrieval.precision_at_5,
        n_samples=1000
    )
    assert ci_lower > 0.6, "CI lower bound too low"
```

#### Files to Test:
```
tests/integration/
├── pipelines/
│   ├── test_citation_resolution_pipeline.py    # 20 tests
│   ├── test_rag_evaluation_pipeline.py         # 25 tests
│   ├── test_article_discovery_pipeline.py      # 15 tests
│   └── test_knowledge_extraction_pipeline.py   # 20 tests
├── database/
│   ├── test_async_operations.py                # 15 tests (concurrency)
│   ├── test_repository_integration.py          # 20 tests (CRUD)
│   └── test_transaction_safety.py              # 10 tests (rollback, isolation)
├── api/
│   ├── test_research_api_endpoints.py          # 25 tests
│   ├── test_websocket_coordination.py          # 10 tests
│   └── test_mcp_tool_integration.py            # 15 tests
└── external/
    ├── test_arxiv_api_integration.py           # 10 tests (mocked)
    ├── test_semantic_scholar_api.py            # 10 tests (mocked)
    └── test_llm_provider_fallback.py           # 10 tests
```

**Total Integration Tests**: ~205 tests covering critical workflows

---

### 3. End-to-End Tests (15% of coverage, ~8% of total codebase)

**Purpose**: Validate complete user workflows with realistic data

#### Test Scenarios:
```python
@pytest.mark.e2e
@pytest.mark.slow
async def test_researcher_workflow_pdf_to_insights():
    """
    Simulate researcher workflow:
    1. Upload PDF with citations
    2. Extract and resolve citations
    3. Build knowledge graph
    4. Query for insights
    """
    async with E2ETestEnvironment() as env:
        # 1. Upload PDF
        pdf_path = "fixtures/sample_paper_with_citations.pdf"
        upload_result = await env.api_client.upload_pdf(pdf_path)
        paper_id = upload_result["paper_id"]

        # 2. Wait for processing (with timeout)
        await env.wait_for_processing(paper_id, timeout_secs=60)

        # 3. Verify citations extracted
        citations = await env.api_client.get_citations(paper_id)
        assert len(citations) >= 10, "Should extract at least 10 citations"

        # 4. Verify resolution quality
        resolved = [c for c in citations if c.confidence > 0.7]
        resolution_rate = len(resolved) / len(citations)
        assert resolution_rate > 0.6, f"Resolution rate {resolution_rate} too low"

        # 5. Query knowledge graph
        query_result = await env.api_client.rag_query(
            question="What are the main contributions of this paper?",
            paper_id=paper_id
        )

        # 6. Validate answer quality
        assert query_result.confidence > 0.7
        assert len(query_result.sources) >= 2
        assert paper_id in [s.paper_id for s in query_result.sources]

@pytest.mark.e2e
async def test_discovery_to_analysis_workflow():
    """
    Test automated discovery and analysis:
    1. Configure discovery source
    2. Run discovery job
    3. Filter results
    4. Download relevant papers
    5. Extract and analyze
    """
    # Implementation similar to above
    pass
```

#### Files to Test:
```
tests/e2e/
├── test_pdf_processing_workflow.py         # 5 major workflows
├── test_citation_resolution_workflow.py    # 5 major workflows
├── test_rag_query_workflow.py              # 5 major workflows
├── test_discovery_automation_workflow.py   # 5 major workflows
└── test_knowledge_graph_building.py        # 5 major workflows
```

**Total E2E Tests**: ~25 comprehensive workflow tests

---

### 4. Property-Based Tests (5% of coverage)

**Purpose**: Discover edge cases through generative testing

#### Focus Areas:
```python
from hypothesis import given, strategies as st

# String matching robustness
@given(
    text1=st.text(min_size=1, max_size=100),
    text2=st.text(min_size=1, max_size=100)
)
def test_fuzzy_matching_symmetric(text1, text2):
    """Fuzzy matching should be symmetric."""
    score_1_2 = fuzzy_match(text1, text2)
    score_2_1 = fuzzy_match(text2, text1)
    assert abs(score_1_2 - score_2_1) < 1e-6

# Citation parsing robustness
@given(citation=st.builds(
    Citation,
    title=st.text(min_size=5, max_size=200),
    authors=st.lists(st.text(min_size=2, max_size=50), min_size=1, max_size=10),
    year=st.integers(min_value=1900, max_value=2030) | st.none(),
))
def test_citation_formatter_no_crashes(citation):
    """Citation formatter should never crash on valid inputs."""
    for style in CitationStyle:
        result = format_citation(citation, style)
        assert isinstance(result, str)
        assert len(result) > 0

# Metric calculation properties
@given(
    scores=st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=100)
)
def test_ndcg_bounded(scores):
    """NDCG should always be between 0 and 1."""
    retrieved = [f"doc_{i}" for i in range(len(scores))]
    relevant = [f"doc_{i}" for i, s in enumerate(scores) if s > 0.5]

    ndcg = calculate_ndcg_at_k(retrieved, relevant, k=10)
    assert 0.0 <= ndcg <= 1.0
```

#### Files to Test:
```
tests/property_based/
├── test_citation_properties.py         # 10 properties
├── test_string_matching_properties.py  # 10 properties
├── test_metric_properties.py           # 10 properties
└── test_confidence_scoring_properties.py # 10 properties
```

**Total Property-Based Tests**: ~40 generative tests

---

### 5. Benchmark Tests (10% of coverage)

**Purpose**: Validate performance characteristics and detect regressions

#### Key Benchmarks:
```python
@pytest.mark.benchmark
def test_citation_resolution_latency(benchmark):
    """Citation resolution should complete within SLA."""
    resolver = CitationResolver()
    citation_text = "Smith et al. (2023) Deep Learning Review"

    result = benchmark(resolver.resolve, citation_text)

    # Latency assertions
    assert benchmark.stats['mean'] < 0.5, "Mean latency > 500ms"
    assert benchmark.stats['max'] < 2.0, "Max latency > 2s"

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_rag_retrieval_throughput():
    """RAG retrieval should handle >10 QPS."""
    vector_store = await setup_test_vector_store(n_docs=1000)
    queries = load_test_queries(n=100)

    start_time = time.time()
    results = await asyncio.gather(*[
        vector_store.search(q, k=10) for q in queries
    ])
    duration = time.time() - start_time

    qps = len(queries) / duration
    assert qps > 10, f"Throughput {qps:.1f} QPS below target"

@pytest.mark.benchmark
def test_embedding_generation_performance():
    """Embedding generation should scale linearly."""
    embedder = EmbeddingGenerator()

    # Measure scaling
    timings = {}
    for n_docs in [10, 100, 1000]:
        docs = [f"Document {i}" for i in range(n_docs)]

        start = time.time()
        embeddings = embedder.embed_batch(docs)
        duration = time.time() - start

        timings[n_docs] = duration

    # Verify linear scaling (within tolerance)
    ratio_10_100 = timings[100] / timings[10]
    ratio_100_1000 = timings[1000] / timings[100]

    assert 8 <= ratio_10_100 <= 12, "Non-linear scaling detected"
    assert 8 <= ratio_100_1000 <= 12, "Non-linear scaling detected"
```

#### Files to Test:
```
tests/benchmarks/
├── test_citation_resolution_performance.py    # 10 benchmarks
├── test_rag_retrieval_performance.py          # 10 benchmarks
├── test_embedding_generation_performance.py   # 10 benchmarks
├── test_database_query_performance.py         # 10 benchmarks
└── test_llm_inference_performance.py          # 10 benchmarks
```

**Total Benchmark Tests**: ~50 performance tests

---

## TOP 10 Most Critical Components to Test

These components are **essential for ML/research credibility** and demonstrate understanding of ML systems:

### 1. RAG Evaluation Metrics (`src/thoth/rag/evaluation/metrics.py`)
**Why**: Core ML evaluation - incorrect metrics = invalid research
**Tests**: 30+ tests covering all metric edge cases, mathematical properties
**Key Focus**: NDCG calculation, MRR correctness, statistical properties

### 2. Ground Truth Generation (`src/thoth/rag/evaluation/ground_truth.py`)
**Why**: Reproducibility is critical for research - flaky ground truth = unreliable benchmarks
**Tests**: 25+ tests for reproducibility, sampling strategies, dataset quality
**Key Focus**: Deterministic generation with seeds, balanced difficulty distribution

### 3. Citation Formatter (`src/thoth/analyze/citations/formatter.py`)
**Why**: Demonstrates attention to detail and domain knowledge
**Tests**: 20+ tests for all citation styles, field combinations, edge cases
**Key Focus**: IEEE/APA/MLA correctness, missing field handling, special characters

### 4. Article Evaluation Service (`src/thoth/services/article_service.py`)
**Why**: Core ML inference pipeline - confidence scoring, relevance ranking
**Tests**: 25+ tests for evaluation logic, confidence calibration, multi-query aggregation
**Key Focus**: Calibrated confidence scores, threshold behavior, edge cases

### 5. Context Analyzer (`src/thoth/discovery/context_analyzer.py`)
**Why**: Complex NLP logic with pattern matching and topic extraction
**Tests**: 30+ tests for regex patterns, topic merging, confidence calculation
**Key Focus**: Pattern robustness, topic similarity logic, frequency tracking

### 6. Vector Store Operations (`src/thoth/rag/vector_store.py`)
**Why**: Core retrieval component - incorrect retrieval = bad RAG performance
**Tests**: 25+ tests for similarity search, batch operations, index consistency
**Key Focus**: Cosine similarity correctness, index updates, concurrent access

### 7. Database Repositories (`src/thoth/repositories/base.py`)
**Why**: Async database operations have race conditions and transaction issues
**Tests**: 20+ tests for concurrent writes, transaction isolation, error handling
**Key Focus**: Race condition prevention, connection pooling, retry logic

### 8. Embedding Consistency (`src/thoth/rag/embeddings.py`)
**Why**: Embeddings must be consistent across sessions for reproducibility
**Tests**: 15+ tests for determinism, normalization, model versioning
**Key Focus**: Same input = same embedding, L2 normalization, version tracking

### 9. API Endpoints (`src/thoth/server/routers/`)
**Why**: Production reliability - handle errors gracefully, validate inputs
**Tests**: 25+ tests for validation, error handling, async behavior
**Key Focus**: Input validation, error responses, rate limiting

### 10. LLM Service (`src/thoth/services/llm/`)
**Why**: External API integration - retry logic, fallbacks, cost tracking
**Tests**: 15+ tests for retries, timeouts, provider fallback, mock responses
**Key Focus**: Exponential backoff, timeout handling, cost calculation

---

## ML Evaluation Best Practices

### Statistical Significance Testing
```python
def test_metric_improvement_statistically_significant():
    """Metric improvements must be statistically significant."""
    baseline_scores = load_baseline_results("v1.0")
    current_scores = run_evaluation("v2.0")

    # Bootstrap confidence intervals
    ci_baseline = bootstrap_ci(baseline_scores, n_iterations=1000)
    ci_current = bootstrap_ci(current_scores, n_iterations=1000)

    # Check for non-overlapping CIs
    assert ci_current[0] > ci_baseline[1], \
        "Improvement not statistically significant at 95% confidence"
```

### Ground Truth Validation
```python
def test_ground_truth_quality():
    """Ground truth must meet quality thresholds."""
    gt_pairs = load_ground_truth()

    # Coverage checks
    assert len(gt_pairs) >= 100, "Need at least 100 test cases"

    # Difficulty distribution
    difficulties = [p.difficulty for p in gt_pairs]
    easy_frac = difficulties.count("easy") / len(difficulties)
    assert 0.2 <= easy_frac <= 0.4, "Difficulty imbalance"

    # Relevance annotation quality
    avg_relevant_docs = np.mean([len(p.ground_truth_doc_ids) for p in gt_pairs])
    assert 1 <= avg_relevant_docs <= 5, "Unrealistic relevance annotations"
```

### Deterministic Testing
```python
@pytest.fixture
def deterministic_environment():
    """Ensure reproducible test environment."""
    # Set all random seeds
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)

    # Set deterministic algorithms
    torch.use_deterministic_algorithms(True)
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'

    yield

    # Cleanup
    del os.environ['CUBLAS_WORKSPACE_CONFIG']

def test_embedding_reproducibility(deterministic_environment):
    """Embeddings must be reproducible."""
    embedder = EmbeddingGenerator(model="all-MiniLM-L6-v2")
    text = "This is a test document."

    embedding_1 = embedder.embed(text)
    embedding_2 = embedder.embed(text)

    np.testing.assert_array_equal(embedding_1, embedding_2)
```

---

## Research Reproducibility

### Version Control for Datasets
```python
@pytest.fixture
def versioned_ground_truth():
    """Load versioned ground truth dataset."""
    version = "v1.2.0"
    gt_path = f"fixtures/ground_truth_{version}.json"

    # Verify checksum
    expected_checksum = "a1b2c3d4e5f6..."
    actual_checksum = compute_checksum(gt_path)
    assert actual_checksum == expected_checksum, \
        f"Ground truth dataset corrupted or modified"

    return load_ground_truth(gt_path)
```

### Experiment Tracking
```python
def test_rag_evaluation_with_tracking():
    """Log all evaluation parameters for reproducibility."""
    config = {
        "model": "all-MiniLM-L6-v2",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "top_k": 10,
        "temperature": 0.7,
        "seed": 42,
    }

    # Run evaluation
    results = run_rag_evaluation(config)

    # Log to experiment tracker
    log_experiment(
        experiment_name="rag_eval",
        config=config,
        metrics=results.to_dict(),
        git_commit=get_git_commit_hash(),
        timestamp=datetime.now().isoformat(),
    )

    assert results.retrieval.precision_at_5 > 0.7
```

---

## Production Reliability

### Async Safety
```python
@pytest.mark.asyncio
async def test_concurrent_citation_resolution():
    """Citation resolver must handle concurrent requests safely."""
    resolver = CitationResolver()
    citations = [f"Citation {i}" for i in range(100)]

    # Resolve concurrently
    tasks = [resolver.resolve(c) for c in citations]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # No crashes
    exceptions = [r for r in results if isinstance(r, Exception)]
    assert len(exceptions) == 0, f"Crashed on {len(exceptions)} requests"

    # No race conditions (check internal state)
    assert resolver._internal_state_consistent()
```

### Resource Limits
```python
@pytest.mark.timeout(30)
@pytest.mark.asyncio
async def test_large_batch_processing_with_limits():
    """Large batches should respect memory limits."""
    processor = DocumentProcessor(max_memory_mb=500)

    # Process large batch
    documents = [create_large_doc() for _ in range(1000)]

    with monitor_memory() as memory_tracker:
        results = await processor.process_batch(documents)

    # Memory limit respected
    peak_memory_mb = memory_tracker.peak_usage_mb
    assert peak_memory_mb < 600, f"Memory limit exceeded: {peak_memory_mb}MB"
```

### Error Recovery
```python
@pytest.mark.asyncio
async def test_api_failure_recovery():
    """System should recover gracefully from API failures."""
    llm_service = LLMService()

    # Simulate API failures
    with mock_api_failures(failure_rate=0.5):
        results = []
        for query in test_queries:
            result = await llm_service.query_with_retry(
                query,
                max_retries=3,
                backoff_factor=2.0
            )
            results.append(result)

    # Most requests should eventually succeed
    success_rate = sum(1 for r in results if r.success) / len(results)
    assert success_rate > 0.9, "Retry logic insufficient"
```

---

## Test Infrastructure

### Fixtures and Test Data
```
tests/fixtures/
├── ground_truth/
│   ├── rag_test_set_v1.2.0.json           # 100 Q&A pairs
│   ├── citation_resolution_cases.json      # 50 citation examples
│   └── checksums.json                      # Dataset verification
├── sample_papers/
│   ├── sample_paper_with_citations.pdf
│   ├── sample_paper_no_citations.pdf
│   └── sample_paper_malformed.pdf
└── mock_responses/
    ├── arxiv_api_responses.json
    ├── semantic_scholar_responses.json
    └── llm_responses.json
```

### Test Utilities
```python
# tests/conftest.py
import pytest
from thoth.services.postgres_service import PostgresService

@pytest.fixture(scope="session")
async def test_database():
    """Provide isolated test database."""
    db = PostgresService(database_url="postgresql://test_db")
    await db.initialize()
    await db.create_schema()

    yield db

    await db.drop_all()
    await db.close()

@pytest.fixture
def mock_llm_client():
    """Mock LLM client with deterministic responses."""
    class MockLLM:
        def __init__(self):
            self.call_count = 0

        async def generate(self, prompt, **kwargs):
            self.call_count += 1
            return {"text": "Mocked response", "tokens": 50}

    return MockLLM()

@pytest.fixture
def sample_citations():
    """Load sample citations for testing."""
    return load_json_fixture("fixtures/citation_samples.json")
```

---

## Coverage Goals by Module

| Module | Target Coverage | Priority | Test Types |
|--------|----------------|----------|------------|
| `rag/evaluation/` | **90%** | Critical | Unit + Integration + Property |
| `analyze/citations/` | **85%** | Critical | Unit + Property |
| `services/article_service.py` | **80%** | Critical | Unit + Integration |
| `discovery/context_analyzer.py` | **75%** | High | Unit + Integration |
| `rag/vector_store.py` | **80%** | High | Unit + Integration + Benchmark |
| `repositories/` | **70%** | High | Integration |
| `server/routers/` | **60%** | Medium | Integration + E2E |
| `utilities/schemas/` | **85%** | Medium | Unit |
| `mcp/tools/` | **50%** | Medium | Integration |
| `pipeline.py` | **70%** | Medium | Integration + E2E |

**Overall Target**: 50-55% total coverage with strategic focus on critical paths

---

## Testing Workflow

### Development
```bash
# Run unit tests during development (fast feedback)
pytest tests/unit/ -v --tb=short

# Run integration tests before committing
pytest tests/integration/ -v

# Run property-based tests (discovery mode)
pytest tests/property_based/ --hypothesis-profile=dev
```

### CI/CD Pipeline
```bash
# Stage 1: Fast tests (< 5 minutes)
pytest tests/unit/ --cov=src/thoth --cov-report=xml

# Stage 2: Integration tests (< 15 minutes)
pytest tests/integration/ --maxfail=5

# Stage 3: E2E + Benchmarks (< 30 minutes)
pytest tests/e2e/ tests/benchmarks/ --benchmark-only

# Stage 4: Property-based (extended, nightly)
pytest tests/property_based/ --hypothesis-profile=ci
```

### Pre-Release
```bash
# Full test suite with coverage report
pytest tests/ --cov=src/thoth --cov-report=html --cov-report=term

# Generate benchmark comparison
pytest tests/benchmarks/ --benchmark-compare=baseline

# Validate ground truth datasets
pytest tests/integration/test_ground_truth_validation.py
```

---

## Success Metrics

### Coverage Metrics
- **Overall coverage**: 50-55%
- **Critical modules**: 75-90%
- **Test execution time**: < 30 minutes for full suite
- **Test flakiness**: < 1% failure rate

### Quality Metrics
- **Property-based tests**: Find at least 5 edge cases in first month
- **Benchmark stability**: < 10% variance across runs
- **E2E test success rate**: > 95%
- **Integration test isolation**: 100% (no test interdependencies)

### Research Credibility Metrics
- **Metric correctness**: 100% (verified against reference implementations)
- **Reproducibility**: 100% (deterministic with seed control)
- **Ground truth quality**: Inter-annotator agreement > 0.8 (if human-labeled)
- **Statistical rigor**: All claims supported by significance tests

---

## Maintenance and Evolution

### Quarterly Reviews
- **Review coverage**: Identify untested critical paths
- **Update ground truth**: Add new test cases for edge cases discovered in production
- **Benchmark baseline**: Update performance baselines
- **Test performance**: Optimize slow tests (target: all tests < 1s except E2E)

### Continuous Improvement
- **Monitor flaky tests**: Track and fix tests with inconsistent results
- **Add regression tests**: Convert production bugs into test cases
- **Expand property-based tests**: Add more generators for edge case discovery
- **Update fixtures**: Keep test data in sync with production distributions

---

## Portfolio Highlights

**This test strategy demonstrates**:

1. ✅ **ML Evaluation Expertise**: Comprehensive metric validation, ground truth quality control
2. ✅ **Research Rigor**: Deterministic testing, statistical significance, reproducibility
3. ✅ **Production Engineering**: Async safety, resource management, error recovery
4. ✅ **System Understanding**: Property-based testing, performance benchmarking, integration testing
5. ✅ **Pragmatic Approach**: Strategic 50% coverage focused on critical paths, not blanket testing

**Key Differentiators for Research Roles**:
- Focus on correctness of ML metrics (NDCG, MRR, Precision@K)
- Ground truth generation and validation
- Deterministic testing for reproducibility
- Statistical significance testing
- Performance benchmarking with realistic workloads

---

## Next Steps

### Phase 1: Foundation (Week 1-2)
1. Set up test infrastructure (`conftest.py`, fixtures)
2. Implement TOP 5 critical component tests
3. Create mock LLM client and test database

### Phase 2: Core Coverage (Week 3-4)
1. Implement unit tests for all TOP 10 components
2. Add integration tests for critical pipelines
3. Achieve 30% overall coverage

### Phase 3: Advanced Testing (Week 5-6)
1. Add property-based tests
2. Implement benchmark tests
3. Create E2E test scenarios
4. Achieve 50% overall coverage

### Phase 4: Polish (Week 7-8)
1. Optimize slow tests
2. Fix flaky tests
3. Generate coverage reports
4. Document testing best practices

---

**Author**: Project Thoth Development Team
**Date**: 2025-12-31
**Version**: 1.0
**Review Frequency**: Quarterly

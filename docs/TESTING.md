# Thoth Test Suite Documentation

Comprehensive testing framework for the Thoth research assistant, featuring end-to-end integration tests, property-based robustness validation, and performance benchmarks.

## Test Organization

```
tests/
├── conftest.py                              # Shared fixtures and pytest configuration
├── e2e/                                     # End-to-end integration tests
│   ├── test_citation_resolution_workflow.py # Complete citation resolution pipeline
│   └── test_evaluation_pipeline.py          # Analysis evaluation workflow
├── unit/
│   └── properties/                          # Property-based tests
│       ├── test_citation_parser_properties.py  # Citation parsing robustness
│       └── test_matching_properties.py         # Fuzzy matching properties
└── benchmarks/
    └── test_resolution_performance.py       # Performance benchmarks
```

## Test Types

### 1. End-to-End (E2E) Integration Tests

**Purpose**: Validate complete workflows from input to storage.

**Files**:
- `test_citation_resolution_workflow.py`: Tests citation resolution pipeline
  - Single citation resolution
  - Batch processing with concurrency
  - API fallback chain behavior
  - Database persistence
  - Error recovery

- `test_evaluation_pipeline.py`: Tests analysis evaluation system
  - Ground truth generation
  - LLM analysis execution
  - Metrics calculation
  - Report generation

**Run E2E tests**:
```bash
# All E2E tests
pytest tests/e2e/ -v -m e2e

# Specific workflow
pytest tests/e2e/test_citation_resolution_workflow.py -v

# With coverage
pytest tests/e2e/ --cov=thoth.analyze --cov-report=html
```

### 2. Property-Based Tests

**Purpose**: Validate universal properties that should hold for ALL inputs using Hypothesis framework.

**Files**:
- `test_citation_parser_properties.py`: Citation parsing robustness
  - Parser never crashes on any input
  - Idempotency (parse → serialize → parse)
  - Unicode handling
  - Malformed input graceful handling
  - Field validation

- `test_matching_properties.py`: Fuzzy matching properties
  - **Symmetry**: `match(A, B) = match(B, A)`
  - **Reflexivity**: `match(A, A) = 1.0`
  - **Confidence bounds**: `0 ≤ score ≤ 1`
  - **Monotonicity**: More similar → higher scores
  - **Normalization consistency**

**Run property tests**:
```bash
# All property tests
pytest tests/unit/properties/ -v -m property

# With more examples (thorough validation)
pytest tests/unit/properties/ -v --hypothesis-show-statistics

# Specific property test
pytest tests/unit/properties/test_matching_properties.py::test_weighted_similarity_symmetry -v
```

### 3. Performance Benchmarks

**Purpose**: Measure throughput, latency, and scalability.

**File**: `test_resolution_performance.py`

**Metrics Measured**:
- **Throughput**: Citations resolved per second
- **Latency**: P50, P95, P99 resolution times
- **Scalability**: Performance with increasing batch sizes
- **Memory usage**: RAM consumption during batch processing
- **Cache efficiency**: Hit rate and impact

**Performance Targets**:
- Single citation: <500ms average
- Batch of 100: <30 seconds total (<300ms per citation)
- Throughput: >3 citations/second sustained
- Memory: <500MB for 1000 citations

**Run benchmarks**:
```bash
# All benchmarks
pytest tests/benchmarks/ -v -m benchmark

# With detailed statistics
pytest tests/benchmarks/ -v --benchmark-verbose

# Save benchmark results
pytest tests/benchmarks/ --benchmark-autosave

# Compare with previous runs
pytest tests/benchmarks/ --benchmark-compare
```

## Installation

Install test dependencies:

```bash
# Basic test dependencies
pip install -e ".[test]"

# All dependencies including dev tools
pip install -e ".[dev,test]"
```

## Running Tests

### Quick Start

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=thoth --cov-report=html

# Run specific test type
pytest tests/e2e/ -v -m e2e
pytest tests/unit/properties/ -v -m property
pytest tests/benchmarks/ -v -m benchmark
```

## Test Coverage Summary

The test suite provides comprehensive validation:

- **E2E Tests**: 2 files, 20+ test scenarios covering complete workflows
- **Property Tests**: 2 files, 40+ properties validating robustness
- **Benchmarks**: 1 file, 15+ performance metrics tracked

**Key Features Tested**:
- ✅ Citation resolution pipeline (input → API → storage)
- ✅ Batch processing with concurrency
- ✅ Fuzzy matching algorithm correctness
- ✅ Database persistence and retrieval
- ✅ Error recovery and graceful degradation
- ✅ Unicode and internationalization
- ✅ Performance and scalability
- ✅ Memory efficiency

See the full test files for detailed documentation of each test scenario.

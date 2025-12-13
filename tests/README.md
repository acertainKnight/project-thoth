# Thoth Testing Suite

Comprehensive testing infrastructure for Thoth migration and services.

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── migration/                  # Migration-specific tests
│   ├── test_extraction.py     # Data extraction tests
│   ├── test_transformation.py # Data transformation tests
│   └── test_loading.py        # Data loading tests
├── integration/               # Integration tests
│   ├── test_migration_e2e.py # End-to-end migration tests
│   └── test_services.py      # Service integration tests
├── performance/              # Performance benchmarks
│   └── test_queries.py      # Query performance tests
├── validation/              # Data validation tests
│   └── test_data_integrity.py
└── fixtures/               # Sample data for testing
    ├── sample_citation_graph.json
    ├── sample_processed_pdfs.json
    └── sample_embeddings.json
```

## Running Tests

### Run all tests:
```bash
pytest
```

### Run specific test categories:
```bash
# Unit tests
pytest tests/migration/

# Integration tests
pytest tests/integration/

# Performance tests
pytest tests/performance/ -v

# Data validation tests
pytest tests/validation/
```

### Run with coverage:
```bash
pytest --cov=src/thoth --cov-report=html
```

### Run specific markers:
```bash
# Migration tests only
pytest -m migration

# Performance tests only
pytest -m performance

# Async tests only
pytest -m asyncio
```

## Test Coverage Goals

- **Overall Coverage**: ≥80%
- **Statements**: ≥80%
- **Branches**: ≥75%
- **Functions**: ≥80%
- **Lines**: ≥80%

## Performance Targets

- **Vector Similarity Search**: <100ms
- **Full-Text Search**: <50ms
- **Citation Graph Traversal**: <200ms
- **Concurrent Load**: 100+ users

## Test Features

### Unit Tests (tests/migration/)
- Data extraction from JSON sources
- Path normalization and resolution
- Data transformation and validation
- Batch loading operations
- Error handling and recovery

### Integration Tests (tests/integration/)
- End-to-end migration pipeline
- Service integration with Postgres
- Backward compatibility
- Feature flag switching
- Connection pool management

### Performance Tests (tests/performance/)
- Vector similarity search benchmarks
- Full-text search performance
- Citation graph query optimization
- Concurrent load testing
- Index performance validation

### Validation Tests (tests/validation/)
- Data integrity verification
- Row count comparison
- Checksum validation
- Relationship integrity
- Embedding accuracy

## Fixtures

### Available Fixtures (conftest.py)
- `temp_dir`: Temporary directory for tests
- `mock_config`: Mock configuration object
- `sample_tracker_data`: Sample processed_pdfs.json data
- `sample_citation_graph`: Sample citations graph
- `sample_embeddings`: Sample embedding data
- `mock_db_session`: Mock database session
- `async_mock_db_session`: Async mock database session
- `mock_vector_store`: Mock vector store

### Sample Data Files
- `fixtures/sample_citation_graph.json`: Citation graph with 3 papers
- `fixtures/sample_processed_pdfs.json`: Processed PDFs tracker
- `fixtures/sample_embeddings.json`: Sample 768-dim embeddings

## Writing New Tests

### Test Naming Convention
- Test files: `test_<feature>.py`
- Test classes: `Test<Feature>`
- Test functions: `test_<scenario>`

### Example Test:
```python
import pytest

class TestMyFeature:
    """Test my feature functionality."""

    def test_basic_functionality(self, mock_config):
        """Test basic feature works."""
        # Arrange
        service = MyService(mock_config)

        # Act
        result = service.my_method()

        # Assert
        assert result == expected_value

    @pytest.mark.asyncio
    async def test_async_functionality(self, async_mock_db_session):
        """Test async feature works."""
        result = await service.async_method()
        assert result is not None
```

## CI/CD Integration

Tests are automatically run on:
- Pull requests
- Commits to main branch
- Pre-commit hooks (if configured)

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure `src/thoth` is in PYTHONPATH
2. **Async test failures**: Check asyncio_mode in pytest.ini
3. **Coverage too low**: Add more test cases or remove untestable code
4. **Slow tests**: Use `-m "not slow"` to skip slow tests

### Debug Mode
```bash
# Run with verbose output and no capture
pytest -vv -s tests/migration/test_extraction.py

# Run single test with pdb on failure
pytest --pdb tests/integration/test_migration_e2e.py::TestEndToEndMigration::test_full_tracker_migration_pipeline
```

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Ensure tests pass locally
3. Maintain ≥80% coverage
4. Add appropriate markers
5. Update this README if needed

## Test Maintenance

- Review and update fixtures quarterly
- Keep sample data realistic and minimal
- Remove obsolete tests
- Update performance targets as system improves

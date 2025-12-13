# Integration Tests Quick Start Guide

## 🚀 Run Tests Immediately

```bash
# Run all integration tests
pytest tests/integration/test_research_questions_api.py -v

# Run with coverage
pytest tests/integration/test_research_questions_api.py --cov=thoth.server.routers --cov-report=term

# Run specific test
pytest tests/integration/test_research_questions_api.py::test_create_research_question_success -v

# Run all create tests
pytest tests/integration/test_research_questions_api.py -k "test_create" -v

# Run with detailed output
pytest tests/integration/test_research_questions_api.py -vvs
```

## 📋 Test Categories

```bash
# CREATE tests (7 tests)
pytest tests/integration/test_research_questions_api.py -k "test_create" -v

# LIST tests (3 tests)
pytest tests/integration/test_research_questions_api.py -k "test_list" -v

# GET tests (3 tests)
pytest tests/integration/test_research_questions_api.py -k "test_get_research_question" -v

# UPDATE tests (5 tests)
pytest tests/integration/test_research_questions_api.py -k "test_update" -v

# DELETE tests (4 tests)
pytest tests/integration/test_research_questions_api.py -k "test_delete" -v

# DISCOVERY tests (4 tests)
pytest tests/integration/test_research_questions_api.py -k "test_trigger" -v

# ARTICLES tests (4 tests)
pytest tests/integration/test_research_questions_api.py -k "test_get_matched_articles" -v

# STATISTICS tests (3 tests)
pytest tests/integration/test_research_questions_api.py -k "test_get_question_statistics" -v

# Permission tests
pytest tests/integration/test_research_questions_api.py -k "permission" -v

# Validation tests
pytest tests/integration/test_research_questions_api.py -k "invalid or empty or missing" -v
```

## 🎯 Common Use Cases

### Before Committing
```bash
# Run tests with coverage
pytest tests/integration/test_research_questions_api.py --cov=thoth.server.routers --cov-report=html

# Check coverage report
open htmlcov/index.html
```

### During Development
```bash
# Run tests in watch mode (requires pytest-watch)
ptw tests/integration/test_research_questions_api.py -- -v

# Run failed tests only
pytest tests/integration/test_research_questions_api.py --lf -v

# Run with debugging on first failure
pytest tests/integration/test_research_questions_api.py -x --pdb
```

### CI/CD Pipeline
```bash
# Run with strict settings
pytest tests/integration/test_research_questions_api.py \
  --strict-markers \
  --tb=short \
  --cov=thoth.server.routers \
  --cov-report=xml \
  --junitxml=test-results.xml
```

## 🔧 Setup Requirements

### Install Dependencies
```bash
# Using uv
uv pip install -e ".[test]"

# Or using pip
pip install -e ".[test]"
```

### Required Packages
- pytest >= 8.3.5
- pytest-asyncio >= 0.26.0
- pytest-cov >= 6.1.1
- pytest-mock >= 3.14.0
- fastapi
- pydantic

## 📊 Expected Output

### Success
```
tests/integration/test_research_questions_api.py::test_create_research_question_success PASSED [ 2%]
tests/integration/test_research_questions_api.py::test_create_research_question_missing_name PASSED [ 5%]
...
===================== 37 passed in 2.45s =====================
```

### With Coverage
```
----------- coverage: platform linux, python 3.11.0 -----------
Name                                               Stmts   Miss  Cover
----------------------------------------------------------------------
src/thoth/server/routers/research_questions.py      145     12    92%
----------------------------------------------------------------------
TOTAL                                                145     12    92%
```

## ❌ Common Issues

### Issue: "No module named 'thoth'"
**Solution**: Install package in development mode
```bash
uv pip install -e .
```

### Issue: "RuntimeError: no running event loop"
**Solution**: Ensure pytest-asyncio is installed and configured
```bash
uv pip install pytest-asyncio
```

### Issue: "fixture 'mock_service_manager' not found"
**Solution**: Check conftest.py exists or fixtures are in test file
```bash
# Verify fixtures
pytest tests/integration/test_research_questions_api.py --fixtures
```

### Issue: Tests pass but coverage is low
**Solution**: Add more edge cases and error path tests
```bash
# Generate coverage report to see what's missing
pytest tests/integration/test_research_questions_api.py --cov --cov-report=html
open htmlcov/index.html
```

## 📚 Test Structure

```
tests/integration/test_research_questions_api.py
├── Fixtures (lines 1-150)
│   ├── mock_service_manager
│   ├── sample_question_data
│   ├── sample_articles
│   └── client
├── Create Tests (lines 151-250)
├── List Tests (lines 251-300)
├── Get Tests (lines 301-350)
├── Update Tests (lines 351-450)
├── Delete Tests (lines 451-500)
├── Discovery Tests (lines 501-550)
├── Articles Tests (lines 551-600)
├── Statistics Tests (lines 601-650)
└── Edge Cases (lines 651-700)
```

## 🔍 Debugging Tips

### Print Request/Response
```python
# Add to test
print(f"Request: {request.json()}")
print(f"Response: {response.json()}")
print(f"Status: {response.status_code}")
```

### Check Mock Calls
```python
# Verify mock was called
print(mock_service.method.call_count)
print(mock_service.method.call_args)
print(mock_service.method.call_args_list)
```

### Run with Verbose Logging
```bash
pytest tests/integration/test_research_questions_api.py -vvs --log-cli-level=DEBUG
```

## 📝 Writing New Tests

### Template
```python
@pytest.mark.asyncio
async def test_new_endpoint_success(client, mock_service_manager, sample_user_id):
    """Test description here."""
    # Arrange
    mock_service_manager.service.method.return_value = expected_value

    # Act
    response = client.post(
        "/api/endpoint",
        json={"data": "value"},
        headers={"X-User-ID": sample_user_id},
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["field"] == expected_value
    mock_service_manager.service.method.assert_called_once()
```

## 🎓 Learning Resources

- **Full Documentation**: `tests/integration/README_RESEARCH_QUESTIONS_API.md`
- **Test Patterns**: Review existing tests in the file
- **Service Layer**: `tests/services/test_research_question_service.py`
- **Pytest Docs**: https://docs.pytest.org/
- **FastAPI Testing**: https://fastapi.tiangolo.com/tutorial/testing/

## 💡 Pro Tips

1. **Use `-k` flag** to run subset of tests by name pattern
2. **Use `--lf`** to re-run only last failed tests
3. **Use `-x`** to stop on first failure
4. **Use `--pdb`** to drop into debugger on failure
5. **Use `-vv`** for extra verbose output
6. **Use `--durations=10`** to see slowest tests
7. **Use `--markers`** to see available test markers

## 🤝 Contributing

When adding tests:
1. Follow AAA pattern (Arrange-Act-Assert)
2. Use descriptive test names
3. Mock at service layer, not lower
4. Test both success and error paths
5. Add docstrings explaining what you're testing
6. Update this guide if adding new patterns

## 🚨 Important Notes

- Tests use **mocks** - no real database or HTTP calls
- All endpoints require **X-User-ID** header
- UUIDs must be valid format (use `uuid4()`)
- Relevance scores must be 0.0-1.0 range
- At least one keyword OR topic required

## ✅ Checklist

Before committing:
- [ ] All tests pass
- [ ] Coverage >= 80%
- [ ] No skipped tests (unless documented)
- [ ] Test names are descriptive
- [ ] Docstrings added
- [ ] Edge cases covered
- [ ] Error paths tested

## 📞 Getting Help

- Check `README_RESEARCH_QUESTIONS_API.md` for detailed docs
- Review `docs/WEEK4-INTEGRATION-TESTS-SUMMARY.md` for overview
- Ask QA team for test patterns
- Refer to service layer tests for examples

---

**Ready to test?** Start with:
```bash
pytest tests/integration/test_research_questions_api.py -v
```

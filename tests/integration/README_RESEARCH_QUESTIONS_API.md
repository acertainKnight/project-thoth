# Research Questions API Integration Tests

## Overview

Comprehensive integration test suite for the Research Questions API endpoints. These tests validate HTTP layer behavior, request/response handling, validation, permissions, and error handling.

## Test Structure

### File Location
`tests/integration/test_research_questions_api.py`

### Test Coverage: 37 Test Cases

#### 1. Create Endpoint (7 tests)
- ✅ Successful creation with valid data
- ✅ Missing required field (name)
- ✅ Empty name validation
- ✅ No keywords or topics validation
- ✅ Empty sources validation
- ✅ Invalid relevance score (>1.0)
- ✅ Duplicate name handling

#### 2. List Endpoint (3 tests)
- ✅ List active questions only
- ✅ List all questions (including inactive)
- ✅ Empty list handling

#### 3. Get Single Question (3 tests)
- ✅ Successful retrieval
- ✅ 404 for non-existent question
- ✅ 403 for permission denied

#### 4. Update Endpoint (5 tests)
- ✅ Successful full update
- ✅ Partial update (single field)
- ✅ Invalid relevance score validation
- ✅ 404 for non-existent question
- ✅ 403 for permission denied

#### 5. Delete Endpoint (4 tests)
- ✅ Soft delete (default behavior)
- ✅ Hard delete with query parameter
- ✅ 404 for non-existent question
- ✅ 403 for permission denied

#### 6. Manual Discovery Trigger (4 tests)
- ✅ Successful discovery run
- ✅ Custom max_articles parameter
- ✅ 404 for non-existent question
- ✅ Error handling for service failures

#### 7. Get Matched Articles (4 tests)
- ✅ Successful article retrieval
- ✅ Pagination (limit/offset)
- ✅ Filter by minimum relevance score
- ✅ 404 for non-existent question

#### 8. Get Statistics (3 tests)
- ✅ Successful statistics retrieval
- ✅ 404 for non-existent question
- ✅ 403 for permission denied

#### 9. Edge Cases & Error Handling (4 tests)
- ✅ Invalid UUID format handling
- ✅ Wildcard source ['*'] creation
- ✅ Empty update handling
- ✅ Concurrent creation race condition

## Running the Tests

### Run All Integration Tests
```bash
pytest tests/integration/test_research_questions_api.py -v
```

### Run Specific Test Category
```bash
# Create endpoint tests
pytest tests/integration/test_research_questions_api.py -k "test_create" -v

# Update endpoint tests
pytest tests/integration/test_research_questions_api.py -k "test_update" -v

# Permission tests
pytest tests/integration/test_research_questions_api.py -k "permission" -v
```

### Run with Coverage
```bash
pytest tests/integration/test_research_questions_api.py --cov=thoth.server.routers.research_questions --cov-report=html
```

## Test Patterns

### Mocking Strategy
Tests use `unittest.mock.AsyncMock` to mock:
- `ServiceManager` - Main service coordinator
- `ResearchQuestionService` - Business logic layer
- `DiscoveryOrchestrator` - Discovery execution

### Authentication
All endpoints require `X-User-ID` header:
```python
headers={"X-User-ID": "test_user_123"}
```

### Request/Response Examples

#### Create Question
```python
# Request
POST /api/research/questions
{
    "name": "Machine Learning Research",
    "keywords": ["neural networks", "deep learning"],
    "topics": ["artificial intelligence"],
    "selected_sources": ["arxiv", "pubmed"],
    "min_relevance_score": 0.7
}

# Response (201 Created)
{
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Machine Learning Research",
    "is_active": true,
    "created_at": "2024-12-05T10:00:00"
}
```

#### Update Question
```python
# Request
PATCH /api/research/questions/{question_id}
{
    "min_relevance_score": 0.8,
    "keywords": ["new keyword"]
}

# Response (200 OK)
{
    "success": true
}
```

#### Get Matched Articles
```python
# Request
GET /api/research/questions/{question_id}/articles?min_relevance=0.8&limit=10

# Response (200 OK)
{
    "articles": [
        {
            "id": "...",
            "doi": "10.1234/test1",
            "title": "Test Paper",
            "relevance_score": 0.85,
            "matched_keywords": ["neural networks"]
        }
    ]
}
```

## Validation Rules Tested

### Name Validation
- Cannot be empty or whitespace-only
- Must be unique per user
- Required field

### Keywords/Topics Validation
- At least one keyword OR topic required
- Empty lists for both are invalid

### Sources Validation
- Cannot be empty list
- Accepts wildcard ['*'] for all sources
- Accepts specific source names

### Relevance Score Validation
- Must be between 0.0 and 1.0 (inclusive)
- Validated on create and update

## Error Responses

### 400 Bad Request
Validation errors, business logic violations:
```json
{
    "detail": "Question name cannot be empty"
}
```

### 401 Unauthorized
Missing authentication header:
```json
{
    "detail": "Authentication required"
}
```

### 403 Forbidden
Permission denied (wrong user):
```json
{
    "detail": "User does not have permission to access this question"
}
```

### 404 Not Found
Resource doesn't exist:
```json
{
    "detail": "Question not found"
}
```

### 422 Unprocessable Entity
Invalid request format (e.g., invalid UUID):
```json
{
    "detail": [
        {
            "loc": ["path", "question_id"],
            "msg": "value is not a valid uuid",
            "type": "type_error.uuid"
        }
    ]
}
```

### 500 Internal Server Error
Unexpected server errors:
```json
{
    "detail": "Internal server error"
}
```

## Fixtures

### `mock_service_manager`
Mock ServiceManager with research_question and discovery_orchestrator services.

### `sample_question_data`
Valid question data for creation tests:
```python
{
    "name": "Machine Learning Research",
    "keywords": ["neural networks", "deep learning"],
    "topics": ["artificial intelligence"],
    "selected_sources": ["arxiv", "pubmed"],
    "min_relevance_score": 0.7
}
```

### `sample_articles`
Sample matched articles with relevance scores, metadata, and user flags.

### `client`
FastAPI TestClient configured with mocked dependencies.

## Test Maintenance

### Adding New Tests
1. Follow existing patterns for consistency
2. Use descriptive test names: `test_<endpoint>_<scenario>`
3. Include arrange-act-assert comments
4. Mock at the service layer, not repository
5. Test both success and error paths

### Updating Tests for API Changes
1. Update request/response models
2. Update validation rules
3. Add new test cases for new fields
4. Keep error handling tests current

## Integration with CI/CD

These tests should run:
- On every pull request
- Before merging to main
- In staging environment tests
- As part of release validation

### Coverage Goals
- Line coverage: >80%
- Branch coverage: >75%
- All endpoints tested
- All error paths covered

## Related Documentation
- Service Layer Tests: `tests/services/test_research_question_service.py`
- Repository Tests: `tests/repositories/test_research_question_repository.py`
- API Documentation: `docs/api/research_questions.md`
- Architecture: `docs/architecture/week4-api-layer.md`

## Contact
For questions about these tests, contact the QA team or backend-dev team.

# TEST STRATEGY - Project Thoth

## Executive Summary

**Current State**: Only **2 of 31 services** (6%) have test coverage, creating a **critical risk** for the planned remediation work.

**Problem**: Cannot safely fix bugs, refactor code, or improve patterns without tests to ensure nothing breaks.

**Solution**: Three-phase test implementation strategy aligned with dead code cleanup and bug remediation.

---

## Current Test Inventory

### What EXISTS (60 test files):
- **Unit tests**: 28 files
  - Citations: 3 files ✅
  - Config: 8 files ✅
  - Evaluation: 4 files ✅
  - MCP: 2 files ⚠️
  - Monitoring: 4 files ✅
  - Performance: 1 file
  - Properties: 2 files ✅ (Hypothesis)
  - Repositories: 2 files ⚠️
  - Services: 2 files ❌❌❌

- **Integration tests**: 5 files
  - Citation workflow ✅
  - Database transactions
  - MCP CLI commands
  - MCP monitoring pipeline
  - MCP server lifecycle

- **E2E tests**: 3 files
  - Complete MCP workflow
  - Citation resolution workflow
  - Evaluation pipeline

- **Benchmarks**: 1 file
  - Resolution performance

### What's MISSING (Critical Gaps):

#### 1. **Service Layer** (29 of 31 services untested):
- ❌ ServiceManager (orchestrator!)
- ❌ LLMService (11 imports)
- ❌ ProcessingService (3 imports)
- ❌ CitationService (1 import)
- ❌ RAGService (1 import)
- ❌ LettaService (1 import)
- ❌ ArticleService (2 imports)
- ❌ NoteService (2 imports)
- ❌ QueryService (1 import)
- ❌ TagService (1 import)
- ❌ WebSearchService (1 import)
- ❌ PdfLocatorService (4 imports)
- ❌ ResearchQuestionService (3 imports)
- ❌ DiscoveryService (3 imports)
- ❌ DiscoveryOrchestrator (2 imports)
- ❌ All other services...

#### 2. **Router Layer** (11 routers, ~0 tests):
- ❌ tools.py
- ❌ operations.py
- ❌ research_questions.py
- ❌ browser_workflows.py
- ❌ agent.py, chat.py, config.py, health.py
- ❌ All API endpoints

#### 3. **Pipeline Layer** (3 pipelines, minimal tests):
- ⚠️ OptimizedDocumentPipeline (current)
- ⚠️ DocumentPipeline (legacy)
- ⚠️ KnowledgePipeline (RAG)

#### 4. **MCP Tools** (54 tools in 16 files, ~0 tests):
- ❌ Discovery tools
- ❌ Article tools
- ❌ Processing tools
- ❌ Citation tools
- ❌ RAG tools
- ❌ Settings tools
- ❌ All other tools

---

## Test Quality Assessment

### ✅ **Good Tests** (Keep & Expand):
1. **test_cache_service.py** (413 lines)
   - Comprehensive: 19 test methods
   - Tests: LRU eviction, TTL expiration, multi-layer caching
   - Uses proper fixtures and mocking
   - **Grade: A+**

2. **test_citation_workflow.py** (Integration, 442 lines)
   - Tests: End-to-end resolution, cache integration, async correctness
   - Performance testing included
   - **Grade: A**

3. **Config tests** (8 files)
   - Covers: vault detection, hot-reload, path resolution, callbacks
   - **Grade: A-**

4. **Citation unit tests** (3 files)
   - Resolution chain, matching, API clients
   - **Grade: B+**

5. **Hypothesis property tests** (2 files)
   - Property-based testing for citations and matching
   - **Grade: A** (advanced technique)

### ⚠️ **Needs Improvement**:
1. **MCP tests** (2 files)
   - Only health endpoints and monitoring
   - Missing: All 54 MCP tools
   - **Grade: D**

2. **Repository tests** (2 files)
   - Only citation and paper repositories
   - Missing: 15 other repositories
   - **Grade: D**

---

## THREE-PHASE TEST STRATEGY

### **PHASE 0: Dead Code Cleanup** (Week 1)
**Priority**: HIGHEST  
**Goal**: Remove 50+ unused files before writing tests

**Actions**:
1. Delete 4 unused services (discovery_scheduler, etc.)
2. Move 14 migration scripts to scripts/
3. Delete unified_registry.py
4. Remove coordination module (if verified unused)
5. Mark deprecated code for removal

**Why First**: Don't waste time testing code about to be deleted

**Outcome**: 
- 187 files instead of 237 (-21%)
- ~20 active services instead of 31 (-35%)
- Clearer architecture

---

### **PHASE 1: Critical Service Tests** (Weeks 2-4)
**Priority**: HIGH (Blocks remediation)  
**Goal**: Test the 20 remaining core services

**Focus Areas** (Priority order):

#### 1.1 ServiceManager Tests (Week 2, Day 1-2)
**File**: `tests/unit/services/test_service_manager.py`  
**Critical**: This is the orchestrator—everything depends on it

**Test Cases**:
- [ ] Initialization order is correct
- [ ] All services created with proper dependencies
- [ ] Optional services (RAG, Processing, Letta) handle missing extras
- [ ] Dynamic attribute access (`__getattr__`) works
- [ ] `set_citation_tracker()` method works
- [ ] Lazy initialization works
- [ ] Double initialization is prevented
- [ ] Service lookup by name works
- [ ] Service lookup for non-existent service raises AttributeError

**Estimated**: 200 lines, ~10 test methods

#### 1.2 LLMService Tests (Week 2, Day 3-4)
**File**: `tests/unit/services/test_llm_service.py`  
**Why**: 11 imports—most used service

**Test Cases**:
- [ ] Client creation for each provider (OpenRouter, Mistral, OpenAI, Anthropic)
- [ ] Model fallback logic
- [ ] Rate limiting
- [ ] API key validation
- [ ] Structured output generation
- [ ] Error handling for API failures
- [ ] Caching responses

**Estimated**: 300 lines, ~15 test methods

#### 1.3 ProcessingService Tests (Week 2, Day 5)
**File**: `tests/unit/services/test_processing_service.py`  
**Why**: Core PDF processing

**Test Cases**:
- [ ] PDF text extraction
- [ ] Metadata extraction
- [ ] OCR fallback
- [ ] Error handling for malformed PDFs
- [ ] Optional service check

**Estimated**: 150 lines, ~8 test methods

#### 1.4 CitationService Tests (Week 3, Day 1-2)
**File**: `tests/unit/services/test_citation_service.py`

**Test Cases**:
- [ ] Citation extraction from text
- [ ] Citation enrichment
- [ ] Resolution chain integration
- [ ] Batch processing
- [ ] Error recovery

**Estimated**: 250 lines, ~12 test methods

#### 1.5 RAGService Tests (Week 3, Day 3)
**File**: `tests/unit/services/test_rag_service.py`

**Test Cases**:
- [ ] Vector index creation
- [ ] Semantic search
- [ ] Document indexing
- [ ] Optional service check (embeddings extras)

**Estimated**: 150 lines, ~8 test methods

#### 1.6 Discovery Tests (Week 3, Day 4-5)
**Files**: 
- `tests/unit/services/test_discovery_service.py`
- `tests/unit/services/test_discovery_orchestrator.py`

**Test Cases**:
- [ ] Source configuration
- [ ] Paper discovery from ArXiv
- [ ] Paper discovery from Semantic Scholar
- [ ] Deduplication
- [ ] Orchestration workflow

**Estimated**: 300 lines total, ~15 test methods

#### 1.7 Other Core Services (Week 4)
**Priority order**:
1. ArticleService
2. NoteService  
3. QueryService
4. TagService
5. PostgresService (enhance existing)
6. ResearchQuestionService
7. PdfLocatorService
8. WebSearchService

**Estimated**: 100-150 lines each, ~8 test methods each

---

### **PHASE 2: Router & Integration Tests** (Weeks 5-6)
**Priority**: MEDIUM (After service tests)  
**Goal**: Ensure API endpoints work correctly

#### 2.1 Router Integration Tests (Week 5)
**Files**: `tests/integration/routers/`

**Critical Routers**:
1. **test_tools_router.py**
   - Test all tool execution endpoints
   - Test error handling
   - Test optional service guards
   
2. **test_operations_router.py**
   - Test PDF processing operations
   - Test batch operations
   - Test discovery operations

3. **test_research_questions_router.py**
   - Test CRUD operations
   - Test discovery integration
   - Test matching workflow

**Estimated**: 200-300 lines per router, ~15 test methods each

#### 2.2 End-to-End Workflows (Week 6)
**Files**: `tests/e2e/`

**Workflows to Test**:
1. **Complete PDF Processing**
   - Upload PDF → Process → Extract Citations → Generate Note
   
2. **Discovery Workflow**
   - Create research question → Run discovery → Match articles
   
3. **RAG Workflow**
   - Index documents → Semantic search → Retrieve context

**Estimated**: 300 lines per workflow, ~10 test scenarios each

---

### **PHASE 3: MCP Tools & Edge Cases** (Weeks 7-8)
**Priority**: LOW (After core functionality)  
**Goal**: Complete test coverage

#### 3.1 MCP Tool Tests (Week 7)
**Strategy**: Test critical tools first, batch the rest

**Critical Tools** (Priority):
1. Discovery tools (most complex)
2. Processing tools (core functionality)
3. Citation tools (complex logic)
4. Settings tools (error handling issues found)

**Standard Pattern** for Each Tool:
```python
async def test_{tool_name}_success():
    """Test successful tool execution."""
    
async def test_{tool_name}_with_invalid_params():
    """Test parameter validation."""
    
async def test_{tool_name}_error_handling():
    """Test error is properly handled."""
```

**Estimated**: 50-100 lines per tool, ~3 test methods each

#### 3.2 Property-Based Tests (Week 8)
**Expand Hypothesis Testing**:
- Add properties for service operations
- Add properties for API responses
- Add properties for data validation

---

## Test Infrastructure Needs

### 1. **Fixtures** (`tests/fixtures/`)
**Create**:
- `service_fixtures.py` - Mock ServiceManager and all services
- `llm_fixtures.py` - Mock LLM responses
- `pdf_fixtures.py` - Sample PDF files
- `api_fixtures.py` - Mock API responses (Crossref, OpenAlex, etc.)
- `database_fixtures.py` - Test database setup

### 2. **Mocking Utilities** (`tests/utils/`)
**Create**:
- `mock_builders.py` - Helper functions to create mocks
- `assertions.py` - Custom assertion helpers
- `async_helpers.py` - Async test utilities

### 3. **Test Database**
**Setup**:
- PostgreSQL test instance
- Migration scripts for test schema
- Cleanup after each test

### 4. **Coverage Configuration**
**Update** `.coveragerc`:
```ini
[run]
source = src/thoth
omit = 
    */tests/*
    */migration/*
    */__init__.py

[report]
precision = 2
show_missing = True
skip_covered = False

[html]
directory = htmlcov
```

---

## Coverage Goals

### Phase 1 Target (After Service Tests):
- **Service Layer**: 80%+ coverage
- **Overall**: 40%+ coverage

### Phase 2 Target (After Router Tests):
- **Service Layer**: 85%+ coverage
- **Router Layer**: 70%+ coverage
- **Overall**: 55%+ coverage

### Phase 3 Target (After MCP Tests):
- **Service Layer**: 90%+ coverage
- **Router Layer**: 80%+ coverage
- **MCP Tools**: 70%+ coverage
- **Overall**: 70%+ coverage

---

## Testing Best Practices

### 1. **Use Proper Mocking**
```python
# GOOD: Mock external dependencies
@patch('thoth.services.llm_service.OpenRouterClient')
async def test_llm_call(mock_client):
    mock_client.return_value.invoke.return_value = "response"
    
# BAD: Don't mock the thing you're testing
@patch('thoth.services.llm_service.LLMService')
async def test_llm_service(mock_service):
    # This tests nothing!
```

### 2. **Test Real Behavior, Not Implementation**
```python
# GOOD: Test observable behavior
def test_cache_respects_ttl():
    cache.set('key', 'value', ttl=1)
    time.sleep(1.1)
    assert cache.get('key') is None  # Expired
    
# BAD: Test internal implementation
def test_cache_internal_dict():
    assert 'key' in cache._internal_cache  # Fragile!
```

### 3. **Use Fixtures for Reusable Setup**
```python
@pytest.fixture
def service_manager():
    """Create a fully initialized ServiceManager."""
    manager = ServiceManager()
    manager.initialize()
    yield manager
    # Cleanup
    manager.shutdown()
```

### 4. **Test Error Cases**
```python
# Always test the happy path AND error cases
async def test_process_pdf_success():
    result = await service.process_pdf('valid.pdf')
    assert result is not None
    
async def test_process_pdf_not_found():
    with pytest.raises(FileNotFoundError):
        await service.process_pdf('missing.pdf')
        
async def test_process_pdf_malformed():
    result = await service.process_pdf('malformed.pdf')
    # Should handle gracefully, not crash
    assert result.error is not None
```

### 5. **Keep Tests Fast**
- Mock I/O operations (file, network, database)
- Use in-memory databases for tests
- Parallelize test execution with `pytest-xdist`
- Skip slow integration tests by default, run in CI

### 6. **Make Tests Deterministic**
- Don't rely on system time (use `freezegun`)
- Don't rely on randomness (seed generators)
- Don't rely on external services (mock them)
- Clean up after each test (fixtures with teardown)

---

## CI/CD Integration

### GitHub Actions Workflow

**`.github/workflows/test.yml`**:
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
          
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --all-extras
          
      - name: Run unit tests
        run: pytest tests/unit -v --cov=src/thoth
        
      - name: Run integration tests
        run: pytest tests/integration -v
        
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

**`.pre-commit-config.yaml`**:
```yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest tests/unit -x
        language: system
        pass_filenames: false
        always_run: true
```

---

## Effort Estimation

| Phase | Focus | Duration | Team Size |
|-------|-------|----------|-----------|
| Phase 0 | Dead code cleanup | 1 week | 1 person |
| Phase 1 | Service tests | 3 weeks | 1-2 people |
| Phase 2 | Router/integration tests | 2 weeks | 1-2 people |
| Phase 3 | MCP tools & edge cases | 2 weeks | 1 person |
| **TOTAL** | **Complete test suite** | **8 weeks** | **1-2 people** |

**Parallel with Remediation**:
- Weeks 1-4: Write tests + Delete dead code + Fix critical bugs
- Weeks 5-8: Write integration tests + Fix important issues
- Weeks 9-12: Polish + Fix good practice issues

**Total Time to Production Excellence**: 12 weeks (3 months)

---

## Success Criteria

### Definition of Done (per Phase):

**Phase 1**:
- ✅ All 20 core services have unit tests
- ✅ Service test coverage ≥ 80%
- ✅ All tests pass in CI
- ✅ Test run time < 5 minutes

**Phase 2**:
- ✅ All critical routers have integration tests
- ✅ Router test coverage ≥ 70%
- ✅ E2E workflows have test coverage
- ✅ All tests pass in CI

**Phase 3**:
- ✅ Critical MCP tools have tests
- ✅ Overall coverage ≥ 70%
- ✅ Property tests expanded
- ✅ All tests pass in CI
- ✅ Test suite runs in < 10 minutes

---

## Maintenance Strategy

### Ongoing (After Initial Implementation):

1. **New Code Must Have Tests**:
   - Minimum 80% coverage for new services
   - All new MCP tools must have 3 test methods
   - All new routers must have integration tests

2. **Test-Driven Development**:
   - Write failing test first
   - Implement feature
   - Verify test passes
   - Refactor

3. **Regular Coverage Review**:
   - Weekly: Check coverage hasn't dropped
   - Monthly: Review and improve lowest-coverage areas
   - Quarterly: Property test audit

4. **Performance Monitoring**:
   - Keep test suite under 10 minutes
   - Parallelize slow tests
   - Profile and optimize slow tests

---

## Conclusion

**Current State**: 6% service test coverage (2 of 31)  
**Blocks**: All remediation work (can't safely refactor)  
**Solution**: 8-week test implementation plan  
**Outcome**: 70%+ coverage, safe remediation, production-ready code

**Next Steps**:
1. Review and approve this strategy
2. Begin Phase 0 (dead code cleanup)
3. Start Phase 1 (service tests) Week 2
4. Run parallel with remediation Weeks 5-12

---

*Test Strategy: January 4, 2026*  
*Target Completion: March 2026*  
*Enables: Bug fixes, pattern improvements, production deployment*

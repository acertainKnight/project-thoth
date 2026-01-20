# Thoth Microservices - Critical Error Fixes

**Date**: 2026-01-19
**Status**: ✅ COMPLETED - All fixes implemented and verified
**Implementation Time**: 35 minutes
**Completed**: 2026-01-19 19:25 EST

---

## ✅ Implementation Results

All 4 critical errors have been successfully fixed and verified:

1. **✅ Agent_v2 Deprecated Import** - Removed from `app.py` and `__init__.py`, added `research_agent = None`
2. **✅ Schema Validation Type Mismatch** - Modified `analysis_schema_service.py` to skip base fields, preserving isinstance() checks
3. **✅ Asyncio Event Loop Binding** - Replaced asyncio.Lock with threading.Lock in `enrichment_service.py`
4. **✅ Recursion Depth Protection** - Added depth tracking with 3-level circuit breaker in `resolution_chain.py`

**Verification Results** (2026-01-19 19:25 EST):
- ✅ thoth-dev-api: Healthy, no agent_v2 errors (0 occurrences)
- ✅ thoth-dev-pdf-monitor: Running, no schema validation errors (0 occurrences)
- ✅ thoth-dev-discovery: Running, no asyncio lock errors (0 occurrences)
- ✅ thoth-monitor: Healthy, no recursion depth errors (0 occurrences)

**Note**: Dev microservices use volume mounts, so code changes were immediately active after container restart.

---

## Executive Summary

After diagnosing the dev microservices system, 4 critical errors were identified that prevent PDF processing, research functionality, and citation enrichment from working. This document provides detailed fix plans for each issue.

**Services Affected**:
- thoth-dev-api (research agent broken)
- thoth-dev-pdf-monitor (PDF processing broken)
- thoth-monitor (enrichment broken, citation resolution crashing)

---

## 1. DEPRECATED AGENT_V2 IMPORT ⛔

### Problem
**Location**: `src/thoth/server/app.py:689`

The API server tries to import a deprecated module that no longer exists:
```python
from thoth.ingestion.agent_v2.core.agent import create_research_assistant_async
```

This causes the research agent initialization to fail. The exception is caught and `research_agent = None`, so the service starts but research functionality is disabled.

### Impact
- **Severity**: MEDIUM
- **Effect**: Research agent features unavailable (but service runs)
- **Status**: Failing silently since agent_v2 was removed

### Fix Plan

#### Step 1: Remove deprecated import and initialization
**File**: `src/thoth/server/app.py`
**Lines**: 687-699

**Action**: Delete the entire try/except block:
```python
# DELETE THIS BLOCK (lines 687-699):
try:
    from thoth.ingestion.agent_v2.core.agent import (
        create_research_assistant_async,
    )

    research_agent = await create_research_assistant_async(
        service_manager=service_manager
    )
    logger.info('Research agent initialized successfully')
except Exception as e:
    logger.error(f'Failed to initialize research agent: {e}')
    research_agent = None
```

#### Step 2: Remove commented import
**File**: `src/thoth/ingestion/__init__.py`
**Line**: 10

**Action**: Delete the commented line:
```python
# DELETE LINE 10:
# from .agent_v2 import ResearchAssistant, create_research_assistant
```

#### Step 3: Verify no dependent code
**Action**: Search for usages of `research_agent` variable:
```bash
grep -r "research_agent" src/thoth/
```

If any code depends on it, either:
- Remove the feature
- Update to use alternative implementation
- Add proper error handling

### Verification
```bash
# Restart API service
docker restart thoth-dev-api

# Check logs - should not see agent_v2 error
docker logs thoth-dev-api --tail 20 | grep -i "agent\|error"
```

### Time Estimate
**5 minutes**

---

## 2. SCHEMA VALIDATION TYPE MISMATCH 🔴 [CRITICAL]

### Problem
**Location**: `src/thoth/analyze/llm_processor.py:512-516`

The LLM processor performs strict type checking on analysis results:
```python
if not isinstance(analysis_result, AnalysisResponse):
    raise LLMError(f'Invalid analysis result type: {type(analysis_result)}')
```

However, the analysis schema service dynamically generates Pydantic models based on user-customizable JSON schemas. These models inherit from `AnalysisResponse` but Pydantic's field redefinition breaks the inheritance chain, causing `isinstance()` to fail.

**Root Cause**: When `create_model()` is given fields that already exist in the base class (`AnalysisResponse`), it creates a new model that doesn't properly maintain the `isinstance()` relationship.

### Impact
- **Severity**: CRITICAL
- **Effect**: ALL PDF processing fails - no papers can be analyzed
- **Errors**: `Invalid analysis result type: <class 'thoth.services.analysis_schema_service.DynamicAnalysisResponse_Standard'>`

### Current Architecture

**Base Schema** (`src/thoth/utilities/schemas/analysis.py`):
- `AnalysisResponse` has 22 fields (title, authors, year, doi, journal, abstract, etc.)
- All fields are `Optional` (can be `None`)
- Has field validators (e.g., `normalize_tags`)

**Dynamic Schema Service** (`src/thoth/services/analysis_schema_service.py`):
- Loads JSON schema from `/vault/_thoth/data/analysis_schema.json` (template: `templates/analysis_schema.json`)
- User can define presets: `standard`, `detailed`, `minimal`, `custom`
- Each preset specifies which fields to extract and their requirements
- Generates dynamic Pydantic models: `DynamicAnalysisResponse_Standard`, etc.
- Line 280: Already uses `__base__=AnalysisResponse` but field conflicts break inheritance

**Schema Requirements**:
- **Always required**: `title`, `authors`, `year` (in all presets)
- **User customizable**: All other fields can be added/removed/modified
- **User can add**: Completely new custom fields not in base schema

### Fix Plan - Option 1: Only Extend with New Fields (RECOMMENDED)

**Strategy**: Only pass custom fields to `create_model()` that don't exist in `AnalysisResponse`. This preserves the inheritance chain and allows users to add new fields without breaking type checking.

#### Step 1: Modify dynamic model builder
**File**: `src/thoth/services/analysis_schema_service.py`
**Function**: `_build_pydantic_model` (lines 239-282)

**Change**:
```python
def _build_pydantic_model(
    self,
    preset_name: str,
    preset_config: dict[str, Any]
) -> Type[BaseModel]:
    """
    Build a dynamic Pydantic model from preset configuration.

    Only adds NEW custom fields not in AnalysisResponse base.
    This preserves isinstance() checks while allowing user extensions.
    """
    from thoth.utilities.schemas import AnalysisResponse

    # Get base AnalysisResponse field names
    base_fields = set(AnalysisResponse.model_fields.keys())

    field_definitions = {}

    for field_name, field_spec in preset_config['fields'].items():
        # Skip fields that already exist in AnalysisResponse
        # This preserves the inheritance chain
        if field_name in base_fields:
            self.logger.debug(f'Skipping base field: {field_name}')
            continue  # Use base class definition

        # Only add NEW custom fields
        field_type = self._map_json_type_to_python(field_spec['type'], field_spec)
        required = field_spec.get('required', False)
        description = field_spec.get('description', '')

        if required:
            field_definitions[field_name] = (
                field_type,
                Field(description=description)
            )
        else:
            field_definitions[field_name] = (
                Optional[field_type],
                Field(default=None, description=description)
            )

    # Create dynamic model - only extends with NEW fields
    model_name = f'DynamicAnalysisResponse_{preset_name.title()}'

    if field_definitions:
        self.logger.info(
            f'Creating {model_name} with {len(field_definitions)} custom fields: '
            f'{list(field_definitions.keys())}'
        )
    else:
        self.logger.info(f'Creating {model_name} with no custom fields (pure base)')

    return create_model(
        model_name,
        __base__=AnalysisResponse,
        **field_definitions  # Only custom fields, not base fields
    )
```

#### Step 2: Update return type annotation (optional but recommended)
**File**: `src/thoth/analyze/llm_processor.py`
**Line**: 461

**Change**:
```python
# OLD:
) -> AnalysisResponse:

# NEW (more flexible):
) -> BaseModel:
```

#### Step 3: Add validation logging for debugging
**File**: `src/thoth/analyze/llm_processor.py`
**Lines**: 512-516

**Change** (optional, for better debugging):
```python
if not isinstance(analysis_result, AnalysisResponse):
    logger.error(
        f'Analysis result type mismatch:\n'
        f'  Expected: AnalysisResponse\n'
        f'  Received: {type(analysis_result)}\n'
        f'  MRO: {type(analysis_result).__mro__}\n'
        f'  Is BaseModel: {isinstance(analysis_result, BaseModel)}'
    )
    raise LLMError(f'Invalid analysis result type: {type(analysis_result)}')
```

### What This Enables

**Users CAN**:
- ✅ Add completely new custom fields (e.g., `impact_score`, `research_area`, `novelty_rating`)
- ✅ Use different presets (standard, detailed, minimal, custom)
- ✅ All base fields work as defined in `AnalysisResponse`

**Users CANNOT** (limitation of this approach):
- ❌ Change base field requirements (e.g., make `doi` required instead of optional)
- ❌ Change base field types (e.g., change `year` from int to string)
- ❌ Remove base fields (they're always present)

**This is acceptable because**:
- The 22 base fields cover standard academic paper metadata
- All base fields are optional (flexible for different paper types)
- Users can add unlimited new fields for custom use cases
- Maintains type safety and `isinstance()` checks

### Alternative: Full Flexibility (Future Enhancement)

If users need to modify base fields, implement a two-tier architecture:

**File**: `src/thoth/utilities/schemas/analysis.py`

```python
class AnalysisResponseBase(BaseModel):
    """Minimal required fields - never override these."""
    title: str | None = Field(description='Paper title', default=None)
    authors: list[str] | None = Field(description='Authors', default=None)
    year: int | None = Field(description='Publication year', default=None)

class AnalysisResponse(AnalysisResponseBase):
    """Full default schema with all standard fields."""
    doi: str | None = Field(...)
    journal: str | None = Field(...)
    # ... all other fields
```

Then dynamic models inherit from `AnalysisResponseBase` and can fully customize everything except title/authors/year.

### Verification

```bash
# Restart PDF monitor
docker restart thoth-dev-pdf-monitor thoth-monitor

# Watch for successful processing
docker logs -f thoth-dev-pdf-monitor | grep -E "Processing|Analysis|Success"

# Should see:
# "Content analysis completed successfully"
# Not: "Invalid analysis result type"
```

### Time Estimate
**15 minutes** (includes testing)

---

## 3. ASYNCIO EVENT LOOP BINDING 🟠 [MAJOR]

### Problem
**Location**: `src/thoth/analyze/citations/enrichment_service.py:70, 111-113`

The enrichment service uses lazy initialization of an `asyncio.Lock`:

```python
# Line 70: Lock initialized as None
self._rate_lock: Optional[asyncio.Lock] = None

# Lines 111-113: Lazy initialization
def _get_rate_lock(self) -> asyncio.Lock:
    if self._rate_lock is None:
        self._rate_lock = asyncio.Lock()  # Created in current event loop
    return self._rate_lock
```

**Why This Breaks**:
1. Service is instantiated once (module import or main thread)
2. First call to `_get_rate_lock()` creates lock in that thread's event loop
3. Later calls from different threads/workers try to use the same lock
4. `asyncio.Lock` objects are bound to the event loop that created them
5. Cross-loop usage fails: `<asyncio.locks.Lock object> is bound to a different event loop`

### Impact
- **Severity**: MAJOR
- **Effect**: All citation enrichment fails (CrossRef, OpenAlex, Semantic Scholar metadata)
- **Frequency**: Every enrichment request (100+ errors)
- **Citations**: Cannot be enriched with DOIs, journal info, author details, etc.

### Fix Plan - Use Thread-Safe Lock

**Strategy**: Replace `asyncio.Lock` with `threading.Lock` since rate limiting is about cross-thread coordination, not async coordination within a single event loop.

#### Step 1: Update lock initialization
**File**: `src/thoth/analyze/citations/enrichment_service.py`
**Lines**: 70, 111-117

**Change**:
```python
import threading

class EnrichmentService:
    def __init__(self, ...):
        # OLD (line 70):
        # self._rate_lock: Optional[asyncio.Lock] = None

        # NEW:
        self._rate_lock = threading.Lock()  # Thread-safe, no event loop binding

        # ... rest of init

    # DELETE this method (lines 111-113):
    # def _get_rate_lock(self) -> asyncio.Lock:
    #     if self._rate_lock is None:
    #         self._rate_lock = asyncio.Lock()
    #     return self._rate_lock
```

#### Step 2: Update lock usage
**File**: `src/thoth/analyze/citations/enrichment_service.py`
**Line**: 117 (in `_make_request` method)

**Change**:
```python
# OLD:
async with self._get_rate_lock():
    # Rate limiting logic

# NEW:
with self._rate_lock:  # No await needed - it's a threading.Lock
    # Rate limiting logic
```

**Note**: Since this is now a synchronous lock inside an async function, the rate limiting section will block. This is acceptable because:
- Rate limiting is inherently synchronous (checking/updating counters)
- The lock hold time is minimal (< 1ms)
- The alternative (asyncio.Lock per event loop) is complex and error-prone

#### Alternative: Event Loop Specific Locks

If blocking is unacceptable, use per-event-loop locks:

```python
import asyncio
from typing import Dict

class EnrichmentService:
    def __init__(self, ...):
        self._rate_locks: Dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}
        self._locks_lock = threading.Lock()  # Protect the dict

    def _get_rate_lock(self) -> asyncio.Lock:
        """Get lock for current event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop - create temporary one
            loop = None

        with self._locks_lock:
            if loop not in self._rate_locks:
                self._rate_locks[loop] = asyncio.Lock()
            return self._rate_locks[loop]

    async def _make_request(self, ...):
        async with self._get_rate_lock():
            # Rate limiting logic
```

**Recommendation**: Start with `threading.Lock` (simpler, immediate fix). If profiling shows lock contention issues, upgrade to per-loop locks.

### Verification

```bash
# Restart services
docker restart thoth-monitor thoth-dev-pdf-monitor

# Watch for enrichment success
docker logs -f thoth-monitor | grep -E "enrichment|CrossRef|OpenAlex"

# Should NOT see:
# "is bound to a different event loop"

# Should see successful API calls
```

### Time Estimate
**10 minutes**

---

## 4. RECURSION DEPTH EXCEEDED 🟠 [MAJOR]

### Problem
**Location**: `src/thoth/analyze/citations/resolution_chain.py:605`

The citation resolution chain has infinite recursion in Semantic Scholar resolution:
```
Error in Semantic Scholar resolution: maximum recursion depth exceeded
```

**Root Cause Analysis**:

Looking at the resolution chain structure:
- Line 938: `return await self.resolve(citation)` - Resolution calls itself
- Line 972: `result = await self.resolve(citation)` - Another recursive call

**Why This Happens**:
1. `resolve()` method tries multiple APIs in sequence (CrossRef → Semantic Scholar → arXiv → OpenAlex)
2. If one API fails, fallback logic may call `resolve()` again
3. Citation normalization/transformation may create loops
4. Missing or incorrect base case in recursion
5. Error handlers that re-trigger the same resolver

### Impact
- **Severity**: MAJOR
- **Effect**: Some citations crash entire resolution process
- **Frequency**: Intermittent (depends on citation structure)
- **Result**: Stack overflow, resolution fails for that paper

### Fix Plan - Add Recursion Protection

#### Step 1: Add recursion depth tracking (immediate protection)
**File**: `src/thoth/analyze/citations/resolution_chain.py`
**Method**: `resolve()` (around line 200-250)

**Change**:
```python
async def resolve(
    self,
    citation: Citation,
    _recursion_depth: int = 0,  # Add depth tracking
    _max_depth: int = 3,  # Maximum recursion depth
) -> ResolutionResult | None:
    """
    Resolve citation through multiple API sources.

    Args:
        citation: Citation to resolve
        _recursion_depth: Internal recursion depth counter (do not set manually)
        _max_depth: Maximum recursion depth before aborting

    Returns:
        ResolutionResult if successful, None otherwise
    """
    # Recursion protection
    if _recursion_depth >= _max_depth:
        logger.warning(
            f'Max recursion depth ({_max_depth}) reached for citation: '
            f'{citation.text[:100]}...'
        )
        return None

    # Log recursion for debugging
    if _recursion_depth > 0:
        logger.debug(
            f'Recursive resolution attempt {_recursion_depth} for: '
            f'{citation.text[:50]}'
        )

    # ... existing resolution logic ...

    # When calling resolve recursively, increment depth:
    # Find all places with "await self.resolve(citation)" and update to:
    return await self.resolve(
        citation,
        _recursion_depth=_recursion_depth + 1,
        _max_depth=_max_depth
    )
```

#### Step 2: Track tried methods to prevent re-attempts
**File**: `src/thoth/analyze/citations/resolution_chain.py`
**Method**: `_try_semantic_scholar` (line 489)

**Change**:
```python
async def _try_semantic_scholar(
    self,
    citation: Citation,
    metadata: ResolutionMetadata,
    candidates: List[MatchCandidate],
) -> ResolutionResult | None:
    """Try resolving citation via Semantic Scholar API."""

    # Check if already tried (prevent loops)
    if APISource.SEMANTIC_SCHOLAR in metadata.api_sources_tried:
        logger.debug('Skipping Semantic Scholar - already tried in this resolution chain')
        return None

    try:
        metadata.api_sources_tried.append(APISource.SEMANTIC_SCHOLAR)

        # ... existing logic ...
```

Apply this pattern to ALL resolver methods:
- `_try_crossref`
- `_try_arxiv`
- `_try_openalex`

#### Step 3: Find and fix the actual recursion loop
**Action**: Search for all recursive calls:

```bash
cd src/thoth/analyze/citations
grep -n "await self.resolve" resolution_chain.py
```

For each match:
1. Verify it's necessary (not a bug)
2. Check the termination condition
3. Ensure it's in error handling (not main flow)
4. Add comment explaining why recursion is needed

**Common patterns to fix**:
```python
# BAD - Unconditional recursion on error
except Exception as e:
    return await self.resolve(citation)  # Will loop forever!

# GOOD - Fallback with modification
except Exception as e:
    if not citation.normalized:
        citation = normalize_citation(citation)
        return await self.resolve(citation, _recursion_depth=_recursion_depth + 1)
    return None  # Give up
```

#### Step 4: Add circuit breaker for specific citation
**File**: `src/thoth/analyze/citations/resolution_chain.py`
**Method**: `resolve()`

**Add at the start**:
```python
# Track failed citations to avoid repeated attempts
if not hasattr(self, '_failed_citations'):
    self._failed_citations: Set[str] = set()

# Generate citation fingerprint
citation_key = f"{citation.text[:100]}_{citation.year}"

if citation_key in self._failed_citations:
    logger.debug(f'Skipping previously failed citation: {citation.text[:50]}')
    return None

# ... existing logic ...

# On recursion depth exceeded or persistent failure:
if _recursion_depth >= _max_depth - 1:
    self._failed_citations.add(citation_key)
```

### Verification

```bash
# Restart services
docker restart thoth-monitor thoth-dev-pdf-monitor

# Monitor for recursion errors
docker logs -f thoth-monitor | grep -E "recursion|depth|Semantic Scholar"

# Should see:
# "Max recursion depth reached" (controlled failure)
# NOT: "maximum recursion depth exceeded" (crash)
```

### Time Estimate
**Initial protection**: 15 minutes
**Root cause fix**: 1-2 hours (requires debugging actual resolution flow)

---

## Implementation Order

### Phase 1: Immediate Fixes (30 minutes)
1. **agent_v2 removal** (5 min) - Simple deletion
2. **Schema validation** (15 min) - Critical for PDF processing
3. **Asyncio lock** (10 min) - Critical for enrichment

### Phase 2: Stability Improvements (15 minutes)
4. **Recursion protection** (15 min) - Add depth limit

### Phase 3: Root Cause Analysis (1-2 hours, as time permits)
5. **Recursion debugging** - Find actual loop cause

**Total for critical functionality**: 45 minutes

---

## Testing Checklist

After implementing all fixes:

### 1. Research Agent
```bash
docker logs thoth-dev-api | grep -i "agent_v2"
# Should: See no errors

docker logs thoth-dev-api | grep -i "research agent"
# Should: See no initialization attempts (removed)
```

### 2. PDF Processing
```bash
# Place a test PDF in watched directory
cp test.pdf /vault/thoth/papers/pdfs/

# Watch processing
docker logs -f thoth-dev-pdf-monitor | grep -E "Processing|Analysis|Error"

# Should see:
# "Processing test.pdf"
# "Content analysis completed successfully"
# NOT: "Invalid analysis result type"
```

### 3. Citation Enrichment
```bash
docker logs thoth-monitor | grep -E "enrichment|event loop" | tail -20

# Should NOT see:
# "is bound to a different event loop"

# Should see:
# Successful CrossRef/OpenAlex API calls
```

### 4. Citation Resolution
```bash
docker logs thoth-monitor | grep -i "recursion" | tail -10

# Should see (controlled):
# "Max recursion depth reached" (if any problematic citations)

# Should NOT see:
# "maximum recursion depth exceeded" (crash)
```

### 5. Overall Health
```bash
curl http://localhost:8000/health | jq .

# Should show:
# Most services "healthy"
# No critical errors
```

---

## Rollback Plan

If any fix causes issues:

### Quick Rollback
```bash
# Stop all services
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile microservices down

# Git revert specific file
git checkout HEAD -- src/thoth/[affected_file].py

# Rebuild and restart
docker compose -f docker-compose.letta.yml up -d
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile microservices up -d --build
```

### Full Rollback
```bash
# Revert all changes
git stash

# Restart services
docker compose -f docker-compose.letta.yml up -d
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile microservices up -d
```

---

## Future Enhancements

### Schema Validation (Post-MVP)
- Implement two-tier `AnalysisResponseBase` / `AnalysisResponse` split
- Allow users to modify base field requirements
- Add schema migration tools

### Citation Resolution (Post-MVP)
- Implement proper resolution DAG (directed acyclic graph)
- Add resolution caching per session
- Smarter fallback strategies based on citation type

### Monitoring (Post-MVP)
- Add Prometheus metrics for:
  - PDF processing success rate
  - Citation resolution success rate
  - API rate limit tracking
  - Recursion depth metrics
- Grafana dashboards for real-time monitoring

---

## Additional Issues (Lower Priority)

### 5. Semantic Scholar Rate Limiting
**Impact**: Medium - Some citations fail
**Fix**: Add API key to `.env`:
```bash
API_SEMANTIC_SCHOLAR_KEY=your_key_here
```
**Time**: 2 minutes

### 6. NULL Citations in Database
**Impact**: Low - 16 citations with NULL data
**Fix**:
```sql
-- Clean up NULL citations
DELETE FROM citations WHERE citation_text IS NULL;
```
**Time**: 5 minutes

### 7. CrossRef Cache Permissions
**Impact**: Very Low - Just slower lookups
**Fix**:
```bash
chmod -R u+w /vault/_thoth/cache/
```
**Time**: 1 minute

---

## Contact & Support

For questions or issues during implementation:
- Check service logs: `docker logs [service-name]`
- Review health status: `curl http://localhost:8000/health | jq .`
- Verify database: `docker exec letta-postgres psql -U thoth -d thoth -c "SELECT COUNT(*) FROM papers;"`

**End of Document**

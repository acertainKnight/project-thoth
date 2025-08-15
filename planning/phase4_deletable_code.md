# Code That Can Be Deleted After Phase 4

## Summary

With Phase 4 complete, we have created modular structures for large files but **cannot delete the original files yet** due to existing imports throughout the codebase.

## Current Status

### 1. api_sources.py
- **Original**: 1,261 lines of implementation
- **Current**: 41 lines (compatibility wrapper)
- **Savings**: 1,220 lines (~97% reduction)
- **Status**: Cannot delete - still imported by 4 files
- **Blockers**:
  - `analyze/citations/async_enhancer.py`
  - `analyze/citations/enhancer.py`
  - `discovery/discovery_manager.py`
  - `services/discovery_service.py`

### 2. api_server.py
- **Original**: 2,385 lines
- **Current**: Still 2,385 lines (unchanged)
- **New Structure**: Created modular `app.py` and 8 router files
- **Status**: Cannot delete - still imported by 2 files
- **Blockers**:
  - `cli/system.py`
  - `cli/server.py`

## Migration Strategy

### Option 1: Update Imports (Recommended)
Update all files that import from the old modules to use the new paths:

```python
# Old
from thoth.discovery.api_sources import ArxivClient
# New
from thoth.discovery.sources import ArxivClient

# Old
from thoth.server.api_server import start_obsidian_server
# New
from thoth.server.app import app  # or create start_obsidian_server function
```

### Option 2: Create Compatibility Wrappers
We've already done this for `api_sources.py` - reduced it to a 41-line wrapper that imports from the new modules and issues deprecation warnings.

## Immediate Actions Available

1. **api_sources.py is already reduced** - We've replaced 1,220 lines with a 41-line wrapper
2. **api_server.py could be wrapped similarly** - Replace 2,385 lines with a small wrapper

## Code Reduction Achieved

- **api_sources.py**: 1,220 lines removed (97% reduction)
- **Total Phase 4 savings**: 1,220 lines

## Next Steps

To fully delete these files:

1. Update the 4 files importing from `api_sources.py`
2. Update the 2 files importing from `api_server.py`
3. Then delete both compatibility wrappers

This would remove an additional ~2,400 lines of code.
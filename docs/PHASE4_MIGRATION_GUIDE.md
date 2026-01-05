# Phase 4 Migration Guide: ThothPipeline Deprecation

**Status**: Complete (Phase 4a + 4b) ✅  
**Timeline**: Deprecation warnings active now, removal in 2-3 releases  
**Impact**: Medium - affects initialization code, but 100% backward compatible

---

## Overview

Phase 4 removes the `ThothPipeline` wrapper layer to simplify the architecture from 5 layers to 2-3 layers. All functionality remains the same, but initialization is cleaner and more explicit.

**Benefits**:
- ✅ Simpler, more explicit code
- ✅ Fewer layers of abstraction
- ✅ Easier to understand and maintain
- ✅ No functional changes - everything works the same

---

## What Changed

### Before (Old Pattern - Deprecated)

```python
from thoth.pipeline import ThothPipeline

# Old way - creates wrapper with all components
pipeline = ThothPipeline()

# Access components through wrapper
pipeline.process_pdf('paper.pdf')
pipeline.services.llm.generate(...)
pipeline.document_pipeline.process_pdf(...)
```

### After (New Pattern - Recommended)

```python
from thoth.initialization import initialize_thoth

# New way - explicit component access
services, document_pipeline, citation_graph = initialize_thoth()

# Use components directly
document_pipeline.process_pdf('paper.pdf')
services.llm.generate(...)
citation_graph.get_all_papers()
```

---

## Migration Steps

### 1. Update Imports

**Before**:
```python
from thoth.pipeline import ThothPipeline
```

**After**:
```python
from thoth.initialization import initialize_thoth
```

### 2. Update Initialization

**Before**:
```python
pipeline = ThothPipeline()
```

**After**:
```python
services, document_pipeline, citation_graph = initialize_thoth()
```

### 3. Update Method Calls

**Before**:
```python
pipeline.process_pdf('paper.pdf')
```

**After**:
```python
document_pipeline.process_pdf('paper.pdf')
```

**Before**:
```python
pipeline.services.llm.generate(...)
```

**After**:
```python
services.llm.generate(...)
```

### 4. Update PDFMonitor Usage

**Before**:
```python
from thoth.pipeline import ThothPipeline
from thoth.server.pdf_monitor import PDFMonitor

pipeline = ThothPipeline()
monitor = PDFMonitor(watch_dir=path, pipeline=pipeline)
```

**After**:
```python
from thoth.initialization import initialize_thoth
from thoth.server.pdf_monitor import PDFMonitor

_, document_pipeline, _ = initialize_thoth()
monitor = PDFMonitor(watch_dir=path, document_pipeline=document_pipeline)
```

---

## Common Patterns

### Pattern 1: Simple PDF Processing

**Before**:
```python
from thoth.pipeline import ThothPipeline

pipeline = ThothPipeline()
result = pipeline.process_pdf('paper.pdf')
```

**After**:
```python
from thoth.initialization import initialize_thoth

_, document_pipeline, _ = initialize_thoth()
result = document_pipeline.process_pdf('paper.pdf')
```

### Pattern 2: Using Services

**Before**:
```python
from thoth.pipeline import ThothPipeline

pipeline = ThothPipeline()
articles = pipeline.services.article.list_articles()
tags = pipeline.services.tag.generate_tags(text)
```

**After**:
```python
from thoth.initialization import initialize_thoth

services, _, _ = initialize_thoth()
articles = services.article.list_articles()
tags = services.tag.generate_tags(text)
```

### Pattern 3: PDF Monitoring

**Before**:
```python
from thoth.pipeline import ThothPipeline
from thoth.server.pdf_monitor import PDFMonitor

pipeline = ThothPipeline()
monitor = PDFMonitor(pipeline=pipeline)  # Deprecated parameter
monitor.start()
```

**After**:
```python
from thoth.initialization import initialize_thoth
from thoth.server.pdf_monitor import PDFMonitor

_, document_pipeline, _ = initialize_thoth()
monitor = PDFMonitor(document_pipeline=document_pipeline)  # New parameter
monitor.start()
```

### Pattern 4: Citation Graph Operations

**Before**:
```python
from thoth.pipeline import ThothPipeline

pipeline = ThothPipeline()
papers = pipeline.citation_tracker.get_all_papers()
```

**After**:
```python
from thoth.initialization import initialize_thoth

_, _, citation_graph = initialize_thoth()
papers = citation_graph.get_all_papers()
```

---

## Backward Compatibility

**All old code continues to work** with deprecation warnings:

```python
# This still works! Just shows a warning.
from thoth.pipeline import ThothPipeline

pipeline = ThothPipeline()  # DeprecationWarning shown
result = pipeline.process_pdf('paper.pdf')  # Works correctly
```

You can suppress warnings temporarily:

```python
import warnings
from thoth.pipeline import ThothPipeline

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    pipeline = ThothPipeline()
```

---

## Deprecation Timeline

| Release | Status | Action |
|---------|--------|--------|
| **Current** | Deprecation warnings active | Both patterns work |
| **+1 release** | Continue warnings | Update your code |
| **+2 releases** | Continue warnings | Final reminder |
| **+3 releases** | ThothPipeline removed | Must use new pattern |

---

## Why This Change?

### Before (5 Layers)
```
User Code
  → ThothPipeline (wrapper)
    → OptimizedDocumentPipeline
      → ServiceManager
        → Services
          → Actual work
```

### After (2-3 Layers)
```
User Code
  → OptimizedDocumentPipeline
    → Services
      → Actual work
```

**Benefits**:
- Simpler architecture (-312 lines of wrapper code)
- More explicit - no hidden indirection
- Easier to test and maintain
- Clearer separation of concerns

---

## Testing Your Migration

Run your code and check for deprecation warnings:

```bash
python -Wd your_script.py  # Show all deprecation warnings
```

If you see:
```
DeprecationWarning: ThothPipeline is deprecated...
```

Then you need to migrate that code using this guide.

---

## Need Help?

- Check examples in `tests/integration/test_initialization_workflow.py`
- See `src/thoth/cli/system.py` for CLI migration example
- Open an issue if you encounter problems

---

## Quick Reference

| Old | New |
|-----|-----|
| `ThothPipeline()` | `initialize_thoth()` |
| `pipeline.process_pdf()` | `document_pipeline.process_pdf()` |
| `pipeline.services` | `services` |
| `pipeline.document_pipeline` | `document_pipeline` |
| `pipeline.citation_tracker` | `citation_graph` |
| `PDFMonitor(pipeline=...)` | `PDFMonitor(document_pipeline=...)` |

---

**Last Updated**: January 5, 2026  
**Phase**: 4 (ThothPipeline Deprecation)  
**Status**: Complete ✅

# API Sources Migration Guide

## Overview

The `api_sources.py` file has been refactored from a single 1,261-line file into a modular structure with one file per API source for better maintainability.

## New Structure

```
discovery/
├── api_sources.py          # Legacy file (to be deprecated)
└── sources/                # New modular structure
    ├── __init__.py
    ├── base.py            # Base classes (APISourceError, BaseAPISource)
    ├── arxiv.py           # ArXiv source (ArxivClient, ArxivAPISource)
    ├── pubmed.py          # PubMed source (PubMedAPISource)
    ├── crossref.py        # CrossRef source (CrossRefAPISource)
    ├── openalex.py        # OpenAlex source (OpenAlexAPISource)
    └── biorxiv.py         # BioRxiv source (BioRxivAPISource)
```

## Migration Steps

### 1. Update Imports

#### Old imports:
```python
from thoth.discovery.api_sources import (
    ArxivAPISource,
    PubMedAPISource,
    CrossRefAPISource,
    OpenAlexAPISource,
    BioRxivAPISource,
    APISourceError,
    ArxivClient
)
```

#### New imports (Option A - from package):
```python
from thoth.discovery.sources import (
    ArxivAPISource,
    PubMedAPISource,
    CrossRefAPISource,
    OpenAlexAPISource,
    BioRxivAPISource,
    APISourceError,
    ArxivClient
)
```

#### New imports (Option B - from individual modules):
```python
from thoth.discovery.sources.base import APISourceError, BaseAPISource
from thoth.discovery.sources.arxiv import ArxivAPISource, ArxivClient
from thoth.discovery.sources.pubmed import PubMedAPISource
from thoth.discovery.sources.crossref import CrossRefAPISource
from thoth.discovery.sources.openalex import OpenAlexAPISource
from thoth.discovery.sources.biorxiv import BioRxivAPISource
```

### 2. No API Changes

All classes maintain the same interfaces:
- Same method signatures
- Same configuration options
- Same return types

### 3. Gradual Migration

During the transition period:
1. Both import paths work (old and new)
2. The old `api_sources.py` can import from the new modules
3. No changes needed to existing code using these sources

### 4. Benefits

1. **Better Organization**: Each source in its own file (~200 lines each vs 1261 lines)
2. **Easier Maintenance**: Find and modify source-specific code quickly
3. **Better Testing**: Test each source independently
4. **Clearer Dependencies**: Each source declares its own imports

## Example Usage

No changes needed in usage:

```python
# Creating sources - same as before
arxiv = ArxivAPISource(rate_limit_delay=3.0)
pubmed = PubMedAPISource(rate_limit_delay=0.34)

# Using sources - same as before
config = {
    'keywords': ['machine learning'],
    'categories': ['cs.LG']
}
results = arxiv.search(config, max_results=10)
```

## Timeline

1. **Phase 1** (Current): Both structures coexist
2. **Phase 2** (3 months): Mark `api_sources.py` as deprecated
3. **Phase 3** (6 months): Remove `api_sources.py`

## Adding New Sources

To add a new API source:

1. Create a new file in `sources/` (e.g., `sources/semantic_scholar.py`)
2. Inherit from `BaseAPISource`
3. Implement the `search()` method
4. Add import to `sources/__init__.py`

Example:
```python
# sources/semantic_scholar.py
from .base import BaseAPISource, APISourceError

class SemanticScholarAPISource(BaseAPISource):
    def search(self, config, max_results=50):
        # Implementation here
        pass
```
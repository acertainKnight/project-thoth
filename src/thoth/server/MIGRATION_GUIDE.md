# API Server Migration Guide

## Overview

The Thoth API server has been refactored from a single 2,385-line file (`api_server.py`) into a modular router-based architecture for better maintainability and organization.

## Migration Steps

### 1. New Application Structure

The API server is now organized as follows:

```
server/
├── app.py                    # New main application (modular)
├── api_server.py            # Legacy monolithic file (to be deprecated)
├── routers/                 # Organized endpoints
│   ├── __init__.py
│   ├── agent.py            # Agent management endpoints
│   ├── chat.py             # Chat sessions and messages
│   ├── config.py           # Configuration management
│   ├── health.py           # Health checks and utilities
│   ├── operations.py       # Long-running operations
│   ├── research.py         # Research and query endpoints
│   ├── tools.py            # Tool execution endpoints
│   └── websocket.py        # WebSocket connections
└── chat_models.py          # Shared chat models

```

### 2. Using the New Modular App

#### Option A: Gradual Migration (Recommended)

1. Start using the new modular app alongside the existing one:
   ```python
   # For new features, import from app.py
   from thoth.server.app import app
   ```

2. Test thoroughly before switching production traffic.

3. Update your server startup scripts:
   ```python
   # Old way
   uvicorn thoth.server.api_server:app
   
   # New way
   uvicorn thoth.server.app:app
   ```

#### Option B: Direct Replacement

1. Replace all imports:
   ```python
   # Old
   from thoth.server.api_server import app
   
   # New
   from thoth.server.app import app
   ```

2. Update any direct endpoint references to use the router structure.

### 3. Endpoint Changes

All endpoints remain the same, but are now organized by router:

- `/health`, `/download-pdf`, `/view-markdown` → `health.py`
- `/ws/*` → `websocket.py`
- `/chat/*` → `chat.py`
- `/agent/*` → `agent.py`
- `/research/*` → `research.py`
- `/config/*` → `config.py`
- `/operations/*`, `/stream/*`, `/batch/*` → `operations.py`
- `/tools/*`, `/execute/*` → `tools.py`

### 4. Dependency Injection

The new app uses FastAPI's dependency injection more extensively:

```python
# Old way (global variables)
if research_agent is None:
    raise HTTPException(...)

# New way (dependency injection)
@router.get('/status')
def get_status(research_agent=Depends(get_research_agent)):
    ...
```

### 5. Shared State

Application state is now managed through `app.state`:

```python
# Access shared resources
app.state.service_manager
app.state.chat_manager
app.state.research_agent
```

### 6. WebSocket Managers

WebSocket connection managers are now in `websocket.py`:

```python
from thoth.server.routers.websocket import (
    chat_ws_manager,
    status_ws_manager,
    progress_ws_manager
)
```

### 7. Testing

Update your tests to import from the appropriate routers:

```python
# Old
from thoth.server.api_server import app
client = TestClient(app)

# New
from thoth.server.app import app
client = TestClient(app)
```

### 8. Custom Middleware

Add any custom middleware to `app.py` instead of `api_server.py`:

```python
# In app.py
app.add_middleware(YourMiddleware)
```

## Benefits

1. **Better Organization**: Endpoints grouped by functionality
2. **Easier Testing**: Test individual routers in isolation
3. **Improved Maintainability**: Smaller, focused files
4. **Better Type Safety**: Clearer request/response models
5. **Scalability**: Easy to add new routers/endpoints

## Deprecation Timeline

1. **Phase 1** (Current): Both `api_server.py` and `app.py` coexist
2. **Phase 2** (3 months): `api_server.py` marked as deprecated
3. **Phase 3** (6 months): `api_server.py` removed from codebase

## Need Help?

- Check individual router files for endpoint documentation
- Review `app.py` for application setup
- See request/response models in each router file
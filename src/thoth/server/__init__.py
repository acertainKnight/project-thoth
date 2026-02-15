"""Server components for Thoth, including API server and file monitor."""

# Lazy imports to avoid pulling the entire FastAPI app (and all its router
# dependencies like python-multipart) into non-server contexts like the MCP
# server or pipeline CLI commands.
from .pdf_monitor import PDFMonitor

__all__ = ['PDFMonitor', 'app', 'create_app', 'start_obsidian_server', 'start_server']


def __getattr__(name: str):
    """Lazy-load the FastAPI app objects on first access."""
    if name in ('app', 'create_app', 'start_obsidian_server', 'start_server'):
        from .app import app, create_app, start_obsidian_server, start_server

        globals().update(
            {
                'app': app,
                'create_app': create_app,
                'start_obsidian_server': start_obsidian_server,
                'start_server': start_server,
            }
        )
        return globals()[name]
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')

"""Server components for Thoth, including API server and file monitor."""

# Import from the new modular structure
from .app import app, create_app, start_obsidian_server, start_server
from .pdf_monitor import PDFMonitor

# Backward compatibility - keep legacy imports working
try:
    # For any legacy code that imports from api_server directly
    from .api_server import start_obsidian_server as legacy_start_obsidian_server
except ImportError:
    # If api_server.py is removed, use the new implementation
    legacy_start_obsidian_server = start_obsidian_server

__all__ = ['PDFMonitor', 'app', 'create_app', 'start_obsidian_server', 'start_server']

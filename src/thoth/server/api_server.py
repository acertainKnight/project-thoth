"""
Legacy API server module - Compatibility wrapper.

This module now imports from the new modular structure in app.py and routers/.
It will be removed in a future release.

DEPRECATED: Use imports from thoth.server.app instead.
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "Importing from thoth.server.api_server is deprecated. "
    "Please import from thoth.server.app instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import the main app and compatibility functions
from thoth.server.app import app, start_server, start_obsidian_server

# Export for backward compatibility
__all__ = ['app', 'start_server', 'start_obsidian_server']

"""
Thoth - Academic PDF processing system.

This package provides tools for processing academic PDF documents.
"""

__version__ = '0.3.0-alpha.1'

# Lazy imports to avoid loading heavy dependencies at module import time
# Import only when actually used to support running without all optional dependencies

def __getattr__(name):
    """Lazy import of heavy components."""
    if name == 'ThothPipeline':
        from thoth.pipeline import ThothPipeline
        return ThothPipeline
    elif name == 'DocumentPipeline':
        from thoth.pipelines import DocumentPipeline
        return DocumentPipeline
    elif name == 'PDFMonitor':
        from thoth.server.pdf_monitor import PDFMonitor
        return PDFMonitor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ['DocumentPipeline', 'PDFMonitor', 'ThothPipeline']

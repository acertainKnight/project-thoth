"""
Thoth - Academic PDF processing system.

This package provides tools for processing academic PDF documents.
"""

__version__ = '0.1.0'
__all__ = ['PDFMonitor', 'ThothPipeline']


# Using lazy imports to break circular dependencies
def __getattr__(name):
    if name == 'PDFMonitor':
        from thoth.monitor.pdf_monitor import PDFMonitor

        return PDFMonitor
    elif name == 'ThothPipeline':
        from thoth.pipeline import ThothPipeline

        return ThothPipeline
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

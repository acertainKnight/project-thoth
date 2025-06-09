"""
Thoth - Academic PDF processing system.

This package provides tools for processing academic PDF documents.
"""

__version__ = '0.1.0'

# Import key components for easier access
from thoth.pipeline import ThothPipeline
from thoth.server.pdf_monitor import PDFMonitor

__all__ = ['PDFMonitor', 'ThothPipeline']

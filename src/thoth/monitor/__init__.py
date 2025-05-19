"""
Monitor module for Thoth.

This module provides monitoring functionality for Thoth.
"""

from thoth.monitor.obsidian import app as obsidian_app
from thoth.monitor.obsidian import start_server as obsidian_server
from thoth.monitor.pdf_monitor import PDFMonitor

__all__ = ['PDFMonitor', 'obsidian_app', 'obsidian_server']

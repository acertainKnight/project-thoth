"""
Thoth ingestion package.

This package contains components for ingesting and processing research articles,
including the research assistant agent and filtering capabilities.
"""

from .agent_v2 import ResearchAssistant, create_research_assistant
from .pdf_downloader import download_pdf

__all__ = [
    'ResearchAssistant',
    'create_research_assistant',
    'download_pdf',
]

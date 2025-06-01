"""
Thoth ingestion package.

This package provides functionality for ingesting various types of content into Thoth.
"""

# New modular agent
from thoth.ingestion.agent_v2 import ResearchAssistant, create_research_assistant

# Filter for discovery
from thoth.ingestion.filter import Filter
from thoth.ingestion.pdf_downloader import download_pdf

__all__ = [
    'Filter',
    'ResearchAssistant',
    'create_research_assistant',
    'download_pdf',
]

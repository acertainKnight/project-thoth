"""
Thoth ingestion package.

This package contains components for ingesting and processing research articles,
including the research assistant agent and filtering capabilities.
"""

# NOTE: agent_v2 module has been migrated to Letta native agents
# Legacy imports commented out to prevent import errors
# from .agent_v2 import ResearchAssistant, create_research_assistant
from .pdf_downloader import download_pdf

__all__ = [
    # 'ResearchAssistant',  # Migrated to Letta
    # 'create_research_assistant',  # Migrated to Letta
    'download_pdf',
]

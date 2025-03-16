"""
Linking module for Thoth.

This module handles the management of citation links between notes.
"""

from thoth.linking.manager import LinkManager
from thoth.linking.updater import (
    extract_citations_from_section,
    find_citation_sections,
    update_note_citations,
)

__all__ = [
    "LinkManager",
    "extract_citations_from_section",
    "find_citation_sections",
    "update_note_citations",
]

"""
Citation module for Thoth.

This module handles the extraction and processing of citations from papers.
"""

from thoth.citation.citation import Citation
from thoth.citation.extractor import (
    CitationExtractionError,
    CitationExtractor,
    extract_citations,
)

__all__ = [
    "Citation",
    "CitationExtractionError",
    "CitationExtractor",
    "extract_citations",
]

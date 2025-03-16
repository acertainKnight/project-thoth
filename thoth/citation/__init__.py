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
from thoth.citation.formatter import (
    CitationFormatError,
    CitationFormatter,
    CitationStyle,
    format_citation,
)

__all__ = [
    "Citation",
    "CitationExtractionError",
    "CitationExtractor",
    "CitationFormatError",
    "CitationFormatter",
    "CitationStyle",
    "extract_citations",
    "format_citation",
]

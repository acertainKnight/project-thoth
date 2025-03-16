"""
Citation module for Thoth.

This module handles the extraction and processing of citations from papers.
"""

from thoth.citation.citation import Citation
from thoth.citation.downloader import (
    CitationDownloader,
    CitationDownloadError,
    download_citation,
)
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
    "CitationDownloadError",
    "CitationDownloader",
    "CitationExtractionError",
    "CitationExtractor",
    "CitationFormatError",
    "CitationFormatter",
    "CitationStyle",
    "download_citation",
    "extract_citations",
    "format_citation",
]

"""
Discovery API sources - backwards compatibility module.

This module provides backwards compatibility by importing and re-exporting
all the API sources from their new modular locations in the sources/ package.
"""

# Import all sources from the new modular structure
from .sources import (
    APISourceError,
    ArxivAPISource,
    ArxivClient,
    BaseAPISource,
    BioRxivAPISource,
    CrossRefAPISource,
    OpenAlexAPISource,
    PubMedAPISource,
)

# Re-export all sources for backwards compatibility
__all__ = [
    'APISourceError',
    'ArxivAPISource',
    'ArxivClient',
    'BaseAPISource',
    'BioRxivAPISource',
    'CrossRefAPISource',
    'OpenAlexAPISource',
    'PubMedAPISource',
]

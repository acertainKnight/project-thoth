"""
API sources for article discovery.

This module provides API source classes for discovering articles from
various research databases.
"""

from .arxiv import ArxivClient
from .base import APISourceError, BaseAPISource
from .biorxiv import BioRxivAPISource
from .crossref import CrossRefAPISource
from .openalex import OpenAlexAPISource
from .pubmed import PubMedAPISource

__all__ = [
    'APISourceError',
    'BaseAPISource',
    'ArxivClient',
    'PubMedAPISource',
    'CrossRefAPISource',
    'OpenAlexAPISource',
    'BioRxivAPISource',
]
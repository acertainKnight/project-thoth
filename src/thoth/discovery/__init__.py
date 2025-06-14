"""
Thoth discovery package.

This package contains components for discovering research articles from
various sources like ArXiv, PubMed, and web scrapers.
"""

from .api_sources import ArxivAPISource, PubMedAPISource
from .discovery_manager import DiscoveryManager
from .emulator_scraper import EmulatorScraper
from .scheduler import DiscoveryScheduler
from .web_scraper import WebScraper

__all__ = [
    'ArxivAPISource',
    'DiscoveryManager',
    'DiscoveryScheduler',
    'EmulatorScraper',
    'PubMedAPISource',
    'WebScraper',
]

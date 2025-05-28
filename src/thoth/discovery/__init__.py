"""
Thoth discovery package.

This package provides functionality for discovering new research articles through
various sources including APIs and web scraping.
"""

from thoth.discovery.api_sources import ArxivAPISource, PubMedAPISource
from thoth.discovery.chrome_extension import ChromeExtensionServer
from thoth.discovery.discovery_manager import DiscoveryManager
from thoth.discovery.scheduler import DiscoveryScheduler
from thoth.discovery.web_scraper import WebScraper

__all__ = [
    'ArxivAPISource',
    'ChromeExtensionServer',
    'DiscoveryManager',
    'DiscoveryScheduler',
    'PubMedAPISource',
    'WebScraper',
]

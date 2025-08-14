"""
Thoth discovery package.

This package contains components for discovering research articles from
various sources like ArXiv, PubMed, and web scrapers, with intelligent
context-aware auto-discovery based on conversation analysis.
"""

from .api_sources import ArxivAPISource, PubMedAPISource
from .auto_discovery_hook import AutoDiscoveryHook, AutoDiscoveryManager
from .context_analyzer import (
    ChatContextAnalyzer,
    DiscoverySourceSuggestion,
    ResearchTopic,
)
from .discovery_manager import DiscoveryManager
from .emulator_scraper import EmulatorScraper
from .plugins import ArxivPlugin, plugin_registry
from .scheduler import DiscoveryScheduler
from .web_scraper import WebScraper

__all__ = [
    'ArxivAPISource',
    'ArxivPlugin',
    'AutoDiscoveryHook',
    'AutoDiscoveryManager',
    'ChatContextAnalyzer',
    'DiscoveryManager',
    'DiscoveryScheduler',
    'DiscoverySourceSuggestion',
    'EmulatorScraper',
    'PubMedAPISource',
    'ResearchTopic',
    'WebScraper',
    'plugin_registry',
]

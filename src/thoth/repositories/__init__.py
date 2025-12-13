"""
Repository pattern for database access.

This module provides a clean separation between business logic and data access,
with support for caching, feature flags, and backward compatibility.
"""

from thoth.repositories.base import BaseRepository
from thoth.repositories.paper_repository import PaperRepository
from thoth.repositories.citation_repository import CitationRepository
from thoth.repositories.tag_repository import TagRepository
from thoth.repositories.cache_repository import CacheRepository
from thoth.repositories.discovery_source_repository import DiscoverySourceRepository
from thoth.repositories.paper_discovery_repository import PaperDiscoveryRepository

__all__ = [
    'BaseRepository',
    'PaperRepository',
    'CitationRepository',
    'TagRepository',
    'CacheRepository',
    'DiscoverySourceRepository',
    'PaperDiscoveryRepository',
]

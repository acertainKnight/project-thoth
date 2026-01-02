"""
Repository pattern for database access.

This module provides a clean separation between business logic and data access,
with support for caching, feature flags, and backward compatibility.
"""

from thoth.repositories.base import BaseRepository  # noqa: I001
from thoth.repositories.paper_repository import PaperRepository
from thoth.repositories.citation_repository import CitationRepository
from thoth.repositories.tag_repository import TagRepository
from thoth.repositories.cache_repository import CacheRepository
from thoth.repositories.discovery_source_repository import DiscoverySourceRepository
from thoth.repositories.paper_discovery_repository import PaperDiscoveryRepository
from thoth.repositories.workflow_actions_repository import WorkflowActionsRepository
from thoth.repositories.workflow_search_config_repository import (
    WorkflowSearchConfigRepository,
)
from thoth.repositories.workflow_executions_repository import (
    WorkflowExecutionsRepository,
)

__all__ = [  # noqa: RUF022
    'BaseRepository',
    'PaperRepository',
    'CitationRepository',
    'TagRepository',
    'CacheRepository',
    'DiscoverySourceRepository',
    'PaperDiscoveryRepository',
    'WorkflowActionsRepository',
    'WorkflowSearchConfigRepository',
    'WorkflowExecutionsRepository',
]

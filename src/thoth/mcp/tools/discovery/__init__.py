"""Discovery tools module."""

from .arxiv_source import CreateArxivSourceMCPTool
from .list_sources import ListDiscoverySourcesMCPTool
from .management import (
    DeleteDiscoverySourceMCPTool,
    GetDiscoverySourceMCPTool,
    RunDiscoveryMCPTool,
)
from .other_sources import (
    CreateBiorxivSourceMCPTool,
    CreateCrossrefSourceMCPTool,
    CreateOpenalexSourceMCPTool,
)
from .pubmed_source import CreatePubmedSourceMCPTool

__all__ = [
    'ListDiscoverySourcesMCPTool',
    'CreateArxivSourceMCPTool',
    'CreatePubmedSourceMCPTool',
    'CreateCrossrefSourceMCPTool',
    'CreateOpenalexSourceMCPTool',
    'CreateBiorxivSourceMCPTool',
    'GetDiscoverySourceMCPTool',
    'RunDiscoveryMCPTool',
    'DeleteDiscoverySourceMCPTool',
]
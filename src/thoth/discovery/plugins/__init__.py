from .base import BaseDiscoveryPlugin, DiscoveryPluginRegistry
from .arxiv_plugin import ArxivPlugin

plugin_registry = DiscoveryPluginRegistry()
plugin_registry.register('arxiv', ArxivPlugin)

__all__ = [
    'ArxivPlugin',
    'BaseDiscoveryPlugin',
    'DiscoveryPluginRegistry',
    'plugin_registry',
]

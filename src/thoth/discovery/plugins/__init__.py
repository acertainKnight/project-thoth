from .arxiv_plugin import ArxivPlugin
from .base import BaseDiscoveryPlugin, DiscoveryPluginRegistry

plugin_registry = DiscoveryPluginRegistry()
plugin_registry.register('arxiv', ArxivPlugin)

__all__ = [
    'ArxivPlugin',
    'BaseDiscoveryPlugin',
    'DiscoveryPluginRegistry',
    'plugin_registry',
]

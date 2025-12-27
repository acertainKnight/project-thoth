from .arxiv_plugin import ArxivPlugin
from .base import BaseDiscoveryPlugin, DiscoveryPluginRegistry
from .browser_workflow_plugin import BrowserWorkflowPlugin

plugin_registry = DiscoveryPluginRegistry()
plugin_registry.register('arxiv', ArxivPlugin)
plugin_registry.register('browser_workflow', BrowserWorkflowPlugin)

__all__ = [
    'ArxivPlugin',
    'BaseDiscoveryPlugin',
    'BrowserWorkflowPlugin',
    'DiscoveryPluginRegistry',
    'plugin_registry',
]

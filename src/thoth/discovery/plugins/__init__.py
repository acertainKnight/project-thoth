from .arxiv_plugin import ArxivPlugin
from .base import BaseDiscoveryPlugin, DiscoveryPluginRegistry

# Browser workflow plugin is optional (requires playwright)
# NOTE: Import is disabled to prevent deadlock until circular dependency is resolved
BROWSER_WORKFLOW_AVAILABLE = False
BrowserWorkflowPlugin = None

# try:
#     from .browser_workflow_plugin import BrowserWorkflowPlugin
#     BROWSER_WORKFLOW_AVAILABLE = True
# except ImportError:
#     BROWSER_WORKFLOW_AVAILABLE = False
#     BrowserWorkflowPlugin = None

plugin_registry = DiscoveryPluginRegistry()
plugin_registry.register('arxiv', ArxivPlugin)

# Only register browser workflow plugin if available
# if BROWSER_WORKFLOW_AVAILABLE:
#     plugin_registry.register('browser_workflow', BrowserWorkflowPlugin)

__all__ = [
    'ArxivPlugin',
    'BaseDiscoveryPlugin',
    'BrowserWorkflowPlugin',
    'DiscoveryPluginRegistry',
    'plugin_registry',
    'BROWSER_WORKFLOW_AVAILABLE',
]

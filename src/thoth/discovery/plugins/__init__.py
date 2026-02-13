from .arxiv_plugin import ArxivPlugin
from .base import BaseDiscoveryPlugin, DiscoveryPluginRegistry
from .icml_plugin import ICMLPlugin
from .neurips_plugin import NeurIPSPlugin
from .semantic_scholar_plugin import SemanticScholarPlugin

# Browser workflow plugin is optional (requires playwright).
# Imported lazily to avoid circular imports at module init time.
BROWSER_WORKFLOW_AVAILABLE = False
BrowserWorkflowPlugin = None


def get_browser_workflow_plugin_class():
    """Lazy import for BrowserWorkflowPlugin to avoid circular imports."""
    global BROWSER_WORKFLOW_AVAILABLE, BrowserWorkflowPlugin
    if BrowserWorkflowPlugin is not None:
        return BrowserWorkflowPlugin
    try:
        from .browser_workflow_plugin import (
            BrowserWorkflowPlugin as _BrowserWorkflowPlugin,
        )

        BrowserWorkflowPlugin = _BrowserWorkflowPlugin
        BROWSER_WORKFLOW_AVAILABLE = True
        return BrowserWorkflowPlugin
    except ImportError:
        BROWSER_WORKFLOW_AVAILABLE = False
        return None


# Optional plugins with external dependencies
try:
    from .openreview_plugin import OpenReviewPlugin

    OPENREVIEW_AVAILABLE = True
except ImportError:
    OpenReviewPlugin = None
    OPENREVIEW_AVAILABLE = False

try:
    from .acl_anthology_plugin import ACLAnthologyPlugin

    ACL_ANTHOLOGY_AVAILABLE = True
except ImportError:
    ACLAnthologyPlugin = None
    ACL_ANTHOLOGY_AVAILABLE = False

# Register all tested and working plugins
plugin_registry = DiscoveryPluginRegistry()
plugin_registry.register('arxiv', ArxivPlugin)
plugin_registry.register('semantic_scholar', SemanticScholarPlugin)
# plugin_registry.register('paperswithcode', ...)  # Disabled - API needs verification
plugin_registry.register('neurips', NeurIPSPlugin)
plugin_registry.register('icml', ICMLPlugin)
plugin_registry.register('pmlr', ICMLPlugin)  # Alias for any PMLR volume

if OPENREVIEW_AVAILABLE:
    plugin_registry.register('openreview', OpenReviewPlugin)

if ACL_ANTHOLOGY_AVAILABLE:
    plugin_registry.register('acl_anthology', ACLAnthologyPlugin)

# Browser workflow plugin is NOT registered in the generic registry because it needs
# postgres_service for construction. It's handled directly by the DiscoveryOrchestrator
# via get_browser_workflow_plugin_class().

__all__ = [
    'ACL_ANTHOLOGY_AVAILABLE',
    'BROWSER_WORKFLOW_AVAILABLE',
    'OPENREVIEW_AVAILABLE',
    'ACLAnthologyPlugin',
    'ArxivPlugin',
    'BaseDiscoveryPlugin',
    'BrowserWorkflowPlugin',
    'DiscoveryPluginRegistry',
    'ICMLPlugin',
    'NeurIPSPlugin',
    'OpenReviewPlugin',
    'SemanticScholarPlugin',
    'get_browser_workflow_plugin_class',
    'plugin_registry',
]

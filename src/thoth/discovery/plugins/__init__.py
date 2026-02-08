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

# Always available plugins (use httpx which is already a dependency)
from .icml_plugin import ICMLPlugin

# from .paperswithcode_plugin import PapersWithCodePlugin  # Disabled - API endpoint has changed/redirects
from .neurips_plugin import NeurIPSPlugin
from .semantic_scholar_plugin import SemanticScholarPlugin

# Register all tested and working plugins
plugin_registry = DiscoveryPluginRegistry()
plugin_registry.register('arxiv', ArxivPlugin)
plugin_registry.register('semantic_scholar', SemanticScholarPlugin)
# plugin_registry.register('paperswithcode', PapersWithCodePlugin)  # Disabled - API needs verification
plugin_registry.register('neurips', NeurIPSPlugin)
plugin_registry.register('icml', ICMLPlugin)
plugin_registry.register('pmlr', ICMLPlugin)  # Alias for any PMLR volume

if OPENREVIEW_AVAILABLE:
    plugin_registry.register('openreview', OpenReviewPlugin)

if ACL_ANTHOLOGY_AVAILABLE:
    plugin_registry.register('acl_anthology', ACLAnthologyPlugin)

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
    # Tested and working plugins
    'SemanticScholarPlugin',
    # 'PapersWithCodePlugin',  # Disabled - API needs verification
    'NeurIPSPlugin',
    'ICMLPlugin',
    'OpenReviewPlugin',
    'ACLAnthologyPlugin',
    'OPENREVIEW_AVAILABLE',
    'ACL_ANTHOLOGY_AVAILABLE',
]

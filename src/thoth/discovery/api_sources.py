"""
API sources for article discovery - Compatibility wrapper.

This module now imports from the new modular structure in sources/.
It will be removed in a future release.

DEPRECATED: Use imports from thoth.discovery.sources instead.
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "Importing from thoth.discovery.api_sources is deprecated. "
    "Please import from thoth.discovery.sources instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import everything from the new modules for backward compatibility
from thoth.discovery.sources import (
    APISourceError,
    BaseAPISource,
    ArxivAPISource,
    ArxivClient,
    PubMedAPISource,
    CrossRefAPISource,
    OpenAlexAPISource,
    BioRxivAPISource,
)

__all__ = [
    'APISourceError',
    'BaseAPISource',
    'ArxivAPISource',
    'ArxivClient',
    'PubMedAPISource',
    'CrossRefAPISource',
    'OpenAlexAPISource',
    'BioRxivAPISource',
]

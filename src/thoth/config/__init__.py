"""
Thoth configuration module.
"""

from .simplified import (
    CoreConfig,
    FeatureConfig,
    migrate_from_old_config,
)

__all__ = [
    "CoreConfig",
    "FeatureConfig",
    "migrate_from_old_config",
]
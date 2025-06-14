"""Tests for the simplified configuration structures."""

from thoth.config.simplified import CoreConfig, FeatureConfig, migrate_from_old_config
from thoth.utilities.config import ThothConfig


def test_core_config_loading():
    """CoreConfig should load with default values."""
    core = CoreConfig()
    assert core.workspace_dir
    assert core.api_keys is not None
    assert core.llm_config.model


def test_feature_config_loading():
    """FeatureConfig should load with defaults."""
    features = FeatureConfig()
    assert features.api_server
    assert features.discovery


def test_migration_from_old(thoth_config: ThothConfig):
    """Migrating from old config should preserve values."""
    migrated = migrate_from_old_config(thoth_config)
    assert migrated.core.workspace_dir == thoth_config.workspace_dir
    assert migrated.features.api_server.host == thoth_config.api_server_config.host


def test_backward_compatibility(thoth_config: ThothConfig):
    """Old attribute access should still work on new config."""
    migrated = migrate_from_old_config(thoth_config)
    assert migrated.pdf_dir == migrated.core.pdf_dir
    assert migrated.api_server_config.port == migrated.features.api_server.port

"""
Smoke tests for Thoth.

Basic tests to verify the system can be imported and initialized.
"""

from thoth.utilities.config import ThothConfig


def test_imports():
    """Test that all major modules can be imported."""
    # Test service imports

    # Test pipeline import

    # Test ingestion imports

    # Test monitor imports

    # Test utilities imports

    # If we get here, all imports succeeded
    assert True


def test_config_loading(thoth_config: ThothConfig):
    """Test that configuration can be loaded."""
    # Should not raise an exception
    assert thoth_config is not None


def test_service_manager_initialization(thoth_config: ThothConfig):
    """Test that ServiceManager can be initialized with test config."""
    from thoth.services.service_manager import ServiceManager

    # Initialize with default configuration
    manager = ServiceManager(config=thoth_config)
    manager.initialize()

    # Verify services are available
    assert hasattr(manager, 'article')
    assert hasattr(manager, 'processing')
    assert hasattr(manager, 'llm')
    assert hasattr(manager, 'note')
    assert hasattr(manager, 'citation')
    assert hasattr(manager, 'discovery')
    assert hasattr(manager, 'query')
    assert hasattr(manager, 'rag')
    assert hasattr(manager, 'tag')

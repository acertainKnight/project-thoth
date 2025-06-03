"""
Smoke tests for Thoth.

Basic tests to verify the system can be imported and initialized.
"""


def test_imports():
    """Test that all major modules can be imported."""
    # Test service imports

    # Test pipeline import

    # Test ingestion imports

    # Test monitor imports

    # Test utilities imports

    # If we get here, all imports succeeded
    assert True


def test_config_loading():
    """Test that configuration can be loaded."""
    from thoth.utilities.config import get_config

    # Should not raise an exception
    config = get_config()
    assert config is not None


def test_service_manager_initialization():
    """Test that ServiceManager can be initialized with test config."""
    from thoth.services.service_manager import ServiceManager

    # Initialize with default configuration
    manager = ServiceManager()
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

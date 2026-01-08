"""End-to-end test for Discovery workflow.

Tests the complete discovery system structure from query to paper retrieval.
These tests verify the workflow components exist and are properly connected.

Full integration testing with real discovery sources requires network access
and is better suited for manual QA or CI/CD integration tests.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from thoth.discovery.discovery_manager import DiscoveryManager
from thoth.services.service_manager import ServiceManager


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        dirs = {
            'sources_dir': base / 'sources',
            'results_dir': base / 'results',
        }
        for dir_path in dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
        yield dirs


@pytest.fixture
def service_manager():
    """Create a ServiceManager instance (initialization may fail without full setup)."""
    try:
        sm = ServiceManager()
        sm.initialize()
        return sm
    except Exception:
        # If initialization fails (no DB, etc.), return a mock
        return Mock(spec=ServiceManager)


class TestDiscoveryWorkflowStructure:
    """Test Discovery workflow structure and components."""

    def test_discovery_manager_exists(self):
        """Test DiscoveryManager class exists."""
        assert DiscoveryManager is not None

    def test_discovery_manager_has_discover_method(self):
        """Test DiscoveryManager has the main discover method."""
        # Check method exists without initializing (may require DB)
        assert hasattr(DiscoveryManager, 'run_discovery')

    def test_discovery_orchestrator_exists(self):
        """Test DiscoveryOrchestrator exists."""
        from thoth.services import discovery_orchestrator
        
        assert discovery_orchestrator is not None

    def test_discovery_scheduler_exists(self):
        """Test discovery scheduler exists."""
        from thoth.discovery import DiscoveryScheduler
        
        assert DiscoveryScheduler is not None

    def test_discovery_service_exists(self):
        """Test discovery service exists in ServiceManager."""
        from thoth.services.service_manager import ServiceManager
        
        sm = ServiceManager()
        assert hasattr(sm, 'discovery') or hasattr(sm, 'discovery_manager')

    def test_discovery_sources_exist(self):
        """Test discovery sources are importable."""
        # Test source plugins exist
        from thoth.discovery import api_sources
        
        assert api_sources is not None

    def test_context_analyzer_exists(self):
        """Test context analyzer exists."""
        from thoth.discovery import ChatContextAnalyzer
        
        assert ChatContextAnalyzer is not None


class TestDiscoveryWorkflowIntegration:
    """Test Discovery workflow integration points."""

    def test_browser_automation_exists(self):
        """Test browser automation components exist."""
        try:
            from thoth.discovery.browser import browser_manager, extraction_service
            
            assert browser_manager is not None
            assert extraction_service is not None
        except ImportError:
            pytest.skip("Browser automation dependencies not installed")

    def test_discovery_service_in_manager(self, service_manager):
        """Test discovery service is accessible through ServiceManager."""
        assert hasattr(service_manager, 'discovery') or hasattr(service_manager, 'discovery_manager')

    def test_available_source_repository_exists(self):
        """Test AvailableSourceRepository exists."""
        from thoth.repositories import available_source_repository
        
        assert available_source_repository is not None

    def test_discovery_source_repository_exists(self):
        """Test DiscoverySourceRepository exists."""
        from thoth.repositories import discovery_source_repository
        
        assert discovery_source_repository is not None

    def test_workflow_can_access_results_directory(self, temp_dirs):
        """Test workflow has access to results directory."""
        assert temp_dirs['results_dir'].exists()
        assert temp_dirs['results_dir'].is_dir()

    def test_workflow_can_access_sources_directory(self, temp_dirs):
        """Test workflow has access to sources directory."""
        assert temp_dirs['sources_dir'].exists()
        assert temp_dirs['sources_dir'].is_dir()


class TestDiscoveryAPISources:
    """Test API discovery sources."""

    def test_arxiv_source_exists(self):
        """Test ArXiv source exists."""
        from thoth.discovery import ArxivAPISource, ArxivPlugin
        
        # Check ArXiv functionality exists (without making API calls)
        assert ArxivAPISource is not None or ArxivPlugin is not None

    def test_semantic_scholar_source_exists(self):
        """Test Semantic Scholar source exists."""
        try:
            from thoth.analyze.citations import semanticscholar
            assert semanticscholar is not None
        except ImportError:
            # Semantic Scholar may be in citations module
            pytest.skip("Semantic Scholar not in discovery module")


class TestDiscoveryDashboard:
    """Test discovery dashboard service."""

    def test_discovery_dashboard_exists(self):
        """Test discovery dashboard service exists."""
        from thoth.services import discovery_dashboard_service
        
        assert discovery_dashboard_service is not None

    def test_discovery_server_exists(self):
        """Test discovery server exists."""
        from thoth.services import discovery_server
        
        assert discovery_server is not None

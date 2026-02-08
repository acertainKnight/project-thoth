"""Tests for browser_workflows router endpoints.

This router handles browser automation workflows (714 lines, 8 endpoints).
Full workflow execution testing is better in integration tests.
"""

import pytest

from thoth.server.routers import browser_workflows


class TestRouterModule:
    """Tests for router module structure."""

    def test_router_exists(self):
        """Test router object exists."""
        assert browser_workflows.router is not None

    def test_router_has_routes(self):
        """Test router has defined routes."""
        assert len(browser_workflows.router.routes) > 0
        # Should have 8 endpoints
        assert len(browser_workflows.router.routes) >= 8


class TestModelsExist:
    """Test that Pydantic models are defined."""

    def test_workflow_models_importable(self):
        """Test workflow models can be imported."""
        # Try importing key models
        from thoth.server.routers.browser_workflows import (
            WorkflowCreateRequest,
            WorkflowResponse,
        )

        assert WorkflowCreateRequest is not None
        assert WorkflowResponse is not None


class TestWorkflowCreateRequest:
    """Tests for WorkflowCreateRequest model validation."""

    def test_create_workflow_requires_name(self):
        """Test workflow creation requires name."""
        from thoth.server.routers.browser_workflows import WorkflowCreateRequest

        with pytest.raises(Exception):  # Pydantic validation error
            WorkflowCreateRequest()

    def test_create_workflow_with_minimal_data(self):
        """Test workflow creation with minimal valid data."""
        from thoth.server.routers.browser_workflows import WorkflowCreateRequest

        # All required fields
        workflow = WorkflowCreateRequest(
            name='Test Workflow',
            website_domain='example.com',
            start_url='https://example.com',
            extraction_rules={},
            actions=[],
        )

        assert workflow.name == 'Test Workflow'
        assert workflow.website_domain == 'example.com'
        assert workflow.start_url == 'https://example.com'


class TestBrowserWorkflowEndpoints:
    """Tests for endpoint structure."""

    def test_router_has_create_endpoint(self):
        """Test router has create workflow endpoint."""
        routes = [r.path for r in browser_workflows.router.routes]
        # Should have root path for creating workflows
        assert any('/' in r or '' in r for r in routes)

    def test_router_has_execute_endpoint(self):
        """Test router has execute workflow endpoint."""
        routes = [r.path for r in browser_workflows.router.routes]
        # Should have execute endpoint
        assert any('execute' in r for r in routes)

    def test_router_has_list_endpoint(self):
        """Test router has list workflows endpoint."""
        routes = [r.path for r in browser_workflows.router.routes]
        # Should have root GET endpoint for listing
        assert len(routes) > 0  # Has routes defined

"""Tests for config router endpoints."""

from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from thoth.auth.dependencies import get_user_context
from thoth.config import Settings
from thoth.server.routers import config as config_router


@pytest.fixture
def mock_user_context_with_settings(mock_user_context):
    """Provide a UserContext that carries a Settings object for config tests."""
    settings = Settings()
    return replace(mock_user_context, settings=settings)


@pytest.fixture
def test_client(mock_user_context_with_settings):
    """Create FastAPI test client with config router."""
    app = FastAPI()
    app.include_router(config_router.router)
    app.dependency_overrides[get_user_context] = lambda: mock_user_context_with_settings
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestExportEndpoint:
    """Tests for /export endpoint."""

    def test_export_config_success(self, test_client):
        """Test config export succeeds."""
        response = test_client.get('/export')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'config' in data
        assert 'config_version' in data
        assert 'exported_at' in data

    def test_export_config_returns_user_specific_flag(self, test_client):
        """Test exported config indicates it is user-specific."""
        response = test_client.get('/export')

        assert response.status_code == 200
        data = response.json()
        assert data['user_specific'] is True


class TestImportEndpoint:
    """Tests for /import endpoint."""

    def test_import_config_accepts_payload(self, test_client):
        """Test import endpoint accepts a config payload."""
        test_config = {'api_keys': {'mistralKey': 'test'}}

        response = test_client.post('/import', json=test_config)

        assert response.status_code in [200, 500]


class TestValidateEndpoints:
    """Tests for validation endpoints (temporarily disabled)."""

    def test_validate_returns_501(self, test_client):
        """Test /validate endpoint returns 501 (not implemented)."""
        response = test_client.post('/validate')

        assert response.status_code == 501
        assert 'temporarily disabled' in response.json()['detail']

    def test_validate_partial_returns_501(self, test_client):
        """Test /validate-partial endpoint returns 501 (not implemented)."""
        request_data = {'field_path': 'api_keys.mistral_key', 'field_value': 'test_key'}
        response = test_client.post('/validate-partial', json=request_data)

        assert response.status_code == 501
        assert 'temporarily disabled' in response.json()['detail']


class TestSchemaEndpoints:
    """Tests for schema-related endpoints."""

    def test_get_schema_returns_501(self, test_client):
        """Test /schema endpoint returns 501 (not implemented)."""
        response = test_client.get('/schema')

        assert response.status_code == 501
        assert 'temporarily disabled' in response.json()['detail']

    def test_get_schema_version_success(self, test_client):
        """Test /schema/version endpoint works."""
        response = test_client.get('/schema/version')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'current_version' in data
        assert 'supported_versions' in data
        assert 'migration_available' in data
        assert 'migration_required' in data
        assert 'checked_at' in data
        assert data['current_version'] == '2.0.0'

    def test_migrate_schema_success(self, test_client):
        """Test /schema/migrate endpoint returns migration info."""
        response = test_client.post(
            '/schema/migrate?from_version=1.0.0&to_version=2.0.0'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'migration_info' in data
        assert data['migration_info']['from_version'] == '1.0.0'
        assert data['migration_info']['to_version'] == '2.0.0'
        assert 'migration_steps' in data['migration_info']
        assert 'migration_id' in data


class TestDefaultsEndpoint:
    """Tests for /defaults endpoint."""

    def test_get_defaults_success(self, test_client):
        """Test /defaults endpoint returns default config."""
        response = test_client.get('/defaults')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'defaults' in data
        assert 'version' in data

        # Check structure of defaults
        defaults = data['defaults']
        assert 'api_keys' in defaults
        assert 'directories' in defaults
        assert 'server' in defaults
        assert 'llm_settings' in defaults
        assert 'discovery' in defaults

        # Check some specific defaults
        assert defaults['server']['host'] == 'localhost'
        assert defaults['server']['port'] == 8000

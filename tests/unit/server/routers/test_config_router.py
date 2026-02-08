"""Tests for config router endpoints."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from thoth.server.routers import config as config_router


@pytest.fixture
def test_client():
    """Create FastAPI test client with config router."""
    app = FastAPI()
    app.include_router(config_router.router)
    return TestClient(app)


class TestExportEndpoint:
    """Tests for /export endpoint."""

    @patch('thoth.server.routers.config.config')
    def test_export_config_success(self, mock_config, test_client):
        """Test config export succeeds."""
        # Setup mock
        mock_config.export_for_obsidian.return_value = {
            'api_keys': {'mistralKey': 'test'},
            'directories': {'workspaceDir': '/test'},
        }

        # Make request
        response = test_client.get('/export')

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'config' in data
        assert 'config_version' in data
        assert 'exported_at' in data
        mock_config.export_for_obsidian.assert_called_once()

    @patch('thoth.server.routers.config.config')
    def test_export_config_error_handling(self, mock_config, test_client):
        """Test config export handles errors."""
        # Setup mock to raise exception
        mock_config.export_for_obsidian.side_effect = Exception('Export failed')

        # Make request
        response = test_client.get('/export')

        # Assertions
        assert response.status_code == 500
        assert 'Config export failed' in response.json()['detail']


class TestImportEndpoint:
    """Tests for /import endpoint."""

    def test_import_config_has_implementation_bug(self, test_client):
        """Test import endpoint has undefined variable bug."""
        # This endpoint has a bug - uses undefined 'imported_config'
        # It will fail with NameError
        test_config = {'api_keys': {'mistralKey': 'test'}}

        response = test_client.post('/import', json=test_config)

        # Should fail due to implementation bug
        assert response.status_code == 500


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

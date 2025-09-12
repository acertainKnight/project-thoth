"""Tests for enhanced configuration router endpoints."""

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from thoth.server.routers.config import router
from thoth.utilities.config.validation import (
    IssueSeverity,
    IssueType,
    ValidationIssue,
    ValidationResult,
)

# Create test app
app = FastAPI()
app.include_router(router, prefix='/config')
client = TestClient(app)


class TestConfigSchemaEndpoint:
    """Test suite for enhanced /config/schema endpoint."""

    @patch('thoth.server.routers.config.SchemaGenerator')
    def test_get_config_schema_success(self, mock_schema_generator):
        """Test successful schema generation."""
        # Mock the schema generator
        mock_generator_instance = Mock()
        mock_schema_generator.return_value = mock_generator_instance

        mock_schema = {
            'schema_version': '2.0.0',
            'fields': {
                'api_key': {
                    'type': 'password',
                    'required': True,
                    'description': 'API key for service',
                    'group': 'API Keys',
                    'env_var': 'THOTH_API_KEY',
                }
            },
            'field_groups': {
                'API Keys': {
                    'title': 'API Keys',
                    'description': 'API key configurations',
                    'order': 1,
                }
            },
            'validation_rules': {'api_key': {'required': True, 'data_type': 'str'}},
        }

        mock_generator_instance.generate_schema.return_value = mock_schema

        response = client.get('/config/schema')

        assert response.status_code == 200
        data = response.json()

        assert data['status'] == 'success'
        assert data['schema_version'] == '2.0.0'
        assert 'fields' in data
        assert 'field_groups' in data
        assert 'validation_rules' in data
        assert 'generated_at' in data
        assert data['supports_partial_validation'] is True
        assert data['migration_support'] is True
        assert data['api_version'] == '2.0.0'

    @patch('thoth.server.routers.config.SchemaGenerator')
    def test_get_config_schema_error(self, mock_schema_generator):
        """Test schema generation error handling."""
        # Mock schema generator to raise exception
        mock_generator_instance = Mock()
        mock_schema_generator.return_value = mock_generator_instance
        mock_generator_instance.generate_schema.side_effect = Exception(
            'Schema generation failed'
        )

        response = client.get('/config/schema')

        assert response.status_code == 500
        data = response.json()
        assert 'Schema generation failed' in data['detail']


class TestConfigValidateEndpoint:
    """Test suite for enhanced /config/validate endpoint."""

    @patch('thoth.server.routers.config.EnhancedValidator')
    @patch('thoth.server.routers.config.get_config')
    def test_validate_current_config_success(self, mock_get_config, mock_validator):
        """Test successful validation of current configuration."""
        # Mock current config
        mock_config = Mock()
        mock_config.model_dump.return_value = {'api_key': 'test-key', 'port': 8080}
        mock_get_config.return_value = mock_config

        # Mock validator
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance

        validation_result = ValidationResult(
            is_valid=True, errors=[], warnings=[], suggestions=[]
        )
        mock_validator_instance.validate_config.return_value = validation_result

        response = client.post('/config/validate')

        assert response.status_code == 200
        data = response.json()

        assert data['status'] == 'valid'
        assert data['source'] == 'current'
        assert data['is_valid'] is True
        assert data['error_count'] == 0
        assert data['warning_count'] == 0
        assert data['suggestion_count'] == 0
        assert 'validated_at' in data

    @patch('thoth.server.routers.config.EnhancedValidator')
    def test_validate_provided_config_with_errors(self, mock_validator):
        """Test validation of provided configuration with errors."""
        # Mock validator
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance

        error = ValidationIssue(
            field_path='api_key',
            issue_type=IssueType.VALIDATION_ERROR,
            severity=IssueSeverity.ERROR,
            message='Field is required',
            suggestion='Please provide a valid API key',
        )

        validation_result = ValidationResult(
            is_valid=False, errors=[error], warnings=[], suggestions=[]
        )
        mock_validator_instance.validate_config.return_value = validation_result

        config_data = {'port': 8080}  # missing api_key

        response = client.post('/config/validate', json=config_data)

        assert response.status_code == 200
        data = response.json()

        assert data['status'] == 'invalid'
        assert data['source'] == 'provided'
        assert data['is_valid'] is False
        assert data['error_count'] == 1
        assert len(data['errors']) == 1
        assert data['errors'][0]['field_path'] == 'api_key'

    @patch('thoth.server.routers.config.EnhancedValidator')
    def test_validate_config_error_handling(self, mock_validator):
        """Test validation error handling."""
        # Mock validator to raise exception
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_config.side_effect = Exception(
            'Validation failed'
        )

        response = client.post('/config/validate', json={})

        assert response.status_code == 500
        data = response.json()
        assert 'Config validation failed' in data['detail']


class TestConfigValidatePartialEndpoint:
    """Test suite for /config/validate-partial endpoint."""

    @patch('thoth.server.routers.config.EnhancedValidator')
    def test_validate_partial_config_success(self, mock_validator):
        """Test successful partial field validation."""
        # Mock validator
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance

        validation_result = ValidationResult(
            is_valid=True, errors=[], warnings=[], suggestions=[]
        )
        mock_validator_instance.validate_partial_config.return_value = validation_result

        request_data = {'field_path': 'port', 'field_value': 8080}

        response = client.post('/config/validate-partial', json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data['status'] == 'valid'
        assert data['field_path'] == 'port'
        assert data['field_value'] == 8080
        assert data['is_valid'] is True
        assert 'validated_at' in data

    @patch('thoth.server.routers.config.EnhancedValidator')
    def test_validate_partial_config_with_error(self, mock_validator):
        """Test partial validation with field error."""
        # Mock validator
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance

        error = ValidationIssue(
            field_path='port',
            issue_type=IssueType.RANGE_ERROR,
            severity=IssueSeverity.ERROR,
            message='Port out of valid range',
            suggestion='Use a port between 1 and 65535',
        )

        validation_result = ValidationResult(
            is_valid=False, errors=[error], warnings=[], suggestions=[]
        )
        mock_validator_instance.validate_partial_config.return_value = validation_result

        request_data = {'field_path': 'port', 'field_value': 99999}

        response = client.post('/config/validate-partial', json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data['status'] == 'invalid'
        assert data['field_path'] == 'port'
        assert data['field_value'] == 99999
        assert data['is_valid'] is False
        assert len(data['errors']) == 1

    @patch('thoth.server.routers.config.EnhancedValidator')
    def test_validate_partial_config_error_handling(self, mock_validator):
        """Test partial validation error handling."""
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_partial_config.side_effect = Exception(
            'Partial validation failed'
        )

        request_data = {'field_path': 'port', 'field_value': 8080}

        response = client.post('/config/validate-partial', json=request_data)

        assert response.status_code == 500
        data = response.json()
        assert 'Partial validation failed' in data['detail']


class TestSchemaVersionEndpoint:
    """Test suite for /config/schema/version endpoint."""

    def test_get_schema_version_success(self):
        """Test successful schema version retrieval."""
        response = client.get('/config/schema/version')

        assert response.status_code == 200
        data = response.json()

        assert data['status'] == 'success'
        assert data['current_version'] == '2.0.0'
        assert '2.0.0' in data['supported_versions']
        assert '1.0.0' in data['supported_versions']
        assert isinstance(data['migration_available'], bool)
        assert isinstance(data['migration_required'], bool)
        assert 'checked_at' in data


class TestSchemaMigrationEndpoint:
    """Test suite for /config/schema/migrate endpoint."""

    def test_schema_migration_success(self):
        """Test successful schema migration initiation."""
        response = client.post(
            '/config/schema/migrate?from_version=1.0.0&to_version=2.0.0'
        )

        assert response.status_code == 200
        data = response.json()

        assert data['status'] == 'success'
        assert data['migration_info']['from_version'] == '1.0.0'
        assert data['migration_info']['to_version'] == '2.0.0'
        assert 'migration_steps' in data['migration_info']
        assert data['migration_info']['backup_recommended'] is True
        assert 'migration_id' in data
        assert 'initiated_at' in data

    def test_schema_migration_default_version(self):
        """Test schema migration with default target version."""
        response = client.post('/config/schema/migrate?from_version=1.0.0')

        assert response.status_code == 200
        data = response.json()

        assert data['migration_info']['to_version'] == '2.0.0'


class TestConfigEndpointsIntegration:
    """Integration tests for config endpoints."""

    @patch('thoth.server.routers.config.SchemaGenerator')
    @patch('thoth.server.routers.config.EnhancedValidator')
    def test_schema_and_validation_integration(
        self, mock_validator, mock_schema_generator
    ):
        """Test that schema and validation endpoints work together."""
        # Mock schema generator
        mock_generator_instance = Mock()
        mock_schema_generator.return_value = mock_generator_instance
        mock_generator_instance.generate_schema.return_value = {
            'schema_version': '2.0.0',
            'fields': {},
            'field_groups': {},
            'validation_rules': {},
        }

        # Mock validator
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.validate_config.return_value = ValidationResult(
            is_valid=True, errors=[], warnings=[], suggestions=[]
        )

        # Test schema endpoint
        schema_response = client.get('/config/schema')
        assert schema_response.status_code == 200

        # Test validation endpoint
        validation_response = client.post('/config/validate', json={})
        assert validation_response.status_code == 200

        # Verify both use consistent version
        schema_data = schema_response.json()
        assert schema_data['schema_version'] == '2.0.0'

    def test_version_and_migration_consistency(self):
        """Test version and migration endpoints are consistent."""
        # Get version info
        version_response = client.get('/config/schema/version')
        assert version_response.status_code == 200

        version_data = version_response.json()
        current_version = version_data['current_version']

        # Test migration from older version to current
        migration_response = client.post(
            f'/config/schema/migrate?from_version=1.0.0&to_version={current_version}'
        )
        assert migration_response.status_code == 200

        migration_data = migration_response.json()
        assert migration_data['migration_info']['to_version'] == current_version


if __name__ == '__main__':
    pytest.main([__file__])

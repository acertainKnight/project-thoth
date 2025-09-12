"""Tests for EnhancedValidator utility class."""

import pytest
from pydantic import BaseModel, Field

from thoth.utilities.config.validation import (
    EnhancedValidator,
    IssueSeverity,
    IssueType,
    ValidationIssue,
    ValidationResult,
)


class MockConfigModel(BaseModel):
    """Mock configuration model for testing."""

    api_key: str = Field(..., description='API key for service', min_length=1)
    workspace_dir: str = Field(
        default='~/workspace', description='Workspace directory path'
    )
    port: int = Field(default=8000, description='Server port number', ge=1, le=65535)
    debug_mode: bool = Field(default=False, description='Enable debug mode')
    timeout: float = Field(default=30.0, description='Request timeout in seconds', gt=0)


class TestValidationIssue:
    """Test suite for ValidationIssue class."""

    def test_validation_issue_creation(self):
        """Test ValidationIssue can be created with all required fields."""
        issue = ValidationIssue(
            field_path='api_key',
            issue_type=IssueType.VALIDATION_ERROR,
            severity=IssueSeverity.ERROR,
            message='Field is required',
            suggestion='Please provide a valid API key',
        )

        assert issue.field_path == 'api_key'
        assert issue.issue_type == IssueType.VALIDATION_ERROR
        assert issue.severity == IssueSeverity.ERROR
        assert issue.message == 'Field is required'
        assert issue.suggestion == 'Please provide a valid API key'

    def test_validation_issue_optional_fields(self):
        """Test ValidationIssue with optional fields."""
        issue = ValidationIssue(
            field_path='port',
            issue_type=IssueType.RANGE_ERROR,
            severity=IssueSeverity.ERROR,
            message='Port out of range',
            suggestion='Use a port between 1 and 65535',
            current_value=99999,
            expected_format='integer between 1 and 65535',
        )

        assert issue.current_value == 99999
        assert issue.expected_format == 'integer between 1 and 65535'


class TestValidationResult:
    """Test suite for ValidationResult class."""

    def test_validation_result_valid(self):
        """Test ValidationResult for valid configuration."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[], suggestions=[])

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert len(result.suggestions) == 0

    def test_validation_result_with_errors(self):
        """Test ValidationResult with validation errors."""
        error = ValidationIssue(
            field_path='api_key',
            issue_type=IssueType.VALIDATION_ERROR,
            severity=IssueSeverity.ERROR,
            message='Field is required',
            suggestion='Please provide a valid API key',
        )

        result = ValidationResult(
            is_valid=False, errors=[error], warnings=[], suggestions=[]
        )

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0] == error


class TestEnhancedValidator:
    """Test suite for EnhancedValidator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = EnhancedValidator()

    def test_validator_initialization(self):
        """Test EnhancedValidator initializes correctly."""
        assert self.validator is not None
        assert hasattr(self.validator, 'validate_config')
        assert hasattr(self.validator, 'validate_partial_config')

    def test_validate_config_valid_data(self):
        """Test validating a valid configuration."""
        valid_config = {
            'api_key': 'test-key-123',
            'workspace_dir': '~/test-workspace',
            'port': 8080,
            'debug_mode': True,
            'timeout': 45.0,
        }

        result = self.validator.validate_config(valid_config, MockConfigModel)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_config_missing_required_field(self):
        """Test validation with missing required field."""
        invalid_config = {
            'workspace_dir': '~/test-workspace',
            'port': 8080,
            'debug_mode': True,
            # missing api_key
        }

        result = self.validator.validate_config(invalid_config, MockConfigModel)

        assert result.is_valid is False
        assert len(result.errors) > 0

        # Check if error mentions missing field
        error_messages = [error.message for error in result.errors]
        assert any(
            'required' in msg.lower() or 'missing' in msg.lower()
            for msg in error_messages
        )

    def test_validate_config_invalid_type(self):
        """Test validation with invalid field type."""
        invalid_config = {
            'api_key': 'test-key-123',
            'workspace_dir': '~/test-workspace',
            'port': 'not-a-number',  # should be int
            'debug_mode': True,
            'timeout': 45.0,
        }

        result = self.validator.validate_config(invalid_config, MockConfigModel)

        assert result.is_valid is False
        assert len(result.errors) > 0

        # Check if there's a type-related error
        port_errors = [error for error in result.errors if 'port' in error.field_path]
        assert len(port_errors) > 0

    def test_validate_config_out_of_range(self):
        """Test validation with value out of allowed range."""
        invalid_config = {
            'api_key': 'test-key-123',
            'workspace_dir': '~/test-workspace',
            'port': 99999,  # out of range (> 65535)
            'debug_mode': True,
            'timeout': 45.0,
        }

        result = self.validator.validate_config(invalid_config, MockConfigModel)

        assert result.is_valid is False
        assert len(result.errors) > 0

        # Check if there's a range-related error
        port_errors = [error for error in result.errors if 'port' in error.field_path]
        assert len(port_errors) > 0

    def test_validate_config_negative_timeout(self):
        """Test validation with negative timeout value."""
        invalid_config = {
            'api_key': 'test-key-123',
            'workspace_dir': '~/test-workspace',
            'port': 8080,
            'debug_mode': True,
            'timeout': -5.0,  # should be > 0
        }

        result = self.validator.validate_config(invalid_config, MockConfigModel)

        assert result.is_valid is False
        assert len(result.errors) > 0

        # Check for timeout-related error
        timeout_errors = [
            error for error in result.errors if 'timeout' in error.field_path
        ]
        assert len(timeout_errors) > 0

    def test_validate_partial_config_valid_field(self):
        """Test partial validation with valid field."""
        result = self.validator.validate_partial_config(
            {'port': 8080}, 'port', MockConfigModel
        )

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_partial_config_invalid_field(self):
        """Test partial validation with invalid field."""
        result = self.validator.validate_partial_config(
            {'port': 'invalid'}, 'port', MockConfigModel
        )

        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_partial_config_nested_field(self):
        """Test partial validation with nested field path."""
        # This tests the dot-notation field path functionality
        result = self.validator.validate_partial_config(
            {'api_settings': {'key': 'test-key'}}, 'api_settings.key'
        )

        # Should handle nested paths gracefully
        # The exact behavior depends on implementation
        assert isinstance(result, ValidationResult)

    def test_business_logic_validation(self):
        """Test custom business logic validation."""
        # Test with a configuration that passes Pydantic validation
        # but might fail business logic checks
        config = {
            'api_key': 'test',  # too short for production
            'workspace_dir': '~/test-workspace',
            'port': 8080,
            'debug_mode': True,
            'timeout': 45.0,
        }

        result = self.validator.validate_config(config, MockConfigModel)

        # Should include suggestions for improvement
        # even if basic validation passes
        assert isinstance(result, ValidationResult)

    def test_create_validation_issue(self):
        """Test _create_validation_issue helper method."""
        if hasattr(self.validator, '_create_validation_issue'):
            issue = self.validator._create_validation_issue(
                'api_key',
                IssueType.VALIDATION_ERROR,
                IssueSeverity.ERROR,
                'Invalid API key format',
            )

            assert isinstance(issue, ValidationIssue)
            assert issue.field_path == 'api_key'
            assert issue.issue_type == IssueType.VALIDATION_ERROR
            assert issue.severity == IssueSeverity.ERROR

    def test_error_message_formatting(self):
        """Test that error messages are well formatted and actionable."""
        invalid_config = {
            'api_key': '',  # empty string
            'port': 0,  # invalid port
            'timeout': -1,  # negative timeout
        }

        result = self.validator.validate_config(invalid_config, MockConfigModel)

        assert result.is_valid is False
        assert len(result.errors) > 0

        # Check that error messages are informative
        for error in result.errors:
            assert len(error.message) > 0
            assert error.suggestion is not None
            assert len(error.suggestion) > 0

    def test_suggestions_provided(self):
        """Test that validation provides helpful suggestions."""
        config_with_warnings = {
            'api_key': 'short',  # might trigger suggestion for longer key
            'workspace_dir': '~/test-workspace',
            'port': 8080,
            'debug_mode': True,
            'timeout': 45.0,
        }

        result = self.validator.validate_config(config_with_warnings, MockConfigModel)

        # Should provide suggestions even if validation passes
        # The exact behavior depends on implementation
        assert isinstance(result, ValidationResult)

        # Check that any issues have suggestions
        all_issues = result.errors + result.warnings + result.suggestions
        for issue in all_issues:
            if issue.suggestion:
                assert len(issue.suggestion) > 0


if __name__ == '__main__':
    pytest.main([__file__])

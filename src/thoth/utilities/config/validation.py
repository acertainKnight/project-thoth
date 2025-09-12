"""
Enhanced validation utilities for configuration with detailed error reporting.

This module provides comprehensive validation functions that generate
detailed, actionable error messages for the Obsidian plugin UI.
"""

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError


class IssueType(str, Enum):
    """Types of validation issues."""

    VALIDATION_ERROR = 'validation_error'
    RANGE_ERROR = 'range_error'
    TYPE_ERROR = 'type_error'
    FORMAT_ERROR = 'format_error'
    MISSING_FIELD = 'missing_field'
    BUSINESS_LOGIC = 'business_logic'


class IssueSeverity(str, Enum):
    """Severity levels for validation issues."""

    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'


class ValidationIssue(BaseModel):
    """A single validation issue with detailed information."""

    field_path: str
    issue_type: IssueType
    severity: IssueSeverity
    message: str
    suggestion: str | None = None
    current_value: Any = None
    expected_format: str | None = None


class ValidationResult(BaseModel):
    """Structured validation result with detailed error information."""

    is_valid: bool
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    suggestions: list[ValidationIssue] = []


class EnhancedValidator:
    """Enhanced configuration validator with detailed error reporting."""

    def __init__(self):
        """Initialize the enhanced validator."""
        pass

    def validate_config(
        self, config_data: dict[str, Any], model_class: type[BaseModel] | None = None
    ) -> ValidationResult:
        """Validate configuration data with detailed error reporting."""
        errors = []
        warnings = []
        suggestions = []

        # Use provided model class or try to import ThothConfig
        if model_class is None:
            try:
                from thoth.utilities.config import ThothConfig

                model_class = ThothConfig
            except ImportError:
                # If ThothConfig is not available, we can't validate
                errors.append(
                    ValidationIssue(
                        field_path='__root__',
                        issue_type=IssueType.VALIDATION_ERROR,
                        severity=IssueSeverity.ERROR,
                        message='Configuration model not available for validation',
                        suggestion='Please ensure the configuration module is properly imported',
                    )
                )
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    suggestions=suggestions,
                )

        try:
            # Attempt to create and validate the config
            config_instance = model_class.model_validate(config_data)

            # Perform additional business logic validation
            business_issues = self._perform_business_validation(config_instance)
            warnings.extend(business_issues.get('warnings', []))
            suggestions.extend(business_issues.get('suggestions', []))

        except ValidationError as e:
            # Parse Pydantic validation errors
            errors.extend(self._parse_pydantic_errors(e))
        except Exception as e:
            # Handle unexpected errors
            errors.append(
                ValidationIssue(
                    field_path='__root__',
                    issue_type=IssueType.VALIDATION_ERROR,
                    severity=IssueSeverity.ERROR,
                    message=f'Unexpected validation error: {e!s}',
                    suggestion='Please check your configuration format and try again',
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def validate_partial_config(
        self,
        partial_data: dict[str, Any],
        field_path: str,
        model_class: type[BaseModel] | None = None,
    ) -> ValidationResult:
        """Validate a single field change without full config validation."""
        errors = []
        warnings = []
        suggestions = []

        # Use provided model class or try to import ThothConfig
        if model_class is None:
            try:
                from thoth.utilities.config import ThothConfig

                model_class = ThothConfig
            except ImportError:
                # If ThothConfig is not available, we can't validate
                errors.append(
                    ValidationIssue(
                        field_path=field_path,
                        issue_type=IssueType.VALIDATION_ERROR,
                        severity=IssueSeverity.ERROR,
                        message='Configuration model not available for validation',
                        suggestion='Please ensure the configuration module is properly imported',
                    )
                )
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    suggestions=suggestions,
                )

        try:
            # Split field path to navigate nested structures
            path_parts = field_path.split('.')

            # Create a minimal config structure for validation
            test_data = self._build_minimal_config(
                path_parts, partial_data.get(field_path)
            )

            # Validate just this field
            config_instance = model_class.model_validate(test_data, strict=False)

            # Extract the specific field for validation
            field_obj = self._get_field_from_path(config_instance, path_parts)

            # Perform field-specific validation
            field_issues = self._validate_single_field(field_path, field_obj)
            warnings.extend(field_issues.get('warnings', []))
            suggestions.extend(field_issues.get('suggestions', []))

        except ValidationError as e:
            # Parse errors specific to this field
            errors.extend(self._parse_partial_errors(e, field_path))
        except Exception as e:
            errors.append(
                ValidationIssue(
                    field_path=field_path,
                    issue_type=IssueType.VALIDATION_ERROR,
                    severity=IssueSeverity.ERROR,
                    message=f'Field validation failed: {e!s}',
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def _parse_pydantic_errors(self, error: ValidationError) -> list[ValidationIssue]:
        """Parse Pydantic validation errors into detailed messages."""
        issues = []
        for error_detail in error.errors():
            field_path = '.'.join(str(loc) for loc in error_detail['loc'])
            error_type = error_detail['type']
            message = error_detail['msg']
            input_value = error_detail.get('input', 'N/A')

            # Generate enhanced error messages and suggestions
            enhanced_message, suggestion = self._enhance_error_message(
                error_type, message, field_path, input_value
            )

            issues.append(
                ValidationIssue(
                    field_path=field_path,
                    issue_type=IssueType.VALIDATION_ERROR,
                    severity=IssueSeverity.ERROR,
                    message=enhanced_message,
                    suggestion=suggestion,
                    current_value=input_value,
                )
            )
        return issues

    def _parse_partial_errors(
        self, error: ValidationError, target_field: str
    ) -> list[ValidationIssue]:
        """Parse errors from partial validation focusing on the target field."""
        issues = []
        for error_detail in error.errors():
            field_path = '.'.join(str(loc) for loc in error_detail['loc'])

            # Only include errors relevant to the target field
            if field_path.startswith(target_field) or target_field.startswith(
                field_path
            ):
                error_type = error_detail['type']
                message = error_detail['msg']
                input_value = error_detail.get('input', 'N/A')

                enhanced_message, suggestion = self._enhance_error_message(
                    error_type, message, field_path, input_value
                )

                issues.append(
                    ValidationIssue(
                        field_path=target_field,  # Use the original target field
                        issue_type=IssueType.VALIDATION_ERROR,
                        severity=IssueSeverity.ERROR,
                        message=enhanced_message,
                        suggestion=suggestion,
                        current_value=input_value,
                    )
                )
        return issues

    def _enhance_error_message(
        self, error_type: str, original_message: str, field_path: str, input_value: Any
    ) -> tuple[str, str | None]:
        """Generate enhanced error messages with helpful suggestions."""

        field_name = field_path.split('.')[-1]

        # Error type specific enhancements
        if error_type == 'missing':
            message = f"Required field '{field_name}' is missing"
            suggestion = f'Please provide a value for {field_name}'

        elif error_type == 'string_type':
            message = f"Field '{field_name}' must be a text value"
            suggestion = f"Provided value '{input_value}' is not valid text. Please enter a string value."

        elif error_type == 'int_type':
            message = f"Field '{field_name}' must be a whole number"
            suggestion = f"Provided value '{input_value}' is not a valid number. Please enter an integer."

        elif error_type == 'float_type':
            message = f"Field '{field_name}' must be a number"
            suggestion = f"Provided value '{input_value}' is not a valid number. Please enter a numeric value."

        elif error_type == 'bool_type':
            message = f"Field '{field_name}' must be true or false"
            suggestion = f"Provided value '{input_value}' is not valid. Please select true or false."

        elif error_type == 'greater_than_equal':
            message = f"Field '{field_name}' must be greater than or equal to the minimum value"
            suggestion = 'Please increase the value to meet the minimum requirement'

        elif error_type == 'less_than_equal':
            message = (
                f"Field '{field_name}' must be less than or equal to the maximum value"
            )
            suggestion = 'Please decrease the value to meet the maximum requirement'

        elif error_type == 'string_pattern_mismatch':
            if 'api' in field_name.lower() and 'key' in field_name.lower():
                message = 'API key format is invalid'
                suggestion = "Please check that you've copied the complete API key from your provider"
            else:
                message = f"Field '{field_name}' format is invalid"
                suggestion = 'Please check the format requirements and try again'

        elif error_type == 'path_not_exists':
            message = f"Directory or file path does not exist: '{input_value}'"
            suggestion = 'Please create the directory or choose an existing path'

        elif error_type == 'url_parsing':
            message = f"Invalid URL format in field '{field_name}'"
            suggestion = 'Please enter a valid URL starting with http:// or https://'

        else:
            # Fallback for unknown error types
            message = f"Validation error in '{field_name}': {original_message}"
            suggestion = 'Please check the value format and requirements'

        return message, suggestion

    def _perform_business_validation(
        self, config: BaseModel
    ) -> dict[str, list[ValidationIssue]]:
        """Perform business logic validation beyond basic Pydantic validation."""
        warnings = []
        suggestions = []

        # Example business validations that could be added:

        # Check for API key presence
        if hasattr(config, 'api_keys'):
            api_keys = config.api_keys
            if not any(
                [
                    getattr(api_keys, 'mistral_key', None),
                    getattr(api_keys, 'openrouter_key', None),
                    getattr(api_keys, 'openai_key', None),
                ]
            ):
                warnings.append(
                    ValidationIssue(
                        field_path='api_keys',
                        issue_type=IssueType.BUSINESS_LOGIC,
                        severity=IssueSeverity.WARNING,
                        message='No LLM API keys configured',
                        suggestion='Configure at least one LLM provider API key for full functionality',
                    )
                )

        # Check directory accessibility
        if hasattr(config, 'core') and hasattr(config.core, 'workspace_dir'):
            workspace_path = Path(config.core.workspace_dir)
            if not workspace_path.exists():
                warnings.append(
                    ValidationIssue(
                        field_path='core.workspace_dir',
                        issue_type=IssueType.BUSINESS_LOGIC,
                        severity=IssueSeverity.WARNING,
                        message='Workspace directory does not exist',
                        suggestion='The directory will be created automatically when needed',
                    )
                )
            elif not workspace_path.is_dir():
                warnings.append(
                    ValidationIssue(
                        field_path='core.workspace_dir',
                        issue_type=IssueType.BUSINESS_LOGIC,
                        severity=IssueSeverity.ERROR,
                        message='Workspace path exists but is not a directory',
                        suggestion='Please choose a different path or remove the existing file',
                    )
                )

        # Check port conflicts
        if hasattr(config, 'features') and hasattr(config.features, 'api_server'):
            api_port = getattr(config.features.api_server, 'port', None)
            if (
                hasattr(config.features, 'mcp')
                and getattr(config.features.mcp, 'port', None) == api_port
            ):
                warnings.append(
                    ValidationIssue(
                        field_path='features.mcp.port',
                        issue_type=IssueType.BUSINESS_LOGIC,
                        severity=IssueSeverity.ERROR,
                        message='MCP server port conflicts with API server port',
                        suggestion=f'Choose a different port (API server uses {api_port})',
                    )
                )

        return {'warnings': warnings, 'suggestions': suggestions}

    def _build_minimal_config(
        self, path_parts: list[str], value: Any
    ) -> dict[str, Any]:
        """Build minimal config structure for partial validation."""
        if not path_parts:
            return {}

        # Build nested structure
        result: dict[str, Any] = {}
        current = result

        for part in path_parts[:-1]:
            current[part] = {}
            current = current[part]

        # Set the final value
        current[path_parts[-1]] = value

        return result

    def _get_field_from_path(self, config: BaseModel, path_parts: list[str]) -> Any:
        """Navigate to a specific field in the config using path parts."""
        current = config

        for part in path_parts:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return None

        return current

    def _validate_single_field(
        self, field_path: str, field_value: Any
    ) -> dict[str, list[ValidationIssue]]:
        """Perform additional validation on a single field."""
        warnings = []
        suggestions = []

        # Field-specific validation logic
        field_name = field_path.split('.')[-1].lower()

        # Validate API keys
        if 'key' in field_name and field_value:
            if isinstance(field_value, str):
                if len(field_value.strip()) == 0:
                    warnings.append(
                        ValidationIssue(
                            field_path=field_path,
                            issue_type=IssueType.BUSINESS_LOGIC,
                            severity=IssueSeverity.WARNING,
                            message='API key appears to be empty',
                            suggestion='Please enter a valid API key',
                        )
                    )
                elif len(field_value) < 10:
                    warnings.append(
                        ValidationIssue(
                            field_path=field_path,
                            issue_type=IssueType.BUSINESS_LOGIC,
                            severity=IssueSeverity.WARNING,
                            message='API key seems unusually short',
                            suggestion="Please verify you've copied the complete key",
                        )
                    )

        # Validate ports
        if 'port' in field_name and isinstance(field_value, int):
            if field_value < 1024:
                warnings.append(
                    ValidationIssue(
                        field_path=field_path,
                        issue_type=IssueType.RANGE_ERROR,
                        severity=IssueSeverity.ERROR,
                        message='Port number is too low',
                        suggestion='Use ports 1024 or higher to avoid conflicts with system services',
                    )
                )
            elif field_value > 65535:
                warnings.append(
                    ValidationIssue(
                        field_path=field_path,
                        issue_type=IssueType.RANGE_ERROR,
                        severity=IssueSeverity.ERROR,
                        message='Port number is too high',
                        suggestion='Use ports 65535 or lower',
                    )
                )

        # Validate temperatures
        if 'temperature' in field_name and isinstance(field_value, int | float):
            if field_value < 0.0 or field_value > 1.0:
                warnings.append(
                    ValidationIssue(
                        field_path=field_path,
                        issue_type=IssueType.RANGE_ERROR,
                        severity=IssueSeverity.ERROR,
                        message='Temperature must be between 0.0 and 1.0',
                        suggestion='Use 0.0 for deterministic outputs, 1.0 for maximum creativity',
                    )
                )

        return {'warnings': warnings, 'suggestions': suggestions}


# Convenience function for easy import
def validate_config(
    config_data: dict[str, Any], model_class: type[BaseModel] | None = None
) -> ValidationResult:
    """Validate configuration with enhanced error reporting."""
    validator = EnhancedValidator()
    return validator.validate_config(config_data, model_class)


def validate_partial_config(
    field_path: str, field_value: Any, model_class: type[BaseModel] | None = None
) -> ValidationResult:
    """Validate a single field change."""
    validator = EnhancedValidator()
    partial_data = {field_path: field_value}
    return validator.validate_partial_config(partial_data, field_path, model_class)

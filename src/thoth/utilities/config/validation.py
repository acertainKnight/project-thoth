"""
Enhanced validation utilities for configuration with detailed error reporting.

This module provides comprehensive validation functions that generate
detailed, actionable error messages for the Obsidian plugin UI.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError


class ValidationResult:
    """Structured validation result with detailed error information."""

    def __init__(self):
        self.valid = True
        self.errors: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []
        self.suggestions: list[dict[str, Any]] = []

    def add_error(
        self,
        field: str,
        error_type: str,
        message: str,
        suggestion: str | None = None,
        severity: str = 'error',
    ):
        """Add a validation error."""
        self.valid = False
        error_entry = {
            'field': field,
            'type': error_type,
            'message': message,
            'severity': severity,
        }
        if suggestion:
            error_entry['suggestion'] = suggestion

        self.errors.append(error_entry)

    def add_warning(self, field: str, message: str, suggestion: str | None = None):
        """Add a validation warning."""
        warning_entry = {'field': field, 'message': message, 'severity': 'warning'}
        if suggestion:
            warning_entry['suggestion'] = suggestion

        self.warnings.append(warning_entry)

    def add_suggestion(self, field: str, message: str, action: str | None = None):
        """Add a helpful suggestion."""
        suggestion_entry = {'field': field, 'message': message}
        if action:
            suggestion_entry['action'] = action

        self.suggestions.append(suggestion_entry)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for API responses."""
        return {
            'valid': self.valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'suggestions': self.suggestions,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
        }


class EnhancedValidator:
    """Enhanced configuration validator with detailed error reporting."""

    def __init__(self):
        """Initialize the enhanced validator."""
        pass

    def validate_config(
        self, config_class: type[BaseModel], config_data: dict[str, Any]
    ) -> ValidationResult:
        """Validate configuration data with detailed error reporting."""
        result = ValidationResult()

        try:
            # Attempt to create and validate the config
            config_instance = config_class.model_validate(config_data)

            # Perform additional business logic validation
            self._perform_business_validation(config_instance, result)

        except ValidationError as e:
            # Parse Pydantic validation errors
            self._parse_pydantic_errors(e, result)
        except Exception as e:
            # Handle unexpected errors
            result.add_error(
                field='__root__',
                error_type='unexpected_error',
                message=f'Unexpected validation error: {e!s}',
                suggestion='Please check your configuration format and try again',
            )

        return result

    def validate_partial_config(
        self, config_class: type[BaseModel], field_path: str, field_value: Any
    ) -> ValidationResult:
        """Validate a single field change without full config validation."""
        result = ValidationResult()

        try:
            # Split field path to navigate nested structures
            path_parts = field_path.split('.')

            # Create a minimal config structure for validation
            test_data = self._build_minimal_config(path_parts, field_value)

            # Validate just this field
            config_instance = config_class.model_validate(test_data, strict=False)

            # Extract the specific field for validation
            field_obj = self._get_field_from_path(config_instance, path_parts)

            # Perform field-specific validation
            self._validate_single_field(field_path, field_obj, result)

        except ValidationError as e:
            # Parse errors specific to this field
            self._parse_partial_errors(e, field_path, result)
        except Exception as e:
            result.add_error(
                field=field_path,
                error_type='validation_error',
                message=f'Field validation failed: {e!s}',
            )

        return result

    def _parse_pydantic_errors(self, error: ValidationError, result: ValidationResult):
        """Parse Pydantic validation errors into detailed messages."""
        for error_detail in error.errors():
            field_path = '.'.join(str(loc) for loc in error_detail['loc'])
            error_type = error_detail['type']
            message = error_detail['msg']
            input_value = error_detail.get('input', 'N/A')

            # Generate enhanced error messages and suggestions
            enhanced_message, suggestion = self._enhance_error_message(
                error_type, message, field_path, input_value
            )

            result.add_error(
                field=field_path,
                error_type=error_type,
                message=enhanced_message,
                suggestion=suggestion,
            )

    def _parse_partial_errors(
        self, error: ValidationError, target_field: str, result: ValidationResult
    ):
        """Parse errors from partial validation focusing on the target field."""
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

                result.add_error(
                    field=target_field,  # Use the original target field
                    error_type=error_type,
                    message=enhanced_message,
                    suggestion=suggestion,
                )

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

    def _perform_business_validation(self, config: BaseModel, result: ValidationResult):
        """Perform business logic validation beyond basic Pydantic validation."""

        # Example business validations that could be added:

        # Check for API key presence
        if hasattr(config, 'api_keys'):
            api_keys = config.api_keys
            if not any(
                [api_keys.mistral_key, api_keys.openrouter_key, api_keys.openai_key]
            ):
                result.add_warning(
                    field='api_keys',
                    message='No LLM API keys configured',
                    suggestion='Configure at least one LLM provider API key for full functionality',
                )

        # Check directory accessibility
        if hasattr(config, 'workspace_dir'):
            workspace_path = Path(config.workspace_dir)
            if not workspace_path.exists():
                result.add_warning(
                    field='workspace_dir',
                    message='Workspace directory does not exist',
                    suggestion='The directory will be created automatically when needed',
                )
            elif not workspace_path.is_dir():
                result.add_error(
                    field='workspace_dir',
                    error_type='path_validation',
                    message='Workspace path exists but is not a directory',
                    suggestion='Please choose a different path or remove the existing file',
                )

        # Check port conflicts
        if hasattr(config, 'features') and hasattr(config.features, 'api_server'):
            api_port = config.features.api_server.port
            if hasattr(config.features, 'mcp') and config.features.mcp.port == api_port:
                result.add_error(
                    field='features.mcp.port',
                    error_type='port_conflict',
                    message='MCP server port conflicts with API server port',
                    suggestion=f'Choose a different port (API server uses {api_port})',
                )

    def _build_minimal_config(
        self, path_parts: list[str], value: Any
    ) -> dict[str, Any]:
        """Build minimal config structure for partial validation."""
        if not path_parts:
            return {}

        # Build nested structure
        result: dict[str, Any] = {}
        current = result

        for _i, part in enumerate(path_parts[:-1]):
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
        self, field_path: str, field_value: Any, result: ValidationResult
    ):
        """Perform additional validation on a single field."""

        # Field-specific validation logic
        field_name = field_path.split('.')[-1].lower()

        # Validate API keys
        if 'key' in field_name and field_value:
            if isinstance(field_value, str):
                if len(field_value.strip()) == 0:
                    result.add_warning(
                        field=field_path,
                        message='API key appears to be empty',
                        suggestion='Please enter a valid API key',
                    )
                elif len(field_value) < 10:
                    result.add_warning(
                        field=field_path,
                        message='API key seems unusually short',
                        suggestion="Please verify you've copied the complete key",
                    )

        # Validate ports
        if 'port' in field_name and isinstance(field_value, int):
            if field_value < 1024:
                result.add_error(
                    field=field_path,
                    error_type='port_range',
                    message='Port number is too low',
                    suggestion='Use ports 1024 or higher to avoid conflicts with system services',
                )
            elif field_value > 65535:
                result.add_error(
                    field=field_path,
                    error_type='port_range',
                    message='Port number is too high',
                    suggestion='Use ports 65535 or lower',
                )

        # Validate temperatures
        if 'temperature' in field_name and isinstance(field_value, int | float):
            if field_value < 0.0 or field_value > 1.0:
                result.add_error(
                    field=field_path,
                    error_type='range_validation',
                    message='Temperature must be between 0.0 and 1.0',
                    suggestion='Use 0.0 for deterministic outputs, 1.0 for maximum creativity',
                )


# Convenience function for easy import
def validate_config(
    config_class: type[BaseModel], config_data: dict[str, Any]
) -> ValidationResult:
    """Validate configuration with enhanced error reporting."""
    validator = EnhancedValidator()
    return validator.validate_config(config_class, config_data)


def validate_partial_config(
    config_class: type[BaseModel], field_path: str, field_value: Any
) -> ValidationResult:
    """Validate a single field change."""
    validator = EnhancedValidator()
    return validator.validate_partial_config(config_class, field_path, field_value)

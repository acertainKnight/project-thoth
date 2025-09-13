"""
Enhanced validation utilities for configuration with detailed error reporting.

This module provides comprehensive validation functions that generate
detailed, actionable error messages for the Obsidian plugin UI.

Enhanced with pre-restart validation capabilities for Docker environments.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, ValidationError

# Import service manager types if available
try:
    from thoth.services.service_manager import (
        ConfigChanges,
        ImpactAnalysis,
        ImpactReport,
        ServiceManager,
    )

    SERVICE_MANAGER_AVAILABLE = True
except ImportError:
    SERVICE_MANAGER_AVAILABLE = False
    logger.debug('Service manager not available for validation')


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


class AutoFix(BaseModel):
    """Represents an automatic fix for a validation issue."""

    fix_id: str
    description: str
    field_path: str
    current_value: Any
    suggested_value: Any
    confidence: float  # 0.0 to 1.0
    risk_level: str  # 'low', 'medium', 'high'
    fix_type: str  # 'value_correction', 'format_fix', 'default_substitution', 'type_conversion'


class ContextualHelp(BaseModel):
    """Contextual help information for configuration fields."""

    help_id: str
    field_path: str
    title: str
    content: str
    examples: list[str] = []
    related_fields: list[str] = []
    documentation_links: list[str] = []
    troubleshooting_steps: list[str] = []


class ValidationIssue(BaseModel):
    """A single validation issue with detailed information."""

    field_path: str
    issue_type: IssueType
    severity: IssueSeverity
    message: str
    suggestion: str | None = None
    current_value: Any = None
    expected_format: str | None = None
    auto_fixes: list[AutoFix] = []
    contextual_help: ContextualHelp | None = None


class ValidationResult(BaseModel):
    """Structured validation result with detailed error information."""

    is_valid: bool
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    suggestions: list[ValidationIssue] = []
    auto_fixes: list[AutoFix] = []
    contextual_help: list[ContextualHelp] = []


@dataclass
class StagingResult:
    """Result of configuration staging operation."""

    success: bool
    staging_path: str
    validation_result: Optional['ValidationResult'] = None
    error_message: str | None = None


@dataclass
class RollbackPoint:
    """Information about a rollback point."""

    rollback_id: str
    timestamp: datetime
    description: str
    config_snapshot: dict[str, Any]
    file_backup_path: str


class AutoFixSuggestions:
    """Auto-fix suggestion engine for common configuration errors."""

    def __init__(self):
        """Initialize the auto-fix engine."""
        self.fix_patterns = self._build_fix_patterns()
        self.help_database = self._build_help_database()

    def detect_fixable_errors(
        self, validation_result: ValidationResult
    ) -> list[AutoFix]:
        """Detect errors that can be automatically fixed."""
        auto_fixes = []

        for error in validation_result.errors:
            fixes = self._generate_auto_fixes_for_error(error)
            auto_fixes.extend(fixes)

        return auto_fixes

    def apply_auto_fix(self, auto_fix: AutoFix) -> dict[str, Any]:
        """Apply an auto-fix and return the result."""
        try:
            result = {
                'success': True,
                'field_path': auto_fix.field_path,
                'old_value': auto_fix.current_value,
                'new_value': auto_fix.suggested_value,
                'fix_type': auto_fix.fix_type,
                'message': f'Applied {auto_fix.description}',
            }

            logger.info(
                f'Applied auto-fix {auto_fix.fix_id} for {auto_fix.field_path}: {auto_fix.current_value} -> {auto_fix.suggested_value}'
            )
            return result

        except Exception as e:
            logger.error(f'Failed to apply auto-fix {auto_fix.fix_id}: {e}')
            return {'success': False, 'error': str(e), 'fix_id': auto_fix.fix_id}

    def suggest_configuration_improvements(self, config: dict) -> list[ValidationIssue]:
        """Suggest configuration improvements based on best practices."""
        suggestions = []

        # Check for common improvement opportunities
        suggestions.extend(self._check_performance_improvements(config))
        suggestions.extend(self._check_security_improvements(config))
        suggestions.extend(self._check_usability_improvements(config))

        return suggestions

    def provide_contextual_help(
        self, field_path: str, error: ValidationIssue
    ) -> ContextualHelp:
        """Provide contextual help for a specific field and error."""
        help_content = self.help_database.get(field_path, {})

        return ContextualHelp(
            help_id=f'help_{field_path}_{error.issue_type}',
            field_path=field_path,
            title=help_content.get('title', f'Help for {field_path}'),
            content=help_content.get(
                'content', self._generate_default_help(field_path, error)
            ),
            examples=help_content.get('examples', []),
            related_fields=help_content.get('related_fields', []),
            documentation_links=help_content.get('documentation_links', []),
            troubleshooting_steps=help_content.get('troubleshooting_steps', []),
        )

    def _generate_auto_fixes_for_error(self, error: ValidationIssue) -> list[AutoFix]:
        """Generate auto-fixes for a specific error."""
        fixes = []
        field_path = error.field_path
        current_value = error.current_value

        # Common auto-fixes based on error type and field patterns
        if error.issue_type == IssueType.TYPE_ERROR:
            fixes.extend(
                self._generate_type_conversion_fixes(field_path, current_value, error)
            )
        elif error.issue_type == IssueType.FORMAT_ERROR:
            fixes.extend(self._generate_format_fixes(field_path, current_value, error))
        elif error.issue_type == IssueType.RANGE_ERROR:
            fixes.extend(self._generate_range_fixes(field_path, current_value, error))
        elif error.issue_type == IssueType.MISSING_FIELD:
            fixes.extend(
                self._generate_default_value_fixes(field_path, current_value, error)
            )

        return fixes

    def _generate_type_conversion_fixes(
        self, field_path: str, current_value: Any, _error: ValidationIssue
    ) -> list[AutoFix]:
        """Generate type conversion fixes."""
        fixes = []

        if 'port' in field_path.lower() and isinstance(current_value, str):
            try:
                port_num = int(current_value)
                if 1024 <= port_num <= 65535:
                    fixes.append(
                        AutoFix(
                            fix_id=f'convert_port_{field_path}',
                            description=f'Convert port "{current_value}" to integer',
                            field_path=field_path,
                            current_value=current_value,
                            suggested_value=port_num,
                            confidence=0.9,
                            risk_level='low',
                            fix_type='type_conversion',
                        )
                    )
            except ValueError:
                pass

        # Boolean conversion fixes
        if isinstance(current_value, str) and current_value.lower() in [
            'true',
            'false',
            'yes',
            'no',
            '1',
            '0',
        ]:
            bool_value = current_value.lower() in ['true', 'yes', '1']
            fixes.append(
                AutoFix(
                    fix_id=f'convert_bool_{field_path}',
                    description=f'Convert "{current_value}" to boolean',
                    field_path=field_path,
                    current_value=current_value,
                    suggested_value=bool_value,
                    confidence=0.9,
                    risk_level='low',
                    fix_type='type_conversion',
                )
            )

        return fixes

    def _generate_format_fixes(
        self, field_path: str, current_value: Any, _error: ValidationIssue
    ) -> list[AutoFix]:
        """Generate format fixes."""
        fixes = []

        # URL format fixes
        if 'url' in field_path.lower() and isinstance(current_value, str):
            if not current_value.startswith(('http://', 'https://')):
                fixes.append(
                    AutoFix(
                        fix_id=f'fix_url_protocol_{field_path}',
                        description='Add https:// protocol to URL',
                        field_path=field_path,
                        current_value=current_value,
                        suggested_value=f'https://{current_value}',
                        confidence=0.8,
                        risk_level='low',
                        fix_type='format_fix',
                    )
                )

        # Path format fixes
        if ('dir' in field_path.lower() or 'path' in field_path.lower()) and isinstance(
            current_value, str
        ):
            # Convert backslashes to forward slashes on Windows
            if '\\' in current_value and '/' not in current_value:
                normalized_path = current_value.replace('\\', '/')
                fixes.append(
                    AutoFix(
                        fix_id=f'normalize_path_{field_path}',
                        description='Normalize path separators',
                        field_path=field_path,
                        current_value=current_value,
                        suggested_value=normalized_path,
                        confidence=0.9,
                        risk_level='low',
                        fix_type='format_fix',
                    )
                )

        return fixes

    def _generate_range_fixes(
        self, field_path: str, current_value: Any, _error: ValidationIssue
    ) -> list[AutoFix]:
        """Generate range fixes."""
        fixes = []

        if isinstance(current_value, int | float):
            # Port range fixes
            if 'port' in field_path.lower():
                if current_value < 1024:
                    fixes.append(
                        AutoFix(
                            fix_id=f'fix_port_range_{field_path}',
                            description='Adjust port to minimum safe value',
                            field_path=field_path,
                            current_value=current_value,
                            suggested_value=8000,
                            confidence=0.7,
                            risk_level='medium',
                            fix_type='value_correction',
                        )
                    )
                elif current_value > 65535:
                    fixes.append(
                        AutoFix(
                            fix_id=f'fix_port_range_{field_path}',
                            description='Adjust port to maximum allowed value',
                            field_path=field_path,
                            current_value=current_value,
                            suggested_value=65535,
                            confidence=0.8,
                            risk_level='low',
                            fix_type='value_correction',
                        )
                    )

            # Temperature range fixes
            if 'temperature' in field_path.lower():
                if current_value < 0:
                    fixes.append(
                        AutoFix(
                            fix_id=f'fix_temp_range_{field_path}',
                            description='Set temperature to minimum value',
                            field_path=field_path,
                            current_value=current_value,
                            suggested_value=0.0,
                            confidence=0.9,
                            risk_level='low',
                            fix_type='value_correction',
                        )
                    )
                elif current_value > 1:
                    fixes.append(
                        AutoFix(
                            fix_id=f'fix_temp_range_{field_path}',
                            description='Set temperature to maximum value',
                            field_path=field_path,
                            current_value=current_value,
                            suggested_value=1.0,
                            confidence=0.9,
                            risk_level='low',
                            fix_type='value_correction',
                        )
                    )

        return fixes

    def _generate_default_value_fixes(
        self, field_path: str, current_value: Any, _error: ValidationIssue
    ) -> list[AutoFix]:
        """Generate default value fixes for missing fields."""
        fixes = []

        # Common default values based on field patterns
        defaults = {
            'port': 8000,
            'host': 'localhost',
            'temperature': 0.7,
            'max_tokens': 4096,
            'timeout': 30,
            'enabled': True,
            'auto_start': False,
            'batch_size': 10,
            'chunk_size': 1000,
        }

        for pattern, default_value in defaults.items():
            if pattern in field_path.lower():
                fixes.append(
                    AutoFix(
                        fix_id=f'set_default_{field_path}',
                        description=f'Set default value for {field_path}',
                        field_path=field_path,
                        current_value=current_value,
                        suggested_value=default_value,
                        confidence=0.6,
                        risk_level='low',
                        fix_type='default_substitution',
                    )
                )
                break

        return fixes

    def _build_fix_patterns(self) -> dict[str, Any]:
        """Build patterns for auto-fix detection."""
        return {
            'type_conversions': {
                'string_to_int': r'^\d+$',
                'string_to_float': r'^\d*\.\d+$',
                'string_to_bool': r'^(true|false|yes|no|1|0)$',
            },
            'format_fixes': {
                'url_protocol': r'^[^:]+\.[^:]+',
                'path_separators': r'.*\\.*',
            },
            'common_typos': {
                'localhost': ['127.0.0.1', 'local', 'loalhost'],
                'https': ['http', 'htps'],
                'enabled': ['enable', 'enabed'],
            },
        }

    def _build_help_database(self) -> dict[str, dict[str, Any]]:
        """Build contextual help database."""
        return {
            'api_keys.mistral_key': {
                'title': 'Mistral AI API Key',
                'content': 'API key for accessing Mistral AI language models. Get your key from console.mistral.ai',
                'examples': ['sk-proj-...', 'api_key_...'],
                'related_fields': ['api_keys.openrouter_key', 'llm.default.model'],
                'documentation_links': ['https://docs.mistral.ai/api/'],
                'troubleshooting_steps': [
                    'Ensure the API key is copied completely',
                    'Check if the key has proper permissions',
                    'Verify your account has sufficient credits',
                ],
            },
            'servers.api.port': {
                'title': 'API Server Port',
                'content': 'Port number for the Thoth API server. Must be between 1024-65535.',
                'examples': ['8000', '8080', '3000'],
                'related_fields': ['servers.api.host', 'servers.mcp.port'],
                'troubleshooting_steps': [
                    'Ensure port is not already in use',
                    'Use ports above 1024 for user applications',
                    'Check firewall settings if connecting remotely',
                ],
            },
            'llm.default.temperature': {
                'title': 'LLM Temperature Setting',
                'content': 'Controls randomness in AI responses. 0.0 = deterministic, 1.0 = very creative.',
                'examples': ['0.7', '0.3', '0.9'],
                'related_fields': ['llm.default.model', 'llm.default.max_tokens'],
                'troubleshooting_steps': [
                    'Use 0.0-0.3 for factual tasks',
                    'Use 0.7-1.0 for creative tasks',
                    'Adjust based on response quality',
                ],
            },
        }

    def _generate_default_help(self, field_path: str, error: ValidationIssue) -> str:
        """Generate default help content for unknown fields."""
        return f"Configuration field '{field_path}' has a validation error: {error.message}. Please check the field value and format."

    def _check_performance_improvements(self, config: dict) -> list[ValidationIssue]:
        """Check for performance improvement opportunities."""
        suggestions = []

        # Check chunk sizes
        chunk_size = config.get('rag', {}).get('chunk_size', 1000)
        if chunk_size > 2000:
            suggestions.append(
                ValidationIssue(
                    field_path='rag.chunk_size',
                    issue_type=IssueType.BUSINESS_LOGIC,
                    severity=IssueSeverity.INFO,
                    message='Large chunk size may impact performance',
                    suggestion='Consider reducing chunk size to 1000-1500 for better performance',
                )
            )

        return suggestions

    def _check_security_improvements(self, config: dict) -> list[ValidationIssue]:
        """Check for security improvement opportunities."""
        suggestions = []

        # Check for insecure protocols
        api_host = config.get('servers', {}).get('api', {}).get('host', '')
        if api_host and not api_host.startswith(('https://', 'localhost', '127.0.0.1')):
            suggestions.append(
                ValidationIssue(
                    field_path='servers.api.host',
                    issue_type=IssueType.BUSINESS_LOGIC,
                    severity=IssueSeverity.WARNING,
                    message='Consider using HTTPS for remote connections',
                    suggestion='Use HTTPS protocol for secure remote connections',
                )
            )

        return suggestions

    def _check_usability_improvements(self, config: dict) -> list[ValidationIssue]:
        """Check for usability improvement opportunities."""
        suggestions = []

        # Check for missing API keys
        api_keys = config.get('api_keys', {})
        if not any(api_keys.values()):
            suggestions.append(
                ValidationIssue(
                    field_path='api_keys',
                    issue_type=IssueType.BUSINESS_LOGIC,
                    severity=IssueSeverity.INFO,
                    message='No LLM API keys configured',
                    suggestion='Configure at least one LLM provider API key for full functionality',
                )
            )

        return suggestions


class EnhancedValidator:
    """Enhanced configuration validator with detailed error reporting."""

    def __init__(self):
        """Initialize the enhanced validator."""
        self.auto_fix_engine = AutoFixSuggestions()

    def validate_config(
        self, config_data: dict[str, Any], model_class: type[BaseModel] | None = None
    ) -> ValidationResult:
        """
        Validate configuration data with detailed error reporting and auto-fix.
        """
        errors = []
        warnings = []
        suggestions = []
        auto_fixes = []
        contextual_help = []

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
                    auto_fixes=auto_fixes,
                    contextual_help=contextual_help,
                )

        try:
            # Attempt to create and validate the config
            config_instance = model_class.model_validate(config_data)

            # Perform additional business logic validation
            business_issues = self._perform_business_validation(config_instance)
            warnings.extend(business_issues.get('warnings', []))
            suggestions.extend(business_issues.get('suggestions', []))

        except ValidationError as e:
            # Parse Pydantic validation errors with enhanced information
            parsed_errors = self._parse_pydantic_errors_enhanced(e)
            errors.extend(parsed_errors)
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

        # Create initial validation result
        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            auto_fixes=auto_fixes,
            contextual_help=contextual_help,
        )

        # Generate auto-fixes for detected errors
        if errors:
            auto_fixes = self.auto_fix_engine.detect_fixable_errors(result)
            result.auto_fixes = auto_fixes

        # Generate contextual help for errors
        for error in errors:
            help_content = self.auto_fix_engine.provide_contextual_help(
                error.field_path, error
            )
            contextual_help.append(help_content)
            # Add help and auto-fixes to the error
            error.contextual_help = help_content
            error.auto_fixes = [
                fix for fix in auto_fixes if fix.field_path == error.field_path
            ]

        result.contextual_help = contextual_help

        # Add configuration improvement suggestions
        improvement_suggestions = (
            self.auto_fix_engine.suggest_configuration_improvements(config_data)
        )
        result.suggestions.extend(improvement_suggestions)

        return result

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

    def _parse_pydantic_errors_enhanced(
        self, error: ValidationError
    ) -> list[ValidationIssue]:
        """
        Parse Pydantic validation errors with enhanced auto-fix and contextual help.
        """
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

            # Determine issue type from Pydantic error type
            issue_type = self._map_pydantic_error_type(error_type)

            # Create validation issue
            issue = ValidationIssue(
                field_path=field_path,
                issue_type=issue_type,
                severity=IssueSeverity.ERROR,
                message=enhanced_message,
                suggestion=suggestion,
                current_value=input_value,
            )

            issues.append(issue)
        return issues

    def _map_pydantic_error_type(self, pydantic_error_type: str) -> IssueType:
        """Map Pydantic error types to our issue types."""
        mapping = {
            'missing': IssueType.MISSING_FIELD,
            'string_type': IssueType.TYPE_ERROR,
            'int_type': IssueType.TYPE_ERROR,
            'float_type': IssueType.TYPE_ERROR,
            'bool_type': IssueType.TYPE_ERROR,
            'greater_than_equal': IssueType.RANGE_ERROR,
            'less_than_equal': IssueType.RANGE_ERROR,
            'string_pattern_mismatch': IssueType.FORMAT_ERROR,
            'url_parsing': IssueType.FORMAT_ERROR,
            'path_not_exists': IssueType.VALIDATION_ERROR,
        }
        return mapping.get(pydantic_error_type, IssueType.VALIDATION_ERROR)

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


class PreRestartValidator:
    """
    Validator for configuration changes before service restart.

    This class provides comprehensive validation for configuration changes
    that might require service restarts, with special handling for container
    environments.
    """

    def __init__(self, service_manager: Optional['ServiceManager'] = None):
        """Initialize the pre-restart validator."""
        self.service_manager = service_manager
        self._rollback_points: list[RollbackPoint] = []

    def validate_configuration_for_restart(
        self, new_config: dict[str, Any]
    ) -> 'ValidationResult':
        """
        Validate configuration changes before applying and restarting services.

        Args:
            new_config: New configuration to validate

        Returns:
            ValidationResult with detailed validation information
        """
        # First do standard configuration validation
        validator = EnhancedValidator()
        basic_result = validator.validate_config(new_config)

        if not basic_result.is_valid:
            logger.warning('Configuration failed basic validation')
            return basic_result

        # Additional pre-restart validation
        restart_issues = self._validate_restart_safety(new_config)

        # Combine results
        all_errors = basic_result.errors + restart_issues.get('errors', [])
        all_warnings = basic_result.warnings + restart_issues.get('warnings', [])
        all_suggestions = basic_result.suggestions + restart_issues.get(
            'suggestions', []
        )

        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            suggestions=all_suggestions,
        )

    def analyze_service_impact(
        self, config_changes: 'ConfigChanges'
    ) -> 'ImpactAnalysis':
        """
        Analyze the impact of configuration changes on services.

        Args:
            config_changes: Configuration changes to analyze

        Returns:
            ImpactAnalysis with detailed impact information
        """
        affected_services = set()
        restart_required = False
        estimated_downtime = 0.0
        risk_level = 'low'
        warnings = []

        # Analyze changed paths to determine affected services
        for path in config_changes.changed_paths:
            path_lower = path.lower()

            # Map configuration paths to affected services
            if 'llm' in path_lower:
                affected_services.update(['llm', 'processing', 'article', 'tag'])
                restart_required = True
                estimated_downtime += 5.0  # LLM services take time to restart

            elif 'rag' in path_lower or 'vector' in path_lower:
                affected_services.update(['rag', 'query'])
                restart_required = True
                estimated_downtime += 10.0  # RAG service restart can be slow

            elif 'memory' in path_lower or 'letta' in path_lower:
                affected_services.add('letta')
                restart_required = True
                estimated_downtime += 15.0  # Memory service restart is slow
                risk_level = 'medium'  # Memory restart has higher risk

            elif 'discovery' in path_lower:
                affected_services.add('discovery')
                restart_required = True
                estimated_downtime += 3.0

            elif 'server' in path_lower or 'port' in path_lower:
                affected_services.update(['api_gateway'])
                restart_required = True
                estimated_downtime += 2.0
                risk_level = 'high'  # Server config changes are risky
                warnings.append(
                    'Server configuration changes may cause temporary unavailability'
                )

            elif 'path' in path_lower:
                # Path changes might affect multiple services
                affected_services.update(['note', 'query', 'discovery'])
                # Usually doesn't require restart unless paths are invalid

        # Check for high-risk combinations
        if len(affected_services) > 3:
            risk_level = 'high'
            warnings.append(
                f'Configuration change affects {len(affected_services)} services'
            )

        # Check if we have rollback capability
        rollback_available = True
        if not SERVICE_MANAGER_AVAILABLE:
            rollback_available = False
            warnings.append(
                'Service manager not available - limited rollback capability'
            )

        return ImpactAnalysis(
            affected_services=affected_services,
            restart_required=restart_required,
            estimated_downtime_seconds=estimated_downtime,
            rollback_available=rollback_available,
            risk_level=risk_level,
            warnings=warnings,
        )

    def create_rollback_point(self, description: str = '') -> RollbackPoint:
        """
        Create a rollback point for configuration changes.

        Args:
            description: Description of the rollback point

        Returns:
            RollbackPoint with backup information
        """
        try:
            timestamp = datetime.now()
            rollback_id = f'rollback_{timestamp.strftime("%Y%m%d_%H%M%S")}_{len(self._rollback_points)}'

            # Get current configuration
            current_config = self._get_current_configuration()

            # Create file backup
            backup_path = self._create_config_backup(rollback_id)

            rollback_point = RollbackPoint(
                rollback_id=rollback_id,
                timestamp=timestamp,
                description=description
                or f'Rollback point created at {timestamp.isoformat()}',
                config_snapshot=current_config,
                file_backup_path=backup_path,
            )

            self._rollback_points.append(rollback_point)

            # Keep only last 10 rollback points
            if len(self._rollback_points) > 10:
                old_point = self._rollback_points.pop(0)
                self._cleanup_rollback_point(old_point)

            logger.info(f'Created rollback point: {rollback_id}')
            return rollback_point

        except Exception as e:
            logger.error(f'Failed to create rollback point: {e}')
            raise

    def stage_configuration_changes(self, changes: 'ConfigChanges') -> StagingResult:
        """
        Stage configuration changes for validation before applying.

        Args:
            changes: Configuration changes to stage

        Returns:
            StagingResult with staging operation details
        """
        try:
            # Create staging directory
            staging_dir = Path('/tmp/thoth_config_staging')
            staging_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            staging_file = staging_dir / f'staged_config_{timestamp}.json'

            # Get current config and apply changes
            current_config = self._get_current_configuration()
            staged_config = current_config.copy()

            # Apply changes to staged config
            self._apply_changes_to_config(staged_config, changes.changed_paths)

            # Write staged config to file
            import json

            with open(staging_file, 'w') as f:
                json.dump(staged_config, f, indent=2)

            # Validate staged configuration
            validation_result = self.validate_configuration_for_restart(staged_config)

            return StagingResult(
                success=True,
                staging_path=str(staging_file),
                validation_result=validation_result,
                error_message=None,
            )

        except Exception as e:
            logger.error(f'Failed to stage configuration changes: {e}')
            return StagingResult(success=False, staging_path='', error_message=str(e))

    def generate_change_impact_report(self, changes: 'ConfigChanges') -> 'ImpactReport':
        """
        Generate detailed impact report for configuration changes.

        Args:
            changes: Configuration changes to analyze

        Returns:
            ImpactReport with comprehensive impact analysis
        """
        impact_analysis = self.analyze_service_impact(changes)
        validation_result = self.validate_configuration_for_restart(
            self._get_current_configuration()
        )

        # Generate recommendations
        recommended_actions = []

        if impact_analysis.risk_level == 'high':
            recommended_actions.append('Create rollback point before proceeding')
            recommended_actions.append(
                'Consider applying changes during maintenance window'
            )

        if impact_analysis.restart_required:
            if impact_analysis.estimated_downtime_seconds > 30:
                recommended_actions.append(
                    'Use rolling restart strategy to minimize downtime'
                )
            recommended_actions.append('Verify all services are healthy before restart')

        if len(impact_analysis.affected_services) > 1:
            recommended_actions.append('Restart services in dependency order')

        # Add container-specific recommendations
        try:
            from thoth.docker.container_utils import is_running_in_docker

            if is_running_in_docker():
                recommended_actions.append('Ensure persistent volumes are healthy')
                recommended_actions.append(
                    'Use graceful restart strategy in container environment'
                )
        except ImportError:
            pass

        return ImpactReport(
            timestamp=datetime.now(),
            changes=changes,
            impact_analysis=impact_analysis,
            validation_result=validation_result,
            recommended_actions=recommended_actions,
        )

    def _validate_restart_safety(
        self, config: dict[str, Any]
    ) -> dict[str, list[ValidationIssue]]:
        """Validate that configuration is safe for restart operations."""
        errors = []
        warnings = []
        suggestions = []

        # Check for critical service configuration
        if 'servers' in config:
            servers_config = config['servers']

            # Validate API server configuration
            if 'api' in servers_config:
                api_config = servers_config['api']
                if 'port' in api_config:
                    port = api_config['port']
                    if not isinstance(port, int) or port < 1024 or port > 65535:
                        errors.append(
                            ValidationIssue(
                                field_path='servers.api.port',
                                issue_type=IssueType.RANGE_ERROR,
                                severity=IssueSeverity.ERROR,
                                message='Invalid API server port for restart',
                                suggestion='Use a valid port number between 1024 and 65535',
                            )
                        )

        # Check for required services configuration
        required_sections = ['llm', 'rag']
        for section in required_sections:
            if section not in config:
                warnings.append(
                    ValidationIssue(
                        field_path=section,
                        issue_type=IssueType.MISSING_FIELD,
                        severity=IssueSeverity.WARNING,
                        message=f'Missing {section} configuration section',
                        suggestion=f'Add {section} configuration for full functionality',
                    )
                )

        return {'errors': errors, 'warnings': warnings, 'suggestions': suggestions}

    def _get_current_configuration(self) -> dict[str, Any]:
        """Get current configuration from settings service."""
        try:
            # Try to import and use settings service
            from thoth.services.settings_service import SettingsService

            settings_service = SettingsService(config=None)  # Avoid circular dependency
            return settings_service.load_settings()
        except Exception:
            # Fallback to empty config
            return {}

    def _apply_changes_to_config(
        self, config: dict[str, Any], changed_paths: list[str]
    ) -> None:
        """Apply configuration changes to a config dictionary."""
        # This is a placeholder - in a real implementation, you'd apply specific changes
        # based on the changed_paths and new values
        pass

    def _create_config_backup(self, backup_id: str) -> str:
        """Create a backup of current configuration."""
        try:
            import json
            from pathlib import Path

            backup_dir = Path('/tmp/thoth_config_backups')
            backup_dir.mkdir(exist_ok=True)

            backup_file = backup_dir / f'{backup_id}.json'
            current_config = self._get_current_configuration()

            with open(backup_file, 'w') as f:
                json.dump(current_config, f, indent=2)

            return str(backup_file)

        except Exception as e:
            logger.error(f'Failed to create config backup: {e}')
            return ''

    def _cleanup_rollback_point(self, rollback_point: RollbackPoint) -> None:
        """Clean up a rollback point and its associated files."""
        try:
            backup_path = Path(rollback_point.file_backup_path)
            if backup_path.exists():
                backup_path.unlink()
                logger.debug(f'Cleaned up rollback backup: {backup_path}')
        except Exception as e:
            logger.warning(f'Failed to cleanup rollback point: {e}')


# Convenience functions for easy import
def validate_config(
    config_data: dict[str, Any], model_class: type[BaseModel] | None = None
) -> ValidationResult:
    """Validate configuration with enhanced error reporting and auto-fix suggestions."""
    validator = EnhancedValidator()
    return validator.validate_config(config_data, model_class)


def validate_partial_config(
    field_path: str, field_value: Any, model_class: type[BaseModel] | None = None
) -> ValidationResult:
    """Validate a single field change with auto-fix suggestions."""
    validator = EnhancedValidator()
    partial_data = {field_path: field_value}
    return validator.validate_partial_config(partial_data, field_path, model_class)


def apply_auto_fix(auto_fix: AutoFix) -> dict[str, Any]:
    """Apply an auto-fix suggestion and return the result."""
    auto_fix_engine = AutoFixSuggestions()
    return auto_fix_engine.apply_auto_fix(auto_fix)


def get_contextual_help(field_path: str, error: ValidationIssue) -> ContextualHelp:
    """Get contextual help for a specific field and error."""
    auto_fix_engine = AutoFixSuggestions()
    return auto_fix_engine.provide_contextual_help(field_path, error)


def suggest_configuration_improvements(config: dict[str, Any]) -> list[ValidationIssue]:
    """Get configuration improvement suggestions."""
    auto_fix_engine = AutoFixSuggestions()
    return auto_fix_engine.suggest_configuration_improvements(config)


def validate_configuration_for_restart(
    new_config: dict[str, Any], service_manager: Optional['ServiceManager'] = None
) -> 'ValidationResult':
    """
    Validate configuration for restart operations.

    Args:
        new_config: New configuration to validate
        service_manager: Optional service manager for advanced validation

    Returns:
        ValidationResult with restart-specific validation
    """
    validator = PreRestartValidator(service_manager)
    return validator.validate_configuration_for_restart(new_config)


def analyze_configuration_impact(
    changes: 'ConfigChanges', service_manager: Optional['ServiceManager'] = None
) -> 'ImpactAnalysis':
    """
    Analyze impact of configuration changes.

    Args:
        changes: Configuration changes to analyze
        service_manager: Optional service manager for analysis

    Returns:
        ImpactAnalysis with detailed impact information
    """
    validator = PreRestartValidator(service_manager)
    return validator.analyze_service_impact(changes)

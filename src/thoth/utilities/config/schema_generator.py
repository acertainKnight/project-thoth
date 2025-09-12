"""
Schema generation utilities for creating rich UI metadata from Pydantic models.

This module provides utilities to generate comprehensive schema metadata
that drives dynamic UI generation in the Obsidian plugin.
"""

import inspect
import re
from pathlib import Path
from typing import Any, ClassVar, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo


class UIFieldType:
    """UI field type constants."""

    TEXT = 'text'
    PASSWORD = 'password'
    NUMBER = 'number'
    BOOLEAN = 'boolean'
    SELECT = 'select'
    MULTISELECT = 'multiselect'
    FILE = 'file'
    DIRECTORY = 'directory'
    EMAIL = 'email'
    URL = 'url'


class SchemaGenerator:
    """Generate rich UI metadata from Pydantic models."""

    # Schema version for migration support
    SCHEMA_VERSION = '1.0.0'

    # Field groupings for logical organization
    FIELD_GROUPS: ClassVar[dict[str, dict[str, Any]]] = {
        'API Keys': {
            'title': 'API Configuration',
            'description': 'Configure your AI provider API keys and external service credentials',
            'priority': 1,
            'fields': ['api_keys.*'],
        },
        'Directories': {
            'title': 'Directory Configuration',
            'description': 'Configure file system paths for workspace and data storage',
            'priority': 2,
            'fields': [
                'core.workspace_dir',
                'core.pdf_dir',
                'core.notes_dir',
                'core.prompts_dir',
                'core.output_dir',
            ],
        },
        'LLM Configuration': {
            'title': 'Language Model Settings',
            'description': 'Configure AI model settings and behavior',
            'priority': 3,
            'fields': [
                'core.llm_config.*',
                'citation_llm_config.*',
                'tag_consolidator_llm_config.*',
            ],
        },
        'Server Configuration': {
            'title': 'Server & Network Settings',
            'description': 'Configure API server, MCP server, and network settings',
            'priority': 4,
            'fields': ['features.api_server.*', 'features.mcp.*'],
        },
        'Discovery Settings': {
            'title': 'Research Discovery',
            'description': 'Configure automated research paper discovery and monitoring',
            'priority': 5,
            'fields': ['features.discovery.*'],
        },
        'RAG Configuration': {
            'title': 'Retrieval-Augmented Generation',
            'description': 'Configure vector database and knowledge retrieval settings',
            'priority': 6,
            'fields': ['features.rag.*'],
        },
        'Performance': {
            'title': 'Performance & Monitoring',
            'description': 'Configure performance, caching, and monitoring settings',
            'priority': 7,
            'fields': [
                'performance_config.*',
                'api_gateway_config.*',
                'logging_config.*',
            ],
        },
        'Advanced': {
            'title': 'Advanced Settings',
            'description': 'Advanced configuration options for power users',
            'priority': 8,
            'fields': [
                'features.research_agent.*',
                'citation_config.*',
                'letta_config.*',
            ],
        },
    }

    # Field type mappings based on field names and types
    FIELD_TYPE_MAPPINGS: ClassVar[dict[str, str]] = {
        # Password fields (by name pattern)
        r'.*(?:key|password|secret|token).*': UIFieldType.PASSWORD,
        # Email fields
        r'.*email.*': UIFieldType.EMAIL,
        # URL fields
        r'.*(?:url|host|endpoint).*': UIFieldType.URL,
        # Directory fields
        r'.*(?:dir|directory|path).*': UIFieldType.DIRECTORY,
        # File fields
        r'.*(?:file|filename).*': UIFieldType.FILE,
    }

    # Environment variable mappings for fields
    ENV_VAR_MAPPINGS: ClassVar[dict[str, str]] = {
        'api_keys.mistral_key': 'API_MISTRAL_KEY',
        'api_keys.openrouter_key': 'API_OPENROUTER_KEY',
        'api_keys.openai_key': 'API_OPENAI_KEY',
        'api_keys.anthropic_key': 'API_ANTHROPIC_KEY',
        'api_keys.opencitations_key': 'API_OPENCITATIONS_KEY',
        'api_keys.google_api_key': 'API_GOOGLE_API_KEY',
        'api_keys.semanticscholar_api_key': 'API_SEMANTICSCHOLAR_API_KEY',
        'api_keys.web_search_key': 'API_WEB_SEARCH_KEY',
        'core.workspace_dir': 'WORKSPACE_DIR',
        'core.pdf_dir': 'PDF_DIR',
        'core.notes_dir': 'NOTES_DIR',
        'core.prompts_dir': 'PROMPTS_DIR',
        'core.llm_config.model': 'LLM_MODEL',
        'features.api_server.host': 'ENDPOINT_HOST',
        'features.api_server.port': 'ENDPOINT_PORT',
        'features.mcp.host': 'MCP_HOST',
        'features.mcp.port': 'MCP_PORT',
        'logging_config.level': 'LOG_LEVEL',
    }

    def __init__(self):
        """Initialize the schema generator."""
        pass

    def generate_schema(self, model_class: type[BaseModel]) -> dict[str, Any]:
        """Generate complete UI schema from a Pydantic model."""
        fields_dict: dict[str, Any] = {}
        schema = {
            'version': self.SCHEMA_VERSION,
            'schema': {'fields': fields_dict, 'groups': self.FIELD_GROUPS.copy()},
        }

        # Generate field metadata recursively
        self._process_model_fields(model_class, fields_dict, '')

        return schema

    def _process_model_fields(
        self,
        model_class: type[BaseModel],
        fields_dict: dict[str, Any],
        prefix: str = '',
    ):
        """Process all fields in a Pydantic model recursively."""
        model_fields = model_class.model_fields

        for field_name, field_info in model_fields.items():
            full_field_path = f'{prefix}.{field_name}' if prefix else field_name

            # Check if this is a nested model
            if self._is_pydantic_model(field_info.annotation):
                # Recursively process nested model
                self._process_model_fields(
                    field_info.annotation, fields_dict, full_field_path
                )
            else:
                # Generate field metadata
                field_metadata = self._generate_field_metadata(
                    field_name, field_info, full_field_path
                )
                fields_dict[full_field_path] = field_metadata

    def _is_pydantic_model(self, annotation: Any) -> bool:
        """Check if an annotation is a Pydantic model."""
        try:
            return inspect.isclass(annotation) and issubclass(annotation, BaseModel)
        except TypeError:
            return False

    def _generate_field_metadata(
        self, field_name: str, field_info: FieldInfo, full_path: str
    ) -> dict[str, Any]:
        """Generate comprehensive metadata for a single field."""
        # Get basic type information
        field_type = self._determine_field_type(field_name, field_info, full_path)
        annotation = field_info.annotation

        # Build base metadata
        metadata = {
            'type': field_type,
            'required': field_info.is_required(),
            'title': self._generate_field_title(field_name),
            'description': field_info.description
            or self._generate_field_description(field_name),
        }

        # Add default value if available
        if field_info.default is not None and field_info.default != ...:
            metadata['default'] = field_info.default
        elif hasattr(field_info, 'default_factory') and field_info.default_factory:
            try:
                default = field_info.default_factory()
                metadata['default'] = default
            except Exception:
                pass

        # Add environment variable mapping
        if full_path in self.ENV_VAR_MAPPINGS:
            metadata['env_var'] = self.ENV_VAR_MAPPINGS[full_path]

        # Add validation rules
        validation = self._extract_validation_rules(field_info, annotation)
        if validation:
            metadata['validation'] = validation

        # Add UI hints
        ui_hints = self._generate_ui_hints(field_name, field_type, full_path)
        if ui_hints:
            metadata['ui_hints'] = ui_hints

        # Add group assignment
        group = self._determine_field_group(full_path)
        if group:
            metadata['group'] = group

        return metadata

    def _determine_field_type(
        self, field_name: str, field_info: FieldInfo, full_path: str
    ) -> str:
        """Determine the UI field type based on field name and annotation."""
        annotation = field_info.annotation

        # Check field name patterns first
        field_name_lower = field_name.lower()
        full_path_lower = full_path.lower()

        for pattern, field_type in self.FIELD_TYPE_MAPPINGS.items():
            if re.match(pattern, field_name_lower) or re.match(
                pattern, full_path_lower
            ):
                return field_type

        # Check annotation type
        origin = get_origin(annotation)
        if origin is not None:
            annotation = origin

        # Handle Union types (Optional)
        if hasattr(annotation, '__args__'):
            args = get_args(field_info.annotation)
            if len(args) == 2 and type(None) in args:
                # This is Optional[T], get the non-None type
                annotation = next(arg for arg in args if arg is not type(None))

        # Map Python types to UI types
        if isinstance(annotation, bool):
            return UIFieldType.BOOLEAN
        elif isinstance(annotation, (int | float)):
            return UIFieldType.NUMBER
        elif isinstance(annotation, str):
            return UIFieldType.TEXT
        elif isinstance(annotation, Path):
            if 'dir' in field_name_lower:
                return UIFieldType.DIRECTORY
            else:
                return UIFieldType.FILE
        elif hasattr(annotation, '__origin__') and isinstance(
            annotation.__origin__, list
        ):
            return UIFieldType.MULTISELECT

        return UIFieldType.TEXT

    def _extract_validation_rules(
        self, field_info: FieldInfo, annotation: Any
    ) -> dict[str, Any] | None:
        """Extract validation rules from field constraints."""
        validation = {}

        # Handle constraints from field_info
        constraints = getattr(field_info, 'constraints', []) or []

        for constraint in constraints:
            if hasattr(constraint, 'ge'):  # greater than or equal
                validation['min'] = constraint.ge
            elif hasattr(constraint, 'gt'):  # greater than
                validation['min'] = constraint.gt + (
                    0.01 if isinstance(constraint.gt, float) else 1
                )
            elif hasattr(constraint, 'le'):  # less than or equal
                validation['max'] = constraint.le
            elif hasattr(constraint, 'lt'):  # less than
                validation['max'] = constraint.lt - (
                    0.01 if isinstance(constraint.lt, float) else 1
                )
            elif hasattr(constraint, 'pattern'):  # regex pattern
                validation['pattern'] = constraint.pattern
                validation['message'] = f'Must match pattern: {constraint.pattern}'

        # Add specific validation messages based on field type
        origin = get_origin(annotation)
        if origin is not None:
            annotation = origin

        if isinstance(annotation, int):
            validation['type'] = 'integer'
        elif isinstance(annotation, float):
            validation['type'] = 'number'
        elif isinstance(annotation, str):
            validation['type'] = 'string'

        return validation if validation else None

    def _generate_field_title(self, field_name: str) -> str:
        """Generate a human-readable title from field name."""
        # Convert snake_case to Title Case
        return ' '.join(word.capitalize() for word in field_name.split('_'))

    def _generate_field_description(self, field_name: str) -> str:
        """Generate a description for fields without explicit descriptions."""
        descriptions = {
            'api_key': 'API key for authentication with external service',
            'host': 'Hostname or IP address for the server',
            'port': 'Port number for network connections',
            'enabled': 'Enable or disable this feature',
            'auto_start': 'Automatically start this service when the application starts',
            'temperature': 'Controls randomness in AI model responses (0.0 = deterministic, 1.0 = very random)',
            'max_tokens': 'Maximum number of tokens the AI model can generate',
            'model': 'AI model identifier to use for this feature',
            'timeout': 'Maximum time to wait for operations to complete (in seconds)',
            'interval': 'Time interval between operations (in minutes)',
            'batch_size': 'Number of items to process together in a single batch',
        }

        field_lower = field_name.lower()
        for key, desc in descriptions.items():
            if key in field_lower:
                return desc

        return f'Configuration setting for {self._generate_field_title(field_name)}'

    def _generate_ui_hints(
        self, field_name: str, field_type: str, full_path: str
    ) -> dict[str, Any] | None:
        """Generate UI hints for better user experience."""
        hints: dict[str, Any] = {}

        # Add placeholders based on field type and name
        if field_type == UIFieldType.PASSWORD:
            hints['placeholder'] = 'Enter your API key...'
        elif field_type == UIFieldType.EMAIL:
            hints['placeholder'] = 'user@example.com'
        elif field_type == UIFieldType.URL:
            hints['placeholder'] = 'https://example.com'
        elif field_type == UIFieldType.DIRECTORY:
            hints['placeholder'] = '/path/to/directory'
        elif field_type == UIFieldType.NUMBER:
            if 'port' in field_name.lower():
                hints['placeholder'] = '8000'
                hints['min'] = 1024
                hints['max'] = 65535
            elif 'temperature' in field_name.lower():
                hints['placeholder'] = '0.7'
                hints['min'] = 0.0
                hints['max'] = 1.0
                hints['step'] = 0.1

        # Add suggestions for select fields
        if field_type == UIFieldType.SELECT:
            if 'model' in field_name.lower():
                hints['suggestions'] = [
                    'mistral/mistral-large-latest',
                    'openai/gpt-4o',
                    'openai/gpt-4o-mini',
                    'anthropic/claude-3-sonnet',
                    'anthropic/claude-3-haiku',
                ]
            elif 'level' in field_name.lower() and 'log' in full_path.lower():
                hints['suggestions'] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

        return hints if hints else None

    def _determine_field_group(self, field_path: str) -> str | None:
        """Determine which group a field belongs to."""
        for group_name, group_info in self.FIELD_GROUPS.items():
            field_patterns = group_info.get('fields', [])
            if isinstance(field_patterns, list):
                for pattern in field_patterns:
                    # Convert glob pattern to regex
                    regex_pattern = pattern.replace('*', '.*')
                    if re.match(regex_pattern, field_path):
                        return group_name
        return None


def generate_config_schema(config_class: type[BaseModel]) -> dict[str, Any]:
    """Generate a complete UI schema for a configuration class."""
    generator = SchemaGenerator()
    return generator.generate_schema(config_class)

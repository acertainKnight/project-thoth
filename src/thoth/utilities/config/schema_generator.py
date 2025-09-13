"""
Schema generation utilities for creating rich UI metadata from Pydantic models.

This module provides utilities to generate comprehensive schema metadata
that drives dynamic UI generation in the Obsidian plugin.
"""

import inspect
import re
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, get_args, get_origin

from loguru import logger
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .validation import (
    IssueSeverity,
    IssueType,
    ValidationIssue,
)


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


class FieldDependency(BaseModel):
    """Defines a dependency relationship between fields."""

    field_path: str
    depends_on: str
    condition: str  # 'equals', 'not_equals', 'greater_than', 'less_than', 'contains', 'not_empty'
    value: Any
    action: str  # 'show', 'hide', 'enable', 'disable', 'require', 'optional'


class ConditionalRule(BaseModel):
    """Defines conditional visibility/behavior rules."""

    rule_id: str
    description: str
    condition_expression: str  # e.g., "api_keys.mistral_key != '' AND llm.enabled == true"
    affected_fields: list[str]
    action: str  # 'show', 'hide', 'enable', 'disable', 'require', 'optional'
    priority: int = 0


class FieldRelationship(BaseModel):
    """Defines relationships between configuration fields."""

    relationship_id: str
    relationship_type: str  # 'mutual_exclusive', 'dependent', 'complementary', 'conflicting'
    primary_field: str
    related_fields: list[str]
    description: str
    validation_rules: dict[str, Any] | None = None


class AdvancedCategory(BaseModel):
    """Advanced categorization with nested structure and dependencies."""

    category_id: str
    title: str
    description: str
    parent_category: str | None = None
    subcategories: list[str] = []
    priority: int = 0
    icon: str | None = None
    collapsed_by_default: bool = False
    visibility_condition: str | None = None
    required_for_functionality: list[str] = []  # What functionality this category enables


class ConfigurationUseCase(BaseModel):
    """Represents a specific configuration use case with optimized settings."""

    use_case_id: str
    name: str
    description: str
    recommended_settings: dict[str, Any]
    required_fields: list[str]
    optional_fields: list[str]
    performance_impact: str  # 'low', 'medium', 'high'
    complexity_level: str  # 'beginner', 'intermediate', 'advanced'


class SchemaGenerator:
    """Generate rich UI metadata from Pydantic models with advanced organization."""

    # Schema version for migration support
    SCHEMA_VERSION = '2.0.0'

    def __init__(self):
        """Initialize the schema generator."""
        self.field_dependencies = self._build_field_dependencies()
        self.conditional_rules = self._build_conditional_rules()
        self.field_relationships = self._build_field_relationships()
        self.advanced_categories = self._build_advanced_categories()
        self.configuration_use_cases = self._build_configuration_use_cases()

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
        'Server': {
            'title': 'Server Configuration',
            'description': 'Server and network configuration settings',
            'priority': 4,
            'fields': ['port', 'host'],
        },
        'General': {
            'title': 'General Settings',
            'description': 'General configuration options',
            'priority': 9,
            'fields': ['*'],
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

    def _build_field_dependencies(self) -> list[FieldDependency]:
        """Build field dependency definitions."""
        return [
            # API server dependencies
            FieldDependency(
                field_path='servers.api.host',
                depends_on='features.api_server.enabled',
                condition='equals',
                value=True,
                action='show'
            ),
            FieldDependency(
                field_path='servers.api.port',
                depends_on='features.api_server.enabled',
                condition='equals',
                value=True,
                action='require'
            ),
            # LLM configuration dependencies
            FieldDependency(
                field_path='llm.default.temperature',
                depends_on='api_keys.mistral_key',
                condition='not_empty',
                value=None,
                action='enable'
            ),
            # RAG dependencies
            FieldDependency(
                field_path='rag.embedding_model',
                depends_on='features.rag.enabled',
                condition='equals',
                value=True,
                action='require'
            ),
            # Discovery dependencies
            FieldDependency(
                field_path='discovery.interval_minutes',
                depends_on='features.discovery.enabled',
                condition='equals',
                value=True,
                action='show'
            )
        ]

    def _build_conditional_rules(self) -> list[ConditionalRule]:
        """Build conditional visibility and behavior rules."""
        return [
            ConditionalRule(
                rule_id='api_server_config',
                description='Show API server configuration when enabled',
                condition_expression="features.api_server.enabled == true",
                affected_fields=['servers.api.host', 'servers.api.port', 'servers.api.cors_enabled'],
                action='show',
                priority=1
            ),
            ConditionalRule(
                rule_id='llm_provider_config',
                description='Show LLM configuration when API key is provided',
                condition_expression="api_keys.mistral_key != '' OR api_keys.openrouter_key != ''",
                affected_fields=['llm.default.model', 'llm.default.temperature', 'llm.default.max_tokens'],
                action='enable',
                priority=2
            ),
            ConditionalRule(
                rule_id='advanced_features',
                description='Show advanced features for power users',
                condition_expression="ui_preferences.show_advanced == true",
                affected_fields=['performance_config.*', 'logging_config.level', 'features.research_agent.*'],
                action='show',
                priority=3
            ),
            ConditionalRule(
                rule_id='docker_mode',
                description='Show Docker-specific settings in container environment',
                condition_expression="environment.is_docker == true",
                affected_fields=['docker.volume_mounts', 'docker.network_mode', 'docker.resource_limits'],
                action='show',
                priority=4
            )
        ]

    def _build_field_relationships(self) -> list[FieldRelationship]:
        """Build field relationship definitions."""
        return [
            FieldRelationship(
                relationship_id='api_mcp_ports',
                relationship_type='conflicting',
                primary_field='servers.api.port',
                related_fields=['servers.mcp.port'],
                description='API and MCP servers cannot use the same port',
                validation_rules={'ensure_different_ports': True}
            ),
            FieldRelationship(
                relationship_id='llm_api_keys',
                relationship_type='dependent',
                primary_field='llm.default.model',
                related_fields=['api_keys.mistral_key', 'api_keys.openrouter_key'],
                description='LLM model requires corresponding API key',
                validation_rules={'require_matching_provider': True}
            ),
            FieldRelationship(
                relationship_id='rag_workspace',
                relationship_type='dependent',
                primary_field='rag.vector_db_path',
                related_fields=['paths.workspace'],
                description='Vector database should be within workspace for portability'
            ),
            FieldRelationship(
                relationship_id='discovery_paths',
                relationship_type='complementary',
                primary_field='features.discovery.enabled',
                related_fields=['paths.pdf', 'paths.notes', 'discovery.sources'],
                description='Discovery feature works best with configured paths and sources'
            )
        ]

    def _build_advanced_categories(self) -> list[AdvancedCategory]:
        """Build advanced category structure."""
        return [
            AdvancedCategory(
                category_id='quick_start',
                title='🚀 Quick Start',
                description='Essential settings to get started quickly',
                priority=0,
                icon='🚀',
                collapsed_by_default=False,
                required_for_functionality=['basic_llm', 'file_processing']
            ),
            AdvancedCategory(
                category_id='api_configuration',
                title='🔑 API Configuration',
                description='Configure AI provider API keys and external services',
                priority=1,
                icon='🔑',
                collapsed_by_default=False,
                required_for_functionality=['llm_processing', 'web_search', 'citation_enhancement']
            ),
            AdvancedCategory(
                category_id='workspace_setup',
                title='📁 Workspace Setup',
                description='Configure directories and file organization',
                priority=2,
                icon='📁',
                collapsed_by_default=False,
                required_for_functionality=['file_organization', 'pdf_processing', 'note_management']
            ),
            AdvancedCategory(
                category_id='ai_models',
                title='🤖 AI Models',
                description='Configure language models and AI behavior',
                priority=3,
                icon='🤖',
                collapsed_by_default=False,
                visibility_condition="api_keys.mistral_key != '' OR api_keys.openrouter_key != ''",
                required_for_functionality=['text_analysis', 'content_generation', 'research_assistance']
            ),
            AdvancedCategory(
                category_id='advanced_features',
                title='⚙️ Advanced Features',
                description='Advanced configuration for power users',
                priority=4,
                icon='⚙️',
                collapsed_by_default=True,
                visibility_condition="ui_preferences.show_advanced == true"
            ),
            AdvancedCategory(
                category_id='performance',
                title='🚀 Performance',
                description='Performance and monitoring settings',
                parent_category='advanced_features',
                priority=5,
                icon='📊',
                collapsed_by_default=True
            ),
            AdvancedCategory(
                category_id='development',
                title='🛠️ Development',
                description='Development and debugging settings',
                parent_category='advanced_features',
                priority=6,
                icon='🛠️',
                collapsed_by_default=True,
                visibility_condition="environment.is_development == true"
            )
        ]

    def _build_configuration_use_cases(self) -> list[ConfigurationUseCase]:
        """Build configuration use cases for guided setup."""
        return [
            ConfigurationUseCase(
                use_case_id='researcher_basic',
                name='Basic Research Assistant',
                description='Simple setup for research paper analysis and note-taking',
                recommended_settings={
                    'api_keys.mistral_key': '',
                    'paths.workspace': './research',
                    'paths.pdf': './research/papers',
                    'paths.notes': './research/notes',
                    'llm.default.model': 'mistral/mistral-large-latest',
                    'llm.default.temperature': 0.3,
                    'features.discovery.enabled': True,
                    'features.api_server.enabled': False
                },
                required_fields=['api_keys.mistral_key', 'paths.workspace'],
                optional_fields=['features.discovery.enabled'],
                performance_impact='low',
                complexity_level='beginner'
            ),
            ConfigurationUseCase(
                use_case_id='power_user',
                name='Power User Setup',
                description='Full-featured setup with all services enabled',
                recommended_settings={
                    'api_keys.mistral_key': '',
                    'api_keys.openrouter_key': '',
                    'features.api_server.enabled': True,
                    'features.mcp.enabled': True,
                    'features.rag.enabled': True,
                    'features.discovery.enabled': True,
                    'performance_config.cache_enabled': True,
                    'monitoring.health_checks': True
                },
                required_fields=['api_keys.mistral_key', 'paths.workspace'],
                optional_fields=['api_keys.openrouter_key', 'monitoring.health_checks'],
                performance_impact='high',
                complexity_level='advanced'
            ),
            ConfigurationUseCase(
                use_case_id='team_server',
                name='Team Server',
                description='Multi-user server setup for team collaboration',
                recommended_settings={
                    'features.api_server.enabled': True,
                    'servers.api.host': '0.0.0.0',
                    'servers.api.port': 8000,
                    'servers.api.cors_enabled': True,
                    'features.rag.enabled': True,
                    'monitoring.health_checks': True,
                    'performance_config.cache_enabled': True
                },
                required_fields=['servers.api.port', 'api_keys.mistral_key'],
                optional_fields=['servers.api.cors_enabled', 'monitoring.health_checks'],
                performance_impact='high',
                complexity_level='intermediate'
            )
        ]

    def generate_schema(self, model_class: type[BaseModel]) -> dict[str, Any]:
        """Generate complete UI schema from a Pydantic model with advanced organization."""
        fields_dict: dict[str, Any] = {}
        validation_rules: dict[str, Any] = {}

        # Generate field metadata recursively
        self._process_model_fields(model_class, fields_dict, validation_rules, '')

        # Organize field groups for UI
        field_groups = {}
        for group_name, group_info in self.FIELD_GROUPS.items():
            field_groups[group_name] = {
                'title': group_info['title'],
                'description': group_info['description'],
                'order': group_info['priority'],
            }

        schema = {
            'schema_version': '2.0.0',
            'fields': fields_dict,
            'field_groups': field_groups,
            'validation_rules': validation_rules,
            'generated_at': datetime.now().isoformat(),
            # Advanced organization features
            'field_dependencies': [dep.dict() for dep in self.field_dependencies],
            'conditional_rules': [rule.dict() for rule in self.conditional_rules],
            'field_relationships': [rel.dict() for rel in self.field_relationships],
            'advanced_categories': [cat.dict() for cat in self.advanced_categories],
            'configuration_use_cases': [case.dict() for case in self.configuration_use_cases],
            'ui_metadata': {
                'supports_conditional_visibility': True,
                'supports_auto_fix': True,
                'supports_guided_setup': True,
                'supports_advanced_organization': True
            }
        }

        return schema

    def evaluate_field_visibility(self, field_name: str, current_config: dict[str, Any]) -> bool:
        """Evaluate whether a field should be visible based on dependencies and conditions."""
        # Check field dependencies
        for dependency in self.field_dependencies:
            if dependency.field_path == field_name:
                depends_value = self._get_config_value(current_config, dependency.depends_on)

                if dependency.condition == 'equals':
                    if depends_value != dependency.value:
                        return dependency.action != 'show'
                elif dependency.condition == 'not_equals':
                    if depends_value == dependency.value:
                        return dependency.action != 'show'
                elif dependency.condition == 'not_empty':
                    if not depends_value:
                        return dependency.action != 'show'

        # Check conditional rules
        for rule in self.conditional_rules:
            if field_name in rule.affected_fields:
                condition_met = self._evaluate_condition_expression(rule.condition_expression, current_config)
                if rule.action == 'show':
                    return condition_met
                elif rule.action == 'hide':
                    return not condition_met

        return True  # Default to visible

    def get_smart_defaults(self, field_name: str, current_config: dict[str, Any]) -> Any:
        """Get smart default values based on other settings."""
        # API server defaults
        if field_name == 'servers.api.port':
            # Use different default if MCP port is already set
            mcp_port = self._get_config_value(current_config, 'servers.mcp.port')
            if mcp_port == 8000:
                return 8001
            return 8000

        # LLM model defaults based on API key
        if field_name == 'llm.default.model':
            if self._get_config_value(current_config, 'api_keys.mistral_key'):
                return 'mistral/mistral-large-latest'
            elif self._get_config_value(current_config, 'api_keys.openrouter_key'):
                return 'openai/gpt-4o'
            return 'mistral/mistral-large-latest'

        # Temperature defaults based on use case
        if field_name == 'llm.default.temperature':
            model = self._get_config_value(current_config, 'llm.default.model', '')
            if 'research' in model.lower() or 'analysis' in model.lower():
                return 0.3  # More deterministic for research
            return 0.7  # Balanced default

        return None

    def suggest_optimal_configuration(self, use_case: ConfigurationUseCase) -> dict[str, Any]:
        """Suggest optimal configuration for a specific use case."""
        config = use_case.recommended_settings.copy()

        # Apply smart defaults and optimizations
        for field_name in use_case.required_fields + use_case.optional_fields:
            if field_name not in config:
                smart_default = self.get_smart_defaults(field_name, config)
                if smart_default is not None:
                    config[field_name] = smart_default

        # Add metadata
        config['_use_case'] = {
            'id': use_case.use_case_id,
            'name': use_case.name,
            'applied_at': datetime.now().isoformat(),
            'complexity_level': use_case.complexity_level
        }

        return config

    def get_configuration_wizard_steps(self, use_case_id: str) -> list[dict[str, Any]]:
        """Get wizard steps for guided configuration setup."""
        use_case = next((uc for uc in self.configuration_use_cases if uc.use_case_id == use_case_id), None)
        if not use_case:
            return []

        steps = []

        # Step 1: Use case selection and overview
        steps.append({
            'step_id': 'overview',
            'title': f'Setup: {use_case.name}',
            'description': use_case.description,
            'step_type': 'info',
            'fields': [],
            'validation_required': False
        })

        # Step 2: Required fields
        if use_case.required_fields:
            steps.append({
                'step_id': 'required_fields',
                'title': 'Required Configuration',
                'description': 'These settings are required for basic functionality',
                'step_type': 'form',
                'fields': use_case.required_fields,
                'validation_required': True
            })

        # Step 3: Optional fields (grouped by category)
        optional_by_category = self._group_fields_by_category(use_case.optional_fields)
        for category, fields in optional_by_category.items():
            steps.append({
                'step_id': f'optional_{category.lower().replace(" ", "_")}',
                'title': f'Optional: {category}',
                'description': f'Additional {category.lower()} settings',
                'step_type': 'form',
                'fields': fields,
                'validation_required': False
            })

        # Step 4: Review and confirmation
        steps.append({
            'step_id': 'review',
            'title': 'Review Configuration',
            'description': 'Review your configuration before applying',
            'step_type': 'review',
            'fields': use_case.required_fields + use_case.optional_fields,
            'validation_required': True
        })

        return steps

    def _evaluate_condition_expression(self, expression: str, config: dict[str, Any]) -> bool:
        """Evaluate a conditional expression against current configuration."""
        try:
            # Simple expression parser for basic conditions
            # In a production system, you might want to use a proper expression parser

            # Replace field references with actual values
            expression_with_values = expression

            # Find field references (format: field.path)
            import re
            field_refs = re.findall(r'[\w.]+(?=\s*[!=<>])', expression)

            for field_ref in field_refs:
                if '.' in field_ref:  # Skip operators like 'true', 'false'
                    field_value = self._get_config_value(config, field_ref)

                    # Convert to string representation for expression
                    if isinstance(field_value, str):
                        value_repr = f"'{field_value}'"
                    elif field_value is None:
                        value_repr = "''"
                    else:
                        value_repr = str(field_value).lower()

                    expression_with_values = expression_with_values.replace(field_ref, value_repr)

            # Evaluate the expression
            # Note: In production, use a safe expression evaluator
            result = eval(expression_with_values)
            return bool(result)

        except Exception as e:
            logger.warning(f'Failed to evaluate condition expression "{expression}": {e}')
            return True  # Default to showing field if evaluation fails

    def _get_config_value(self, config: dict[str, Any], field_path: str, default: Any = None) -> Any:
        """Get a nested configuration value using dot notation."""
        keys = field_path.split('.')
        current = config

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def _group_fields_by_category(self, fields: list[str]) -> dict[str, list[str]]:
        """Group fields by their categories."""
        grouped = {}

        for field in fields:
            category = self._get_field_group(field.split('.')[-1])
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(field)

        return grouped

    def validate_field_relationships(self, config: dict[str, Any]) -> list[ValidationIssue]:
        """Validate field relationships and detect conflicts."""
        issues = []

        for relationship in self.field_relationships:
            primary_value = self._get_config_value(config, relationship.primary_field)

            if relationship.relationship_type == 'conflicting':
                # Check for conflicts
                for related_field in relationship.related_fields:
                    related_value = self._get_config_value(config, related_field)

                    if primary_value and related_value and primary_value == related_value:
                        issues.append(ValidationIssue(
                            field_path=relationship.primary_field,
                            issue_type=IssueType.BUSINESS_LOGIC,
                            severity=IssueSeverity.ERROR,
                            message=f'Conflict with {related_field}: {relationship.description}',
                            suggestion=f'Choose a different value for {relationship.primary_field} or {related_field}'
                        ))

            elif relationship.relationship_type == 'dependent':
                # Check dependencies
                if primary_value:
                    for related_field in relationship.related_fields:
                        related_value = self._get_config_value(config, related_field)
                        if not related_value:
                            issues.append(ValidationIssue(
                                field_path=related_field,
                                issue_type=IssueType.BUSINESS_LOGIC,
                                severity=IssueSeverity.WARNING,
                                message=f'Required for {relationship.primary_field}: {relationship.description}',
                                suggestion=f'Configure {related_field} to use {relationship.primary_field}'
                            ))

        return issues

    def _process_model_fields(
        self,
        model_class: type[BaseModel],
        fields_dict: dict[str, Any],
        validation_rules: dict[str, Any],
        prefix: str = '',
    ):
        """Process all fields in a Pydantic model recursively."""
        model_fields = model_class.model_fields

        for field_name, field_info in model_fields.items():
            full_field_path = f'{prefix}.{field_name}' if prefix else field_name

            # Check if this is a nested model
            if self._is_pydantic_model(field_info.annotation):
                # Add the nested field itself
                field_metadata = self._generate_field_metadata(
                    field_name, field_info, full_field_path
                )
                fields_dict[full_field_path] = field_metadata

                # Recursively process nested model
                self._process_model_fields(
                    field_info.annotation,
                    fields_dict,
                    validation_rules,
                    full_field_path,
                )
            else:
                # Generate field metadata
                field_metadata = self._generate_field_metadata(
                    field_name, field_info, full_field_path
                )
                fields_dict[full_field_path] = field_metadata

                # Add validation rules
                validation = self._extract_validation_rules(
                    field_info, field_info.annotation
                )
                if validation:
                    validation_rules[full_field_path] = validation

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
        field_type = self._determine_field_type(
            field_name, field_info.annotation, field_info.description
        )
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
        env_var = self._get_env_var_name(full_path)
        if env_var:
            metadata['env_var'] = env_var

        # Add validation rules
        validation = self._extract_validation_rules(field_info, annotation)
        if validation:
            metadata['validation'] = validation

        # Add UI hints
        ui_hints = self._generate_ui_hints(field_name, field_type, full_path)
        if ui_hints:
            metadata['ui_hints'] = ui_hints

        # Add group assignment
        group = self._get_field_group(field_name)
        metadata['group'] = group

        return metadata

    def _determine_field_type(
        self, field_name: str, field_annotation: Any, description: str | None = None
    ) -> str:
        """Determine the UI field type based on field name and annotation."""
        # Support both old signature (3 params) and new signature (FieldInfo)
        if isinstance(field_annotation, FieldInfo):
            # New signature: field_info, full_path
            field_info = field_annotation
            full_path = description or field_name
            annotation = field_info.annotation
        else:
            # Old signature: field_name, type, description
            annotation = field_annotation
            full_path = field_name

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
            args = get_args(annotation)
            if len(args) == 2 and type(None) in args:
                # This is Optional[T], get the non-None type
                annotation = next(arg for arg in args if arg is not type(None))

        # Map Python types to UI types
        if annotation is bool:
            return UIFieldType.BOOLEAN
        elif annotation in (int, float):
            return UIFieldType.NUMBER
        elif annotation is str:
            return UIFieldType.TEXT
        elif annotation is Path:
            if 'dir' in field_name_lower:
                return UIFieldType.DIRECTORY
            else:
                return UIFieldType.FILE
        elif hasattr(annotation, '__origin__') and annotation.__origin__ is list:
            return UIFieldType.MULTISELECT

        return UIFieldType.TEXT

    def _extract_validation_rules(
        self, field_info: FieldInfo, annotation: Any
    ) -> dict[str, Any] | None:
        """Extract validation rules from field constraints."""
        validation = {}

        # Set required field
        validation['required'] = field_info.is_required()

        # Handle Union types (Optional) to get the actual type
        origin = get_origin(annotation)
        actual_type = annotation

        if origin is not None:
            if hasattr(annotation, '__args__'):
                args = get_args(annotation)
                if len(args) == 2 and type(None) in args:
                    # This is Optional[T], get the non-None type
                    actual_type = next(arg for arg in args if arg is not type(None))
                else:
                    actual_type = origin
            else:
                actual_type = origin

        # Set data type for validation
        if actual_type is int:
            validation['data_type'] = 'int'
        elif actual_type is float:
            validation['data_type'] = 'float'
        elif actual_type is str:
            validation['data_type'] = 'str'
        elif actual_type is bool:
            validation['data_type'] = 'bool'
        else:
            validation['data_type'] = 'str'  # Default fallback

        # Handle constraints from field_info
        if hasattr(field_info, 'constraints') and field_info.constraints:
            for constraint in field_info.constraints:
                if hasattr(constraint, 'ge'):  # greater than or equal
                    validation['min_value'] = constraint.ge
                elif hasattr(constraint, 'gt'):  # greater than
                    validation['min_value'] = constraint.gt + (
                        0.01 if isinstance(constraint.gt, float) else 1
                    )
                elif hasattr(constraint, 'le'):  # less than or equal
                    validation['max_value'] = constraint.le
                elif hasattr(constraint, 'lt'):  # less than
                    validation['max_value'] = constraint.lt - (
                        0.01 if isinstance(constraint.lt, float) else 1
                    )
                elif hasattr(constraint, 'pattern'):  # regex pattern
                    validation['pattern'] = constraint.pattern
                    validation['message'] = f'Must match pattern: {constraint.pattern}'

        # Check for constraints in field_info metadata
        if hasattr(field_info, 'metadata'):
            for metadata_item in field_info.metadata:
                if hasattr(metadata_item, 'ge'):
                    validation['min_value'] = metadata_item.ge
                elif hasattr(metadata_item, 'le'):
                    validation['max_value'] = metadata_item.le
                elif hasattr(metadata_item, 'gt'):
                    validation['min_value'] = metadata_item.gt + (
                        0.01 if isinstance(metadata_item.gt, float) else 1
                    )
                elif hasattr(metadata_item, 'lt'):
                    validation['max_value'] = metadata_item.lt - (
                        0.01 if isinstance(metadata_item.lt, float) else 1
                    )

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

    def _get_field_group(self, field_name: str) -> str:
        """Determine which group a field belongs to based on field name patterns."""
        field_name_lower = field_name.lower()

        # Check for API key fields
        if 'key' in field_name_lower:
            return 'API Keys'

        # Check for directory fields
        if 'dir' in field_name_lower or 'directory' in field_name_lower:
            return 'Directories'

        # Check for server-related fields
        if 'port' in field_name_lower or 'host' in field_name_lower:
            return 'Server'

        # Default group
        return 'General'

    def _get_env_var_name(self, field_path: str) -> str:
        """Generate environment variable name for a field."""
        # Check if there's a specific mapping
        if field_path in self.ENV_VAR_MAPPINGS:
            return self.ENV_VAR_MAPPINGS[field_path]

        # Generate standard format: THOTH_FIELD_NAME
        env_name = field_path.replace('.', '_').upper()
        if not env_name.startswith('THOTH_'):
            env_name = f'THOTH_{env_name}'
        return env_name

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
    """Generate a complete UI schema for a configuration class with advanced features."""
    generator = SchemaGenerator()
    return generator.generate_schema(config_class)


def evaluate_field_visibility(field_name: str, current_config: dict[str, Any], schema: dict[str, Any]) -> bool:
    """Evaluate field visibility based on schema dependencies."""
    generator = SchemaGenerator()
    return generator.evaluate_field_visibility(field_name, current_config)


def get_configuration_use_cases() -> list[ConfigurationUseCase]:
    """Get available configuration use cases."""
    generator = SchemaGenerator()
    return generator.configuration_use_cases


def get_wizard_steps_for_use_case(use_case_id: str) -> list[dict[str, Any]]:
    """Get configuration wizard steps for a specific use case."""
    generator = SchemaGenerator()
    return generator.get_configuration_wizard_steps(use_case_id)


def validate_field_relationships(config: dict[str, Any]) -> list[Any]:
    """Validate field relationships in configuration."""
    generator = SchemaGenerator()
    return generator.validate_field_relationships(config)


def suggest_optimal_configuration(use_case_id: str) -> dict[str, Any]:
    """Suggest optimal configuration for a use case."""
    generator = SchemaGenerator()
    use_case = next((uc for uc in generator.configuration_use_cases if uc.use_case_id == use_case_id), None)
    if use_case:
        return generator.suggest_optimal_configuration(use_case)
    return {}

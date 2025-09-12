"""Tests for SchemaGenerator utility class."""

import pytest
from pydantic import BaseModel, Field

from thoth.utilities.config.schema_generator import SchemaGenerator, UIFieldType


class MockConfigModel(BaseModel):
    """Mock configuration model for testing."""

    api_key: str = Field(..., description='API key for service')
    workspace_dir: str = Field(
        default='~/workspace', description='Workspace directory path'
    )
    port: int = Field(default=8000, description='Server port number')
    debug_mode: bool = Field(default=False, description='Enable debug mode')
    optional_field: str | None = Field(None, description='Optional configuration field')


class TestSchemaGenerator:
    """Test suite for SchemaGenerator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = SchemaGenerator()

    def test_schema_generator_initialization(self):
        """Test SchemaGenerator initializes correctly."""
        assert self.generator is not None
        assert hasattr(self.generator, 'FIELD_GROUPS')
        assert hasattr(self.generator, 'FIELD_TYPE_MAPPINGS')
        assert hasattr(self.generator, 'ENV_VAR_MAPPINGS')

    def test_determine_field_type_string(self):
        """Test field type determination for string fields."""
        # Test regular string field
        field_type = self.generator._determine_field_type(
            'api_key', str, 'API key for service'
        )
        assert field_type == UIFieldType.PASSWORD

        # Test directory path field
        field_type = self.generator._determine_field_type(
            'workspace_dir', str, 'Workspace directory path'
        )
        assert field_type == UIFieldType.DIRECTORY

        # Test port field
        field_type = self.generator._determine_field_type(
            'port', int, 'Server port number'
        )
        assert field_type == UIFieldType.NUMBER

    def test_determine_field_type_boolean(self):
        """Test field type determination for boolean fields."""
        field_type = self.generator._determine_field_type(
            'debug_mode', bool, 'Enable debug mode'
        )
        assert field_type == UIFieldType.BOOLEAN

    def test_determine_field_type_number(self):
        """Test field type determination for number fields."""
        field_type = self.generator._determine_field_type(
            'port', int, 'Server port number'
        )
        assert field_type == UIFieldType.NUMBER

        field_type = self.generator._determine_field_type(
            'timeout', float, 'Request timeout in seconds'
        )
        assert field_type == UIFieldType.NUMBER

    def test_extract_validation_rules(self):
        """Test validation rules extraction from Pydantic field info."""
        from pydantic import Field

        # Test field with constraints
        field_info = Field(ge=1, le=65535, description='Port number')
        rules = self.generator._extract_validation_rules(field_info, int)

        assert rules['required'] is True
        assert rules['min_value'] == 1
        assert rules['max_value'] == 65535
        assert rules['data_type'] == 'int'

    def test_extract_validation_rules_optional(self):
        """Test validation rules for optional fields."""
        from pydantic import Field

        field_info = Field(None, description='Optional field')
        rules = self.generator._extract_validation_rules(field_info, str | None)

        assert rules['required'] is False
        assert rules['data_type'] == 'str'

    def test_get_field_group(self):
        """Test field group determination."""
        # Test API key field
        group = self.generator._get_field_group('api_key')
        assert group == 'API Keys'

        # Test directory field
        group = self.generator._get_field_group('workspace_dir')
        assert group == 'Directories'

        # Test server field
        group = self.generator._get_field_group('port')
        assert group == 'Server'

        # Test unknown field
        group = self.generator._get_field_group('unknown_field')
        assert group == 'General'

    def test_get_env_var_name(self):
        """Test environment variable name mapping."""
        # Test mapped field
        env_var = self.generator._get_env_var_name('api_key')
        assert env_var == 'THOTH_API_KEY'

        # Test unmapped field - should generate standard format
        env_var = self.generator._get_env_var_name('custom_field')
        assert env_var == 'THOTH_CUSTOM_FIELD'

    def test_generate_schema(self):
        """Test complete schema generation."""
        schema = self.generator.generate_schema(MockConfigModel)

        # Test top-level structure
        assert 'schema_version' in schema
        assert 'field_groups' in schema
        assert 'fields' in schema
        assert 'validation_rules' in schema

        # Test field structure
        assert 'api_key' in schema['fields']
        field = schema['fields']['api_key']

        assert field['type'] == UIFieldType.PASSWORD
        assert field['required'] is True
        assert field['description'] == 'API key for service'
        assert field['group'] == 'API Keys'
        assert field['env_var'] == 'THOTH_API_KEY'

        # Test optional field
        assert 'optional_field' in schema['fields']
        optional_field = schema['fields']['optional_field']
        assert optional_field['required'] is False

    def test_generate_schema_with_nested_models(self):
        """Test schema generation with nested Pydantic models."""

        class NestedModel(BaseModel):
            nested_value: str = Field(..., description='Nested field')

        class ParentModel(BaseModel):
            nested: NestedModel = Field(..., description='Nested configuration')
            simple_field: str = Field(..., description='Simple field')

        schema = self.generator.generate_schema(ParentModel)

        # Should handle nested models gracefully
        assert 'nested' in schema['fields']
        assert 'simple_field' in schema['fields']

    def test_field_groups_structure(self):
        """Test field groups structure in generated schema."""
        schema = self.generator.generate_schema(MockConfigModel)

        # Test field groups structure
        groups = schema['field_groups']
        assert isinstance(groups, dict)

        # Should contain groups for our test fields
        group_names = [field['group'] for field in schema['fields'].values()]
        unique_groups = set(group_names)

        for group_name in unique_groups:
            assert group_name in groups
            assert 'title' in groups[group_name]
            assert 'description' in groups[group_name]
            assert 'order' in groups[group_name]

    def test_validation_rules_structure(self):
        """Test validation rules structure in generated schema."""
        schema = self.generator.generate_schema(MockConfigModel)

        # Test validation rules structure
        rules = schema['validation_rules']
        assert isinstance(rules, dict)

        # Test specific field rules
        for field_name, _field_info in schema['fields'].items():
            if field_name in rules:
                field_rules = rules[field_name]
                assert 'required' in field_rules
                assert 'data_type' in field_rules

    def test_schema_versioning(self):
        """Test schema version information."""
        schema = self.generator.generate_schema(MockConfigModel)

        assert schema['schema_version'] == '2.0.0'
        assert 'generated_at' in schema
        assert isinstance(schema['generated_at'], str)


if __name__ == '__main__':
    pytest.main([__file__])

"""
Unit tests for AnalysisSchemaService.

Tests schema loading, validation, dynamic model generation, and hot-reload.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from thoth.services.analysis_schema_service import AnalysisSchemaService
from thoth.utilities.schemas import AnalysisResponse


@pytest.fixture
def temp_schema_file():
    """Create a temporary schema file for testing."""
    schema_content = {
        "version": "1.0",
        "active_preset": "test",
        "presets": {
            "test": {
                "name": "Test Schema",
                "description": "Test schema for unit tests",
                "fields": {
                    "title": {
                        "type": "string",
                        "required": True,
                        "description": "Paper title"
                    },
                    "authors": {
                        "type": "array",
                        "items": "string",
                        "required": True,
                        "description": "Authors"
                    },
                    "summary": {
                        "type": "string",
                        "required": False,
                        "description": "Summary"
                    },
                    "custom_field": {
                        "type": "string",
                        "required": False,
                        "description": "Custom test field"
                    }
                },
                "instructions": "Test extraction instructions"
            },
            "minimal": {
                "name": "Minimal Schema",
                "description": "Minimal test schema",
                "fields": {
                    "title": {"type": "string", "required": True, "description": "Title"},
                    "year": {"type": "integer", "required": False, "description": "Year"}
                },
                "instructions": "Minimal instructions"
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(schema_content, f)
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def mock_config(temp_schema_file):
    """Create a mock config with schema path."""
    config = MagicMock()
    config.analysis_schema_path = temp_schema_file
    config.workspace_dir = temp_schema_file.parent
    return config


class TestAnalysisSchemaServiceInit:
    """Test service initialization."""
    
    def test_init_with_config(self, mock_config):
        """Test initialization with config."""
        service = AnalysisSchemaService(config=mock_config)
        assert service.schema_path == mock_config.analysis_schema_path
        assert service._schema_config is None  # Not loaded until initialize()
    
    def test_init_with_schema_path(self, temp_schema_file):
        """Test initialization with explicit schema path."""
        service = AnalysisSchemaService(schema_path=temp_schema_file)
        assert service.schema_path == temp_schema_file


class TestSchemaLoading:
    """Test schema loading and validation."""
    
    def test_load_valid_schema(self, mock_config, temp_schema_file):
        """Test loading a valid schema file."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        assert service._schema_config is not None
        assert service._schema_config['version'] == '1.0'
        assert service._schema_config['active_preset'] == 'test'
        assert 'test' in service._schema_config['presets']
    
    def test_load_schema_missing_file(self, mock_config):
        """Test loading when schema file doesn't exist."""
        mock_config.analysis_schema_path = Path('/nonexistent/schema.json')
        service = AnalysisSchemaService(config=mock_config)
        
        # Should not raise, just log warning and use default
        service.initialize()
        assert service._schema_config is None
    
    def test_load_schema_invalid_json(self, mock_config):
        """Test loading invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            invalid_path = Path(f.name)
        
        try:
            mock_config.analysis_schema_path = invalid_path
            service = AnalysisSchemaService(config=mock_config)
            service.initialize()
            
            # Should fall back to None
            assert service._schema_config is None
        finally:
            invalid_path.unlink()
    
    def test_validate_schema_missing_required_keys(self, mock_config):
        """Test validation catches missing required keys."""
        invalid_schema = {"version": "1.0"}  # Missing active_preset and presets
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_schema, f)
            invalid_path = Path(f.name)
        
        try:
            mock_config.analysis_schema_path = invalid_path
            service = AnalysisSchemaService(config=mock_config)
            service.initialize()
            
            assert service._schema_config is None  # Should fail validation
        finally:
            invalid_path.unlink()
    
    def test_validate_schema_missing_preset(self, mock_config):
        """Test validation catches when active_preset doesn't exist."""
        invalid_schema = {
            "version": "1.0",
            "active_preset": "nonexistent",
            "presets": {"test": {"fields": {}}}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_schema, f)
            invalid_path = Path(f.name)
        
        try:
            mock_config.analysis_schema_path = invalid_path
            service = AnalysisSchemaService(config=mock_config)
            service.initialize()
            
            assert service._schema_config is None
        finally:
            invalid_path.unlink()


class TestDynamicModelGeneration:
    """Test dynamic Pydantic model generation."""
    
    def test_get_active_model_returns_model(self, mock_config):
        """Test getting active model returns a Pydantic model."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        model = service.get_active_model()
        
        assert model is not None
        assert issubclass(model, BaseModel)
    
    def test_get_active_model_fallback_to_default(self, mock_config):
        """Test fallback to AnalysisResponse when no schema."""
        mock_config.analysis_schema_path = Path('/nonexistent/schema.json')
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        model = service.get_active_model()
        
        assert model == AnalysisResponse
    
    def test_generated_model_has_correct_fields(self, mock_config):
        """Test generated model has fields from schema."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        model = service.get_active_model()
        
        # Check required fields exist
        assert 'title' in model.model_fields
        assert 'authors' in model.model_fields
        assert 'summary' in model.model_fields
        assert 'custom_field' in model.model_fields
    
    def test_generated_model_validates_data(self, mock_config):
        """Test generated model validates data correctly."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        model = service.get_active_model()
        
        # Valid data should work
        instance = model(
            title="Test Paper",
            authors=["Author 1", "Author 2"],
            summary="Test summary",
            custom_field="Custom value"
        )
        assert instance.title == "Test Paper"
        assert len(instance.authors) == 2
        
        # Missing required field should fail
        with pytest.raises(ValidationError):
            model(summary="Missing title and authors")
    
    def test_get_model_for_specific_preset(self, mock_config):
        """Test getting model for specific preset."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        # Get minimal preset model
        model = service.get_model_for_preset('minimal')
        
        assert model is not None
        assert 'title' in model.model_fields
        assert 'year' in model.model_fields
        assert 'custom_field' not in model.model_fields  # Should not have test fields
    
    def test_model_caching(self, mock_config):
        """Test that generated models are cached."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        model1 = service.get_active_model()
        model2 = service.get_active_model()
        
        # Should return same cached model
        assert model1 is model2
    
    def test_cache_cleared_on_reload(self, mock_config):
        """Test cache is cleared when schema reloaded."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        model1 = service.get_active_model()
        
        # Force reload
        service.load_schema(force_reload=True)
        model2 = service.get_active_model()
        
        # Should be different instances after reload
        assert model1 is not model2


class TestSchemaMetadata:
    """Test schema metadata retrieval."""
    
    def test_get_active_preset_name(self, mock_config):
        """Test getting active preset name."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        preset_name = service.get_active_preset_name()
        assert preset_name == 'test'
    
    def test_get_schema_version(self, mock_config):
        """Test getting schema version."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        version = service.get_schema_version()
        assert version == '1.0'
    
    def test_get_preset_instructions(self, mock_config):
        """Test getting preset instructions."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        instructions = service.get_preset_instructions()
        assert instructions == "Test extraction instructions"
    
    def test_get_preset_instructions_for_specific_preset(self, mock_config):
        """Test getting instructions for specific preset."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        instructions = service.get_preset_instructions('minimal')
        assert instructions == "Minimal instructions"
    
    def test_list_available_presets(self, mock_config):
        """Test listing all available presets."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        presets = service.list_available_presets()
        
        assert len(presets) == 2
        assert any(p['name'] == 'Test Schema' for p in presets)
        assert any(p['name'] == 'Minimal Schema' for p in presets)


class TestTypeMapping:
    """Test JSON type to Python type mapping."""
    
    def test_map_string_type(self, mock_config):
        """Test mapping string type."""
        service = AnalysisSchemaService(config=mock_config)
        
        py_type = service._map_json_type_to_python('string', {})
        assert py_type == str
    
    def test_map_integer_type(self, mock_config):
        """Test mapping integer type."""
        service = AnalysisSchemaService(config=mock_config)
        
        py_type = service._map_json_type_to_python('integer', {})
        assert py_type == int
    
    def test_map_array_of_strings(self, mock_config):
        """Test mapping array of strings."""
        service = AnalysisSchemaService(config=mock_config)
        
        py_type = service._map_json_type_to_python('array', {'items': 'string'})
        assert py_type == list[str]
    
    def test_map_array_of_integers(self, mock_config):
        """Test mapping array of integers."""
        service = AnalysisSchemaService(config=mock_config)
        
        py_type = service._map_json_type_to_python('array', {'items': 'integer'})
        assert py_type == list[int]


class TestHealthCheck:
    """Test service health check."""
    
    def test_health_check_healthy(self, mock_config):
        """Test health check when service is healthy."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        health = service.health_check()
        
        assert health['status'] == 'healthy'
        assert health['schema_loaded'] is True
        assert health['schema_version'] == '1.0'
        assert health['active_preset'] == 'test'
    
    def test_health_check_degraded(self, mock_config):
        """Test health check when schema not loaded."""
        mock_config.analysis_schema_path = Path('/nonexistent/schema.json')
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        health = service.health_check()
        
        # Should still be healthy, using default
        assert 'status' in health
        assert health.get('using_default') is True or health.get('schema_loaded') is False


class TestHotReload:
    """Test hot-reload functionality."""
    
    @patch('thoth.config.Config.register_reload_callback')
    def test_registers_reload_callback(self, mock_register, mock_config):
        """Test that service registers for config reload."""
        mock_config.register_reload_callback = mock_register
        
        service = AnalysisSchemaService(config=mock_config)
        
        # Should have registered callback
        mock_register.assert_called_once()
    
    def test_on_config_reload_reloads_schema(self, mock_config, temp_schema_file):
        """Test that config reload triggers schema reload."""
        service = AnalysisSchemaService(config=mock_config)
        service.initialize()
        
        original_version = service.get_schema_version()
        
        # Modify schema file
        schema_content = json.loads(temp_schema_file.read_text())
        schema_content['version'] = '2.0'
        temp_schema_file.write_text(json.dumps(schema_content))
        
        # Trigger reload
        service._on_config_reload()
        
        # Should have new version
        new_version = service.get_schema_version()
        assert new_version == '2.0'
        assert new_version != original_version

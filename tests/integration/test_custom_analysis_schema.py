"""
Integration tests for custom analysis schema pipeline.

Tests that custom schemas work end-to-end through the processing pipeline.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thoth.services.analysis_schema_service import AnalysisSchemaService
from thoth.services.processing_service import ProcessingService


@pytest.fixture
def custom_schema_file():
    """Create a custom schema for testing."""
    schema = {
        "version": "1.0",
        "active_preset": "custom_test",
        "presets": {
            "custom_test": {
                "name": "Custom Test Schema",
                "description": "Schema for integration testing",
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
                        "description": "List of authors"
                    },
                    "year": {
                        "type": "integer",
                        "required": False,
                        "description": "Publication year"
                    },
                    "main_contribution": {
                        "type": "string",
                        "required": False,
                        "description": "The main contribution of this paper"
                    },
                    "technical_approach": {
                        "type": "string",
                        "required": False,
                        "description": "Technical approach used"
                    }
                },
                "instructions": "Focus on extracting the main contribution and technical approach."
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(schema, f)
        temp_path = Path(f.name)
    
    yield temp_path
    
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def mock_config_with_schema(custom_schema_file):
    """Create mock config with custom schema."""
    config = MagicMock()
    config.analysis_schema_path = custom_schema_file
    config.workspace_dir = custom_schema_file.parent
    config.api_keys = MagicMock()
    config.api_keys.mistral_key = "test_key"
    config.llm_config = MagicMock()
    config.llm_config.model = "test/model"
    config.llm_config.max_output_tokens = 8000
    config.llm_config.max_context_length = 8000
    config.llm_config.chunk_size = 4000
    config.llm_config.chunk_overlap = 200
    config.llm_config.model_settings = MagicMock()
    config.llm_config.model_settings.model_dump = MagicMock(return_value={})
    config.prompts_dir = Path(__file__).parent.parent.parent / "templates" / "prompts"
    return config


class TestCustomSchemaIntegration:
    """Integration tests for custom schema functionality."""
    
    def test_schema_service_loads_custom_schema(self, mock_config_with_schema):
        """Test that schema service loads custom schema correctly."""
        service = AnalysisSchemaService(config=mock_config_with_schema)
        service.initialize()
        
        assert service.get_active_preset_name() == 'custom_test'
        assert service.get_schema_version() == '1.0'
        
        model = service.get_active_model()
        assert 'main_contribution' in model.model_fields
        assert 'technical_approach' in model.model_fields
    
    def test_processing_service_uses_custom_schema(self, mock_config_with_schema):
        """Test that processing service integrates with schema service."""
        processing_service = ProcessingService(config=mock_config_with_schema)
        
        # Access analysis_schema_service property
        schema_service = processing_service.analysis_schema_service
        
        assert schema_service is not None
        assert schema_service.get_active_preset_name() == 'custom_test'
    
    def test_custom_instructions_retrieved(self, mock_config_with_schema):
        """Test that custom instructions are retrieved from schema."""
        service = AnalysisSchemaService(config=mock_config_with_schema)
        service.initialize()
        
        instructions = service.get_preset_instructions()
        assert "main contribution" in instructions.lower()
        assert "technical approach" in instructions.lower()
    
    def test_generated_model_has_custom_fields(self, mock_config_with_schema):
        """Test that generated model includes custom fields."""
        service = AnalysisSchemaService(config=mock_config_with_schema)
        service.initialize()
        
        model = service.get_active_model()
        
        # Create instance with custom fields
        instance = model(
            title="Test Paper",
            authors=["Author 1"],
            year=2024,
            main_contribution="Novel algorithm",
            technical_approach="Deep learning"
        )
        
        assert instance.title == "Test Paper"
        assert instance.main_contribution == "Novel algorithm"
        assert instance.technical_approach == "Deep learning"
    
    def test_schema_metadata_for_database(self, mock_config_with_schema):
        """Test that schema metadata is available for storage."""
        service = AnalysisSchemaService(config=mock_config_with_schema)
        service.initialize()
        
        preset_name = service.get_active_preset_name()
        version = service.get_schema_version()
        
        assert preset_name == 'custom_test'
        assert version == '1.0'
        
        # These values should be stored in database with each paper
        assert preset_name != 'default'  # Ensures we're using custom schema
    
    def test_multiple_preset_switching(self, custom_schema_file, mock_config_with_schema):
        """Test switching between presets."""
        # Add another preset to schema
        schema_content = json.loads(custom_schema_file.read_text())
        schema_content['presets']['minimal'] = {
            "name": "Minimal",
            "fields": {
                "title": {"type": "string", "required": True, "description": "Title"},
                "summary": {"type": "string", "required": False, "description": "Summary"}
            },
            "instructions": "Brief extraction"
        }
        custom_schema_file.write_text(json.dumps(schema_content))
        
        service = AnalysisSchemaService(config=mock_config_with_schema)
        service.initialize()
        
        # Get minimal preset model
        minimal_model = service.get_model_for_preset('minimal')
        assert 'title' in minimal_model.model_fields
        assert 'summary' in minimal_model.model_fields
        assert 'main_contribution' not in minimal_model.model_fields
        
        # Get custom_test preset model  
        custom_model = service.get_model_for_preset('custom_test')
        assert 'main_contribution' in custom_model.model_fields
        assert 'technical_approach' in custom_model.model_fields


class TestSchemaFallback:
    """Test fallback behavior when custom schema not available."""
    
    def test_falls_back_to_default_when_file_missing(self):
        """Test that system falls back to default AnalysisResponse."""
        from thoth.utilities.schemas import AnalysisResponse
        
        config = MagicMock()
        config.analysis_schema_path = Path('/nonexistent/schema.json')
        config.workspace_dir = Path('/tmp')
        
        service = AnalysisSchemaService(config=config)
        service.initialize()
        
        model = service.get_active_model()
        
        # Should fallback to default AnalysisResponse
        assert model == AnalysisResponse
    
    def test_preset_name_is_default_on_fallback(self):
        """Test that preset name is 'default' when using fallback."""
        config = MagicMock()
        config.analysis_schema_path = Path('/nonexistent/schema.json')
        config.workspace_dir = Path('/tmp')
        
        service = AnalysisSchemaService(config=config)
        service.initialize()
        
        preset_name = service.get_active_preset_name()
        version = service.get_schema_version()
        
        assert preset_name == 'default'
        assert version == 'default'


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""
    
    def test_works_with_original_analysis_response(self, mock_config_with_schema):
        """Test that custom schemas are compatible with AnalysisResponse."""
        from thoth.utilities.schemas import AnalysisResponse
        
        service = AnalysisSchemaService(config=mock_config_with_schema)
        service.initialize()
        
        custom_model = service.get_active_model()
        
        # Both should have title and authors (core fields)
        assert 'title' in custom_model.model_fields
        assert 'authors' in custom_model.model_fields
        
        assert 'title' in AnalysisResponse.model_fields
        assert 'authors' in AnalysisResponse.model_fields

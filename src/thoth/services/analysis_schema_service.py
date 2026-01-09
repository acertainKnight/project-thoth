"""
Analysis Schema Service for managing customizable document analysis schemas.

This service enables users to customize what information is extracted from
academic papers during document analysis through configuration files.
"""

import json
from pathlib import Path
from typing import Any, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field, ValidationError, create_model

from thoth.services.base import BaseService, ServiceError
from thoth.utilities.schemas import AnalysisResponse


class AnalysisSchemaService(BaseService):
    """
    Service for managing customizable analysis schemas.
    
    Features:
    - Load schema configurations from JSON files
    - Generate dynamic Pydantic models from schemas
    - Support multiple presets (standard, detailed, minimal, custom)
    - Hot-reload schemas on file changes
    - Fallback to default AnalysisResponse if schema invalid
    """
    
    def __init__(self, config=None, schema_path: Path | str | None = None):
        """
        Initialize the AnalysisSchemaService.
        
        Args:
            config: Optional configuration object
            schema_path: Path to schema JSON file (overrides config)
        """
        super().__init__(config)
        
        # Determine schema file path
        if schema_path:
            self.schema_path = Path(schema_path)
        elif hasattr(self.config, 'analysis_schema_path'):
            self.schema_path = Path(self.config.analysis_schema_path)
        else:
            # Default: vault/_thoth/data/analysis_schema.json
            self.schema_path = self.config.workspace_dir / 'data' / 'analysis_schema.json'
        
        # Cache for generated models
        self._model_cache: dict[str, Type[BaseModel]] = {}
        self._schema_config: dict[str, Any] | None = None
        self._schema_version: str | None = None
        
        # Register for config reload if hot-reload enabled
        if self.config and hasattr(self.config, 'register_reload_callback'):
            from thoth.config import Config
            Config.register_reload_callback('analysis_schema_service', self._on_config_reload)
            self.logger.debug('AnalysisSchemaService registered for hot-reload')
    
    def initialize(self) -> None:
        """Initialize the service by loading the schema."""
        try:
            # Copy default template if schema file doesn't exist
            if not self.schema_path.exists():
                self._copy_default_template()
            
            self.load_schema()
            self.logger.info(f'AnalysisSchemaService initialized with schema: {self.schema_path}')
        except Exception as e:
            self.logger.warning(f'Failed to load custom schema, using default: {e}')
            self._schema_config = None
    
    def _copy_default_template(self) -> None:
        """Copy default schema template to vault if it doesn't exist."""
        try:
            # Find template in repository
            import shutil
            from pathlib import Path
            
            # Template should be in templates/analysis_schema.json
            repo_root = Path(__file__).resolve().parents[3]
            template_path = repo_root / 'templates' / 'analysis_schema.json'
            
            if not template_path.exists():
                self.logger.warning(f'Default schema template not found: {template_path}')
                return
            
            # Ensure parent directory exists
            self.schema_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy template
            shutil.copy(template_path, self.schema_path)
            self.logger.success(f'Copied default analysis schema template to {self.schema_path}')
            
        except Exception as e:
            self.logger.warning(f'Failed to copy default schema template: {e}')
    
    def load_schema(self, force_reload: bool = False) -> dict[str, Any]:
        """
        Load schema configuration from file.
        
        Args:
            force_reload: Force reload even if already cached
            
        Returns:
            dict: Schema configuration
            
        Raises:
            ServiceError: If schema file invalid or missing
        """
        if self._schema_config and not force_reload:
            return self._schema_config
        
        if not self.schema_path.exists():
            self.logger.debug(f'Schema file not found: {self.schema_path}')
            raise ServiceError(f'Schema file not found: {self.schema_path}')
        
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema_config = json.load(f)
            
            # Validate schema structure
            self._validate_schema_config(schema_config)
            
            self._schema_config = schema_config
            self._schema_version = schema_config.get('version', '1.0')
            
            # Clear model cache on reload
            if force_reload:
                self._model_cache.clear()
            
            self.logger.success(f'Loaded analysis schema v{self._schema_version} from {self.schema_path}')
            return schema_config
            
        except json.JSONDecodeError as e:
            raise ServiceError(f'Invalid JSON in schema file: {e}') from e
        except Exception as e:
            raise ServiceError(f'Failed to load schema: {e}') from e
    
    def _validate_schema_config(self, config: dict[str, Any]) -> None:
        """
        Validate schema configuration structure.
        
        Args:
            config: Schema configuration to validate
            
        Raises:
            ServiceError: If schema structure is invalid
        """
        # Check required top-level keys
        required_keys = ['version', 'active_preset', 'presets']
        for key in required_keys:
            if key not in config:
                raise ServiceError(f'Schema missing required key: {key}')
        
        # Check that active preset exists
        active_preset = config['active_preset']
        if active_preset not in config['presets']:
            raise ServiceError(f'Active preset "{active_preset}" not found in presets')
        
        # Validate each preset
        for preset_name, preset_config in config['presets'].items():
            if 'fields' not in preset_config:
                raise ServiceError(f'Preset "{preset_name}" missing "fields" key')
            
            # Validate field specifications
            for field_name, field_spec in preset_config['fields'].items():
                if 'type' not in field_spec:
                    raise ServiceError(
                        f'Field "{field_name}" in preset "{preset_name}" missing "type"'
                    )
    
    def get_active_model(self) -> Type[BaseModel]:
        """
        Get the Pydantic model for the currently active preset.
        
        Returns:
            Type[BaseModel]: Dynamic or default AnalysisResponse model
        """
        try:
            # Load schema if not already loaded
            if not self._schema_config:
                self.load_schema()
            
            if not self._schema_config:
                # No custom schema, use default
                self.logger.debug('Using default AnalysisResponse model')
                return AnalysisResponse
            
            active_preset = self._schema_config['active_preset']
            return self.get_model_for_preset(active_preset)
            
        except Exception as e:
            self.logger.warning(f'Error getting active model, using default: {e}')
            return AnalysisResponse
    
    def get_model_for_preset(self, preset_name: str) -> Type[BaseModel]:
        """
        Get or generate Pydantic model for a specific preset.
        
        Args:
            preset_name: Name of the preset (e.g., 'standard', 'detailed')
            
        Returns:
            Type[BaseModel]: Generated Pydantic model
            
        Raises:
            ServiceError: If preset not found or model generation fails
        """
        # Check cache first
        cache_key = f'{self._schema_version}_{preset_name}'
        if cache_key in self._model_cache:
            self.logger.debug(f'Using cached model for preset: {preset_name}')
            return self._model_cache[cache_key]
        
        # Load schema if needed
        if not self._schema_config:
            self.load_schema()
        
        if preset_name not in self._schema_config['presets']:
            raise ServiceError(f'Preset not found: {preset_name}')
        
        preset_config = self._schema_config['presets'][preset_name]
        
        try:
            # Generate dynamic model
            model = self._build_pydantic_model(preset_name, preset_config)
            
            # Cache it
            self._model_cache[cache_key] = model
            
            self.logger.success(f'Generated Pydantic model for preset: {preset_name}')
            return model
            
        except Exception as e:
            raise ServiceError(f'Failed to generate model for preset "{preset_name}": {e}') from e
    
    def _build_pydantic_model(
        self, 
        preset_name: str, 
        preset_config: dict[str, Any]
    ) -> Type[BaseModel]:
        """
        Build a dynamic Pydantic model from preset configuration.
        
        Args:
            preset_name: Name of the preset
            preset_config: Preset configuration with fields
            
        Returns:
            Type[BaseModel]: Generated Pydantic model
        """
        field_definitions = {}
        
        for field_name, field_spec in preset_config['fields'].items():
            # Map JSON type to Python type
            field_type = self._map_json_type_to_python(field_spec['type'], field_spec)
            
            # Check if required
            required = field_spec.get('required', False)
            description = field_spec.get('description', '')
            
            if required:
                field_definitions[field_name] = (
                    field_type,
                    Field(description=description)
                )
            else:
                field_definitions[field_name] = (
                    Optional[field_type],
                    Field(default=None, description=description)
                )
        
        # Create dynamic model with custom name
        model_name = f'DynamicAnalysisResponse_{preset_name.title()}'
        return create_model(
            model_name,
            __base__=BaseModel,
            **field_definitions
        )
    
    def _map_json_type_to_python(
        self, 
        json_type: str, 
        field_spec: dict[str, Any]
    ) -> Type:
        """
        Map JSON schema type to Python type.
        
        Args:
            json_type: JSON type string ('string', 'integer', 'array', etc.)
            field_spec: Full field specification with metadata
            
        Returns:
            Type: Python type for Pydantic field
        """
        type_mapping = {
            'string': str,
            'integer': int,
            'number': float,
            'boolean': bool,
        }
        
        if json_type == 'array':
            # Handle array types
            items_type = field_spec.get('items', 'string')
            if items_type == 'string':
                return list[str]
            elif items_type == 'integer':
                return list[int]
            elif items_type == 'number':
                return list[float]
            else:
                return list[str]  # Default to list of strings
        
        return type_mapping.get(json_type, str)
    
    def get_preset_instructions(self, preset_name: str | None = None) -> str:
        """
        Get custom instructions for a preset.
        
        Args:
            preset_name: Name of preset (uses active if None)
            
        Returns:
            str: Custom instructions for LLM, or empty string
        """
        try:
            if not self._schema_config:
                self.load_schema()
            
            if not self._schema_config:
                return ''
            
            if preset_name is None:
                preset_name = self._schema_config['active_preset']
            
            preset_config = self._schema_config['presets'].get(preset_name, {})
            return preset_config.get('instructions', '')
            
        except Exception as e:
            self.logger.debug(f'Failed to get preset instructions: {e}')
            return ''
    
    def get_active_preset_name(self) -> str:
        """
        Get the name of the currently active preset.
        
        Returns:
            str: Preset name (e.g., 'standard') or 'default'
        """
        try:
            if not self._schema_config:
                self.load_schema()
            
            if self._schema_config:
                return self._schema_config['active_preset']
            
        except Exception:
            pass
        
        return 'default'
    
    def get_schema_version(self) -> str:
        """
        Get the current schema version.
        
        Returns:
            str: Schema version (e.g., '1.0') or 'default'
        """
        if self._schema_version:
            return self._schema_version
        
        try:
            if not self._schema_config:
                self.load_schema()
            
            return self._schema_config.get('version', 'default')
        except Exception:
            return 'default'
    
    def list_available_presets(self) -> list[dict[str, str]]:
        """
        List all available presets with their descriptions.
        
        Returns:
            list: List of preset info dicts with 'name' and 'description'
        """
        try:
            if not self._schema_config:
                self.load_schema()
            
            if not self._schema_config:
                return [{'name': 'default', 'description': 'Default AnalysisResponse schema'}]
            
            presets = []
            for preset_id, config in self._schema_config['presets'].items():
                presets.append({
                    'id': preset_id,
                    'name': config.get('name', preset_id),
                    'description': config.get('description', ''),
                })
            
            return presets
            
        except Exception as e:
            self.logger.warning(f'Failed to list presets: {e}')
            return [{'name': 'default', 'description': 'Default schema'}]
    
    def _on_config_reload(self) -> None:
        """Callback for config hot-reload - reload schema."""
        try:
            self.logger.info('Config reloaded, reloading analysis schema...')
            self.load_schema(force_reload=True)
        except Exception as e:
            self.logger.error(f'Failed to reload schema on config change: {e}')
    
    def health_check(self) -> dict[str, Any]:
        """
        Check health of the schema service.
        
        Returns:
            dict: Health status information
        """
        try:
            schema_exists = self.schema_path.exists()
            
            if schema_exists and not self._schema_config:
                self.load_schema()
            
            return {
                'status': 'healthy',
                'schema_file_exists': schema_exists,
                'schema_loaded': self._schema_config is not None,
                'schema_version': self.get_schema_version(),
                'active_preset': self.get_active_preset_name(),
                'schema_path': str(self.schema_path),
                'cached_models': len(self._model_cache),
            }
        except Exception as e:
            return {
                'status': 'degraded',
                'error': str(e),
                'using_default': True,
            }

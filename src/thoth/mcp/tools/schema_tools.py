"""
MCP tools for managing analysis schemas.

Provides tools for listing, switching, and managing analysis schemas.
"""

import json
from pathlib import Path
from typing import Any

from thoth.mcp.base_tools import MCPTool


class GetSchemaInfoTool(MCPTool):
    """Get information about the current analysis schema."""
    
    name = "get_schema_info"
    description = "Get information about the currently active analysis schema including preset name, version, and available fields"
    
    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs) -> dict[str, Any]:
        """Execute the tool."""
        try:
            # Get schema service
            if not hasattr(self.services, 'processing'):
                return {
                    "success": False,
                    "error": "Processing service not available"
                }
            
            schema_service = self.services.processing.analysis_schema_service
            
            # Get current schema info
            preset_name = schema_service.get_active_preset_name()
            version = schema_service.get_schema_version()
            instructions = schema_service.get_preset_instructions()
            
            # Get model fields
            model = schema_service.get_active_model()
            fields = list(model.model_fields.keys())
            
            return {
                "success": True,
                "preset_name": preset_name,
                "version": version,
                "instructions": instructions,
                "field_count": len(fields),
                "fields": fields,
                "schema_path": str(schema_service.schema_path)
            }
            
        except Exception as e:
            return self.handle_error(e, "getting schema info")


class ListSchemaPresetsTool(MCPTool):
    """List all available analysis schema presets."""
    
    name = "list_schema_presets"
    description = "List all available analysis schema presets with their descriptions"
    
    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs) -> dict[str, Any]:
        """Execute the tool."""
        try:
            # Get schema service
            if not hasattr(self.services, 'processing'):
                return {
                    "success": False,
                    "error": "Processing service not available"
                }
            
            schema_service = self.services.processing.analysis_schema_service
            
            # Get available presets
            presets = schema_service.list_available_presets()
            active_preset = schema_service.get_active_preset_name()
            
            return {
                "success": True,
                "active_preset": active_preset,
                "presets": presets,
                "count": len(presets)
            }
            
        except Exception as e:
            return self.handle_error(e, "listing schema presets")


class SetSchemaPresetTool(MCPTool):
    """Switch to a different analysis schema preset."""
    
    name = "set_schema_preset"
    description = "Switch the active analysis schema preset (e.g., 'standard', 'detailed', 'minimal')"
    
    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            "type": "object",
            "properties": {
                "preset": {
                    "type": "string",
                    "description": "The preset name to activate (e.g., 'standard', 'detailed', 'minimal', 'custom')"
                }
            },
            "required": ["preset"]
        }
    
    async def execute(self, preset: str, **kwargs) -> dict[str, Any]:
        """Execute the tool."""
        try:
            # Get schema service
            if not hasattr(self.services, 'processing'):
                return {
                    "success": False,
                    "error": "Processing service not available"
                }
            
            schema_service = self.services.processing.analysis_schema_service
            
            # Load current schema
            schema_config = schema_service.load_schema()
            
            # Check if preset exists
            if preset not in schema_config['presets']:
                available = list(schema_config['presets'].keys())
                return {
                    "success": False,
                    "error": f"Preset '{preset}' not found",
                    "available_presets": available
                }
            
            # Update active preset
            schema_config['active_preset'] = preset
            
            # Save back to file
            schema_path = schema_service.schema_path
            with open(schema_path, 'w', encoding='utf-8') as f:
                json.dump(schema_config, f, indent=2, ensure_ascii=False)
            
            # Reload schema
            schema_service.load_schema(force_reload=True)
            
            # Get new preset info
            new_model = schema_service.get_active_model()
            field_count = len(new_model.model_fields)
            instructions = schema_service.get_preset_instructions()
            
            return {
                "success": True,
                "message": f"Switched to '{preset}' preset",
                "preset": preset,
                "field_count": field_count,
                "instructions": instructions
            }
            
        except Exception as e:
            return self.handle_error(e, f"setting schema preset to '{preset}'")


class GetPresetDetailsTool(MCPTool):
    """Get detailed information about a specific preset."""
    
    name = "get_preset_details"
    description = "Get detailed information about a specific analysis schema preset including all fields and their specifications"
    
    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            "type": "object",
            "properties": {
                "preset": {
                    "type": "string",
                    "description": "The preset name to get details for (e.g., 'standard', 'detailed', 'minimal')"
                }
            },
            "required": ["preset"]
        }
    
    async def execute(self, preset: str, **kwargs) -> dict[str, Any]:
        """Execute the tool."""
        try:
            # Get schema service
            if not hasattr(self.services, 'processing'):
                return {
                    "success": False,
                    "error": "Processing service not available"
                }
            
            schema_service = self.services.processing.analysis_schema_service
            
            # Load schema
            schema_config = schema_service.load_schema()
            
            # Check if preset exists
            if preset not in schema_config['presets']:
                available = list(schema_config['presets'].keys())
                return {
                    "success": False,
                    "error": f"Preset '{preset}' not found",
                    "available_presets": available
                }
            
            preset_config = schema_config['presets'][preset]
            
            # Extract field details
            fields = []
            for field_name, field_spec in preset_config['fields'].items():
                fields.append({
                    "name": field_name,
                    "type": field_spec.get('type', 'string'),
                    "required": field_spec.get('required', False),
                    "description": field_spec.get('description', ''),
                    "items": field_spec.get('items') if field_spec.get('type') == 'array' else None
                })
            
            return {
                "success": True,
                "preset": preset,
                "name": preset_config.get('name', preset),
                "description": preset_config.get('description', ''),
                "instructions": preset_config.get('instructions', ''),
                "field_count": len(fields),
                "fields": fields
            }
            
        except Exception as e:
            return self.handle_error(e, f"getting details for preset '{preset}'")


class ValidateSchemaFileTool(MCPTool):
    """Validate the analysis schema configuration file."""
    
    name = "validate_schema_file"
    description = "Validate the analysis schema configuration file for syntax and structure errors"
    
    @property
    def input_schema(self) -> dict[str, Any]:
        """Define tool input schema."""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs) -> dict[str, Any]:
        """Execute the tool."""
        try:
            # Get schema service
            if not hasattr(self.services, 'processing'):
                return {
                    "success": False,
                    "error": "Processing service not available"
                }
            
            schema_service = self.services.processing.analysis_schema_service
            schema_path = schema_service.schema_path
            
            # Check file exists
            if not schema_path.exists():
                return {
                    "success": False,
                    "error": f"Schema file not found: {schema_path}",
                    "schema_path": str(schema_path)
                }
            
            # Try to load and validate
            try:
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_config = json.load(f)
                
                # Validate structure
                schema_service._validate_schema_config(schema_config)
                
                # Get validation details
                version = schema_config.get('version', 'unknown')
                active_preset = schema_config.get('active_preset', 'unknown')
                preset_count = len(schema_config.get('presets', {}))
                
                return {
                    "success": True,
                    "valid": True,
                    "message": "Schema file is valid",
                    "schema_path": str(schema_path),
                    "version": version,
                    "active_preset": active_preset,
                    "preset_count": preset_count
                }
                
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "valid": False,
                    "error": f"Invalid JSON: {str(e)}",
                    "schema_path": str(schema_path)
                }
            except Exception as e:
                return {
                    "success": False,
                    "valid": False,
                    "error": f"Validation failed: {str(e)}",
                    "schema_path": str(schema_path)
                }
            
        except Exception as e:
            return self.handle_error(e, "validating schema file")


# Register tools
TOOLS = [
    GetSchemaInfoTool,
    ListSchemaPresetsTool,
    SetSchemaPresetTool,
    GetPresetDetailsTool,
    ValidateSchemaFileTool,
]

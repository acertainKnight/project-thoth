"""
Schema management API endpoints.

Provides REST API for managing analysis schemas.
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from thoth.services.service_manager import ServiceManager

router = APIRouter(prefix="/schema", tags=["schema"])

# Initialize service manager (will be set by app factory)
_service_manager: ServiceManager | None = None


def set_dependencies(service_manager: ServiceManager) -> None:
    """Set service manager dependency."""
    global _service_manager
    _service_manager = service_manager


class SetPresetRequest(BaseModel):
    """Request model for setting active preset."""
    preset: str = Field(..., description="Name of the preset to activate")


class PresetInfo(BaseModel):
    """Information about a schema preset."""
    id: str = Field(..., description="Preset identifier")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Preset description")


class SchemaInfoResponse(BaseModel):
    """Response model for schema information."""
    preset_name: str
    version: str
    instructions: str
    field_count: int
    fields: list[str]
    schema_path: str


class PresetsListResponse(BaseModel):
    """Response model for listing presets."""
    active_preset: str
    presets: list[PresetInfo]
    count: int


class PresetDetailsResponse(BaseModel):
    """Response model for preset details."""
    preset: str
    name: str
    description: str
    instructions: str
    field_count: int
    fields: list[dict[str, Any]]


class ValidationResponse(BaseModel):
    """Response model for schema validation."""
    valid: bool
    message: str
    schema_path: str
    version: str | None = None
    active_preset: str | None = None
    preset_count: int | None = None


@router.get("/info", response_model=SchemaInfoResponse)
async def get_schema_info():
    """
    Get information about the currently active analysis schema.
    
    Returns current preset name, version, custom instructions, field list,
    and path to schema file.
    """
    if not _service_manager or not hasattr(_service_manager, 'processing'):
        raise HTTPException(status_code=503, detail="Processing service not available")
    
    try:
        schema_service = _service_manager.processing.analysis_schema_service
        
        preset_name = schema_service.get_active_preset_name()
        version = schema_service.get_schema_version()
        instructions = schema_service.get_preset_instructions()
        
        model = schema_service.get_active_model()
        fields = list(model.model_fields.keys())
        
        return SchemaInfoResponse(
            preset_name=preset_name,
            version=version,
            instructions=instructions,
            field_count=len(fields),
            fields=fields,
            schema_path=str(schema_service.schema_path)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get schema info: {str(e)}")


@router.get("/presets", response_model=PresetsListResponse)
async def list_presets():
    """
    List all available analysis schema presets.
    
    Returns list of presets with their names and descriptions, plus the
    currently active preset.
    """
    if not _service_manager or not hasattr(_service_manager, 'processing'):
        raise HTTPException(status_code=503, detail="Processing service not available")
    
    try:
        schema_service = _service_manager.processing.analysis_schema_service
        
        presets = schema_service.list_available_presets()
        active_preset = schema_service.get_active_preset_name()
        
        return PresetsListResponse(
            active_preset=active_preset,
            presets=[PresetInfo(**p) for p in presets],
            count=len(presets)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list presets: {str(e)}")


@router.post("/preset")
async def set_preset(request: SetPresetRequest):
    """
    Switch to a different analysis schema preset.
    
    Changes the active preset in the schema configuration file and reloads
    the schema service. All subsequent PDF processing will use the new preset.
    """
    if not _service_manager or not hasattr(_service_manager, 'processing'):
        raise HTTPException(status_code=503, detail="Processing service not available")
    
    try:
        schema_service = _service_manager.processing.analysis_schema_service
        
        # Load current schema
        schema_config = schema_service.load_schema()
        
        # Check if preset exists
        if request.preset not in schema_config['presets']:
            available = list(schema_config['presets'].keys())
            raise HTTPException(
                status_code=400,
                detail=f"Preset '{request.preset}' not found. Available: {available}"
            )
        
        # Update active preset
        schema_config['active_preset'] = request.preset
        
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
            "message": f"Switched to '{request.preset}' preset",
            "preset": request.preset,
            "field_count": field_count,
            "instructions": instructions
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set preset: {str(e)}")


@router.get("/presets/{preset}", response_model=PresetDetailsResponse)
async def get_preset_details(preset: str):
    """
    Get detailed information about a specific preset.
    
    Returns all fields in the preset with their types, requirements, and
    descriptions.
    """
    if not _service_manager or not hasattr(_service_manager, 'processing'):
        raise HTTPException(status_code=503, detail="Processing service not available")
    
    try:
        schema_service = _service_manager.processing.analysis_schema_service
        
        # Load schema
        schema_config = schema_service.load_schema()
        
        # Check if preset exists
        if preset not in schema_config['presets']:
            available = list(schema_config['presets'].keys())
            raise HTTPException(
                status_code=404,
                detail=f"Preset '{preset}' not found. Available: {available}"
            )
        
        preset_config = schema_config['presets'][preset]
        
        # Extract field details
        fields = []
        for field_name, field_spec in preset_config['fields'].items():
            field_info = {
                "name": field_name,
                "type": field_spec.get('type', 'string'),
                "required": field_spec.get('required', False),
                "description": field_spec.get('description', '')
            }
            if field_spec.get('type') == 'array':
                field_info['items'] = field_spec.get('items')
            fields.append(field_info)
        
        return PresetDetailsResponse(
            preset=preset,
            name=preset_config.get('name', preset),
            description=preset_config.get('description', ''),
            instructions=preset_config.get('instructions', ''),
            field_count=len(fields),
            fields=fields
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get preset details: {str(e)}")


@router.get("/validate", response_model=ValidationResponse)
async def validate_schema():
    """
    Validate the analysis schema configuration file.
    
    Checks for JSON syntax errors, required keys, and structural validity.
    """
    if not _service_manager or not hasattr(_service_manager, 'processing'):
        raise HTTPException(status_code=503, detail="Processing service not available")
    
    try:
        schema_service = _service_manager.processing.analysis_schema_service
        schema_path = schema_service.schema_path
        
        # Check file exists
        if not schema_path.exists():
            return ValidationResponse(
                valid=False,
                message=f"Schema file not found: {schema_path}",
                schema_path=str(schema_path)
            )
        
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
            
            return ValidationResponse(
                valid=True,
                message="Schema file is valid",
                schema_path=str(schema_path),
                version=version,
                active_preset=active_preset,
                preset_count=preset_count
            )
            
        except json.JSONDecodeError as e:
            return ValidationResponse(
                valid=False,
                message=f"Invalid JSON: {str(e)}",
                schema_path=str(schema_path)
            )
        except Exception as e:
            return ValidationResponse(
                valid=False,
                message=f"Validation failed: {str(e)}",
                schema_path=str(schema_path)
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate schema: {str(e)}")

"""Configuration management endpoints."""

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field

from thoth.utilities.config import ThothConfig, get_config
from thoth.utilities.config.schema_generator import SchemaGenerator
from thoth.utilities.config.validation import EnhancedValidator

router = APIRouter()


class PartialValidationRequest(BaseModel):
    """Request model for partial field validation."""

    field_path: str = Field(
        ..., description="Dot-notation path to the field (e.g., 'api_keys.mistral_key')"
    )
    field_value: Any = Field(..., description='New value for the field')


class SchemaVersionResponse(BaseModel):
    """Response model for schema version information."""

    current_version: str
    supported_versions: list[str]
    migration_available: bool
    migration_required: bool


@router.get('/export')
def export_config_for_obsidian():
    """Export current configuration in Obsidian plugin format."""
    try:
        config = get_config()
        obsidian_config = config.export_for_obsidian()

        return JSONResponse(
            {
                'status': 'success',
                'config': obsidian_config,
                'config_version': '1.0.0',
                'exported_at': time.time(),
            }
        )

    except Exception as e:
        logger.error(f'Failed to export config for Obsidian: {e}')
        raise HTTPException(
            status_code=500, detail=f'Config export failed: {e!s}'
        ) from e


@router.post('/import')
async def import_config_from_obsidian(obsidian_config: dict[str, Any]):
    """Import configuration from Obsidian plugin format and validate it."""
    try:
        from thoth.utilities.config import ThothConfig

        # Import configuration from Obsidian format
        imported_config = ThothConfig.import_from_obsidian(obsidian_config)

        # Validate the imported configuration
        validation_result = imported_config.validate_for_obsidian()

        if validation_result['errors']:
            return JSONResponse(
                {
                    'status': 'validation_failed',
                    'errors': validation_result['errors'],
                    'warnings': validation_result['warnings'],
                    'message': 'Configuration validation failed',
                },
                status_code=400,
            )

        # If validation passed, sync to environment
        synced_vars = imported_config.sync_to_environment()

        return JSONResponse(
            {
                'status': 'success',
                'message': 'Configuration imported and validated successfully',
                'synced_environment_vars': list(synced_vars.keys()),
                'warnings': validation_result['warnings'],
                'imported_at': time.time(),
            }
        )

    except Exception as e:
        logger.error(f'Failed to import config from Obsidian: {e}')
        raise HTTPException(
            status_code=500, detail=f'Config import failed: {e!s}'
        ) from e


@router.post('/validate')
async def validate_config(config_data: dict[str, Any] | None = None):
    """Validate configuration data with enhanced error messages and suggestions."""
    try:
        validator = EnhancedValidator()

        if config_data:
            # Validate provided configuration data
            validation_result = validator.validate_config(config_data)
            source = 'provided'
        else:
            # Validate current configuration
            current_config = get_config()
            config_dict = current_config.model_dump()
            validation_result = validator.validate_config(config_dict)
            source = 'current'

        return JSONResponse(
            {
                'status': 'valid' if validation_result.is_valid else 'invalid',
                'source': source,
                'is_valid': validation_result.is_valid,
                'errors': [error.model_dump() for error in validation_result.errors],
                'warnings': [
                    warning.model_dump() for warning in validation_result.warnings
                ],
                'suggestions': [
                    suggestion.model_dump()
                    for suggestion in validation_result.suggestions
                ],
                'error_count': len(validation_result.errors),
                'warning_count': len(validation_result.warnings),
                'suggestion_count': len(validation_result.suggestions),
                'validated_at': time.time(),
            }
        )

    except Exception as e:
        logger.error(f'Config validation failed: {e}')
        raise HTTPException(
            status_code=500, detail=f'Config validation failed: {e!s}'
        ) from e


@router.post('/validate-partial')
async def validate_partial_config(request: PartialValidationRequest):
    """Validate a single configuration field for real-time UI feedback."""
    try:
        validator = EnhancedValidator()

        # Create partial config data for validation
        partial_data = {request.field_path: request.field_value}

        validation_result = validator.validate_partial_config(
            partial_data, request.field_path
        )

        return JSONResponse(
            {
                'status': 'valid' if validation_result.is_valid else 'invalid',
                'field_path': request.field_path,
                'field_value': request.field_value,
                'is_valid': validation_result.is_valid,
                'errors': [error.model_dump() for error in validation_result.errors],
                'warnings': [
                    warning.model_dump() for warning in validation_result.warnings
                ],
                'suggestions': [
                    suggestion.model_dump()
                    for suggestion in validation_result.suggestions
                ],
                'validated_at': time.time(),
            }
        )

    except Exception as e:
        logger.error(f'Partial config validation failed: {e}')
        raise HTTPException(
            status_code=500, detail=f'Partial validation failed: {e!s}'
        ) from e


@router.get('/schema')
def get_config_schema():
    """
    Get enhanced configuration schema with rich UI metadata for dynamic form generation.
    """
    try:
        # Generate comprehensive schema using SchemaGenerator
        generator = SchemaGenerator()
        schema = generator.generate_schema(ThothConfig)

        # Add API metadata
        schema['generated_at'] = time.time()
        schema['supports_partial_validation'] = True
        schema['migration_support'] = True
        schema['api_version'] = '2.0.0'

        return JSONResponse({'status': 'success', **schema})

    except Exception as e:
        logger.error(f'Failed to generate config schema: {e}')
        raise HTTPException(
            status_code=500, detail=f'Schema generation failed: {e!s}'
        ) from e


@router.get('/schema/version')
def get_schema_version():
    """Get current schema version and migration information."""
    try:
        version_info = SchemaVersionResponse(
            current_version='2.0.0',
            supported_versions=['1.0.0', '2.0.0'],
            migration_available=True,
            migration_required=False,
        )

        return JSONResponse(
            {
                'status': 'success',
                **version_info.model_dump(),
                'checked_at': time.time(),
            }
        )

    except Exception as e:
        logger.error(f'Failed to get schema version: {e}')
        raise HTTPException(
            status_code=500, detail=f'Schema version check failed: {e!s}'
        ) from e


@router.post('/schema/migrate')
async def migrate_schema(from_version: str, to_version: str = '2.0.0'):
    """Migrate configuration schema from one version to another."""
    try:
        # For now, just return migration info
        # In the future, this would contain actual migration logic
        migration_info = {
            'from_version': from_version,
            'to_version': to_version,
            'migration_steps': [
                'Update field names to new schema',
                'Validate new configuration structure',
                'Apply default values for new fields',
            ],
            'backup_recommended': True,
            'estimated_duration': '< 1 minute',
        }

        return JSONResponse(
            {
                'status': 'success',
                'migration_info': migration_info,
                'migration_id': f'migration_{from_version}_to_{to_version}_{int(time.time())}',
                'initiated_at': time.time(),
            }
        )

    except Exception as e:
        logger.error(f'Schema migration failed: {e}')
        raise HTTPException(
            status_code=500, detail=f'Schema migration failed: {e!s}'
        ) from e


@router.get('/defaults')
def get_config_defaults():
    """Get default configuration values."""
    defaults = {
        'api_keys': {
            'mistralKey': '',
            'openrouterKey': '',
            'opencitationsKey': '',
            'googleApiKey': '',
            'semanticScholarKey': '',
            'webSearchKey': '',
        },
        'directories': {
            'workspaceDir': '~/thoth-workspace',
            'pdfDir': '~/thoth-workspace/pdfs',
            'notesDir': '~/thoth-workspace/notes',
        },
        'server': {
            'host': 'localhost',
            'port': 8000,
        },
        'llm_settings': {
            'defaultModel': 'mistral/mistral-large-latest',
            'researchModel': 'mistral/mistral-large-latest',
        },
        'discovery': {
            'autoStartScheduler': False,
            'maxArticlesPerSource': 50,
        },
    }

    return JSONResponse(
        {
            'status': 'success',
            'defaults': defaults,
            'version': '1.0.0',
        }
    )

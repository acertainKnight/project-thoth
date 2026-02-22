"""Configuration management endpoints."""

import os
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field

from thoth.auth.context import UserContext
from thoth.auth.dependencies import get_user_context
from thoth.config import Settings, config

# TODO: Re-implement SchemaGenerator and EnhancedValidator for new config system
# from thoth.utilities.config.schema_generator import SchemaGenerator
# from thoth.utilities.config.validation import EnhancedValidator

router = APIRouter()


def _settings_to_obsidian(settings: Settings) -> dict[str, Any]:
    """Convert Settings model to Obsidian-friendly dict."""
    return settings.model_dump(by_alias=True)


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
def export_config_for_obsidian(user_context: UserContext = Depends(get_user_context)):  # noqa: B008
    """Export current configuration in Obsidian plugin format.

    In multi-user mode, exports the requesting user's settings from their vault.
    In single-user mode, exports the global config.
    """
    try:
        effective_settings = (
            user_context.settings
            if user_context.settings is not None
            else config.get_user_settings(user_context.username)
        )
        obsidian_config = _settings_to_obsidian(effective_settings)

        return JSONResponse(
            {
                'status': 'success',
                'config': obsidian_config,
                'config_version': '1.0.0',
                'exported_at': time.time(),
                'user_specific': user_context.settings is not None,
            }
        )

    except Exception as e:
        logger.error(f'Failed to export config for Obsidian: {e}')
        raise HTTPException(
            status_code=500, detail=f'Config export failed: {e!s}'
        ) from e


@router.post('/import')
async def import_config_from_obsidian(
    obsidian_config: dict[str, Any],
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
):
    """Import configuration from Obsidian plugin format and save to user's vault.

    In multi-user mode, writes to the user's vault settings.json.
    In single-user mode, writes to the global vault settings.json.
    """
    try:
        # Determine which settings file to write to
        multi_user = os.getenv('THOTH_MULTI_USER', 'false').lower() == 'true'

        if multi_user and config.vaults_root:
            # Write to user's vault
            settings_file = (
                config.vaults_root
                / user_context.username
                / 'thoth'
                / '_thoth'
                / 'settings.json'
            )
        else:
            # Write to global vault
            settings_file = (
                user_context.vault_path / 'thoth' / '_thoth' / 'settings.json'
            )

        # Ensure directory exists
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        # Write the config
        import json

        validated = Settings.model_validate(obsidian_config)
        settings_file.write_text(
            json.dumps(validated.model_dump(by_alias=True), indent=2),
            encoding='utf-8',
        )

        # Invalidate cache if multi-user
        if multi_user and config.user_config_manager:
            config.user_config_manager.invalidate_cache(user_context.username)

        logger.info(
            f"Config imported for user '{user_context.username}' to {settings_file}"
        )

        return JSONResponse(
            {
                'status': 'success',
                'message': 'Configuration imported successfully',
                'imported_at': time.time(),
                'settings_file': str(settings_file),
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
    raise HTTPException(
        status_code=501,
        detail='Validation endpoint temporarily disabled - needs migration to new config system',
    )
    try:
        # validator = EnhancedValidator()

        if config_data:
            # Validate provided configuration data
            validation_result = validator.validate_config(config_data)  # noqa: F821
            source = 'provided'
        else:
            # Validate current configuration
            config  # noqa: B018
            config_dict = current_config.model_dump()  # noqa: F821
            validation_result = validator.validate_config(config_dict)  # noqa: F821
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
    raise HTTPException(
        status_code=501,
        detail='Partial validation endpoint temporarily disabled - needs migration to new config system',
    )
    try:
        # validator = EnhancedValidator()

        # Create partial config data for validation
        partial_data = {request.field_path: request.field_value}

        validation_result = validator.validate_partial_config(  # noqa: F821
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
    raise HTTPException(
        status_code=501,
        detail='Schema generation endpoint temporarily disabled - needs migration to new config system',
    )
    try:
        # Generate comprehensive schema using SchemaGenerator
        # generator = SchemaGenerator()
        # schema = generator.generate_schema(Config)

        # Add API metadata
        schema['generated_at'] = time.time()  # noqa: F821
        schema['supports_partial_validation'] = True  # noqa: F821
        schema['migration_support'] = True  # noqa: F821
        schema['api_version'] = '2.0.0'  # noqa: F821

        return JSONResponse({'status': 'success', **schema})  # noqa: F821

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

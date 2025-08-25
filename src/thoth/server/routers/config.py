"""Configuration management endpoints."""

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from thoth.utilities.config import get_config

router = APIRouter()


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
    """Validate configuration data (current or provided) for Obsidian integration."""
    try:
        from thoth.utilities.config import ThothConfig

        if config_data:
            # Validate provided configuration
            test_config = ThothConfig.import_from_obsidian(config_data)
            validation_result = test_config.validate_for_obsidian()
            source = 'provided'
        else:
            # Validate current configuration
            current_config = get_config()
            validation_result = current_config.validate_for_obsidian()
            source = 'current'

        is_valid = len(validation_result['errors']) == 0

        return JSONResponse(
            {
                'status': 'valid' if is_valid else 'invalid',
                'source': source,
                'is_valid': is_valid,
                'errors': validation_result['errors'],
                'warnings': validation_result['warnings'],
                'error_count': len(validation_result['errors']),
                'warning_count': len(validation_result['warnings']),
                'validated_at': time.time(),
            }
        )

    except Exception as e:
        logger.error(f'Config validation failed: {e}')
        raise HTTPException(
            status_code=500, detail=f'Config validation failed: {e!s}'
        ) from e


@router.get('/schema')
def get_config_schema():
    """Get the configuration schema for the Obsidian plugin."""
    schema = {
        'version': '1.0.0',
        'sections': {
            'api_keys': {
                'title': 'API Keys',
                'description': 'External service API keys',
                'fields': {
                    'mistralKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                    'openrouterKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                    'opencitationsKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                    'googleApiKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                    'semanticScholarKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                    'webSearchKey': {
                        'type': 'string',
                        'required': False,
                        'sensitive': True,
                    },
                },
            },
            'directories': {
                'title': 'Directory Configuration',
                'description': 'File system paths',
                'fields': {
                    'workspaceDir': {
                        'type': 'string',
                        'required': True,
                        'description': 'Main Thoth workspace directory',
                    },
                    'pdfDir': {
                        'type': 'string',
                        'required': False,
                        'description': 'Directory for downloaded PDFs',
                    },
                    'notesDir': {
                        'type': 'string',
                        'required': False,
                        'description': 'Directory for generated notes',
                    },
                },
            },
            'server': {
                'title': 'Server Configuration',
                'description': 'API server settings',
                'fields': {
                    'host': {
                        'type': 'string',
                        'default': 'localhost',
                        'description': 'Server host address',
                    },
                    'port': {
                        'type': 'integer',
                        'default': 8000,
                        'description': 'Server port number',
                    },
                },
            },
            'llm_settings': {
                'title': 'LLM Configuration',
                'description': 'Language model settings',
                'fields': {
                    'defaultModel': {
                        'type': 'string',
                        'default': 'mistral/mistral-large-latest',
                        'description': 'Default language model',
                    },
                    'researchModel': {
                        'type': 'string',
                        'default': 'mistral/mistral-large-latest',
                        'description': 'Model for research tasks',
                    },
                },
            },
            'discovery': {
                'title': 'Discovery Settings',
                'description': 'Paper discovery configuration',
                'fields': {
                    'autoStartScheduler': {
                        'type': 'boolean',
                        'default': False,
                        'description': 'Auto-start discovery scheduler',
                    },
                    'maxArticlesPerSource': {
                        'type': 'integer',
                        'default': 50,
                        'description': 'Maximum articles per discovery source',
                    },
                },
            },
        },
    }

    return JSONResponse(schema)


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

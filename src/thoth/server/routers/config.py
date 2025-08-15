"""
Configuration management endpoints.
"""

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from thoth.utilities.config import get_config, ThothConfig

router = APIRouter(prefix="/config", tags=["configuration"])


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
        logger.error(f'Config import failed: {e}')
        raise HTTPException(
            status_code=500, detail=f'Config import failed: {e!s}'
        ) from e


@router.post('/validate')
async def validate_config_for_obsidian(config_data: dict[str, Any]):
    """Validate configuration for Obsidian plugin compatibility."""
    try:
        # Determine source of configuration
        source = 'obsidian'
        if 'api_keys' in config_data:
            source = 'thoth'

        # Create or import config based on source
        if source == 'thoth':
            config = ThothConfig(**config_data)
        else:
            config = ThothConfig.import_from_obsidian(config_data)

        # Validate configuration
        validation_result = config.validate_for_obsidian()
        is_valid = len(validation_result['errors']) == 0

        return JSONResponse(
            {
                'status': 'success' if is_valid else 'validation_failed',
                'message': 'Configuration is valid' if is_valid else 'Configuration has errors',
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
                    'workspaceDirectory': {'type': 'path', 'required': True},
                    'obsidianDirectory': {'type': 'path', 'required': True},
                    'pdfDirectory': {'type': 'path', 'required': False},
                    'promptsDirectory': {'type': 'path', 'required': False},
                },
            },
            'connection': {
                'title': 'Connection Settings',
                'description': 'Server connection configuration',
                'fields': {
                    'remoteMode': {
                        'type': 'boolean',
                        'required': False,
                        'default': False,
                    },
                    'endpointHost': {
                        'type': 'string',
                        'required': False,
                        'default': '127.0.0.1',
                    },
                    'endpointPort': {
                        'type': 'integer',
                        'required': False,
                        'default': 8000,
                        'min': 1024,
                        'max': 65535,
                    },
                    'remoteEndpointUrl': {'type': 'string', 'required': False},
                },
            },
            'llm': {
                'title': 'Language Model Configuration',
                'description': 'LLM settings and parameters',
                'fields': {
                    'primaryLlmModel': {
                        'type': 'string',
                        'required': False,
                        'default': 'anthropic/claude-3-sonnet',
                    },
                    'llmTemperature': {
                        'type': 'number',
                        'required': False,
                        'default': 0.7,
                        'min': 0.0,
                        'max': 1.0,
                    },
                    'llmMaxOutputTokens': {
                        'type': 'integer',
                        'required': False,
                        'default': 4096,
                        'min': 1,
                    },
                },
            },
            'agent': {
                'title': 'Agent Behavior',
                'description': 'Research agent configuration',
                'fields': {
                    'agentMaxToolCalls': {
                        'type': 'integer',
                        'required': False,
                        'default': 20,
                        'min': 1,
                    },
                    'agentTimeoutSeconds': {
                        'type': 'integer',
                        'required': False,
                        'default': 300,
                        'min': 30,
                    },
                    'researchAgentMemoryEnabled': {
                        'type': 'boolean',
                        'required': False,
                        'default': True,
                    },
                },
            },
            'discovery': {
                'title': 'Discovery System',
                'description': 'Research discovery configuration',
                'fields': {
                    'discoveryDefaultMaxArticles': {
                        'type': 'integer',
                        'required': False,
                        'default': 50,
                        'min': 1,
                    },
                    'discoveryDefaultIntervalMinutes': {
                        'type': 'integer',
                        'required': False,
                        'default': 60,
                        'min': 15,
                    },
                    'discoveryRateLimitDelay': {
                        'type': 'number',
                        'required': False,
                        'default': 1.0,
                        'min': 0.1,
                    },
                },
            },
        },
    }

    return JSONResponse(schema)


@router.get('/defaults')
def get_config_defaults():
    """Get default configuration values."""
    try:
        # Create a default config instance
        default_config = ThothConfig()

        return JSONResponse(
            {
                'status': 'success',
                'defaults': {
                    'api_keys': {
                        'opencitations_key': 'default',
                    },
                    'llm': {
                        'model': default_config.llm_config.model,
                        'temperature': default_config.llm_config.model_settings.temperature,
                        'max_output_tokens': default_config.llm_config.max_output_tokens,
                        'chunk_size': default_config.llm_config.chunk_size,
                        'chunk_overlap': default_config.llm_config.chunk_overlap,
                    },
                    'paths': {
                        'base_dir': str(default_config.base_dir),
                        'data_dir': str(default_config.data_dir),
                        'pdf_dir': str(default_config.pdf_dir),
                        'notes_dir': str(default_config.notes_dir),
                    },
                    'server': {
                        'api_host': default_config.endpoint_config.host,
                        'api_port': default_config.endpoint_config.port,
                        'mcp_host': default_config.mcp_config.host,
                        'mcp_port': default_config.mcp_config.port,
                    },
                    'features': {
                        'auto_process_pdfs': default_config.monitor_config.enabled,
                        'enable_discovery': default_config.discovery_config.auto_start_scheduler,
                        'enable_memory': default_config.research_agent_config.enable_memory,
                    },
                },
                'generated_at': time.time(),
            }
        )

    except Exception as e:
        logger.error(f'Failed to get config defaults: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get defaults: {e!s}'
        ) from e
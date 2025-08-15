"""
Agent management endpoints.
"""

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from thoth.utilities.config import get_config

router = APIRouter(prefix="/agent", tags=["agent"])


class ConfigUpdateRequest(BaseModel):
    """Request model for configuration updates."""
    config: dict[str, Any]
    restart_services: bool = False


class AgentRestartRequest(BaseModel):
    """Request model for agent restart."""
    reset_memory: bool = False
    reload_config: bool = True


@router.get('/status')
def get_agent_status(research_agent=None):
    """Get the current status of the research agent."""
    if research_agent is None:
        return JSONResponse(
            {
                'status': 'not_initialized',
                'message': 'Research agent has not been initialized',
                'available': False,
            }
        )

    try:
        return JSONResponse(
            {
                'status': 'running',
                'message': 'Research agent is active',
                'available': True,
                'capabilities': {
                    'memory_enabled': hasattr(research_agent, 'memory_enabled')
                    and research_agent.memory_enabled,
                    'tool_count': len(research_agent.tools) if hasattr(research_agent, 'tools') else 0,
                },
            }
        )
    except Exception as e:
        logger.error(f'Error checking agent status: {e}')
        return JSONResponse(
            {
                'status': 'error',
                'message': f'Error checking agent status: {e!s}',
                'available': False,
            },
            status_code=500,
        )


@router.get('/tools')
def get_agent_tools(research_agent=None):
    """Get available tools for the research agent."""
    if research_agent is None:
        raise HTTPException(
            status_code=503, detail='Research agent not initialized'
        )

    try:
        tools = []
        if hasattr(research_agent, 'tools'):
            for tool in research_agent.tools:
                tools.append(
                    {
                        'name': getattr(tool, 'name', str(tool)),
                        'description': getattr(tool, 'description', ''),
                    }
                )

        return JSONResponse({'status': 'success', 'tools': tools})
    except Exception as e:
        logger.error(f'Error getting agent tools: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get tools: {e!s}'
        ) from e


@router.get('/config')
def get_agent_config():
    """Get current agent configuration."""
    try:
        # Get current config from the global config or reload it
        config = get_config()

        # Extract agent-specific configuration
        agent_config = {
            'llm': {
                'model': config.research_agent_llm_config.model,
                'temperature': config.research_agent_llm_config.model_settings.temperature,
                'max_output_tokens': config.research_agent_llm_config.max_output_tokens,
                'max_context_length': config.research_agent_llm_config.max_context_length,
            },
            'memory': {
                'enabled': config.research_agent_config.enable_memory,
            },
            'behavior': {
                'auto_start': config.research_agent_config.auto_start,
                'default_queries': config.research_agent_config.default_queries,
            },
        }

        return JSONResponse(
            {
                'status': 'success',
                'config': agent_config,
                'config_path': str(config.config_file)
                if hasattr(config, 'config_file')
                else None,
            }
        )
    except Exception as e:
        logger.error(f'Error getting agent config: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get config: {e!s}'
        ) from e


@router.post('/config')
async def update_agent_config(request: ConfigUpdateRequest):
    """Update agent configuration."""
    try:
        config = get_config()

        # Update configuration based on provided values
        if 'llm' in request.config:
            llm_config = request.config['llm']
            if 'model' in llm_config:
                config.research_agent_llm_config.model = llm_config['model']
            if 'temperature' in llm_config:
                config.research_agent_llm_config.model_settings.temperature = llm_config[
                    'temperature'
                ]
            if 'max_output_tokens' in llm_config:
                config.research_agent_llm_config.max_output_tokens = llm_config[
                    'max_output_tokens'
                ]

        if 'memory' in request.config:
            memory_config = request.config['memory']
            if 'enabled' in memory_config:
                config.research_agent_config.enable_memory = memory_config['enabled']

        # Save configuration if possible
        if hasattr(config, 'save'):
            config.save()

        response = {
            'status': 'success',
            'message': 'Configuration updated successfully',
            'requires_restart': request.restart_services,
        }

        if request.restart_services:
            response['message'] += ' (restart required for changes to take effect)'

        return JSONResponse(response)

    except Exception as e:
        logger.error(f'Error updating agent config: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to update config: {e!s}'
        ) from e


@router.post('/restart')
async def restart_agent(
    request: AgentRestartRequest,
    service_manager=None
):
    """Restart the research agent with optional configuration reload."""
    try:
        if request.reload_config:
            # Force config reload
            from thoth.utilities.config import reset_config
            reset_config()

        config = get_config()

        # Reinitialize research agent
        from thoth.ingestion.agent_v2.core.agent import create_research_assistant_async

        if service_manager is None:
            from thoth.services.service_manager import ServiceManager
            service_manager = ServiceManager(config)
            service_manager.initialize()

        # Create new agent instance
        new_agent = await create_research_assistant_async(
            service_manager=service_manager,
            enable_memory=not request.reset_memory,
        )

        return JSONResponse(
            {
                'status': 'success',
                'message': 'Research agent restarted successfully',
                'memory_reset': request.reset_memory,
                'config_reloaded': request.reload_config,
            }
        )

    except Exception as e:
        logger.error(f'Failed to restart agent: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to restart agent: {e!s}'
        ) from e


@router.post('/sync-settings')
async def sync_obsidian_settings(settings: dict[str, Any]):
    """Sync settings from Obsidian plugin to backend."""
    try:
        # Map Obsidian settings to environment variables
        env_updates = {}

        # API Keys
        if settings.get('mistralKey'):
            env_updates['API_MISTRAL_KEY'] = settings['mistralKey']
            os.environ['API_MISTRAL_KEY'] = settings['mistralKey']

        if settings.get('openrouterKey'):
            env_updates['API_OPENROUTER_KEY'] = settings['openrouterKey']
            os.environ['API_OPENROUTER_KEY'] = settings['openrouterKey']

        # Directories
        if settings.get('workspaceDirectory'):
            env_updates['WORKSPACE_DIR'] = settings['workspaceDirectory']
            os.environ['WORKSPACE_DIR'] = settings['workspaceDirectory']

        if settings.get('obsidianDirectory'):
            env_updates['NOTES_DIR'] = settings['obsidianDirectory']
            os.environ['NOTES_DIR'] = settings['obsidianDirectory']

        # Server settings
        if settings.get('endpointHost'):
            env_updates['ENDPOINT_HOST'] = settings['endpointHost']
            os.environ['ENDPOINT_HOST'] = settings['endpointHost']

        if settings.get('endpointPort'):
            env_updates['ENDPOINT_PORT'] = str(settings['endpointPort'])
            os.environ['ENDPOINT_PORT'] = str(settings['endpointPort'])

        logger.info(f'Synced settings from Obsidian: {list(env_updates.keys())}')

        return JSONResponse(
            {
                'status': 'success',
                'message': 'Settings synced successfully',
                'synced_keys': list(env_updates.keys()),
            }
        )

    except Exception as e:
        logger.error(f'Error syncing Obsidian settings: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to sync settings: {e!s}'
        ) from e
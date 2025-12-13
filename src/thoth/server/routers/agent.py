"""Agent management endpoints."""

import asyncio
import os
import subprocess
import sys
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from thoth.config import config

router = APIRouter()

# Module-level variables that will be set by the main app
research_agent = None
current_config: dict[str, Any] = {}
orchestrator = None  # Will hold the ThothOrchestrator instance


def set_dependencies(agent, config, thoth_orchestrator=None):
    """Set the dependencies for this router."""
    global research_agent, current_config, orchestrator
    research_agent = agent
    current_config = config
    orchestrator = thoth_orchestrator


# Request Models
class ConfigUpdateRequest(BaseModel):
    api_keys: dict[str, str] | None = None
    directories: dict[str, str] | None = None
    settings: dict[str, Any] | None = None


class AgentRestartRequest(BaseModel):
    update_config: bool = False
    new_config: ConfigUpdateRequest | None = None


class ChatMessage(BaseModel):
    message: str
    conversation_id: str | None = None
    user_id: str = 'default'


async def delayed_shutdown():
    """Delay shutdown to allow response to be sent."""
    await asyncio.sleep(2)  # Give time for response to be sent
    logger.info('Shutting down for restart...')
    os.kill(os.getpid(), 15)  # SIGTERM


async def reinitialize_agent():
    """Reinitialize the agent without restarting the process."""
    global research_agent

    try:
        logger.info('Reinitializing research agent...')

        # Import here to avoid circular imports
        from thoth.ingestion.agent_v2.core.agent import create_research_assistant_async
        from thoth.services.service_manager import ServiceManager

        # Create new service manager and agent
        service_manager = ServiceManager()
        new_agent = await create_research_assistant_async(
            service_manager=service_manager
        )

        # Replace the global agent
        research_agent = new_agent

        logger.info('Agent reinitialization completed successfully')

    except Exception as e:
        logger.error(f'Failed to reinitialize agent: {e}')
        raise


@router.get('/status')
def agent_status():
    """Agent status endpoint for health checks."""
    if research_agent is None:
        return JSONResponse(
            {
                'status': 'not_initialized',
                'agent_initialized': False,
                'message': 'Research agent not initialized',
            },
            status_code=503,
        )

    try:
        # Check if agent has tools available (basic functionality test)
        tools = research_agent.get_available_tools()
        return JSONResponse(
            {
                'status': 'running',
                'agent_initialized': True,
                'tools_count': len(tools),
                'message': 'Research agent is running and ready',
            }
        )
    except Exception as e:
        logger.error(f'Error checking agent status: {e}')
        return JSONResponse(
            {
                'status': 'error',
                'agent_initialized': False,
                'error': str(e),
                'message': 'Research agent encountered an error',
            },
            status_code=500,
        )


@router.get('/tools')
def list_agent_tools():
    """List all available tools for the research agent."""
    if research_agent is None:
        raise HTTPException(status_code=503, detail='Research agent not initialized')

    try:
        tools = research_agent.get_available_tools()
        return JSONResponse({'tools': tools, 'count': len(tools)})
    except Exception as e:
        logger.error(f'Error listing agent tools: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to list tools: {e!s}'
        ) from e


@router.get('/config')
def get_agent_config():
    """Get current agent configuration."""
    try:
        # Get current config from the global config or reload it
        config  # Already imported at module level

        # Return sanitized config (without sensitive data)
        sanitized_config = {
            'directories': {
                'workspace_dir': str(config.workspace_dir),
                'pdf_dir': str(config.pdf_dir),
                'notes_dir': str(config.notes_dir),
                'queries_dir': str(config.queries_dir),
                'agent_storage_dir': str(config.agent_storage_dir),
            },
            'api_server': {
                'host': config.api_server_config.host,
                'port': config.api_server_config.port,
                'base_url': config.api_server_config.base_url,
            },
            'llm_models': {
                'llm_model': config.llm_config.model,
                'research_agent_model': config.research_agent_llm_config.model,
            },
            'discovery': {
                'auto_start_scheduler': config.discovery_config.auto_start_scheduler,
                'default_max_articles': config.discovery_config.default_max_articles,
            },
            'has_api_keys': {
                'mistral': bool(config.api_keys.mistral_key),
                'openrouter': bool(config.api_keys.openrouter_key),
            },
        }

        return JSONResponse(sanitized_config)

    except Exception as e:
        logger.error(f'Error getting agent config: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get config: {e!s}'
        ) from e


@router.post('/config')
async def update_agent_config(request: ConfigUpdateRequest):
    """Update agent configuration dynamically."""
    try:
        # Update environment variables
        env_updates = {}

        # Handle API keys
        if request.api_keys:
            for key, value in request.api_keys.items():
                if value:  # Only update non-empty values
                    env_key = f'API_{key.upper()}_KEY'
                    env_updates[env_key] = value
                    os.environ[env_key] = value

        # Handle directory settings
        if request.directories:
            for key, value in request.directories.items():
                if value:  # Only update non-empty values
                    env_key = key.upper() + '_DIR'
                    env_updates[env_key] = value
                    os.environ[env_key] = value

        # Handle other settings
        if request.settings:
            for key, value in request.settings.items():
                if value is not None:  # Allow False values
                    env_updates[key.upper()] = str(value)
                    os.environ[key.upper()] = str(value)

        logger.info(f'Updated environment variables: {list(env_updates.keys())}')

        return JSONResponse(
            {
                'status': 'success',
                'message': 'Configuration updated successfully',
                'updated_keys': list(env_updates.keys()),
                'note': 'Agent restart required for changes to take full effect',
            }
        )

    except Exception as e:
        logger.error(f'Error updating agent config: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to update config: {e!s}'
        ) from e


@router.post('/restart')
async def restart_agent(request: AgentRestartRequest = None):
    """Restart the agent process."""
    try:
        # Update config if requested
        if request and request.update_config and request.new_config:
            await update_agent_config(request.new_config)

        # Get current process info
        current_pid = os.getpid()

        # For development/local mode, try to restart gracefully
        if hasattr(sys, '_called_from_test'):
            # In test mode, just reinitialize
            await reinitialize_agent()
            return JSONResponse(
                {
                    'status': 'success',
                    'message': 'Agent reinitialized successfully (test mode)',
                    'method': 'reinitialize',
                }
            )

        # Try to restart the process
        try:
            # Get the command line arguments
            python_executable = sys.executable
            script_args = sys.argv

            logger.info(f'Restarting agent process (PID: {current_pid})')
            logger.info(f'Command: {python_executable} {" ".join(script_args)}')

            # Start new process
            subprocess.Popen([python_executable, *script_args])

            # Send response before terminating
            response_data = {
                'status': 'success',
                'message': 'Agent restart initiated',
                'old_pid': current_pid,
                'method': 'process_restart',
            }

            # Schedule process termination after response
            task = asyncio.create_task(delayed_shutdown())
            # Keep reference to prevent garbage collection
            _ = task

            return JSONResponse(response_data)

        except Exception as restart_error:
            logger.error(f'Process restart failed: {restart_error}')

            # Fall back to reinitializing the agent
            logger.info('Falling back to agent reinitialization...')
            await reinitialize_agent()

            return JSONResponse(
                {
                    'status': 'success',
                    'message': 'Agent reinitialized successfully (restart fallback)',
                    'method': 'reinitialize',
                    'restart_error': str(restart_error),
                }
            )

    except Exception as e:
        logger.error(f'Error restarting agent: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to restart agent: {e!s}'
        ) from e


@router.post('/sync-settings')
async def sync_obsidian_settings(settings: dict[str, Any]):
    """Sync settings from Obsidian plugin."""
    try:
        logger.info('Syncing settings from Obsidian plugin')
        logger.debug(f'Received settings: {settings}')

        # Update environment variables based on Obsidian settings
        env_updates = {}

        # Map Obsidian settings to environment variables
        setting_mappings = {
            'mistralApiKey': 'API_MISTRAL_KEY',
            'openaiApiKey': 'API_OPENAI_KEY',
            'anthropicApiKey': 'API_ANTHROPIC_KEY',
            'thothWorkspaceDir': 'THOTH_WORKSPACE_DIR',
            'enableAutoDiscovery': 'AUTO_START_DISCOVERY',
            'defaultMaxArticles': 'DEFAULT_MAX_ARTICLES',
        }

        for obsidian_key, env_key in setting_mappings.items():
            if settings.get(obsidian_key):
                value = settings[obsidian_key]
                env_updates[env_key] = str(value)
                os.environ[env_key] = str(value)

        # Update current config dict
        global current_config
        current_config.update(env_updates)

        logger.info(
            f'Updated environment variables from Obsidian: {list(env_updates.keys())}'
        )

        return JSONResponse(
            {
                'status': 'success',
                'message': 'Settings synchronized successfully',
                'updated_keys': list(env_updates.keys()),
                'synced_settings_count': len(env_updates),
            }
        )

    except Exception as e:
        logger.error(f'Error syncing Obsidian settings: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to sync settings: {e!s}'
        ) from e


@router.post('/chat')
async def agent_chat(message_request: ChatMessage):
    """
    Handle chat messages with Letta-based agent orchestration.

    This endpoint routes messages to appropriate agents based on content,
    supports agent creation, and manages @agent mentions.
    """
    try:
        # Check if orchestrator is available
        if orchestrator is None:
            # Fallback to regular research agent if orchestrator not available
            if research_agent is None:
                raise HTTPException(
                    status_code=503,
                    detail='Neither orchestrator nor research agent is available',
                )

            # Use the regular research agent for backward compatibility
            response = research_agent.astream_events(
                {'messages': [('user', message_request.message)]}, version='v1'
            )

            # Extract response from events
            result_text = ''
            async for event in response:
                if event['event'] == 'on_chain_end':
                    result_text = (
                        event['data']['output']
                        .get('messages', [{}])[-1]
                        .get('content', '')
                    )
                    break

            return JSONResponse(
                {
                    'response': result_text or 'No response generated',
                    'agent_type': 'research',
                    'conversation_id': message_request.conversation_id,
                }
            )

        # Use the Letta orchestrator for advanced agent management
        response = await orchestrator.handle_message(
            message=message_request.message,
            user_id=message_request.user_id,
            thread_id=message_request.conversation_id,
        )

        return JSONResponse(
            {
                'response': response,
                'agent_type': 'letta_orchestrated',
                'conversation_id': message_request.conversation_id,
                'user_id': message_request.user_id,
            }
        )

    except HTTPException:
        # Re-raise HTTPExceptions to preserve status codes
        raise
    except Exception as e:
        logger.error(f'Error in agent chat: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to process agent chat: {e!s}'
        ) from e


@router.get('/list')
async def list_available_agents():
    """List all available agents."""
    try:
        if orchestrator is None:
            return JSONResponse(
                {
                    'agents': [],
                    'message': 'Orchestrator not available - no custom agents available',
                }
            )

        # Get available agents from orchestrator
        try:
            system_agents = (
                await orchestrator._get_system_agents()
                if hasattr(orchestrator, '_get_system_agents')
                else []
            )
            user_agents = (
                await orchestrator._get_user_agents('default')
                if hasattr(orchestrator, '_get_user_agents')
                else []
            )

            agents_list = []

            # Add system agents
            for agent in system_agents:
                agents_list.append(
                    {
                        'name': agent.name,
                        'description': agent.description,
                        'type': 'system',
                        'capabilities': getattr(agent, 'capabilities', []),
                    }
                )

            # Add user agents
            for agent in user_agents:
                agents_list.append(
                    {
                        'name': agent.name,
                        'description': agent.description,
                        'type': 'user',
                        'capabilities': getattr(agent, 'capabilities', []),
                    }
                )

            return JSONResponse(
                {
                    'agents': agents_list,
                    'total_count': len(agents_list),
                    'system_count': len(system_agents),
                    'user_count': len(user_agents),
                }
            )

        except Exception as e:
            logger.error(f'Error getting agent lists: {e}')
            return JSONResponse(
                {'agents': [], 'message': f'Error retrieving agents: {e!s}'}
            )

    except Exception as e:
        logger.error(f'Error listing agents: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to list agents: {e!s}'
        ) from e

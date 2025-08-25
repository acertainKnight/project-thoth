"""Tool execution endpoints."""

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

router = APIRouter()

# Module-level variables that will be set by the main app
research_agent = None
service_manager = None


def set_dependencies(agent, sm):
    """Set the dependencies for this router."""
    global research_agent, service_manager
    research_agent = agent
    service_manager = sm


# Request Models
class ToolExecutionRequest(BaseModel):
    tool_name: str
    parameters: dict[str, Any] = {}
    bypass_agent: bool = False


class CommandExecutionRequest(BaseModel):
    command: str
    args: list[str] = []
    kwargs: dict[str, Any] = {}
    streaming: bool = False


@router.post('/execute')
async def execute_tool_direct(request: ToolExecutionRequest):
    """Execute a specific tool directly, optionally bypassing the agent."""
    if research_agent is None:
        raise HTTPException(status_code=503, detail='Research agent not initialized')

    try:
        if request.bypass_agent:
            # Execute tool directly
            tools = research_agent.get_available_tools()
            tool_info = next(
                (t for t in tools if t.get('name') == request.tool_name), None
            )

            if not tool_info:
                raise HTTPException(
                    status_code=404, detail=f'Tool {request.tool_name} not found'
                )

            # Execute the tool (implementation based on tool structure)
            result = await execute_tool_directly(request.tool_name, request.parameters)

            return JSONResponse(
                {
                    'tool': request.tool_name,
                    'parameters': request.parameters,
                    'result': result,
                    'bypassed_agent': True,
                }
            )
        else:
            # Execute through agent
            message = f'Please use the {request.tool_name} tool with these parameters: {request.parameters}'
            response = await research_agent.chat(
                message=message, session_id=f'tool-execution-{int(time.time())}'
            )

            return JSONResponse(
                {
                    'tool': request.tool_name,
                    'parameters': request.parameters,
                    'response': response.get('response'),
                    'tool_calls': response.get('tool_calls', []),
                    'bypassed_agent': False,
                }
            )

    except Exception as e:
        logger.error(f'Tool execution failed: {e}')
        raise HTTPException(
            status_code=500, detail=f'Tool execution failed: {e!s}'
        ) from e


async def execute_tool_directly(
    tool_name: str, parameters: dict[str, Any]
) -> dict[str, Any]:
    """Execute a tool directly without going through the agent."""
    try:
        # Map tool names to their direct execution methods
        if tool_name.startswith('thoth_search_papers'):
            return await execute_search_papers_tool(parameters)
        elif tool_name.startswith('thoth_analyze_document'):
            return await execute_analyze_document_tool(parameters)
        elif tool_name.startswith('thoth_download_pdf'):
            return await execute_download_pdf_tool(parameters)
        elif tool_name.startswith('thoth_rag_search'):
            return await execute_rag_search_tool(parameters)
        else:
            # Fallback for unknown tools
            logger.warning(f'Direct execution not implemented for tool: {tool_name}')
            return {
                'tool_executed': tool_name,
                'parameters_used': parameters,
                'result': f'Direct execution not implemented for {tool_name}',
                'timestamp': time.time(),
                'status': 'not_implemented',
            }

    except Exception as e:
        logger.error(f'Error in direct tool execution: {e}')
        return {
            'tool_executed': tool_name,
            'parameters_used': parameters,
            'error': str(e),
            'timestamp': time.time(),
            'status': 'error',
        }


async def execute_search_papers_tool(parameters: dict[str, Any]) -> dict[str, Any]:
    """Execute the search papers tool directly."""
    if service_manager is None:
        raise ValueError('Service manager not available')

    query = parameters.get('query', '')
    max_results = parameters.get('max_results', 10)

    try:
        discovery_service = service_manager.discovery_service
        results = await discovery_service.search_papers(query, max_results)

        return {
            'tool': 'thoth_search_papers',
            'query': query,
            'results': results,
            'count': len(results),
            'timestamp': time.time(),
            'status': 'success',
        }
    except Exception as e:
        raise ValueError(f'Search papers failed: {e}')


async def execute_analyze_document_tool(parameters: dict[str, Any]) -> dict[str, Any]:
    """Execute the analyze document tool directly."""
    if service_manager is None:
        raise ValueError('Service manager not available')

    document_id = parameters.get('document_id')
    analysis_type = parameters.get('analysis_type', 'full')

    try:
        # Use the processing service to analyze document
        processing_service = service_manager.processing_service
        result = await processing_service.analyze_document(document_id, analysis_type)

        return {
            'tool': 'thoth_analyze_document',
            'document_id': document_id,
            'analysis_type': analysis_type,
            'result': result,
            'timestamp': time.time(),
            'status': 'success',
        }
    except Exception as e:
        raise ValueError(f'Document analysis failed: {e}')


async def execute_download_pdf_tool(parameters: dict[str, Any]) -> dict[str, Any]:
    """Execute the download PDF tool directly."""
    url = parameters.get('url', '')
    if not url:
        raise ValueError('URL parameter is required')

    try:
        from thoth.ingestion.pdf_downloader import download_pdf
        from thoth.utilities.config import get_config

        config = get_config()
        pdf_path, metadata = download_pdf(url, config.pdf_dir)

        return {
            'tool': 'thoth_download_pdf',
            'url': url,
            'pdf_path': str(pdf_path),
            'metadata': metadata,
            'timestamp': time.time(),
            'status': 'success',
        }
    except Exception as e:
        raise ValueError(f'PDF download failed: {e}')


async def execute_rag_search_tool(parameters: dict[str, Any]) -> dict[str, Any]:
    """Execute the RAG search tool directly."""
    if service_manager is None:
        raise ValueError('Service manager not available')

    query = parameters.get('query', '')
    top_k = parameters.get('top_k', 5)

    try:
        rag_service = service_manager.rag_service
        results = await rag_service.search(query, top_k=top_k)

        return {
            'tool': 'thoth_rag_search',
            'query': query,
            'results': results,
            'count': len(results),
            'timestamp': time.time(),
            'status': 'success',
        }
    except Exception as e:
        raise ValueError(f'RAG search failed: {e}')


@router.post('/execute/command')
async def execute_command(request: CommandExecutionRequest):
    """Execute a Thoth CLI command through the API."""
    if service_manager is None:
        raise HTTPException(status_code=503, detail='Service manager not initialized')

    try:
        if request.streaming:
            # Execute with streaming support
            result = await execute_command_streaming(request)
        else:
            # Execute synchronously
            result = await execute_command_sync(request)

        return JSONResponse(result)

    except Exception as e:
        logger.error(f'Command execution failed: {e}')
        raise HTTPException(
            status_code=500, detail=f'Command execution failed: {e!s}'
        ) from e


async def execute_command_streaming(
    request: CommandExecutionRequest,
) -> dict[str, Any]:
    """Execute a command with streaming support."""
    # Implementation would depend on the specific command structure
    # For now, return a placeholder
    return {
        'command': request.command,
        'args': request.args,
        'kwargs': request.kwargs,
        'result': f'Streaming execution of {request.command} (placeholder)',
        'streaming': True,
        'timestamp': time.time(),
    }


async def execute_command_sync(request: CommandExecutionRequest) -> dict[str, Any]:
    """Execute a command synchronously."""
    command_handlers = {
        'discovery': execute_discovery_command,
        'pdf_locate': execute_pdf_locate_command,
        'rag': execute_rag_command,
        'notes': execute_notes_command,
    }

    handler = command_handlers.get(request.command)
    if not handler:
        raise ValueError(f'Unknown command: {request.command}')

    try:
        result = await handler(request.args, request.kwargs)
        return {
            'command': request.command,
            'args': request.args,
            'kwargs': request.kwargs,
            'result': result,
            'streaming': False,
            'timestamp': time.time(),
        }
    except Exception as e:
        raise ValueError(f'Command execution failed: {e}')


async def execute_discovery_command(
    args: list[str], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Execute a discovery command."""
    discovery_service = service_manager.discovery_service

    action = args[0] if args else 'list'

    if action == 'list':
        sources = await discovery_service.list_sources()
        return {'action': 'list', 'sources': sources}
    elif action == 'run':
        source_name = args[1] if len(args) > 1 else None
        if not source_name:
            raise ValueError('Source name required for run action')
        results = await discovery_service.run_discovery_for_source(source_name)
        return {'action': 'run', 'source': source_name, 'results': results}
    else:
        raise ValueError(f'Unknown discovery action: {action}')


async def execute_pdf_locate_command(
    args: list[str], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Execute a PDF locate command."""
    pdf_locator_service = service_manager.pdf_locator_service

    if not args:
        raise ValueError('DOI or identifier required')

    identifier = args[0]
    locations = await pdf_locator_service.locate(identifier)

    return {
        'identifier': identifier,
        'locations': locations,
        'found': len(locations) > 0,
    }


async def execute_rag_command(
    args: list[str], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Execute a RAG command."""
    rag_service = service_manager.rag_service

    action = args[0] if args else 'search'

    if action == 'search':
        query = ' '.join(args[1:]) if len(args) > 1 else kwargs.get('query', '')
        if not query:
            raise ValueError('Query required for search')

        results = await rag_service.search(query)
        return {'action': 'search', 'query': query, 'results': results}
    else:
        raise ValueError(f'Unknown RAG action: {action}')


async def execute_notes_command(
    args: list[str], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Execute a notes command."""
    note_service = service_manager.note_service

    action = args[0] if args else 'list'

    if action == 'list':
        notes = await note_service.list_notes()
        return {'action': 'list', 'notes': notes}
    elif action == 'generate':
        document_id = args[1] if len(args) > 1 else kwargs.get('document_id')
        if not document_id:
            raise ValueError('Document ID required for generate action')

        note = await note_service.generate_note(document_id)
        return {'action': 'generate', 'document_id': document_id, 'note': note}
    else:
        raise ValueError(f'Unknown notes action: {action}')

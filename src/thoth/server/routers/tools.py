"""
Tools execution endpoints.
"""

import asyncio
import subprocess
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

router = APIRouter(tags=["tools"])


class CommandExecutionRequest(BaseModel):
    """Request model for command execution."""
    command: str
    args: list[str] = []
    cwd: str | None = None
    timeout: int = 30
    capture_output: bool = True


class ToolExecutionRequest(BaseModel):
    """Request model for tool execution."""
    tool_name: str
    parameters: dict[str, Any]
    session_id: str | None = None


@router.post('/execute/command')
async def execute_command(request: CommandExecutionRequest):
    """
    Execute a system command with timeout and output capture.
    
    WARNING: This endpoint executes arbitrary commands and should be
    properly secured in production environments.
    """
    try:
        # Security warning
        logger.warning(
            f'Executing command: {request.command} {" ".join(request.args)}'
        )
        
        # Prepare command
        cmd = [request.command] + request.args
        
        # Execute command
        if request.capture_output:
            result = subprocess.run(
                cmd,
                cwd=request.cwd,
                capture_output=True,
                text=True,
                timeout=request.timeout,
            )
            
            return JSONResponse({
                'status': 'success',
                'command': request.command,
                'args': request.args,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0,
            })
        else:
            # Run without capturing output
            result = subprocess.run(
                cmd,
                cwd=request.cwd,
                timeout=request.timeout,
            )
            
            return JSONResponse({
                'status': 'success',
                'command': request.command,
                'args': request.args,
                'return_code': result.returncode,
                'success': result.returncode == 0,
            })
            
    except subprocess.TimeoutExpired:
        logger.error(f'Command timed out: {request.command}')
        raise HTTPException(
            status_code=408,
            detail=f'Command execution timed out after {request.timeout} seconds'
        )
    except Exception as e:
        logger.error(f'Command execution failed: {e}')
        raise HTTPException(
            status_code=500,
            detail=f'Command execution failed: {e!s}'
        ) from e


@router.post('/tools/execute')
async def execute_tool(
    request: ToolExecutionRequest,
    research_agent=None
):
    """
    Execute a specific tool with the provided parameters.
    
    This endpoint allows direct tool execution without going through
    the full agent conversation flow.
    """
    if research_agent is None:
        raise HTTPException(
            status_code=503, detail='Research agent not initialized'
        )
    
    try:
        # Find the requested tool
        tool = None
        if hasattr(research_agent, 'tools'):
            for t in research_agent.tools:
                if getattr(t, 'name', str(t)) == request.tool_name:
                    tool = t
                    break
        
        if tool is None:
            available_tools = [
                getattr(t, 'name', str(t))
                for t in getattr(research_agent, 'tools', [])
            ]
            raise HTTPException(
                status_code=404,
                detail=f'Tool "{request.tool_name}" not found. Available tools: {available_tools}'
            )
        
        # Execute the tool
        logger.info(f'Executing tool: {request.tool_name}')
        
        # Tools might be async or sync, handle both
        if asyncio.iscoroutinefunction(tool):
            result = await tool(**request.parameters)
        else:
            result = tool(**request.parameters)
        
        return JSONResponse({
            'status': 'success',
            'tool_name': request.tool_name,
            'parameters': request.parameters,
            'result': result if isinstance(result, dict) else str(result),
            'session_id': request.session_id,
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Tool execution failed: {e}')
        raise HTTPException(
            status_code=500,
            detail=f'Tool execution failed: {e!s}'
        ) from e


@router.get('/tools/list')
async def list_available_tools(research_agent=None):
    """Get a list of all available tools with their descriptions."""
    if research_agent is None:
        raise HTTPException(
            status_code=503, detail='Research agent not initialized'
        )
    
    try:
        tools = []
        if hasattr(research_agent, 'tools'):
            for tool in research_agent.tools:
                tool_info = {
                    'name': getattr(tool, 'name', str(tool)),
                    'description': getattr(tool, 'description', 'No description available'),
                }
                
                # Try to get parameter information
                if hasattr(tool, 'args_schema'):
                    schema = tool.args_schema
                    if hasattr(schema, 'schema'):
                        tool_info['parameters'] = schema.schema()
                elif hasattr(tool, '__doc__') and tool.__doc__:
                    tool_info['docstring'] = tool.__doc__.strip()
                
                tools.append(tool_info)
        
        return JSONResponse({
            'status': 'success',
            'tool_count': len(tools),
            'tools': tools,
        })
        
    except Exception as e:
        logger.error(f'Failed to list tools: {e}')
        raise HTTPException(
            status_code=500,
            detail=f'Failed to list tools: {e!s}'
        ) from e


@router.post('/tools/batch')
async def execute_tools_batch(
    tools_requests: list[ToolExecutionRequest],
    parallel: bool = True,
    research_agent=None
):
    """
    Execute multiple tools in batch.
    
    Supports both parallel and sequential execution modes.
    """
    if research_agent is None:
        raise HTTPException(
            status_code=503, detail='Research agent not initialized'
        )
    
    try:
        results = []
        
        if parallel:
            # Execute tools in parallel
            import asyncio
            
            async def execute_single(req: ToolExecutionRequest):
                try:
                    # Reuse the execute_tool logic
                    response = await execute_tool(req, research_agent)
                    return response.body
                except Exception as e:
                    return {
                        'status': 'error',
                        'tool_name': req.tool_name,
                        'error': str(e),
                    }
            
            # Execute all tools concurrently
            tasks = [execute_single(req) for req in tools_requests]
            results = await asyncio.gather(*tasks)
        else:
            # Execute tools sequentially
            for req in tools_requests:
                try:
                    response = await execute_tool(req, research_agent)
                    results.append(response.body)
                except Exception as e:
                    results.append({
                        'status': 'error',
                        'tool_name': req.tool_name,
                        'error': str(e),
                    })
        
        # Count successes and failures
        successes = sum(1 for r in results if r.get('status') == 'success')
        failures = len(results) - successes
        
        return JSONResponse({
            'status': 'completed',
            'total': len(tools_requests),
            'successes': successes,
            'failures': failures,
            'parallel': parallel,
            'results': results,
        })
        
    except Exception as e:
        logger.error(f'Batch tool execution failed: {e}')
        raise HTTPException(
            status_code=500,
            detail=f'Batch execution failed: {e!s}'
        ) from e
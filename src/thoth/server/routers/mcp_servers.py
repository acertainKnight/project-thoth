"""
REST API endpoints for MCP server management.

This router provides HTTP endpoints for managing external MCP server connections.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from thoth.models.mcp_server_config import MCPServerEntry
from thoth.server.dependencies import get_service_manager
from thoth.services.service_manager import ServiceManager

router = APIRouter(prefix='/api/mcp-servers', tags=['mcp-servers'])


class MCPServerCreateRequest(BaseModel):
    """Request model for creating an MCP server."""

    server_id: str = Field(..., description='Unique server identifier')
    server_config: MCPServerEntry = Field(..., description='Server configuration')


class MCPServerUpdateRequest(BaseModel):
    """Request model for updating an MCP server."""

    server_config: MCPServerEntry = Field(
        ..., description='Updated server configuration'
    )


class MCPServerToggleRequest(BaseModel):
    """Request model for toggling an MCP server."""

    enabled: bool = Field(..., description='Whether to enable the server')


class MCPServerTestResponse(BaseModel):
    """Response model for connection test."""

    success: bool = Field(..., description='Whether the test succeeded')
    message: str = Field(..., description='Test result message')
    tool_count: int | None = Field(None, description='Number of tools discovered')


class ToolInfo(BaseModel):
    """Information about a tool from an MCP server."""

    name: str = Field(..., description='Tool name (unprefixed)')
    description: str = Field(..., description='Tool description')
    prefixed_name: str = Field(..., description='Prefixed tool name for use in Letta')
    attached: bool = Field(
        default=False, description='Whether tool is attached to agent'
    )


class ToolAttachRequest(BaseModel):
    """Request model for attaching tools to an agent."""

    agent_id: str = Field(..., description='Letta agent ID')
    tool_names: list[str] = Field(..., description='Tool names to attach (unprefixed)')


class ToolDetachRequest(BaseModel):
    """Request model for detaching tools from an agent."""

    agent_id: str = Field(..., description='Letta agent ID')
    tool_names: list[str] = Field(..., description='Tool names to detach (unprefixed)')


class MCPServerStatusResponse(BaseModel):
    """Response model for server status."""

    server_id: str
    name: str
    enabled: bool
    connected: bool
    transport: str
    auto_attach: bool
    tool_count: int


@router.get('', response_model=list[MCPServerStatusResponse])
async def list_mcp_servers(
    service_manager: ServiceManager = Depends(get_service_manager),
) -> list[MCPServerStatusResponse]:
    """
    List all configured MCP servers with their status.

    Returns:
        list[MCPServerStatusResponse]: List of server status information
    """
    try:
        mcp_manager = service_manager.get_service('mcp_servers_manager')

        if not mcp_manager:
            raise HTTPException(
                status_code=503, detail='MCP Servers Manager not available'
            )

        status = await mcp_manager.get_server_status()

        return [
            MCPServerStatusResponse(
                server_id=server_id,
                name=info['name'],
                enabled=info['enabled'],
                connected=info['connected'],
                transport=info['transport'],
                auto_attach=info['auto_attach'],
                tool_count=info['tool_count'],
            )
            for server_id, info in status.items()
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post('', status_code=201)
async def add_mcp_server(
    request: MCPServerCreateRequest,
    service_manager: ServiceManager = Depends(get_service_manager),
) -> dict[str, str]:
    """
    Add a new MCP server to the configuration.

    Args:
        request: Server creation request

    Returns:
        dict: Success message with server ID
    """
    try:
        mcp_manager = service_manager.get_service('mcp_servers_manager')

        if not mcp_manager:
            raise HTTPException(
                status_code=503, detail='MCP Servers Manager not available'
            )

        # Validate transport-specific requirements
        if (
            request.server_config.transport == 'stdio'
            and not request.server_config.command
        ):
            raise HTTPException(
                status_code=400, detail="'command' is required for stdio transport"
            )

        if (
            request.server_config.transport in ['http', 'sse']
            and not request.server_config.url
        ):
            raise HTTPException(
                status_code=400,
                detail=f"'url' is required for {request.server_config.transport} transport",
            )

        await mcp_manager.add_server(request.server_id, request.server_config)

        return {
            'message': f"Successfully added MCP server '{request.server_id}'",
            'server_id': request.server_id,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get('/{server_id}', response_model=MCPServerEntry)
async def get_mcp_server(
    server_id: str,
    service_manager: ServiceManager = Depends(get_service_manager),
) -> MCPServerEntry:
    """
    Get a specific MCP server configuration.

    Args:
        server_id: Server identifier

    Returns:
        MCPServerEntry: Server configuration
    """
    try:
        mcp_manager = service_manager.get_service('mcp_servers_manager')

        if not mcp_manager:
            raise HTTPException(
                status_code=503, detail='MCP Servers Manager not available'
            )

        servers = await mcp_manager.list_servers()

        if server_id not in servers:
            raise HTTPException(
                status_code=404, detail=f"Server '{server_id}' not found"
            )

        return servers[server_id]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch('/{server_id}')
async def update_mcp_server(
    server_id: str,
    request: MCPServerUpdateRequest,
    service_manager: ServiceManager = Depends(get_service_manager),
) -> dict[str, str]:
    """
    Update an existing MCP server configuration.

    Args:
        server_id: Server identifier
        request: Server update request

    Returns:
        dict: Success message
    """
    try:
        mcp_manager = service_manager.get_service('mcp_servers_manager')

        if not mcp_manager:
            raise HTTPException(
                status_code=503, detail='MCP Servers Manager not available'
            )

        await mcp_manager.update_server(server_id, request.server_config)

        return {'message': f"Successfully updated MCP server '{server_id}'"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete('/{server_id}')
async def remove_mcp_server(
    server_id: str,
    service_manager: ServiceManager = Depends(get_service_manager),
) -> dict[str, str]:
    """
    Remove an MCP server from the configuration.

    Args:
        server_id: Server identifier

    Returns:
        dict: Success message
    """
    try:
        mcp_manager = service_manager.get_service('mcp_servers_manager')

        if not mcp_manager:
            raise HTTPException(
                status_code=503, detail='MCP Servers Manager not available'
            )

        await mcp_manager.remove_server(server_id)

        return {'message': f"Successfully removed MCP server '{server_id}'"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post('/{server_id}/toggle')
async def toggle_mcp_server(
    server_id: str,
    request: MCPServerToggleRequest,
    service_manager: ServiceManager = Depends(get_service_manager),
) -> dict[str, str]:
    """
    Enable or disable an MCP server.

    Args:
        server_id: Server identifier
        request: Toggle request

    Returns:
        dict: Success message
    """
    try:
        mcp_manager = service_manager.get_service('mcp_servers_manager')

        if not mcp_manager:
            raise HTTPException(
                status_code=503, detail='MCP Servers Manager not available'
            )

        await mcp_manager.toggle_server(server_id, request.enabled)

        action = 'enabled' if request.enabled else 'disabled'
        return {'message': f"Successfully {action} MCP server '{server_id}'"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post('/{server_id}/test', response_model=MCPServerTestResponse)
async def test_mcp_connection(
    server_id: str,
    service_manager: ServiceManager = Depends(get_service_manager),
) -> MCPServerTestResponse:
    """
    Test connectivity to an MCP server.

    Args:
        server_id: Server identifier

    Returns:
        MCPServerTestResponse: Test result
    """
    try:
        mcp_manager = service_manager.get_service('mcp_servers_manager')

        if not mcp_manager:
            raise HTTPException(
                status_code=503, detail='MCP Servers Manager not available'
            )

        result = await mcp_manager.test_connection(server_id)

        return MCPServerTestResponse(
            success=result['success'],
            message=result['message'],
            tool_count=result.get('tool_count'),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get('/{server_id}/tools', response_model=list[ToolInfo])
async def get_server_tools(
    server_id: str,
    agent_id: str | None = None,
    service_manager: ServiceManager = Depends(get_service_manager),
) -> list[ToolInfo]:
    """
    Get detailed tool list from an MCP server.

    Args:
        server_id: Server identifier
        agent_id: Optional agent ID to check attached status

    Returns:
        list[ToolInfo]: List of tool details
    """
    try:
        mcp_manager = service_manager.get_service('mcp_servers_manager')

        if not mcp_manager:
            raise HTTPException(
                status_code=503, detail='MCP Servers Manager not available'
            )

        # Get tool details from manager
        tool_details = mcp_manager.get_server_tool_details(server_id)

        if not tool_details:
            # Server might not be connected or has no tools
            servers = await mcp_manager.list_servers()
            if server_id not in servers:
                raise HTTPException(
                    status_code=404, detail=f"Server '{server_id}' not found"
                )
            # Server exists but has no tools or isn't connected
            return []

        # If agent_id provided, check which tools are attached
        attached_tools = set()
        if agent_id:
            letta_service = service_manager.get_service('letta_service')
            if letta_service:
                try:
                    current_tools = letta_service.get_agent_tools(agent_id)
                    attached_tools = set(current_tools)
                except Exception as e:
                    # Log but don't fail - just won't show attached status
                    print(f'Warning: Could not get agent tools: {e}')

        # Build response
        result = []
        for tool in tool_details:
            result.append(
                ToolInfo(
                    name=tool['name'],
                    description=tool['description'],
                    prefixed_name=tool['prefixed_name'],
                    attached=tool['prefixed_name'] in attached_tools,
                )
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post('/{server_id}/tools/attach')
async def attach_tools_to_agent(
    server_id: str,
    request: ToolAttachRequest,
    service_manager: ServiceManager = Depends(get_service_manager),
) -> dict[str, Any]:
    """
    Attach selected tools from an MCP server to a Letta agent.

    Args:
        server_id: Server identifier
        request: Tool attachment request

    Returns:
        dict: Attachment result with counts
    """
    try:
        mcp_manager = service_manager.get_service('mcp_servers_manager')
        letta_service = service_manager.get_service('letta_service')

        if not mcp_manager:
            raise HTTPException(
                status_code=503, detail='MCP Servers Manager not available'
            )

        if not letta_service:
            raise HTTPException(status_code=503, detail='Letta Service not available')

        # Get tool details to verify tools exist and get their prefixed names
        tool_details = mcp_manager.get_server_tool_details(server_id)
        tool_name_map = {tool['name']: tool['prefixed_name'] for tool in tool_details}

        # Verify all requested tools exist
        missing_tools = [
            name for name in request.tool_names if name not in tool_name_map
        ]
        if missing_tools:
            raise HTTPException(
                status_code=400,
                detail=f'Tools not found on server {server_id}: {", ".join(missing_tools)}',
            )

        # Get prefixed tool names as registered with Letta
        prefixed_names = [tool_name_map[name] for name in request.tool_names]

        # Attach tools via Letta service
        result = letta_service.attach_tools_to_agent(
            agent_id=request.agent_id, tool_names=prefixed_names
        )

        return {
            'message': f'Successfully processed tool attachment for agent {request.agent_id}',
            'attached': result['attached'],
            'already_attached': result['already_attached'],
            'not_found': result['not_found'],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post('/{server_id}/tools/detach')
async def detach_tools_from_agent(
    server_id: str,
    request: ToolDetachRequest,
    service_manager: ServiceManager = Depends(get_service_manager),
) -> dict[str, Any]:
    """
    Detach selected tools from a Letta agent.

    Args:
        server_id: Server identifier
        request: Tool detachment request

    Returns:
        dict: Detachment result with counts
    """
    try:
        mcp_manager = service_manager.get_service('mcp_servers_manager')
        letta_service = service_manager.get_service('letta_service')

        if not mcp_manager:
            raise HTTPException(
                status_code=503, detail='MCP Servers Manager not available'
            )

        if not letta_service:
            raise HTTPException(status_code=503, detail='Letta Service not available')

        # Get tool details to get their prefixed names
        tool_details = mcp_manager.get_server_tool_details(server_id)
        tool_name_map = {tool['name']: tool['prefixed_name'] for tool in tool_details}

        # Get prefixed tool names as registered with Letta
        prefixed_names = [
            tool_name_map.get(name, f'{server_id}__{name}')
            for name in request.tool_names
        ]

        # Detach tools via Letta service
        result = letta_service.detach_tools_from_agent(
            agent_id=request.agent_id, tool_names=prefixed_names
        )

        return {
            'message': f'Successfully processed tool detachment for agent {request.agent_id}',
            'detached': result['detached'],
            'not_attached': result['not_attached'],
            'not_found': result['not_found'],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

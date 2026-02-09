"""
REST API endpoints for MCP server management.

This router provides HTTP endpoints for managing external MCP server connections.
"""

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

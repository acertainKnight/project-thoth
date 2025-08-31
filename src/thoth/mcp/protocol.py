"""
MCP Protocol Implementation

This module implements the core Model Context Protocol JSON-RPC 2.0 message handling
according to the official MCP specification.
"""

import json
import uuid
from enum import Enum
from typing import Any

from loguru import logger
from pydantic import BaseModel, model_validator


class MCPProtocolVersion(str, Enum):
    """Supported MCP protocol versions."""

    CURRENT = '2025-06-18'


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: Any | None = None


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request message."""

    jsonrpc: str = '2.0'
    id: str | int | None = None
    method: str
    params: dict[str, Any] | None = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response message."""

    jsonrpc: str = '2.0'
    id: str | int | None
    result: Any | None = None
    error: JSONRPCError | None = None

    @model_validator(mode='after')
    def validate_response_structure(self):
        """Validate that exactly one of result or error is present."""
        if self.result is not None and self.error is not None:
            raise ValueError('Response cannot have both result and error')
        if self.result is None and self.error is None:
            raise ValueError('Response must have either result or error')
        return self


class JSONRPCNotification(BaseModel):
    """JSON-RPC 2.0 notification message."""

    jsonrpc: str = '2.0'
    method: str
    params: dict[str, Any] | None = None


class MCPCapabilities(BaseModel):
    """MCP server capabilities."""

    tools: dict[str, Any] | None = None
    resources: dict[str, Any] | None = None
    prompts: dict[str, Any] | None = None
    logging: dict[str, Any] | None = None


class MCPServerInfo(BaseModel):
    """MCP server information."""

    name: str
    version: str


class MCPInitializeParams(BaseModel):
    """Parameters for MCP initialize request."""

    protocolVersion: str
    capabilities: MCPCapabilities
    clientInfo: MCPServerInfo


class MCPInitializeResult(BaseModel):
    """Result for MCP initialize response."""

    protocolVersion: str = MCPProtocolVersion.CURRENT
    capabilities: MCPCapabilities
    serverInfo: MCPServerInfo


class MCPToolSchema(BaseModel):
    """MCP tool definition schema."""

    name: str
    description: str
    inputSchema: dict[str, Any]


class MCPToolCallParams(BaseModel):
    """Parameters for MCP tool call."""

    name: str
    arguments: dict[str, Any]


class MCPToolCallResult(BaseModel):
    """Result for MCP tool call."""

    content: list[dict[str, Any]]
    isError: bool = False


class MCPResourceTemplate(BaseModel):
    """MCP resource template."""

    uriTemplate: str
    name: str
    description: str
    mimeType: str | None = None


class MCPResource(BaseModel):
    """MCP resource definition."""

    uri: str
    name: str
    description: str
    mimeType: str | None = None


class MCPResourceContents(BaseModel):
    """MCP resource contents."""

    uri: str
    mimeType: str | None = None
    text: str | None = None
    blob: str | None = None  # base64 encoded


class MCPPromptTemplate(BaseModel):
    """MCP prompt template."""

    name: str
    description: str
    arguments: list[dict[str, Any]]


class MCPPromptMessage(BaseModel):
    """MCP prompt message."""

    role: str
    content: dict[str, Any]


class MCPGetPromptResult(BaseModel):
    """Result for MCP get prompt."""

    description: str
    messages: list[MCPPromptMessage]


class MCPProtocolHandler:
    """
    Core MCP protocol message handler.

    Handles JSON-RPC 2.0 message parsing, validation, and routing
    according to the MCP specification.
    """

    def __init__(self):
        self.initialized = False
        self.client_capabilities: MCPCapabilities | None = None
        self.protocol_version = MCPProtocolVersion.CURRENT

    def parse_message(
        self, raw_message: str
    ) -> JSONRPCRequest | JSONRPCResponse | JSONRPCNotification:
        """Parse raw JSON message into appropriate JSON-RPC object."""
        try:
            data = json.loads(raw_message)

            # Validate JSON-RPC 2.0 format
            if data.get('jsonrpc') != '2.0':
                raise ValueError('Invalid JSON-RPC version')

            # Determine message type
            if 'method' in data:
                if 'id' in data:
                    return JSONRPCRequest(**data)
                else:
                    return JSONRPCNotification(**data)
            elif 'result' in data or 'error' in data:
                return JSONRPCResponse(**data)
            else:
                raise ValueError('Invalid JSON-RPC message format')

        except json.JSONDecodeError as e:
            raise ValueError(f'Invalid JSON: {e}') from e
        except Exception as e:
            raise ValueError(f'Invalid message format: {e}') from e

    def create_response(
        self,
        request_id: str | int | None,
        result: Any = None,
        error: JSONRPCError = None,
    ) -> JSONRPCResponse:
        """Create a JSON-RPC response message."""
        if error is not None:
            # For error responses, don't include result field
            return JSONRPCResponse(id=request_id, error=error)
        else:
            # For success responses, don't include error field
            return JSONRPCResponse(id=request_id, result=result)

    def create_error_response(
        self,
        request_id: str | int | None,
        code: int,
        message: str,
        data: Any = None,
    ) -> JSONRPCResponse:
        """Create a JSON-RPC error response."""
        error = JSONRPCError(code=code, message=message, data=data)
        return self.create_response(request_id, error=error)

    def create_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> JSONRPCNotification:
        """Create a JSON-RPC notification message."""
        return JSONRPCNotification(method=method, params=params)

    def generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return str(uuid.uuid4())

    def validate_initialize_request(
        self, params: dict[str, Any]
    ) -> MCPInitializeParams:
        """Validate and parse initialize request parameters."""
        try:
            return MCPInitializeParams(**params)
        except Exception as e:
            raise ValueError(f'Invalid initialize parameters: {e}') from e

    def handle_initialize(
        self,
        params: MCPInitializeParams,
        server_info: MCPServerInfo,
        server_capabilities: MCPCapabilities,
    ) -> MCPInitializeResult:
        """Handle MCP initialize request."""
        # Allow multiple clients to initialize (each gets their own session)
        # Store the client info for this session
        client_name = params.clientInfo.name if params.clientInfo else 'unknown'

        if self.initialized:
            logger.debug(
                f'Additional client connecting: {client_name} (server already initialized)'
            )
        else:
            logger.info(f'First client connecting: {client_name} (initializing server)')

        # Validate protocol version compatibility
        if params.protocolVersion != self.protocol_version:
            logger.warning(
                f'Protocol version mismatch: client={params.protocolVersion}, server={self.protocol_version}'
            )

        # Store client capabilities (last client wins, but that's OK for our use case)
        self.client_capabilities = params.capabilities
        self.initialized = True

        return MCPInitializeResult(
            protocolVersion=self.protocol_version,
            capabilities=server_capabilities,
            serverInfo=server_info,
        )

    def handle_initialized(self) -> None:
        """Handle MCP initialized notification."""
        if not self.initialized:
            raise ValueError('Not initialized')
        logger.info('MCP client initialization completed')

    def validate_tool_call_params(self, params: dict[str, Any]) -> MCPToolCallParams:
        """Validate and parse tool call parameters."""
        try:
            return MCPToolCallParams(**params)
        except Exception as e:
            raise ValueError(f'Invalid tool call parameters: {e}') from e

    def serialize_message(
        self, message: JSONRPCRequest | JSONRPCResponse | JSONRPCNotification
    ) -> str:
        """Serialize message object to JSON string."""
        return message.model_dump_json(exclude_none=True)


# Standard MCP error codes
class MCPErrorCodes:
    """Standard MCP error codes following JSON-RPC 2.0 specification."""

    # JSON-RPC 2.0 standard errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # MCP-specific errors
    CAPABILITY_NOT_SUPPORTED = -32000
    TOOL_NOT_FOUND = -32001
    RESOURCE_NOT_FOUND = -32002
    PROMPT_NOT_FOUND = -32003
    UNAUTHORIZED = -32004

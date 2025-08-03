"""
Thoth Model Context Protocol (MCP) Implementation

This package provides a fully MCP-compliant server and client implementation
for the Thoth research assistant, following the official MCP specification.
"""

from .base_tools import MCPTool, MCPToolRegistry
from .client import MCPClient
from .resources import MCPResource, MCPResourceManager
from .server import MCPServer
from .transports import HTTPTransport, StdioTransport

__all__ = [
    'HTTPTransport',
    'MCPClient',
    'MCPResource',
    'MCPResourceManager',
    'MCPServer',
    'MCPTool',
    'MCPToolRegistry',
    'StdioTransport',
]

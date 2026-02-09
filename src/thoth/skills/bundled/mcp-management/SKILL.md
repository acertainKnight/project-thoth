---
skill_id: mcp-management
name: MCP Server Management
description: Manage external MCP server connections to extend Thoth's capabilities
version: 1.0.0
author: Thoth Team
required_tools:
  - list_mcp_servers
  - add_mcp_server
  - update_mcp_server
  - remove_mcp_server
  - toggle_mcp_server
  - test_mcp_connection
tags:
  - management
  - mcp
  - configuration
  - tools
---

# MCP Server Management Skill

## Overview

This skill provides comprehensive management of external MCP (Model Context Protocol) servers that can extend Thoth's capabilities with additional tools and resources.

## What is MCP?

MCP (Model Context Protocol) is a standard protocol that allows AI assistants to connect to external tool servers. By adding MCP servers, you can:

- Access additional tools (filesystem, databases, APIs, etc.)
- Integrate with external services
- Extend Thoth's capabilities without modifying core code
- Connect to custom tool servers you or others have built

## Core Capabilities

### 1. List MCP Servers
View all configured external MCP servers, their connection status, and tool counts.

**Example:**
```
Can you show me what MCP servers are configured?
```

### 2. Add MCP Server
Add a new external MCP server with stdio, HTTP, or SSE transport.

**Example for stdio transport:**
```
Add an MCP server called "my-filesystem" with:
- transport: stdio
- command: npx
- args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/folder"]
- enabled: true
- auto_attach: true
```

**Example for SSE transport:**
```
Add an MCP server called "remote-analysis" with:
- transport: sse
- url: http://localhost:8080/mcp
- enabled: true
- auto_attach: false
```

### 3. Update MCP Server
Modify an existing server's configuration.

**Example:**
```
Update the "my-filesystem" server to enable auto-attach
```

### 4. Remove MCP Server
Remove a server from the configuration (disconnects and detaches tools).

**Example:**
```
Remove the "remote-analysis" MCP server
```

### 5. Toggle MCP Server
Enable or disable a server without removing it.

**Example:**
```
Disable the "my-filesystem" server
```

### 6. Test Connection
Test connectivity to a configured MCP server.

**Example:**
```
Test the connection to the "my-filesystem" server
```

## Configuration File

All MCP servers are stored in `vault/thoth/_thoth/mcps.json`. This file serves as the single source of truth and is monitored for changes (hot-reload enabled).

### File Format

```json
{
  "version": "1.0.0",
  "mcpServers": {
    "server-id": {
      "name": "Server Name",
      "enabled": true,
      "transport": "stdio|http|sse",
      "command": "command-for-stdio",
      "args": ["arg1", "arg2"],
      "url": "http://url-for-http-or-sse",
      "env": {"ENV_VAR": "value"},
      "autoAttach": true,
      "timeout": 30
    }
  }
}
```

## Transport Types

### stdio (Standard Input/Output)
Best for local command-line tools that communicate via stdin/stdout.

**Required fields:** `command`, `args`
**Example:** npx-based MCP servers

### HTTP
Best for HTTP-based REST APIs.

**Required fields:** `url`
**Example:** `http://localhost:8080/mcp`

### SSE (Server-Sent Events)
Best for streaming responses and real-time updates.

**Required fields:** `url`
**Example:** `http://localhost:8080/mcp`

## Auto-Attach Behavior

When `autoAttach: true`:
- Tools from the server are automatically attached to all Letta agents
- New agents automatically get these tools
- Disabling the server detaches tools from agents

When `autoAttach: false`:
- Tools are available but not automatically attached
- Useful for servers with tools you want to use selectively

## Hot-Reload

The system watches `mcps.json` for changes and automatically:
1. Connects new servers when added
2. Reconnects servers when configuration changes
3. Disconnects servers when removed or disabled
4. Syncs tool attachments with Letta agents

You can manually edit the file or use the provided tools.

## Common MCP Servers

### Filesystem Access
```json
{
  "filesystem": {
    "name": "Filesystem Server",
    "enabled": true,
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
    "autoAttach": true,
    "timeout": 30
  }
}
```

### SQLite Database
```json
{
  "sqlite": {
    "name": "SQLite Database",
    "enabled": true,
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "./data.db"],
    "autoAttach": true,
    "timeout": 30
  }
}
```

### GitHub Integration
```json
{
  "github": {
    "name": "GitHub Server",
    "enabled": true,
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {"GITHUB_TOKEN": "your-token"},
    "autoAttach": false,
    "timeout": 30
  }
}
```

## Best Practices

1. **Start disabled**: Add new servers with `enabled: false` and test before enabling
2. **Test connections**: Always test connectivity before fully configuring
3. **Use auto-attach wisely**: Only auto-attach tools that are broadly useful
4. **Set appropriate timeouts**: Adjust based on server response times
5. **Secure credentials**: Use environment variables for sensitive data
6. **Document custom servers**: Add clear descriptions for custom MCP servers

## Troubleshooting

### Server won't connect
- Check the command/URL is correct
- Verify the server is installed and accessible
- Check logs for connection errors
- Test with a longer timeout

### Tools not appearing
- Ensure server is enabled
- Check `autoAttach` setting
- Verify server connection status
- Check Letta agent tool list

### Configuration not updating
- Wait 2-3 seconds for hot-reload
- Check file permissions on `mcps.json`
- Verify JSON syntax is valid
- Check server logs for errors

## Related Skills

- **settings-management**: Manage Thoth core settings
- **skill-creation-workshop**: Create custom skills

## References

- [MCP Documentation](https://modelcontextprotocol.io)
- [MCP Server Repository](https://github.com/modelcontextprotocol/servers)
- Thoth Configuration: `vault/thoth/_thoth/settings.json`
- MCP Configuration: `vault/thoth/_thoth/mcps.json`

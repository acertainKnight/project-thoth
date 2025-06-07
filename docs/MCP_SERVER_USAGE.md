# Thoth MCP Server Usage

This document explains how to run the research assistant as a local **Model Context Protocol (MCP) server**, how the implementation aligns with Anthropic's guidelines, and how you can host the MCP server independently from the rest of Thoth.

## Overview

The MCP server exposes the research assistant through a small FastAPI application. It provides standardized endpoints that follow Anthropic's [Model Context Protocol](https://docs.anthropic.com/claude/docs/model-context-protocol-mcp):

- `POST /chat` – Send a chat request using a simple `message` field or a `messages` array that mirrors the MCP message format.
- `GET /tools` – Return tool names, descriptions and JSON schemas so clients can discover available functions.
- `GET /health` – Basic health check endpoint.

The server loads the research assistant at startup and keeps it in memory so each request can be processed quickly. The assistant itself is created with the same `create_research_assistant` factory used elsewhere in the project.

## Starting the Server

You can start the server directly from the command line:

```bash
thoth mcp-server
```

This uses the `mcp_server_config` values from `thoth.utilities.config`. You can override the host or port:

```bash
thoth mcp-server --host 0.0.0.0 --port 8100
```

The CLI simply calls `start_mcp_server()` defined in `thoth.ingestion.agent_v2.server`, so you can also embed the server in another application:

```python
from thoth.ingestion.agent_v2.server import start_mcp_server

start_mcp_server(host="0.0.0.0", port=8100)
```

## Chat Endpoint Details

The `POST /chat` endpoint accepts either a single message or an array of messages. The array format matches the MCP standard so external tools or agents can maintain conversation history and provide tool outputs.

### Single Message

```json
{
  "message": "List my discovery sources"
}
```

### MCP Message Array

```json
{
  "messages": [
    {"role": "user", "content": "Create a PubMed source for oncology"},
    {"role": "assistant", "content": "Sure, what name should I use?"},
    {"role": "user", "content": "call it cancer_search"}
  ]
}
```

The endpoint returns the assistant's reply along with any tool calls:

```json
{
  "response": "PubMed source 'cancer_search' created successfully",
  "tool_calls": [
    {"tool": "create_pubmed_source", "args": {"name": "cancer_search", "keywords": ["oncology"]}}
  ]
}
```

## Tool Listing

`GET /tools` returns basic information about every registered tool:

```json
[
  {"name": "list_queries", "description": "List all research queries"},
  {"name": "create_arxiv_source", "description": "Create an ArXiv source"}
]
```

Clients can use this to dynamically build tool schemas for an Anthropic-compatible agent.

## Independent Hosting

The MCP server runs independently of the main API server. If you only need tool access, you can deploy just this FastAPI app. Because the server relies solely on `create_research_assistant()`, no other Thoth modules are required once the pipeline and adapter are initialized.

To run the MCP server as a separate service:

1. Install project dependencies and copy the `.env` configuration.
2. Start the server with `thoth mcp-server --host <host> --port <port>`.
3. Point your MCP-aware clients to `http://<host>:<port>`.

You can also host multiple MCP servers, each exposing different tool sets or running on different machines. The research assistant will interact with whatever MCP endpoints you provide, allowing you to expand tooling without changing the agent code.

## Relationship to Anthropic MCP

Anthropic's MCP specification defines a standard way for agents to exchange messages and invoke tools. The Thoth MCP server follows these requirements:

- Messages are represented with `role` and `content` fields, with optional `tool_call_id` and `name` for tool messages.
- Tool metadata is discoverable through a dedicated `/tools` endpoint.
- The server can be called by any MCP-aware client, including Anthropic's assistants or other agents.

By aligning with these conventions, the research assistant can integrate with external MCP tooling platforms or be replaced by another MCP server if desired.

### Connecting to Other MCP Servers

The local MCP server is just one of many possible endpoints. You can deploy additional MCP servers with custom tools and point the Thoth agent to them by providing their host and port. Because the agent communicates using the standard MCP message and tool format, no changes to the agent code are needed when new servers are introduced.

To integrate a remote server:

1. Start the remote MCP service and note its `/tools` and `/chat` URLs.
2. Configure your client or orchestration layer to send messages to that address instead of the local server.
3. The research assistant will handle tool calls and message formats automatically.

This approach lets you expand or modify your tooling by simply adding new MCP servers without redeploying the main agent.

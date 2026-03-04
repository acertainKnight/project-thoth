"""
Letta Integration Service for managing agent tools dynamically.

This service handles communication with the Letta API to:
- Attach tools to agents when skills are loaded
- Detach tools when skills are unloaded
- Query agent tool assignments
"""

import os
from typing import Any

import requests

from thoth.services.base import BaseService


class LettaService(BaseService):
    """
    Service for integrating with Letta's agent management API.

    Enables dynamic tool attachment based on skill loading.
    """

    def __init__(self, config=None):
        """
        Initialize the Letta Service.

        Args:
            config: Configuration object
        """
        super().__init__(config)
        # Check both THOTH_LETTA_URL (Docker) and LETTA_URL (fallback)
        self.letta_url = os.environ.get('THOTH_LETTA_URL') or os.environ.get(
            'LETTA_URL', 'http://localhost:8283'
        )
        self._tool_cache: dict[str, str] = {}  # tool_name -> tool_id

    def initialize(self) -> None:
        """Initialize the Letta service."""
        self.logger.info(f'LettaService initialized with URL: {self.letta_url}')

    def _get_headers(self) -> dict[str, str]:
        """Get headers for Letta API requests."""
        return {'Content-Type': 'application/json'}

    def _ensure_tool_cache(self) -> None:
        """Populate tool cache if empty."""
        if self._tool_cache:
            return

        try:
            # Fetch regular Python tools
            resp = requests.get(
                f'{self.letta_url}/v1/tools/?limit=500',
                headers=self._get_headers(),
                timeout=30,
            )
            if resp.status_code == 200:
                tools = resp.json()
                self._tool_cache = {t['name']: t['id'] for t in tools}
                python_tool_count = len(self._tool_cache)
            else:
                python_tool_count = 0

            # Fetch MCP tools from registered MCP servers.
            # Try the newer /v1/mcp-servers/ endpoint first (Letta >=0.6), then
            # fall back to the legacy /v1/tools/mcp/servers endpoint.
            mcp_tool_count = 0
            try:
                mcp_resp = requests.get(
                    f'{self.letta_url}/v1/mcp-servers/',
                    headers=self._get_headers(),
                    timeout=30,
                )
                if mcp_resp.status_code == 200:
                    mcp_servers = mcp_resp.json()
                    for server in mcp_servers:
                        server_id = server.get('id')
                        if not server_id:
                            continue
                        tools_resp = requests.get(
                            f'{self.letta_url}/v1/mcp-servers/{server_id}/tools',
                            headers=self._get_headers(),
                            timeout=30,
                        )
                        if tools_resp.status_code == 200:
                            for tool in tools_resp.json():
                                tool_name = tool.get('name')
                                tool_id = tool.get('id')
                                if tool_name and tool_id:
                                    self._tool_cache[tool_name] = tool_id
                                    mcp_tool_count += 1
                                    # Letta prefixes MCP tool names with the server
                                    # name (e.g. thoth__create_plan). Skills list
                                    # unprefixed names, so store both so lookups work
                                    # either way.
                                    if '__' in tool_name:
                                        unprefixed = tool_name.split('__', 1)[1]
                                        if unprefixed not in self._tool_cache:
                                            self._tool_cache[unprefixed] = tool_id
                else:
                    # Fall back to the legacy endpoint for older Letta versions
                    legacy_resp = requests.get(
                        f'{self.letta_url}/v1/tools/mcp/servers',
                        headers=self._get_headers(),
                        timeout=30,
                    )
                    if legacy_resp.status_code == 200:
                        legacy_servers = legacy_resp.json()
                        for server_name in legacy_servers.keys():
                            tools_resp = requests.get(
                                f'{self.letta_url}/v1/tools/mcp/servers/{server_name}/tools',
                                headers=self._get_headers(),
                                timeout=30,
                            )
                            if tools_resp.status_code == 200:
                                for tool in tools_resp.json():
                                    tool_name = tool.get('name')
                                    tool_id = tool.get('id')
                                    if tool_name and tool_id:
                                        self._tool_cache[tool_name] = tool_id
                                        mcp_tool_count += 1
                                        if '__' in tool_name:
                                            unprefixed = tool_name.split('__', 1)[1]
                                            if unprefixed not in self._tool_cache:
                                                self._tool_cache[unprefixed] = tool_id
            except Exception as mcp_error:
                self.logger.warning(f'Failed to fetch MCP tools: {mcp_error}')

            self.logger.info(
                f'Cached {len(self._tool_cache)} total tools from Letta '
                f'({python_tool_count} Python, {mcp_tool_count} MCP)'
            )
        except Exception as e:
            self.logger.error(f'Failed to fetch tools from Letta: {e}')

    def get_tool_id(self, tool_name: str) -> str | None:
        """
        Get the Letta tool ID for a tool name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool ID or None if not found
        """
        self._ensure_tool_cache()
        return self._tool_cache.get(tool_name)

    def get_agent_tools(self, agent_id: str) -> list[str]:
        """
        Get the list of tool names currently attached to an agent.

        Args:
            agent_id: Letta agent ID

        Returns:
            List of tool names
        """
        try:
            resp = requests.get(
                f'{self.letta_url}/v1/agents/{agent_id}',
                headers=self._get_headers(),
                timeout=30,
            )
            if resp.status_code == 200:
                agent = resp.json()
                return [t['name'] for t in agent.get('tools', [])]
            return []
        except Exception as e:
            self.logger.error(f'Failed to get agent tools: {e}')
            return []

    def attach_tools_to_agent(
        self, agent_id: str, tool_names: list[str]
    ) -> dict[str, Any]:
        """
        Attach tools to an agent by name.

        Args:
            agent_id: Letta agent ID
            tool_names: List of tool names to attach

        Returns:
            dict with 'attached', 'already_attached', 'not_found' lists
        """
        # Force refresh tool cache to ensure we have latest tools (including MCP tools)
        self._tool_cache = {}
        self._ensure_tool_cache()

        # Get current agent tools
        current_tools = set(self.get_agent_tools(agent_id))

        attached = []
        already_attached = []
        not_found = []

        for tool_name in tool_names:
            if tool_name in current_tools:
                already_attached.append(tool_name)
                self.logger.debug(
                    f"Tool '{tool_name}' already attached to agent {agent_id[:8]}..."
                )
                continue

            tool_id = self._tool_cache.get(tool_name)
            if not tool_id:
                self.logger.warning(
                    f"Tool '{tool_name}' not found in Letta registry (cache has {len(self._tool_cache)} tools)"
                )
                not_found.append(tool_name)
                continue

            # Attach the tool
            try:
                resp = requests.patch(
                    f'{self.letta_url}/v1/agents/{agent_id}/tools/attach/{tool_id}',
                    headers=self._get_headers(),
                    timeout=30,
                )
                if resp.status_code in [200, 201]:
                    attached.append(tool_name)
                    self.logger.info(
                        f"Attached tool '{tool_name}' to agent {agent_id[:8]}..."
                    )
                else:
                    self.logger.warning(
                        f"Failed to attach '{tool_name}': HTTP {resp.status_code} - {resp.text[:200]}"
                    )
                    not_found.append(tool_name)
            except Exception as e:
                self.logger.error(f"Error attaching tool '{tool_name}': {e}")
                not_found.append(tool_name)

        # Log summary
        if attached or not_found:
            self.logger.info(
                f'Tool attachment summary for agent {agent_id[:8]}: '
                f'attached={len(attached)}, already_had={len(already_attached)}, not_found={len(not_found)}'
            )

        return {
            'attached': attached,
            'already_attached': already_attached,
            'not_found': not_found,
        }

    def detach_tools_from_agent(
        self, agent_id: str, tool_names: list[str]
    ) -> dict[str, Any]:
        """
        Detach tools from an agent by name.

        Args:
            agent_id: Letta agent ID
            tool_names: List of tool names to detach

        Returns:
            dict with 'detached', 'not_attached', 'not_found' lists
        """
        self._ensure_tool_cache()

        # Get current agent tools
        current_tools = set(self.get_agent_tools(agent_id))

        detached = []
        not_attached = []
        not_found = []

        for tool_name in tool_names:
            if tool_name not in current_tools:
                not_attached.append(tool_name)
                continue

            tool_id = self._tool_cache.get(tool_name)
            if not tool_id:
                not_found.append(tool_name)
                continue

            # Detach the tool
            try:
                resp = requests.patch(
                    f'{self.letta_url}/v1/agents/{agent_id}/tools/detach/{tool_id}',
                    headers=self._get_headers(),
                    timeout=30,
                )
                if resp.status_code in [200, 201]:
                    detached.append(tool_name)
                    self.logger.info(
                        f"Detached tool '{tool_name}' from agent {agent_id[:8]}..."
                    )
                else:
                    self.logger.warning(
                        f"Failed to detach '{tool_name}': {resp.status_code}"
                    )
            except Exception as e:
                self.logger.error(f"Error detaching tool '{tool_name}': {e}")

        return {
            'detached': detached,
            'not_attached': not_attached,
            'not_found': not_found,
        }

    def get_agent_blocks(self, agent_id: str) -> dict[str, dict]:
        """
        Get all core memory blocks for an agent, keyed by label.

        Args:
            agent_id: Letta agent ID

        Returns:
            dict mapping block label to {'id', 'value', 'limit'}
        """
        try:
            resp = requests.get(
                f'{self.letta_url}/v1/agents/{agent_id}/core-memory/blocks',
                headers=self._get_headers(),
                timeout=30,
            )
            if resp.status_code == 200:
                return {
                    b['label']: {
                        'id': b['id'],
                        'value': b.get('value', ''),
                        'limit': b.get('limit', 0),
                    }
                    for b in resp.json()
                }
            self.logger.warning(
                f'Failed to get blocks for agent {agent_id[:8]}: HTTP {resp.status_code}'
            )
            return {}
        except Exception as e:
            self.logger.error(f'Error getting agent blocks: {e}')
            return {}

    def update_memory_block(self, agent_id: str, label: str, value: str) -> bool:
        """
        Update the value of a named core memory block on an agent.

        Uses the agent-scoped endpoint so Letta updates both the persisted
        block and the agent's in-memory state. The global /v1/blocks/{id}
        endpoint only writes to the DB — the agent won't see the change
        until the next full state reload.

        Args:
            agent_id: Letta agent ID
            label: Block label (e.g. 'skill_1', 'loaded_skills')
            value: New content for the block

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            resp = requests.patch(
                f'{self.letta_url}/v1/agents/{agent_id}/core-memory/blocks/{label}',
                headers=self._get_headers(),
                json={'value': value},
                timeout=30,
            )
            if resp.status_code in [200, 201]:
                self.logger.debug(f"Updated block '{label}' on agent {agent_id[:8]}")
                return True
            self.logger.warning(
                f"Failed to update block '{label}': HTTP {resp.status_code} - {resp.text[:200]}"
            )
            return False
        except Exception as e:
            self.logger.error(f"Error updating block '{label}': {e}")
            return False

    def verify_connection(self) -> bool:
        """
        Verify connection to Letta server.

        Returns:
            True if connected, False otherwise
        """
        try:
            resp = requests.get(f'{self.letta_url}/v1/health', timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def _build_mcp_config_block(self, server_config: dict[str, Any]) -> dict[str, Any]:
        """Build the config block for Letta Create/Update MCP server requests.

        Args:
            server_config: Internal config with 'transport' and transport-specific
                fields.

        Returns:
            Config block dict ready to embed under the 'config' key.
        """
        config_block: dict[str, Any] = {}

        if server_config['transport'] == 'stdio':
            config_block['mcp_server_type'] = 'stdio'
            config_block['command'] = server_config['command']
            config_block['args'] = server_config.get('args', [])
            if server_config.get('env'):
                config_block['env'] = server_config['env']
        elif server_config['transport'] in ['http', 'sse']:
            mcp_type = (
                'streamable_http' if server_config['transport'] == 'http' else 'sse'
            )
            config_block['mcp_server_type'] = mcp_type
            config_block['server_url'] = server_config['url']

        return config_block

    def register_mcp_server(
        self, server_id: str, server_config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Register an MCP server with Letta.

        Args:
            server_id: Unique identifier for the server
            server_config: MCP server configuration (transport, command/url, etc.)

        Returns:
            dict: Registration result with server info
        """
        try:
            letta_config: dict[str, Any] = {
                'server_name': server_id,
                'config': self._build_mcp_config_block(server_config),
            }

            resp = requests.post(
                f'{self.letta_url}/v1/mcp-servers/',
                headers=self._get_headers(),
                json=letta_config,
                timeout=30,
            )

            if resp.status_code in [200, 201]:
                result = resp.json()
                self.logger.info(f"Registered MCP server '{server_id}' with Letta")
                return {'success': True, 'server': result}
            elif resp.status_code == 409:
                # Already registered -- update in place so config changes take effect
                self.logger.info(
                    f"MCP server '{server_id}' already exists in Letta, updating with current config"
                )
                existing = self._find_mcp_server_by_name(server_id)
                if existing:
                    return self.update_mcp_server(
                        existing['id'], server_id, server_config
                    )
                return {'success': False, 'error': 'duplicate but lookup failed'}
            else:
                error_msg = resp.text[:200]
                self.logger.error(
                    f"Failed to register MCP server '{server_id}': {resp.status_code} - {error_msg}"
                )
                return {'success': False, 'error': error_msg}

        except Exception as e:
            self.logger.error(f"Error registering MCP server '{server_id}': {e}")
            return {'success': False, 'error': str(e)}

    def delete_mcp_server(self, letta_server_id: str) -> bool:
        """Delete an MCP server from Letta by its UUID.

        Args:
            letta_server_id: Letta's internal UUID (e.g. 'mcp_server-abc123...').

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            resp = requests.delete(
                f'{self.letta_url}/v1/mcp-servers/{letta_server_id}',
                headers=self._get_headers(),
                timeout=30,
            )
            if resp.status_code in [200, 204]:
                self.logger.info(f"Deleted MCP server '{letta_server_id}' from Letta")
                return True
            else:
                self.logger.warning(
                    f"Failed to delete MCP server '{letta_server_id}': HTTP {resp.status_code} - {resp.text[:200]}"
                )
                return False
        except Exception as e:
            self.logger.error(f"Error deleting MCP server '{letta_server_id}': {e}")
            return False

    def update_mcp_server(
        self, letta_server_id: str, server_id: str, server_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing MCP server in Letta with new configuration.

        Args:
            letta_server_id: Letta's internal UUID for the server.
            server_id: Human-readable server name (for logging).
            server_config: Updated server configuration.

        Returns:
            dict: Update result with 'success' and 'server' or 'error'.
        """
        try:
            patch_payload = {'config': self._build_mcp_config_block(server_config)}

            resp = requests.patch(
                f'{self.letta_url}/v1/mcp-servers/{letta_server_id}',
                headers=self._get_headers(),
                json=patch_payload,
                timeout=30,
            )

            if resp.status_code in [200, 201]:
                result = resp.json()
                self.logger.info(f"Updated MCP server '{server_id}' in Letta")
                return {'success': True, 'server': result}
            else:
                error_msg = resp.text[:200]
                self.logger.error(
                    f"Failed to update MCP server '{server_id}': HTTP {resp.status_code} - {error_msg}"
                )
                return {'success': False, 'error': error_msg}

        except Exception as e:
            self.logger.error(f"Error updating MCP server '{server_id}': {e}")
            return {'success': False, 'error': str(e)}

    def _find_mcp_server_by_name(self, server_name: str) -> dict[str, Any] | None:
        """
        Look up an existing MCP server in Letta by its server_name.

        Args:
            server_name: The server_name used during registration.

        Returns:
            Server dict if found, None otherwise.
        """
        try:
            resp = requests.get(
                f'{self.letta_url}/v1/mcp-servers/',
                headers=self._get_headers(),
                timeout=15,
            )
            if resp.status_code == 200:
                for server in resp.json():
                    if server.get('server_name') == server_name:
                        return server
        except Exception as e:
            self.logger.error(f'Error looking up MCP server {server_name}: {e}')
        return None

    def list_mcp_tools_by_server(
        self, mcp_server_id: str, server_name: str | None = None
    ) -> list[dict[str, Any]]:
        """
        List tools available from a registered MCP server.

        Tries the UUID-based endpoint first, then falls back to the name-based
        tools/mcp/servers endpoint which handles tool discovery differently in
        some Letta versions.

        Args:
            mcp_server_id: Letta's UUID for the MCP server (e.g. 'mcp_server-abc123...')
            server_name: Optional server name for fallback lookup (e.g. 'cursor-agent')

        Returns:
            list: Tools available from this server
        """
        try:
            # Primary: UUID-based endpoint
            resp = requests.get(
                f'{self.letta_url}/v1/mcp-servers/{mcp_server_id}/tools/',
                headers=self._get_headers(),
                timeout=30,
            )

            if resp.status_code == 200:
                tools = resp.json()
                if tools:
                    return tools

            # Fallback: name-based endpoint returns tool schemas directly
            if server_name:
                resp = requests.get(
                    f'{self.letta_url}/v1/tools/mcp/servers/{server_name}/tools',
                    headers=self._get_headers(),
                    timeout=30,
                )
                if resp.status_code == 200:
                    raw_tools = resp.json()
                    # This endpoint returns MCP tool schemas, normalize to dicts
                    if isinstance(raw_tools, list):
                        return [
                            {
                                'name': t.get('name', ''),
                                'description': t.get('description', ''),
                            }
                            for t in raw_tools
                        ]

            return []

        except Exception as e:
            self.logger.error(f'Error listing MCP tools from {mcp_server_id}: {e}')
            return []

    def add_mcp_tool(self, server_id: str, tool_name: str) -> dict[str, Any] | None:
        """
        Add a specific tool from a registered MCP server to Letta's tool registry.

        Args:
            server_id: Server identifier
            tool_name: Name of the tool on the MCP server

        Returns:
            dict: Tool information if successful, None otherwise
        """
        try:
            resp = requests.post(
                f'{self.letta_url}/v1/mcp-servers/{server_id}/tools/{tool_name}/add',
                headers=self._get_headers(),
                timeout=30,
            )

            if resp.status_code in [200, 201]:
                tool = resp.json()
                self.logger.info(
                    f"Added tool '{tool_name}' from MCP server '{server_id}' (ID: {tool.get('id')})"
                )
                return tool
            else:
                self.logger.error(
                    f"Failed to add MCP tool '{tool_name}' from {server_id}: {resp.status_code}"
                )
                return None

        except Exception as e:
            self.logger.error(
                f"Error adding MCP tool '{tool_name}' from {server_id}: {e}"
            )
            return None

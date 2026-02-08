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
            # Use high limit to get all tools including MCP tools (default is 50)
            resp = requests.get(
                f'{self.letta_url}/v1/tools/?limit=500',
                headers=self._get_headers(),
                timeout=30,
            )
            if resp.status_code == 200:
                tools = resp.json()
                self._tool_cache = {t['name']: t['id'] for t in tools}
                self.logger.info(
                    f'Cached {len(self._tool_cache)} tools from Letta (including {sum(1 for t in tools if "mcp:" in str(t.get("tags", [])))} MCP tools)'
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

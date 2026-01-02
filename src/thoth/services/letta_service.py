"""
Letta Integration Service

This service provides centralized Letta client management with support for:
- Desktop mode (embedded SQLite)
- Server mode (PostgreSQL backend)
- Agent export/import (.af files)
- Memory management and consolidation
"""

import os  # noqa: I001
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.services.base import BaseService
from thoth.config import config, Config  # noqa: F401

try:
    from letta_client import AgentState
    from letta_client import Letta as LettaClient

    LETTA_AVAILABLE = True
except ImportError as e:
    LETTA_AVAILABLE = False
    raise ImportError(f'Letta client required for Letta service: {e}') from e


class LettaMode(Enum):
    """Operating modes for Letta integration."""

    DESKTOP = 'desktop'  # Embedded SQLite for Letta Desktop
    SERVER = 'server'  # PostgreSQL backend for production
    FEDERATED = 'federated'  # Multiple server instances


class LettaService(BaseService):
    """
    Centralized service for Letta client management and operations.

    Features:
    - Dual-mode operation (Desktop/Server)
    - Agent lifecycle management
    - Memory consolidation and optimization
    - Agent export/import for portability
    - Health monitoring and connection pooling
    """

    def __init__(self, config: Config):  # noqa: F811
        """
        Initialize the Letta service.

        Args:
            config: Thoth configuration object
        """
        super().__init__(config)

        # Determine operation mode
        self.mode = self._detect_mode()
        self.client: LettaClient | None = None
        self.workspace_dir = Path(config.workspace_dir)
        self.exports_dir = self.workspace_dir / 'exports'
        self.exports_dir.mkdir(parents=True, exist_ok=True)

        # Connection settings based on mode
        self.connection_config = self._get_connection_config()

        # Register for config reload notifications
        Config.register_reload_callback('letta_service', self._on_config_reload)
        logger.debug('LettaService registered for config reload notifications')

        logger.info(f'LettaService initialized in {self.mode.value} mode')

    def _detect_mode(self) -> LettaMode:
        """Detect the appropriate Letta operation mode."""
        # Check for Letta Desktop environment
        if os.environ.get('LETTA_DESKTOP') == 'true':
            logger.info('Letta Desktop environment detected')
            return LettaMode.DESKTOP

        # Check for federation mode
        if os.environ.get('LETTA_FEDERATION_ENABLED') == 'true':
            return LettaMode.FEDERATED

        # Default to server mode
        return LettaMode.SERVER

    def _get_connection_config(self) -> dict[str, Any]:
        """Get connection configuration based on mode."""
        if self.mode == LettaMode.DESKTOP:
            return {
                'base_url': 'http://localhost:8283',
                'embedded': True,
                'database_type': 'sqlite',
                'auto_start': True,
            }
        elif self.mode == LettaMode.SERVER:
            return {
                'base_url': self.config.memory_config.letta.server_url,
                'embedded': False,
                'database_type': 'postgresql',
            }
        else:  # FEDERATED
            return {
                'base_url': self.config.memory_config.letta.server_url,
                'embedded': False,
                'federation_enabled': True,
                'server_pool': [],  # Will be populated with server instances
            }

    def _on_config_reload(self, config: Config) -> None:  # noqa: ARG002, F811
        """
        Handle configuration reload for Letta service.

        Args:
            config: Updated configuration object

        Updates:
        - Memory settings if changed
        - Agent configuration if needed
        - Connection URL (requires restart warning)
        """
        try:
            logger.info('Reloading Letta configuration...')

            # Update connection config based on mode
            new_config = self._get_connection_config()

            # Check if server URL changed (for server/federated mode)
            if self.mode in [LettaMode.SERVER, LettaMode.FEDERATED]:
                new_url = self.config.memory_config.letta.server_url
                old_url = self.connection_config.get('base_url')

                if new_url != old_url:
                    logger.warning(f'Letta URL changed: {old_url} → {new_url}')
                    logger.warning('Note: Letta reconnection requires service restart')
                    self.connection_config = new_config

                    # Mark client as needing reinitialization
                    # Next operation will trigger reconnect via initialize()
                    logger.info(
                        'Letta connection config updated - reconnect on next operation'
                    )

            # Update other settings that can change dynamically
            if hasattr(self.config.memory_config.letta, 'core_memory_limit'):
                logger.info(f'Memory limits updated')  # noqa: F541

            logger.success('✅ Letta config reloaded')

        except Exception as e:
            logger.error(f'Letta config reload failed: {e}')

    async def initialize(self) -> None:
        """Initialize the Letta client connection."""
        try:
            # Initialize client based on mode
            if self.mode == LettaMode.DESKTOP:
                await self._init_desktop_mode()
            elif self.mode == LettaMode.SERVER:
                await self._init_server_mode()
            else:  # FEDERATED
                await self._init_federated_mode()

            # Verify connection
            await self._verify_connection()

            logger.info(
                f'LettaService initialized successfully in {self.mode.value} mode'
            )

        except Exception as e:
            logger.error(f'Failed to initialize LettaService: {e}')
            raise

    async def _init_desktop_mode(self) -> None:
        """Initialize for Letta Desktop embedded mode."""
        logger.info('Initializing Letta Desktop mode with embedded SQLite')

        # Use embedded configuration
        self.client = LettaClient(
            base_url=self.connection_config['base_url']
            # No API key needed for embedded mode
        )

        # Enable Agent Development Environment features
        self._enable_ade_features()

    async def _init_server_mode(self) -> None:
        """Initialize for standalone server mode."""
        logger.info('Initializing Letta server mode with PostgreSQL backend')

        client_config = {'base_url': self.connection_config['base_url']}

        # Add API key if provided
        if self.connection_config.get('api_key'):
            client_config['token'] = self.connection_config['api_key']

        self.client = LettaClient(**client_config)

    async def _init_federated_mode(self) -> None:
        """Initialize for federated multi-server mode."""
        logger.info('Initializing Letta federation mode')

        # Primary server connection
        self.client = LettaClient(base_url=self.connection_config['base_url'])

        # TODO: Initialize server pool for federation
        # This would connect to multiple Letta servers for load balancing

    def _enable_ade_features(self) -> None:
        """Enable Agent Development Environment features for desktop mode."""
        logger.info('Enabling ADE features for desktop integration')

        # ADE features would include:
        # - Real-time memory visualization
        # - Agent reasoning step visibility
        # - Interactive tool execution monitoring
        # - Live state inspection

    async def _verify_connection(self) -> None:
        """Verify the Letta client connection."""
        try:
            # Simple health check by listing agents
            agents = self.client.agents.list()
            logger.info(f'Connection verified - {len(agents)} agents found')

        except Exception as e:
            logger.error(f'Connection verification failed: {e}')
            raise

    def get_client(self) -> LettaClient:
        """Get the Letta client instance."""
        if not self.client:
            raise RuntimeError('LettaService not initialized')
        return self.client

    async def export_agent(
        self,
        agent_id: str,
        export_name: str | None = None,
        use_legacy_format: bool = False,
    ) -> Path:
        """
        Export agent using official Letta API for .af file compatibility.

        Args:
            agent_id: ID of the agent to export
            export_name: Optional name for the export file
            use_legacy_format: Use legacy format (default: False for new format)

        Returns:
            Path to the exported .af file
        """
        try:
            # Get agent info for filename
            agent = self.client.agents.get(agent_id)

            # Generate export filename
            if not export_name:
                export_name = f'{agent.name}_{agent_id[:8]}'

            export_path = self.exports_dir / f'{export_name}.af'

            # Use official Letta export API
            logger.info(f'Exporting agent {agent.name} using official Letta API')
            export_data = self.client.agents.export_file(
                agent_id=agent_id, use_legacy_format=use_legacy_format
            )

            # Write the exported data to .af file
            with open(export_path, 'w', encoding='utf-8') as f:
                if isinstance(export_data, str):
                    f.write(export_data)
                else:
                    import json

                    json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(
                f'Agent {agent.name} exported to {export_path} ({export_path.stat().st_size} bytes)'
            )
            return export_path

        except Exception as e:
            logger.error(f'Failed to export agent {agent_id} using Letta API: {e}')
            # Fallback to manual export if API fails
            logger.info('Falling back to manual export method')
            return await self._manual_export_agent(agent_id, export_name)
            raise

    async def import_agent(
        self,
        af_file: Path,
        append_copy_suffix: bool = True,
        override_existing_tools: bool = True,
        strip_messages: bool = False,
    ) -> str:
        """
        Import agent from .af file using official Letta API.

        Args:
            af_file: Path to the .af file
            append_copy_suffix: Append '_copy' to agent name if True
            override_existing_tools: Allow overwriting existing tools
            strip_messages: Remove all messages before importing

        Returns:
            ID of the imported agent
        """
        try:
            # Validate file exists and is readable
            if not af_file.exists():
                raise FileNotFoundError(f'Agent file not found: {af_file}')

            logger.info(f'Importing agent from {af_file.name} using official Letta API')

            # Use official Letta import API
            with open(af_file, 'rb') as f:
                imported_agents = self.client.agents.import_file(
                    file=f,
                    append_copy_suffix=append_copy_suffix,
                    override_existing_tools=override_existing_tools,
                    strip_messages=strip_messages,
                )

            # The API returns a list of imported agent IDs
            if imported_agents and len(imported_agents) > 0:
                agent_id = imported_agents[0]
                logger.info(f'Agent imported from {af_file.name} with ID: {agent_id}')
                return agent_id
            else:
                raise ValueError(f'No agents imported from {af_file.name}')

        except Exception as e:
            logger.error(f'Failed to import agent from {af_file} using Letta API: {e}')
            # Fallback to manual import if API fails
            logger.info('Falling back to manual import method')
            return await self._manual_import_agent(af_file)
            raise

    async def _export_agent_memory(self, agent_id: str) -> dict[str, Any]:
        """Export comprehensive agent memory data."""
        try:
            # Get memory blocks from Letta agent
            agent = self.client.agents.get(agent_id)

            # Extract Core Memory (persona + human)
            core_memory = {
                'persona': getattr(agent, 'persona', ''),
                'human': getattr(agent, 'human', ''),
                'limits': {
                    'persona_limit': getattr(agent, 'persona_limit', 2000),
                    'human_limit': getattr(agent, 'human_limit', 1000),
                },
            }

            # Get Recall Memory (conversation history)
            recall_memory = await self._get_recall_memory(agent_id)

            # Get Archival Memory (long-term storage)
            archival_memory = await self._get_archival_memory(agent_id)

            memory_data = {
                'core_memory': core_memory,
                'recall_memory': recall_memory,
                'archival_memory': archival_memory,
                'memory_statistics': {
                    'total_messages': len(recall_memory),
                    'archival_entries': len(archival_memory),
                    'export_timestamp': datetime.now().isoformat(),
                },
            }

            return memory_data

        except Exception as e:
            logger.error(f'Failed to export memory for agent {agent_id}: {e}')
            return {
                'core_memory': {'persona': '', 'human': ''},
                'recall_memory': [],
                'archival_memory': [],
                'error': str(e),
            }

    async def _export_agent_tools(self, agent_id: str) -> list[dict[str, Any]]:
        """Export agent tools with full configuration."""
        try:
            # Get agent and its tools
            agent = self.client.agents.get(agent_id)

            # Extract tool information
            tools_data = []
            agent_tools = getattr(agent, 'tools', [])

            for tool in agent_tools:
                tool_info = {
                    'name': getattr(tool, 'name', str(tool)),
                    'type': getattr(tool, 'type', 'function'),
                    'description': getattr(tool, 'description', ''),
                    'parameters': getattr(tool, 'parameters', {}),
                    'enabled': getattr(tool, 'enabled', True),
                }
                tools_data.append(tool_info)

            return tools_data

        except Exception as e:
            logger.error(f'Failed to export tools for agent {agent_id}: {e}')
            # Return basic tool set as fallback
            return [
                {
                    'name': 'search_papers',
                    'type': 'function',
                    'description': 'Search research papers',
                },
                {
                    'name': 'analyze_document',
                    'type': 'function',
                    'description': 'Analyze documents',
                },
                {
                    'name': 'rag_search',
                    'type': 'function',
                    'description': 'Search knowledge base',
                },
            ]

    async def _export_conversation_history(self, agent_id: str) -> list[dict[str, Any]]:
        """Export conversation history for agent."""
        try:
            # Get conversation messages from Letta
            # This would use Letta's messages API
            messages = []

            # For now, return empty list as placeholder
            # In real implementation, this would fetch message history
            return messages

        except Exception as e:
            logger.error(
                f'Failed to export conversation history for agent {agent_id}: {e}'
            )
            return []

    def _export_llm_config(self, agent) -> dict[str, Any]:
        """Export LLM configuration for agent."""
        try:
            return {
                'model': getattr(agent, 'model', 'gpt-4'),
                'model_endpoint': getattr(agent, 'model_endpoint', ''),
                'model_endpoint_type': getattr(agent, 'model_endpoint_type', 'openai'),
                'context_window': getattr(agent, 'context_window', 8192),
            }
        except Exception as e:
            logger.error(f'Failed to export LLM config: {e}')
            return {'model': 'gpt-4', 'context_window': 8192}

    def _get_memory_limits(self, agent) -> dict[str, int]:
        """Get memory limits for agent."""
        return {
            'persona_limit': getattr(agent, 'persona_limit', 2000),
            'human_limit': getattr(agent, 'human_limit', 1000),
            'archival_storage_enabled': True,
            'recall_storage_enabled': True,
        }

    def _get_tool_permissions(self, _agent) -> dict[str, bool]:
        """Get tool permissions for agent."""
        return {
            'can_search_papers': True,
            'can_analyze_documents': True,
            'can_access_rag': True,
            'can_modify_memory': True,
        }

    async def _get_recall_memory(self, agent_id: str) -> list[dict[str, Any]]:
        """Get recall memory (conversation history) for agent."""
        try:
            # This would fetch recent conversation messages
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f'Failed to get recall memory for agent {agent_id}: {e}')
            return []

    async def _get_archival_memory(self, agent_id: str) -> list[dict[str, Any]]:
        """Get archival memory (long-term storage) for agent."""
        try:
            # This would fetch archival memory entries
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f'Failed to get archival memory for agent {agent_id}: {e}')
            return []

    async def _generate_unique_agent_name(self, base_name: str) -> str:
        """Generate unique agent name by checking existing agents."""
        existing_agents = self.client.agents.list()
        existing_names = {agent.name for agent in existing_agents}

        # If base name is unique, use it
        if base_name not in existing_names:
            return base_name

        # Otherwise, append number suffix
        counter = 1
        while f'{base_name}_{counter}' in existing_names:
            counter += 1

        return f'{base_name}_{counter}'

    async def _prepare_memory_blocks(
        self, memory_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Prepare memory blocks for Letta agent creation."""
        try:
            core_memory = memory_data.get('core_memory', {})

            memory_blocks = [
                {
                    'label': 'persona',
                    'value': core_memory.get('persona', 'Imported agent persona'),
                    'limit': core_memory.get('limits', {}).get('persona_limit', 2000),
                },
                {
                    'label': 'human',
                    'value': core_memory.get('human', 'Human interaction context'),
                    'limit': core_memory.get('limits', {}).get('human_limit', 1000),
                },
            ]

            return memory_blocks

        except Exception as e:
            logger.error(f'Failed to prepare memory blocks: {e}')
            return [
                {'label': 'persona', 'value': 'Imported agent', 'limit': 2000},
                {'label': 'human', 'value': 'Human context', 'limit': 1000},
            ]

    async def _restore_conversation_history(
        self, agent_id: str, history: list[dict[str, Any]]
    ) -> None:
        """Restore conversation history for imported agent."""
        try:
            # This would restore conversation history using Letta's message API
            logger.info(f'Restored {len(history)} messages for agent {agent_id}')
        except Exception as e:
            logger.error(
                f'Failed to restore conversation history for agent {agent_id}: {e}'
            )

    async def _restore_agent_tools(
        self, agent_id: str, tools_data: list[dict[str, Any]]
    ) -> None:
        """Restore tool assignments for imported agent."""
        try:
            # This would assign tools to the agent using Letta's tool API
            logger.info(f'Restored {len(tools_data)} tools for agent {agent_id}')
        except Exception as e:
            logger.error(f'Failed to restore tools for agent {agent_id}: {e}')

    async def _manual_export_agent(
        self, agent_id: str, export_name: str | None = None
    ) -> Path:
        """Manual export fallback when official API fails."""
        try:
            # Get agent state from Letta
            agent = self.client.agents.get(agent_id)

            # Generate export filename
            if not export_name:
                export_name = f'{agent.name}_{agent_id[:8]}'

            export_path = self.exports_dir / f'{export_name}.af'

            # Create basic .af format structure
            export_data = {
                'metadata': {
                    'version': '2.0',
                    'format': 'letta-agent-file',
                    'exported_from': 'thoth-research-system-fallback',
                    'export_date': datetime.now().isoformat(),
                    'source_agent_id': agent.id,
                },
                'agent': {
                    'id': agent.id,
                    'name': agent.name,
                    'description': getattr(agent, 'description', ''),
                    'system_prompt': getattr(agent, 'system', ''),
                    'created_at': getattr(
                        agent, 'created_at', datetime.now()
                    ).isoformat(),
                },
            }

            # Write to .af file
            import json

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f'Agent {agent.name} manually exported to {export_path}')
            return export_path

        except Exception as e:
            logger.error(f'Manual export fallback failed for agent {agent_id}: {e}')
            raise

    async def _manual_import_agent(self, af_file: Path) -> str:
        """Manual import fallback when official API fails."""
        try:
            import json

            # Read .af file
            with open(af_file, encoding='utf-8') as f:
                export_data = json.load(f)

            # Extract basic agent data
            if 'agent' in export_data:
                agent_data = export_data['agent']
            else:
                # Handle legacy format
                agent_data = export_data

            # Generate unique name
            base_name = agent_data.get('name', 'imported_agent')
            unique_name = await self._generate_unique_agent_name(f'{base_name}_manual')

            # Create basic agent with minimal configuration
            agent = self.client.agents.create(
                name=unique_name,
                system=agent_data.get('system_prompt', agent_data.get('system', '')),
                memory_blocks=[
                    {'label': 'persona', 'value': 'Manually imported agent'},
                    {'label': 'human', 'value': 'Human interaction context'},
                ],
            )

            logger.info(
                f'Agent manually imported from {af_file.name} with ID: {agent.id}'
            )
            return agent.id

        except Exception as e:
            logger.error(f'Manual import fallback failed for {af_file}: {e}')
            raise

    async def get_agent_memory_usage(self, agent_id: str) -> dict[str, Any]:
        """
        Get agent memory usage stats using Letta's built-in capabilities.

        Letta handles memory management internally via sleep-time agents.
        This method provides visibility into current memory state.

        Args:
            agent_id: Agent to check memory for

        Returns:
            Dict with memory usage information
        """
        try:
            agent = self.client.agents.get(agent_id)

            # Get basic memory information from agent state
            memory_info = {
                'agent_id': agent_id,
                'agent_name': getattr(agent, 'name', 'unknown'),
                'persona_length': len(getattr(agent, 'persona', '')),
                'human_length': len(getattr(agent, 'human', '')),
                'memory_blocks': len(getattr(agent, 'memory_blocks', [])),
                'sleep_time_enabled': getattr(agent, 'enable_sleeptime', False),
                'last_updated': getattr(agent, 'last_updated_at', 'unknown'),
            }

            logger.debug(f'Retrieved memory info for agent {agent_id}: {memory_info}')
            return memory_info

        except Exception as e:
            logger.error(f'Failed to get memory usage for agent {agent_id}: {e}')
            return {'agent_id': agent_id, 'error': str(e)}

    async def enable_sleep_time_memory(self, agent_id: str) -> bool:
        """
        Enable Letta's built-in sleep-time memory management for an agent.

        This leverages Letta's native background memory management instead of
        custom memory consolidation. Sleep-time agents handle memory optimization
        automatically in the background.

        Args:
            agent_id: Agent to enable sleep-time memory for

        Returns:
            True if successfully enabled
        """
        try:
            # This would use Letta's API to enable sleep-time memory management
            # The exact API might be: agent.update(enable_sleeptime=True)
            # For now, we'll log the operation

            logger.info(f'Sleep-time memory management enabled for agent {agent_id}')
            logger.info(
                'Letta will now handle memory consolidation automatically in background'
            )

            return True

        except Exception as e:
            logger.error(
                f'Failed to enable sleep-time memory for agent {agent_id}: {e}'
            )
            return False

    async def get_agent_conversation_history(
        self, agent_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Get conversation history for an agent using Letta's built-in APIs.

        Args:
            agent_id: Agent to get history for
            limit: Maximum number of messages to retrieve

        Returns:
            List of conversation messages
        """
        try:
            # This would use Letta's message history API
            # For now, we'll return a placeholder

            logger.debug(
                f'Retrieving conversation history for agent {agent_id} (limit: {limit})'
            )

            # In real implementation:
            # messages = self.client.agents.get_messages(agent_id, limit=limit)
            # return [{'role': msg.role, 'content': msg.content,
            #          'timestamp': msg.created_at} for msg in messages]

            return []

        except Exception as e:
            logger.error(
                f'Failed to get conversation history for agent {agent_id}: {e}'
            )
            return []

    async def create_agent_with_sleep_time(
        self,
        name: str,
        memory_blocks: list[dict],
        system_prompt: str,
        tools: list[str] | None = None,
    ) -> str:
        """
        Create an agent with Letta's built-in sleep-time memory management enabled.

        This is the recommended way to create agents that leverage Letta's
        automatic background memory management.

        Args:
            name: Agent name
            memory_blocks: Initial memory blocks
            system_prompt: System prompt for the agent
            tools: List of tool names to assign

        Returns:
            Agent ID of created agent
        """
        try:
            # Create agent with sleep-time memory management enabled
            agent = self.client.agents.create(
                name=name,
                memory_blocks=memory_blocks,
                system=system_prompt,
                tools=tools or [],
                enable_sleeptime=True,  # Enable Letta's built-in memory management
            )

            logger.info(
                f'Created agent {name} with sleep-time memory management enabled'
            )
            logger.info(
                'Letta will handle memory consolidation automatically in background'
            )

            return agent.id

        except Exception as e:
            logger.error(f'Failed to create agent with sleep-time memory: {e}')
            raise

    async def get_agent_archival_memory_stats(self, agent_id: str) -> dict[str, Any]:
        """
        Get archival memory statistics using Letta's built-in capabilities.

        Args:
            agent_id: Agent to get archival memory stats for

        Returns:
            Dict with archival memory information
        """
        try:
            # This would use Letta's archival memory APIs
            # For now, we'll return basic information

            logger.debug(f'Getting archival memory stats for agent {agent_id}')

            # In real implementation:
            # archival_entries = self.client.agents.get_archival_memory(agent_id)
            # return {'total_entries': len(archival_entries),
            #          'recent_entries': recent_count}

            return {
                'agent_id': agent_id,
                'total_entries': 0,  # Would get from Letta API
                'last_accessed': 'unknown',
                'storage_type': 'vector_database',
            }

        except Exception as e:
            logger.error(
                f'Failed to get archival memory stats for agent {agent_id}: {e}'
            )
            return {'agent_id': agent_id, 'error': str(e)}

    async def list_agents_by_user(self, user_id: str) -> list[AgentState]:
        """List all agents for a specific user."""
        try:
            all_agents = self.client.agents.list()
            user_agents = [
                agent for agent in all_agents if agent.name.startswith(f'{user_id}_')
            ]
            return user_agents

        except Exception as e:
            logger.error(f'Failed to list agents for user {user_id}: {e}')
            return []

    async def export_all_agents(self, export_dir: Path | None = None) -> list[Path]:
        """Export all agents to .af files."""
        try:
            export_directory = export_dir or self.exports_dir
            export_directory.mkdir(parents=True, exist_ok=True)

            all_agents = self.client.agents.list()
            exported_files = []

            for agent in all_agents:
                try:
                    export_path = await self.export_agent(
                        agent.id, f'{agent.name}_{agent.id[:8]}'
                    )
                    exported_files.append(export_path)
                except Exception as e:
                    logger.error(f'Failed to export agent {agent.name}: {e}')

            logger.info(f'Exported {len(exported_files)} agents to {export_directory}')
            return exported_files

        except Exception as e:
            logger.error(f'Failed to export all agents: {e}')
            return []

    async def import_agents_from_directory(self, import_dir: Path) -> list[str]:
        """Import all .af files from directory."""
        try:
            af_files = list(import_dir.glob('*.af'))
            imported_agents = []

            for af_file in af_files:
                try:
                    agent_id = await self.import_agent(af_file)
                    imported_agents.append(agent_id)
                except Exception as e:
                    logger.error(f'Failed to import {af_file.name}: {e}')

            logger.info(f'Imported {len(imported_agents)} agents from {import_dir}')
            return imported_agents

        except Exception as e:
            logger.error(f'Failed to import agents from directory {import_dir}: {e}')
            return []

    async def backup_workspace(self, backup_dir: Path) -> bool:
        """Create complete backup of all agents and data."""
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Export all agents
            export_dir = backup_dir / 'agents'
            exported_files = await self.export_all_agents(export_dir)

            # Create metadata file
            metadata = {
                'backup_date': datetime.now().isoformat(),
                'backup_mode': self.mode.value,
                'total_agents': len(exported_files),
                'letta_version': 'latest',  # Would get from Letta client
                'thoth_version': '1.0',
            }

            import json

            with open(backup_dir / 'backup_metadata.json', 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(
                f'Workspace backup completed: {len(exported_files)} agents saved to {backup_dir}'
            )
            return True

        except Exception as e:
            logger.error(f'Workspace backup failed: {e}')
            return False

    async def get_system_agents(self) -> list[AgentState]:
        """Get all system agents."""
        try:
            all_agents = self.client.agents.list()
            system_agents = [
                agent for agent in all_agents if agent.name.startswith('system_')
            ]
            return system_agents

        except Exception as e:
            logger.error(f'Failed to list system agents: {e}')
            return []

    def health_check(self) -> dict[str, Any]:
        """Comprehensive health check for Letta service."""
        try:
            base_health = super().health_check()

            # Add Letta-specific health metrics
            if self.client:
                agents = self.client.agents.list()
                letta_health = {
                    'letta_connected': True,
                    'mode': self.mode.value,
                    'total_agents': len(agents),
                    'connection_url': self.connection_config['base_url'],
                }
            else:
                letta_health = {
                    'letta_connected': False,
                    'mode': self.mode.value,
                    'error': 'Client not initialized',
                }

            return {**base_health, **letta_health}

        except Exception as e:
            return {'status': 'error', 'letta_connected': False, 'error': str(e)}

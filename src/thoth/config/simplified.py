"""Simplified configuration structures for Thoth."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from thoth.utilities.config import (
        APIKeys,
        DiscoveryConfig,
        EndpointConfig,
        LLMConfig,
        MCPConfig,
        MonitorConfig,
        QueryBasedRoutingConfig,
        RAGConfig,
        ResearchAgentConfig,
        ResearchAgentLLMConfig,
        ScrapeFilterLLMConfig,
        ThothConfig,
    )


class CoreConfig(BaseSettings):
    """Core configuration values required by most of Thoth."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra='ignore',
    )

    # Nested configuration
    api_keys: APIKeys = Field(
        default_factory=lambda: __import__(
            'thoth.utilities.config', fromlist=['APIKeys']
        ).APIKeys(),
        description='API keys',
    )
    llm_config: LLMConfig = Field(
        default_factory=lambda: __import__(
            'thoth.utilities.config', fromlist=['LLMConfig']
        ).LLMConfig(),
        description='LLM settings',
    )

    # Directory paths - automatically detects .thoth directory
    workspace_dir: Path = Field(
        default_factory=lambda: CoreConfig._get_default_workspace(),
        description='Base workspace directory - auto-detects .thoth or uses THOTH_WORKSPACE_DIR',
    )

    @staticmethod
    def _get_default_workspace() -> Path:
        """Auto-detect workspace directory with priority order."""
        # 1. Environment variable (highest priority)
        if env_workspace := os.getenv('THOTH_WORKSPACE_DIR'):
            return Path(env_workspace)

        # 2. Docker default
        if os.getenv('DOCKER_ENV') or os.path.exists('/.dockerenv'):
            return Path('/workspace')

        # 3. Look for .thoth directory in user directories (Obsidian vaults)
        # Check common Obsidian vault locations
        home = Path.home()
        common_vault_paths = [
            home / 'Documents',
            home / 'Obsidian',
            home / 'vaults',
            home / 'Notes',
            home / 'Desktop',
            home,
        ]

        # Look for .thoth directories in potential vault locations
        for base_path in common_vault_paths:
            if base_path.exists():
                # Look for .thoth directories in subdirectories (vault folders)
                try:
                    for vault_dir in base_path.iterdir():
                        if vault_dir.is_dir():
                            thoth_dir = vault_dir / '.thoth'
                            if thoth_dir.exists() and thoth_dir.is_dir():
                                return thoth_dir
                except (PermissionError, OSError):
                    continue

        # 4. Check if we're running from within an Obsidian vault
        current_dir = Path.cwd()
        for parent in [current_dir, *list(current_dir.parents)]:
            # Look for .obsidian folder indicating this is a vault
            if (parent / '.obsidian').exists():
                thoth_dir = parent / '.thoth'
                if thoth_dir.exists() and thoth_dir.is_dir():
                    return thoth_dir
                # If .thoth doesn't exist in the vault, suggest creating it there
                return thoth_dir  # Return the path even if it doesn't exist yet

        # 5. Fallback - suggest creating .thoth in user's Documents
        fallback = home / 'Documents' / 'Thoth' / '.thoth'
        return fallback

    # All paths are relative to workspace_dir and use new .thoth structure
    pdf_dir: Path = Field(Path('data/pdfs'), description='Directory for PDF files')
    markdown_dir: Path = Field(
        Path('data/markdown'), description='Directory for Markdown files'
    )
    notes_dir: Path = Field(
        Path('data/notes'), description='Directory for research notes'
    )
    prompts_dir: Path = Field(
        Path('data/prompts'), description='Directory for custom prompts'
    )
    templates_dir: Path = Field(
        Path('data/templates'), description='Directory for templates'
    )
    output_dir: Path = Field(
        Path('exports'), description='Directory for output files and exports'
    )
    knowledge_base_dir: Path = Field(
        Path('data/knowledge'), description='Directory for knowledge base'
    )
    graph_storage_path: Path = Field(
        Path('data/knowledge/citations.graphml'),
        description='Path for citation graph storage',
    )
    queries_dir: Path = Field(
        Path('data/queries'), description='Directory for research queries'
    )
    agent_storage_dir: Path = Field(
        Path('data/agents'), description='Directory for agent session data'
    )
    discovery_sources_dir: Path = Field(
        Path('data/discovery/sources'),
        description='Directory for discovery source configs',
    )
    discovery_results_dir: Path = Field(
        Path('data/discovery/results'), description='Directory for discovery results'
    )
    chrome_extension_configs_dir: Path = Field(
        Path('data/discovery/chrome_configs'),
        description='Directory for Chrome extension configs',
    )
    cache_dir: Path = Field(
        Path('cache'), description='Directory for temporary cache files'
    )
    logs_dir: Path = Field(Path('logs'), description='Directory for log files')
    config_dir: Path = Field(
        Path('config'), description='Directory for local config overrides'
    )

    @field_validator('workspace_dir', mode='before')
    @classmethod
    def resolve_workspace_dir(cls, v) -> Path:
        """Ensure workspace directory is resolved."""
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        return Path(v).expanduser().resolve() if v else cls._get_default_workspace()

    @field_validator(
        'pdf_dir',
        'markdown_dir',
        'notes_dir',
        'prompts_dir',
        'templates_dir',
        'output_dir',
        'knowledge_base_dir',
        'graph_storage_path',
        'queries_dir',
        'agent_storage_dir',
        'discovery_sources_dir',
        'discovery_results_dir',
        'chrome_extension_configs_dir',
        'cache_dir',
        'logs_dir',
        'config_dir',
        mode='before',
    )
    @classmethod
    def resolve_path_fields(cls, v, info) -> Path:
        """Resolve path fields - use absolute paths as-is, make relative paths
        relative to workspace_dir.

        Args:
            v: The path value to resolve
            info: Validation context containing other field values

        Returns:
            Resolved Path object
        """
        # Convert to Path if string
        if isinstance(v, str):
            path = Path(v)
        else:
            path = Path(v) if v else Path('.')

        # Expand user home directory references
        path = path.expanduser()

        # If path is absolute, use it as-is
        if path.is_absolute():
            return path.resolve()

        # If path is relative, make it relative to workspace_dir
        # Get workspace_dir from the validation context
        workspace_dir = info.data.get('workspace_dir')
        if workspace_dir:
            if isinstance(workspace_dir, str):
                workspace_dir = Path(workspace_dir)
            return (workspace_dir / path).resolve()

        # Fallback: return the path as-is if workspace_dir not available yet
        return path


class FeatureConfig(BaseSettings):
    """Configuration for optional features of Thoth."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra='ignore',
    )

    api_server: EndpointConfig = Field(
        default_factory=lambda: __import__(
            'thoth.utilities.config', fromlist=['EndpointConfig']
        ).EndpointConfig(),
        description='API server configuration',
    )
    monitor: MonitorConfig = Field(
        default_factory=lambda: __import__(
            'thoth.utilities.config', fromlist=['MonitorConfig']
        ).MonitorConfig(),
        description='Monitor configuration',
    )
    research_agent: ResearchAgentConfig = Field(
        default_factory=lambda: __import__(
            'thoth.utilities.config', fromlist=['ResearchAgentConfig']
        ).ResearchAgentConfig(),
        description='Research agent configuration',
    )
    research_agent_llm: ResearchAgentLLMConfig = Field(
        default_factory=lambda: __import__(
            'thoth.utilities.config', fromlist=['ResearchAgentLLMConfig']
        ).ResearchAgentLLMConfig(),
        description='Research agent LLM configuration',
    )
    mcp: MCPConfig = Field(
        default_factory=lambda: __import__(
            'thoth.utilities.config', fromlist=['MCPConfig']
        ).MCPConfig(),
        description='MCP server configuration',
    )
    scrape_filter_llm: ScrapeFilterLLMConfig = Field(
        default_factory=lambda: __import__(
            'thoth.utilities.config', fromlist=['ScrapeFilterLLMConfig']
        ).ScrapeFilterLLMConfig(),
        description='Scrape filter LLM configuration',
    )
    discovery: DiscoveryConfig = Field(
        default_factory=lambda: __import__(
            'thoth.utilities.config', fromlist=['DiscoveryConfig']
        ).DiscoveryConfig(),
        description='Discovery system configuration',
    )
    rag: RAGConfig = Field(
        default_factory=lambda: __import__(
            'thoth.utilities.config', fromlist=['RAGConfig']
        ).RAGConfig(),
        description='RAG system configuration',
    )
    query_based_routing: QueryBasedRoutingConfig = Field(
        default_factory=lambda: __import__(
            'thoth.utilities.config', fromlist=['QueryBasedRoutingConfig']
        ).QueryBasedRoutingConfig(),
        description='Query-based routing configuration',
    )


# ----------------------------------------------------------------------------
# Migration utilities
# ----------------------------------------------------------------------------


def migrate_from_old_config(old_config: ThothConfig) -> ThothConfig:
    """Migrate an old-style ``ThothConfig`` to the new structure."""

    from thoth.utilities.config import ThothConfig as NewThothConfig

    core = CoreConfig(
        api_keys=old_config.api_keys,
        llm_config=old_config.llm_config,
        workspace_dir=old_config.workspace_dir,
        pdf_dir=old_config.pdf_dir,
        markdown_dir=old_config.markdown_dir,
        notes_dir=old_config.notes_dir,
        prompts_dir=old_config.prompts_dir,
        templates_dir=old_config.templates_dir,
        output_dir=old_config.output_dir,
        knowledge_base_dir=old_config.knowledge_base_dir,
        graph_storage_path=old_config.graph_storage_path,
        queries_dir=old_config.queries_dir,
        agent_storage_dir=old_config.agent_storage_dir,
        discovery_sources_dir=old_config.discovery_sources_dir,
        discovery_results_dir=old_config.discovery_results_dir,
        chrome_extension_configs_dir=old_config.chrome_extension_configs_dir,
    )

    features = FeatureConfig(
        api_server=old_config.api_server_config,
        monitor=old_config.monitor_config,
        research_agent=old_config.research_agent_config,
        research_agent_llm=old_config.research_agent_llm_config,
        scrape_filter_llm=old_config.scrape_filter_llm_config,
        discovery=old_config.discovery_config,
        rag=old_config.rag_config,
        query_based_routing=old_config.query_based_routing_config,
        mcp=old_config.mcp_config,
    )

    return NewThothConfig(
        core=core,
        features=features,
        citation_llm_config=old_config.citation_llm_config,
        tag_consolidator_llm_config=old_config.tag_consolidator_llm_config,
        citation_config=old_config.citation_config,
        logging_config=old_config.logging_config,
    )

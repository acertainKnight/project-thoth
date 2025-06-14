from __future__ import annotations

"""Simplified configuration structures for Thoth."""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from thoth.utilities.config import (
        APIKeys,
        LLMConfig,
        EndpointConfig,
        MonitorConfig,
        ResearchAgentConfig,
        ResearchAgentLLMConfig,
        ScrapeFilterLLMConfig,
        DiscoveryConfig,
        RAGConfig,
        QueryBasedRoutingConfig,
        ThothConfig,
    )


class CoreConfig(BaseSettings):
    """Core configuration values required by most of Thoth."""

    model_config = SettingsConfigDict(
        env_prefix='THOTH_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
    )

    # Nested configuration
    api_keys: 'APIKeys' = Field(
        default_factory=lambda: __import__('thoth.utilities.config', fromlist=['APIKeys']).APIKeys(),
        description='API keys',
    )
    llm_config: 'LLMConfig' = Field(
        default_factory=lambda: __import__('thoth.utilities.config', fromlist=['LLMConfig']).LLMConfig(),
        description='LLM settings',
    )

    # Directory paths
    workspace_dir: Path = Field(Path('.'), description='Base workspace directory')
    pdf_dir: Path = Field(Path('data/pdf'), description='Directory for PDF files')
    markdown_dir: Path = Field(Path('data/markdown'), description='Directory for Markdown files')
    notes_dir: Path = Field(Path('data/notes'), description='Directory for Obsidian notes')
    prompts_dir: Path = Field(Path('templates/prompts'), description='Directory for prompts')
    templates_dir: Path = Field(Path('templates'), description='Directory for templates')
    output_dir: Path = Field(Path('data/output'), description='Directory for output files')
    knowledge_base_dir: Path = Field(Path('data/knowledge'), description='Directory for knowledge base')
    graph_storage_path: Path = Field(
        Path('data/graph/citations.graphml'), description='Path for citation graph storage'
    )
    queries_dir: Path = Field(Path('data/queries'), description='Directory for research queries')
    agent_storage_dir: Path = Field(
        Path('data/agent'), description='Directory for agent-managed articles'
    )
    discovery_sources_dir: Path = Field(
        Path('data/discovery/sources'), description='Directory for discovery source configs'
    )
    discovery_results_dir: Path = Field(
        Path('data/discovery/results'), description='Directory for discovery results'
    )
    chrome_extension_configs_dir: Path = Field(
        Path('data/discovery/chrome_configs'),
        description='Directory for Chrome extension configs',
    )


class FeatureConfig(BaseSettings):
    """Configuration for optional features of Thoth."""

    model_config = SettingsConfigDict(
        env_prefix='THOTH_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
    )

    api_server: 'EndpointConfig' = Field(
        default_factory=lambda: __import__('thoth.utilities.config', fromlist=['EndpointConfig']).EndpointConfig(),
        description='API server configuration',
    )
    monitor: 'MonitorConfig' = Field(
        default_factory=lambda: __import__('thoth.utilities.config', fromlist=['MonitorConfig']).MonitorConfig(),
        description='Monitor configuration',
    )
    research_agent: 'ResearchAgentConfig' = Field(
        default_factory=lambda: __import__('thoth.utilities.config', fromlist=['ResearchAgentConfig']).ResearchAgentConfig(),
        description='Research agent configuration',
    )
    research_agent_llm: 'ResearchAgentLLMConfig' = Field(
        default_factory=lambda: __import__('thoth.utilities.config', fromlist=['ResearchAgentLLMConfig']).ResearchAgentLLMConfig(),
        description='Research agent LLM configuration',
    )
    scrape_filter_llm: 'ScrapeFilterLLMConfig' = Field(
        default_factory=lambda: __import__('thoth.utilities.config', fromlist=['ScrapeFilterLLMConfig']).ScrapeFilterLLMConfig(),
        description='Scrape filter LLM configuration',
    )
    discovery: 'DiscoveryConfig' = Field(
        default_factory=lambda: __import__('thoth.utilities.config', fromlist=['DiscoveryConfig']).DiscoveryConfig(),
        description='Discovery system configuration',
    )
    rag: 'RAGConfig' = Field(
        default_factory=lambda: __import__('thoth.utilities.config', fromlist=['RAGConfig']).RAGConfig(),
        description='RAG system configuration',
    )
    query_based_routing: 'QueryBasedRoutingConfig' = Field(
        default_factory=lambda: __import__('thoth.utilities.config', fromlist=['QueryBasedRoutingConfig']).QueryBasedRoutingConfig(),
        description='Query-based routing configuration',
    )



# ----------------------------------------------------------------------------
# Migration utilities
# ----------------------------------------------------------------------------

def migrate_from_old_config(old_config: 'ThothConfig') -> 'ThothConfig':
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
    )

    return NewThothConfig(
        core=core,
        features=features,
        citation_llm_config=old_config.citation_llm_config,
        tag_consolidator_llm_config=old_config.tag_consolidator_llm_config,
        citation_config=old_config.citation_config,
        logging_config=old_config.logging_config,
    )


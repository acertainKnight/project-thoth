"""
Service configurations for various Thoth components.

This module contains configuration classes for all the services
and components that make up the Thoth system.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .base import BaseServerConfig


class EndpointConfig(BaseServerConfig):
    """Configuration for API endpoints."""

    model_config = SettingsConfigDict(
        env_prefix='ENDPOINT_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    base_url: str = Field(
        'http://localhost:8000', description='Base URL for the endpoint'
    )


class MonitorConfig(BaseSettings):
    """Configuration for the monitor."""

    model_config = SettingsConfigDict(
        env_prefix='MONITOR_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # Make case-insensitive to handle env vars
        extra='ignore',  # Ignore extra inputs
    )
    auto_start: bool = Field(
        False, description='Whether to automatically start the monitor'
    )
    watch_interval: int = Field(
        10, description='Interval to check for new files in the watch directory'
    )


class MCPConfig(BaseServerConfig):
    """Configuration for MCP (Model Context Protocol) server."""

    model_config = SettingsConfigDict(
        env_prefix='MCP_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # Override defaults
    host: str = Field('localhost', description='MCP server host')
    port: int = Field(8001, description='MCP server port')
    auto_start: bool = Field(True, description='Auto-start MCP server with main server')

    enabled: bool = Field(True, description='Whether MCP server is enabled')


class LettaConfig(BaseSettings):
    """Configuration for Letta memory system."""

    model_config = SettingsConfigDict(
        env_prefix='LETTA_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # Server connection
    server_url: str = Field('http://localhost:8283', description='Letta server URL')
    api_key: str | None = Field(
        None,
        description='Optional API key for Letta server authentication (not required for local Letta installation)',
    )

    # Agent configuration
    agent_name: str = Field(
        'thoth_research_agent', description='Name of the Thoth research agent in Letta'
    )

    # Memory configuration
    core_memory_limit: int = Field(
        10000, description='Character limit for core memory blocks'
    )
    archival_memory_enabled: bool = Field(
        True, description='Enable archival memory for long-term storage'
    )
    recall_memory_enabled: bool = Field(
        True, description='Enable recall memory for conversation history'
    )

    # Performance settings
    enable_smart_truncation: bool = Field(
        True, description='Enable intelligent memory truncation when limits are reached'
    )
    consolidation_interval_hours: int = Field(
        24, description='Hours between memory consolidation runs'
    )

    # Agent system configuration
    enable_agent_system: bool = Field(
        True, description='Enable Letta-based agent orchestration system'
    )
    agent_workspace_subdir: str = Field(
        'agents', description='Subdirectory within workspace for agent storage'
    )
    max_agents_per_user: int = Field(
        50, description='Maximum number of agents per user'
    )
    default_agent_tools: list[str] = Field(
        default_factory=lambda: ['search_articles', 'analyze_document'],
        description='Default tools assigned to new agents',
    )

    # Fallback behavior
    fallback_enabled: bool = Field(
        True,
        description='Enable fallback to basic memory store when Letta is unavailable',
    )


class DiscoveryConfig(BaseSettings):
    """Configuration for the discovery system."""

    model_config = SettingsConfigDict(
        env_prefix='DISCOVERY_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )
    auto_start_scheduler: bool = Field(
        False, description='Whether to automatically start the discovery scheduler'
    )
    default_max_articles: int = Field(
        50, description='Default maximum articles per discovery run'
    )
    default_interval_minutes: int = Field(
        60, description='Default interval between discovery runs in minutes'
    )
    rate_limit_delay: float = Field(
        1.0, description='Default delay between web scraping requests in seconds'
    )
    chrome_extension_enabled: bool = Field(
        True, description='Whether Chrome extension integration is enabled'
    )
    chrome_extension_host: str = Field(
        'localhost', description='Host for Chrome extension WebSocket communication'
    )
    chrome_extension_port: int = Field(
        8765, description='Port for Chrome extension WebSocket communication'
    )


class ResearchAgentConfig(BaseSettings):
    """Configuration for the research agent."""

    model_config = SettingsConfigDict(
        env_prefix='RESEARCH_AGENT_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # Make case-insensitive to handle env vars
        extra='ignore',  # Ignore extra inputs
    )
    auto_start: bool = Field(
        False, description='Whether to automatically start the research agent CLI'
    )
    default_queries: bool = Field(
        True, description='Whether to create default research queries on first run'
    )


class RAGConfig(BaseSettings):
    """Configuration for the RAG (Retrieval-Augmented Generation) system."""

    model_config = SettingsConfigDict(
        env_prefix='RAG_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )
    # Embedding configuration
    embedding_model: str = Field(
        'all-MiniLM-L6-v2',
        description='Model to use for generating embeddings (local sentence-transformers model)',
    )
    embedding_batch_size: int = Field(
        100, description='Batch size for embedding generation'
    )

    # Content filtering configuration
    skip_files_with_images: bool = Field(
        True,
        description='Skip indexing markdown files that contain images to reduce noise',
    )

    # Vector store configuration
    vector_db_path: Path = Field(
        Path('knowledge/vector_db'),
        description='Path to persist the vector database',
    )
    collection_name: str = Field(
        'thoth_knowledge', description='Name of the vector database collection'
    )

    # Document processing configuration
    chunk_size: int = Field(
        500, description='Size of text chunks in tokens for splitting documents'
    )
    chunk_overlap: int = Field(
        50, description='Overlap between consecutive chunks in tokens'
    )
    chunk_encoding: str = Field(
        'cl100k_base',
        description='Encoding to use for token counting (cl100k_base for GPT-4, p50k_base for GPT-3.5)',
    )

    # Question answering configuration
    qa_model: str = Field(
        'openai/gpt-4o-mini',
        description='Model to use for question answering',
    )
    qa_temperature: float = Field(
        0.2, description='Temperature for QA model (lower = more focused)'
    )
    qa_max_tokens: int = Field(2000, description='Maximum tokens for QA responses')
    retrieval_k: int = Field(
        4, description='Number of documents to retrieve for context'
    )


class CitationConfig(BaseSettings):
    """Configuration for citations."""

    model_config = SettingsConfigDict(
        env_prefix='CITATION_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # Make case-insensitive to handle env vars
        extra='ignore',  # Ignore extra inputs
    )
    link_format: str = Field(
        'uri', description='Format for citations (uri, wikilink, etc.)'
    )
    style: str = Field('IEEE', description='Citation style (e.g., IEEE, APA)')
    use_opencitations: bool = Field(
        True, description='Whether to use OpenCitations API'
    )
    use_scholarly: bool = Field(
        False, description='Whether to use Scholarly for Google Scholar search'
    )
    use_semanticscholar: bool = Field(
        True, description='Enable Semantic Scholar lookups'
    )
    use_arxiv: bool = Field(True, description='Enable arXiv lookups')
    processing_mode: str = Field(
        'single',
        description='Processing mode for citation extraction. "single" for one-by-one, "batch" for batching.',
    )
    citation_batch_size: int = Field(
        1,
        description='Batch size for citation processing. A size of 1 uses single processing (more robust). Sizes > 1 use batch processing (faster).',
        ge=1,
        le=20,
    )


class LoggingConfig(BaseSettings):
    """Configuration for logging."""

    model_config = SettingsConfigDict(
        env_prefix='LOG_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # Make case-insensitive to handle env vars
        extra='ignore',  # Ignore extra inputs
    )
    level: str = Field('INFO', description='Logging level')
    logformat: str = Field(
        '{time} | {level} | {file}:{line} | {function} | {message}',
        description='Logging format',
    )
    dateformat: str = Field('YYYY-MM-DD HH:mm:ss', description='Logging date format')
    filename: str = Field('logs/thoth.log', description='Logging filename')
    filemode: str = Field('a', description='Logging file mode')
    file_level: str = Field('INFO', description='Logging file level')


class APIGatewayConfig(BaseSettings):
    """Configuration for the external API gateway."""

    model_config = SettingsConfigDict(
        env_prefix='API_GATEWAY_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    rate_limit: float = Field(
        5.0, description='Requests per second allowed for external APIs'
    )
    cache_expiry: int = Field(
        3600, description='Cache expiry time for API responses in seconds'
    )
    default_timeout: int = Field(
        15, description='Default timeout for API requests in seconds'
    )
    endpoints: dict[str, str] = Field(
        default_factory=dict,
        description='Mapping of service name to base URL',
    )

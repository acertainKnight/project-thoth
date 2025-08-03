"""
Configuration utilities for Thoth.
"""

import os
import sys
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from thoth.config.simplified import CoreConfig, FeatureConfig


class APIKeys(BaseSettings):
    """API keys for external services."""

    model_config = SettingsConfigDict(
        env_prefix='API_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # Make case-insensitive to handle env vars
        extra='allow',
    )
    mistral_key: str | None = Field(
        None, description='Mistral API key for OCR (optional)'
    )
    openrouter_key: str | None = Field(None, description='OpenRouter API key for LLM')
    openai_key: str | None = Field(None, description='OpenAI API key for LLM')
    anthropic_key: str | None = Field(None, description='Anthropic API key for LLM')
    opencitations_key: str = Field(..., description='OpenCitations API key')
    google_api_key: str | None = Field(
        None, description='Google API key for web search (legacy)'
    )
    google_search_engine_id: str | None = Field(
        None, description='Google Custom Search Engine ID (legacy)'
    )
    semanticscholar_api_key: str | None = Field(
        None, description='Semantic Scholar API key'
    )
    web_search_key: str | None = Field(
        None, description='Serper.dev API key for general web search'
    )
    web_search_providers: list[str] = Field(
        default_factory=lambda: ['serper'],
        description='Comma-separated list of enabled web search providers '
        '(serper, duckduckgo, scrape)',
    )
    unpaywall_email: str | None = Field(
        None,
        description='Email address for Unpaywall API (required for OA PDF lookups)',
    )


class ModelConfig(BaseSettings):
    """Configuration for model parameters."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra='ignore',
    )
    temperature: float = Field(0.9, description='Model temperature')
    max_tokens: int = Field(500000, description='Model max tokens for generation')
    top_p: float = Field(1.0, description='Model top p')
    streaming: bool = Field(False, description='Model streaming')
    use_rate_limiter: bool = Field(True, description='Model use rate limiter')


class BaseLLMConfig(BaseSettings):
    """Base configuration class for LLM models."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
        env_nested_delimiter='_',
    )

    model: str = Field('', description='LLM model identifier')
    model_settings: ModelConfig = Field(
        default_factory=ModelConfig, description='Model parameters'
    )
    max_output_tokens: int = Field(50000, description='Max tokens for generation')
    max_context_length: int = Field(8000, description='Max context length for model')


class LLMConfig(BaseLLMConfig):
    """Configuration for primary LLM."""

    model_config = SettingsConfigDict(
        env_prefix='LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
        env_nested_delimiter='_',
    )

    # Primary LLM requires model field
    model: str = Field(..., description='Primary LLM model identifier')

    chunk_size: int = Field(4000, description='Chunk size for splitting documents')
    chunk_overlap: int = Field(200, description='Chunk overlap for splitting documents')
    refine_threshold_multiplier: float = Field(
        1.2, description='Multiplier for max_context_length to choose refine strategy'
    )
    map_reduce_threshold_multiplier: float = Field(
        3.0,
        description='Multiplier for max_context_length to choose map_reduce strategy',
    )


class QueryBasedRoutingConfig(BaseSettings):
    """Configuration for query-based model routing."""

    model_config = SettingsConfigDict(
        env_prefix='ROUTING_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )
    enabled: bool = Field(False, description='Enable query-based routing')
    routing_model: str = Field(
        'openai/gpt-4o-mini',
        description='The model used to select the best model for a query',
    )
    use_dynamic_prompt: bool = Field(
        True, description='Use a dynamic Jinja2 template for the routing prompt'
    )


class CitationLLMConfig(BaseLLMConfig):
    """Configuration for citation processing LLM."""

    model_config = SettingsConfigDict(
        env_prefix='CITATION_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )

    # Citation LLM requires model field
    model: str = Field(..., description='Default citation LLM model')

    # Override defaults for citation-specific use case
    max_output_tokens: int = Field(
        10000, description='Max tokens for citation processing (focused outputs)'
    )
    max_context_length: int = Field(
        4000, description='Max context length (smaller for focused citation inputs)'
    )

    # Citation-specific models
    document_citation_model: str | None = Field(
        None, description='Model for extracting document citations'
    )
    reference_cleaning_model: str | None = Field(
        None, description='Model for cleaning references section'
    )
    structured_extraction_model: str | None = Field(
        None, description='Model for structured citation extraction (single mode)'
    )
    batch_structured_extraction_model: str | None = Field(
        None, description='Model for structured citation extraction (batch mode)'
    )


class PerformanceConfig(BaseSettings):
    """
    Configuration for performance and concurrency settings optimized for local
    servers.
    """

    model_config = SettingsConfigDict(
        env_prefix='PERFORMANCE_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # Auto-scaling settings
    auto_scale_workers: bool = Field(
        True,
        description='Automatically scale workers based on available CPU cores',
    )

    # Tag processing workers - optimized for local processing
    tag_mapping_workers: int = Field(
        default_factory=lambda: min(max(1, (os.cpu_count() or 4) - 1), 8),
        description='Number of parallel workers for tag mapping operations',
        ge=1,
        le=20,
    )
    article_processing_workers: int = Field(
        default_factory=lambda: min(max(1, (os.cpu_count() or 4) // 2), 6),
        description='Number of parallel workers for article tag processing',
        ge=1,
        le=10,
    )

    # Document pipeline workers - CPU-aware defaults
    content_analysis_workers: int = Field(
        default_factory=lambda: min(max(1, (os.cpu_count() or 4) - 1), 4),
        description='Number of parallel workers for content analysis and citation extraction',
        ge=1,
        le=8,
    )

    # Citation enhancement workers - I/O bound, can handle more
    citation_enhancement_workers: int = Field(
        default_factory=lambda: min(max(2, (os.cpu_count() or 4) - 1), 8),
        description='Number of parallel workers for citation enhancement APIs',
        ge=1,
        le=15,
    )
    citation_pdf_workers: int = Field(
        default_factory=lambda: min(max(2, (os.cpu_count() or 4) - 1), 10),
        description='Number of parallel workers for PDF location',
        ge=1,
        le=20,
    )

    # Citation extraction workers - parallel processing friendly
    citation_extraction_workers: int = Field(
        default_factory=lambda: min(max(2, (os.cpu_count() or 4) - 1), 8),
        description='Number of parallel workers for citation extraction from raw strings',
        ge=1,
        le=16,
    )

    # OCR processing settings
    ocr_max_concurrent: int = Field(
        3,
        description='Maximum concurrent OCR operations (API rate limited)',
        ge=1,
        le=6,
    )
    ocr_enable_caching: bool = Field(
        True,
        description='Enable OCR result caching for improved performance',
    )
    ocr_cache_ttl_hours: int = Field(
        24,
        description='OCR cache time-to-live in hours',
        ge=1,
        le=168,  # 1 week max
    )

    # Async processing settings
    async_enabled: bool = Field(
        True,
        description='Enable async I/O processing for better performance',
    )
    async_timeout_seconds: int = Field(
        300,
        description='Timeout for async operations in seconds',
        ge=30,
        le=1800,
    )

    # Memory management
    memory_optimization_enabled: bool = Field(
        True,
        description='Enable memory optimization techniques',
    )
    chunk_processing_enabled: bool = Field(
        True,
        description='Enable chunk-based processing for large documents',
    )
    max_document_size_mb: int = Field(
        50,
        description='Maximum document size in MB before switching to streaming',
        ge=5,
        le=500,
    )

    # Semantic Scholar API optimization
    semanticscholar_max_retries: int = Field(
        3, description='Maximum retries for Semantic Scholar API requests', ge=1, le=10
    )
    semanticscholar_max_backoff_seconds: float = Field(
        30.0,
        description='Maximum backoff time for Semantic Scholar API',
        ge=5.0,
        le=300.0,
    )
    semanticscholar_backoff_multiplier: float = Field(
        1.5,
        description='Backoff multiplier for Semantic Scholar exponential backoff',
        ge=1.1,
        le=3.0,
    )


class TagConsolidatorLLMConfig(BaseLLMConfig):
    """Configuration for tag consolidation LLM."""

    model_config = SettingsConfigDict(
        env_prefix='TAG_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )

    # Override defaults for tag processing
    max_output_tokens: int = Field(
        10000, description='Max tokens for tag processing (focused outputs)'
    )

    # Tag-specific models (base model field is optional for this config)
    consolidate_model: str = Field(..., description='Tag consolidator LLM model')
    suggest_model: str = Field(..., description='Tag suggestor LLM model')
    map_model: str = Field(..., description='Tag mapper LLM model')


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


class BaseServerConfig(BaseSettings):
    """Base configuration for server endpoints."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    host: str = Field(..., description='Host to bind to')
    port: int = Field(..., description='Port to bind to')
    auto_start: bool = Field(False, description='Whether to auto-start')


class EndpointConfig(BaseServerConfig):
    """Configuration for API endpoints."""

    model_config = SettingsConfigDict(
        env_prefix='ENDPOINT_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    base_url: str = Field(..., description='Base URL for the endpoint')


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


class ResearchAgentLLMConfig(BaseLLMConfig):
    """Configuration for research agent LLM."""

    model_config = SettingsConfigDict(
        env_prefix='RESEARCH_AGENT_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )

    # Override model field to support multiple models
    model: str | list[str] = Field(..., description='Research agent LLM model(s)')

    # Override defaults for research agent (needs larger context)
    max_context_length: int = Field(
        100000, description='Max context length for research tasks'
    )

    # Research agent specific features
    use_auto_model_selection: bool = Field(
        False, description='Whether to use auto model selection'
    )
    auto_model_require_tool_calling: bool = Field(
        False, description='Auto-selected model must support tool calling'
    )
    auto_model_require_structured_output: bool = Field(
        False, description='Auto-selected model must support structured output'
    )


class ScrapeFilterLLMConfig(BaseLLMConfig):
    """Configuration for scrape filtering LLM."""

    model_config = SettingsConfigDict(
        env_prefix='SCRAPE_FILTER_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )

    # Scrape filter LLM requires model field
    model: str = Field(..., description='Scrape filter LLM model')

    # Override defaults for scrape filtering (needs larger context for web content)
    max_output_tokens: int = Field(10000, description='Max tokens for scrape filtering')
    max_context_length: int = Field(
        50000, description='Max context length for web content filtering'
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


# Resolve forward references on simplified config classes
CoreConfig.model_rebuild()
FeatureConfig.model_rebuild()


class ThothConfig(BaseSettings):
    """Configuration for Thoth."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # Make case-insensitive to handle env vars
        extra='ignore',  # Ignore extra inputs
    )

    core: CoreConfig = Field(
        default_factory=CoreConfig, description='Core configuration settings'
    )
    features: FeatureConfig = Field(
        default_factory=FeatureConfig, description='Optional feature settings'
    )

    citation_llm_config: CitationLLMConfig = Field(
        default_factory=CitationLLMConfig, description='Citation LLM configuration'
    )
    tag_consolidator_llm_config: TagConsolidatorLLMConfig = Field(
        default_factory=TagConsolidatorLLMConfig,
        description='Tag consolidator LLM configuration',
    )
    citation_config: CitationConfig = Field(
        default_factory=CitationConfig, description='Citation configuration'
    )
    performance_config: PerformanceConfig = Field(
        default_factory=PerformanceConfig,
        description='Performance and concurrency configuration',
    )
    logging_config: LoggingConfig = Field(
        default_factory=LoggingConfig, description='Logging configuration'
    )
    api_gateway_config: APIGatewayConfig = Field(
        default_factory=APIGatewayConfig,
        description='External API gateway configuration',
    )
    # ------------------------------------------------------------------
    # Backwards compatibility helpers
    # ------------------------------------------------------------------

    @property
    def api_keys(self) -> APIKeys:  # pragma: no cover - simple passthrough
        """Return API keys from the core configuration."""
        return self.core.api_keys

    @property
    def llm_config(self) -> LLMConfig:  # pragma: no cover - simple passthrough
        """Return LLM configuration from the core settings."""
        return self.core.llm_config

    @property
    def workspace_dir(self) -> Path:  # pragma: no cover
        return self.core.workspace_dir

    @property
    def pdf_dir(self) -> Path:  # pragma: no cover
        return self.core.pdf_dir

    @property
    def markdown_dir(self) -> Path:  # pragma: no cover
        return self.core.markdown_dir

    @property
    def notes_dir(self) -> Path:  # pragma: no cover
        return self.core.notes_dir

    @property
    def prompts_dir(self) -> Path:  # pragma: no cover
        return self.core.prompts_dir

    @property
    def templates_dir(self) -> Path:  # pragma: no cover
        return self.core.templates_dir

    @property
    def output_dir(self) -> Path:  # pragma: no cover
        return self.core.output_dir

    @property
    def knowledge_base_dir(self) -> Path:  # pragma: no cover
        return self.core.knowledge_base_dir

    @property
    def graph_storage_path(self) -> Path:  # pragma: no cover
        return self.core.graph_storage_path

    @property
    def queries_dir(self) -> Path:  # pragma: no cover
        return self.core.queries_dir

    @property
    def agent_storage_dir(self) -> Path:  # pragma: no cover
        return self.core.agent_storage_dir

    @property
    def discovery_sources_dir(self) -> Path:  # pragma: no cover
        return self.core.discovery_sources_dir

    @property
    def discovery_results_dir(self) -> Path:  # pragma: no cover
        return self.core.discovery_results_dir

    @property
    def chrome_extension_configs_dir(self) -> Path:  # pragma: no cover
        return self.core.chrome_extension_configs_dir

    @property
    def api_server_config(self) -> EndpointConfig:  # pragma: no cover
        return self.features.api_server

    @property
    def monitor_config(self) -> MonitorConfig:  # pragma: no cover
        return self.features.monitor

    @property
    def research_agent_config(self) -> ResearchAgentConfig:  # pragma: no cover
        return self.features.research_agent

    @property
    def research_agent_llm_config(self) -> ResearchAgentLLMConfig:  # pragma: no cover
        return self.features.research_agent_llm

    @property
    def scrape_filter_llm_config(self) -> ScrapeFilterLLMConfig:  # pragma: no cover
        return self.features.scrape_filter_llm

    @property
    def discovery_config(self) -> DiscoveryConfig:  # pragma: no cover
        return self.features.discovery

    @property
    def rag_config(self) -> RAGConfig:  # pragma: no cover
        return self.features.rag

    @property
    def query_based_routing_config(self) -> QueryBasedRoutingConfig:  # pragma: no cover
        return self.features.query_based_routing

    @property
    def mcp_config(self) -> MCPConfig:  # pragma: no cover
        return self.features.mcp

    # Convenience properties for common MCP settings
    @property
    def mcp_port(self) -> int:  # pragma: no cover
        return self.mcp_config.port

    @property
    def mcp_host(self) -> str:  # pragma: no cover
        return self.mcp_config.host

    def setup_logging(self) -> None:
        """Set up logging configuration using loguru."""
        setup_logging(self)

    def export_for_obsidian(self) -> dict[str, Any]:
        """Export configuration in Obsidian plugin format.

        This method converts the internal Thoth configuration to the format
        expected by the Obsidian plugin, maintaining compatibility while
        providing a unified interface.
        """
        return {
            # API Keys
            'mistralKey': self.api_keys.mistral_key or '',
            'openrouterKey': self.api_keys.openrouter_key or '',
            'opencitationsKey': self.api_keys.opencitations_key or '',
            'googleApiKey': self.api_keys.google_api_key or '',
            'googleSearchEngineId': self.api_keys.google_search_engine_id or '',
            'semanticScholarKey': self.api_keys.semanticscholar_api_key or '',
            'webSearchKey': self.api_keys.web_search_key or '',
            'webSearchProviders': ','.join(self.api_keys.web_search_providers),
            # Directories
            'workspaceDirectory': str(self.workspace_dir),
            'obsidianDirectory': str(self.notes_dir),
            'dataDirectory': str(self.core.workspace_dir / 'data'),
            'knowledgeDirectory': str(self.core.knowledge_base_dir),
            'logsDirectory': str(Path(self.logging_config.filename).parent),
            'queriesDirectory': str(self.queries_dir),
            'agentStorageDirectory': str(self.agent_storage_dir),
            'pdfDirectory': str(self.pdf_dir),
            'promptsDirectory': str(self.prompts_dir),
            # Connection Settings
            'remoteMode': False,  # Default to local mode
            'remoteEndpointUrl': '',
            'endpointHost': self.api_server_config.host,
            'endpointPort': self.api_server_config.port,
            'endpointBaseUrl': self.api_server_config.base_url,
            'corsOrigins': ['http://localhost:3000', 'http://127.0.0.1:8080'],
            # LLM Configuration
            'primaryLlmModel': self.llm_config.model,
            'analysisLlmModel': self.citation_llm_config.model,
            'researchAgentModel': self.research_agent_llm_config.model,
            'llmTemperature': self.llm_config.model_settings.temperature,
            'analysisLlmTemperature': self.citation_llm_config.model_settings.temperature,
            'llmMaxOutputTokens': self.llm_config.max_output_tokens,
            'analysisLlmMaxOutputTokens': self.citation_llm_config.max_output_tokens,
            # Agent Behavior
            'researchAgentAutoStart': self.research_agent_config.auto_start,
            'researchAgentDefaultQueries': self.research_agent_config.default_queries,
            'researchAgentMemoryEnabled': True,  # Default value
            'agentMaxToolCalls': 50,  # Default value
            'agentTimeoutSeconds': 300,  # Default value
            # Discovery System
            'discoveryAutoStartScheduler': self.discovery_config.auto_start_scheduler,
            'discoveryDefaultMaxArticles': self.discovery_config.default_max_articles,
            'discoveryDefaultIntervalMinutes': self.discovery_config.default_interval_minutes,
            'discoveryRateLimitDelay': self.discovery_config.rate_limit_delay,
            'discoveryChromeExtensionEnabled': self.discovery_config.chrome_extension_enabled,
            'discoveryChromeExtensionHost': self.discovery_config.chrome_extension_host,
            'discoveryChromeExtensionPort': self.discovery_config.chrome_extension_port,
            # MCP Server Configuration
            'mcpServerEnabled': self.mcp_config.enabled,
            'mcpServerHost': self.mcp_config.host,
            'mcpServerPort': self.mcp_config.port,
            'mcpServerAutoStart': self.mcp_config.auto_start,
            # Logging Configuration
            'logLevel': self.logging_config.level,
            'logFormat': self.logging_config.logformat,
            'logRotation': '10 MB',  # Default value
            'logRetention': '30 days',  # Default value
            'enablePerformanceMonitoring': False,  # Default value
            'metricsInterval': 60,  # Default value
            # Security & Performance
            'encryptionKey': '',  # Not stored in config
            'sessionTimeout': 3600,  # Default value
            'apiRateLimit': self.api_gateway_config.rate_limit,
            'healthCheckTimeout': 30,  # Default value
            'developmentMode': False,  # Default value
            # Plugin Behavior (defaults for now)
            'autoStartAgent': False,
            'showStatusBar': True,
            'showRibbonIcon': True,
            'autoSaveSettings': True,
            'chatHistoryLimit': 20,
            'chatHistory': [],
            # UI Preferences (defaults for now)
            'theme': 'auto',
            'compactMode': False,
            'showAdvancedSettings': False,
            'enableNotifications': True,
            'notificationDuration': 5000,
        }

    @classmethod
    def import_from_obsidian(cls, obsidian_settings: dict[str, Any]) -> 'ThothConfig':
        """Import configuration from Obsidian plugin format.

        This method creates a ThothConfig instance from Obsidian plugin settings,
        allowing seamless integration between the plugin and backend.
        """
        import os

        # Set environment variables from Obsidian settings
        env_vars = {}

        # API Keys
        if obsidian_settings.get('mistralKey'):
            env_vars['API_MISTRAL_KEY'] = obsidian_settings['mistralKey']
        if obsidian_settings.get('openrouterKey'):
            env_vars['API_OPENROUTER_KEY'] = obsidian_settings['openrouterKey']
        if obsidian_settings.get('opencitationsKey'):
            env_vars['API_OPENCITATIONS_KEY'] = obsidian_settings['opencitationsKey']
        if obsidian_settings.get('googleApiKey'):
            env_vars['API_GOOGLE_API_KEY'] = obsidian_settings['googleApiKey']
        if obsidian_settings.get('googleSearchEngineId'):
            env_vars['API_GOOGLE_SEARCH_ENGINE_ID'] = obsidian_settings[
                'googleSearchEngineId'
            ]
        if obsidian_settings.get('semanticScholarKey'):
            env_vars['API_SEMANTICSCHOLAR_API_KEY'] = obsidian_settings[
                'semanticScholarKey'
            ]
        if obsidian_settings.get('webSearchKey'):
            env_vars['API_WEB_SEARCH_KEY'] = obsidian_settings['webSearchKey']
        if obsidian_settings.get('webSearchProviders'):
            env_vars['API_WEB_SEARCH_PROVIDERS'] = obsidian_settings[
                'webSearchProviders'
            ]

        # Directories
        if obsidian_settings.get('workspaceDirectory'):
            env_vars['WORKSPACE_DIR'] = obsidian_settings['workspaceDirectory']
        if obsidian_settings.get('obsidianDirectory'):
            env_vars['NOTES_DIR'] = obsidian_settings['obsidianDirectory']
        if obsidian_settings.get('pdfDirectory'):
            env_vars['PDF_DIR'] = obsidian_settings['pdfDirectory']
        if obsidian_settings.get('promptsDirectory'):
            env_vars['PROMPTS_DIR'] = obsidian_settings['promptsDirectory']

        # LLM Configuration
        if obsidian_settings.get('primaryLlmModel'):
            env_vars['LLM_MODEL'] = obsidian_settings['primaryLlmModel']
        if obsidian_settings.get('llmTemperature') is not None:
            env_vars['LLM_MODEL_SETTINGS_TEMPERATURE'] = str(
                obsidian_settings['llmTemperature']
            )
        if obsidian_settings.get('llmMaxOutputTokens'):
            env_vars['LLM_MAX_OUTPUT_TOKENS'] = str(
                obsidian_settings['llmMaxOutputTokens']
            )

        # Research Agent Configuration
        if obsidian_settings.get('researchAgentModel'):
            env_vars['RESEARCH_AGENT_LLM_MODEL'] = obsidian_settings[
                'researchAgentModel'
            ]
        if obsidian_settings.get('agentMaxToolCalls'):
            env_vars['RESEARCH_AGENT_MAX_TOOL_CALLS'] = str(
                obsidian_settings['agentMaxToolCalls']
            )
        if obsidian_settings.get('agentTimeoutSeconds'):
            env_vars['RESEARCH_AGENT_TIMEOUT_SECONDS'] = str(
                obsidian_settings['agentTimeoutSeconds']
            )

        # Citation LLM Configuration (for analysis)
        if obsidian_settings.get('analysisLlmModel'):
            env_vars['CITATION_LLM_MODEL'] = obsidian_settings['analysisLlmModel']
        if obsidian_settings.get('analysisLlmTemperature') is not None:
            env_vars['CITATION_LLM_MODEL_SETTINGS_TEMPERATURE'] = str(
                obsidian_settings['analysisLlmTemperature']
            )
        if obsidian_settings.get('analysisLlmMaxOutputTokens'):
            env_vars['CITATION_LLM_MAX_OUTPUT_TOKENS'] = str(
                obsidian_settings['analysisLlmMaxOutputTokens']
            )

        # Discovery Configuration
        if obsidian_settings.get('discoveryDefaultMaxArticles'):
            env_vars['DISCOVERY_DEFAULT_MAX_ARTICLES'] = str(
                obsidian_settings['discoveryDefaultMaxArticles']
            )
        if obsidian_settings.get('discoveryDefaultIntervalMinutes'):
            env_vars['DISCOVERY_DEFAULT_INTERVAL_MINUTES'] = str(
                obsidian_settings['discoveryDefaultIntervalMinutes']
            )
        if obsidian_settings.get('discoveryRateLimitDelay'):
            env_vars['DISCOVERY_RATE_LIMIT_DELAY'] = str(
                obsidian_settings['discoveryRateLimitDelay']
            )
        if obsidian_settings.get('discoveryChromeExtensionEnabled') is not None:
            env_vars['DISCOVERY_CHROME_EXTENSION_ENABLED'] = str(
                obsidian_settings['discoveryChromeExtensionEnabled']
            )
        if obsidian_settings.get('discoveryChromeExtensionHost'):
            env_vars['DISCOVERY_CHROME_EXTENSION_HOST'] = obsidian_settings[
                'discoveryChromeExtensionHost'
            ]
        if obsidian_settings.get('discoveryChromeExtensionPort'):
            env_vars['DISCOVERY_CHROME_EXTENSION_PORT'] = str(
                obsidian_settings['discoveryChromeExtensionPort']
            )

        # MCP Server Configuration
        if obsidian_settings.get('mcpServerEnabled') is not None:
            env_vars['MCP_ENABLED'] = str(obsidian_settings['mcpServerEnabled'])
        if obsidian_settings.get('mcpServerHost'):
            env_vars['MCP_HOST'] = obsidian_settings['mcpServerHost']
        if obsidian_settings.get('mcpServerPort'):
            env_vars['MCP_PORT'] = str(obsidian_settings['mcpServerPort'])
        if obsidian_settings.get('mcpServerAutoStart') is not None:
            env_vars['MCP_AUTO_START'] = str(obsidian_settings['mcpServerAutoStart'])

        # Server Configuration
        if obsidian_settings.get('endpointHost'):
            env_vars['ENDPOINT_HOST'] = obsidian_settings['endpointHost']
        if obsidian_settings.get('endpointPort'):
            env_vars['ENDPOINT_PORT'] = str(obsidian_settings['endpointPort'])

        # Logging Configuration
        if obsidian_settings.get('logLevel'):
            env_vars['LOG_LEVEL'] = obsidian_settings['logLevel']

        # Set environment variables temporarily
        original_env = {}
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            # Create config with updated environment
            config = cls()
            return config
        finally:
            # Restore original environment variables
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value

    def validate_for_obsidian(self) -> dict[str, list[str]]:
        """Validate configuration for Obsidian integration and return any issues.

        Returns:
            Dict with 'errors' and 'warnings' keys containing lists of validation
            messages.
        """
        errors = []
        warnings = []

        # Check required API keys
        if not self.api_keys.mistral_key and not self.api_keys.openrouter_key:
            errors.append('At least one of Mistral or OpenRouter API key is required')

        if not self.api_keys.opencitations_key:
            warnings.append(
                'OpenCitations API key is recommended for citation functionality'
            )

        # Check directory accessibility
        if not self.workspace_dir.exists():
            warnings.append(f'Workspace directory does not exist: {self.workspace_dir}')

        if not self.pdf_dir.exists():
            warnings.append(f'PDF directory does not exist: {self.pdf_dir}')

        # Check server configuration
        if not (1024 <= self.api_server_config.port <= 65535):
            errors.append('Main API server port must be between 1024 and 65535')

        if not (1024 <= self.mcp_config.port <= 65535):
            errors.append('MCP server port must be between 1024 and 65535')

        if self.api_server_config.port == self.mcp_config.port:
            errors.append('Main API server and MCP server cannot use the same port')

        if not (1024 <= self.discovery_config.chrome_extension_port <= 65535):
            errors.append('Chrome Extension server port must be between 1024 and 65535')

        # Check for port conflicts
        ports = [
            self.api_server_config.port,
            self.mcp_config.port,
            self.discovery_config.chrome_extension_port,
        ]
        if len(ports) != len(set(ports)):
            errors.append('All server ports must be unique to avoid conflicts')

        # Check LLM parameters
        if not (0.0 <= self.llm_config.model_settings.temperature <= 1.0):
            errors.append('LLM temperature must be between 0.0 and 1.0')

        if self.llm_config.max_output_tokens < 1:
            errors.append('LLM max output tokens must be positive')

        # Check agent configuration
        # Note: max_tool_calls and timeout_seconds are handled at runtime level,
        # not in the config object itself

        # Check discovery configuration
        if self.discovery_config.default_max_articles < 1:
            errors.append('Discovery max articles must be positive')

        if self.discovery_config.default_interval_minutes < 15:
            warnings.append(
                'Discovery interval less than 15 minutes may cause rate limiting'
            )

        return {'errors': errors, 'warnings': warnings}

    def sync_to_environment(self) -> dict[str, str]:
        """Sync current configuration to environment variables.

        Returns:
            Dict of environment variables that were set.
        """
        import os

        env_vars = {}

        # API Keys
        if self.api_keys.mistral_key:
            env_vars['API_MISTRAL_KEY'] = self.api_keys.mistral_key
        if self.api_keys.openrouter_key:
            env_vars['API_OPENROUTER_KEY'] = self.api_keys.openrouter_key
        if self.api_keys.opencitations_key:
            env_vars['API_OPENCITATIONS_KEY'] = self.api_keys.opencitations_key

        # Directories
        env_vars['WORKSPACE_DIR'] = str(self.workspace_dir)
        env_vars['NOTES_DIR'] = str(self.notes_dir)
        env_vars['PDF_DIR'] = str(self.pdf_dir)
        env_vars['PROMPTS_DIR'] = str(self.prompts_dir)

        # LLM Configuration
        env_vars['LLM_MODEL'] = self.llm_config.model
        env_vars['LLM_MODEL_SETTINGS_TEMPERATURE'] = str(
            self.llm_config.model_settings.temperature
        )
        env_vars['LLM_MAX_OUTPUT_TOKENS'] = str(self.llm_config.max_output_tokens)

        # Server Configuration
        env_vars['ENDPOINT_HOST'] = self.api_server_config.host
        env_vars['ENDPOINT_PORT'] = str(self.api_server_config.port)

        # MCP Server Configuration
        env_vars['MCP_HOST'] = self.mcp_config.host
        env_vars['MCP_PORT'] = str(self.mcp_config.port)
        env_vars['MCP_ENABLED'] = str(self.mcp_config.enabled)
        env_vars['MCP_AUTO_START'] = str(self.mcp_config.auto_start)

        # Set all environment variables
        for key, value in env_vars.items():
            os.environ[key] = value

        return env_vars


def load_config() -> ThothConfig:
    """Load the configuration."""
    config = ThothConfig()
    config.setup_logging()
    return config


def get_config() -> ThothConfig:
    """Get the configuration."""
    return load_config()


def setup_logging(config: ThothConfig) -> None:
    """Set up logging configuration using loguru.

    Args:
        config (ThothConfig): The Thoth configuration object containing logging settings.

    Returns:
        None: Sets up loguru logger with file and console handlers.

    Example:
        >>> config = get_config()
        >>> setup_logging(config)
    """  # noqa: W505
    # Remove default loguru handler
    logger.remove()
    # Add console handler with configured level
    logger.add(
        sys.stderr,
        format=config.logging_config.logformat,
        level=config.logging_config.level,
        colorize=True,
    )

    # Add file handler
    logger.add(
        config.logging_config.filename,
        format=config.logging_config.logformat,
        level=config.logging_config.file_level,
        rotation='10 MB',
        mode=config.logging_config.filemode,
    )

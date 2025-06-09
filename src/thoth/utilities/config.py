"""
Configuration utilities for Thoth.
"""

import sys
from pathlib import Path

from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


class ModelConfig(BaseSettings):
    """Configuration for models."""

    model_config = SettingsConfigDict(
        env_prefix='MODEL_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # Make case-insensitive to handle env vars
        extra='ignore',
    )
    temperature: float = Field(0.9, description='Model temperature')
    max_tokens: int = Field(500000, description='Model max tokens for generation')
    top_p: float = Field(1.0, description='Model top p')
    frequency_penalty: float = Field(0.0, description='Model frequency penalty')
    presence_penalty: float = Field(0.0, description='Model presence penalty')
    streaming: bool = Field(False, description='Model streaming')
    use_rate_limiter: bool = Field(True, description='Model use rate limiter')


class LLMConfig(BaseSettings):
    """Configuration for LLM."""

    model_config = SettingsConfigDict(
        env_prefix='LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # Make case-insensitive to handle env vars
        extra='allow',
        env_nested_delimiter='_',  # Explicitly set single underscore for nesting
    )
    model: str = Field(..., description='LLM model')
    model_settings: ModelConfig = Field(
        default_factory=ModelConfig, description='Model configuration'
    )
    doc_processing: str = Field(
        'auto', description='LLM document processing strategy hint'
    )
    max_output_tokens: int = Field(
        50000, description='LLM max input tokens for direct processing strategy'
    )
    max_context_length: int = Field(
        8000, description='LLM max context length for model'
    )
    chunk_size: int = Field(4000, description='LLM chunk size for splitting documents')
    chunk_overlap: int = Field(
        200, description='LLM chunk overlap for splitting documents'
    )
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


class CitationLLMConfig(BaseSettings):
    """Configuration for the LLM used specifically for citation processing."""

    model_config = SettingsConfigDict(
        env_prefix='CITATION_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )
    model: str = Field(..., description='Default citation LLM model')
    document_citation_model: str | None = Field(
        None, description='Model for extracting the document citation'
    )
    reference_cleaning_model: str | None = Field(
        None, description='Model for cleaning the references section'
    )
    structured_extraction_model: str | None = Field(
        None, description='Model for extracting structured citations (single mode)'
    )
    batch_structured_extraction_model: str | None = Field(
        None, description='Model for extracting structured citations (batch mode)'
    )
    model_settings: ModelConfig = Field(
        default_factory=ModelConfig, description='Citation model configuration'
    )
    max_output_tokens: int = Field(
        10000,
        description='Citation LLM max tokens for generation (typically for smaller, focused outputs)',
    )
    max_context_length: int = Field(
        4000,
        description='Citation LLM max context length for model (can be smaller if inputs are focused e.g. reference strings)',
    )


class TagConsolidatorLLMConfig(BaseSettings):
    """Configuration for the LLM used specifically for tag consolidation."""

    model_config = SettingsConfigDict(
        env_prefix='TAG_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )
    consolidate_model: str = Field(..., description='Tag consolidator LLM model')
    suggest_model: str = Field(..., description='Tag suggestor LLM model')
    map_model: str = Field(..., description='Tag mapper LLM model')
    model_settings: ModelConfig = Field(
        default_factory=ModelConfig, description='Tag consolidator model configuration'
    )
    max_output_tokens: int = Field(
        10000,
        description='Tag consolidator LLM max tokens for generation (typically for smaller, focused outputs)',
    )
    max_context_length: int = Field(
        8000,
        description='Tag consolidator LLM max context length for model',
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


class EndpointConfig(BaseSettings):
    """Configuration for endpoints."""

    model_config = SettingsConfigDict(
        env_prefix='ENDPOINT_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # Make case-insensitive to handle env vars
        extra='ignore',  # Ignore extra inputs
    )
    host: str = Field(..., description='Host to bind the endpoint to')
    port: int = Field(..., description='Port to bind the endpoint to')
    base_url: str = Field(..., description='Base URL for the endpoint')
    auto_start: bool = Field(
        False,
        description='Whether to automatically start the endpoint with the monitor',
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
    bulk_process_size: int = Field(10, description='Number of files to process in bulk')


class ResearchAgentLLMConfig(BaseSettings):
    """Configuration for the LLM used specifically for research agent tasks."""

    model_config = SettingsConfigDict(
        env_prefix='RESEARCH_AGENT_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )
    model: str | list[str] = Field(..., description='Research agent LLM model(s)')
    model_settings: ModelConfig = Field(
        default_factory=ModelConfig, description='Research agent model configuration'
    )
    use_auto_model_selection: bool = Field(
        False, description='Whether to use auto model selection'
    )
    auto_model_require_tool_calling: bool = Field(
        False, description='Auto-selected model must support tool calling'
    )
    auto_model_require_structured_output: bool = Field(
        False, description='Auto-selected model must support structured output'
    )
    max_output_tokens: int = Field(
        50000,
        description='Research agent LLM max tokens for generation',
    )
    max_context_length: int = Field(
        100000,
        description='Research agent LLM max context length for model',
    )


class ScrapeFilterLLMConfig(BaseSettings):
    """Configuration for the LLM used specifically for scrape filtering tasks."""

    model_config = SettingsConfigDict(
        env_prefix='SCRAPE_FILTER_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )
    model: str = Field(..., description='Scrape filter LLM model')
    model_settings: ModelConfig = Field(
        default_factory=ModelConfig, description='Scrape filter model configuration'
    )
    max_output_tokens: int = Field(
        10000,
        description='Scrape filter LLM max tokens for generation',
    )
    max_context_length: int = Field(
        50000,
        description='Scrape filter LLM max context length for model',
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


class ThothConfig(BaseSettings):
    """Configuration for Thoth."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # Make case-insensitive to handle env vars
        extra='ignore',  # Ignore extra inputs
    )

    # Base paths
    workspace_dir: Path = Field(Path('.'), description='Base workspace directory')
    pdf_dir: Path = Field(Path('data/pdf'), description='Directory for PDF files')
    markdown_dir: Path = Field(
        Path('data/markdown'), description='Directory for Markdown files'
    )
    notes_dir: Path = Field(
        Path('data/notes'), description='Directory for Obsidian notes'
    )
    prompts_dir: Path = Field(
        Path('templates/prompts'), description='Directory for prompts'
    )
    templates_dir: Path = Field(
        Path('templates'), description='Directory for templates'
    )
    output_dir: Path = Field(
        Path('data/output'), description='Directory for output files'
    )
    knowledge_base_dir: Path = Field(
        Path('data/knowledge'), description='Directory for knowledge base'
    )
    graph_storage_path: Path = Field(
        Path('data/graph/citations.graphml'),
        description='Path for citation graph storage',
    )

    # Research agent directories
    queries_dir: Path = Field(
        Path('data/queries'), description='Directory for research query files'
    )
    agent_storage_dir: Path = Field(
        Path('data/agent'), description='Directory for agent-managed articles'
    )

    # Discovery directories
    discovery_sources_dir: Path = Field(
        Path('data/discovery/sources'),
        description='Directory for discovery source configurations',
    )
    discovery_results_dir: Path = Field(
        Path('data/discovery/results'), description='Directory for discovery results'
    )
    chrome_extension_configs_dir: Path = Field(
        Path('data/discovery/chrome_configs'),
        description='Directory for Chrome extension configurations',
    )

    # Configuration objects
    api_keys: APIKeys = Field(
        default_factory=APIKeys, description='API keys for external services'
    )
    llm_config: LLMConfig = Field(
        default_factory=LLMConfig, description='LLM configuration'
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
    logging_config: LoggingConfig = Field(
        default_factory=LoggingConfig, description='Logging configuration'
    )
    api_server_config: EndpointConfig = Field(
        default_factory=EndpointConfig, description='API server configuration'
    )
    monitor_config: MonitorConfig = Field(
        default_factory=MonitorConfig, description='Monitor configuration'
    )
    research_agent_config: ResearchAgentConfig = Field(
        default_factory=ResearchAgentConfig, description='Research agent configuration'
    )
    research_agent_llm_config: ResearchAgentLLMConfig = Field(
        default_factory=ResearchAgentLLMConfig,
        description='Research agent LLM configuration',
    )
    scrape_filter_llm_config: ScrapeFilterLLMConfig = Field(
        default_factory=ScrapeFilterLLMConfig,
        description='Scrape filter LLM configuration',
    )
    discovery_config: DiscoveryConfig = Field(
        default_factory=DiscoveryConfig, description='Discovery system configuration'
    )
    rag_config: RAGConfig = Field(
        default_factory=RAGConfig, description='RAG system configuration'
    )
    query_based_routing_config: QueryBasedRoutingConfig = Field(
        default_factory=QueryBasedRoutingConfig,
        description='Query-based routing configuration',
    )

    def setup_logging(self) -> None:
        """Set up logging configuration using loguru."""
        setup_logging(self)


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

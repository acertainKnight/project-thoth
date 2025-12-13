"""
Single unified configuration system for Thoth.

This module provides ONE configuration object that:
1. Detects Obsidian vault location from OBSIDIAN_VAULT_PATH
2. Loads ALL user settings from vault_root/_thoth/settings.json (UNCHANGED)
3. Loads secrets from .env file (for keys not in settings.json)
4. Resolves all paths to absolute at startup (only change: vault-relative)
5. Exports a single global 'config' object

IMPORTANT: This reads the existing settings.json file WITHOUT modification.
All your custom model configurations, temperatures, and settings are preserved.
The ONLY change is path resolution - converting relative paths to absolute.

Usage throughout codebase:
    from thoth.config import config

    # Access nested settings exactly as before:
    model = config.llm_config.default.model
    citation_model = config.llm_config.citation.model
    tag_model = config.llm_config.tag_consolidator.consolidate_model

    # Paths are now absolute (resolved at startup):
    pdf_path = config.pdf_dir / "paper.pdf"
    api_key = config.api_keys.openai_key
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================================
# 1. VAULT DETECTION
# ============================================================================


def get_vault_root() -> Path:
    """Get vault root from OBSIDIAN_VAULT_PATH or auto-detect.

    Priority:
    1. OBSIDIAN_VAULT_PATH environment variable
    2. THOTH_VAULT_PATH environment variable (legacy)
    3. Auto-detect by walking up looking for _thoth/ directory

    Returns:
        Path to vault root

    Raises:
        ValueError: If vault cannot be detected
    """
    # 1. Check OBSIDIAN_VAULT_PATH
    if vault := os.getenv('OBSIDIAN_VAULT_PATH'):
        path = Path(vault).expanduser().resolve()
        if path.exists():
            logger.info(f"Vault detected from OBSIDIAN_VAULT_PATH: {path}")
            return path
        logger.warning(
            f"OBSIDIAN_VAULT_PATH set to '{vault}' but path doesn't exist"
        )

    # 2. Check THOTH_VAULT_PATH (legacy support)
    if vault := os.getenv('THOTH_VAULT_PATH'):
        path = Path(vault).expanduser().resolve()
        if path.exists():
            logger.info(f"Vault detected from THOTH_VAULT_PATH: {path}")
            return path
        logger.warning(f"THOTH_VAULT_PATH set to '{vault}' but path doesn't exist")

    # 3. Auto-detect by walking up looking for _thoth/ directory
    current = Path.cwd()
    for _ in range(6):  # Check up to 5 parent levels
        thoth_dir = current / '_thoth'
        if thoth_dir.exists() and thoth_dir.is_dir():
            logger.info(f"Vault auto-detected at: {current}")
            return current

        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    # 4. Check specific known location based on your setup
    known_location = Path.home() / 'Documents' / 'thoth'
    if (known_location / '_thoth').exists():
        logger.info(f"Vault found at known location: {known_location}")
        return known_location

    raise ValueError(
        "Could not detect vault. Please set OBSIDIAN_VAULT_PATH:\n"
        "  export OBSIDIAN_VAULT_PATH=/path/to/your/vault\n\n"
        "Or run from within vault directory (contains _thoth/)"
    )


# ============================================================================
# 2. PYDANTIC MODELS - Map to your existing settings.json structure
# ============================================================================


class APIKeys(BaseModel):
    """API keys from settings.json - exactly as you have them."""

    mistral_key: str = Field(default='', alias='mistralKey')
    openrouter_key: str = Field(default='', alias='openrouterKey')
    openai_key: str = Field(default='', alias='openaiKey')
    anthropic_key: str = Field(default='', alias='anthropicKey')
    opencitations_key: str = Field(default='', alias='opencitationsKey')
    google_api_key: str = Field(default='', alias='googleApiKey')
    google_search_engine_id: str = Field(default='', alias='googleSearchEngineId')
    semantic_scholar_key: str = Field(default='', alias='semanticScholarKey')
    web_search_key: str = Field(default='', alias='webSearchKey')
    web_search_providers: List[str] = Field(
        default_factory=list, alias='webSearchProviders'
    )
    letta_api_key: str = Field(default='', alias='lettaApiKey')
    unpaywall_email: str = Field(default='', alias='unpaywallEmail')

    class Config:
        populate_by_name = True


class LLMDefaultConfig(BaseModel):
    """LLM default configuration - preserves ALL your settings."""

    model: str = 'google/gemini-2.5-flash'
    temperature: float = 0.9
    max_tokens: int = Field(default=500000, alias='maxTokens')
    top_p: float = Field(default=1.0, alias='topP')
    frequency_penalty: float = Field(default=0.0, alias='frequencyPenalty')
    presence_penalty: float = Field(default=0.0, alias='presencePenalty')
    streaming: bool = False
    use_rate_limiter: bool = Field(default=True, alias='useRateLimiter')
    doc_processing: str = Field(default='auto', alias='docProcessing')
    max_output_tokens: int = Field(default=500000, alias='maxOutputTokens')
    max_context_length: int = Field(default=8000, alias='maxContextLength')
    chunk_size: int = Field(default=4000, alias='chunkSize')
    chunk_overlap: int = Field(default=200, alias='chunkOverlap')
    refine_threshold_multiplier: float = Field(
        default=1.2, alias='refineThresholdMultiplier'
    )
    map_reduce_threshold_multiplier: float = Field(
        default=3.0, alias='mapReduceThresholdMultiplier'
    )

    class Config:
        populate_by_name = True


class LLMCitationModels(BaseModel):
    """Citation sub-models."""

    document_citation: Optional[str] = Field(default=None, alias='documentCitation')
    reference_cleaning: Optional[str] = Field(default=None, alias='referenceCleaning')
    structured_extraction: Optional[str] = Field(
        default=None, alias='structuredExtraction'
    )
    batch_structured_extraction: Optional[str] = Field(
        default=None, alias='batchStructuredExtraction'
    )

    class Config:
        populate_by_name = True


class LLMCitationConfig(BaseModel):
    """Citation LLM configuration."""

    model: str = 'openai/gpt-4o-mini'
    temperature: float = 0.9
    max_tokens: int = Field(default=10000, alias='maxTokens')
    max_output_tokens: int = Field(default=10000, alias='maxOutputTokens')
    max_context_length: int = Field(default=4000, alias='maxContextLength')
    models: LLMCitationModels = Field(default_factory=LLMCitationModels)

    class Config:
        populate_by_name = True


class LLMTagConsolidatorConfig(BaseModel):
    """Tag consolidator LLM configuration."""

    consolidate_model: str = Field(
        default='google/gemini-2.5-flash', alias='consolidateModel'
    )
    suggest_model: str = Field(default='google/gemini-2.5-flash', alias='suggestModel')
    map_model: str = Field(default='google/gemini-2.5-flash', alias='mapModel')
    temperature: float = 0.9
    max_tokens: int = Field(default=10000, alias='maxTokens')
    max_output_tokens: int = Field(default=10000, alias='maxOutputTokens')
    max_context_length: int = Field(default=8000, alias='maxContextLength')

    class Config:
        populate_by_name = True


class LLMResearchAgentConfig(BaseModel):
    """Research agent LLM configuration."""

    model: str = 'google/gemini-3-pro-preview'
    temperature: float = 0.9
    max_tokens: int = Field(default=50000, alias='maxTokens')
    max_output_tokens: int = Field(default=50000, alias='maxOutputTokens')
    max_context_length: int = Field(default=100000, alias='maxContextLength')
    use_auto_model_selection: bool = Field(
        default=False, alias='useAutoModelSelection'
    )
    auto_model_require_tool_calling: bool = Field(
        default=False, alias='autoModelRequireToolCalling'
    )
    auto_model_require_structured_output: bool = Field(
        default=False, alias='autoModelRequireStructuredOutput'
    )

    class Config:
        populate_by_name = True

    @property
    def model_settings(self):
        """Get model settings for backward compatibility."""
        return self


class LLMScrapeFilterConfig(BaseModel):
    """Scrape filter LLM configuration."""

    model: str = 'google/gemini-2.5-flash'
    temperature: float = 0.9
    max_tokens: int = Field(default=10000, alias='maxTokens')
    max_output_tokens: int = Field(default=10000, alias='maxOutputTokens')
    max_context_length: int = Field(default=50000, alias='maxContextLength')

    class Config:
        populate_by_name = True

    @property
    def model_settings(self):
        """Get model settings for backward compatibility."""
        return self


class LLMQueryBasedRoutingConfig(BaseModel):
    """Query-based routing configuration."""

    enabled: bool = False
    routing_model: str = Field(
        default='google/gemini-2.5-flash', alias='routingModel'
    )
    use_dynamic_prompt: bool = Field(default=False, alias='useDynamicPrompt')

    class Config:
        populate_by_name = True


class LLMConfig(BaseModel):
    """Complete LLM configuration - ALL your model settings."""

    default: LLMDefaultConfig = Field(default_factory=LLMDefaultConfig)
    citation: LLMCitationConfig = Field(default_factory=LLMCitationConfig)
    tag_consolidator: LLMTagConsolidatorConfig = Field(
        default_factory=LLMTagConsolidatorConfig, alias='tagConsolidator'
    )
    research_agent: LLMResearchAgentConfig = Field(
        default_factory=LLMResearchAgentConfig, alias='researchAgent'
    )
    scrape_filter: LLMScrapeFilterConfig = Field(
        default_factory=LLMScrapeFilterConfig, alias='scrapeFilter'
    )
    query_based_routing: LLMQueryBasedRoutingConfig = Field(
        default_factory=LLMQueryBasedRoutingConfig, alias='queryBasedRouting'
    )

    class Config:
        populate_by_name = True

    # Convenience properties to access default config attributes
    @property
    def model(self) -> str:
        """Get default model."""
        return self.default.model

    @property
    def model_settings(self):
        """Get default model settings (for backward compatibility)."""
        return self.default

    @property
    def temperature(self) -> float:
        """Get default temperature."""
        return self.default.temperature

    @property
    def max_tokens(self) -> int:
        """Get default max_tokens."""
        return self.default.max_tokens

    @property
    def max_output_tokens(self) -> int:
        """Get default max_output_tokens."""
        return self.default.max_output_tokens

    @property
    def max_context_length(self) -> int:
        """Get default max_context_length."""
        return self.default.max_context_length

    @property
    def chunk_size(self) -> int:
        """Get default chunk_size for document processing."""
        return self.default.chunk_size

    @property
    def chunk_overlap(self) -> int:
        """Get default chunk_overlap for document processing."""
        return self.default.chunk_overlap

    @property
    def top_p(self) -> float:
        """Get default top_p."""
        return self.default.top_p

    @property
    def frequency_penalty(self) -> float:
        """Get default frequency_penalty."""
        return self.default.frequency_penalty

    @property
    def presence_penalty(self) -> float:
        """Get default presence_penalty."""
        return self.default.presence_penalty

    @property
    def streaming(self) -> bool:
        """Get default streaming setting."""
        return self.default.streaming

    @property
    def use_rate_limiter(self) -> bool:
        """Get default use_rate_limiter setting."""
        return self.default.use_rate_limiter

    @property
    def doc_processing(self) -> str:
        """Get default doc_processing strategy."""
        return self.default.doc_processing

    @property
    def refine_threshold_multiplier(self) -> float:
        """Get default refine_threshold_multiplier."""
        return self.default.refine_threshold_multiplier

    @property
    def map_reduce_threshold_multiplier(self) -> float:
        """Get default map_reduce_threshold_multiplier."""
        return self.default.map_reduce_threshold_multiplier

    @property
    def provider(self) -> str:
        """Get provider from model string or default to openrouter."""
        model = self.default.model
        if '/' in model:
            return model.split('/')[0]
        return 'openrouter'


class RAGQAConfig(BaseModel):
    """RAG QA configuration."""

    model: str = 'google/gemini-2.5-flash'
    temperature: float = 0.2
    max_tokens: int = Field(default=2000, alias='maxTokens')
    retrieval_k: int = Field(default=4, alias='retrievalK')

    class Config:
        populate_by_name = True


class RAGConfig(BaseModel):
    """RAG system configuration."""

    embedding_model: str = Field(
        default='openai/text-embedding-3-small', alias='embeddingModel'
    )
    embedding_batch_size: int = Field(default=100, alias='embeddingBatchSize')
    skip_files_with_images: bool = Field(default=True, alias='skipFilesWithImages')
    vector_db_path: str = Field(default='knowledge/vector_db', alias='vectorDbPath')
    collection_name: str = Field(default='thoth_knowledge', alias='collectionName')
    chunk_size: int = Field(default=1000, alias='chunkSize')
    chunk_overlap: int = Field(default=200, alias='chunkOverlap')
    chunk_encoding: str = Field(default='cl100k_base', alias='chunkEncoding')
    qa: RAGQAConfig = Field(default_factory=RAGQAConfig)

    class Config:
        populate_by_name = True


class LettaMemoryConfig(BaseModel):
    """Letta memory configuration."""

    server_url: str = Field(default='http://localhost:8283', alias='serverUrl')
    agent_name: str = Field(default='thoth_research_agent', alias='agentName')
    core_memory_limit: int = Field(default=10000, alias='coreMemoryLimit')
    archival_memory_enabled: bool = Field(default=True, alias='archivalMemoryEnabled')
    recall_memory_enabled: bool = Field(default=True, alias='recallMemoryEnabled')
    enable_smart_truncation: bool = Field(default=True, alias='enableSmartTruncation')
    consolidation_interval_hours: int = Field(
        default=24, alias='consolidationIntervalHours'
    )
    fallback_enabled: bool = Field(default=True, alias='fallbackEnabled')

    class Config:
        populate_by_name = True


class ThothMemoryPipelineConfig(BaseModel):
    """Thoth memory pipeline configuration."""

    enabled: bool = True
    min_salience: float = Field(default=0.1, alias='minSalience')
    enable_enrichment: bool = Field(default=True, alias='enableEnrichment')
    enable_filtering: bool = Field(default=True, alias='enableFiltering')

    class Config:
        populate_by_name = True


class ThothMemoryRetrievalConfig(BaseModel):
    """Thoth memory retrieval configuration."""

    enabled: bool = True
    relevance_weight: float = Field(default=0.4, alias='relevanceWeight')
    salience_weight: float = Field(default=0.3, alias='salienceWeight')
    recency_weight: float = Field(default=0.2, alias='recencyWeight')
    diversity_weight: float = Field(default=0.1, alias='diversityWeight')

    class Config:
        populate_by_name = True


class ThothMemoryConfig(BaseModel):
    """Thoth memory configuration."""

    vector_backend: str = Field(default='chromadb', alias='vectorBackend')
    namespace: str = 'thoth'
    pipeline: ThothMemoryPipelineConfig = Field(
        default_factory=ThothMemoryPipelineConfig
    )
    retrieval: ThothMemoryRetrievalConfig = Field(
        default_factory=ThothMemoryRetrievalConfig
    )

    class Config:
        populate_by_name = True


class EpisodicSummarizationParameters(BaseModel):
    """Episodic summarization job parameters."""

    analysis_window_hours: int = Field(default=168, alias='analysisWindowHours')
    min_memories_threshold: int = Field(default=10, alias='minMemoriesThreshold')
    cleanup_after_summary: bool = Field(default=False, alias='cleanupAfterSummary')

    class Config:
        populate_by_name = True


class EpisodicSummarizationJob(BaseModel):
    """Episodic summarization job configuration."""

    enabled: bool = True
    interval_hours: int = Field(default=24, alias='intervalHours')
    time_of_day: Optional[str] = Field(default=None, alias='timeOfDay')
    days_of_week: Optional[List[str]] = Field(default=None, alias='daysOfWeek')
    parameters: EpisodicSummarizationParameters = Field(
        default_factory=EpisodicSummarizationParameters
    )

    class Config:
        populate_by_name = True


class MemorySchedulerConfig(BaseModel):
    """Memory scheduler configuration."""

    jobs: Dict[str, EpisodicSummarizationJob] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class MemoryConfig(BaseModel):
    """Complete memory configuration."""

    letta: LettaMemoryConfig = Field(default_factory=LettaMemoryConfig)
    thoth: ThothMemoryConfig = Field(default_factory=ThothMemoryConfig)
    scheduler: MemorySchedulerConfig = Field(default_factory=MemorySchedulerConfig)

    class Config:
        populate_by_name = True


class DiscoveryPaths(BaseModel):
    """Discovery-specific paths."""

    sources: str = 'data/discovery/sources'
    results: str = 'data/discovery/results'
    chrome_configs: str = Field(
        default='data/discovery/chrome_configs', alias='chromeConfigs'
    )

    class Config:
        populate_by_name = True


class PathsConfig(BaseModel):
    """Path configuration."""

    workspace: str = '/workspace'
    pdf: str = 'data/pdf'
    markdown: str = 'data/markdown'
    notes: str = '/thoth/notes'
    prompts: str = 'data/prompts'
    templates: str = 'data/templates'
    output: str = 'data/output'
    knowledge_base: str = Field(default='data/knowledge', alias='knowledgeBase')
    graph_storage: str = Field(
        default='data/graph/citations.graphml', alias='graphStorage'
    )
    queries: str = 'data/queries'
    agent_storage: str = Field(default='data/agent', alias='agentStorage')
    discovery: DiscoveryPaths = Field(default_factory=DiscoveryPaths)
    logs: str = 'logs'

    class Config:
        populate_by_name = True


class EndpointConfig(BaseModel):
    """API endpoint configuration."""

    host: str = '0.0.0.0'
    port: int = 8000
    base_url: str = Field(default='http://localhost:8000', alias='baseUrl')
    auto_start: bool = Field(default=False, alias='autoStart')

    class Config:
        populate_by_name = True


class MCPConfig(BaseModel):
    """MCP server configuration."""

    host: str = 'localhost'
    port: int = 8001
    auto_start: bool = Field(default=True, alias='autoStart')
    enabled: bool = True

    class Config:
        populate_by_name = True


class MonitorConfig(BaseModel):
    """Monitor configuration."""

    auto_start: bool = Field(default=True, alias='autoStart')
    watch_interval: int = Field(default=10, alias='watchInterval')
    bulk_process_size: int = Field(default=10, alias='bulkProcessSize')
    watch_directories: List[str] = Field(
        default_factory=list, alias='watchDirectories'
    )
    recursive: bool = True
    optimized: bool = True

    class Config:
        populate_by_name = True


class ServersConfig(BaseModel):
    """Servers configuration."""

    api: EndpointConfig = Field(default_factory=EndpointConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    monitor: MonitorConfig = Field(default_factory=MonitorConfig)

    class Config:
        populate_by_name = True


class ChromeExtensionConfig(BaseModel):
    """Chrome extension configuration."""

    enabled: bool = True
    host: str = 'localhost'
    port: int = 8765

    class Config:
        populate_by_name = True


class WebSearchConfig(BaseModel):
    """Web search configuration."""

    providers: List[str] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class DiscoveryConfig(BaseModel):
    """Discovery system configuration."""

    auto_start_scheduler: bool = Field(default=False, alias='autoStartScheduler')
    default_max_articles: int = Field(default=50, alias='defaultMaxArticles')
    default_interval_minutes: int = Field(
        default=60, alias='defaultIntervalMinutes'
    )
    rate_limit_delay: float = Field(default=1.0, alias='rateLimitDelay')
    chrome_extension: ChromeExtensionConfig = Field(
        default_factory=ChromeExtensionConfig, alias='chromeExtension'
    )
    web_search: WebSearchConfig = Field(
        default_factory=WebSearchConfig, alias='webSearch'
    )

    class Config:
        populate_by_name = True


class CitationAPIsConfig(BaseModel):
    """Citation APIs configuration."""

    use_opencitations: bool = Field(default=True, alias='useOpencitations')
    use_scholarly: bool = Field(default=True, alias='useScholarly')
    use_semantic_scholar: bool = Field(default=False, alias='useSemanticScholar')
    use_arxiv: bool = Field(default=False, alias='useArxiv')

    class Config:
        populate_by_name = True


class CitationProcessingConfig(BaseModel):
    """Citation processing configuration."""

    mode: str = 'single'
    batch_size: int = Field(default=5, alias='batchSize')

    class Config:
        populate_by_name = True


class CitationConfig(BaseModel):
    """Citation configuration."""

    link_format: str = Field(default='uri', alias='linkFormat')
    style: str = 'IEEE'
    apis: CitationAPIsConfig = Field(default_factory=CitationAPIsConfig)
    processing: CitationProcessingConfig = Field(
        default_factory=CitationProcessingConfig
    )

    class Config:
        populate_by_name = True


class WorkersConfig(BaseModel):
    """Workers configuration."""

    tag_mapping: str = Field(default='auto', alias='tagMapping')
    article_processing: str = Field(default='auto', alias='articleProcessing')
    content_analysis: str = Field(default='auto', alias='contentAnalysis')
    citation_enhancement: str = Field(default='auto', alias='citationEnhancement')
    citation_pdf: str = Field(default='auto', alias='citationPdf')
    citation_extraction: str = Field(default='auto', alias='citationExtraction')

    class Config:
        populate_by_name = True


class OCRConfig(BaseModel):
    """OCR configuration."""

    max_concurrent: int = Field(default=3, alias='maxConcurrent')
    enable_caching: bool = Field(default=True, alias='enableCaching')
    cache_ttl_hours: int = Field(default=24, alias='cacheTtlHours')

    class Config:
        populate_by_name = True


class AsyncConfig(BaseModel):
    """Async configuration."""

    enabled: bool = True
    timeout_seconds: int = Field(default=300, alias='timeoutSeconds')

    class Config:
        populate_by_name = True


class PerformanceMemoryConfig(BaseModel):
    """Performance memory configuration."""

    optimization_enabled: bool = Field(default=True, alias='optimizationEnabled')
    chunk_processing_enabled: bool = Field(
        default=True, alias='chunkProcessingEnabled'
    )
    max_document_size_mb: int = Field(default=50, alias='maxDocumentSizeMb')

    class Config:
        populate_by_name = True


class SemanticScholarConfig(BaseModel):
    """Semantic Scholar configuration."""

    max_retries: int = Field(default=3, alias='maxRetries')
    max_backoff_seconds: float = Field(default=30.0, alias='maxBackoffSeconds')
    backoff_multiplier: float = Field(default=1.5, alias='backoffMultiplier')

    class Config:
        populate_by_name = True


class PerformanceConfig(BaseModel):
    """Performance configuration."""

    auto_scale_workers: bool = Field(default=True, alias='autoScaleWorkers')
    workers: WorkersConfig = Field(default_factory=WorkersConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    async_: AsyncConfig = Field(default_factory=AsyncConfig, alias='async')
    memory: PerformanceMemoryConfig = Field(default_factory=PerformanceMemoryConfig)
    semantic_scholar: SemanticScholarConfig = Field(
        default_factory=SemanticScholarConfig, alias='semanticScholar'
    )

    class Config:
        populate_by_name = True


class LoggingRotationConfig(BaseModel):
    """Logging rotation configuration."""

    enabled: bool = True
    max_bytes: int = Field(default=10485760, alias='maxBytes')
    backup_count: int = Field(default=3, alias='backupCount')

    class Config:
        populate_by_name = True


class LoggingFileConfig(BaseModel):
    """Logging file configuration."""

    enabled: bool = True
    path: str = '/workspace/logs/thoth.log'
    mode: str = 'a'
    level: str = 'WARNING'
    rotation: str = '10 MB'
    retention: str = '7 days'
    compression: str = 'zip'

    class Config:
        populate_by_name = True


class LoggingConsoleConfig(BaseModel):
    """Logging console configuration."""

    enabled: bool = True
    level: str = 'WARNING'

    class Config:
        populate_by_name = True


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = 'WARNING'
    format: str = '{time} | {level} | {file}:{line} | {function} | {message}'
    date_format: str = Field(default='YYYY-MM-DD HH:mm:ss', alias='dateFormat')
    rotation: LoggingRotationConfig = Field(default_factory=LoggingRotationConfig)
    file: LoggingFileConfig = Field(default_factory=LoggingFileConfig)
    console: LoggingConsoleConfig = Field(default_factory=LoggingConsoleConfig)

    class Config:
        populate_by_name = True


class APIGatewayConfig(BaseModel):
    """API Gateway configuration."""

    rate_limit: float = Field(default=5.0, alias='rateLimit')
    cache_expiry: int = Field(default=3600, alias='cacheExpiry')
    default_timeout: int = Field(default=15, alias='defaultTimeout')
    endpoints: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class SecurityConfig(BaseModel):
    """Security configuration."""

    session_timeout: int = Field(default=3600, alias='sessionTimeout')
    api_rate_limit: int = Field(default=100, alias='apiRateLimit')

    class Config:
        populate_by_name = True


class EnvironmentConfig(BaseModel):
    """Environment configuration."""

    type: str = 'docker'
    python_unbuffered: bool = Field(default=True, alias='pythonUnbuffered')
    development: bool = False
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    class Config:
        populate_by_name = True


class PostgresConfig(BaseModel):
    """PostgreSQL database configuration."""

    enabled: bool = Field(default=True, alias='enabled')
    pool_min_size: int = Field(default=5, alias='poolMinSize')
    pool_max_size: int = Field(default=20, alias='poolMaxSize')
    connection_timeout: float = Field(default=60.0, alias='connectionTimeout')
    command_timeout: float = Field(default=60.0, alias='commandTimeout')
    retry_attempts: int = Field(default=3, alias='retryAttempts')

    class Config:
        populate_by_name = True


class FeatureFlagsConfig(BaseModel):
    """Feature flags for A/B testing and gradual rollout."""

    use_postgres_for_citations: bool = Field(default=False, alias='usePostgresForCitations')
    use_postgres_for_tags: bool = Field(default=False, alias='usePostgresForTags')
    use_postgres_for_rag_metadata: bool = Field(default=False, alias='usePostgresForRagMetadata')
    enable_cache_layer: bool = Field(default=True, alias='enableCacheLayer')
    cache_ttl_seconds: int = Field(default=300, alias='cacheTtlSeconds')

    class Config:
        populate_by_name = True


class Settings(BaseModel):
    """Complete settings - maps EXACTLY to your settings.json file."""

    schema_: Optional[str] = Field(default=None, alias='$schema')
    version: Optional[str] = None
    last_modified: Optional[str] = Field(default=None, alias='lastModified')
    comment_: Optional[str] = Field(default=None, alias='_comment')

    api_keys: APIKeys = Field(default_factory=APIKeys, alias='apiKeys')
    llm: LLMConfig = Field(default_factory=LLMConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    servers: ServersConfig = Field(default_factory=ServersConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    citation: CitationConfig = Field(default_factory=CitationConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    api_gateway: APIGatewayConfig = Field(
        default_factory=APIGatewayConfig, alias='apiGateway'
    )
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    feature_flags: FeatureFlagsConfig = Field(
        default_factory=FeatureFlagsConfig, alias='featureFlags'
    )

    class Config:
        populate_by_name = True
        extra = 'allow'

    @classmethod
    def from_json_file(cls, settings_file: Path) -> Settings:
        """Load settings from JSON file - reads YOUR settings unchanged.

        Args:
            settings_file: Path to settings.json

        Returns:
            Settings instance with all your configurations
        """
        if not settings_file.exists():
            raise FileNotFoundError(
                f"Settings file not found: {settings_file}\n"
                f"Please ensure your settings.json exists in the vault/_thoth/ directory"
            )

        try:
            data = json.loads(settings_file.read_text())
            logger.info(f"Loaded settings from {settings_file}")
            return cls(**data)
        except Exception as e:
            logger.error(f"Error loading settings from {settings_file}: {e}")
            raise


# ============================================================================
# 3. SECRETS FROM .ENV (Override/supplement settings.json API keys)
# ============================================================================


class Secrets(BaseSettings):
    """Secrets from .env file - supplements/overrides settings.json keys."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # API Keys (override settings.json if set in .env)
    openai_api_key: str = Field(default='', alias='OPENAI_API_KEY')
    anthropic_api_key: str = Field(default='', alias='ANTHROPIC_API_KEY')
    openrouter_api_key: str = Field(default='', alias='OPENROUTER_API_KEY')
    google_api_key: str = Field(default='', alias='GOOGLE_API_KEY')
    mistral_api_key: str = Field(default='', alias='MISTRAL_API_KEY')

    # Database
    database_url: str = Field(default='', alias='DATABASE_URL')

    # Letta/Memory
    letta_api_key: str = Field(default='', alias='LETTA_API_KEY')
    letta_server_url: str = Field(
        default='http://localhost:8283', alias='LETTA_SERVER_URL'
    )

    # Web Search
    serper_api_key: str = Field(default='', alias='SERPER_API_KEY')
    brave_api_key: str = Field(default='', alias='BRAVE_API_KEY')


# ============================================================================
# 4. THE SINGLE CONFIG OBJECT
# ============================================================================


class Config:
    """THE configuration object - preserves ALL your settings.

    Loads your complete settings.json unchanged, only resolves paths to absolute.
    """

    _instance: Config | None = None
    _reload_callbacks: Dict[str, Callable[[Config], None]] = {}

    def __new__(cls) -> Config:
        """Singleton pattern - only one Config instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize configuration by loading vault and ALL settings."""
        if self._initialized:
            return

        # 1. Detect vault
        self.vault_root = get_vault_root()
        logger.info(f"Vault root: {self.vault_root}")

        # 2. Initialize callback system for reload notifications (named callbacks with Config parameter)
        self._reload_callbacks: Dict[str, Callable[[Config], None]] = {}
        self._reload_lock = threading.Lock()

        # 3. Load ALL settings from your existing JSON file
        settings_file = self.vault_root / '_thoth' / 'settings.json'
        self.settings = Settings.from_json_file(settings_file)

        # 4. Load secrets from .env (supplement/override API keys)
        self.secrets = Secrets()

        # 5. Resolve ALL paths to absolute (ONLY change to your settings)
        self._resolve_paths()

        # 6. Configure logging
        self._configure_logging()

        self._initialized = True
        logger.success("Configuration loaded successfully with ALL settings preserved")

    def _resolve_paths(self) -> None:
        """Convert relative paths to absolute (vault-relative).

        This is the ONLY modification - path resolution.
        All other settings preserved exactly as-is.
        """
        paths = self.settings.paths

        def resolve_path(path_str: str) -> Path:
            """Resolve a path relative to vault root.

            Special handling:
            - /workspace -> vault_root (Docker default)
            - /thoth/notes -> vault_root/notes (Docker absolute paths)
            - Relative paths -> vault_root/path
            """
            path = Path(path_str)

            # Special case: /workspace is Docker default, map to vault root
            if path == Path('/workspace'):
                return self.vault_root.resolve()

            # If absolute path starts with /thoth or /workspace, make it vault-relative
            if path.is_absolute():
                path_str_lower = str(path).lower()
                if path_str_lower.startswith('/thoth/'):
                    # /thoth/notes -> vault_root/notes
                    relative_part = str(path)[7:]  # Remove /thoth/
                    return (self.vault_root / relative_part).resolve()
                elif path_str_lower.startswith('/workspace/'):
                    # /workspace/logs -> vault_root/logs
                    relative_part = str(path)[11:]  # Remove /workspace/
                    return (self.vault_root / relative_part).resolve()
                else:
                    # Other absolute paths: use as-is but warn
                    logger.warning(f"Absolute path outside vault: {path} - using as-is")
                    return path.resolve()

            # Relative path: resolve relative to vault root
            return (self.vault_root / path).resolve()

        # Resolve all main paths
        self.workspace_dir = resolve_path(paths.workspace)
        self.pdf_dir = resolve_path(paths.pdf)
        self.markdown_dir = resolve_path(paths.markdown)
        self.notes_dir = resolve_path(paths.notes)
        self.prompts_dir = resolve_path(paths.prompts)
        self.templates_dir = resolve_path(paths.templates)
        self.output_dir = resolve_path(paths.output)
        self.knowledge_base_dir = resolve_path(paths.knowledge_base)
        self.graph_storage_path = resolve_path(paths.graph_storage)
        self.queries_dir = resolve_path(paths.queries)
        self.agent_storage_dir = resolve_path(paths.agent_storage)
        self.logs_dir = resolve_path(paths.logs)

        # Resolve discovery paths
        self.discovery_sources_dir = resolve_path(paths.discovery.sources)
        self.discovery_results_dir = resolve_path(paths.discovery.results)
        self.discovery_chrome_configs_dir = resolve_path(paths.discovery.chrome_configs)

        # Create directories if they don't exist
        for dir_path in [
            self.workspace_dir,
            self.pdf_dir,
            self.markdown_dir,
            self.notes_dir,
            self.prompts_dir,
            self.templates_dir,
            self.output_dir,
            self.knowledge_base_dir,
            self.queries_dir,
            self.agent_storage_dir,
            self.logs_dir,
            self.discovery_sources_dir,
            self.discovery_results_dir,
            self.discovery_chrome_configs_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {dir_path}")

    def _configure_logging(self) -> None:
        """Configure loguru logging based on your settings."""
        log_config = self.settings.logging

        # Remove default handler
        logger.remove()

        # Add console handler if enabled
        if log_config.console.enabled:
            logger.add(
                lambda msg: print(msg, end=''),
                level=log_config.console.level,
                format=log_config.format.replace('{file}', '<cyan>{file}</cyan>')
                .replace('{line}', '<cyan>{line}</cyan>')
                .replace('{function}', '<cyan>{function}</cyan>')
                .replace('{level}', '<level>{level}</level>')
                .replace('{message}', '<level>{message}</level>'),
            )

        # Add file handler if enabled
        if log_config.file.enabled:
            log_file = self.logs_dir / Path(log_config.file.path).name
            logger.add(
                log_file,
                level=log_config.file.level,
                rotation=log_config.file.rotation,
                retention=log_config.file.retention,
                compression=log_config.file.compression,
                format=log_config.format,
            )

    @classmethod
    def register_reload_callback(cls, name: str, callback: Callable[[Config], None]) -> None:
        """
        Register a callback to be called after config reload.

        Args:
            name: Unique identifier for the callback
            callback: Function that takes Config instance as parameter

        Example:
            def on_config_reload(config: Config):
                print(f"Config reloaded: {config.vault_root}")

            Config.register_reload_callback("my_service", on_config_reload)
        """
        if not cls._instance:
            cls._instance = cls()

        cls._instance._reload_callbacks[name] = callback
        logger.debug(f"Registered reload callback: {name}")

    @classmethod
    def unregister_reload_callback(cls, name: str) -> None:
        """Unregister a reload callback."""
        if cls._instance and name in cls._instance._reload_callbacks:
            del cls._instance._reload_callbacks[name]
            logger.debug(f"Unregistered reload callback: {name}")

    def _notify_reload_callbacks(self) -> None:
        """Notify all registered callbacks after successful reload."""
        for name, callback in self._reload_callbacks.items():
            try:
                callback(self)
                logger.debug(f"✓ Notified callback: {name}")
            except Exception as e:
                logger.error(f"Callback '{name}' failed: {e}")

    def reload_settings(self) -> None:
        """
        Reload settings from JSON file (hot-reload support).

        This method:
        1. Reloads settings from vault/_thoth/settings.json
        2. Resolves all paths
        3. Reconfigures logging
        4. Notifies all registered callbacks

        Thread-safe and can be called at any time.
        """
        logger.info("Reloading settings from JSON...")

        try:
            # Store old config for rollback
            old_settings = self.settings
            old_paths = {
                'workspace': self.workspace_dir,
                'pdf': self.pdf_dir,
                'markdown': self.markdown_dir,
                'notes': self.notes_dir,
            }

            # Load new settings
            settings_file = self.vault_root / '_thoth' / 'settings.json'
            self.settings = Settings.from_json_file(settings_file)

            # Resolve paths
            self._resolve_paths()

            # Reconfigure logging
            self._configure_logging()

            logger.success("✅ Settings reloaded successfully")

            # Notify all callbacks
            self._notify_reload_callbacks()

        except Exception as e:
            logger.error(f"Settings reload failed: {e}")
            # Rollback to old settings
            if 'old_settings' in locals():
                self.settings = old_settings
                self.workspace_dir = old_paths['workspace']
                self.pdf_dir = old_paths['pdf']
                self.markdown_dir = old_paths['markdown']
                self.notes_dir = old_paths['notes']
                logger.warning("Rolled back to previous settings")
            raise

    # ========================================================================
    # Convenience properties - access your settings easily
    # ========================================================================

    @property
    def reload_callback_count(self) -> int:
        """Get number of registered reload callbacks.

        This property is thread-safe and useful for monitoring.

        Returns:
            Number of currently registered callbacks
        """
        with self._reload_lock:
            return len(self._reload_callbacks)

    @property
    def api_keys(self) -> APIKeys:
        """Get all API keys."""
        return self.settings.api_keys

    @property
    def llm_config(self) -> LLMConfig:
        """Get complete LLM configuration."""
        return self.settings.llm

    @property
    def rag_config(self) -> RAGConfig:
        """Get RAG configuration."""
        return self.settings.rag

    @property
    def memory_config(self) -> MemoryConfig:
        """Get memory configuration."""
        return self.settings.memory

    @property
    def servers_config(self) -> ServersConfig:
        """Get servers configuration."""
        return self.settings.servers

    @property
    def discovery_config(self) -> DiscoveryConfig:
        """Get discovery configuration."""
        return self.settings.discovery

    @property
    def citation_config(self) -> CitationConfig:
        """Get citation configuration."""
        return self.settings.citation

    @property
    def performance_config(self) -> PerformanceConfig:
        """Get performance configuration."""
        return self.settings.performance

    @property
    def logging_config(self) -> LoggingConfig:
        """Get logging configuration."""
        return self.settings.logging

    @property
    def api_gateway_config(self) -> APIGatewayConfig:
        """Get API gateway configuration."""
        return self.settings.api_gateway

    @property
    def environment_config(self) -> EnvironmentConfig:
        """Get environment configuration."""
        return self.settings.environment

    @property
    def postgres_config(self) -> PostgresConfig:
        """Get PostgreSQL configuration."""
        return self.settings.postgres

    @property
    def feature_flags_config(self) -> FeatureFlagsConfig:
        """Get feature flags configuration."""
        return self.settings.feature_flags

    # Additional convenience properties for sub-configs
    @property
    def tag_consolidator_llm_config(self) -> LLMTagConsolidatorConfig:
        """Get tag consolidator LLM configuration."""
        return self.settings.llm.tag_consolidator

    @property
    def query_based_routing_config(self) -> LLMQueryBasedRoutingConfig:
        """Get query-based routing configuration."""
        return self.settings.llm.query_based_routing

    @property
    def research_agent_llm_config(self) -> LLMResearchAgentConfig:
        """Get research agent LLM configuration."""
        return self.settings.llm.research_agent

    @property
    def mcp_host(self) -> str:
        """Get MCP server host for HTTP fallback connection."""
        return os.getenv('THOTH_MCP_HOST', 'thoth-mcp')

    @property
    def mcp_port(self) -> int:
        """Get MCP server port for HTTP fallback connection."""
        return int(os.getenv('THOTH_MCP_PORT', '8001'))

    def __repr__(self) -> str:
        """String representation of config."""
        return (
            f"Config(vault_root={self.vault_root}, "
            f"model={self.llm_config.default.model}, "
            f"log_level={self.logging_config.level})"
        )


# ============================================================================
# 5. GLOBAL CONFIG INSTANCE - Import this everywhere
# ============================================================================

config = Config()

# ============================================================================
# Usage throughout codebase:
#
# from thoth.config import config, Config
#
# # Access ALL your settings exactly as before:
# default_model = config.llm_config.default.model  # google/gemini-2.5-flash
# citation_model = config.llm_config.citation.model  # openai/gpt-4o-mini
# tag_consolidate = config.llm_config.tag_consolidator.consolidate_model
# research_model = config.llm_config.research_agent.model
# scrape_model = config.llm_config.scrape_filter.model
#
# # Paths are now absolute (resolved at startup):
# pdf_path = config.pdf_dir / "paper.pdf"
#
# # API keys from settings.json or .env:
# openai_key = config.api_keys.openai_key
# openrouter_key = config.api_keys.openrouter_key
#
# # All other settings preserved:
# rag_settings = config.rag_config
# memory_settings = config.memory_config
# performance = config.performance_config
#
# # Hot-reload with callbacks:
# def on_config_reload(config: Config):
#     print(f"Config reloaded! Vault: {config.vault_root}")
#
# Config.register_reload_callback("my_service", on_config_reload)
# config.reload_settings()  # Will trigger callback
# ============================================================================


# ============================================================================
# Example usage for testing hot-reload callbacks (commented out):
#
# def test_callback(config: Config):
#     print(f"Config reloaded! Vault: {config.vault_root}")
#     print(f"Current model: {config.llm_config.default.model}")
#     print(f"Log level: {config.logging_config.level}")
#
# # Register callback
# Config.register_reload_callback("test", test_callback)
#
# # Trigger reload (will call callback)
# config.reload_settings()
#
# # Unregister when done
# Config.unregister_reload_callback("test")
# ============================================================================

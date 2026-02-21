"""
Single unified configuration system for Thoth.

This module provides ONE configuration object that:
1. Detects Obsidian vault location from OBSIDIAN_VAULT_PATH
2. Loads ALL user settings from vault_root/thoth/_thoth/settings.json (UNCHANGED)
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

from __future__ import annotations  # noqa: I001

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List  # noqa: UP035

from loguru import logger
from pydantic import BaseModel, Field, field_validator  # noqa: F401
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- Vault Detection ---


def get_vault_root() -> Path:
    """Get vault root from OBSIDIAN_VAULT_PATH or auto-detect.

    Priority:
    1. OBSIDIAN_VAULT_PATH environment variable
    2. THOTH_VAULT_PATH environment variable (legacy)
    3. Auto-detect by walking up looking for _thoth/ directory (unless THOTH_DISABLE_AUTODETECT is set)
    4. Check known location (unless THOTH_DISABLE_AUTODETECT is set)

    Returns:
        Path to vault root

    Raises:
        ValueError: If vault cannot be detected

    Environment Variables:
        THOTH_DISABLE_AUTODETECT: Set to '1' to disable auto-detection and known location fallbacks (for testing)
    """  # noqa: W505
    # Check if auto-detection is disabled (for testing)
    disable_autodetect = os.getenv('THOTH_DISABLE_AUTODETECT') == '1'

    # 1. Check OBSIDIAN_VAULT_PATH
    if vault := os.getenv('OBSIDIAN_VAULT_PATH'):
        path = Path(vault).expanduser().resolve()
        if path.exists():
            logger.info(f'Vault detected from OBSIDIAN_VAULT_PATH: {path}')
            return path
        logger.warning(f"OBSIDIAN_VAULT_PATH set to '{vault}' but path doesn't exist")
        # If auto-detection is disabled, raise immediately instead of falling through
        if disable_autodetect:
            raise ValueError(
                f"OBSIDIAN_VAULT_PATH set to '{vault}' but path doesn't exist. "
                'Auto-detection is disabled (THOTH_DISABLE_AUTODETECT=1).'
            )

    # 2. Check THOTH_VAULT_PATH (legacy support)
    if vault := os.getenv('THOTH_VAULT_PATH'):
        path = Path(vault).expanduser().resolve()
        if path.exists():
            logger.info(f'Vault detected from THOTH_VAULT_PATH: {path}')
            return path
        logger.warning(f"THOTH_VAULT_PATH set to '{vault}' but path doesn't exist")
        # If auto-detection is disabled, raise immediately
        if disable_autodetect:
            raise ValueError(
                f"THOTH_VAULT_PATH set to '{vault}' but path doesn't exist. "
                'Auto-detection is disabled (THOTH_DISABLE_AUTODETECT=1).'
            )

    # If auto-detection is disabled, stop here
    if disable_autodetect:
        raise ValueError(
            'Could not detect vault. THOTH_DISABLE_AUTODETECT=1 prevents fallbacks. '
            'Please set OBSIDIAN_VAULT_PATH or THOTH_VAULT_PATH to a valid path.'
        )

    # 3. Auto-detect by walking up looking for thoth/_thoth/ directory
    current = Path.cwd()
    for _ in range(6):  # Check up to 5 parent levels
        thoth_dir = current / 'thoth' / '_thoth'
        # Also check legacy _thoth/ location for backward compat
        legacy_dir = current / '_thoth'
        if thoth_dir.exists() and thoth_dir.is_dir():
            logger.info(f'Vault auto-detected at: {current}')
            return current
        if legacy_dir.exists() and legacy_dir.is_dir():
            logger.info(f'Vault auto-detected at: {current} (legacy _thoth/ layout)')
            return current

        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    # 4. Check specific known location based on your setup
    known_location = Path.home() / 'Documents' / 'thoth'
    if (known_location / 'thoth' / '_thoth').exists():
        logger.info(f'Vault found at known location: {known_location}')
        return known_location
    # Legacy fallback
    if (known_location / '_thoth').exists():
        logger.info(f'Vault found at known location: {known_location} (legacy layout)')
        return known_location

    raise ValueError(
        'Could not detect vault. Please set OBSIDIAN_VAULT_PATH:\n'
        '  export OBSIDIAN_VAULT_PATH=/path/to/your/vault\n\n'
        'Or run from within vault directory (contains thoth/_thoth/)'
    )


# --- Pydantic Models ---


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
    web_search_providers: List[str] = Field(  # noqa: UP006
        default_factory=list, alias='webSearchProviders'
    )
    letta_api_key: str = Field(default='', alias='lettaApiKey')
    unpaywall_email: str = Field(default='', alias='unpaywallEmail')
    cohere_key: str = Field(
        default='', alias='cohereKey', description='Cohere API key for reranking'
    )

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

    document_citation: str | None = Field(default=None, alias='documentCitation')
    reference_cleaning: str | None = Field(default=None, alias='referenceCleaning')
    structured_extraction: str | None = Field(
        default=None, alias='structuredExtraction'
    )
    batch_structured_extraction: str | None = Field(
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
    use_auto_model_selection: bool = Field(default=False, alias='useAutoModelSelection')
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
    routing_model: str = Field(default='google/gemini-2.5-flash', alias='routingModel')
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

    @property
    def model(self) -> str:
        return self.default.model

    @property
    def model_settings(self):
        """Get default model settings (for backward compatibility)."""
        return self.default

    @property
    def temperature(self) -> float:
        return self.default.temperature

    @property
    def max_tokens(self) -> int:
        return self.default.max_tokens

    @property
    def max_output_tokens(self) -> int:
        return self.default.max_output_tokens

    @property
    def max_context_length(self) -> int:
        return self.default.max_context_length

    @property
    def chunk_size(self) -> int:
        return self.default.chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self.default.chunk_overlap

    @property
    def top_p(self) -> float:
        return self.default.top_p

    @property
    def frequency_penalty(self) -> float:
        return self.default.frequency_penalty

    @property
    def presence_penalty(self) -> float:
        return self.default.presence_penalty

    @property
    def streaming(self) -> bool:
        return self.default.streaming

    @property
    def use_rate_limiter(self) -> bool:
        return self.default.use_rate_limiter

    @property
    def doc_processing(self) -> str:
        return self.default.doc_processing

    @property
    def refine_threshold_multiplier(self) -> float:
        return self.default.refine_threshold_multiplier

    @property
    def map_reduce_threshold_multiplier(self) -> float:
        return self.default.map_reduce_threshold_multiplier

    @property
    def provider(self) -> str:
        """Extract provider prefix from model string, default to openrouter."""
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


class AgenticRetrievalConfig(BaseModel):
    """Agentic retrieval configuration."""

    enabled: bool = Field(
        default=False,
        description='Enable agentic retrieval orchestrator',
    )
    max_retries: int = Field(
        default=2,
        alias='maxRetries',
        description='Maximum query rewrite retries on low confidence',
    )
    document_grading_enabled: bool = Field(
        default=True,
        alias='documentGradingEnabled',
        description='Enable LLM-based document relevance grading',
    )
    query_expansion_enabled: bool = Field(
        default=True,
        alias='queryExpansionEnabled',
        description='Enable query expansion for better coverage',
    )
    hallucination_check_enabled: bool = Field(
        default=True,
        alias='hallucinationCheckEnabled',
        description='Enable hallucination detection and correction',
    )
    strict_hallucination_check: bool = Field(
        default=False,
        alias='strictHallucinationCheck',
        description='Use strict mode for hallucination checking',
    )
    web_search_fallback_enabled: bool = Field(
        default=False,
        alias='webSearchFallbackEnabled',
        description='Enable web search fallback when retrieval fails',
    )
    confidence_threshold: float = Field(
        default=0.5,
        alias='confidenceThreshold',
        description='Minimum confidence threshold for accepting results (0-1)',
    )
    crag_upper_threshold: float = Field(
        default=0.7,
        alias='cragUpperThreshold',
        description='Upper threshold for CRAG CORRECT assessment (0-1)',
    )
    crag_lower_threshold: float = Field(
        default=0.4,
        alias='cragLowerThreshold',
        description='Lower threshold for CRAG INCORRECT assessment (0-1)',
    )
    knowledge_refinement_enabled: bool = Field(
        default=True,
        alias='knowledgeRefinementEnabled',
        description='Enable knowledge strip decomposition and filtering',
    )
    max_strips_per_document: int = Field(
        default=20,
        alias='maxStripsPerDocument',
        description='Maximum knowledge strips per document (controls LLM cost)',
    )

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

    # Hybrid search configuration
    hybrid_search_enabled: bool = Field(default=True, alias='hybridSearchEnabled')
    hybrid_rrf_k: int = Field(
        default=60,
        alias='hybridRrfK',
        description='RRF constant for rank fusion (typically 60)',
    )
    hybrid_vector_weight: float = Field(
        default=0.7,
        alias='hybridVectorWeight',
        description='Weight for vector search in hybrid fusion (0.0-1.0)',
    )
    hybrid_text_weight: float = Field(
        default=0.3,
        alias='hybridTextWeight',
        description='Weight for text search in hybrid fusion (0.0-1.0)',
    )
    full_text_backend: str = Field(
        default='tsvector',
        alias='fullTextBackend',
        description='Full-text search backend: tsvector (default) or paradedb',
    )

    # Reranking configuration
    reranking_enabled: bool = Field(default=True, alias='rerankingEnabled')
    reranker_provider: str = Field(
        default='auto',
        alias='rerankerProvider',
        description='Reranker provider: auto, cohere, llm, or none',
    )
    reranker_model: str = Field(
        default='rerank-v3.5',
        alias='rerankerModel',
        description='Reranker model name (for Cohere)',
    )
    reranker_top_n: int = Field(
        default=5,
        alias='rerankerTopN',
        description='Number of top results after reranking',
    )
    retrieval_candidates: int = Field(
        default=30,
        alias='retrievalCandidates',
        description='Number of candidates to retrieve before reranking',
    )

    # Contextual enrichment configuration
    contextual_enrichment_enabled: bool = Field(
        default=False,
        alias='contextualEnrichmentEnabled',
        description='Enable Anthropic-style contextual retrieval (adds context to chunks before embedding)',
    )
    contextual_enrichment_model: str = Field(
        default='google/gemini-2.0-flash-lite',
        alias='contextualEnrichmentModel',
        description='Model for generating chunk context (use cheap model)',
    )

    # Adaptive routing configuration
    adaptive_routing_enabled: bool = Field(
        default=False,
        alias='adaptiveRoutingEnabled',
        description='Enable adaptive query routing (classifies queries and selects strategy)',
    )
    use_semantic_router: bool = Field(
        default=False,
        alias='useSemanticRouter',
        description='Use semantic-router library for ML-based classification (requires installation)',
    )
    crag_confidence_threshold: float = Field(
        default=0.6,
        alias='cragConfidenceThreshold',
        description='Confidence threshold for CRAG fallback (0-1, lower = more aggressive)',
    )

    # Agentic retrieval configuration
    agentic_retrieval: AgenticRetrievalConfig = Field(
        default_factory=AgenticRetrievalConfig,
        alias='agenticRetrieval',
        description='Agentic retrieval settings for adaptive, self-correcting RAG',
    )

    class Config:
        populate_by_name = True


class LettaFilesystemConfig(BaseModel):
    """Letta filesystem synchronization configuration."""

    enabled: bool = True
    folder_name: str = Field(default='thoth_processed_articles', alias='folderName')
    embedding_model: str = Field(
        default='openai/text-embedding-3-small', alias='embeddingModel'
    )
    auto_sync: bool = Field(default=False, alias='autoSync')
    sync_on_startup: bool = Field(default=False, alias='syncOnStartup')
    debounce_seconds: int = Field(default=5, alias='debounceSeconds')

    class Config:
        populate_by_name = True


class LettaMemoryConfig(BaseModel):
    """Letta memory configuration."""

    # Deployment mode
    mode: str = Field(
        default='self-hosted',
        alias='mode',
        description='Deployment mode: "cloud" for Letta Cloud, "self-hosted" for local server',
    )

    # Self-hosted configuration
    server_url: str = Field(default='http://localhost:8283', alias='serverUrl')

    # Cloud configuration
    cloud_api_key: str = Field(
        default='',
        alias='cloudApiKey',
        description='Letta Cloud API key (optional if using OAuth)',
    )

    # OAuth configuration
    oauth_enabled: bool = Field(
        default=True,
        alias='oauthEnabled',
        description='Use OAuth for Letta Cloud authentication (recommended)',
    )
    oauth_credentials_path: str = Field(
        default='~/.letta/credentials',
        alias='oauthCredentialsPath',
        description='Path to OAuth credentials file',
    )

    # Agent LLM model (litellm format, e.g. "anthropic/claude-sonnet-4-20250514")
    agent_model: str = Field(
        default='',
        alias='agentModel',
        description=(
            'LLM model for Letta agents in litellm format (e.g. '
            '"anthropic/claude-sonnet-4-20250514"). '
            'Empty string means use Letta server default.'
        ),
    )

    # Agent configuration
    agent_name: str = Field(default='thoth_research_agent', alias='agentName')
    core_memory_limit: int = Field(default=10000, alias='coreMemoryLimit')
    archival_memory_enabled: bool = Field(default=True, alias='archivalMemoryEnabled')
    recall_memory_enabled: bool = Field(default=True, alias='recallMemoryEnabled')
    enable_smart_truncation: bool = Field(default=True, alias='enableSmartTruncation')
    consolidation_interval_hours: int = Field(
        default=24, alias='consolidationIntervalHours'
    )
    fallback_enabled: bool = Field(default=True, alias='fallbackEnabled')
    filesystem: LettaFilesystemConfig = Field(default_factory=LettaFilesystemConfig)

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

    vector_backend: str = Field(default='pgvector', alias='vectorBackend')
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
    time_of_day: str | None = Field(default=None, alias='timeOfDay')
    days_of_week: List[str] | None = Field(default=None, alias='daysOfWeek')  # noqa: UP006
    parameters: EpisodicSummarizationParameters = Field(
        default_factory=EpisodicSummarizationParameters
    )

    class Config:
        populate_by_name = True


class MemorySchedulerConfig(BaseModel):
    """Memory scheduler configuration."""

    jobs: Dict[str, EpisodicSummarizationJob] = Field(default_factory=dict)  # noqa: UP006

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

    sources: str = 'thoth/_thoth/data/discovery/sources'
    results: str = 'thoth/_thoth/data/discovery/results'
    chrome_configs: str = Field(
        default='thoth/_thoth/data/discovery/chrome_configs', alias='chromeConfigs'
    )

    class Config:
        populate_by_name = True


class PathsConfig(BaseModel):
    """Path configuration.

    All paths are relative to the vault root unless absolute.
    User-facing directories live under ``thoth/`` in the vault.
    Internal data lives under ``thoth/_thoth/``.
    """

    workspace: str = 'thoth/_thoth'
    pdf: str = 'thoth/papers/pdfs'
    markdown: str = 'thoth/papers/markdown'
    notes: str = 'thoth/notes'
    prompts: str = 'thoth/_thoth/prompts'
    templates: str = 'thoth/_thoth/templates'
    output: str = 'thoth/_thoth/data/output'
    knowledge_base: str = Field(default='thoth/knowledge', alias='knowledgeBase')
    graph_storage: str = Field(
        default='thoth/_thoth/data/graph/citations.graphml', alias='graphStorage'
    )
    queries: str = 'thoth/_thoth/data/queries'
    agent_storage: str = Field(default='thoth/_thoth/data/agent', alias='agentStorage')
    discovery: DiscoveryPaths = Field(default_factory=DiscoveryPaths)
    logs: str = 'thoth/_thoth/logs'

    class Config:
        populate_by_name = True


class EndpointConfig(BaseModel):
    """API endpoint configuration."""

    host: str = '0.0.0.0'  # nosec B104 - bind all interfaces for server listen
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
    external_servers_file: str | None = Field(
        default=None,
        alias='externalServersFile',
        description='Path to external MCP servers config file (mcps.json)',
    )
    plugins_enabled: bool = Field(
        default=True,
        alias='pluginsEnabled',
        description='Whether external MCP plugins are enabled',
    )
    max_concurrent_plugins: int = Field(
        default=10,
        alias='maxConcurrentPlugins',
        description='Maximum number of concurrent plugin connections',
    )

    class Config:
        populate_by_name = True


class MonitorConfig(BaseModel):
    """Monitor configuration."""

    auto_start: bool = Field(default=True, alias='autoStart')
    watch_interval: int = Field(default=10, alias='watchInterval')
    bulk_process_size: int = Field(default=10, alias='bulkProcessSize')
    watch_directories: List[str] = Field(  # noqa: UP006
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
    """Chrome extension configuration.

    For remote access, set host to '0.0.0.0' and optionally provide an auth_token.
    If no auth_token is provided and host is not localhost, one is auto-generated.
    """

    enabled: bool = True
    host: str = 'localhost'
    port: int = 8765
    auth_token: str | None = None

    class Config:
        populate_by_name = True


class WebSearchConfig(BaseModel):
    """Web search configuration."""

    providers: List[str] = Field(default_factory=list)  # noqa: UP006

    class Config:
        populate_by_name = True


class DiscoveryConfig(BaseModel):
    """Discovery system configuration."""

    auto_start_scheduler: bool = Field(default=False, alias='autoStartScheduler')
    default_max_articles: int = Field(default=50, alias='defaultMaxArticles')
    default_interval_minutes: int = Field(default=60, alias='defaultIntervalMinutes')
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
    use_resolution_chain: bool = Field(
        default=False,  # TEMPORARY: Disabled to test database save fix
        alias='useResolutionChain',
        description='Enable improved citation resolution chain with Crossref, ArXiv, OpenAlex, and Semantic Scholar',
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
    chunk_processing_enabled: bool = Field(default=True, alias='chunkProcessingEnabled')
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
    endpoints: Dict[str, Any] = Field(default_factory=dict)  # noqa: UP006

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

    use_postgres_for_citations: bool = Field(
        default=False, alias='usePostgresForCitations'
    )
    use_postgres_for_tags: bool = Field(default=False, alias='usePostgresForTags')
    use_postgres_for_rag_metadata: bool = Field(
        default=False, alias='usePostgresForRagMetadata'
    )
    enable_cache_layer: bool = Field(default=True, alias='enableCacheLayer')
    cache_ttl_seconds: int = Field(default=300, alias='cacheTtlSeconds')

    class Config:
        populate_by_name = True


class Settings(BaseModel):
    """Complete settings - maps EXACTLY to your settings.json file."""

    schema_: str | None = Field(default=None, alias='$schema')
    version: str | None = None
    last_modified: str | None = Field(default=None, alias='lastModified')
    comment_: str | None = Field(default=None, alias='_comment')

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
            # Create minimal default settings for fresh installation
            logger.warning(f'Settings file not found: {settings_file}')
            logger.info('Creating default settings.json for fresh installation...')

            # Ensure parent directory exists
            settings_file.parent.mkdir(parents=True, exist_ok=True)

            # Create minimal default settings
            default_settings = {
                '$schema': './thoth.settings.schema.json',
                'version': '1.0.0',
                'lastModified': None,
                '_comment': 'Thoth configuration - edit with setup wizard or manually',
                'apiKeys': {},
                'llm': {
                    'default': {
                        'model': 'google/gemini-2.5-flash',
                        'temperature': 0.9,
                        'maxTokens': 500000,
                    }
                },
                'paths': {
                    'workspace': 'thoth/_thoth',
                    'pdf': 'thoth/papers/pdfs',
                    'markdown': 'thoth/papers/markdown',
                    'notes': 'thoth/notes',
                    'prompts': 'thoth/_thoth/prompts',
                    'templates': 'thoth/_thoth/templates',
                    'output': 'thoth/_thoth/data/output',
                    'knowledgeBase': 'thoth/knowledge',
                    'queries': 'thoth/_thoth/data/queries',
                    'agentStorage': 'thoth/_thoth/data/agent',
                    'logs': 'thoth/_thoth/logs',
                },
                'servers': {
                    'api': {'host': '0.0.0.0', 'port': 8000, 'autoStart': False},  # nosec B104
                    'mcp': {
                        'host': 'localhost',
                        'port': 8001,
                        'autoStart': True,
                        'enabled': True,
                    },
                },
                'logging': {
                    'level': 'WARNING',
                    'file': {'enabled': True, 'path': '/workspace/logs/thoth.log'},
                },
            }

            # Write default settings
            settings_file.write_text(json.dumps(default_settings, indent=2))
            logger.success(f'Created default settings at {settings_file}')
            logger.info(
                'You can customize these settings using the setup wizard or by editing the file'
            )

        try:
            data = json.loads(settings_file.read_text())
            logger.info(f'Loaded settings from {settings_file}')
            return cls(**data)
        except Exception as e:
            logger.error(f'Error loading settings from {settings_file}: {e}')
            raise


# --- Secrets from .env ---


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
    letta_mode: str = Field(default='self-hosted', alias='LETTA_MODE')
    letta_api_key: str = Field(default='', alias='LETTA_API_KEY')
    letta_server_url: str = Field(
        default='http://localhost:8283', alias='LETTA_SERVER_URL'
    )
    letta_cloud_api_key: str = Field(default='', alias='LETTA_CLOUD_API_KEY')
    letta_credentials_path: str = Field(
        default='~/.letta/credentials', alias='LETTA_CREDENTIALS_PATH'
    )

    # Web Search
    serper_api_key: str = Field(default='', alias='SERPER_API_KEY')
    brave_api_key: str = Field(default='', alias='BRAVE_API_KEY')


# --- User Config Manager (Multi-User) ---


class UserConfigManager:
    """Manages per-user settings in multi-user mode.

    In multi-user deployments, each user has their own settings.json file
    in their vault. This manager loads and caches per-user Settings objects,
    reloading when files change.

    In single-user mode, this class is not used -- the Config singleton
    loads settings directly from the single vault.
    """

    def __init__(self, vaults_root: Path):
        """Initialize the user config manager.

        Args:
            vaults_root: Root directory containing all user vaults (e.g. /vaults/)
        """
        self._vaults_root = vaults_root
        # Cache: username -> (Settings, mtime)
        self._cache: dict[str, tuple[Settings, float]] = {}
        self._cache_lock = threading.Lock()

    def get_settings(self, username: str) -> Settings:
        """Load settings for a user, using cache when file hasn't changed.

        Args:
            username: The user's username

        Returns:
            Settings object for this user

        Raises:
            FileNotFoundError: If the user's settings.json doesn't exist
        """
        settings_path = (
            self._vaults_root / username / 'thoth' / '_thoth' / 'settings.json'
        )

        if not settings_path.exists():
            # Try legacy location
            legacy_path = self._vaults_root / username / '_thoth' / 'settings.json'
            if legacy_path.exists():
                settings_path = legacy_path
            else:
                raise FileNotFoundError(
                    f"Settings file not found for user '{username}' at {settings_path}"
                )

        # Get current mtime
        current_mtime = settings_path.stat().st_mtime

        with self._cache_lock:
            # Check cache
            if username in self._cache:
                cached_settings, cached_mtime = self._cache[username]
                # If file hasn't changed, return cached version
                if cached_mtime == current_mtime:
                    return cached_settings

            # Load fresh settings
            settings = Settings.from_json_file(settings_path)

            # Update cache
            self._cache[username] = (settings, current_mtime)

            logger.debug(f"Loaded settings for user '{username}' from {settings_path}")
            return settings

    def get_settings_or_default(self, username: str) -> Settings:
        """Return user settings, falling back to a default Settings instance.

        This is useful for background services that process data for users who
        may not have fully initialized settings yet.

        Args:
            username: The user's username

        Returns:
            Settings object (loaded or default)
        """
        try:
            return self.get_settings(username)
        except FileNotFoundError:
            logger.warning(
                f"Settings not found for user '{username}', using default settings"
            )
            return Settings()

    def invalidate_cache(self, username: str | None = None) -> None:
        """Invalidate the settings cache for a user or all users.

        Args:
            username: User to invalidate, or None to invalidate all
        """
        with self._cache_lock:
            if username is None:
                self._cache.clear()
                logger.debug('Invalidated all user settings cache')
            elif username in self._cache:
                del self._cache[username]
                logger.debug(f"Invalidated settings cache for user '{username}'")


# --- User Paths (multi-user path resolution) ---


@dataclass(frozen=True)
class UserPaths:
    """Resolved absolute paths for a specific user's vault.

    Produced by ``Config.resolve_paths_for_vault`` so that services and MCP
    tools can work with user-scoped directories instead of the global config
    paths.
    """

    vault_root: Path
    workspace_dir: Path
    pdf_dir: Path
    markdown_dir: Path
    notes_dir: Path
    prompts_dir: Path
    templates_dir: Path
    output_dir: Path
    knowledge_base_dir: Path
    graph_storage_path: Path
    queries_dir: Path
    agent_storage_dir: Path
    logs_dir: Path
    analysis_schema_path: Path
    discovery_sources_dir: Path
    discovery_results_dir: Path
    discovery_chrome_configs_dir: Path
    data_dir: Path


# --- Config Object ---


class Config:
    """THE configuration object - preserves ALL your settings.

    Loads your complete settings.json unchanged, only resolves paths to absolute.
    """

    _instance: Config | None = None
    _reload_callbacks: Dict[str, Callable[[Config], None]] = {}  # noqa: UP006, RUF012
    _instance_lock = threading.Lock()  # Thread-safe singleton and initialization

    def __new__(cls) -> Config:
        """Singleton pattern - only one Config instance (thread-safe)."""
        # Thread-safe singleton check
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize configuration by loading vault and ALL settings (thread-safe)."""
        # Thread-safe initialization check - prevent multiple threads from initializing
        with self._instance_lock:
            if self._initialized:
                return

            # Mark as initializing immediately to prevent other threads from entering
            # We haven't finished initialization yet, but this prevents race conditions
            self._initialized = True

        # 1. Detect vault
        self.vault_root = get_vault_root()
        logger.info(f'Vault root: {self.vault_root}')

        # 2. Initialize callback system for reload notifications (named callbacks with Config parameter)  # noqa: W505
        self._reload_callbacks: Dict[str, Callable[[Config], None]] = {}  # noqa: UP006
        self._reload_lock = threading.Lock()

        # 3. Load ALL settings from your existing JSON file
        # New location: vault/thoth/_thoth/settings.json
        # Falls back to legacy vault/_thoth/settings.json for migration
        settings_file = self.vault_root / 'thoth' / '_thoth' / 'settings.json'
        if not settings_file.exists():
            legacy_file = self.vault_root / '_thoth' / 'settings.json'
            if legacy_file.exists():
                logger.warning(
                    f'Found settings at legacy location {legacy_file}. '
                    f'Consider moving to {settings_file}'
                )
                settings_file = legacy_file
        self.settings = Settings.from_json_file(settings_file)

        # 4. Load secrets from .env (supplement/override API keys)
        self.secrets = Secrets()

        # 5. Resolve ALL paths to absolute (ONLY change to your settings)
        self._resolve_paths()

        # 6. Configure logging
        self._configure_logging()

        # 7. Multi-user mode detection
        self.multi_user: bool = os.getenv('THOTH_MULTI_USER', 'false').lower() == 'true'
        self.vaults_root: Path | None = None
        self.user_config_manager: UserConfigManager | None = None

        if self.multi_user:
            vaults_root_str = os.getenv('THOTH_VAULTS_ROOT')
            if not vaults_root_str:
                logger.warning(
                    'THOTH_MULTI_USER=true but THOTH_VAULTS_ROOT not set. '
                    'Defaulting to /vaults'
                )
                vaults_root_str = '/vaults'
            self.vaults_root = Path(vaults_root_str).resolve()

            # Initialize UserConfigManager for per-user settings
            self.user_config_manager = UserConfigManager(self.vaults_root)

            logger.info(f'Multi-user mode enabled. Vaults root: {self.vaults_root}')

        self._initialized = True
        logger.success('Configuration loaded successfully with ALL settings preserved')

    def _resolve_paths(self) -> None:
        """Convert relative paths to absolute (vault-relative).

        All paths in settings are relative to the vault root.
        Absolute paths are used as-is (with a warning if outside the vault).
        Legacy Docker paths (/workspace, /thoth/) are migrated automatically.
        """
        paths = self.settings.paths

        def resolve_path(path_str: str) -> Path:
            """Resolve a path relative to vault root.

            Args:
                path_str: Path string from settings (relative or absolute).

            Returns:
                Resolved absolute Path.
            """
            path = Path(path_str)

            # --- Legacy migration: old Docker-era absolute paths ---
            if path == Path('/workspace'):
                return (self.vault_root / 'thoth' / '_thoth').resolve()
            if path.is_absolute():
                path_lower = str(path).lower()
                if path_lower.startswith('/thoth/'):
                    relative_part = str(path)[7:]
                    return (self.vault_root / 'thoth' / relative_part).resolve()
                if path_lower.startswith('/workspace/'):
                    relative_part = str(path)[11:]
                    return (self.vault_root / relative_part).resolve()
                # Other absolute paths: use as-is
                logger.warning(f'Absolute path outside vault: {path} - using as-is')
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

        # Analysis schema path (for customizable document analysis)
        self.analysis_schema_path = resolve_path('thoth/_thoth/analysis_schema.json')

        # Resolve discovery paths
        self.discovery_sources_dir = resolve_path(paths.discovery.sources)
        self.discovery_results_dir = resolve_path(paths.discovery.results)
        self.discovery_chrome_configs_dir = resolve_path(paths.discovery.chrome_configs)

        # Resolve RAG vector_db_path (avoid relative path permission errors)
        rag_config = self.settings.rag
        rag_config.vector_db_path = str(resolve_path(rag_config.vector_db_path))

        # Resolve external MCP servers config path
        mcp_config = self.settings.servers.mcp
        if not mcp_config.external_servers_file:
            # Default to _thoth/mcps.json
            mcp_config.external_servers_file = str(
                self.vault_root / 'thoth' / '_thoth' / 'mcps.json'
            )
        else:
            mcp_config.external_servers_file = str(
                resolve_path(mcp_config.external_servers_file)
            )

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
            self.analysis_schema_path.parent,  # Create parent dir for schema file
        ]:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.debug(f'Ensured directory exists: {dir_path}')
            except PermissionError:
                logger.warning(f'Permission denied creating directory: {dir_path}')

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
    def register_reload_callback(
        cls, name: str, callback: Callable[[Config], None]
    ) -> None:
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

        with cls._instance._reload_lock:
            cls._instance._reload_callbacks[name] = callback
            logger.debug(f'Registered reload callback: {name}')

    @classmethod
    def unregister_reload_callback(cls, name: str) -> None:
        """Unregister a reload callback."""
        if cls._instance:
            with cls._instance._reload_lock:
                if name in cls._instance._reload_callbacks:
                    del cls._instance._reload_callbacks[name]
                    logger.debug(f'Unregistered reload callback: {name}')

    def _notify_reload_callbacks(self) -> None:
        """Notify all registered callbacks after successful reload."""
        for name, callback in self._reload_callbacks.items():
            try:
                callback(self)
                logger.debug(f'Notified callback: {name}')
            except Exception as e:
                logger.error(f"Callback '{name}' failed: {e}")

    def reload_settings(self) -> None:
        """
        Reload settings from JSON file (hot-reload support).

        This method:
        1. Reloads settings from vault/thoth/_thoth/settings.json
        2. Resolves all paths
        3. Reconfigures logging
        4. Notifies all registered callbacks

        Thread-safe and can be called at any time.
        """
        logger.info('Reloading settings from JSON...')

        try:
            # Store old config for rollback
            old_settings = self.settings
            old_paths = {
                'workspace': self.workspace_dir,
                'pdf': self.pdf_dir,
                'markdown': self.markdown_dir,
                'notes': self.notes_dir,
            }

            # Load new settings (check new location first, then legacy)
            settings_file = self.vault_root / 'thoth' / '_thoth' / 'settings.json'
            if not settings_file.exists():
                legacy = self.vault_root / '_thoth' / 'settings.json'
                if legacy.exists():
                    settings_file = legacy
            self.settings = Settings.from_json_file(settings_file)

            # Resolve paths
            self._resolve_paths()

            # Reconfigure logging
            self._configure_logging()

            logger.success('Settings reloaded successfully')

            # Notify all callbacks
            self._notify_reload_callbacks()

        except Exception as e:
            logger.error(f'Settings reload failed: {e}')
            # Rollback to old settings
            if 'old_settings' in locals():
                self.settings = old_settings
                self.workspace_dir = old_paths['workspace']
                self.pdf_dir = old_paths['pdf']
                self.markdown_dir = old_paths['markdown']
                self.notes_dir = old_paths['notes']
                logger.warning('Rolled back to previous settings')
            raise

    # --- Convenience properties ---

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
        return self.settings.api_keys

    @property
    def llm_config(self) -> LLMConfig:
        return self.settings.llm

    @property
    def rag_config(self) -> RAGConfig:
        return self.settings.rag

    @property
    def memory_config(self) -> MemoryConfig:
        return self.settings.memory

    @property
    def servers_config(self) -> ServersConfig:
        return self.settings.servers

    @property
    def discovery_config(self) -> DiscoveryConfig:
        return self.settings.discovery

    @property
    def citation_config(self) -> CitationConfig:
        return self.settings.citation

    @property
    def performance_config(self) -> PerformanceConfig:
        return self.settings.performance

    @property
    def logging_config(self) -> LoggingConfig:
        return self.settings.logging

    @property
    def api_gateway_config(self) -> APIGatewayConfig:
        return self.settings.api_gateway

    @property
    def environment_config(self) -> EnvironmentConfig:
        return self.settings.environment

    @property
    def postgres_config(self) -> PostgresConfig:
        return self.settings.postgres

    @property
    def feature_flags_config(self) -> FeatureFlagsConfig:
        return self.settings.feature_flags

    @property
    def tag_consolidator_llm_config(self) -> LLMTagConsolidatorConfig:
        return self.settings.llm.tag_consolidator

    @property
    def query_based_routing_config(self) -> LLMQueryBasedRoutingConfig:
        return self.settings.llm.query_based_routing

    @property
    def research_agent_llm_config(self) -> LLMResearchAgentConfig:
        return self.settings.llm.research_agent

    @property
    def mcp_host(self) -> str:
        """Get MCP server host for HTTP fallback connection."""
        return os.getenv('THOTH_MCP_HOST', 'thoth-mcp')

    @property
    def mcp_port(self) -> int:
        return int(os.getenv('THOTH_MCP_PORT', '8001'))

    def resolve_user_vault_path(self, username: str) -> Path:
        """
        Resolve the absolute vault path for a specific user.

        In multi-user mode, each user has an isolated vault under THOTH_VAULTS_ROOT.
        In single-user mode, always returns the global vault_root.

        Args:
            username: The user's username

        Returns:
            Absolute path to the user's vault directory

        Example:
            >>> config.resolve_user_vault_path('alice')
            PosixPath('/vaults/alice')
        """
        if self.multi_user and self.vaults_root:
            return self.vaults_root / username
        return self.vault_root

    @property
    def data_dir(self) -> Path:
        """Data directory under workspace (for custom indexes, etc.)."""
        return self.workspace_dir / 'data'

    def resolve_paths_for_vault(
        self,
        vault_root: Path,
        paths_config: PathsConfig | None = None,
    ) -> UserPaths:
        """Resolve all standard paths relative to a specific vault root.

        This is the multi-user equivalent of ``_resolve_paths``. Given a
        user's vault root directory, it returns a ``UserPaths`` with every
        path resolved to an absolute location inside that vault.

        Args:
            vault_root: Absolute path to the user's vault directory.
            paths_config: Optional PathsConfig; defaults to global settings.

        Returns:
            UserPaths with all directories resolved.

        Example:
            >>> paths = config.resolve_paths_for_vault(Path('/vaults/alice'))
            >>> paths.pdf_dir
            PosixPath('/vaults/alice/thoth/papers/pdfs')
        """
        paths = paths_config or self.settings.paths

        def _resolve(path_str: str) -> Path:
            p = Path(path_str)
            if p.is_absolute():
                return p.resolve()
            return (vault_root / p).resolve()

        workspace = _resolve(paths.workspace)

        return UserPaths(
            vault_root=vault_root,
            workspace_dir=workspace,
            pdf_dir=_resolve(paths.pdf),
            markdown_dir=_resolve(paths.markdown),
            notes_dir=_resolve(paths.notes),
            prompts_dir=_resolve(paths.prompts),
            templates_dir=_resolve(paths.templates),
            output_dir=_resolve(paths.output),
            knowledge_base_dir=_resolve(paths.knowledge_base),
            graph_storage_path=_resolve(paths.graph_storage),
            queries_dir=_resolve(paths.queries),
            agent_storage_dir=_resolve(paths.agent_storage),
            logs_dir=_resolve(paths.logs),
            analysis_schema_path=_resolve('thoth/_thoth/analysis_schema.json'),
            discovery_sources_dir=_resolve(paths.discovery.sources),
            discovery_results_dir=_resolve(paths.discovery.results),
            discovery_chrome_configs_dir=_resolve(paths.discovery.chrome_configs),
            data_dir=workspace / 'data',
        )

    def get_user_settings(self, username: str) -> Settings:
        """
        Get effective settings for a user.

        In multi-user mode this reads the user's settings file from their vault.
        In single-user mode this returns the global settings.
        """
        if self.multi_user and self.user_config_manager:
            return self.user_config_manager.get_settings_or_default(username)
        return self.settings

    def __repr__(self) -> str:
        return (
            f'Config(vault_root={self.vault_root}, '
            f'multi_user={self.multi_user}, '
            f'model={self.llm_config.default.model}, '
            f'log_level={self.logging_config.level})'
        )


# --- Global Config Instance ---


# Use __getattr__ to make 'config' dynamically reference the current singleton
# This allows tests to reset Config._instance and have the global config update
def __getattr__(name: str):
    """Lazy evaluation of module-level attributes."""
    if name == 'config':
        return Config()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

"""Tests for Pydantic models in configuration system.

Tests all 20+ nested Pydantic models with valid/invalid data:
- Validation correctness
- CamelCase alias parsing
- Default values
- Field constraints
- Type coercion
"""

import pytest
from pydantic import ValidationError

from tests.fixtures.config_fixtures import (
    sample_api_keys_dict,
    sample_citation_config_dict,
    sample_llm_default_dict,
    sample_logging_config_dict,
    sample_memory_config_dict,
    sample_paths_config_dict,
    sample_rag_config_dict,
)
from thoth.config import (
    APIGatewayConfig,
    APIKeys,
    AsyncConfig,
    ChromeExtensionConfig,
    CitationAPIsConfig,
    CitationConfig,
    CitationProcessingConfig,
    DiscoveryConfig,
    DiscoveryPaths,
    EndpointConfig,
    EnvironmentConfig,
    EpisodicSummarizationJob,
    EpisodicSummarizationParameters,
    FeatureFlagsConfig,
    LettaMemoryConfig,
    LLMCitationConfig,
    LLMCitationModels,
    LLMConfig,
    LLMDefaultConfig,
    LLMQueryBasedRoutingConfig,
    LLMResearchAgentConfig,
    LLMScrapeFilterConfig,
    LLMTagConsolidatorConfig,
    LoggingConfig,
    LoggingConsoleConfig,
    LoggingFileConfig,
    LoggingRotationConfig,
    MCPConfig,
    MemoryConfig,
    MemorySchedulerConfig,
    MonitorConfig,
    OCRConfig,
    PathsConfig,
    PerformanceConfig,
    PerformanceMemoryConfig,
    PostgresConfig,
    RAGConfig,
    RAGQAConfig,
    SecurityConfig,
    SemanticScholarConfig,
    ServersConfig,
    Settings,
    ThothMemoryConfig,
    ThothMemoryPipelineConfig,
    ThothMemoryRetrievalConfig,
    WebSearchConfig,
    WorkersConfig,
)


class TestAPIKeys:
    """Test APIKeys model."""

    def test_valid_api_keys(self, sample_api_keys_dict):
        """Test APIKeys with valid data."""
        keys = APIKeys(**sample_api_keys_dict)

        assert keys.mistral_key == "test-mistral"
        assert keys.openai_key == "test-openai"
        assert keys.anthropic_key == "test-anthropic"
        assert keys.web_search_providers == ["google"]

    def test_api_keys_camel_case_aliases(self):
        """Test camelCase alias parsing."""
        data = {
            "mistralKey": "key1",
            "openrouterKey": "key2",
            "googleApiKey": "key3"
        }
        keys = APIKeys(**data)

        assert keys.mistral_key == "key1"
        assert keys.openrouter_key == "key2"
        assert keys.google_api_key == "key3"

    def test_api_keys_defaults(self):
        """Test default values for API keys."""
        keys = APIKeys()

        assert keys.mistral_key == ""
        assert keys.openai_key == ""
        assert keys.web_search_providers == []

    def test_api_keys_mixed_case(self):
        """Test both snake_case and camelCase work."""
        data = {
            "mistral_key": "snake",
            "openrouterKey": "camel"
        }
        keys = APIKeys(**data)

        assert keys.mistral_key == "snake"
        assert keys.openrouter_key == "camel"


class TestLLMDefaultConfig:
    """Test LLMDefaultConfig model."""

    def test_valid_llm_default(self, sample_llm_default_dict):
        """Test LLMDefaultConfig with valid data."""
        config = LLMDefaultConfig(**sample_llm_default_dict)

        assert config.model == "test-model"
        assert config.temperature == 0.7
        assert config.max_tokens == 2000
        assert config.streaming is True

    def test_llm_default_camel_case(self):
        """Test camelCase aliases."""
        data = {
            "model": "test",
            "maxTokens": 5000,
            "topP": 0.95,
            "frequencyPenalty": 0.3,
            "useRateLimiter": False
        }
        config = LLMDefaultConfig(**data)

        assert config.max_tokens == 5000
        assert config.top_p == 0.95
        assert config.frequency_penalty == 0.3
        assert config.use_rate_limiter is False

    def test_llm_default_defaults(self):
        """Test default values."""
        config = LLMDefaultConfig()

        assert config.model == "google/gemini-2.5-flash"
        assert config.temperature == 0.9
        assert config.max_tokens == 500000
        assert config.streaming is False

    def test_llm_default_invalid_temperature(self):
        """Test validation for invalid temperature."""
        # Note: Pydantic doesn't enforce range by default, just type
        data = {"temperature": "not-a-number"}

        with pytest.raises(ValidationError):
            LLMDefaultConfig(**data)

    def test_llm_default_negative_max_tokens(self):
        """Test negative max_tokens (Pydantic allows but may be invalid logically)."""
        data = {"maxTokens": -1000}

        # Pydantic won't reject this without explicit validator
        config = LLMDefaultConfig(**data)
        assert config.max_tokens == -1000  # Document current behavior


class TestLLMCitationModels:
    """Test LLMCitationModels model."""

    def test_citation_models_all_fields(self):
        """Test with all optional fields provided."""
        data = {
            "documentCitation": "doc-model",
            "referenceCleaning": "ref-model",
            "structuredExtraction": "extract-model",
            "batchStructuredExtraction": "batch-model"
        }
        models = LLMCitationModels(**data)

        assert models.document_citation == "doc-model"
        assert models.reference_cleaning == "ref-model"
        assert models.structured_extraction == "extract-model"
        assert models.batch_structured_extraction == "batch-model"

    def test_citation_models_optional(self):
        """Test all fields are optional."""
        models = LLMCitationModels()

        assert models.document_citation is None
        assert models.reference_cleaning is None
        assert models.structured_extraction is None
        assert models.batch_structured_extraction is None


class TestLLMCitationConfig:
    """Test LLMCitationConfig model."""

    def test_valid_citation_config(self, sample_citation_config_dict):
        """Test valid citation configuration."""
        config = LLMCitationConfig(**sample_citation_config_dict)

        assert config.model == "test-citation-model"
        assert config.temperature == 0.3
        assert config.models.document_citation == "doc-model"

    def test_citation_config_defaults(self):
        """Test default values."""
        config = LLMCitationConfig()

        assert config.model == "openai/gpt-4o-mini"
        assert config.temperature == 0.9
        assert config.max_tokens == 10000
        assert isinstance(config.models, LLMCitationModels)


class TestLLMTagConsolidatorConfig:
    """Test LLMTagConsolidatorConfig model."""

    def test_tag_consolidator_all_fields(self):
        """Test with all fields."""
        data = {
            "consolidateModel": "consolidate-model",
            "suggestModel": "suggest-model",
            "mapModel": "map-model",
            "temperature": 0.5,
            "maxTokens": 5000
        }
        config = LLMTagConsolidatorConfig(**data)

        assert config.consolidate_model == "consolidate-model"
        assert config.suggest_model == "suggest-model"
        assert config.map_model == "map-model"
        assert config.temperature == 0.5

    def test_tag_consolidator_defaults(self):
        """Test default values."""
        config = LLMTagConsolidatorConfig()

        assert config.consolidate_model == "google/gemini-2.5-flash"
        assert config.suggest_model == "google/gemini-2.5-flash"
        assert config.temperature == 0.9


class TestLLMResearchAgentConfig:
    """Test LLMResearchAgentConfig model."""

    def test_research_agent_all_fields(self):
        """Test with all fields."""
        data = {
            "model": "research-model",
            "temperature": 0.8,
            "maxTokens": 60000,
            "useAutoModelSelection": True,
            "autoModelRequireToolCalling": True,
            "autoModelRequireStructuredOutput": True
        }
        config = LLMResearchAgentConfig(**data)

        assert config.model == "research-model"
        assert config.use_auto_model_selection is True
        assert config.auto_model_require_tool_calling is True

    def test_research_agent_model_settings_property(self):
        """Test model_settings property for backward compatibility."""
        config = LLMResearchAgentConfig()

        assert config.model_settings == config


class TestLLMScrapeFilterConfig:
    """Test LLMScrapeFilterConfig model."""

    def test_scrape_filter_all_fields(self):
        """Test with all fields."""
        data = {
            "model": "scrape-model",
            "temperature": 0.6,
            "maxTokens": 8000
        }
        config = LLMScrapeFilterConfig(**data)

        assert config.model == "scrape-model"
        assert config.temperature == 0.6

    def test_scrape_filter_model_settings_property(self):
        """Test model_settings property."""
        config = LLMScrapeFilterConfig()

        assert config.model_settings == config


class TestLLMQueryBasedRoutingConfig:
    """Test LLMQueryBasedRoutingConfig model."""

    def test_query_routing_all_fields(self):
        """Test with all fields."""
        data = {
            "enabled": True,
            "routingModel": "routing-model",
            "useDynamicPrompt": True
        }
        config = LLMQueryBasedRoutingConfig(**data)

        assert config.enabled is True
        assert config.routing_model == "routing-model"
        assert config.use_dynamic_prompt is True

    def test_query_routing_defaults(self):
        """Test default values."""
        config = LLMQueryBasedRoutingConfig()

        assert config.enabled is False
        assert config.use_dynamic_prompt is False


class TestLLMConfig:
    """Test LLMConfig model."""

    def test_llm_config_nested_defaults(self):
        """Test nested model defaults."""
        config = LLMConfig()

        assert isinstance(config.default, LLMDefaultConfig)
        assert isinstance(config.citation, LLMCitationConfig)
        assert isinstance(config.tag_consolidator, LLMTagConsolidatorConfig)
        assert isinstance(config.research_agent, LLMResearchAgentConfig)
        assert isinstance(config.scrape_filter, LLMScrapeFilterConfig)

    def test_llm_config_convenience_properties(self):
        """Test convenience properties."""
        config = LLMConfig()

        assert config.model == config.default.model
        assert config.temperature == config.default.temperature
        assert config.max_tokens == config.default.max_tokens
        assert config.streaming == config.default.streaming

    def test_llm_config_provider_property(self):
        """Test provider extraction from model string."""
        config = LLMConfig()
        config.default.model = "openai/gpt-4"

        assert config.provider == "openai"

    def test_llm_config_provider_no_slash(self):
        """Test provider defaults to openrouter when no slash."""
        config = LLMConfig()
        config.default.model = "gpt-4"

        assert config.provider == "openrouter"


class TestRAGQAConfig:
    """Test RAGQAConfig model."""

    def test_rag_qa_all_fields(self):
        """Test with all fields."""
        data = {
            "model": "qa-model",
            "temperature": 0.1,
            "maxTokens": 1500,
            "retrievalK": 5
        }
        config = RAGQAConfig(**data)

        assert config.model == "qa-model"
        assert config.retrieval_k == 5


class TestRAGConfig:
    """Test RAGConfig model."""

    def test_rag_config_all_fields(self, sample_rag_config_dict):
        """Test with all fields."""
        config = RAGConfig(**sample_rag_config_dict)

        assert config.embedding_model == "test-embedding-model"
        assert config.embedding_batch_size == 50
        assert config.skip_files_with_images is False
        assert isinstance(config.qa, RAGQAConfig)

    def test_rag_config_defaults(self):
        """Test default values."""
        config = RAGConfig()

        assert config.embedding_model == "openai/text-embedding-3-small"
        assert config.embedding_batch_size == 100
        assert config.skip_files_with_images is True


class TestLettaMemoryConfig:
    """Test LettaMemoryConfig model."""

    def test_letta_memory_all_fields(self):
        """Test with all fields."""
        data = {
            "serverUrl": "http://test:9000",
            "agentName": "test-agent",
            "coreMemoryLimit": 5000,
            "archivalMemoryEnabled": False,
            "consolidationIntervalHours": 48
        }
        config = LettaMemoryConfig(**data)

        assert config.server_url == "http://test:9000"
        assert config.agent_name == "test-agent"
        assert config.core_memory_limit == 5000


class TestThothMemoryConfig:
    """Test ThothMemoryConfig models."""

    def test_thoth_memory_pipeline(self):
        """Test ThothMemoryPipelineConfig."""
        data = {
            "enabled": False,
            "minSalience": 0.2,
            "enableEnrichment": False
        }
        config = ThothMemoryPipelineConfig(**data)

        assert config.enabled is False
        assert config.min_salience == 0.2

    def test_thoth_memory_retrieval(self):
        """Test ThothMemoryRetrievalConfig."""
        data = {
            "enabled": False,
            "relevanceWeight": 0.5,
            "salienceWeight": 0.2
        }
        config = ThothMemoryRetrievalConfig(**data)

        assert config.relevance_weight == 0.5


class TestEpisodicSummarization:
    """Test episodic summarization models."""

    def test_episodic_parameters(self):
        """Test EpisodicSummarizationParameters."""
        data = {
            "analysisWindowHours": 72,
            "minMemoriesThreshold": 20,
            "cleanupAfterSummary": True
        }
        params = EpisodicSummarizationParameters(**data)

        assert params.analysis_window_hours == 72
        assert params.min_memories_threshold == 20
        assert params.cleanup_after_summary is True

    def test_episodic_job(self):
        """Test EpisodicSummarizationJob."""
        data = {
            "enabled": True,
            "intervalHours": 12,
            "timeOfDay": "03:00",
            "daysOfWeek": ["monday", "friday"]
        }
        job = EpisodicSummarizationJob(**data)

        assert job.enabled is True
        assert job.interval_hours == 12
        assert job.time_of_day == "03:00"
        assert "monday" in job.days_of_week


class TestMemorySchedulerConfig:
    """Test MemorySchedulerConfig model."""

    def test_memory_scheduler_empty_jobs(self):
        """Test with no jobs."""
        config = MemorySchedulerConfig()

        assert config.jobs == {}

    def test_memory_scheduler_with_jobs(self):
        """Test with jobs defined."""
        data = {
            "jobs": {
                "job1": {
                    "enabled": True,
                    "intervalHours": 24
                }
            }
        }
        config = MemorySchedulerConfig(**data)

        assert "job1" in config.jobs


class TestMemoryConfig:
    """Test MemoryConfig model."""

    def test_memory_config_nested(self, sample_memory_config_dict):
        """Test nested memory configuration."""
        config = MemoryConfig(**sample_memory_config_dict)

        assert isinstance(config.letta, LettaMemoryConfig)
        assert isinstance(config.thoth, ThothMemoryConfig)
        assert isinstance(config.scheduler, MemorySchedulerConfig)


class TestPathsConfig:
    """Test PathsConfig models."""

    def test_discovery_paths(self):
        """Test DiscoveryPaths model."""
        data = {
            "sources": "test/sources",
            "results": "test/results",
            "chromeConfigs": "test/configs"
        }
        paths = DiscoveryPaths(**data)

        assert paths.sources == "test/sources"
        assert paths.results == "test/results"
        assert paths.chrome_configs == "test/configs"

    def test_paths_config_all_fields(self, sample_paths_config_dict):
        """Test PathsConfig with all fields."""
        config = PathsConfig(**sample_paths_config_dict)

        assert config.workspace == "/test/workspace"
        assert config.pdf == "test/pdf"
        assert isinstance(config.discovery, DiscoveryPaths)


class TestServersConfig:
    """Test servers configuration models."""

    def test_endpoint_config(self):
        """Test EndpointConfig model."""
        data = {
            "host": "127.0.0.1",
            "port": 9000,
            "baseUrl": "http://localhost:9000",
            "autoStart": True
        }
        config = EndpointConfig(**data)

        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.auto_start is True

    def test_mcp_config(self):
        """Test MCPConfig model."""
        data = {
            "host": "mcp-server",
            "port": 8002,
            "autoStart": False,
            "enabled": False
        }
        config = MCPConfig(**data)

        assert config.host == "mcp-server"
        assert config.enabled is False

    def test_monitor_config(self):
        """Test MonitorConfig model."""
        data = {
            "autoStart": False,
            "watchInterval": 30,
            "bulkProcessSize": 20,
            "watchDirectories": ["dir1", "dir2"],
            "recursive": False
        }
        config = MonitorConfig(**data)

        assert config.watch_interval == 30
        assert len(config.watch_directories) == 2

    def test_servers_config_nested(self):
        """Test ServersConfig with nested configs."""
        config = ServersConfig()

        assert isinstance(config.api, EndpointConfig)
        assert isinstance(config.mcp, MCPConfig)
        assert isinstance(config.monitor, MonitorConfig)


class TestDiscoveryConfig:
    """Test discovery configuration models."""

    def test_chrome_extension_config(self):
        """Test ChromeExtensionConfig model."""
        data = {
            "enabled": False,
            "host": "chrome-host",
            "port": 9999
        }
        config = ChromeExtensionConfig(**data)

        assert config.enabled is False
        assert config.port == 9999

    def test_web_search_config(self):
        """Test WebSearchConfig model."""
        data = {
            "providers": ["google", "brave", "bing"]
        }
        config = WebSearchConfig(**data)

        assert len(config.providers) == 3

    def test_discovery_config_full(self):
        """Test DiscoveryConfig with all fields."""
        data = {
            "autoStartScheduler": True,
            "defaultMaxArticles": 100,
            "defaultIntervalMinutes": 120,
            "rateLimitDelay": 2.0
        }
        config = DiscoveryConfig(**data)

        assert config.auto_start_scheduler is True
        assert config.default_max_articles == 100


class TestCitationConfig:
    """Test citation configuration models."""

    def test_citation_apis_config(self):
        """Test CitationAPIsConfig model."""
        data = {
            "useOpencitations": False,
            "useScholarly": False,
            "useSemanticScholar": True,
            "useArxiv": True
        }
        config = CitationAPIsConfig(**data)

        assert config.use_opencitations is False
        assert config.use_semantic_scholar is True

    def test_citation_processing_config(self):
        """Test CitationProcessingConfig model."""
        data = {
            "mode": "batch",
            "batchSize": 10
        }
        config = CitationProcessingConfig(**data)

        assert config.mode == "batch"
        assert config.batch_size == 10

    def test_citation_config_full(self):
        """Test CitationConfig with all fields."""
        data = {
            "linkFormat": "wiki",
            "style": "APA",
            "useResolutionChain": False
        }
        config = CitationConfig(**data)

        assert config.link_format == "wiki"
        assert config.style == "APA"
        assert config.use_resolution_chain is False


class TestPerformanceConfig:
    """Test performance configuration models."""

    def test_workers_config(self):
        """Test WorkersConfig model."""
        data = {
            "tagMapping": "2",
            "articleProcessing": "4",
            "citationEnhancement": "1"
        }
        config = WorkersConfig(**data)

        assert config.tag_mapping == "2"
        assert config.article_processing == "4"

    def test_ocr_config(self):
        """Test OCRConfig model."""
        data = {
            "maxConcurrent": 5,
            "enableCaching": False,
            "cacheTtlHours": 48
        }
        config = OCRConfig(**data)

        assert config.max_concurrent == 5
        assert config.enable_caching is False

    def test_async_config(self):
        """Test AsyncConfig model."""
        data = {
            "enabled": False,
            "timeoutSeconds": 600
        }
        config = AsyncConfig(**data)

        assert config.enabled is False
        assert config.timeout_seconds == 600

    def test_performance_memory_config(self):
        """Test PerformanceMemoryConfig model."""
        data = {
            "optimizationEnabled": False,
            "chunkProcessingEnabled": False,
            "maxDocumentSizeMb": 100
        }
        config = PerformanceMemoryConfig(**data)

        assert config.max_document_size_mb == 100

    def test_semantic_scholar_config(self):
        """Test SemanticScholarConfig model."""
        data = {
            "maxRetries": 5,
            "maxBackoffSeconds": 60.0,
            "backoffMultiplier": 2.0
        }
        config = SemanticScholarConfig(**data)

        assert config.max_retries == 5
        assert config.backoff_multiplier == 2.0


class TestLoggingConfig:
    """Test logging configuration models."""

    def test_logging_rotation_config(self):
        """Test LoggingRotationConfig model."""
        data = {
            "enabled": False,
            "maxBytes": 5000000,
            "backupCount": 5
        }
        config = LoggingRotationConfig(**data)

        assert config.enabled is False
        assert config.max_bytes == 5000000

    def test_logging_file_config(self):
        """Test LoggingFileConfig model."""
        data = {
            "enabled": False,
            "path": "/test/log.log",
            "mode": "w",
            "level": "DEBUG",
            "rotation": "5 MB",
            "retention": "3 days",
            "compression": "gz"
        }
        config = LoggingFileConfig(**data)

        assert config.path == "/test/log.log"
        assert config.level == "DEBUG"

    def test_logging_console_config(self):
        """Test LoggingConsoleConfig model."""
        data = {
            "enabled": False,
            "level": "ERROR"
        }
        config = LoggingConsoleConfig(**data)

        assert config.enabled is False
        assert config.level == "ERROR"

    def test_logging_config_full(self, sample_logging_config_dict):
        """Test LoggingConfig with all nested models."""
        config = LoggingConfig(**sample_logging_config_dict)

        assert config.level == "DEBUG"
        assert isinstance(config.rotation, LoggingRotationConfig)
        assert isinstance(config.file, LoggingFileConfig)
        assert isinstance(config.console, LoggingConsoleConfig)


class TestOtherConfigs:
    """Test remaining configuration models."""

    def test_api_gateway_config(self):
        """Test APIGatewayConfig model."""
        data = {
            "rateLimit": 10.0,
            "cacheExpiry": 7200,
            "defaultTimeout": 30,
            "endpoints": {"test": "value"}
        }
        config = APIGatewayConfig(**data)

        assert config.rate_limit == 10.0
        assert config.cache_expiry == 7200

    def test_security_config(self):
        """Test SecurityConfig model."""
        data = {
            "sessionTimeout": 7200,
            "apiRateLimit": 200
        }
        config = SecurityConfig(**data)

        assert config.session_timeout == 7200

    def test_environment_config(self):
        """Test EnvironmentConfig model."""
        data = {
            "type": "local",
            "pythonUnbuffered": False,
            "development": True
        }
        config = EnvironmentConfig(**data)

        assert config.type == "local"
        assert config.development is True

    def test_postgres_config(self):
        """Test PostgresConfig model."""
        data = {
            "enabled": False,
            "poolMinSize": 10,
            "poolMaxSize": 50,
            "connectionTimeout": 120.0,
            "retryAttempts": 5
        }
        config = PostgresConfig(**data)

        assert config.pool_min_size == 10
        assert config.retry_attempts == 5

    def test_feature_flags_config(self):
        """Test FeatureFlagsConfig model."""
        data = {
            "usePostgresForCitations": True,
            "usePostgresForTags": True,
            "enableCacheLayer": False,
            "cacheTtlSeconds": 600
        }
        config = FeatureFlagsConfig(**data)

        assert config.use_postgres_for_citations is True
        assert config.cache_ttl_seconds == 600


class TestSettings:
    """Test top-level Settings model."""

    def test_settings_minimal(self):
        """Test Settings with minimal data."""
        from tests.fixtures.config_fixtures import get_minimal_settings_json

        data = get_minimal_settings_json()
        settings = Settings(**data)

        assert isinstance(settings.api_keys, APIKeys)
        assert isinstance(settings.llm, LLMConfig)
        assert isinstance(settings.rag, RAGConfig)

    def test_settings_full(self):
        """Test Settings with complete data."""
        from tests.fixtures.config_fixtures import get_full_settings_json

        data = get_full_settings_json()
        settings = Settings(**data)

        assert settings.version == "1.0.0"
        assert settings.api_keys.openai_key == "test-openai-key"
        assert settings.llm.default.model == "google/gemini-2.5-flash"

    def test_settings_extra_fields_allowed(self):
        """Test Settings allows extra fields."""
        data = {
            "apiKeys": {},
            "unknownField": "should-be-allowed"
        }
        settings = Settings(**data)

        # Extra fields are allowed due to extra='allow'
        assert hasattr(settings, "api_keys")

    def test_settings_schema_field(self):
        """Test $schema field with underscore alias."""
        data = {
            "$schema": "./test.schema.json"
        }
        settings = Settings(**data)

        assert settings.schema_ == "./test.schema.json"

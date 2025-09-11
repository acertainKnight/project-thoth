"""
Hybrid configuration loader for Thoth.

This module implements the hybrid configuration system that loads:
- API keys and secrets from .env file
- Non-sensitive settings from thoth.settings.json
"""

import json
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class HybridConfigLoader:
    """
    Loads configuration from both .env (secrets) and JSON (settings) files.

    Priority order:
    1. Environment variables (highest - for secrets/overrides)
    2. .env file (for API keys and secrets)
    3. thoth.settings.json (for non-sensitive settings)
    4. Default values (lowest)
    """

    def __init__(
        self,
        env_file: Path | str = '.env',
        settings_file: Path | str = '.thoth.settings.json',
    ):
        """
        Initialize the hybrid config loader.

        Args:
            env_file: Path to .env file (Docker settings only)
            settings_file: Path to .thoth.settings.json file (all user settings)
        """
        self.env_file = Path(env_file)
        self.settings_file = Path(settings_file)
        self._settings_cache = None

    def load_json_settings(self) -> dict[str, Any]:
        """Load settings from JSON file."""
        if not self.settings_file.exists():
            logger.warning(f'Settings file not found: {self.settings_file}')
            return {}

        try:
            with open(self.settings_file) as f:
                self._settings_cache = json.load(f)
                logger.info(f'Loaded settings from {self.settings_file}')
                return self._settings_cache
        except Exception as e:
            logger.error(f'Failed to load settings file: {e}')
            return {}

    def get_config_data(self, config_class_name: str) -> dict[str, Any]:
        """
        Get configuration data for a specific config class.

        Args:
            config_class_name: Name of the configuration class

        Returns:
            Configuration data dictionary
        """
        # Load JSON settings
        json_settings = self.load_json_settings()

        # Map settings based on config class name
        if config_class_name == 'ThothConfig':
            return self._get_thoth_config_data(json_settings)
        elif config_class_name == 'LLMConfig':
            return self._map_llm_settings(
                json_settings.get('llm', {}).get('default', {})
            )
        elif config_class_name == 'CitationLLMConfig':
            return self._map_citation_llm_settings(
                json_settings.get('llm', {}).get('citation', {})
            )
        elif config_class_name == 'TagConsolidatorLLMConfig':
            return self._map_tag_llm_settings(
                json_settings.get('llm', {}).get('tagConsolidator', {})
            )
        elif config_class_name == 'ResearchAgentLLMConfig':
            return self._map_research_agent_llm_settings(
                json_settings.get('llm', {}).get('researchAgent', {})
            )
        elif config_class_name == 'ScrapeFilterLLMConfig':
            return self._map_scrape_filter_llm_settings(
                json_settings.get('llm', {}).get('scrapeFilter', {})
            )
        elif config_class_name == 'RAGConfig':
            return self._map_rag_settings(json_settings.get('rag', {}))
        elif config_class_name == 'PerformanceConfig':
            return self._map_performance_settings(json_settings.get('performance', {}))
        elif config_class_name == 'LoggingConfig':
            return self._map_logging_settings(json_settings.get('logging', {}))
        elif config_class_name == 'CitationConfig':
            return self._map_citation_settings(json_settings.get('citation', {}))
        elif config_class_name == 'DiscoveryConfig':
            return self._map_discovery_settings(json_settings.get('discovery', {}))
        elif config_class_name == 'EndpointConfig':
            return self._map_endpoint_settings(
                json_settings.get('servers', {}).get('api', {})
            )
        elif config_class_name == 'MCPConfig':
            return self._map_mcp_settings(
                json_settings.get('servers', {}).get('mcp', {})
            )
        elif config_class_name == 'MonitorConfig':
            return self._map_monitor_settings(
                json_settings.get('servers', {}).get('monitor', {})
            )
        elif config_class_name == 'ResearchAgentConfig':
            return self._map_research_agent_settings(
                json_settings.get('servers', {}).get('researchAgent', {})
            )
        elif config_class_name == 'LettaConfig':
            return self._map_letta_settings(
                json_settings.get('memory', {}).get('letta', {})
            )
        elif config_class_name == 'APIGatewayConfig':
            return self._map_api_gateway_settings(
                json_settings.get('servers', {}).get('apiGateway', {})
            )
        elif config_class_name == 'QueryBasedRoutingConfig':
            return self._map_routing_settings(
                json_settings.get('llm', {}).get('routing', {})
            )
        elif config_class_name == 'APIKeys':
            return self._map_api_keys(json_settings.get('apiKeys', {}))
        else:
            return {}

    def _get_thoth_config_data(self, json_settings: dict) -> dict[str, Any]:
        """Get data for main ThothConfig."""
        from .api_keys import APIKeys
        from .llm_models import (
            CitationLLMConfig,
            LLMConfig,
            QueryBasedRoutingConfig,
            ResearchAgentLLMConfig,
            ScrapeFilterLLMConfig,
            TagConsolidatorLLMConfig,
        )
        from .performance import PerformanceConfig
        from .services import (
            APIGatewayConfig,
            CitationConfig,
            DiscoveryConfig,
            LettaConfig,
            LoggingConfig,
            RAGConfig,
        )

        # Create nested configs
        config_data = {}

        # API Keys
        config_data['api_keys'] = APIKeys(
            **self._map_api_keys(json_settings.get('apiKeys', {}))
        )

        # LLM configs
        config_data['llm_config'] = LLMConfig(
            **self._map_llm_settings(json_settings.get('llm', {}).get('default', {}))
        )
        config_data['citation_llm_config'] = CitationLLMConfig(
            **self._map_citation_llm_settings(
                json_settings.get('llm', {}).get('citation', {})
            )
        )
        config_data['tag_consolidator_llm_config'] = TagConsolidatorLLMConfig(
            **self._map_tag_llm_settings(
                json_settings.get('llm', {}).get('tagConsolidator', {})
            )
        )
        config_data['research_agent_llm_config'] = ResearchAgentLLMConfig(
            **self._map_research_agent_llm_settings(
                json_settings.get('llm', {}).get('researchAgent', {})
            )
        )
        config_data['scrape_filter_llm_config'] = ScrapeFilterLLMConfig(
            **self._map_scrape_filter_llm_settings(
                json_settings.get('llm', {}).get('scrapeFilter', {})
            )
        )

        # Service configs
        config_data['rag_config'] = RAGConfig(
            **self._map_rag_settings(json_settings.get('rag', {}))
        )
        config_data['performance_config'] = PerformanceConfig(
            **self._map_performance_settings(json_settings.get('performance', {}))
        )
        config_data['logging_config'] = LoggingConfig(
            **self._map_logging_settings(json_settings.get('logging', {}))
        )
        config_data['citation_config'] = CitationConfig(
            **self._map_citation_settings(json_settings.get('citation', {}))
        )
        config_data['discovery_config'] = DiscoveryConfig(
            **self._map_discovery_settings(json_settings.get('discovery', {}))
        )
        config_data['api_gateway_config'] = APIGatewayConfig(
            **self._map_api_gateway_settings(
                json_settings.get('servers', {}).get('apiGateway', {})
            )
        )
        config_data['letta_config'] = LettaConfig(
            **self._map_letta_settings(json_settings.get('memory', {}).get('letta', {}))
        )
        config_data['query_based_routing_config'] = QueryBasedRoutingConfig(
            **self._map_routing_settings(
                json_settings.get('llm', {}).get('routing', {})
            )
        )

        return config_data

    def _map_llm_settings(self, settings: dict) -> dict:
        """Map JSON LLM settings to config fields."""
        mapped = {
            'model': settings.get('model', 'openai/gpt-4o-mini'),
            'model_settings': {
                'temperature': settings.get('temperature', 0.9),
                'max_tokens': settings.get('maxTokens', 8000),
                'top_p': settings.get('topP', 1.0),
                'streaming': settings.get('streaming', False),
                'use_rate_limiter': settings.get('useRateLimiter', True),
            },
            'max_output_tokens': settings.get('maxOutputTokens', 8000),
            'max_context_length': settings.get('maxContextLength', 8000),
            'chunk_size': settings.get('chunkSize', 4000),
            'chunk_overlap': settings.get('chunkOverlap', 200),
            'refine_threshold_multiplier': settings.get(
                'refineThresholdMultiplier', 1.2
            ),
            'map_reduce_threshold_multiplier': settings.get(
                'mapReduceThresholdMultiplier', 3.0
            ),
        }
        # Remove None values
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_citation_llm_settings(self, settings: dict) -> dict:
        """Map JSON citation LLM settings to config fields."""
        models = settings.get('models', {})
        mapped = {
            'model': settings.get('model', 'openai/gpt-4o-mini'),
            'model_settings': {
                'temperature': settings.get('temperature', 0.3),
                'max_tokens': settings.get('maxTokens', 10000),
            },
            'max_output_tokens': settings.get('maxOutputTokens', 10000),
            'max_context_length': settings.get('maxContextLength', 4000),
            'document_citation_model': models.get('documentCitation'),
            'reference_cleaning_model': models.get('referenceCleaning'),
            'structured_extraction_model': models.get('structuredExtraction'),
            'batch_structured_extraction_model': models.get(
                'batchStructuredExtraction'
            ),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_tag_llm_settings(self, settings: dict) -> dict:
        """Map JSON tag consolidator LLM settings to config fields."""
        mapped = {
            'consolidate_model': settings.get(
                'consolidateModel', 'google/gemini-flash-1.5-8b'
            ),
            'suggest_model': settings.get('suggestModel', 'google/gemini-flash-1.5-8b'),
            'map_model': settings.get('mapModel', 'mistralai/ministral-3b'),
            'model_settings': {
                'temperature': settings.get('temperature', 0.7),
                'max_tokens': settings.get('maxTokens', 10000),
            },
            'max_output_tokens': settings.get('maxOutputTokens', 10000),
            'max_context_length': settings.get('maxContextLength', 8000),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_research_agent_llm_settings(self, settings: dict) -> dict:
        """Map JSON research agent LLM settings to config fields."""
        mapped = {
            'model': settings.get('model', 'anthropic/claude-3.5-sonnet'),
            'model_settings': {
                'temperature': settings.get('temperature', 0.7),
                'max_tokens': settings.get('maxTokens', 8000),
            },
            'max_output_tokens': settings.get('maxOutputTokens', 8000),
            'max_context_length': settings.get('maxContextLength', 100000),
            'use_auto_model_selection': settings.get('useAutoModelSelection', False),
            'auto_model_require_tool_calling': settings.get(
                'autoModelRequireToolCalling', False
            ),
            'auto_model_require_structured_output': settings.get(
                'autoModelRequireStructuredOutput', False
            ),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_scrape_filter_llm_settings(self, settings: dict) -> dict:
        """Map JSON scrape filter LLM settings to config fields."""
        mapped = {
            'model': settings.get('model', 'mistralai/ministral-8b'),
            'model_settings': {
                'temperature': settings.get('temperature', 0.5),
                'max_tokens': settings.get('maxTokens', 10000),
            },
            'max_output_tokens': settings.get('maxOutputTokens', 10000),
            'max_context_length': settings.get('maxContextLength', 16000),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_rag_settings(self, settings: dict) -> dict:
        """Map JSON RAG settings to config fields."""
        qa_settings = settings.get('qa', {})
        mapped = {
            'embedding_model': settings.get('embeddingModel', 'all-MiniLM-L6-v2'),
            'embedding_batch_size': settings.get('embeddingBatchSize', 100),
            'skip_files_with_images': settings.get('skipFilesWithImages', True),
            'vector_db_path': Path(settings.get('vectorDbPath', 'knowledge/vector_db')),
            'collection_name': settings.get('collectionName', 'thoth_knowledge'),
            'chunk_size': settings.get('chunkSize', 500),
            'chunk_overlap': settings.get('chunkOverlap', 50),
            'chunk_encoding': settings.get('chunkEncoding', 'cl100k_base'),
            'qa_model': qa_settings.get('model', 'openai/gpt-4o-mini'),
            'qa_temperature': qa_settings.get('temperature', 0.2),
            'qa_max_tokens': qa_settings.get('maxTokens', 2000),
            'retrieval_k': settings.get('retrievalK', 4),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_performance_settings(self, settings: dict) -> dict:
        """Map JSON performance settings to config fields."""
        ocr = settings.get('ocr', {})
        async_settings = settings.get('async', {})
        memory = settings.get('memory', {})

        mapped = {
            'auto_scale_workers': settings.get('autoScaleWorkers', True),
            'tag_mapping_workers': settings.get('tagMappingWorkers'),
            'article_processing_workers': settings.get('articleProcessingWorkers'),
            'content_analysis_workers': settings.get('contentAnalysisWorkers'),
            'citation_enhancement_workers': settings.get('citationEnhancementWorkers'),
            'citation_pdf_workers': settings.get('citationPdfWorkers'),
            'citation_extraction_workers': settings.get('citationExtractionWorkers'),
            'ocr_max_concurrent': ocr.get('maxConcurrent', 3),
            'ocr_enable_caching': ocr.get('enableCaching', True),
            'ocr_cache_ttl_hours': ocr.get('cacheTtlHours', 24),
            'async_enabled': async_settings.get('enabled', True),
            'async_timeout_seconds': async_settings.get('timeoutSeconds', 300),
            'memory_optimization_enabled': memory.get('optimizationEnabled', True),
            'chunk_processing_enabled': memory.get('chunkProcessingEnabled', True),
            'max_document_size_mb': memory.get('maxDocumentSizeMb', 50),
            'semanticscholar_max_retries': settings.get('semanticscholarMaxRetries', 3),
            'semanticscholar_max_backoff_seconds': settings.get(
                'semanticscholarMaxBackoffSeconds', 30.0
            ),
            'semanticscholar_backoff_multiplier': settings.get(
                'semanticscholarBackoffMultiplier', 1.5
            ),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_logging_settings(self, settings: dict) -> dict:
        """Map JSON logging settings to config fields."""
        file_settings = settings.get('file', {})
        mapped = {
            'level': settings.get('level', 'INFO'),
            'logformat': settings.get(
                'format', '{time} | {level} | {file}:{line} | {function} | {message}'
            ),
            'dateformat': settings.get('dateFormat', 'YYYY-MM-DD HH:mm:ss'),
            'filename': file_settings.get('path', 'logs/thoth.log'),
            'filemode': file_settings.get('mode', 'a'),
            'file_level': file_settings.get('level', 'INFO'),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_citation_settings(self, settings: dict) -> dict:
        """Map JSON citation settings to config fields."""
        mapped = {
            'link_format': settings.get('linkFormat', 'uri'),
            'style': settings.get('style', 'IEEE'),
            'use_opencitations': settings.get('useOpencitations', True),
            'use_scholarly': settings.get('useScholarly', False),
            'use_semanticscholar': settings.get('useSemanticscholar', True),
            'use_arxiv': settings.get('useArxiv', True),
            'processing_mode': settings.get('processingMode', 'single'),
            'citation_batch_size': settings.get('batchSize', 5),
            'pdf_locator_enabled': settings.get('pdfLocatorEnabled', True),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_discovery_settings(self, settings: dict) -> dict:
        """Map JSON discovery settings to config fields."""
        chrome_ext = settings.get('chromeExtension', {})
        mapped = {
            'auto_start_scheduler': settings.get('autoStartScheduler', False),
            'default_max_articles': settings.get('defaultMaxArticles', 50),
            'default_interval_minutes': settings.get('defaultIntervalMinutes', 60),
            'rate_limit_delay': settings.get('rateLimitDelay', 1.0),
            'chrome_extension_enabled': chrome_ext.get('enabled', True),
            'chrome_extension_host': chrome_ext.get('host', 'localhost'),
            'chrome_extension_port': chrome_ext.get('port', 8765),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_endpoint_settings(self, settings: dict) -> dict:
        """Map JSON endpoint settings to config fields."""
        mapped = {
            'host': settings.get('host', '127.0.0.1'),
            'port': settings.get('port', 8000),
            'base_url': settings.get('baseUrl', '/'),
            'auto_start': settings.get('autoStart', False),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_mcp_settings(self, settings: dict) -> dict:
        """Map JSON MCP settings to config fields."""
        mapped = {
            'host': settings.get('host', 'localhost'),
            'port': settings.get('port', 8001),
            'enabled': settings.get('enabled', True),
            'auto_start': settings.get('autoStart', True),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_monitor_settings(self, settings: dict) -> dict:
        """Map JSON monitor settings to config fields."""
        mapped = {
            'auto_start': settings.get('autoStart', False),
            'watch_interval': settings.get('watchInterval', 1),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_research_agent_settings(self, settings: dict) -> dict:
        """Map JSON research agent settings to config fields."""
        mapped = {
            'auto_start': settings.get('autoStart', False),
            'default_queries': settings.get('defaultQueries', True),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_letta_settings(self, settings: dict) -> dict:
        """Map JSON Letta settings to config fields."""
        mapped = {
            'server_url': settings.get('serverUrl', 'http://localhost:8283'),
            'api_key': settings.get('apiKey'),
            'agent_name': settings.get('agentName', 'thoth_research_agent'),
            'core_memory_limit': settings.get('coreMemoryLimit', 10000),
            'archival_memory_enabled': settings.get('archivalMemoryEnabled', True),
            'recall_memory_enabled': settings.get('recallMemoryEnabled', True),
            'enable_smart_truncation': settings.get('enableSmartTruncation', True),
            'consolidation_interval_hours': settings.get(
                'consolidationIntervalHours', 24
            ),
            'fallback_enabled': settings.get('fallbackEnabled', True),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_api_gateway_settings(self, settings: dict) -> dict:
        """Map JSON API gateway settings to config fields."""
        mapped = {
            'rate_limit': settings.get('rateLimit', 5.0),
            'cache_expiry': settings.get('cacheExpiry', 3600),
            'default_timeout': settings.get('defaultTimeout', 15),
            'endpoints': settings.get('endpoints', {}),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_routing_settings(self, settings: dict) -> dict:
        """Map JSON routing settings to config fields."""
        mapped = {
            'enabled': settings.get('enabled', False),
            'routing_model': settings.get('routingModel', 'openai/gpt-4o-mini'),
            'use_dynamic_prompt': settings.get('useDynamicPrompt', False),
        }
        return {k: v for k, v in mapped.items() if v is not None}

    def _map_api_keys(self, settings: dict) -> dict:
        """Map JSON API keys to config fields."""
        mapped = {
            'mistral_key': settings.get('mistralKey', ''),
            'openrouter_key': settings.get('openrouterKey', ''),
            'openai_key': settings.get('openaiKey', ''),
            'anthropic_key': settings.get('anthropicKey', ''),
            'opencitations_key': settings.get('opencitationsKey', ''),
            'google_api_key': settings.get('googleApiKey', ''),
            'google_search_engine_id': settings.get('googleSearchEngineId', ''),
            'semanticscholar_api_key': settings.get('semanticScholarKey', ''),
            'web_search_key': settings.get('webSearchKey', ''),
            'web_search_providers': settings.get('webSearchProviders', []),
            'letta_api_key': settings.get('lettaApiKey', ''),
        }
        return {k: v for k, v in mapped.items() if v is not None}


def create_hybrid_settings(
    config_class: type[BaseSettings | BaseModel], **kwargs
) -> BaseSettings | BaseModel:
    """
    Create a Pydantic settings instance with hybrid loading.

    This function:
    1. Loads settings from thoth.settings.json
    2. Creates the config instance with those settings
    3. For BaseSettings subclasses, env vars will override JSON settings

    Args:
        config_class: The Pydantic settings class to instantiate
        **kwargs: Additional keyword arguments to pass to the config class

    Returns:
        Configured instance of the settings class
    """
    loader = HybridConfigLoader()

    # Get configuration data for this class
    config_data = loader.get_config_data(config_class.__name__)

    # Merge with any provided kwargs (kwargs take precedence)
    merged_settings = {**config_data, **kwargs}

    # Create the config instance
    return config_class(**merged_settings)

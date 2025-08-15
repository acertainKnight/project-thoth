"""
Configuration utilities for Thoth - Compatibility wrapper.

DEPRECATED: This module provides backward compatibility for the old configuration system.
Please migrate to use `from thoth.config import get_config, ThothConfig` instead.
"""

import warnings
from typing import TYPE_CHECKING

# Issue deprecation warning
warnings.warn(
    "thoth.utilities.config is deprecated. Please use thoth.config instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import everything from the new config module
from thoth.config import (
    ThothConfig,
    get_config,
    reset_config,
    APIConfig,
    LLMConfig,
    DirectoryConfig, 
    ServerConfig,
    PerformanceConfig,
    FeatureFlags,
)

# Import all the old classes to maintain compatibility
# These will be gradually phased out
try:
    from .config_old import (
        APIKeys,
        ModelConfig,
        BaseLLMConfig,
        LLMConfig as OldLLMConfig,
        QueryBasedRoutingConfig,
        CitationLLMConfig,
        PerformanceConfig as OldPerformanceConfig,
        TagConsolidatorLLMConfig,
        CitationConfig,
        BaseServerConfig,
        EndpointConfig,
        MonitorConfig,
        ResearchAgentLLMConfig,
        ScrapeFilterLLMConfig,
        MCPConfig,
        DiscoveryConfig,
        ResearchAgentConfig,
        RAGConfig,
        LoggingConfig,
        APIGatewayConfig,
        ThothConfig as OldThothConfig,
        load_config,
        setup_logging,
    )
except ImportError:
    # If old config is removed, provide stub implementations
    pass

# Override get_config to return the new config but maintain compatibility
_original_get_config = get_config

def get_config() -> ThothConfig:
    """Get the global configuration instance with compatibility layer."""
    config = _original_get_config()
    
    # Add any compatibility attributes that might be missing
    # These provide backward compatibility for old code
    if not hasattr(config, 'citation_llm_config'):
        config.citation_llm_config = type('CitationLLMConfig', (), {
            'model': config.llm.citation_model or config.llm.model,
            'temperature': config.llm.temperature,
            'max_output_tokens': 10000,  # Citation-specific default
            'max_context_length': 4000,  # Citation-specific default
            'document_citation_model': config.llm.document_citation_model,
            'reference_cleaning_model': config.llm.reference_cleaning_model,
            'structured_extraction_model': config.llm.structured_extraction_model,
            'batch_structured_extraction_model': config.llm.batch_structured_extraction_model,
        })()
    
    if not hasattr(config, 'tag_consolidator_llm_config'):
        config.tag_consolidator_llm_config = type('TagConsolidatorLLMConfig', (), {
            'model': config.llm.tag_consolidator_model or config.llm.model,
            'temperature': config.llm.temperature,
            'max_output_tokens': config.llm.max_output_tokens,
        })()
    
    if not hasattr(config, 'citation_config'):
        config.citation_config = type('CitationConfig', (), {
            'include_all_citations': config.api.citation_include_all,
            'min_citation_length': config.api.citation_min_length,
            'max_citations_per_paper': config.api.citation_max_per_paper,
            'opencitations_email': config.api.opencitations_email,
        })()
    
    if not hasattr(config, 'logging_config'):
        config.logging_config = type('LoggingConfig', (), {
            'log_level': config.log_level,
            'log_format': config.log_format,
            'log_to_file': True,
            'log_dir': config.directories.logs_dir,
        })()
    
    if not hasattr(config, 'discovery_config'):
        config.discovery_config = type('DiscoveryConfig', (), {
            'max_results_per_source': 20,
            'query_delay_seconds': 2.0,
            'max_retries': 3,
            'cache_results': True,
            'auto_start_scheduler': config.features.discovery_auto_start_scheduler,
            'default_max_articles': config.features.discovery_default_max_articles,
            'default_interval_minutes': config.features.discovery_default_interval_minutes,
            'rate_limit_delay': config.features.discovery_rate_limit_delay,
            'chrome_extension_enabled': config.server.chrome_extension_enabled,
            'chrome_extension_host': config.server.chrome_extension_host,
            'chrome_extension_port': config.server.chrome_extension_port,
        })()
    
    if not hasattr(config, 'monitor_config'):
        config.monitor_config = type('MonitorConfig', (), {
            'watch_interval': config.features.monitor_watch_interval,
            'process_interval': 10,
            'enabled': config.features.auto_process_pdfs,
            'auto_start': config.features.monitor_auto_start,
        })()
    
    if not hasattr(config, 'endpoint_config'):
        config.endpoint_config = type('EndpointConfig', (), {
            'host': config.server.api_host,
            'port': config.server.api_port,
            'cors_origins': config.server.cors_origins,
        })()
    
    if not hasattr(config, 'rag_config'):
        config.rag_config = type('RAGConfig', (), {
            'enabled': config.features.enable_rag,
            'chunk_size': config.features.rag_chunk_size,
            'chunk_overlap': config.features.rag_chunk_overlap,
            'use_local_embeddings': config.features.use_local_embeddings,
            'embedding_model': config.features.rag_embedding_model,
            'embedding_batch_size': config.features.rag_embedding_batch_size,
            'skip_files_with_images': config.features.rag_skip_files_with_images,
            'vector_db_path': config.directories.vector_db_path,
            'collection_name': config.features.rag_collection_name,
            'qa_model': config.llm.qa_model,
            'qa_temperature': config.llm.qa_temperature,
        })()
    
    if not hasattr(config, 'research_agent_config'):
        config.research_agent_config = type('ResearchAgentConfig', (), {
            'enable_memory': config.features.enable_memory,
            'max_iterations': config.llm.agent_max_iterations,
            'agent_model': config.llm.agent_model,
            'auto_start': config.features.auto_start_agent,
            'default_queries': config.features.research_agent_default_queries,
        })()
    
    if not hasattr(config, 'research_agent_llm_config'):
        config.research_agent_llm_config = type('ResearchAgentLLMConfig', (), {
            'model': config.llm.agent_model,
            'temperature': config.llm.agent_temperature,
            'max_output_tokens': config.llm.max_output_tokens,
            'max_context_length': config.llm.max_context_length,
        })()
    
    if not hasattr(config, 'scrape_filter_llm_config'):
        config.scrape_filter_llm_config = type('ScrapeFilterLLMConfig', (), {
            'model': config.llm.scrape_filter_model or config.llm.model,
            'temperature': config.llm.temperature,
            'max_output_tokens': 10000,
            'max_context_length': config.llm.scrape_filter_max_context,
        })()
    
    if not hasattr(config, 'mcp_config'):
        config.mcp_config = type('MCPConfig', (), {
            'host': config.server.mcp_host,
            'port': config.server.mcp_port,
            'enabled': config.server.mcp_enabled,
            'auto_start': config.server.mcp_auto_start,
        })()
    
    if not hasattr(config, 'query_based_routing_config'):
        config.query_based_routing_config = type('QueryBasedRoutingConfig', (), {
            'enabled': config.llm.routing_enabled,
            'routing_model': config.llm.routing_model,
            'use_dynamic_prompt': True,
        })()
    
    if not hasattr(config, 'performance_config'):
        config.performance_config = type('PerformanceConfig', (), {
            'max_workers': config.performance.max_workers,
            'batch_size': config.performance.batch_size,
            'max_concurrent_api_calls': config.performance.max_concurrent_api_calls,
            'api_retry_count': config.performance.api_retry_count,
            'api_timeout_seconds': config.performance.api_timeout_seconds,
            'max_single_call_size': config.performance.max_single_call_size,
            'batch_processing_threshold': config.performance.batch_processing_threshold,
            'memory_limit_percentage': config.performance.memory_limit_percentage,
            'enable_memory_profiling': config.performance.enable_memory_profiling,
        })()
    
    return config

# Re-export commonly used items
__all__ = [
    'ThothConfig', 
    'get_config', 
    'reset_config',
    'APIKeys',
    'LLMConfig',
    'load_config',
    'setup_logging',
]
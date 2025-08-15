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
            'model': config.llm.model,
            'temperature': config.llm.temperature,
            'max_output_tokens': config.llm.max_output_tokens,
        })()
    
    if not hasattr(config, 'tag_consolidator_llm_config'):
        config.tag_consolidator_llm_config = type('TagConsolidatorLLMConfig', (), {
            'model': config.llm.model,
            'temperature': config.llm.temperature,
            'max_output_tokens': config.llm.max_output_tokens,
        })()
    
    if not hasattr(config, 'citation_config'):
        config.citation_config = type('CitationConfig', (), {
            'include_all_citations': True,
            'min_citation_length': 10,
            'max_citations_per_paper': 100,
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
        })()
    
    if not hasattr(config, 'monitor_config'):
        config.monitor_config = type('MonitorConfig', (), {
            'watch_interval': 5,
            'process_interval': 10,
            'enabled': config.features.auto_process_pdfs,
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
            'chunk_size': config.llm.chunk_size,
            'chunk_overlap': config.llm.chunk_overlap,
            'use_local_embeddings': config.features.use_local_embeddings,
        })()
    
    if not hasattr(config, 'research_agent_config'):
        config.research_agent_config = type('ResearchAgentConfig', (), {
            'enable_memory': config.features.enable_memory,
            'max_iterations': config.llm.agent_max_iterations,
            'agent_model': config.llm.agent_model,
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
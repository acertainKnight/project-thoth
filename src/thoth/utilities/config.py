"""
Configuration utilities for Thoth.

This module maintains backwards compatibility by re-exporting all
configuration components from the new modular structure.
"""

# Re-export everything from the modular config package for backwards compatibility
# Using explicit imports instead of star import for security and clarity

# Specifically import the public API to ensure it's available
from .config import (
    APIGatewayConfig,
    APIKeys,
    BaseLLMConfig,
    BaseServerConfig,
    CitationConfig,
    CitationLLMConfig,
    CoreConfig,
    DiscoveryConfig,
    EndpointConfig,
    FeatureConfig,
    LLMConfig,
    LoggingConfig,
    MCPConfig,
    ModelConfig,
    MonitorConfig,
    PerformanceConfig,
    QueryBasedRoutingConfig,
    RAGConfig,
    ResearchAgentConfig,
    ResearchAgentLLMConfig,
    ScrapeFilterLLMConfig,
    TagConsolidatorLLMConfig,
    ThothConfig,
    get_config,
    load_config,
    setup_logging,
)

__all__ = [
    'APIGatewayConfig',
    'APIKeys',
    'BaseLLMConfig',
    'BaseServerConfig',
    'CitationConfig',
    'CitationLLMConfig',
    'CoreConfig',
    'DiscoveryConfig',
    'EndpointConfig',
    'FeatureConfig',
    'LLMConfig',
    'LoggingConfig',
    'MCPConfig',
    'ModelConfig',
    'MonitorConfig',
    'PerformanceConfig',
    'QueryBasedRoutingConfig',
    'RAGConfig',
    'ResearchAgentConfig',
    'ResearchAgentLLMConfig',
    'ScrapeFilterLLMConfig',
    'TagConsolidatorLLMConfig',
    'ThothConfig',
    'get_config',
    'load_config',
    'setup_logging',
]

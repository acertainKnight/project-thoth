"""
Configuration utilities for Thoth - modular structure.

This module provides a clean import interface for all configuration
components while maintaining backwards compatibility.
"""

# Base classes and utilities
# Import the simplified config classes that are used by main_config
from thoth.config.simplified import CoreConfig, FeatureConfig

# API Keys
from .api_keys import APIKeys
from .base import BaseLLMConfig, BaseServerConfig, ModelConfig, setup_logging

# LLM Model configurations
from .llm_models import (
    CitationLLMConfig,
    LLMConfig,
    QueryBasedRoutingConfig,
    ResearchAgentLLMConfig,
    ScrapeFilterLLMConfig,
    TagConsolidatorLLMConfig,
)

# Main configuration class and functions
from .main_config import ThothConfig, get_config, load_config

# Performance configuration
from .performance import PerformanceConfig

# Service configurations
from .services import (
    APIGatewayConfig,
    CitationConfig,
    DiscoveryConfig,
    EndpointConfig,
    LoggingConfig,
    MCPConfig,
    MonitorConfig,
    RAGConfig,
    ResearchAgentConfig,
)

# Maintain full backwards compatibility - export everything exactly as before
__all__ = [
    # Base classes
    'BaseLLMConfig',
    'BaseServerConfig',
    'ModelConfig',
    # API Keys
    'APIKeys',
    # LLM configurations
    'CitationLLMConfig',
    'LLMConfig',
    'QueryBasedRoutingConfig',
    'ResearchAgentLLMConfig',
    'ScrapeFilterLLMConfig',
    'TagConsolidatorLLMConfig',
    # Performance
    'PerformanceConfig',
    # Service configurations
    'APIGatewayConfig',
    'CitationConfig',
    'DiscoveryConfig',
    'EndpointConfig',
    'LoggingConfig',
    'MCPConfig',
    'MonitorConfig',
    'RAGConfig',
    'ResearchAgentConfig',
    # Main configuration
    'ThothConfig',
    # Simplified config classes (used by ThothConfig)
    'CoreConfig',
    'FeatureConfig',
    # Utility functions
    'get_config',
    'load_config',
    'setup_logging',
]

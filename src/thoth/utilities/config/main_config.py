"""
Main configuration class and integration methods.

This module contains the primary ThothConfig class that integrates all
configuration components and provides methods for Obsidian integration,
validation, and environment synchronization.
"""

import os
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from thoth.config.simplified import CoreConfig, FeatureConfig

from .api_keys import APIKeys
from .base import setup_logging
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
    EndpointConfig,
    LettaConfig,
    LoggingConfig,
    MCPConfig,
    MonitorConfig,
    RAGConfig,
    ResearchAgentConfig,
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
    letta_config: LettaConfig = Field(
        default_factory=LettaConfig, description='Letta memory system configuration'
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

    # Convenience properties for Letta memory system
    @property
    def letta_server_url(self) -> str:  # pragma: no cover
        return self.letta_config.server_url

    @property
    def letta_api_key(self) -> str | None:  # pragma: no cover
        return self.letta_config.api_key

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
    """Load the configuration using hybrid loader."""
    from .hybrid_loader import create_hybrid_settings

    config = create_hybrid_settings(ThothConfig)
    config.setup_logging()
    return config


def get_config() -> ThothConfig:
    """Get the configuration."""
    return load_config()

"""
Simplified configuration system for Thoth.

This module provides a clean, consolidated configuration structure that replaces
the previous 21-class system with a more manageable hierarchy.
"""

import os
import sys
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIConfig(BaseSettings):
    """API keys and external service configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix='API_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )
    
    # Required API Keys
    opencitations_key: str = Field(default='default', description='OpenCitations API key')
    
    # Optional API Keys for various LLM providers
    mistral_key: str | None = Field(None, description='Mistral API key for OCR')
    openrouter_key: str | None = Field(None, description='OpenRouter API key')
    openai_key: str | None = Field(None, description='OpenAI API key')
    anthropic_key: str | None = Field(None, description='Anthropic API key')
    
    # Search API Keys
    google_api_key: str | None = Field(None, description='Google API key')
    google_search_engine_id: str | None = Field(None, description='Google CSE ID')
    semanticscholar_api_key: str | None = Field(None, description='Semantic Scholar API key')
    web_search_key: str | None = Field(None, description='Serper.dev API key')
    
    # Web search configuration
    web_search_providers: list[str] = Field(
        default_factory=lambda: ['serper'],
        description='Enabled web search providers'
    )
    
    # Citation-specific settings
    opencitations_email: str | None = Field(None, description='Email for OpenCitations API')
    citation_include_all: bool = Field(default=True, description='Include all citations')
    citation_min_length: int = Field(default=10, description='Minimum citation length')
    citation_max_per_paper: int = Field(default=100, description='Max citations per paper')


class LLMConfig(BaseSettings):
    """Language model configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix='LLM_',
        env_file='.env',
        case_sensitive=False,
    )
    
    # Primary LLM settings
    model: str = Field(default='gpt-4o-mini', description='Primary LLM model')
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=12000, ge=1)
    max_context_length: int = Field(default=100000, ge=1)
    
    # Processing settings
    chunk_size: int = Field(default=10000, ge=100)
    chunk_overlap: int = Field(default=500, ge=0)
    
    # Analysis model (can be different from primary)
    analysis_model: str | None = Field(None, description='Model for document analysis')
    analysis_temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    
    # Agent model settings
    agent_model: str = Field(default='claude-3-5-sonnet-20241022')
    agent_temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    agent_max_iterations: int = Field(default=5, ge=1, le=20)
    
    # Citation-specific models
    citation_model: str | None = Field(None, description='Model for citation processing')
    document_citation_model: str | None = Field(None, description='Model for extracting document citations')
    reference_cleaning_model: str | None = Field(None, description='Model for cleaning references')
    structured_extraction_model: str | None = Field(None, description='Model for structured citation extraction')
    batch_structured_extraction_model: str | None = Field(None, description='Model for batch citation extraction')
    
    # Tag consolidation model
    tag_consolidator_model: str | None = Field(None, description='Model for tag consolidation')
    
    # Scrape filter model
    scrape_filter_model: str | None = Field(None, description='Model for web scrape filtering')
    scrape_filter_max_context: int = Field(default=50000, description='Max context for scrape filtering')
    
    # Query routing
    routing_enabled: bool = Field(default=False, description='Enable query-based model routing')
    routing_model: str = Field(default='openai/gpt-4o-mini', description='Model for routing queries')
    
    # RAG QA model
    qa_model: str = Field(default='openai/gpt-4o-mini', description='Model for question answering')
    qa_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    
    @property
    def model_settings(self) -> dict[str, Any]:
        """Get model-specific settings."""
        return {
            'temperature': self.temperature,
            'max_tokens': self.max_output_tokens,
        }


class DirectoryConfig(BaseSettings):
    """Directory paths configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix='DIR_',
        env_file='.env',
        case_sensitive=False,
    )
    
    # Base directories
    base_dir: Path = Field(default_factory=lambda: Path.home() / 'Thoth')
    workspace_dir: Path = Field(default_factory=lambda: Path.cwd())
    
    # Data directories
    data_dir: Path | None = None
    knowledge_base_dir: Path | None = None
    logs_dir: Path | None = None
    
    # Content directories
    pdf_dir: Path | None = None
    markdown_dir: Path | None = None
    notes_dir: Path | None = None
    obsidian_dir: Path | None = None
    
    # System directories
    prompts_dir: Path | None = None
    queries_dir: Path | None = None
    agent_storage_dir: Path | None = None
    graph_storage_path: Path | None = None
    
    # RAG directories
    vector_db_path: Path | None = None
    
    # Output directories
    output_dir: Path | None = None
    
    def __init__(self, **data):
        super().__init__(**data)
        self._setup_directories()
    
    def _setup_directories(self):
        """Set up directory paths with defaults."""
        self.data_dir = self.data_dir or self.base_dir / 'data'
        self.knowledge_base_dir = self.knowledge_base_dir or self.data_dir / 'knowledge_base'
        self.logs_dir = self.logs_dir or self.base_dir / 'logs'
        
        self.pdf_dir = self.pdf_dir or self.data_dir / 'pdfs'
        self.markdown_dir = self.markdown_dir or self.data_dir / 'markdown'
        self.notes_dir = self.notes_dir or self.data_dir / 'notes'
        self.obsidian_dir = self.obsidian_dir or self.notes_dir
        
        self.prompts_dir = self.prompts_dir or self.workspace_dir / 'templates' / 'prompts'
        self.queries_dir = self.queries_dir or self.data_dir / 'queries'
        self.agent_storage_dir = self.agent_storage_dir or self.data_dir / 'agent'
        self.graph_storage_path = self.graph_storage_path or self.knowledge_base_dir / 'citation_graph.pkl'
        self.vector_db_path = self.vector_db_path or self.knowledge_base_dir / 'vector_db'
        self.output_dir = self.output_dir or self.data_dir
        
        # Ensure critical directories exist
        for dir_path in [self.data_dir, self.knowledge_base_dir, self.logs_dir, 
                        self.pdf_dir, self.markdown_dir, self.notes_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


class ServerConfig(BaseSettings):
    """Server and endpoint configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix='SERVER_',
        env_file='.env',
        case_sensitive=False,
    )
    
    # API Server
    api_host: str = Field(default='127.0.0.1')
    api_port: int = Field(default=8000, ge=1, le=65535)
    
    # MCP Server
    mcp_host: str = Field(default='127.0.0.1')
    mcp_port: int = Field(default=3000, ge=1, le=65535)
    mcp_enabled: bool = Field(default=True, description='Enable MCP server')
    mcp_auto_start: bool = Field(default=True, description='Auto-start MCP server')
    
    # CORS settings
    cors_origins: list[str] = Field(
        default_factory=lambda: ['http://localhost:*', 'app://obsidian.md']
    )
    
    # Performance settings
    max_concurrent_requests: int = Field(default=10, ge=1)
    request_timeout: int = Field(default=300, ge=1)
    
    # Discovery server settings
    discovery_host: str = Field(default='localhost', description='Discovery server host')
    discovery_port: int = Field(default=8002, description='Discovery server port')
    
    # Chrome extension settings
    chrome_extension_enabled: bool = Field(default=True, description='Enable Chrome extension')
    chrome_extension_host: str = Field(default='localhost', description='Chrome extension host')
    chrome_extension_port: int = Field(default=8765, description='Chrome extension port')
    
    @property
    def api_base_url(self) -> str:
        """Get the API base URL."""
        return f'http://{self.api_host}:{self.api_port}'
    
    @property
    def mcp_base_url(self) -> str:
        """Get the MCP base URL."""
        return f'http://{self.mcp_host}:{self.mcp_port}'


class PerformanceConfig(BaseSettings):
    """Performance and optimization settings."""
    
    model_config = SettingsConfigDict(
        env_prefix='PERF_',
        env_file='.env',
        case_sensitive=False,
    )
    
    # Processing settings
    max_workers: int | None = Field(None, description='Max worker threads (None = auto)')
    batch_size: int = Field(default=10, ge=1)
    cache_enabled: bool = Field(default=True)
    cache_ttl: int = Field(default=3600, ge=0)
    
    # Memory settings
    max_memory_mb: int = Field(default=4096, ge=512)
    gc_threshold: float = Field(default=0.8, ge=0.1, le=1.0)
    
    # Async settings
    async_timeout: int = Field(default=30, ge=1)
    max_retries: int = Field(default=3, ge=0)
    
    # Concurrency settings (from old PerformanceConfig)
    max_concurrent_api_calls: int = Field(default=10, description='Max concurrent API calls')
    api_retry_count: int = Field(default=3, description='API retry count')
    api_timeout_seconds: int = Field(default=60, description='API timeout in seconds')
    
    # Processing thresholds
    max_single_call_size: int = Field(default=4000, description='Max size for single LLM call')
    batch_processing_threshold: int = Field(default=10000, description='Threshold for batch processing')
    
    # Memory management
    memory_limit_percentage: float = Field(default=80.0, description='Memory limit as % of system RAM')
    enable_memory_profiling: bool = Field(default=False, description='Enable memory profiling')


class FeatureFlags(BaseSettings):
    """Feature toggles and experimental settings."""
    
    model_config = SettingsConfigDict(
        env_prefix='FEATURE_',
        env_file='.env',
        case_sensitive=False,
    )
    
    # Core features
    auto_start_agent: bool = Field(default=False)
    auto_process_pdfs: bool = Field(default=True)
    enable_web_search: bool = Field(default=True)
    enable_discovery: bool = Field(default=True)
    
    # UI features
    show_status_bar: bool = Field(default=True)
    show_notifications: bool = Field(default=True)
    
    # Advanced features
    enable_memory: bool = Field(default=True)
    enable_rag: bool = Field(default=True)
    use_local_embeddings: bool = Field(default=False)
    
    # Experimental
    enable_experimental: bool = Field(default=False)
    debug_mode: bool = Field(default=False)
    
    # Monitor settings
    monitor_auto_start: bool = Field(default=False, description='Auto-start PDF monitor')
    monitor_watch_interval: int = Field(default=10, description='File watch interval in seconds')
    
    # Discovery settings  
    discovery_auto_start_scheduler: bool = Field(default=False, description='Auto-start discovery scheduler')
    discovery_default_max_articles: int = Field(default=50, description='Default max articles per run')
    discovery_default_interval_minutes: int = Field(default=60, description='Default discovery interval')
    discovery_rate_limit_delay: float = Field(default=1.0, description='Delay between requests')
    
    # Research agent settings
    research_agent_default_queries: bool = Field(default=True, description='Create default queries')
    
    # RAG settings
    rag_skip_files_with_images: bool = Field(default=True, description='Skip files with images')
    rag_embedding_model: str = Field(default='all-MiniLM-L6-v2', description='Embedding model')
    rag_embedding_batch_size: int = Field(default=100, description='Embedding batch size')
    rag_chunk_size: int = Field(default=500, description='RAG chunk size in tokens')
    rag_chunk_overlap: int = Field(default=50, description='RAG chunk overlap in tokens')
    rag_collection_name: str = Field(default='thoth_knowledge', description='Vector DB collection name')


class ThothConfig(BaseSettings):
    """Main configuration class for Thoth."""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )
    
    # Sub-configurations
    api: APIConfig = Field(default_factory=APIConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    directories: DirectoryConfig = Field(default_factory=DirectoryConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    
    # Logging
    log_level: str = Field(default='INFO')
    log_format: str = Field(
        default='<green>{time:YYYY-MM-DD HH:mm:ss}</green> | '
               '<level>{level: <8}</level> | '
               '<cyan>{name}</cyan>:<cyan>{line}</cyan> - '
               '<level>{message}</level>'
    )
    
    def __init__(self, **data):
        super().__init__(**data)
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure logging based on settings."""
        logger.remove()
        logger.add(
            sys.stderr,
            format=self.log_format,
            level=self.log_level,
            colorize=True
        )
        
        # Add file logging
        if self.directories.logs_dir:
            log_file = self.directories.logs_dir / 'thoth.log'
            logger.add(
                log_file,
                format=self.log_format,
                level=self.log_level,
                rotation='10 MB',
                retention='7 days'
            )
    
    @property
    def api_keys(self) -> APIConfig:
        """Backward compatibility alias."""
        return self.api
    
    @property
    def llm_config(self) -> LLMConfig:
        """Backward compatibility alias."""
        return self.llm
    
    @property
    def output_dir(self) -> Path:
        """Backward compatibility alias."""
        return self.directories.data_dir
    
    @property
    def pdf_dir(self) -> Path:
        """Backward compatibility alias."""
        return self.directories.pdf_dir
    
    @property
    def markdown_dir(self) -> Path:
        """Backward compatibility alias."""
        return self.directories.markdown_dir
    
    @property
    def notes_dir(self) -> Path:
        """Backward compatibility alias."""
        return self.directories.notes_dir
    
    @property
    def knowledge_base_dir(self) -> Path:
        """Backward compatibility alias."""
        return self.directories.knowledge_base_dir
    
    @property
    def graph_storage_path(self) -> Path:
        """Backward compatibility alias."""
        return self.directories.graph_storage_path
    
    @property
    def prompts_dir(self) -> Path:
        """Backward compatibility alias."""
        return self.directories.prompts_dir
    
    @property
    def api_port(self) -> int:
        """Backward compatibility alias."""
        return self.server.api_port
    
    @property
    def mcp_port(self) -> int:
        """Backward compatibility alias."""
        return self.server.mcp_port
    
    @property
    def api_base_url(self) -> str:
        """Backward compatibility alias."""
        return self.server.api_base_url
    
    def to_obsidian_settings(self) -> dict[str, Any]:
        """Convert config to Obsidian plugin settings format."""
        return {
            # API Keys
            'mistralKey': self.api.mistral_key or '',
            'openrouterKey': self.api.openrouter_key or '',
            'opencitationsKey': self.api.opencitations_key,
            'googleApiKey': self.api.google_api_key or '',
            'googleSearchEngineId': self.api.google_search_engine_id or '',
            'semanticScholarKey': self.api.semanticscholar_api_key or '',
            'webSearchKey': self.api.web_search_key or '',
            'webSearchProviders': ','.join(self.api.web_search_providers),
            
            # Directories
            'workspaceDirectory': str(self.directories.workspace_dir),
            'obsidianDirectory': str(self.directories.obsidian_dir),
            'dataDirectory': str(self.directories.data_dir),
            'knowledgeDirectory': str(self.directories.knowledge_base_dir),
            'logsDirectory': str(self.directories.logs_dir),
            'queriesDirectory': str(self.directories.queries_dir),
            'agentStorageDirectory': str(self.directories.agent_storage_dir),
            'pdfDirectory': str(self.directories.pdf_dir),
            'promptsDirectory': str(self.directories.prompts_dir),
            
            # Connection Settings
            'endpointHost': self.server.api_host,
            'endpointPort': self.server.api_port,
            'corsOrigins': self.server.cors_origins,
            
            # LLM Configuration
            'primaryLlmModel': self.llm.model,
            'analysisLlmModel': self.llm.analysis_model or self.llm.model,
            'researchAgentModel': self.llm.agent_model,
            'llmTemperature': self.llm.temperature,
            'analysisLlmTemperature': self.llm.analysis_temperature,
            'llmMaxOutputTokens': self.llm.max_output_tokens,
            'analysisLlmMaxOutputTokens': self.llm.max_output_tokens,
            
            # Agent Settings
            'researchAgentAutoStart': self.features.auto_start_agent,
            'researchAgentMemoryEnabled': self.features.enable_memory,
            'agentMaxToolCalls': 10,  # Fixed for now
            'agentTimeoutSeconds': self.performance.async_timeout,
            
            # Features
            'autoStartAgent': self.features.auto_start_agent,
            'showStatusBar': self.features.show_status_bar,
            'debugMode': self.features.debug_mode,
        }
    
    @classmethod
    def from_obsidian_settings(cls, settings: dict[str, Any]) -> 'ThothConfig':
        """Create config from Obsidian plugin settings."""
        return cls(
            api=APIConfig(
                mistral_key=settings.get('mistralKey'),
                openrouter_key=settings.get('openrouterKey'),
                opencitations_key=settings.get('opencitationsKey', 'default'),
                google_api_key=settings.get('googleApiKey'),
                google_search_engine_id=settings.get('googleSearchEngineId'),
                semanticscholar_api_key=settings.get('semanticScholarKey'),
                web_search_key=settings.get('webSearchKey'),
                web_search_providers=settings.get('webSearchProviders', '').split(',') if settings.get('webSearchProviders') else ['serper'],
            ),
            llm=LLMConfig(
                model=settings.get('primaryLlmModel', 'gpt-4o-mini'),
                temperature=settings.get('llmTemperature', 0.3),
                max_output_tokens=settings.get('llmMaxOutputTokens', 12000),
                analysis_model=settings.get('analysisLlmModel'),
                analysis_temperature=settings.get('analysisLlmTemperature', 0.4),
                agent_model=settings.get('researchAgentModel', 'claude-3-5-sonnet-20241022'),
            ),
            directories=DirectoryConfig(
                workspace_dir=Path(settings.get('workspaceDirectory', '.')),
                obsidian_dir=Path(settings.get('obsidianDirectory', '.')),
                data_dir=Path(settings.get('dataDirectory', '.')),
                knowledge_base_dir=Path(settings.get('knowledgeDirectory', '.')),
                logs_dir=Path(settings.get('logsDirectory', '.')),
                queries_dir=Path(settings.get('queriesDirectory', '.')),
                agent_storage_dir=Path(settings.get('agentStorageDirectory', '.')),
                pdf_dir=Path(settings.get('pdfDirectory', '.')),
                prompts_dir=Path(settings.get('promptsDirectory', '.')),
            ),
            server=ServerConfig(
                api_host=settings.get('endpointHost', '127.0.0.1'),
                api_port=settings.get('endpointPort', 8000),
                cors_origins=settings.get('corsOrigins', ['http://localhost:*', 'app://obsidian.md']),
            ),
            features=FeatureFlags(
                auto_start_agent=settings.get('researchAgentAutoStart', False),
                show_status_bar=settings.get('showStatusBar', True),
                enable_memory=settings.get('researchAgentMemoryEnabled', True),
                debug_mode=settings.get('debugMode', False),
            ),
        )


# Global config instance
_config: ThothConfig | None = None


def get_config() -> ThothConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = ThothConfig()
    return _config


def reset_config() -> None:
    """Reset the global configuration instance."""
    global _config
    _config = None



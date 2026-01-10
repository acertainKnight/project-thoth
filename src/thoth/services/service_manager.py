"""Central service manager for Thoth components."""

from typing import Any, TYPE_CHECKING

from loguru import logger

from thoth.discovery.discovery_manager import DiscoveryManager
from thoth.knowledge.graph import CitationGraph
from thoth.services.api_gateway import ExternalAPIGateway
from thoth.services.article_service import ArticleService
from thoth.services.base import BaseService
from thoth.services.citation_service import CitationService
from thoth.services.discovery_orchestrator import DiscoveryOrchestrator
from thoth.services.discovery_service import DiscoveryService
from thoth.services.llm_service import LLMService

# Optional: Letta filesystem service (requires letta extras with pgvector)
try:
    from thoth.services.letta_filesystem_service import LettaFilesystemService
    from thoth.services.letta_filesystem_watcher import LettaFilesystemWatcherService

    LETTA_FILESYSTEM_AVAILABLE = True
except ImportError:
    LettaFilesystemService = None  # type: ignore
    LettaFilesystemWatcherService = None  # type: ignore
    LETTA_FILESYSTEM_AVAILABLE = False

# Optional: Processing service (requires pdf extras with mistralai)
try:
    from thoth.services.processing_service import ProcessingService

    PROCESSING_AVAILABLE = True
except ImportError:
    ProcessingService = None  # type: ignore
    PROCESSING_AVAILABLE = False

# Optional: RAG service (requires embeddings extras)
try:
    from thoth.services.rag_service import RAGService

    RAG_AVAILABLE = True
except ImportError:
    RAGService = None  # type: ignore
    RAG_AVAILABLE = False

from thoth.services.note_service import NoteService  # noqa: I001
from thoth.services.pdf_locator_service import PdfLocatorService
from thoth.services.query_service import QueryService
from thoth.services.research_question_service import ResearchQuestionService
from thoth.services.skill_service import SkillService
from thoth.services.tag_service import TagService
from thoth.services.web_search_service import WebSearchService
from thoth.services.postgres_service import PostgresService
from thoth.config import config as global_config, Config

# Optional optimized services
try:
    from thoth.services.async_processing_service import AsyncProcessingService
    from thoth.services.cache_service import CacheService

    OPTIMIZED_SERVICES_AVAILABLE = True
except ImportError:
    OPTIMIZED_SERVICES_AVAILABLE = False


class ServiceUnavailableError(Exception):
    """
    Raised when an optional service is not available.
    
    This error indicates that the service requires additional dependencies
    that are not currently installed.
    """
    pass


class ServiceManager:
    """
    Central manager for all Thoth services.

    This class provides a single point of access for all services,
    handling initialization and dependency injection.
    
    Services are accessed by short names (e.g., service_manager.llm)
    NOT by long names (e.g., service_manager.llm_service).
    """

    # Type hints for IDE autocomplete support (no runtime overhead)
    if TYPE_CHECKING:
        # Core services (always available)
        llm: LLMService
        article: ArticleService
        note: NoteService
        query: QueryService
        discovery: DiscoveryService
        discovery_manager: DiscoveryManager
        discovery_orchestrator: DiscoveryOrchestrator
        web_search: WebSearchService
        pdf_locator: PdfLocatorService
        api_gateway: ExternalAPIGateway
        citation: CitationService
        postgres: PostgresService
        research_question: ResearchQuestionService
        tag: TagService
        skill: SkillService
        
        # Optional services (may be None if extras not installed)
        letta_filesystem: LettaFilesystemService | None  # Requires 'memory' extras
        letta_filesystem_watcher: LettaFilesystemWatcherService | None  # Requires 'memory' extras
        processing: ProcessingService | None  # Requires 'pdf' extras
        rag: RAGService | None  # Requires 'embeddings' extras
        cache: CacheService | None  # Requires optimization extras
        async_processing: AsyncProcessingService | None  # Requires optimization extras

    def __init__(self, config: Config | None = None):
        """
        Initialize the ServiceManager.

        Args:
            config: Optional configuration object
        """
        self.config = config or global_config
        self._services = {}
        self._initialized = False
        self.logger = logger.bind(service='ServiceManager')

    def initialize(self) -> None:
        """Initialize all services with proper dependencies."""
        if self._initialized:
            return

        # Initialize core services first
        self._services['llm'] = LLMService(config=self.config)

        # Initialize Processing service (optional - requires pdf extras)
        if PROCESSING_AVAILABLE:
            self._services['processing'] = ProcessingService(
                config=self.config, llm_service=self._services['llm']
            )
            self.logger.debug('Processing service initialized')
        else:
            self._services['processing'] = None
            self.logger.debug('Processing service not available (requires pdf extras)')

        self._services['article'] = ArticleService(
            config=self.config, llm_service=self._services['llm']
        )
        self._services['note'] = NoteService(config=self.config)

        # Initialize services that depend on paths
        self._services['query'] = QueryService(
            config=self.config,
            storage_dir=self.config.queries_dir,
        )

        self._services['discovery'] = DiscoveryService(
            config=self.config,
            sources_dir=self.config.discovery_sources_dir,
            results_dir=self.config.discovery_results_dir,
        )

        # Initialize RAG service (optional - requires embeddings extras)
        if RAG_AVAILABLE:
            self._services['rag'] = RAGService(config=self.config)
            self.logger.debug('RAG service initialized')
        else:
            self._services['rag'] = None
            self.logger.debug('RAG service not available (requires embeddings extras)')

        self._services['web_search'] = WebSearchService(config=self.config)

        self._services['pdf_locator'] = PdfLocatorService(config=self.config)

        self._services['api_gateway'] = ExternalAPIGateway(config=self.config)

        # Note: Letta agents run natively on port 8283 via REST API
        # No LettaService wrapper needed - use direct REST API calls

        # Initialize services that need dependencies
        self._services['citation'] = CitationService(config=self.config)

        # Initialize postgres service for database operations
        self._services['postgres'] = PostgresService(config=self.config)

        # Initialize research question service with postgres
        self._services['research_question'] = ResearchQuestionService(
            config=self.config, postgres_service=self._services['postgres']
        )

        # Initialize discovery manager (needed for orchestrator)
        from thoth.repositories.available_source_repository import (
            AvailableSourceRepository,
        )

        source_repo = AvailableSourceRepository(self._services['postgres'])
        self._services['discovery_manager'] = DiscoveryManager(
            sources_config_dir=self.config.discovery_sources_dir,
            source_repo=source_repo,
        )

        # Initialize discovery orchestrator with dependencies
        self._services['discovery_orchestrator'] = DiscoveryOrchestrator(
            config=self.config,
            llm_service=self._services['llm'],
            discovery_manager=self._services['discovery_manager'],
            postgres_service=self._services['postgres'],
        )

        # Tag service requires OpenRouter API key - initialize if available
        try:
            self._services['tag'] = TagService(
                config=self.config,
                llm_service=self._services['llm'],
                citation_tracker=None,  # Will be set by pipeline
            )
        except Exception as e:
            # Check if this is an expected API key error during early initialization
            error_msg = str(e)
            if 'API key not found' in error_msg or 'OPENROUTER' in error_msg:
                self.logger.debug(
                    f'TagService initialization deferred (API keys loading): {e}'
                )
            else:
                self.logger.warning(f'TagService initialization skipped: {e}')
            self._services['tag'] = None

        # Initialize skill service for agent skills management
        self._services['skill'] = SkillService(config=self.config)
        self._services['skill'].initialize()

        # Initialize Letta filesystem service (optional - requires memory extras)
        if LETTA_FILESYSTEM_AVAILABLE:
            self._services['letta_filesystem'] = LettaFilesystemService(config=self.config)
            self.logger.debug('Letta filesystem service initialized')
            
            # Initialize Letta filesystem watcher (auto-sync on file changes)
            self._services['letta_filesystem_watcher'] = LettaFilesystemWatcherService(
                config=self.config,
                letta_filesystem_service=self._services['letta_filesystem']
            )
            # Start watcher if autoSync is enabled in config
            self._services['letta_filesystem_watcher'].start()
        else:
            self._services['letta_filesystem'] = None
            self._services['letta_filesystem_watcher'] = None
            self.logger.debug('Letta filesystem service not available (requires memory extras with pgvector)')

        # Initialize optimized services if available
        if OPTIMIZED_SERVICES_AVAILABLE:
            self._services['cache'] = CacheService(config=self.config)
            self._services['cache'].initialize()

            self._services['async_processing'] = AsyncProcessingService(
                config=self.config, llm_service=self._services['llm']
            )

        self._initialized = True

    def __getattr__(self, name: str):
        """Dynamically access services by name."""
        self._ensure_initialized()

        # Try to get the service
        if name in self._services:
            service = self._services[name]
            
            # If service is None (optional service not installed), provide helpful error
            if service is None:
                # Map service names to their extras groups
                extras_map = {
                    'processing': 'pdf',
                    'rag': 'embeddings',
                    'cache': 'optimization',
                    'async_processing': 'optimization',
                }
                extras_name = extras_map.get(name, 'unknown')
                raise ServiceUnavailableError(
                    f"Service '{name}' is not available. "
                    f"Install required dependencies: uv sync --extra {extras_name}"
                )
            
            return service

        # If not found, provide helpful error message
        # Check if user tried the old _service suffix pattern
        if name.endswith('_service'):
            short_name = name[:-8]  # Remove '_service' suffix
            if short_name in self._services:
                raise AttributeError(
                    f"ServiceManager has no attribute '{name}'. "
                    f"Use short name 'service_manager.{short_name}' instead of 'service_manager.{name}'"
                )
        
        # General error with available services
        available = ', '.join(sorted(self._services.keys()))
        raise AttributeError(
            f"ServiceManager has no service '{name}'. "
            f"Available services: {available}"
        )

    def get_service(self, name: str) -> BaseService:
        """
        Get a service by name.

        Args:
            name: Service name

        Returns:
            BaseService: The requested service

        Raises:
            KeyError: If service not found
        """
        self._ensure_initialized()
        if name not in self._services:
            raise KeyError(f"Service '{name}' not found")
        return self._services[name]

    def set_citation_tracker(self, citation_tracker: CitationGraph) -> None:
        """
        Set the citation tracker for services that need it.

        Args:
            citation_tracker: CitationGraph instance
        """
        self._ensure_initialized()
        self.logger.info(
            f'Setting citation tracker with {len(citation_tracker.graph.nodes) if citation_tracker else 0} nodes'
        )
        if self._services['tag'] is not None:
            self._services['tag']._citation_tracker = citation_tracker
            self.logger.info(
                f'Citation tracker set in TagService: {len(citation_tracker.graph.nodes) if citation_tracker else 0} nodes'
            )
        else:
            self.logger.warning('TagService is None, cannot set citation tracker')
        self._services['citation']._citation_tracker = citation_tracker

    def set_filter_function(self, filter_func: Any) -> None:
        """
        Set the filter function for the discovery service.

        Args:
            filter_func: Filter function for evaluating articles
        """
        self._ensure_initialized()
        self._services['discovery'].filter_func = filter_func

    def require_service(self, service_name: str, extras_name: str) -> BaseService:
        """
        Get a required service or raise a helpful error if not available.
        
        This method is especially useful for optional services that require
        additional dependencies to be installed.
        
        Args:
            service_name: Name of the service (e.g., 'rag', 'processing')
            extras_name: Name of the extras group to install (e.g., 'embeddings', 'pdf')
            
        Returns:
            BaseService: The requested service
            
        Raises:
            ServiceUnavailableError: If the service is not available
            
        Example:
            >>> rag = service_manager.require_service('rag', 'embeddings')
            >>> results = rag.search(query)
        """
        self._ensure_initialized()
        
        service = self._services.get(service_name)
        
        if service is None:
            raise ServiceUnavailableError(
                f"Service '{service_name}' is not available. "
                f"Install required dependencies: uv sync --extra {extras_name}"
            )
        
        return service

    def get_all_services(self) -> dict[str, BaseService]:
        """Get all initialized services."""
        self._ensure_initialized()
        return self._services.copy()

    def _ensure_initialized(self) -> None:
        """Ensure services are initialized."""
        if not self._initialized:
            self.initialize()

    def shutdown(self) -> None:
        """Shutdown all services and clean up resources."""
        for service in self._services.values():
            # Clean up any resources if services have cleanup methods
            if hasattr(service, 'cleanup'):
                service.cleanup()

        self._services.clear()
        self._initialized = False

"""Central service manager for Thoth components."""

from typing import Any

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

# Optional: Letta service (requires memory extras)
try:
    from thoth.services.letta_service import LettaService
    LETTA_AVAILABLE = True
except ImportError:
    LettaService = None  # type: ignore
    LETTA_AVAILABLE = False

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

from thoth.services.note_service import NoteService
from thoth.services.pdf_locator_service import PdfLocatorService
from thoth.services.query_service import QueryService
from thoth.services.research_question_service import ResearchQuestionService
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


class ServiceManager:
    """
    Central manager for all Thoth services.

    This class provides a single point of access for all services,
    handling initialization and dependency injection.
    """

    def __init__(self, config: Config | None = None):
        """
        Initialize the ServiceManager.

        Args:
            config: Optional configuration object
        """
        self.config = config or global_config
        self._services = {}
        self._initialized = False

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
            logger.debug("Processing service initialized")
        else:
            self._services['processing'] = None
            logger.debug("Processing service not available (requires pdf extras)")

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
            logger.debug("RAG service initialized")
        else:
            self._services['rag'] = None
            logger.debug("RAG service not available (requires embeddings extras)")

        self._services['web_search'] = WebSearchService(config=self.config)

        self._services['pdf_locator'] = PdfLocatorService(config=self.config)

        self._services['api_gateway'] = ExternalAPIGateway(config=self.config)

        # Initialize Letta service for agent management (optional)
        if LETTA_AVAILABLE:
            self._services['letta'] = LettaService(config=self.config)
            logger.debug("Letta service initialized")
        else:
            self._services['letta'] = None
            logger.debug("Letta service not available (requires memory extras)")

        # Initialize services that need dependencies
        self._services['citation'] = CitationService(config=self.config)

        # Initialize postgres service for database operations
        self._services['postgres'] = PostgresService(config=self.config)

        # Initialize research question service with postgres
        self._services['research_question'] = ResearchQuestionService(
            config=self.config,
            postgres_service=self._services['postgres']
        )

        # Initialize discovery manager (needed for orchestrator)
        from thoth.repositories.available_source_repository import AvailableSourceRepository
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
                logger.debug(f'TagService initialization deferred (API keys loading): {e}')
            else:
                logger.warning(f'TagService initialization skipped: {e}')
            self._services['tag'] = None

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

        # Handle special cases for optional services
        if name in ('cache', 'async_processing'):
            if name not in self._services:
                raise RuntimeError(
                    f'{name.replace("_", " ").title()} service not available - optimized services not installed'
                )

        # Try to get the service
        if name in self._services:
            return self._services[name]

        # If not found, raise AttributeError
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
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
        if self._services['tag'] is not None:
            self._services['tag']._citation_tracker = citation_tracker
        self._services['citation']._citation_tracker = citation_tracker

    def set_filter_function(self, filter_func: Any) -> None:
        """
        Set the filter function for the discovery service.

        Args:
            filter_func: Filter function for evaluating articles
        """
        self._ensure_initialized()
        self._services['discovery'].filter_func = filter_func

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

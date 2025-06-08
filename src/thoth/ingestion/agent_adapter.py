"""
Agent adapter for bridging legacy components to the service layer.

This module provides an adapter that allows the ResearchAssistantAgent
and other legacy components to use the new service layer.
"""

from pathlib import Path
from typing import Any

from thoth.services.service_manager import ServiceManager
from thoth.utilities.schemas import (
    AnalysisResponse,
    DiscoverySource,
    QueryEvaluationResponse,
    ResearchQuery,
    ScheduleConfig,
    SearchResult,
)


class AgentAdapter:
    """
    Adapter for ResearchAssistantAgent to use the service layer.

    This class provides backward compatibility by mapping the old
    agent interface to the new service-based architecture.
    """

    def __init__(self, service_manager: ServiceManager):
        """
        Initialize the AgentAdapter.

        Args:
            service_manager: ServiceManager instance
        """
        self.services = service_manager

    # Query Management Methods

    def list_queries(self) -> list[ResearchQuery]:
        """List all research queries."""
        return self.services.query.get_all_queries()

    def create_query(self, query_data: ResearchQuery) -> bool:
        """Create a new research query."""
        return self.services.query.create_query(query_data)

    def get_query(self, name: str) -> ResearchQuery | None:
        """Get a research query by name."""
        return self.services.query.get_query(name)

    def delete_query(self, name: str) -> bool:
        """Delete a research query."""
        return self.services.query.delete_query(name)

    def update_query(self, name: str, updates: dict[str, Any]) -> bool:
        """Update a research query."""
        return self.services.query.update_query(name, updates)

    def evaluate_article(
        self, article: AnalysisResponse, query_name: str
    ) -> QueryEvaluationResponse | None:
        """Evaluate an article against a query."""
        query = self.services.query.get_query(query_name)
        if not query:
            return None

        return self.services.article.evaluate_article(article, query)

    # Discovery Management Methods

    def list_discovery_sources(self) -> list[DiscoverySource]:
        """List all discovery sources."""
        return self.services.discovery.list_sources()

    def create_discovery_source(self, source_config: dict[str, Any]) -> bool:
        """Create a new discovery source."""
        # Convert config dict to DiscoverySource
        if 'schedule_config' in source_config:
            source_config['schedule_config'] = ScheduleConfig(
                **source_config['schedule_config']
            )

        source = DiscoverySource(**source_config)
        return self.services.discovery.create_source(source)

    def delete_discovery_source(self, source_name: str) -> bool:
        """Delete a discovery source."""
        return self.services.discovery.delete_source(source_name)

    def run_discovery(
        self, source_name: str | None = None, max_articles: int | None = None
    ) -> dict[str, Any]:
        """Run discovery for sources."""
        try:
            # Create filter function using the service manager
            from thoth.ingestion.filter import Filter

            filter_instance = Filter(self.services)
            filter_func = filter_instance.process_article

            result = self.services.discovery.run_discovery(
                source_name, max_articles, filter_func
            )
            return {
                'success': True,
                'articles_found': result.articles_found,
                'articles_filtered': result.articles_filtered,
                'articles_downloaded': result.articles_downloaded,
                'execution_time': result.execution_time_seconds,
                'errors': result.errors,
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'articles_found': 0,
                'articles_filtered': 0,
                'articles_downloaded': 0,
            }

    # RAG Methods

    def search_knowledge(
        self, query: str, k: int = 4, filter: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Search the knowledge base."""
        return self.services.rag.search(query, k, filter)

    def ask_knowledge(self, question: str, k: int = 4) -> dict[str, Any]:
        """Ask a question about the knowledge base."""
        return self.services.rag.ask_question(question, k)

    def web_search(
        self, query: str, num_results: int = 5, provider: str | None = None
    ) -> list[SearchResult]:
        """Perform a general web search."""
        return self.services.web_search.search(query, num_results, provider=provider)

    def index_knowledge_file(self, file_path: Path) -> bool:
        """Index a file to the knowledge base."""
        return self.services.rag.index_file(file_path)

    def get_rag_stats(self) -> dict[str, Any]:
        """Get RAG system statistics."""
        return self.services.rag.get_stats()

    def get_llm(self):
        """
        Get the LLM instance for agent reasoning.

        Returns:
            The configured LLM instance
        """
        return self.services.llm.get_llm()


class FilterAdapter:
    """
    Adapter for Filter to use the service layer.

    This class provides backward compatibility by mapping the old
    Filter interface to the new service-based architecture.
    """

    def __init__(self, service_manager: ServiceManager):
        """
        Initialize the FilterAdapter.

        Args:
            service_manager: ServiceManager instance
        """
        self.services = service_manager
        self.agent = AgentAdapter(service_manager)

    def process_article(
        self,
        metadata,
        query_names: list[str] | None = None,
        download_pdf: bool = True,
    ) -> dict[str, Any]:
        """Process an article through the filter."""
        try:
            # Get all queries if none specified
            if query_names is None:
                query_names = self.services.query.list_queries()

            # Get query objects
            queries = []
            for name in query_names:
                query = self.services.query.get_query(name)
                if query:
                    queries.append(query)

            # Evaluate for download
            evaluation = self.services.article.evaluate_for_download(metadata, queries)

            # Build result
            result = {
                'decision': 'download' if evaluation.should_download else 'skip',
                'evaluation': evaluation,
                'all_evaluations': [
                    {
                        'query_name': q.name,
                        'score': evaluation.relevance_score,
                        'reasoning': evaluation.reasoning,
                    }
                    for q in queries
                ],
                'pdf_downloaded': False,
                'pdf_path': None,
                'error_message': None,
            }

            # Download PDF if requested and approved
            if download_pdf and evaluation.should_download:
                # This would use a PDF download service
                # For now, just return the decision
                pass

            return result

        except Exception as e:
            return {
                'decision': 'skip',
                'evaluation': None,
                'error_message': str(e),
            }

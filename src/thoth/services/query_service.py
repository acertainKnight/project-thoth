"""
Query service for managing research queries.

This module consolidates all query-related operations that were previously
scattered across Filter, agent tools, and other components.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from thoth.services.base import BaseService, ServiceError
from thoth.utilities import OpenRouterClient
from thoth.utilities.schemas import QueryEvaluationResponse, ResearchQuery


class QueryService(BaseService):
    """
    Service for managing research queries.

    This service consolidates all query-related operations including:
    - Creating, reading, updating, and deleting queries
    - Evaluating articles against queries
    - Managing query storage
    """

    def __init__(self, config=None, storage_dir: Path | None = None):
        """
        Initialize the QueryService.

        Args:
            config: Optional configuration object
            storage_dir: Directory for storing queries
        """
        super().__init__(config)
        self.storage_dir = Path(storage_dir or self.config.queries_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._llm = None  # Lazy initialization
        self._queries: dict[str, ResearchQuery] = {}

        # Set up prompts directory and Jinja environment
        self.prompts_dir = Path(self.config.prompts_dir)

        # Initialize Jinja environments for different providers
        self.jinja_envs = {}
        for provider in ['openai', 'google']:
            provider_dir = self.prompts_dir / provider
            if provider_dir.exists():
                self.jinja_envs[provider] = Environment(
                    loader=FileSystemLoader(provider_dir),
                    trim_blocks=True,
                    lstrip_blocks=True,
                )

    @property
    def llm(self) -> OpenRouterClient:
        """Get or create the LLM client for query evaluation."""
        if self._llm is None:
            self._llm = OpenRouterClient(
                api_key=self.config.api_keys.openrouter_key,
                model=self.config.research_agent_llm_config.model,
                **self.config.research_agent_llm_config.model_settings.model_dump(),
            )
        return self._llm

    def create_query(self, query: ResearchQuery) -> bool:
        """
        Create or update a research query.

        Args:
            query: The research query to create or update

        Returns:
            bool: True if successful, False otherwise

        Raises:
            ServiceError: If creation fails
        """
        try:
            self.validate_input(query=query)

            # Set timestamps
            now = datetime.now().isoformat()
            if not query.created_at:
                query.created_at = now
            query.updated_at = now

            # Save to file
            query_file = self.storage_dir / f'{query.name}.json'
            with open(query_file, 'w') as f:
                json.dump(query.model_dump(), f, indent=2)

            self.log_operation('query_created', name=query.name)
            return True

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f"creating query '{query.name}'")
            ) from e

    def get_query(self, name: str) -> ResearchQuery | None:
        """
        Get a research query by name.

        Args:
            name: Name of the query

        Returns:
            ResearchQuery: The query if found, None otherwise
        """
        try:
            query_file = self.storage_dir / f'{name}.json'
            if not query_file.exists():
                self.logger.debug(f"Query '{name}' not found")
                return None

            with open(query_file) as f:
                data = json.load(f)
                return ResearchQuery(**data)

        except Exception as e:
            self.logger.error(self.handle_error(e, f"loading query '{name}'"))
            return None

    def list_queries(self) -> list[str]:
        """
        List all available query names.

        Returns:
            list[str]: List of query names
        """
        try:
            queries = []
            for query_file in self.storage_dir.glob('*.json'):
                queries.append(query_file.stem)
            return sorted(queries)

        except Exception as e:
            self.logger.error(self.handle_error(e, 'listing queries'))
            return []

    def delete_query(self, name: str) -> bool:
        """
        Delete a research query.

        Args:
            name: Name of the query to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            query_file = self.storage_dir / f'{name}.json'
            if query_file.exists():
                query_file.unlink()
                self.log_operation('query_deleted', name=name)
                return True
            return False

        except Exception as e:
            self.logger.error(self.handle_error(e, f"deleting query '{name}'"))
            return False

    def evaluate_article(
        self,
        article_title: str,
        article_abstract: str,
        query_name: str,
        article_content: str | None = None,
    ) -> QueryEvaluationResponse | None:
        """
        Evaluate an article against a specific query.

        Args:
            article_title: Title of the article
            article_abstract: Abstract of the article
            query_name: Name of the query to evaluate against
            article_content: Optional full content

        Returns:
            QueryEvaluationResponse: Evaluation result or None if evaluation fails
        """
        try:
            # Get the query
            query = self.get_query(query_name)
            if not query:
                self.logger.error(f"Query '{query_name}' not found")
                return None

            # Prepare evaluation prompt
            prompt = self._build_evaluation_prompt(
                article_title, article_abstract, query, article_content
            )

            # Get structured response
            structured_llm = self.llm.with_structured_output(
                QueryEvaluationResponse,
                include_raw=False,
                method='json_schema',
            )

            # Evaluate
            response = structured_llm.invoke(prompt)

            self.log_operation(
                'article_evaluated',
                query=query_name,
                score=response.relevance_score,
                recommendation=response.recommendation,
            )

            return response

        except Exception as e:
            self.logger.error(
                self.handle_error(e, f"evaluating article against query '{query_name}'")
            )
            return None

    def _build_evaluation_prompt(
        self,
        title: str,
        abstract: str,
        query: ResearchQuery,
        content: str | None = None,
    ) -> str:
        """Build the evaluation prompt for the LLM."""
        # Get model provider from config
        model = self.config.research_agent_llm_config.model
        if isinstance(model, list):
            model = model[0]  # Use first model in list
        provider = model.split('/')[0] if '/' in model else 'openai'

        # Fall back to google templates if provider-specific templates don't exist
        if provider not in self.jinja_envs:
            provider = (
                'google'
                if 'google' in self.jinja_envs
                else next(iter(self.jinja_envs.keys()))
            )

        # Load and render template
        template = self.jinja_envs[provider].get_template('evaluate_article.j2')
        prompt = template.render(
            query=query,
            title=title,
            abstract=abstract,
            content=content,
        )

        return prompt

    def get_all_queries(self) -> list[ResearchQuery]:
        """
        Get all research queries.

        Returns:
            list[ResearchQuery]: List of all queries
        """
        queries = []
        for name in self.list_queries():
            query = self.get_query(name)
            if query:
                queries.append(query)
        return queries

    def update_query(self, name: str, updates: dict[str, Any]) -> bool:
        """
        Update an existing query with new values.

        Args:
            name: Name of the query to update
            updates: Dictionary of fields to update

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            query = self.get_query(name)
            if not query:
                return False

            # Update fields
            for field, value in updates.items():
                if hasattr(query, field):
                    setattr(query, field, value)

            # Save updated query
            return self.create_query(query)

        except Exception as e:
            self.logger.error(self.handle_error(e, f"updating query '{name}'"))
            return False

    def initialize(self) -> None:
        """Initialize the query service."""
        self.logger.info('Query service initialized')

    def health_check(self) -> dict[str, str]:
        """Basic health status for the QueryService."""
        return super().health_check()

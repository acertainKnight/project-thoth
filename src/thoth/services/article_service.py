"""
Article service for managing article evaluation and scoring.

This module consolidates all article-related operations that were previously
scattered across Filter, agent tools, and other components.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from thoth.services.base import BaseService, ServiceError
from thoth.services.llm_service import LLMService
from thoth.utilities.schemas import (
    AnalysisResponse,
    PreDownloadEvaluationResponse,
    QueryEvaluationResponse,
    ResearchQuery,
    ScrapedArticleMetadata,
)


class ArticleService(BaseService):
    """
    Service for managing article evaluation and scoring.

    This service consolidates all article-related operations including:
    - Evaluating articles against queries
    - Scoring article relevance
    - Managing article metadata
    - Determining download decisions
    """

    def __init__(self, config=None, llm_service: LLMService | None = None):
        """
        Initialize the ArticleService.

        Args:
            config: Optional configuration object
            llm_service: Optional LLM service for evaluations
        """
        super().__init__(config)
        self._llm_service = llm_service
        self.query_service = None

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
    def llm_service(self) -> LLMService:
        """Get or create the LLM service."""
        if self._llm_service is None:
            self._llm_service = LLMService(self.config)
        return self._llm_service

    def initialize(self) -> None:
        """Initialize the article service."""
        self.logger.info('Article service initialized')

    def evaluate_against_query(
        self,
        article: AnalysisResponse | ScrapedArticleMetadata,
        query: ResearchQuery,
    ) -> QueryEvaluationResponse:
        """
        Evaluate an article against a research query.

        Args:
            article: Article analysis or metadata to evaluate
            query: Research query to evaluate against

        Returns:
            QueryEvaluationResponse: Evaluation results

        Raises:
            ServiceError: If evaluation fails
        """
        try:
            self.validate_input(article=article, query=query)

            # Prepare evaluation prompt
            prompt = self._build_evaluation_prompt(article, query)

            # Get structured response
            llm = self.llm_service.get_client(
                model=self.config.scrape_filter_llm_config.model
            )
            structured_llm = llm.with_structured_output(
                QueryEvaluationResponse,
                include_raw=False,
                method='json_schema',
            )

            result = structured_llm.invoke(prompt)

            self.log_operation(
                'article_evaluated',
                query=query.name,
                score=result.relevance_score,
                recommendation=result.recommendation,
            )

            return result

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f"evaluating article against query '{query.name}'")
            ) from e

    def evaluate_for_download(
        self,
        metadata: ScrapedArticleMetadata,
        queries: list[ResearchQuery],
    ) -> PreDownloadEvaluationResponse:
        """
        Evaluate scraped metadata to determine if article should be downloaded.

        Args:
            metadata: Scraped article metadata
            queries: List of queries to evaluate against

        Returns:
            PreDownloadEvaluationResponse: Download decision

        Raises:
            ServiceError: If evaluation fails
        """
        try:
            self.validate_input(metadata=metadata)

            if not queries:
                # No queries means download everything
                return PreDownloadEvaluationResponse(
                    relevance_score=1.0,
                    should_download=True,
                    topic_analysis='No queries configured - downloading all articles',
                    reasoning='Automatic download when no queries are configured',
                    confidence=1.0,
                )

            # Evaluate against each query
            evaluations = []
            for query in queries:
                eval_result = self.evaluate_against_query(metadata, query)
                evaluations.append((query, eval_result))

            # Determine overall decision
            best_score = max(eval.relevance_score for _, eval in evaluations)
            matching_queries = [
                query.name
                for query, eval in evaluations
                if eval.relevance_score >= query.minimum_relevance_score
            ]

            should_download = len(matching_queries) > 0

            # Aggregate keyword matches and reasoning
            all_keywords = set()
            all_reasoning = []
            for query, eval in evaluations:
                all_keywords.update(eval.keyword_matches)
                all_reasoning.append(f'{query.name}: {eval.reasoning}')

            result = PreDownloadEvaluationResponse(
                relevance_score=best_score,
                should_download=should_download,
                keyword_matches=list(all_keywords),
                topic_analysis=self._aggregate_topic_analysis(evaluations),
                reasoning='\n'.join(all_reasoning),
                confidence=self._calculate_confidence(evaluations),
                matching_queries=matching_queries,
            )

            self.log_operation(
                'download_evaluation',
                title=metadata.title,
                score=best_score,
                decision='download' if should_download else 'skip',
                matching_queries=len(matching_queries),
            )

            return result

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f"evaluating '{metadata.title}' for download")
            ) from e

    def check_relevance(
        self,
        title: str,
        abstract: str,
        query: ResearchQuery,
    ) -> float:
        """
        Quick relevance check based on keywords and topics.

        Args:
            title: Article title
            abstract: Article abstract
            query: Research query

        Returns:
            float: Relevance score (0.0 to 1.0)
        """
        try:
            score = 0.0
            text_lower = f'{title} {abstract}'.lower()

            # Check keywords
            keyword_matches = sum(
                1 for kw in query.keywords if kw.lower() in text_lower
            )
            if query.keywords:
                score += (keyword_matches / len(query.keywords)) * 0.4

            # Check required topics
            required_matches = sum(
                1 for topic in query.required_topics if topic.lower() in text_lower
            )
            if query.required_topics:
                score += (required_matches / len(query.required_topics)) * 0.4

            # Check preferred topics
            preferred_matches = sum(
                1 for topic in query.preferred_topics if topic.lower() in text_lower
            )
            if query.preferred_topics:
                score += (preferred_matches / len(query.preferred_topics)) * 0.2

            # Check excluded topics (penalty)
            excluded_matches = sum(
                1 for topic in query.excluded_topics if topic.lower() in text_lower
            )
            if excluded_matches > 0:
                score *= 0.5  # Halve score for each excluded topic match

            return min(score, 1.0)

        except Exception as e:
            self.logger.error(self.handle_error(e, 'checking relevance'))
            return 0.0

    def _build_evaluation_prompt(
        self,
        article: AnalysisResponse | ScrapedArticleMetadata,
        query: ResearchQuery,
    ) -> str:
        """Build evaluation prompt for the LLM."""
        # Extract title and abstract based on article type
        if isinstance(article, AnalysisResponse):
            title = article.title if hasattr(article, 'title') else 'Unknown'
            abstract = article.abstract or article.summary or ''
            content = getattr(article, 'content', None)
        else:  # ScrapedArticleMetadata
            title = article.title
            abstract = article.abstract or ''
            content = None

        # Get model provider from config
        model = self.config.scrape_filter_llm_config.model
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

    def _aggregate_topic_analysis(
        self, evaluations: list[tuple[ResearchQuery, QueryEvaluationResponse]]
    ) -> str:
        """Aggregate topic analyses from multiple evaluations."""
        analyses = []
        for query, eval in evaluations:
            if eval.topic_analysis:
                analyses.append(f'{query.name}: {eval.topic_analysis}')
        return ' | '.join(analyses) if analyses else 'No topic analysis available'

    def _calculate_confidence(
        self, evaluations: list[tuple[ResearchQuery, QueryEvaluationResponse]]
    ) -> float:
        """Calculate overall confidence from multiple evaluations."""
        if not evaluations:
            return 0.0
        confidences = [eval.confidence for _, eval in evaluations]
        return sum(confidences) / len(confidences)

    def health_check(self) -> dict[str, str]:
        """Basic health status for the ArticleService."""
        return super().health_check()

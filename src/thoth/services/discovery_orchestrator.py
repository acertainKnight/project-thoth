"""Discovery Orchestrator for research-question-centric article discovery.

This service orchestrates the complete discovery workflow:
1. Resolves source selection (['*'] → all active sources)
2. Queries multiple sources in parallel
3. Uses LLM to calculate relevance scores
4. Handles deduplication
5. Stores matches and updates statistics
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Optional
from uuid import UUID


from thoth.config import Config
from thoth.discovery.discovery_manager import DiscoveryManager
from thoth.repositories.research_question_match_repository import (
    ResearchQuestionMatchRepository,
)
from thoth.repositories.article_research_match_repository import (
    ArticleResearchMatchRepository,
)
from thoth.repositories.available_source_repository import AvailableSourceRepository
from thoth.repositories.research_question_repository import ResearchQuestionRepository
from thoth.services.base import BaseService
from thoth.services.llm_service import LLMService
from thoth.utilities.pdf_url_converter import convert_to_pdf_url
from thoth.utilities.schemas import ScrapedArticleMetadata


class DiscoveryOrchestrator(BaseService):
    """
    Orchestrates research-question-centric article discovery.

    This service coordinates the complete discovery workflow from
    research question to matched articles with LLM-based relevance scoring.
    """

    def __init__(
        self,
        config: Config,
        llm_service: LLMService,
        discovery_manager: DiscoveryManager,
        postgres_service=None,
    ):
        """
        Initialize the Discovery Orchestrator.

        Args:
            config: Application configuration
            llm_service: LLM service for relevance scoring
            discovery_manager: Discovery manager for source querying
            postgres_service: PostgreSQL service for database operations
        """
        super().__init__(config)
        self.llm_service = llm_service
        self.discovery_manager = discovery_manager
        self.postgres_service = postgres_service

        # Initialize repositories with postgres service
        self.question_repo = ResearchQuestionRepository(postgres_service or config)
        self.source_repo = AvailableSourceRepository(postgres_service or config)
        self.match_repo = ResearchQuestionMatchRepository(postgres_service or config)
        self.legacy_match_repo = ArticleResearchMatchRepository(postgres_service or config)

        self.logger.info('DiscoveryOrchestrator initialized')

    async def run_discovery_for_question(
        self,
        question_id: UUID,
        max_articles: Optional[int] = None,  # noqa: UP007
    ) -> dict[str, Any]:
        """
        Run discovery workflow for a single research question.

        This is the main entry point for discovery execution.

        Args:
            question_id: Research question UUID
            max_articles: Maximum articles to process (overrides question config)

        Returns:
            Discovery result summary with statistics
        """
        start_time = time.time()

        # Load research question
        question = await self.question_repo.get_by_id(question_id)
        if not question:
            self.logger.error(f'Research question {question_id} not found')
            return self._error_result(
                question_id=question_id,
                error='Research question not found',
                execution_time=time.time() - start_time,
            )

        self.logger.info(
            f"Starting discovery for research question '{question['name']}' ({question_id})"
        )

        try:
            # Step 1: Resolve source selection
            sources = await self._resolve_sources(question['selected_sources'])
            if not sources:
                self.logger.warning(
                    f'No active sources available for question {question_id}'
                )
                return self._empty_result(
                    question_id=question_id,
                    question_name=question['name'],
                    execution_time=time.time() - start_time,
                )

            self.logger.info(f'Resolved {len(sources)} sources: {sources}')

            # Step 2: Query sources in parallel
            max_per_run = max_articles or question.get('max_articles_per_run', 50)
            articles = await self._query_sources_parallel(
                sources=sources,
                max_articles=max_per_run,
                question=question,
            )

            if not articles:
                self.logger.info(f'No articles found for question {question_id}')
                return self._empty_result(
                    question_id=question_id,
                    question_name=question['name'],
                    execution_time=time.time() - start_time,
                )

            self.logger.info(f'Found {len(articles)} articles from {len(sources)} sources')

            # Step 3: Deduplicate and process articles
            matched_count, processed_count = await self._process_and_match_articles(
                articles=articles,
                question=question,
            )

            execution_time = time.time() - start_time

            self.logger.info(
                f"Discovery completed for '{question['name']}': "
                f'{len(articles)} found, {processed_count} processed, '
                f'{matched_count} matched in {execution_time:.2f}s'
            )

            return {
                'success': True,
                'question_id': str(question_id),
                'question_name': question['name'],
                'sources_queried': sources,
                'articles_found': len(articles),
                'articles_processed': processed_count,
                'articles_matched': matched_count,
                'execution_time_seconds': execution_time,
                'timestamp': datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(
                f'Discovery failed for question {question_id}: {e}', exc_info=True
            )
            return self._error_result(
                question_id=question_id,
                error=str(e),
                execution_time=time.time() - start_time,
            )

    async def run_discovery_batch(
        self,
        question_ids: list[UUID],
    ) -> dict[str, Any]:
        """
        Run discovery for multiple research questions in parallel.

        This is used by the scheduler for daily batch processing.

        Args:
            question_ids: List of research question UUIDs

        Returns:
            Batch result summary with per-question statistics
        """
        start_time = time.time()

        self.logger.info(f'Starting batch discovery for {len(question_ids)} questions')

        # Run discoveries in parallel
        tasks = [
            self.run_discovery_for_question(question_id) for question_id in question_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate statistics
        total_found = 0
        total_processed = 0
        total_matched = 0
        successful = 0
        failed = 0

        for result in results:
            if isinstance(result, Exception):
                failed += 1
                self.logger.error(f'Batch discovery task failed: {result}')
            elif result.get('success'):
                successful += 1
                total_found += result.get('articles_found', 0)
                total_processed += result.get('articles_processed', 0)
                total_matched += result.get('articles_matched', 0)
            else:
                failed += 1

        execution_time = time.time() - start_time

        self.logger.info(
            f'Batch discovery completed: {successful} successful, {failed} failed, '
            f'{total_found} found, {total_processed} processed, {total_matched} matched '
            f'in {execution_time:.2f}s'
        )

        return {
            'success': True,
            'questions_processed': len(question_ids),
            'questions_successful': successful,
            'questions_failed': failed,
            'total_articles_found': total_found,
            'total_articles_processed': total_processed,
            'total_articles_matched': total_matched,
            'execution_time_seconds': execution_time,
            'timestamp': datetime.now().isoformat(),
            'individual_results': [r for r in results if not isinstance(r, Exception)],
        }

    # ==================== Source Resolution ====================

    async def _resolve_sources(self, selected_sources: list[str]) -> list[str]:
        """
        Resolve source selection to actual source names.

        Handles special case: ['*'] → all active sources from database

        Args:
            selected_sources: Source selection array from research question

        Returns:
            List of resolved source names
        """
        # Check for wildcard (ALL sources)
        if len(selected_sources) == 1 and selected_sources[0] == '*':
            self.logger.debug("Resolving '*' to all active sources")
            all_sources = await self.source_repo.list_all_source_names()
            self.logger.info(f"Resolved '*' to {len(all_sources)} active sources")
            return all_sources

        # Validate specific sources against available sources
        available = await self.source_repo.list_all_source_names()
        available_set = set(available)

        valid_sources = []
        for source in selected_sources:
            if source in available_set:
                valid_sources.append(source)
            else:
                self.logger.warning(f"Source '{source}' not available in registry, skipping")

        if not valid_sources:
            self.logger.warning(
                f'None of the selected sources {selected_sources} are available'
            )

        return valid_sources

    # ==================== Parallel Source Querying ====================

    async def _query_sources_parallel(
        self,
        sources: list[str],
        max_articles: int,
        question: dict[str, Any],
    ) -> list[ScrapedArticleMetadata]:
        """
        Query multiple sources in parallel using asyncio.gather.

        Args:
            sources: List of source names to query
            max_articles: Maximum articles per source
            question: Research question with keywords, topics, and authors

        Returns:
            Combined list of articles from all sources
        """
        self.logger.info(
            f'Querying {len(sources)} sources in parallel (max {max_articles} per source)'
        )

        # Create tasks for parallel execution
        tasks = [
            self._query_single_source(source, max_articles, question)
            for source in sources
        ]

        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results and handle errors
        all_articles = []
        for source, result in zip(sources, results):  # noqa: B905
            if isinstance(result, Exception):
                self.logger.error(f"Source '{source}' query failed: {result}")
                # Update source health status
                await self.source_repo.increment_error_count(source)
            else:
                all_articles.extend(result)
                self.logger.debug(f"Source '{source}' returned {len(result)} articles")
                # Update source statistics
                await self.source_repo.increment_query_count(
                    name=source,
                    articles_found=len(result),
                )

        self.logger.info(f'Parallel querying completed: {len(all_articles)} total articles')

        return all_articles

    async def _query_single_source(
        self,
        source_name: str,
        max_articles: int,
        question: dict[str, Any],
    ) -> list[ScrapedArticleMetadata]:
        """
        Query a single source for articles.

        This wraps the DiscoveryManager's source querying with error handling.

        Args:
            source_name: Name of the source to query
            max_articles: Maximum articles to retrieve
            question: Research question with keywords, topics, and authors

        Returns:
            List of articles from the source
        """
        try:
            # Get source configuration from DiscoveryManager (NOW ASYNC)
            source = await self.discovery_manager.get_source(source_name)
            if not source:
                self.logger.warning(f"Source configuration for '{source_name}' not found")
                return []

            # Query the source with research question data
            articles = await asyncio.to_thread(
                self.discovery_manager._discover_from_source,
                source,
                max_articles,
                question,  # Pass question parameter explicitly
            )

            return articles

        except Exception as e:
            self.logger.error(f"Failed to query source '{source_name}': {e}", exc_info=True)
            raise

    # ==================== Article Processing & Matching ====================

    async def _process_and_match_articles(
        self,
        articles: list[ScrapedArticleMetadata],
        question: dict[str, Any],
    ) -> tuple[int, int]:
        """
        Process articles: deduplicate, score relevance, store matches.

        Args:
            articles: List of discovered articles
            question: Research question record

        Returns:
            Tuple of (matched_count, processed_count)
        """
        processed_count = 0
        matched_count = 0
        question_id = question['id']
        min_score = question.get('min_relevance_score', 0.5)

        for article_meta in articles:
            try:
                # Step 1: Get or create paper in paper_metadata (handles deduplication)
                article_id, was_created = await self._get_or_create_article(
                    article_meta
                )

                if not article_id:
                    self.logger.warning(
                        f'Failed to create paper: {article_meta.title}'
                    )
                    continue

                processed_count += 1

                # Step 2: Calculate relevance using LLM
                # Note: create_match has ON CONFLICT handling, so duplicate matches are updated
                relevance_result = await self._calculate_relevance_score(
                    article_meta=article_meta,
                    question=question,
                )

                if relevance_result['score'] < min_score:
                    self.logger.debug(
                        f"Article '{article_meta.title}' relevance {relevance_result['score']:.3f} "
                        f'below threshold {min_score}, skipping'
                    )
                    continue

                # Step 3: Store match (using new schema with paper_id)
                match_id = await self.match_repo.create_match(
                    paper_id=article_id,  # article_id is now paper_id from paper_metadata
                    question_id=question_id,
                    relevance_score=relevance_result['score'],
                    matched_keywords=relevance_result.get('matched_keywords'),
                    discovered_via_source=article_meta.source,
                )

                if match_id:
                    matched_count += 1
                    self.logger.info(
                        f"Matched article '{article_meta.title}' to question '{question['name']}' "
                        f'(relevance: {relevance_result["score"]:.3f})'
                    )
                else:
                    self.logger.error(f'Failed to store match for paper {article_id}')

            except Exception as e:
                self.logger.error(
                    f"Error processing article '{article_meta.title}': {e}",
                    exc_info=True,
                )

        return matched_count, processed_count

    async def _get_or_create_article(
        self,
        article_meta: ScrapedArticleMetadata,
    ) -> tuple[Optional[UUID], bool]:  # noqa: UP007
        """
        Get or create paper in paper_metadata with deduplication.

        Uses ResearchQuestionMatchRepository to create papers in paper_metadata table.

        Args:
            article_meta: Article metadata from source

        Returns:
            Tuple of (paper_id, was_created) where paper_id is UUID or None if creation failed,
            and was_created is True if new paper was created
        """  # noqa: W505
        try:
            # Convert URL to PDF URL if possible (for ArXiv, bioRxiv, etc.)
            pdf_url = None
            if article_meta.url:
                pdf_url = convert_to_pdf_url(article_meta.url)

            # Use repository's find_or_create_paper pattern (creates in paper_metadata)
            paper_id, was_created = await self.match_repo.find_or_create_paper(
                title=article_meta.title,
                abstract=article_meta.abstract,
                authors=article_meta.authors,
                doi=article_meta.doi,
                arxiv_id=article_meta.arxiv_id,
                url=article_meta.url,
                pdf_url=pdf_url,
                publication_date=article_meta.publication_date,
            )

            return article_id, was_created

        except Exception as e:
            self.logger.error(f'Failed to get/create article: {e}', exc_info=True)
            return None, False

    # ==================== LLM Relevance Scoring ====================

    async def _calculate_relevance_score(
        self,
        article_meta: ScrapedArticleMetadata,
        question: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Calculate relevance score using LLM semantic understanding.

        This is the core intelligence of the discovery system.

        Args:
            article_meta: Article metadata
            question: Research question record

        Returns:
            Dictionary with:
                - score: Relevance score (0.0-1.0)
                - matched_keywords: Keywords that matched
                - reasoning: LLM explanation
        """
        # Build prompt for LLM evaluation
        prompt = self._build_relevance_prompt(
            article_title=article_meta.title,
            article_abstract=article_meta.abstract or 'No abstract available',
            article_authors=article_meta.authors or [],
            question_name=question['name'],
            keywords=question.get('keywords', []),
            topics=question.get('topics', []),
            preferred_authors=question.get('authors', []),
        )

        try:
            # Get configured LLM client
            client = await asyncio.to_thread(
                self.llm_service.get_client,
                temperature=0.1,  # Low temperature for consistent scoring
                max_tokens=500,
            )

            # Invoke with retry logic
            response = await asyncio.to_thread(
                self.llm_service.invoke_with_retry,
                client,
                prompt,
            )

            # Extract content from response
            response_content = (
                response.content if hasattr(response, 'content') else str(response)
            )

            # Parse LLM response
            result = self._parse_relevance_response(response_content)

            self.logger.debug(
                f"LLM relevance for '{article_meta.title}': "
                f'score={result["score"]:.3f}, matched={result.get("matched_keywords", [])}'
            )

            return result

        except Exception as e:
            self.logger.error(f'LLM relevance scoring failed: {e}', exc_info=True)
            # Return low score on error to skip article
            return {
                'score': 0.0,
                'matched_keywords': [],
                'reasoning': f'Error during scoring: {e}',
            }

    def _build_relevance_prompt(
        self,
        article_title: str,
        article_abstract: str,
        article_authors: list[str],
        question_name: str,
        keywords: list[str],
        topics: list[str],
        preferred_authors: list[str],
    ) -> str:
        """
        Build LLM prompt for relevance assessment.

        The prompt instructs the LLM to evaluate semantic relevance
        and return a structured response.
        """
        prompt = f"""You are a research article relevance evaluator. Assess whether a research article is relevant to a user's research question.

Research Question: {question_name}
Keywords: {', '.join(keywords) if keywords else 'None specified'}
Topics: {', '.join(topics) if topics else 'None specified'}
Preferred Authors: {', '.join(preferred_authors) if preferred_authors else 'None specified'}

Article to Evaluate:
Title: {article_title}
Abstract: {article_abstract}
Authors: {', '.join(article_authors) if article_authors else 'Unknown'}

Instructions:
1. Evaluate the semantic relevance of this article to the research question
2. Consider:
   - How well the article's content matches the research question
   - Overlap with specified keywords and topics
   - Author match if preferred authors are specified
   - Overall research area alignment

3. Assign a relevance score from 0.0 to 1.0 where:
   - 0.0-0.3: Not relevant or tangentially related
   - 0.3-0.5: Somewhat relevant but not a strong match
   - 0.5-0.7: Relevant and useful
   - 0.7-0.9: Highly relevant
   - 0.9-1.0: Extremely relevant, perfect match

4. Respond ONLY in this exact JSON format:
{{
  "score": <float between 0.0 and 1.0>,
  "matched_keywords": [<list of keywords that matched>],
  "reasoning": "<brief explanation of the score>"
}}

Your response (JSON only):"""

        return prompt

    def _parse_relevance_response(self, llm_response: str) -> dict[str, Any]:
        """
        Parse LLM response into structured result.

        Args:
            llm_response: Raw LLM response text

        Returns:
            Parsed result dictionary
        """
        try:
            import json
            import re

            # Extract JSON from response (handle markdown code blocks)
            response_text = llm_response.strip()

            # Use regex to extract JSON from markdown code blocks
            # Handles: ```json\n{...}\n``` or ```\n{...}\n```
            markdown_pattern = r'```(?:json)?\s*\n(.*?)\n\s*```'
            markdown_match = re.search(markdown_pattern, response_text, re.DOTALL)
            if markdown_match:
                response_text = markdown_match.group(1).strip()
            elif response_text.startswith('```'):
                # Fallback: Remove lines that start with ``` (after stripping whitespace)  # noqa: W505
                lines = response_text.split('\n')
                json_lines = [
                    l for l in lines if l.strip() and not l.strip().startswith('```')  # noqa: E741
                ]
                response_text = '\n'.join(json_lines)

            # Parse JSON
            result = json.loads(response_text)

            # Validate and normalize
            score = float(result.get('score', 0.0))
            score = max(0.0, min(1.0, score))  # Clamp to [0.0, 1.0]

            matched_keywords = result.get('matched_keywords', [])
            if not isinstance(matched_keywords, list):
                matched_keywords = []

            reasoning = result.get('reasoning', 'No reasoning provided')

            return {
                'score': score,
                'matched_keywords': matched_keywords,
                'reasoning': reasoning,
            }

        except Exception as e:
            self.logger.error(f'Failed to parse LLM relevance response: {e}')
            self.logger.debug(f'Raw response: {llm_response}')
            return {
                'score': 0.0,
                'matched_keywords': [],
                'reasoning': f'Failed to parse LLM response: {e}',
            }

    # ==================== Result Helpers ====================

    def _empty_result(
        self,
        question_id: UUID,
        question_name: str,
        execution_time: float,
    ) -> dict[str, Any]:
        """Create empty result for no articles found."""
        return {
            'success': True,
            'question_id': str(question_id),
            'question_name': question_name,
            'sources_queried': [],
            'articles_found': 0,
            'articles_processed': 0,
            'articles_matched': 0,
            'execution_time_seconds': execution_time,
            'timestamp': datetime.now().isoformat(),
        }

    def _error_result(
        self,
        question_id: UUID,
        error: str,
        execution_time: float,
    ) -> dict[str, Any]:
        """Create error result."""
        return {
            'success': False,
            'question_id': str(question_id),
            'error': error,
            'execution_time_seconds': execution_time,
            'timestamp': datetime.now().isoformat(),
        }

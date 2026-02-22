"""Discovery Orchestrator for research-question-centric article discovery.

This service orchestrates the complete discovery workflow:
1. Resolves source selection (['*'] → all active sources)
2. Queries multiple sources in parallel
3. Uses LLM to calculate relevance scores
4. Handles deduplication
5. Stores matches and updates statistics
"""

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from thoth.config import Config
from thoth.discovery.discovery_manager import DiscoveryManager
from thoth.repositories.article_research_match_repository import (
    ArticleResearchMatchRepository,
)
from thoth.repositories.available_source_repository import AvailableSourceRepository
from thoth.repositories.research_question_match_repository import (
    ResearchQuestionMatchRepository,
)
from thoth.repositories.research_question_repository import ResearchQuestionRepository
from thoth.services.base import BaseService
from thoth.services.llm_service import LLMService
from thoth.utilities.pdf_url_converter import convert_to_pdf_url
from thoth.utilities.schemas import ScrapedArticleMetadata


@dataclass
class MergedSourceQuery:
    """Represents a consolidated query to a single source across multiple questions."""

    source_name: str
    keywords: list[str]
    topics: list[str]
    date_start: str | None
    date_end: str | None
    max_articles: int
    question_ids: list[UUID]


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
        self.legacy_match_repo = ArticleResearchMatchRepository(
            postgres_service or config
        )

        self.logger.info('DiscoveryOrchestrator initialized')

    async def run_discovery_for_question(
        self,
        question_id: UUID,
        max_articles: int | None = None,
        _force_run: bool = False,
    ) -> dict[str, Any]:
        """
        Run discovery workflow for a single research question.

        This is the main entry point for discovery execution.

        Args:
            question_id: Research question UUID
            max_articles: Maximum articles to process (overrides question config)
            _force_run: Accepted for backward compat, currently unused.

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

            self.logger.info(
                f'Found {len(articles)} articles from {len(sources)} sources'
            )

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
                self.logger.warning(
                    f"Source '{source}' not available in registry, skipping"
                )

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

        self.logger.info(
            f'Parallel querying completed: {len(all_articles)} total articles'
        )

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
                self.logger.warning(
                    f"Source configuration for '{source_name}' not found"
                )
                return []

            # Browser workflows need async execution -- handle them here
            # instead of delegating to the sync _discover_from_source path.
            if source.source_type == 'browser_workflow':
                return await self._execute_browser_workflow(
                    source, max_articles, question
                )

            # Prepare question data with date filters
            # Convert publication_date_range to date_filter_start/end if present
            question_data = dict(question)
            if question_data.get('publication_date_range'):
                date_range = question_data['publication_date_range']
                if isinstance(date_range, dict):
                    if 'start' in date_range:
                        question_data['date_filter_start'] = date_range['start']
                    if 'end' in date_range:
                        question_data['date_filter_end'] = date_range['end']
                    self.logger.debug(
                        f'Converted publication_date_range to date filters: '
                        f'{date_range.get("start")} to {date_range.get("end")}'
                    )

            # Query the source with research question data
            articles = await asyncio.to_thread(
                self.discovery_manager._discover_from_source,
                source,
                max_articles,
                question_data,  # Pass enhanced question data with date filters
            )

            return articles

        except Exception as e:
            self.logger.error(
                f"Failed to query source '{source_name}': {e}", exc_info=True
            )
            raise

    async def _execute_browser_workflow(
        self,
        source,
        max_articles: int,
        question: dict[str, Any],
    ) -> list[ScrapedArticleMetadata]:
        """
        Execute a browser workflow source asynchronously.

        Browser workflows can't go through the sync _discover_from_source path
        because they need async Playwright execution and a postgres_service reference
        that the DiscoveryManager doesn't carry.

        Args:
            source: DiscoverySource with source_type='browser_workflow'
            max_articles: Maximum articles to retrieve
            question: Research question data

        Returns:
            List of discovered articles, empty on failure
        """
        from thoth.discovery.plugins import get_browser_workflow_plugin_class

        plugin_cls = get_browser_workflow_plugin_class()
        if plugin_cls is None:
            self.logger.warning(
                f'Browser workflow plugin not available (playwright not installed). '
                f'Skipping source {source.name}.'
            )
            return []

        if not self.postgres_service:
            self.logger.error(
                f'Cannot execute browser workflow {source.name}: '
                'postgres_service not configured on orchestrator'
            )
            return []

        plugin = None
        try:
            plugin = plugin_cls(
                postgres_service=self.postgres_service,
                config=source.api_config,
            )
            await plugin.initialize()

            # Build a ResearchQuery from the question data
            from thoth.utilities.schemas import ResearchQuery

            research_query = ResearchQuery(
                name=source.api_config.get('name', source.name),
                description=source.api_config.get(
                    'description', f'Browser workflow: {source.name}'
                ),
                research_question=question.get('question', ''),
                keywords=question.get('keywords', []),
                required_topics=question.get('topics', []),
                preferred_topics=question.get('preferred_topics', []),
                excluded_topics=question.get('excluded_topics', []),
            )

            query_id = question.get('id')
            articles = await plugin.discover_async(
                query=research_query,
                max_results=max_articles,
                query_id=query_id,
            )

            self.logger.info(
                f'Browser workflow {source.name} returned {len(articles)} articles'
            )
            return articles

        except Exception as e:
            self.logger.error(
                f'Browser workflow execution failed for {source.name}: {e}',
                exc_info=True,
            )
            return []

        finally:
            if plugin is not None:
                try:
                    await plugin.shutdown()
                except Exception:
                    pass

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
                article_id, _was_created = await self._get_or_create_article(
                    article_meta, user_id=question.get('user_id')
                )

                if not article_id:
                    self.logger.warning(f'Failed to create paper: {article_meta.title}')
                    continue

                processed_count += 1

                # Step 2: Calculate relevance using LLM
                # Note: create_match has ON CONFLICT handling,
                # so duplicate matches are updated
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
                    user_id=question.get('user_id'),
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
        user_id: str | None = None,
    ) -> tuple[UUID | None, bool]:
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
                user_id=user_id,
                url=article_meta.url,
                pdf_url=pdf_url,
                publication_date=article_meta.publication_date,
            )

            return paper_id, was_created

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
                    line
                    for line in lines
                    if line.strip() and not line.strip().startswith('```')
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

    # ==================== Consolidated Discovery Pipeline ====================

    async def run_consolidated_discovery(
        self, questions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Run consolidated discovery across multiple research questions.

        This is the optimized pipeline that:
        - Merges queries for shared sources
        - Queries each source once
        - Globally deduplicates articles before LLM scoring
        - Scores unique articles against applicable questions only

        Args:
            questions: List of research question records

        Returns:
            Dict with overall stats and per-question results
        """
        start_time = time.time()

        if not questions:
            self.logger.warning('No questions provided for consolidated discovery')
            return {
                'success': True,
                'questions_processed': 0,
                'total_sources_queried': 0,
                'total_articles_found': 0,
                'total_unique_articles': 0,
                'execution_time_seconds': time.time() - start_time,
                'timestamp': datetime.now().isoformat(),
                'question_results': {},
            }

        self.logger.info(
            f'Starting consolidated discovery for {len(questions)} questions'
        )

        try:
            # Step 1: Build source plan (merge queries)
            source_plan = self._build_source_plan(questions)

            # Step 2: Fetch all sources once
            articles_with_source = await self._fetch_all_sources(source_plan)

            # Step 3: Global deduplication
            unique_articles = self._deduplicate_article_pool(articles_with_source)

            # Step 4: Match articles to questions with LLM scoring
            match_results = await self._match_articles_to_questions(
                unique_articles, questions, source_plan
            )

            # Build overall result
            execution_time = time.time() - start_time

            # Aggregate stats
            total_processed = sum(
                r['articles_processed'] for r in match_results.values()
            )
            total_matched = sum(r['articles_matched'] for r in match_results.values())

            # Build per-question results
            question_results = {}
            for question in questions:
                question_id = question['id']
                match_result = match_results.get(question_id, {})

                question_results[str(question_id)] = {
                    'question_id': str(question_id),
                    'question_name': question['name'],
                    'articles_processed': match_result.get('articles_processed', 0),
                    'articles_matched': match_result.get('articles_matched', 0),
                }

            result = {
                'success': True,
                'questions_processed': len(questions),
                'total_sources_queried': len(source_plan),
                'total_articles_found': len(articles_with_source),
                'total_unique_articles': len(unique_articles),
                'total_articles_scored': total_processed,
                'total_articles_matched': total_matched,
                'execution_time_seconds': execution_time,
                'timestamp': datetime.now().isoformat(),
                'question_results': question_results,
            }

            self.logger.info(
                f'Consolidated discovery completed: {len(source_plan)} sources, '
                f'{len(articles_with_source)} articles, {len(unique_articles)} unique, '
                f'{total_matched} matched in {execution_time:.2f}s'
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f'Consolidated discovery failed: {e}', exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'questions_processed': 0,
                'execution_time_seconds': execution_time,
                'timestamp': datetime.now().isoformat(),
            }

    def _build_source_plan(
        self, questions: list[dict[str, Any]]
    ) -> list[MergedSourceQuery]:
        """
        Build consolidated source queries by merging parameters across questions.

        Groups questions by shared sources and merges their search parameters:
        - Keywords/topics: union
        - Date range: widest window (earliest start, latest end)
        - Max articles: maximum across all questions

        Args:
            questions: List of research question records from database

        Returns:
            List of MergedSourceQuery objects, one per unique source
        """
        source_map: dict[str, MergedSourceQuery] = {}

        for question in questions:
            selected = question.get('selected_sources', [])

            # Handle wildcard separately -- we'll expand it later
            if selected == ['*']:
                selected = ['*']

            for source_name in selected:
                if source_name not in source_map:
                    source_map[source_name] = MergedSourceQuery(
                        source_name=source_name,
                        keywords=[],
                        topics=[],
                        date_start=None,
                        date_end=None,
                        max_articles=0,
                        question_ids=[],
                    )

                merged = source_map[source_name]
                merged.question_ids.append(question['id'])

                # Merge keywords
                keywords = question.get('keywords', [])
                if keywords:
                    merged.keywords.extend(keywords)

                # Merge topics
                topics = question.get('topics', [])
                if topics:
                    merged.topics.extend(topics)

                # Expand date range to widest window
                q_start = question.get('date_filter_start')
                q_end = question.get('date_filter_end')

                if q_start:
                    if merged.date_start is None or q_start < merged.date_start:
                        merged.date_start = q_start

                if q_end:
                    if merged.date_end is None or q_end > merged.date_end:
                        merged.date_end = q_end

                # Take max articles
                q_max = question.get('max_articles_per_run', 50)
                if q_max > merged.max_articles:
                    merged.max_articles = q_max

        # Deduplicate keywords and topics within each merged query
        for merged in source_map.values():
            merged.keywords = list(set(merged.keywords))
            merged.topics = list(set(merged.topics))

        queries = list(source_map.values())

        self.logger.info(
            f'Built source plan: {len(queries)} unique sources from '
            f'{len(questions)} questions'
        )

        return queries

    async def _fetch_all_sources(
        self, source_plan: list[MergedSourceQuery]
    ) -> list[tuple[ScrapedArticleMetadata, str]]:
        """
        Query each source once using merged parameters.

        Args:
            source_plan: List of consolidated source queries

        Returns:
            List of (article, source_name) tuples tracking article provenance
        """
        # Expand wildcard sources first
        expanded_plan: list[MergedSourceQuery] = []
        for merged_query in source_plan:
            if merged_query.source_name == '*':
                # Expand to all active sources
                all_sources = await self.source_repo.list_all_source_names()
                for source_name in all_sources:
                    expanded_plan.append(
                        MergedSourceQuery(
                            source_name=source_name,
                            keywords=merged_query.keywords,
                            topics=merged_query.topics,
                            date_start=merged_query.date_start,
                            date_end=merged_query.date_end,
                            max_articles=merged_query.max_articles,
                            question_ids=merged_query.question_ids,
                        )
                    )
            else:
                expanded_plan.append(merged_query)

        self.logger.info(
            f'Fetching {len(expanded_plan)} sources with merged parameters'
        )

        # Query all sources in parallel
        tasks = []
        for merged_query in expanded_plan:
            # Build a synthetic question dict with merged parameters
            synthetic_question = {
                'keywords': merged_query.keywords,
                'topics': merged_query.topics,
                'date_filter_start': merged_query.date_start,
                'date_filter_end': merged_query.date_end,
                'question': f'Consolidated query for {len(merged_query.question_ids)} questions',
            }

            tasks.append(
                self._query_single_source(
                    merged_query.source_name,
                    merged_query.max_articles,
                    synthetic_question,
                )
            )

        # Execute all queries in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results, tracking source provenance
        articles_with_source: list[tuple[ScrapedArticleMetadata, str]] = []
        for merged_query, result in zip(expanded_plan, results):  # noqa: B905
            if isinstance(result, Exception):
                self.logger.error(
                    f"Source '{merged_query.source_name}' query failed: {result}"
                )
                await self.source_repo.increment_error_count(merged_query.source_name)
            else:
                for article in result:
                    articles_with_source.append((article, merged_query.source_name))
                self.logger.debug(
                    f"Source '{merged_query.source_name}' returned {len(result)} articles"
                )
                await self.source_repo.increment_query_count(
                    name=merged_query.source_name,
                    articles_found=len(result),
                )

        self.logger.info(
            f'Fetched {len(articles_with_source)} total articles from '
            f'{len(expanded_plan)} sources'
        )

        return articles_with_source

    def _deduplicate_article_pool(
        self, articles_with_source: list[tuple[ScrapedArticleMetadata, str]]
    ) -> list[tuple[ScrapedArticleMetadata, list[str]]]:
        """
        Deduplicate articles in memory before any DB or LLM calls.

        Uses priority cascade:
        1. DOI match (exact, case-insensitive)
        2. ArXiv ID match (normalized, strip version suffix)
        3. Normalized title + first author match

        When duplicates are found, merges metadata and tracks all sources
        that contributed this article.

        Args:
            articles_with_source: List of (article, source_name) tuples

        Returns:
            List of (article, source_names) tuples with unique articles
        """
        if not articles_with_source:
            return []

        # Use multiple indexes for different ID types
        # Each maps to (article, source_set)
        arxiv_index: dict[str, tuple[ScrapedArticleMetadata, set[str]]] = {}
        doi_index: dict[str, tuple[ScrapedArticleMetadata, set[str]]] = {}
        title_index: dict[str, tuple[ScrapedArticleMetadata, set[str]]] = {}

        for article, source_name in articles_with_source:
            # Generate all possible keys for this article
            arxiv_key = None
            doi_key = None
            title_key = None

            if article.arxiv_id:
                # Normalize ArXiv ID (remove version)
                arxiv_id = article.arxiv_id.strip().lower()
                if 'v' in arxiv_id:
                    arxiv_id = arxiv_id.split('v')[0]
                arxiv_key = arxiv_id

            if article.doi:
                doi_key = article.doi.strip().lower()

            # Always generate title key as fallback
            title_key = self._generate_title_key(article)

            # Check if we've seen this article before
            existing_entry = None

            # Priority 1: Check ArXiv ID
            if arxiv_key and arxiv_key in arxiv_index:
                existing_entry = arxiv_index[arxiv_key]

            # Priority 2: Check DOI
            elif doi_key and doi_key in doi_index:
                existing_entry = doi_index[doi_key]
                # Also add to arxiv_index if this article has ArXiv ID
                if arxiv_key:
                    arxiv_index[arxiv_key] = existing_entry

            # Priority 3: Check title
            elif title_key in title_index:
                existing_entry = title_index[title_key]
                # Update other indexes
                if arxiv_key:
                    arxiv_index[arxiv_key] = existing_entry
                if doi_key:
                    doi_index[doi_key] = existing_entry

            if existing_entry:
                # Duplicate found - merge and track source
                existing_article, existing_sources = existing_entry
                merged = self.discovery_manager._merge_article_metadata(
                    existing_article, article
                )
                existing_sources.add(source_name)

                merged_entry = (merged, existing_sources)

                # Update all relevant indexes with merged version
                if arxiv_key:
                    arxiv_index[arxiv_key] = merged_entry
                if doi_key:
                    doi_index[doi_key] = merged_entry
                title_index[title_key] = merged_entry
            else:
                # New article - add to all relevant indexes
                new_entry = (article, {source_name})
                if arxiv_key:
                    arxiv_index[arxiv_key] = new_entry
                if doi_key:
                    doi_index[doi_key] = new_entry
                title_index[title_key] = new_entry

        # Return unique articles with source lists
        seen_ids = set()
        unique: list[tuple[ScrapedArticleMetadata, list[str]]] = []
        for article, sources in title_index.values():
            article_id = id(article)
            if article_id not in seen_ids:
                seen_ids.add(article_id)
                unique.append((article, list(sources)))

        self.logger.info(
            f'Deduplicated {len(articles_with_source)} articles to '
            f'{len(unique)} unique articles'
        )

        return unique

    def _generate_title_key(self, article: ScrapedArticleMetadata) -> str:
        """Generate normalized title+author key for matching."""
        # Normalize title: lowercase, remove punctuation, collapse whitespace
        title = article.title.lower()
        title = re.sub(r'[^\w\s]', '', title)
        title = ' '.join(title.split())

        # Normalize first author
        first_author = ''
        if article.authors:
            first_author = ' '.join(article.authors[0].lower().split())

        return f'{title}:{first_author}'

    async def _match_articles_to_questions(
        self,
        unique_articles: list[tuple[ScrapedArticleMetadata, list[str]]],
        questions: list[dict[str, Any]],
        source_plan: list[MergedSourceQuery],
    ) -> dict[UUID, dict[str, Any]]:
        """
        Match unique articles to applicable questions with LLM scoring.

        For each article:
        1. Filter questions by source overlap
        2. Filter by question date boundaries
        3. Skip if already scored above threshold
        4. LLM score and store match

        Args:
            unique_articles: List of (article, source_names) tuples
            questions: List of research question records
            source_plan: Source plan to map questions to sources

        Returns:
            Dict mapping question_id to result dict with counts
        """
        # Build question index for quick lookup
        question_by_id = {q['id']: q for q in questions}

        # Build source-to-questions mapping from source plan
        source_to_questions: dict[str, set[UUID]] = {}
        for merged_query in source_plan:
            for question_id in merged_query.question_ids:
                if merged_query.source_name not in source_to_questions:
                    source_to_questions[merged_query.source_name] = set()
                source_to_questions[merged_query.source_name].add(question_id)

        # Initialize result counters per question
        results: dict[UUID, dict[str, Any]] = {}
        for question in questions:
            results[question['id']] = {
                'articles_processed': 0,
                'articles_matched': 0,
            }

        self.logger.info(
            f'Matching {len(unique_articles)} articles to {len(questions)} questions'
        )

        # Process each article
        for article, article_sources in unique_articles:
            # Determine applicable questions
            applicable_question_ids = set()

            for source_name in article_sources:
                if source_name in source_to_questions:
                    applicable_question_ids.update(source_to_questions[source_name])

            if not applicable_question_ids:
                self.logger.debug(
                    f"Article '{article.title}' has no applicable questions"
                )
                continue

            # Get or create paper in database using the first applicable
            # question's user_id.  Papers in paper_metadata are shared; the
            # user_id here only matters for the initial INSERT row ownership.
            first_question = question_by_id[next(iter(applicable_question_ids))]
            paper_id, _was_created = await self._get_or_create_article(
                article, user_id=first_question.get('user_id')
            )
            if not paper_id:
                self.logger.error(
                    f"Failed to get/create paper for '{article.title}', skipping"
                )
                continue

            # Process each applicable question
            for question_id in applicable_question_ids:
                question = question_by_id[question_id]

                # Filter by date boundaries (if specified)
                if not self._article_within_date_range(article, question):
                    continue

                # Check if already scored above threshold
                existing_score = await self._get_existing_match_score(
                    paper_id, question_id, question.get('user_id')
                )
                min_score = question.get('min_relevance_score', 0.5)

                if existing_score is not None and existing_score >= min_score:
                    self.logger.debug(
                        f"Article '{article.title}' already scored {existing_score:.3f} "
                        f"for question '{question['name']}', skipping"
                    )
                    continue

                # Score with LLM
                results[question_id]['articles_processed'] += 1

                try:
                    relevance_result = await self._calculate_relevance_score(
                        article, question
                    )

                    if relevance_result['score'] < min_score:
                        self.logger.debug(
                            f"Article '{article.title}' score {relevance_result['score']:.3f} "
                            f'below threshold {min_score}'
                        )
                        continue

                    # Store match
                    # Use first source as discovered_via_source
                    discovered_via = (
                        article_sources[0] if article_sources else 'unknown'
                    )

                    match_id = await self.match_repo.create_match(
                        paper_id=paper_id,
                        question_id=question_id,
                        relevance_score=relevance_result['score'],
                        user_id=question.get('user_id'),
                        matched_keywords=relevance_result.get('matched_keywords'),
                        discovered_via_source=discovered_via,
                    )

                    if match_id:
                        results[question_id]['articles_matched'] += 1
                        self.logger.info(
                            f"Matched article '{article.title}' to question '{question['name']}' "
                            f'(score: {relevance_result["score"]:.3f}, source: {discovered_via})'
                        )
                    else:
                        self.logger.error(f'Failed to store match for paper {paper_id}')

                except Exception as e:
                    self.logger.error(
                        f"Error scoring article '{article.title}' for question '{question['name']}': {e}",
                        exc_info=True,
                    )

        # Log summary
        for question_id, result in results.items():
            question = question_by_id[question_id]
            self.logger.info(
                f"Question '{question['name']}': processed {result['articles_processed']}, "
                f'matched {result["articles_matched"]}'
            )

        return results

    def _article_within_date_range(
        self, article: ScrapedArticleMetadata, question: dict[str, Any]
    ) -> bool:
        """Check if article publication date falls within question's date range."""
        if not article.publication_date:
            # No date available - allow through (better to score than miss)
            return True

        pub_date = article.publication_date
        if isinstance(pub_date, str):
            try:
                from dateutil import parser as dateutil_parser

                pub_date = dateutil_parser.parse(pub_date).date()
            except Exception:
                return True  # Can't parse, allow through

        # Check start boundary
        date_start = question.get('date_filter_start')
        if date_start:
            try:
                if isinstance(date_start, str):
                    from dateutil import parser as dateutil_parser

                    date_start = dateutil_parser.parse(date_start).date()
                if pub_date < date_start:
                    return False
            except Exception:
                pass

        # Check end boundary
        date_end = question.get('date_filter_end')
        if date_end:
            try:
                if isinstance(date_end, str):
                    from dateutil import parser as dateutil_parser

                    date_end = dateutil_parser.parse(date_end).date()
                if pub_date > date_end:
                    return False
            except Exception:
                pass

        return True

    async def _get_existing_match_score(
        self, paper_id: UUID, question_id: UUID, user_id: str | None = None
    ) -> float | None:
        """Get existing match score if it exists."""
        if user_id:
            query = """
                SELECT relevance_score
                FROM research_question_matches
                WHERE paper_id = $1 AND question_id = $2 AND user_id = $3
            """
            score = await self.postgres_service.fetchval(
                query, paper_id, question_id, user_id
            )
        else:
            query = """
                SELECT relevance_score
                FROM research_question_matches
                WHERE paper_id = $1 AND question_id = $2
            """
            score = await self.postgres_service.fetchval(query, paper_id, question_id)
        return score

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

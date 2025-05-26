"""
Scrape filter for evaluating article metadata before PDF download.

This module provides functionality to filter scraped article metadata
and decide whether to download PDFs based on research query criteria.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from jinja2 import Environment, FileSystemLoader
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from thoth.ingestion.agent import ResearchAssistantAgent
from thoth.utilities.config import get_config
from thoth.utilities.models import (
    FilterLogEntry,
    PreDownloadEvaluationResponse,
    ScrapedArticleMetadata,
)
from thoth.utilities.openrouter import OpenRouterClient


class ScrapeFilterError(Exception):
    """Exception raised for errors in the scrape filtering process."""

    pass


class ScrapeFilter:
    """
    Filter for evaluating scraped article metadata before PDF download.

    This class evaluates scraped article metadata against research queries
    and decides whether to download PDFs. It also manages logging of all
    filtering decisions.
    """

    def __init__(
        self,
        agent: ResearchAssistantAgent | None = None,
        model: str | None = None,
        max_output_tokens: int | None = None,
        max_context_length: int | None = None,
        openrouter_api_key: str | None = None,
        prompts_dir: str | Path | None = None,
        agent_storage_dir: str | Path | None = None,
        log_file: str | Path | None = None,
        model_kwargs: dict[str, Any] | None = None,
    ):
        """
        Initialize the Scrape Filter.

        Args:
            agent: Research assistant agent instance (creates new if None).
            model: The model to use for filtering (defaults to config).
            max_output_tokens: Maximum output tokens for the model (defaults to config).
            max_context_length: Maximum context length for the model (defaults to
                config).
            openrouter_api_key: The OpenRouter API key (optional, uses config if not
                provided).
            prompts_dir: Directory containing Jinja2 prompt templates (defaults to
                config).
            agent_storage_dir: Directory for storing downloaded PDFs (defaults to
                config).
            log_file: Path to log file for filtering decisions (defaults to
                agent_storage_dir/filter.log).
            model_kwargs: Additional keyword arguments for the model.
        """
        self.config = get_config()
        self.agent = agent or ResearchAssistantAgent()

        # Set up model configuration for filtering
        self.model = model or self.config.scrape_filter_llm_config.model
        self.max_output_tokens = (
            max_output_tokens or self.config.scrape_filter_llm_config.max_output_tokens
        )
        self.max_context_length = (
            max_context_length
            or self.config.scrape_filter_llm_config.max_context_length
        )
        self.model_kwargs = (
            model_kwargs
            or self.config.scrape_filter_llm_config.model_settings.model_dump()
        )

        self.agent_storage_dir = Path(
            agent_storage_dir or self.config.agent_storage_dir
        )

        # Set up prompts directory
        self.prompts_dir = (
            Path(prompts_dir or self.config.prompts_dir) / (self.model).split('/')[0]
        )

        # Create storage directory structure
        self.agent_storage_dir.mkdir(parents=True, exist_ok=True)
        (self.agent_storage_dir / 'pdfs').mkdir(exist_ok=True)

        # Set up log file
        self.log_file = Path(log_file or (self.agent_storage_dir / 'filter.log'))
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize the LLM for filtering
        self.llm = OpenRouterClient(
            api_key=openrouter_api_key or self.config.api_keys.openrouter_key,
            model=self.model,
            **self.model_kwargs,
        )

        # Create structured LLM for pre-download evaluation
        self.pre_download_llm = self.llm.with_structured_output(
            PreDownloadEvaluationResponse,
            include_raw=False,
            method='json_schema',
        )

        # Initialize Jinja environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.prompts_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Load the pre-download evaluation prompt
        self.pre_download_prompt = self._create_prompt_from_template(
            'evaluate_scraped_metadata.j2'
        )

        # Build evaluation chain
        self.pre_download_chain = self.pre_download_prompt | self.pre_download_llm

        logger.info(f'Scrape filter initialized with storage: {self.agent_storage_dir}')
        logger.info(f'Scrape filter using model: {self.model}')
        logger.info(f'Max output tokens: {self.max_output_tokens}')
        logger.info(f'Max context length: {self.max_context_length}')
        logger.info(f'Filter log file: {self.log_file}')

    def _create_prompt_from_template(self, template_name: str) -> ChatPromptTemplate:
        """
        Create a ChatPromptTemplate from a Jinja2 template file.

        Args:
            template_name: Name of the template file (e.g.,
                "evaluate_scraped_metadata.j2").

        Returns:
            ChatPromptTemplate: The prompt template for use in LangChain.

        Raises:
            FileNotFoundError: If the template file doesn't exist.
        """
        try:
            template_source, _filename, _uptodate = self.jinja_env.loader.get_source(
                self.jinja_env, template_name
            )
            return ChatPromptTemplate.from_template(
                template_source, template_format='jinja2'
            )
        except Exception as e:
            logger.error(f'Failed to load template {template_name}: {e}')
            raise FileNotFoundError(f'Template {template_name} not found') from e

    def evaluate_scraped_article(
        self,
        metadata: ScrapedArticleMetadata,
        query_names: list[str] | None = None,
    ) -> PreDownloadEvaluationResponse:
        """
        Evaluate scraped article metadata against research queries.

        Args:
            metadata: The scraped article metadata to evaluate.
            query_names: Specific queries to evaluate against (defaults to all active
                queries).

        Returns:
            PreDownloadEvaluationResponse: The evaluation result with download decision.

        Raises:
            ScrapeFilterError: If the evaluation fails.

        Example:
            >>> metadata = ScrapedArticleMetadata(
            ...     title='Deep Learning for NLP',
            ...     abstract='This paper presents...',
            ...     source='arxiv',
            ... )
            >>> evaluation = scrape_filter.evaluate_scraped_article(metadata)
            >>> print(evaluation.should_download)
            True
        """
        logger.info(f'Evaluating scraped article: {metadata.title[:100]}...')

        # Get queries to evaluate against
        if query_names is None:
            query_names = self.agent.list_queries()

        if not query_names:
            logger.warning('No research queries available for evaluation')
            return PreDownloadEvaluationResponse(
                relevance_score=0.0,
                should_download=False,
                keyword_matches=[],
                topic_analysis='No research queries available',
                reasoning='No research queries configured for filtering',
                confidence=1.0,
                matching_queries=[],
            )

        # Evaluate against each query
        evaluations = []
        for query_name in query_names:
            try:
                query = self.agent.get_query(query_name)
                if not query:
                    logger.warning(f'Query {query_name} not found')
                    continue

                evaluation = self.pre_download_chain.invoke(
                    {
                        'query': query.model_dump(),
                        'metadata': metadata.model_dump(),
                    }
                )

                evaluations.append(
                    {
                        'query_name': query_name,
                        'evaluation': evaluation,
                    }
                )

                logger.debug(
                    f'Query {query_name}: score={evaluation.relevance_score}, '
                    f'should_download={evaluation.should_download}'
                )

            except Exception as e:
                logger.error(f'Error evaluating against query {query_name}: {e}')

        if not evaluations:
            logger.warning('No successful evaluations completed')
            return PreDownloadEvaluationResponse(
                relevance_score=0.0,
                should_download=False,
                keyword_matches=[],
                topic_analysis='No successful evaluations',
                reasoning='Failed to evaluate against any queries',
                confidence=0.0,
                matching_queries=[],
            )

        # Determine overall result
        overall_result = self._determine_overall_result(evaluations)
        logger.info(
            f'Evaluation completed: score={overall_result.relevance_score:.2f}, '
            f'should_download={overall_result.should_download}'
        )

        return overall_result

    def _determine_overall_result(
        self, evaluations: list[dict[str, Any]]
    ) -> PreDownloadEvaluationResponse:
        """
        Determine the overall evaluation result from individual query evaluations.

        Args:
            evaluations: List of evaluation results from different queries.

        Returns:
            PreDownloadEvaluationResponse: Overall evaluation result.
        """
        if not evaluations:
            return PreDownloadEvaluationResponse(
                relevance_score=0.0,
                should_download=False,
                keyword_matches=[],
                topic_analysis='No evaluations available',
                reasoning='No evaluations completed',
                confidence=0.0,
                matching_queries=[],
            )

        # Extract evaluation data
        download_evaluations = []
        skip_evaluations = []
        scores = []
        all_keyword_matches = set()

        for eval_data in evaluations:
            evaluation = eval_data['evaluation']
            scores.append(evaluation.relevance_score)
            all_keyword_matches.update(evaluation.keyword_matches)

            if evaluation.should_download:
                download_evaluations.append(eval_data)
            else:
                skip_evaluations.append(eval_data)

        highest_score = max(scores) if scores else 0.0
        matching_queries = [
            eval_data['query_name'] for eval_data in download_evaluations
        ]

        # Decision logic: download if any query recommends it
        if download_evaluations:
            best_evaluation = max(
                download_evaluations,
                key=lambda x: x['evaluation'].relevance_score,
            )['evaluation']

            return PreDownloadEvaluationResponse(
                relevance_score=highest_score,
                should_download=True,
                keyword_matches=list(all_keyword_matches),
                topic_analysis=best_evaluation.topic_analysis,
                reasoning=f'Recommended by {len(download_evaluations)} queries. '
                f'Best match: {best_evaluation.reasoning}',
                confidence=best_evaluation.confidence,
                matching_queries=matching_queries,
            )
        else:
            # All queries recommend skipping
            best_evaluation = max(
                skip_evaluations, key=lambda x: x['evaluation'].relevance_score
            )['evaluation']

            return PreDownloadEvaluationResponse(
                relevance_score=highest_score,
                should_download=False,
                keyword_matches=list(all_keyword_matches),
                topic_analysis=best_evaluation.topic_analysis,
                reasoning=f'Not recommended by any queries. {best_evaluation.reasoning}',
                confidence=best_evaluation.confidence,
                matching_queries=[],
            )

    def download_pdf(
        self, metadata: ScrapedArticleMetadata, timeout: int = 30
    ) -> str | None:
        """
        Download PDF for an article.

        Args:
            metadata: The article metadata containing PDF URL.
            timeout: Timeout for download request in seconds.

        Returns:
            str: Path to downloaded PDF file, or None if download failed.

        Example:
            >>> pdf_path = scrape_filter.download_pdf(metadata)
            >>> if pdf_path:
            ...     print(f'PDF downloaded to: {pdf_path}')
        """
        if not metadata.pdf_url:
            logger.warning(f'No PDF URL available for article: {metadata.title}')
            return None

        try:
            # Create a safe filename
            safe_title = ''.join(
                c for c in metadata.title if c.isalnum() or c in ' -_.'
            ).strip()
            safe_title = safe_title.replace(' ', '_')[:100]  # Limit length

            # Add DOI or ArXiv ID if available
            if metadata.doi:
                safe_title += f'_doi_{metadata.doi.replace("/", "_")}'
            elif metadata.arxiv_id:
                safe_title += f'_arxiv_{metadata.arxiv_id}'

            pdf_filename = f'{safe_title}.pdf'
            pdf_path = self.agent_storage_dir / 'pdfs' / pdf_filename

            # Ensure unique filename
            counter = 1
            while pdf_path.exists():
                name_part = pdf_filename.rsplit('.', 1)[0]
                pdf_path = (
                    self.agent_storage_dir / 'pdfs' / f'{name_part}_{counter}.pdf'
                )
                counter += 1

            # Download the PDF
            logger.info(f'Downloading PDF from: {metadata.pdf_url}')
            response = requests.get(metadata.pdf_url, timeout=timeout, stream=True)
            response.raise_for_status()

            # Save the PDF
            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f'PDF downloaded successfully: {pdf_path}')
            return str(pdf_path)

        except Exception as e:
            logger.error(f'Failed to download PDF for {metadata.title}: {e}')
            return None

    def process_scraped_article(
        self,
        metadata: ScrapedArticleMetadata,
        query_names: list[str] | None = None,
        download_pdf: bool = True,
    ) -> dict[str, Any]:
        """
        Process a scraped article through the complete filtering workflow.

        Args:
            metadata: The scraped article metadata.
            query_names: Specific queries to evaluate against (defaults to all active
                queries).
            download_pdf: Whether to download PDF if article is approved.

        Returns:
            dict: Processing result with decision, paths, and metadata.

        Example:
            >>> result = scrape_filter.process_scraped_article(metadata)
            >>> if result['decision'] == 'download':
            ...     print(f'PDF downloaded to: {result["pdf_path"]}')
        """
        timestamp = datetime.now().isoformat()
        logger.info(f'Processing scraped article: {metadata.title}')

        try:
            # Evaluate the article
            evaluation = self.evaluate_scraped_article(metadata, query_names)

            # Determine decision
            decision = 'download' if evaluation.should_download else 'skip'

            # Download PDF if approved and requested
            pdf_path = None
            pdf_downloaded = False
            error_message = None

            if decision == 'download' and download_pdf:
                pdf_path = self.download_pdf(metadata)
                pdf_downloaded = pdf_path is not None
                if not pdf_downloaded:
                    error_message = 'Failed to download PDF'

            # Create log entry
            log_entry = FilterLogEntry(
                timestamp=timestamp,
                article_metadata=metadata,
                evaluation_result=evaluation,
                decision=decision,
                queries_evaluated=query_names or self.agent.list_queries(),
                pdf_downloaded=pdf_downloaded,
                pdf_path=pdf_path,
                error_message=error_message,
            )

            # Log the decision
            self._log_decision(log_entry)

            result = {
                'decision': decision,
                'evaluation': evaluation,
                'pdf_downloaded': pdf_downloaded,
                'pdf_path': pdf_path,
                'log_entry': log_entry,
                'error_message': error_message,
            }

            logger.info(
                f'Article processing completed: {decision} '
                f'(score: {evaluation.relevance_score:.2f})'
            )
            return result

        except Exception as e:
            error_message = f'Error processing article: {e!s}'
            logger.error(error_message)

            # Log the error
            error_log_entry = FilterLogEntry(
                timestamp=timestamp,
                article_metadata=metadata,
                evaluation_result=PreDownloadEvaluationResponse(
                    relevance_score=0.0,
                    should_download=False,
                    keyword_matches=[],
                    topic_analysis='Error during evaluation',
                    reasoning=error_message,
                    confidence=0.0,
                ),
                decision='skip',
                queries_evaluated=[],
                pdf_downloaded=False,
                pdf_path=None,
                error_message=error_message,
            )

            self._log_decision(error_log_entry)

            return {
                'decision': 'skip',
                'evaluation': None,
                'pdf_downloaded': False,
                'pdf_path': None,
                'log_entry': error_log_entry,
                'error_message': error_message,
            }

    def _log_decision(self, log_entry: FilterLogEntry) -> None:
        """
        Log a filtering decision to the log file.

        Args:
            log_entry: The log entry to write.
        """
        try:
            # Create a human-readable log line
            log_line = (
                f'[{log_entry.timestamp}] '
                f'DECISION: {log_entry.decision.upper()} | '
                f'SCORE: {log_entry.evaluation_result.relevance_score:.2f} | '
                f'TITLE: {log_entry.article_metadata.title} | '
                f'AUTHORS: {", ".join(log_entry.article_metadata.authors) if log_entry.article_metadata.authors else "N/A"} | '
                f'SOURCE: {log_entry.article_metadata.source} | '
                f'QUERIES: {", ".join(log_entry.queries_evaluated)} | '
                f'MATCHES: {", ".join(log_entry.evaluation_result.keyword_matches)} | '
                f'REASONING: {log_entry.evaluation_result.reasoning}'
            )

            if log_entry.pdf_path:
                log_line += f' | PDF: {log_entry.pdf_path}'

            if log_entry.error_message:
                log_line += f' | ERROR: {log_entry.error_message}'

            # Append to log file
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')

            # Also save detailed JSON log
            json_log_file = self.log_file.with_suffix('.json')
            json_entry = log_entry.model_dump()

            # Read existing entries or create new list
            if json_log_file.exists():
                with open(json_log_file, encoding='utf-8') as f:
                    try:
                        entries = json.load(f)
                    except json.JSONDecodeError:
                        entries = []
            else:
                entries = []

            entries.append(json_entry)

            # Write back to JSON file
            with open(json_log_file, 'w', encoding='utf-8') as f:
                json.dump(entries, f, indent=2)

            logger.debug(f'Logged decision to {self.log_file}')

        except Exception as e:
            logger.error(f'Failed to log decision: {e}')

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about filtering decisions.

        Returns:
            dict: Statistics about filtering performance.

        Example:
            >>> stats = scrape_filter.get_statistics()
            >>> print(f'Download rate: {stats["download_rate"]:.2%}')
        """
        try:
            json_log_file = self.log_file.with_suffix('.json')
            if not json_log_file.exists():
                return {
                    'total_articles': 0,
                    'downloaded': 0,
                    'skipped': 0,
                    'download_rate': 0.0,
                    'average_score': 0.0,
                    'errors': 0,
                }

            with open(json_log_file, encoding='utf-8') as f:
                entries = json.load(f)

            total_articles = len(entries)
            downloaded = sum(1 for entry in entries if entry['decision'] == 'download')
            skipped = sum(1 for entry in entries if entry['decision'] == 'skip')
            errors = sum(1 for entry in entries if entry.get('error_message'))

            scores = [
                entry['evaluation_result']['relevance_score']
                for entry in entries
                if entry['evaluation_result']
            ]
            average_score = sum(scores) / len(scores) if scores else 0.0

            download_rate = downloaded / total_articles if total_articles > 0 else 0.0

            return {
                'total_articles': total_articles,
                'downloaded': downloaded,
                'skipped': skipped,
                'download_rate': download_rate,
                'average_score': average_score,
                'errors': errors,
                'available_queries': len(self.agent.list_queries()),
            }

        except Exception as e:
            logger.error(f'Failed to get statistics: {e}')
            return {
                'total_articles': 0,
                'downloaded': 0,
                'skipped': 0,
                'download_rate': 0.0,
                'average_score': 0.0,
                'errors': 1,
            }

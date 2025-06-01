"""
Streamlined article filter for the Thoth system.

This module provides a single, unified filter that:
1. Evaluates article metadata against research queries
2. Downloads PDFs for matching articles
3. Saves full reasoning for ALL decisions (download or skip)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from jinja2 import Environment, FileSystemLoader
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from thoth.ingestion.agent_v2.core.research_agent import ResearchAssistantAgent
from thoth.utilities.config import get_config
from thoth.utilities.models import PreDownloadEvaluationResponse, ScrapedArticleMetadata
from thoth.utilities.openrouter import OpenRouterClient


class FilterError(Exception):
    """Exception raised for errors in the filtering process."""

    pass


class Filter:
    """
    Unified filter for evaluating articles and managing downloads.

    This class:
    - Evaluates scraped metadata against research queries
    - Downloads PDFs for articles that match
    - Saves detailed evaluation results for ALL articles
    - Maintains comprehensive logs
    """

    def __init__(
        self,
        agent: ResearchAssistantAgent | None = None,
        model: str | None = None,
        max_output_tokens: int | None = None,
        max_context_length: int | None = None,
        openrouter_api_key: str | None = None,
        prompts_dir: str | Path | None = None,
        storage_dir: str | Path | None = None,
        model_kwargs: dict[str, Any] | None = None,
    ):
        """
        Initialize the Filter.

        Args:
            agent: Research assistant agent instance (creates new if None).
            model: The model to use for filtering (defaults to config).
            max_output_tokens: Maximum output tokens for the model.
            max_context_length: Maximum context length for the model.
            openrouter_api_key: The OpenRouter API key.
            prompts_dir: Directory containing Jinja2 prompt templates.
            storage_dir: Directory for storing all outputs.
            model_kwargs: Additional keyword arguments for the model.
        """
        self.config = get_config()
        self.agent = agent  # Will be None if not provided
        self.queries_dir = Path(self.config.queries_dir)
        self.queries_dir.mkdir(parents=True, exist_ok=True)

        # Set up model configuration
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

        # Set up directories
        self.storage_dir = Path(storage_dir or self.config.agent_storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.pdfs_dir = self.storage_dir / 'pdfs'
        self.evaluations_dir = self.storage_dir / 'evaluations'
        self.pdfs_dir.mkdir(exist_ok=True)
        self.evaluations_dir.mkdir(exist_ok=True)

        # Set up log files
        self.log_file = self.storage_dir / 'filter.log'
        self.json_log_file = self.storage_dir / 'filter.json'

        # Set up prompts directory
        self.prompts_dir = (
            Path(prompts_dir or self.config.prompts_dir) / self.model.split('/')[0]
        )

        # Initialize the LLM
        self.llm = OpenRouterClient(
            api_key=openrouter_api_key or self.config.api_keys.openrouter_key,
            model=self.model,
            **self.model_kwargs,
        )

        # Create structured LLM for evaluation
        self.evaluation_llm = self.llm.with_structured_output(
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

        # Load evaluation prompt
        self.evaluation_prompt = self._create_prompt_from_template(
            'evaluate_scraped_metadata.j2'
        )

        # Build evaluation chain
        self.evaluation_chain = self.evaluation_prompt | self.evaluation_llm

        logger.info(f'Filter initialized with storage: {self.storage_dir}')
        logger.info(f'Using model: {self.model}')

    def _list_queries(self) -> list[str]:
        """List all available query names from the queries directory."""
        try:
            query_files = list(self.queries_dir.glob('*.json'))
            return [f.stem for f in query_files]
        except Exception as e:
            logger.error(f'Error listing queries: {e}')
            return []

    def _get_query(self, query_name: str):
        """Load a research query from file."""
        from thoth.utilities.models import ResearchQuery

        query_path = self.queries_dir / f'{query_name}.json'
        if not query_path.exists():
            return None

        try:
            with open(query_path, encoding='utf-8') as f:
                query_data = json.load(f)
            return ResearchQuery(**query_data)
        except Exception as e:
            logger.error(f'Failed to load query {query_name}: {e}')
            return None

    def _create_prompt_from_template(self, template_name: str) -> ChatPromptTemplate:
        """Create a ChatPromptTemplate from a Jinja2 template file."""
        try:
            template_source, _, _ = self.jinja_env.loader.get_source(
                self.jinja_env, template_name
            )
            return ChatPromptTemplate.from_template(
                template_source, template_format='jinja2'
            )
        except Exception as e:
            logger.error(f'Failed to load template {template_name}: {e}')
            raise FileNotFoundError(f'Template {template_name} not found') from e

    def process_article(
        self,
        metadata: ScrapedArticleMetadata,
        query_names: list[str] | None = None,
        download_pdf: bool = True,
    ) -> dict[str, Any]:
        """
        Process an article through the complete filtering workflow.

        This method:
        1. Evaluates the article metadata against research queries
        2. Downloads the PDF if it matches any query
        3. Saves full evaluation details for ALL articles
        4. Logs the decision

        Args:
            metadata: The scraped article metadata.
            query_names: Specific queries to evaluate against (defaults to all).
            download_pdf: Whether to download PDF if article matches.

        Returns:
            dict: Complete processing result with decision, evaluation, and paths.
        """
        timestamp = datetime.now().isoformat()
        logger.info(f'Processing article: {metadata.title}')

        try:
            # Get queries to evaluate against
            if query_names is None:
                query_names = (
                    self._list_queries()
                    if not self.agent
                    else self.agent.list_queries()
                )

            if not query_names:
                logger.warning('No research queries available for evaluation')
                # Still save evaluation even with no queries
                evaluation = PreDownloadEvaluationResponse(
                    relevance_score=0.0,
                    should_download=False,
                    keyword_matches=[],
                    topic_analysis='No research queries available',
                    reasoning='No research queries configured for filtering',
                    confidence=1.0,
                    matching_queries=[],
                )
                decision = 'skip'
            else:
                # Evaluate against all queries
                all_evaluations = []
                for query_name in query_names:
                    try:
                        query = (
                            self._get_query(query_name)
                            if not self.agent
                            else self.agent.get_query(query_name)
                        )
                        if not query:
                            logger.warning(f'Query {query_name} not found')
                            continue

                        eval_result = self.evaluation_chain.invoke(
                            {
                                'query': query.model_dump(),
                                'metadata': metadata.model_dump(),
                            }
                        )

                        all_evaluations.append(
                            {
                                'query_name': query_name,
                                'query': query.model_dump(),
                                'evaluation': eval_result,
                            }
                        )

                    except Exception as e:
                        logger.error(
                            f'Error evaluating against query {query_name}: {e}'
                        )

                # Determine overall decision
                evaluation, decision = self._determine_overall_decision(all_evaluations)

            # Download PDF if approved
            pdf_path = None
            pdf_downloaded = False
            error_message = None

            if decision == 'download' and download_pdf:
                pdf_path = self._download_pdf(metadata)
                pdf_downloaded = pdf_path is not None
                if not pdf_downloaded:
                    error_message = 'Failed to download PDF'

            # Save full evaluation details (for ALL articles)
            evaluation_path = self._save_detailed_evaluation(
                metadata=metadata,
                decision=decision,
                evaluation=evaluation,
                all_evaluations=all_evaluations if query_names else [],
                pdf_path=pdf_path,
                error_message=error_message,
                timestamp=timestamp,
            )

            # Log decision
            self._log_decision(
                metadata=metadata,
                decision=decision,
                evaluation=evaluation,
                pdf_path=pdf_path,
                error_message=error_message,
                timestamp=timestamp,
            )

            result = {
                'decision': decision,
                'evaluation': evaluation,
                'pdf_downloaded': pdf_downloaded,
                'pdf_path': pdf_path,
                'evaluation_path': evaluation_path,
                'error_message': error_message,
                'timestamp': timestamp,
            }

            logger.info(
                f'Article processing completed: {decision} '
                f'(score: {evaluation.relevance_score:.2f})'
            )

            return result

        except Exception as e:
            error_message = f'Error processing article: {e!s}'
            logger.error(error_message)

            # Save error evaluation
            error_evaluation = PreDownloadEvaluationResponse(
                relevance_score=0.0,
                should_download=False,
                keyword_matches=[],
                topic_analysis='Error during evaluation',
                reasoning=error_message,
                confidence=0.0,
            )

            evaluation_path = self._save_detailed_evaluation(
                metadata=metadata,
                decision='error',
                evaluation=error_evaluation,
                all_evaluations=[],
                pdf_path=None,
                error_message=error_message,
                timestamp=timestamp,
            )

            return {
                'decision': 'error',
                'evaluation': error_evaluation,
                'pdf_downloaded': False,
                'pdf_path': None,
                'evaluation_path': evaluation_path,
                'error_message': error_message,
                'timestamp': timestamp,
            }

    def _determine_overall_decision(
        self, all_evaluations: list[dict[str, Any]]
    ) -> tuple[PreDownloadEvaluationResponse, str]:
        """
        Determine the overall evaluation and decision from individual query evaluations.

        Returns:
            tuple: (overall_evaluation, decision)
        """
        if not all_evaluations:
            return PreDownloadEvaluationResponse(
                relevance_score=0.0,
                should_download=False,
                keyword_matches=[],
                topic_analysis='No evaluations completed',
                reasoning='No queries were successfully evaluated',
                confidence=0.0,
                matching_queries=[],
            ), 'skip'

        # Collect data from all evaluations
        download_evaluations = []
        all_keyword_matches = set()
        all_scores = []

        for eval_data in all_evaluations:
            evaluation = eval_data['evaluation']
            all_scores.append(evaluation.relevance_score)
            all_keyword_matches.update(evaluation.keyword_matches)

            if evaluation.should_download:
                download_evaluations.append(eval_data)

        highest_score = max(all_scores)
        matching_queries = [
            eval_data['query_name'] for eval_data in download_evaluations
        ]

        # Decision: download if ANY query recommends it
        if download_evaluations:
            best_eval = max(
                download_evaluations, key=lambda x: x['evaluation'].relevance_score
            )['evaluation']

            # Build comprehensive reasoning
            reasoning_parts = [
                f'Recommended by {len(download_evaluations)}/{len(all_evaluations)} queries.',
                f'Highest relevance score: {highest_score:.2f}',
                f'Matching queries: {", ".join(matching_queries)}',
                f'Best match reasoning: {best_eval.reasoning}',
            ]

            return PreDownloadEvaluationResponse(
                relevance_score=highest_score,
                should_download=True,
                keyword_matches=list(all_keyword_matches),
                topic_analysis=best_eval.topic_analysis,
                reasoning=' '.join(reasoning_parts),
                confidence=best_eval.confidence,
                matching_queries=matching_queries,
            ), 'download'
        else:
            # All queries recommend skipping
            best_eval = max(
                all_evaluations, key=lambda x: x['evaluation'].relevance_score
            )['evaluation']

            reasoning_parts = [
                f'Not recommended by any of {len(all_evaluations)} queries.',
                f'Highest relevance score: {highest_score:.2f}',
                f'Best match reasoning: {best_eval.reasoning}',
            ]

            return PreDownloadEvaluationResponse(
                relevance_score=highest_score,
                should_download=False,
                keyword_matches=list(all_keyword_matches),
                topic_analysis=best_eval.topic_analysis,
                reasoning=' '.join(reasoning_parts),
                confidence=best_eval.confidence,
                matching_queries=[],
            ), 'skip'

    def _download_pdf(self, metadata: ScrapedArticleMetadata) -> str | None:
        """Download PDF for an article."""
        if not metadata.pdf_url:
            logger.warning(f'No PDF URL available for article: {metadata.title}')
            return None

        try:
            # Create safe filename
            safe_title = ''.join(
                c for c in metadata.title if c.isalnum() or c in ' -_.'
            ).strip()
            safe_title = safe_title.replace(' ', '_')[:100]

            if metadata.doi:
                safe_title += f'_doi_{metadata.doi.replace("/", "_")}'
            elif metadata.arxiv_id:
                safe_title += f'_arxiv_{metadata.arxiv_id}'

            pdf_filename = f'{safe_title}.pdf'
            pdf_path = self.pdfs_dir / pdf_filename

            # Ensure unique filename
            counter = 1
            while pdf_path.exists():
                name_part = pdf_filename.rsplit('.', 1)[0]
                pdf_path = self.pdfs_dir / f'{name_part}_{counter}.pdf'
                counter += 1

            # Download the PDF
            logger.info(f'Downloading PDF from: {metadata.pdf_url}')
            response = requests.get(metadata.pdf_url, timeout=30, stream=True)
            response.raise_for_status()

            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f'PDF downloaded successfully: {pdf_path}')
            return str(pdf_path)

        except Exception as e:
            logger.error(f'Failed to download PDF for {metadata.title}: {e}')
            return None

    def _save_detailed_evaluation(
        self,
        metadata: ScrapedArticleMetadata,
        decision: str,
        evaluation: PreDownloadEvaluationResponse,
        all_evaluations: list[dict[str, Any]],
        pdf_path: str | None,
        error_message: str | None,
        timestamp: str,
    ) -> Path:
        """
        Save detailed evaluation results for analysis and debugging.

        This saves ALL information about the evaluation process, including
        the full reasoning from each query evaluation.
        """
        # Create unique filename
        timestamp_short = datetime.now().strftime('%Y%m%d_%H%M%S')
        title_part = (
            metadata.title[:50].replace(' ', '_') if metadata.title else 'untitled'
        )
        title_part = ''.join(c for c in title_part if c.isalnum() or c in '_-')

        eval_filename = f'{timestamp_short}_{title_part}.json'
        eval_path = self.evaluations_dir / eval_filename

        # Build comprehensive evaluation data
        evaluation_data = {
            'timestamp': timestamp,
            'decision': decision,
            'article_metadata': metadata.model_dump(),
            'overall_evaluation': evaluation.model_dump(),
            'individual_query_evaluations': [
                {
                    'query_name': eval_data['query_name'],
                    'query': eval_data['query'],
                    'evaluation': eval_data['evaluation'].model_dump(),
                }
                for eval_data in all_evaluations
            ],
            'pdf_path': pdf_path,
            'error_message': error_message,
            'processing_details': {
                'queries_evaluated': len(all_evaluations),
                'queries_matched': len(evaluation.matching_queries),
                'highest_score': evaluation.relevance_score,
                'download_attempted': decision == 'download',
                'download_successful': pdf_path is not None,
            },
        }

        with open(eval_path, 'w', encoding='utf-8') as f:
            json.dump(evaluation_data, f, indent=2, ensure_ascii=False)

        logger.debug(f'Saved detailed evaluation to {eval_path}')
        return eval_path

    def _log_decision(
        self,
        metadata: ScrapedArticleMetadata,
        decision: str,
        evaluation: PreDownloadEvaluationResponse,
        pdf_path: str | None,
        error_message: str | None,
        timestamp: str,
    ) -> None:
        """Log the filtering decision to log files."""
        # Human-readable log line
        log_line = (
            f'[{timestamp}] '
            f'DECISION: {decision.upper()} | '
            f'SCORE: {evaluation.relevance_score:.2f} | '
            f'TITLE: {metadata.title} | '
            f'AUTHORS: {", ".join(metadata.authors) if metadata.authors else "N/A"} | '
            f'SOURCE: {metadata.source} | '
            f'MATCHES: {", ".join(evaluation.keyword_matches)} | '
            f'REASONING: {evaluation.reasoning}'
        )

        if pdf_path:
            log_line += f' | PDF: {pdf_path}'

        if error_message:
            log_line += f' | ERROR: {error_message}'

        # Append to text log
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')

        # Append to JSON log
        json_entry = {
            'timestamp': timestamp,
            'decision': decision,
            'article_metadata': metadata.model_dump(),
            'evaluation_result': evaluation.model_dump(),
            'pdf_path': pdf_path,
            'error_message': error_message,
        }

        # Read existing entries or create new list
        if self.json_log_file.exists():
            with open(self.json_log_file, encoding='utf-8') as f:
                try:
                    entries = json.load(f)
                except json.JSONDecodeError:
                    entries = []
        else:
            entries = []

        entries.append(json_entry)

        # Write back to JSON file
        with open(self.json_log_file, 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=2)

        logger.debug('Logged decision to filter.log and filter.json')

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about filtering decisions."""
        try:
            if not self.json_log_file.exists():
                return {
                    'total_articles': 0,
                    'downloaded': 0,
                    'skipped': 0,
                    'errors': 0,
                    'download_rate': 0.0,
                    'average_score': 0.0,
                    'available_queries': len(
                        self._list_queries()
                        if not self.agent
                        else self.agent.list_queries()
                    ),
                }

            with open(self.json_log_file, encoding='utf-8') as f:
                entries = json.load(f)

            total = len(entries)
            downloaded = sum(1 for e in entries if e['decision'] == 'download')
            skipped = sum(1 for e in entries if e['decision'] == 'skip')
            errors = sum(1 for e in entries if e['decision'] == 'error')

            scores = [
                e['evaluation_result']['relevance_score']
                for e in entries
                if e['evaluation_result']
            ]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            return {
                'total_articles': total,
                'downloaded': downloaded,
                'skipped': skipped,
                'errors': errors,
                'download_rate': downloaded / total if total > 0 else 0.0,
                'average_score': avg_score,
                'available_queries': len(
                    self._list_queries()
                    if not self.agent
                    else self.agent.list_queries()
                ),
            }

        except Exception as e:
            logger.error(f'Failed to get statistics: {e}')
            return {
                'total_articles': 0,
                'downloaded': 0,
                'skipped': 0,
                'errors': 0,
                'download_rate': 0.0,
                'average_score': 0.0,
                'available_queries': 0,
            }

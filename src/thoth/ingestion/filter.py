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
from loguru import logger

from thoth.ingestion.agent_adapter import AgentAdapter
from thoth.services.service_manager import ServiceManager
from thoth.utilities.config import get_config
from thoth.utilities.models import PreDownloadEvaluationResponse, ScrapedArticleMetadata


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
        service_manager: ServiceManager | None = None,
        storage_dir: str | Path | None = None,
    ):
        """
        Initialize the Filter.

        Args:
            service_manager: ServiceManager instance (creates new if None)
            storage_dir: Directory for storing all outputs
        """
        self.config = get_config()

        # Initialize service manager
        self.service_manager = service_manager or ServiceManager(self.config)
        self.service_manager.initialize()

        # Create adapter for backward compatibility
        self.agent = AgentAdapter(self.service_manager)

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

        logger.info(f'Filter initialized with storage: {self.storage_dir}')
        logger.info('Using service layer architecture')

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
                query_names = self.service_manager.query.list_queries()

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
                queries = []
                for query_name in query_names:
                    query = self.service_manager.query.get_query(query_name)
                    if query:
                        queries.append(query)
                    else:
                        logger.warning(f'Query {query_name} not found')

                # Use ArticleService for evaluation
                evaluation = self.service_manager.article.evaluate_for_download(
                    metadata, queries
                )
                decision = 'download' if evaluation.should_download else 'skip'

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
        pdf_path: str | None,
        error_message: str | None,
        timestamp: str,
    ) -> Path:
        """
        Save detailed evaluation results for analysis and debugging.

        This saves ALL information about the evaluation process.
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
            'pdf_path': pdf_path,
            'error_message': error_message,
            'processing_details': {
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
                    'available_queries': len(self.service_manager.query.list_queries()),
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
                'available_queries': len(self.service_manager.query.list_queries()),
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

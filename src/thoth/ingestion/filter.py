"""
Article filtering utilities for the Research Assistant.

This module provides utilities for filtering articles based on research queries
and managing the storage of articles that meet the criteria.
"""

import json
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.ingestion.agent import ResearchAssistantAgent
from thoth.utilities.config import get_config
from thoth.utilities.models import AnalysisResponse


class ArticleFilter:
    """
    Article filter that evaluates articles against research queries.

    This class provides functionality to automatically filter articles based on
    research queries created by the Research Assistant Agent, and manage the
    storage of articles that meet the criteria.
    """

    def __init__(
        self,
        agent: ResearchAssistantAgent | None = None,
        agent_storage_dir: str | Path | None = None,
    ):
        """
        Initialize the Article Filter.

        Args:
            agent: Research assistant agent instance (creates new if None).
            agent_storage_dir: Directory for storing filtered articles (defaults to
                config).
        """
        self.config = get_config()
        self.agent = agent or ResearchAssistantAgent()
        self.agent_storage_dir = Path(
            agent_storage_dir or self.config.agent_storage_dir
        )

        # Create storage directory structure
        self.agent_storage_dir.mkdir(parents=True, exist_ok=True)
        (self.agent_storage_dir / 'approved').mkdir(exist_ok=True)
        (self.agent_storage_dir / 'rejected').mkdir(exist_ok=True)
        (self.agent_storage_dir / 'review').mkdir(exist_ok=True)
        (self.agent_storage_dir / 'evaluations').mkdir(exist_ok=True)

        logger.info(
            f'Article filter initialized with storage: {self.agent_storage_dir}'
        )

    def filter_article(
        self,
        article: AnalysisResponse,
        article_path: Path | None = None,
        query_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Filter an article against research queries and store it appropriately.

        Args:
            article: The article analysis to filter.
            article_path: Path to the original article file (for copying).
            query_names: Specific queries to evaluate against (defaults to all active
                queries).

        Returns:
            dict: Summary of evaluation results and actions taken.

        Example:
            >>> filter_result = article_filter.filter_article(
            ...     article=analysis_response,
            ...     article_path=Path('path/to/article.md'),
            ...     query_names=['deep_learning_nlp'],
            ... )
            >>> print(filter_result['overall_recommendation'])
            'keep'
        """
        logger.info('Filtering article against research queries...')

        # Get queries to evaluate against
        if query_names is None:
            query_names = self.agent.list_queries()

        if not query_names:
            logger.warning('No research queries available for filtering')
            return {
                'overall_recommendation': 'review',
                'reason': 'No research queries available',
                'evaluations': [],
                'stored_path': None,
            }

        # Evaluate against each query
        evaluations = []
        for query_name in query_names:
            try:
                evaluation = self.agent.evaluate_article(article, query_name)
                if evaluation:
                    evaluations.append(
                        {
                            'query_name': query_name,
                            'evaluation': evaluation,
                        }
                    )
                    logger.debug(
                        f'Query {query_name}: score={evaluation.relevance_score}, '
                        f'recommendation={evaluation.recommendation}'
                    )
            except Exception as e:
                logger.error(f'Error evaluating against query {query_name}: {e}')

        if not evaluations:
            logger.warning('No successful evaluations completed')
            return {
                'overall_recommendation': 'review',
                'reason': 'No successful evaluations',
                'evaluations': [],
                'stored_path': None,
            }

        # Determine overall recommendation
        overall_result = self._determine_overall_recommendation(evaluations)

        # Store the article based on recommendation
        stored_path = None
        if article_path and article_path.exists():
            stored_path = self._store_article(
                article_path, overall_result['recommendation'], evaluations
            )

        # Save evaluation results
        self._save_evaluation_results(article, evaluations, overall_result)

        result = {
            'overall_recommendation': overall_result['recommendation'],
            'reason': overall_result['reason'],
            'evaluations': evaluations,
            'stored_path': stored_path,
            'highest_score': overall_result.get('highest_score'),
            'matching_queries': overall_result.get('matching_queries', []),
        }

        logger.info(
            f'Article filtering completed: {result["overall_recommendation"]} '
            f'(score: {result.get("highest_score", "N/A")})'
        )
        return result

    def _determine_overall_recommendation(
        self, evaluations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Determine the overall recommendation based on individual query evaluations.

        Args:
            evaluations: List of evaluation results from different queries.

        Returns:
            dict: Overall recommendation with reasoning.
        """
        if not evaluations:
            return {'recommendation': 'review', 'reason': 'No evaluations available'}

        # Extract evaluation data
        keep_evaluations = []
        review_evaluations = []
        reject_evaluations = []
        scores = []

        for eval_data in evaluations:
            evaluation = eval_data['evaluation']
            scores.append(evaluation.relevance_score)

            if evaluation.recommendation == 'keep':
                keep_evaluations.append(eval_data)
            elif evaluation.recommendation == 'review':
                review_evaluations.append(eval_data)
            else:
                reject_evaluations.append(eval_data)

        highest_score = max(scores) if scores else 0.0
        matching_queries = [
            eval_data['query_name']
            for eval_data in keep_evaluations
            if eval_data['evaluation'].meets_criteria
        ]

        # Decision logic
        if keep_evaluations:
            # At least one query recommends keeping
            return {
                'recommendation': 'keep',
                'reason': f'Matches {len(keep_evaluations)} research queries',
                'highest_score': highest_score,
                'matching_queries': matching_queries,
            }
        elif review_evaluations:
            # Some queries suggest review but none recommend keeping
            return {
                'recommendation': 'review',
                'reason': f'Requires review for {len(review_evaluations)} queries',
                'highest_score': highest_score,
                'matching_queries': matching_queries,
            }
        else:
            # All queries recommend rejection
            return {
                'recommendation': 'reject',
                'reason': 'Does not match any research criteria',
                'highest_score': highest_score,
                'matching_queries': matching_queries,
            }

    def _store_article(
        self,
        article_path: Path,
        recommendation: str,
        evaluations: list[dict[str, Any]],
    ) -> Path:
        """
        Store the article in the appropriate directory based on recommendation.

        Args:
            article_path: Path to the original article file.
            recommendation: Overall recommendation (keep/reject/review).
            evaluations: List of evaluation results.

        Returns:
            Path: Path where the article was stored.
        """
        # Determine target directory
        target_dir = self.agent_storage_dir / recommendation

        # Create a unique filename
        base_name = article_path.stem
        extension = article_path.suffix
        counter = 1
        target_path = target_dir / f'{base_name}{extension}'

        while target_path.exists():
            target_path = target_dir / f'{base_name}_{counter}{extension}'
            counter += 1

        try:
            # Copy the article file
            shutil.copy2(article_path, target_path)

            # Create a metadata file with evaluation results
            metadata_path = target_path.with_suffix('.evaluation.json')
            metadata = {
                'original_path': str(article_path),
                'recommendation': recommendation,
                'evaluations': [
                    {
                        'query_name': eval_data['query_name'],
                        'evaluation': eval_data['evaluation'].model_dump(),
                    }
                    for eval_data in evaluations
                ],
                'stored_at': target_path.name,
            }

            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            logger.info(f'Stored article at {target_path}')
            return target_path

        except Exception as e:
            logger.error(f'Failed to store article: {e}')
            raise

    def _save_evaluation_results(
        self,
        article: AnalysisResponse,
        evaluations: list[dict[str, Any]],
        overall_result: dict[str, Any],
    ) -> None:
        """
        Save detailed evaluation results for analysis and improvement.

        Args:
            article: The article that was evaluated.
            evaluations: List of evaluation results.
            overall_result: Overall recommendation result.
        """
        try:
            # Create a unique filename based on article title or timestamp
            import datetime

            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            title_part = (
                article.title[:50].replace(' ', '_') if article.title else 'untitled'
            )
            # Clean the title part for filename use
            title_part = ''.join(c for c in title_part if c.isalnum() or c in '_-')

            eval_filename = f'{timestamp}_{title_part}.json'
            eval_path = self.agent_storage_dir / 'evaluations' / eval_filename

            evaluation_data = {
                'timestamp': timestamp,
                'article': {
                    'title': getattr(article, 'title', None),
                    'abstract': getattr(article, 'abstract', None),
                    'tags': getattr(article, 'tags', None),
                    'key_points': getattr(article, 'key_points', None),
                },
                'evaluations': [
                    {
                        'query_name': eval_data['query_name'],
                        'evaluation': eval_data['evaluation'].model_dump(),
                    }
                    for eval_data in evaluations
                ],
                'overall_result': overall_result,
            }

            with open(eval_path, 'w', encoding='utf-8') as f:
                json.dump(evaluation_data, f, indent=2)

            logger.debug(f'Saved evaluation results to {eval_path}')

        except Exception as e:
            logger.error(f'Failed to save evaluation results: {e}')

    def get_filtered_articles(self, category: str = 'approved') -> list[dict[str, Any]]:
        """
        Get a list of articles in a specific category.

        Args:
            category: Category to retrieve ('approved', 'rejected', 'review').

        Returns:
            list: List of article information with metadata.

        Example:
            >>> approved_articles = article_filter.get_filtered_articles('approved')
            >>> for article in approved_articles:
            ...     print(f'Title: {article["title"]}')
        """
        category_dir = self.agent_storage_dir / category
        if not category_dir.exists():
            return []

        articles = []
        for article_file in category_dir.glob('*.md'):
            metadata_file = article_file.with_suffix('.evaluation.json')
            if metadata_file.exists():
                try:
                    with open(metadata_file, encoding='utf-8') as f:
                        metadata = json.load(f)
                    articles.append(
                        {
                            'file_path': article_file,
                            'metadata': metadata,
                            'title': self._extract_title_from_file(article_file),
                        }
                    )
                except Exception as e:
                    logger.error(f'Error reading metadata for {article_file}: {e}')

        return articles

    def _extract_title_from_file(self, file_path: Path) -> str:
        """
        Extract title from a markdown file.

        Args:
            file_path: Path to the markdown file.

        Returns:
            str: Extracted title or filename if title not found.
        """
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            # Look for title in frontmatter or first heading
            lines = content.split('\n')
            for line in lines[:20]:  # Check first 20 lines
                if line.startswith('# '):
                    return line[2:].strip()
                elif line.startswith('title:'):
                    return line[6:].strip().strip('"\'')

            return file_path.stem

        except Exception:
            return file_path.stem

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about filtered articles.

        Returns:
            dict: Statistics about article filtering results.

        Example:
            >>> stats = article_filter.get_statistics()
            >>> print(f'Approved: {stats["approved_count"]}')
        """
        stats = {
            'approved_count': len(
                list((self.agent_storage_dir / 'approved').glob('*.md'))
            ),
            'rejected_count': len(
                list((self.agent_storage_dir / 'rejected').glob('*.md'))
            ),
            'review_count': len(list((self.agent_storage_dir / 'review').glob('*.md'))),
            'total_evaluations': len(
                list((self.agent_storage_dir / 'evaluations').glob('*.json'))
            ),
            'available_queries': len(self.agent.list_queries()),
        }

        stats['total_articles'] = (
            stats['approved_count'] + stats['rejected_count'] + stats['review_count']
        )

        return stats

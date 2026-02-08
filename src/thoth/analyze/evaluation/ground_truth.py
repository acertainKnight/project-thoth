"""Ground truth generation for Analysis pipeline evaluation."""

import json  # noqa: I001
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any  # noqa: F401, UP035

from loguru import logger

from thoth.utilities.schemas.analysis import AnalysisResponse
from thoth.services.postgres_service import PostgresService


@dataclass
class AnalysisGroundTruthPair:
    """
    A paper analysis with ground truth for evaluation.

    Attributes:
        paper_content: Raw markdown content of the paper
        ground_truth_analysis: Manually annotated or extracted AnalysisResponse
        paper_id: Database ID of the paper
        paper_title: Title of the paper
        content_length: Length of content in tokens
        complexity: Estimated complexity (low, medium, high)
    """

    paper_content: str
    ground_truth_analysis: AnalysisResponse
    paper_id: str
    paper_title: str
    content_length: int
    complexity: str = 'medium'  # low, medium, high
    expected_strategy: str | None = None  # direct, map_reduce, refine


class AnalysisGroundTruthGenerator:
    """
    Generate ground truth test cases for Analysis pipeline evaluation.

    Creates paper analysis test cases with known correct extractions
    for evaluating analysis quality and extraction accuracy.
    """

    def __init__(self, postgres_service: PostgresService):
        """
        Initialize ground truth generator.

        Args:
            postgres_service: PostgreSQL service for accessing papers
        """
        self.postgres = postgres_service

    async def generate_from_database(
        self,
        num_samples: int = 50,
        complexity_distribution: Dict[str, float] | None = None,  # noqa: UP006
    ) -> List[AnalysisGroundTruthPair]:  # noqa: UP006
        """
        Generate ground truth analysis pairs from database papers.

        Strategy:
        1. Query papers with known metadata (title, authors, year, abstract)
        2. Create AnalysisResponse with known fields as ground truth
        3. Use paper content for analysis
        4. Vary content length for testing different strategies

        Args:
            num_samples: Number of test cases to generate
            complexity_distribution: Distribution of low/medium/high complexity
                                    e.g., {"low": 0.3, "medium": 0.5, "high": 0.2}

        Returns:
            List of AnalysisGroundTruthPair objects
        """
        if complexity_distribution is None:
            complexity_distribution = {'low': 0.3, 'medium': 0.5, 'high': 0.2}

        logger.info(f'Generating {num_samples} ground truth analysis pairs...')

        # Calculate samples per complexity
        low_count = int(num_samples * complexity_distribution.get('low', 0.3))
        medium_count = int(num_samples * complexity_distribution.get('medium', 0.5))
        high_count = num_samples - low_count - medium_count

        pairs = []

        # Generate low complexity (short papers, direct strategy)
        if low_count > 0:
            low_pairs = await self._generate_low_complexity(low_count)
            pairs.extend(low_pairs)

        # Generate medium complexity (medium papers, map-reduce strategy)
        if medium_count > 0:
            medium_pairs = await self._generate_medium_complexity(medium_count)
            pairs.extend(medium_pairs)

        # Generate high complexity (long papers, refine strategy)
        if high_count > 0:
            high_pairs = await self._generate_high_complexity(high_count)
            pairs.extend(high_pairs)

        logger.info(f'Generated {len(pairs)} ground truth analysis pairs')
        return pairs

    async def _generate_low_complexity(
        self, count: int
    ) -> List[AnalysisGroundTruthPair]:  # noqa: UP006
        """Generate low complexity test cases (short abstracts, direct strategy)."""
        pairs = []

        query = """
            SELECT id, title, authors, year, doi, journal, abstract
            FROM papers
            WHERE title IS NOT NULL
                AND abstract IS NOT NULL
                AND LENGTH(abstract) BETWEEN 100 AND 500
            ORDER BY RANDOM()
            LIMIT $1
        """

        try:
            papers = await self.postgres.pool.fetch(query, count)

            for paper in papers:
                # Parse authors
                authors_raw = paper['authors']
                if isinstance(authors_raw, str):
                    authors = json.loads(authors_raw) if authors_raw else []
                else:
                    authors = authors_raw or []

                # Create ground truth analysis with known fields
                ground_truth = AnalysisResponse(
                    title=paper['title'],
                    authors=authors,
                    year=paper['year'],
                    doi=paper['doi'],
                    journal=paper['journal'],
                    abstract=paper['abstract'],
                    # Other fields will be None (to be extracted)
                )

                # Use abstract as paper content
                paper_content = f'# {paper["title"]}\n\n{paper["abstract"]}'

                pair = AnalysisGroundTruthPair(
                    paper_content=paper_content,
                    ground_truth_analysis=ground_truth,
                    paper_id=str(paper['id']),
                    paper_title=paper['title'],
                    content_length=len(paper_content) // 4,  # Rough token estimate
                    complexity='low',
                    expected_strategy='direct',
                )
                pairs.append(pair)

        except Exception as e:
            logger.error(f'Error generating low complexity pairs: {e}')

        return pairs

    async def _generate_medium_complexity(
        self, count: int
    ) -> List[AnalysisGroundTruthPair]:  # noqa: UP006
        """Generate medium complexity test cases (medium-length content, map-reduce)."""
        pairs = []

        query = """
            SELECT id, title, authors, year, doi, journal, abstract
            FROM papers
            WHERE title IS NOT NULL
                AND abstract IS NOT NULL
                AND LENGTH(abstract) BETWEEN 500 AND 2000
            ORDER BY RANDOM()
            LIMIT $1
        """

        try:
            papers = await self.postgres.pool.fetch(query, count)

            for paper in papers:
                # Parse authors
                authors_raw = paper['authors']
                if isinstance(authors_raw, str):
                    authors = json.loads(authors_raw) if authors_raw else []
                else:
                    authors = authors_raw or []

                # Create ground truth with known metadata
                ground_truth = AnalysisResponse(
                    title=paper['title'],
                    authors=authors,
                    year=paper['year'],
                    doi=paper['doi'],
                    journal=paper['journal'],
                    abstract=paper['abstract'],
                )

                # Create longer content by repeating abstract sections
                paper_content = (
                    f'# {paper["title"]}\n\n## Abstract\n{paper["abstract"]}\n\n'
                )
                paper_content += '## Introduction\n' + paper['abstract'][:500] + '\n\n'
                paper_content += '## Methods\n' + paper['abstract'][500:] + '\n\n'

                pair = AnalysisGroundTruthPair(
                    paper_content=paper_content,
                    ground_truth_analysis=ground_truth,
                    paper_id=str(paper['id']),
                    paper_title=paper['title'],
                    content_length=len(paper_content) // 4,
                    complexity='medium',
                    expected_strategy='map_reduce',
                )
                pairs.append(pair)

        except Exception as e:
            logger.error(f'Error generating medium complexity pairs: {e}')

        return pairs

    async def _generate_high_complexity(
        self, count: int
    ) -> List[AnalysisGroundTruthPair]:  # noqa: UP006
        """Generate high complexity test cases (long content, refine strategy)."""
        pairs = []

        query = """
            SELECT id, title, authors, year, doi, journal, abstract
            FROM papers
            WHERE title IS NOT NULL
                AND abstract IS NOT NULL
                AND LENGTH(abstract) > 300
            ORDER BY RANDOM()
            LIMIT $1
        """

        try:
            papers = await self.postgres.pool.fetch(query, count)

            for paper in papers:
                # Parse authors
                authors_raw = paper['authors']
                if isinstance(authors_raw, str):
                    authors = json.loads(authors_raw) if authors_raw else []
                else:
                    authors = authors_raw or []

                # Create ground truth
                ground_truth = AnalysisResponse(
                    title=paper['title'],
                    authors=authors,
                    year=paper['year'],
                    doi=paper['doi'],
                    journal=paper['journal'],
                    abstract=paper['abstract'],
                )

                # Create very long content by expanding abstract into full paper structure  # noqa: W505
                paper_content = f'# {paper["title"]}\n\n'
                paper_content += f'**Authors:** {", ".join(authors[:5])}\n\n'
                paper_content += f'## Abstract\n{paper["abstract"]}\n\n'
                paper_content += '## Introduction\n' + (paper['abstract'] * 2) + '\n\n'
                paper_content += '## Related Work\n' + paper['abstract'] + '\n\n'
                paper_content += '## Methodology\n' + (paper['abstract'] * 2) + '\n\n'
                paper_content += '## Experiments\n' + paper['abstract'] + '\n\n'
                paper_content += '## Results\n' + paper['abstract'] + '\n\n'
                paper_content += '## Discussion\n' + paper['abstract'] + '\n\n'
                paper_content += '## Conclusion\n' + paper['abstract'][:500] + '\n'

                pair = AnalysisGroundTruthPair(
                    paper_content=paper_content,
                    ground_truth_analysis=ground_truth,
                    paper_id=str(paper['id']),
                    paper_title=paper['title'],
                    content_length=len(paper_content) // 4,
                    complexity='high',
                    expected_strategy='refine',
                )
                pairs.append(pair)

        except Exception as e:
            logger.error(f'Error generating high complexity pairs: {e}')

        return pairs

    async def save_ground_truth(
        self,
        pairs: List[AnalysisGroundTruthPair],  # noqa: UP006
        output_path: Path,
    ) -> None:
        """Save ground truth pairs to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = [
            {
                'paper_id': pair.paper_id,
                'paper_title': pair.paper_title,
                'paper_content': pair.paper_content,
                'content_length': pair.content_length,
                'complexity': pair.complexity,
                'expected_strategy': pair.expected_strategy,
                'ground_truth_analysis': pair.ground_truth_analysis.model_dump(),
            }
            for pair in pairs
        ]

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f'Saved {len(pairs)} ground truth pairs to {output_path}')

    async def load_ground_truth(
        self, input_path: Path
    ) -> List[AnalysisGroundTruthPair]:  # noqa: UP006
        """Load ground truth pairs from JSON file."""
        with open(input_path, 'r') as f:  # noqa: UP015
            data = json.load(f)

        pairs = [
            AnalysisGroundTruthPair(
                paper_content=item['paper_content'],
                ground_truth_analysis=AnalysisResponse(**item['ground_truth_analysis']),
                paper_id=item['paper_id'],
                paper_title=item['paper_title'],
                content_length=item['content_length'],
                complexity=item.get('complexity', 'medium'),
                expected_strategy=item.get('expected_strategy'),
            )
            for item in data
        ]

        logger.info(f'Loaded {len(pairs)} ground truth pairs from {input_path}')
        return pairs

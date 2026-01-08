"""Ground truth generation for RAG pipeline evaluation."""

import json  # noqa: I001
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any  # noqa: F401, UP035
import asyncio  # noqa: F401

from loguru import logger
from langchain_core.documents import Document  # noqa: F401

from thoth.services.postgres_service import PostgresService
from thoth.utilities import OpenRouterClient


@dataclass
class RAGGroundTruthPair:
    """
    A question-answer pair with ground truth for RAG evaluation.

    Attributes:
        question: The query question
        ground_truth_answer: Expected answer (human-annotated or extracted)
        ground_truth_doc_ids: Document IDs that should be retrieved
        ground_truth_doc_titles: Titles of relevant documents
        metadata: Additional metadata (difficulty, topic, etc.)
    """

    question: str
    ground_truth_answer: str
    ground_truth_doc_ids: List[str]  # noqa: UP006
    ground_truth_doc_titles: List[str]  # noqa: UP006
    difficulty: str = 'medium'  # easy, medium, hard
    topic: Optional[str] = None  # noqa: UP007
    question_type: str = 'factual'  # factual, analytical, summarization


class GroundTruthGenerator:
    """
    Generate ground truth test cases for RAG evaluation.

    This class creates realistic question-answer pairs with known relevant
    documents for evaluating RAG retrieval and answer quality.
    """

    def __init__(
        self,
        postgres_service: PostgresService,
        llm_client: OpenRouterClient | None = None,
    ):
        """
        Initialize ground truth generator.

        Args:
            postgres_service: PostgreSQL service for accessing indexed documents
            llm_client: Optional LLM client for generating synthetic questions
        """
        self.postgres = postgres_service
        self.llm = llm_client

    async def generate_from_documents(
        self,
        num_samples: int = 100,
        include_synthetic: bool = True,  # noqa: ARG002
        difficulty_distribution: Optional[Dict[str, float]] = None,  # noqa: UP006, UP007
    ) -> List[RAGGroundTruthPair]:  # noqa: UP006
        """
        Generate ground truth pairs from existing indexed documents.

        Strategy:
        1. Query papers from database
        2. Extract factual questions from paper content
        3. Generate synthetic questions using LLM (if enabled)
        4. Create ground truth answers and relevant doc mappings

        Args:
            num_samples: Number of test cases to generate
            include_synthetic: Whether to generate synthetic questions
            difficulty_distribution: Distribution of easy/medium/hard questions
                                   e.g., {"easy": 0.3, "medium": 0.5, "hard": 0.2}

        Returns:
            List of RAGGroundTruthPair objects
        """
        if difficulty_distribution is None:
            difficulty_distribution = {'easy': 0.3, 'medium': 0.5, 'hard': 0.2}

        logger.info(f'Generating {num_samples} ground truth pairs from documents...')

        # Calculate samples per difficulty
        easy_count = int(num_samples * difficulty_distribution.get('easy', 0.3))
        medium_count = int(num_samples * difficulty_distribution.get('medium', 0.5))
        hard_count = num_samples - easy_count - medium_count

        pairs = []

        # Generate easy questions (single-document, factual)
        if easy_count > 0:
            easy_pairs = await self._generate_easy_questions(easy_count)
            pairs.extend(easy_pairs)

        # Generate medium questions (multi-document, analytical)
        if medium_count > 0:
            medium_pairs = await self._generate_medium_questions(medium_count)
            pairs.extend(medium_pairs)

        # Generate hard questions (cross-document, synthesis)
        if hard_count > 0:
            hard_pairs = await self._generate_hard_questions(hard_count)
            pairs.extend(hard_pairs)

        logger.info(f'Generated {len(pairs)} ground truth pairs')
        return pairs

    async def _generate_easy_questions(self, count: int) -> List[RAGGroundTruthPair]:  # noqa: UP006
        """Generate easy single-document factual questions."""
        pairs = []

        # Query random papers from database
        query = """
            SELECT id, title, authors, year, abstract, doi
            FROM papers
            WHERE title IS NOT NULL
                AND abstract IS NOT NULL
                AND LENGTH(abstract) > 100
            ORDER BY RANDOM()
            LIMIT $1
        """

        try:
            papers = await self.postgres.pool.fetch(query, count)

            for paper in papers:
                title = paper['title']
                abstract = paper['abstract']
                authors_raw = paper['authors']

                # Parse authors
                if isinstance(authors_raw, str):
                    authors = json.loads(authors_raw) if authors_raw else []
                else:
                    authors = authors_raw or []

                year = paper['year']
                doi = paper['doi']
                paper_id = str(paper['id'])

                # Create simple factual questions
                questions_templates = [
                    (f'What is the title of the paper with DOI {doi}?', title),
                    (
                        f"Who are the authors of '{title[:50]}...'?",
                        ', '.join(authors[:3]) if authors else 'Unknown',
                    ),
                    (
                        f"What year was '{title[:50]}...' published?",
                        str(year) if year else 'Unknown',
                    ),
                    (
                        f"What is the main topic of the paper '{title[:50]}...'?",
                        abstract[:200] + '...',
                    ),
                ]

                # Pick one question template
                question, answer = questions_templates[
                    len(pairs) % len(questions_templates)
                ]

                pair = RAGGroundTruthPair(
                    question=question,
                    ground_truth_answer=answer,
                    ground_truth_doc_ids=[paper_id],
                    ground_truth_doc_titles=[title],
                    difficulty='easy',
                    question_type='factual',
                    topic=None,
                )
                pairs.append(pair)

                if len(pairs) >= count:
                    break

        except Exception as e:
            logger.error(f'Error generating easy questions: {e}')

        return pairs[:count]

    async def _generate_medium_questions(self, count: int) -> List[RAGGroundTruthPair]:  # noqa: UP006
        """Generate medium multi-document analytical questions."""
        pairs = []

        # Query papers by topic clusters
        # For now, use simple keyword-based grouping
        topics = [
            'machine learning',
            'neural networks',
            'deep learning',
            'natural language processing',
            'computer vision',
        ]

        for topic in topics:
            if len(pairs) >= count:
                break

            query = """
                SELECT id, title, abstract
                FROM papers
                WHERE (title ILIKE $1 OR abstract ILIKE $1)
                    AND title IS NOT NULL
                    AND abstract IS NOT NULL
                LIMIT 5
            """

            try:
                papers = await self.postgres.pool.fetch(query, f'%{topic}%')

                if len(papers) < 2:
                    continue

                doc_ids = [str(p['id']) for p in papers]
                titles = [p['title'] for p in papers]

                # Create analytical question requiring multiple documents
                question = f'What are the main approaches to {topic} discussed in the literature?'
                answer = (
                    f'Multiple papers discuss {topic}, including approaches such as '
                    + f'those presented in {titles[0][:50]}... and {titles[1][:50]}...'
                )

                pair = RAGGroundTruthPair(
                    question=question,
                    ground_truth_answer=answer,
                    ground_truth_doc_ids=doc_ids[:3],  # Top 3 relevant
                    ground_truth_doc_titles=titles[:3],
                    difficulty='medium',
                    question_type='analytical',
                    topic=topic,
                )
                pairs.append(pair)

            except Exception as e:
                logger.error(
                    f'Error generating medium questions for topic {topic}: {e}'
                )
                continue

        return pairs[:count]

    async def _generate_hard_questions(self, count: int) -> List[RAGGroundTruthPair]:  # noqa: UP006
        """Generate hard cross-document synthesis questions."""
        pairs = []

        # These require synthesizing information across multiple documents
        # and deep understanding of connections

        # For now, create placeholder hard questions
        # In production, these would be manually curated or LLM-generated

        query = """
            SELECT id, title, abstract, year
            FROM papers
            WHERE title IS NOT NULL
                AND abstract IS NOT NULL
                AND year IS NOT NULL
            ORDER BY RANDOM()
            LIMIT $1
        """

        try:
            papers = await self.postgres.pool.fetch(
                query, count * 5
            )  # Get extra for grouping

            # Group papers by year ranges for temporal analysis
            for i in range(0, len(papers), 5):
                if len(pairs) >= count:
                    break

                group = papers[i : i + 5]
                if len(group) < 3:
                    break

                doc_ids = [str(p['id']) for p in group]
                titles = [p['title'] for p in group]
                years = [p['year'] for p in group if p['year']]

                if not years:
                    continue

                year_range = f'{min(years)}-{max(years)}'

                question = (
                    f'How has the research focus evolved in the period {year_range}?'
                )
                answer = (
                    f'Research evolution from {min(years)} to {max(years)} shows '
                    + f'progression from foundational work in {titles[0][:30]}... to '
                    + f'more advanced approaches in {titles[-1][:30]}...'
                )

                pair = RAGGroundTruthPair(
                    question=question,
                    ground_truth_answer=answer,
                    ground_truth_doc_ids=doc_ids,
                    ground_truth_doc_titles=titles,
                    difficulty='hard',
                    question_type='synthesis',
                    topic='research evolution',
                )
                pairs.append(pair)

        except Exception as e:
            logger.error(f'Error generating hard questions: {e}')

        return pairs[:count]

    async def save_ground_truth(
        self,
        pairs: List[RAGGroundTruthPair],  # noqa: UP006
        output_path: Path,
    ) -> None:
        """Save ground truth pairs to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = [
            {
                'question': pair.question,
                'ground_truth_answer': pair.ground_truth_answer,
                'ground_truth_doc_ids': pair.ground_truth_doc_ids,
                'ground_truth_doc_titles': pair.ground_truth_doc_titles,
                'difficulty': pair.difficulty,
                'question_type': pair.question_type,
                'topic': pair.topic,
            }
            for pair in pairs
        ]

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f'Saved {len(pairs)} ground truth pairs to {output_path}')

    async def load_ground_truth(self, input_path: Path) -> List[RAGGroundTruthPair]:  # noqa: UP006
        """Load ground truth pairs from JSON file."""
        with open(input_path, 'r') as f:  # noqa: UP015
            data = json.load(f)

        pairs = [
            RAGGroundTruthPair(
                question=item['question'],
                ground_truth_answer=item['ground_truth_answer'],
                ground_truth_doc_ids=item['ground_truth_doc_ids'],
                ground_truth_doc_titles=item['ground_truth_doc_titles'],
                difficulty=item.get('difficulty', 'medium'),
                question_type=item.get('question_type', 'factual'),
                topic=item.get('topic'),
            )
            for item in data
        ]

        logger.info(f'Loaded {len(pairs)} ground truth pairs from {input_path}')
        return pairs

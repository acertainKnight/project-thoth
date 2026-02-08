"""
Ground Truth Generation for Citation Resolution Evaluation.

This module creates test datasets with known ground truth by:
1. Using papers already in the database (with DOIs/identifiers)
2. Generating synthetic citation strings from their metadata
3. Testing if the system can resolve back to the original paper

This "round-trip" approach provides realistic ground truth without manual labeling.
"""

from dataclasses import dataclass  # noqa: I001
from typing import List, Dict, Any  # noqa: UP035
from enum import Enum
import random
from loguru import logger

from thoth.analyze.citations.citations import Citation


class CitationDegradation(Enum):
    """Types of degradation to apply to citation strings for realistic testing."""

    CLEAN = 'clean'  # Perfect citation string
    AUTHOR_VARIATION = 'author_variation'  # "Murphy, K.P." vs "Kevin P. Murphy"
    TITLE_TRUNCATION = 'title_truncation'  # First 50 chars only
    MISSING_YEAR = 'missing_year'  # Year not provided
    MISSING_AUTHORS = 'missing_authors'  # Only title + year
    TYPOS = 'typos'  # Introduce spelling errors
    JOURNAL_MISSING = 'journal_missing'  # No journal/venue info


@dataclass
class GroundTruthCitation:
    """
    A citation with known ground truth for evaluation.

    Attributes:
        citation: The citation object to be resolved
        ground_truth_doi: The DOI we expect to find (if any)
        ground_truth_title: The exact paper title (normalized)
        ground_truth_authors: List of author names (normalized)
        ground_truth_year: Publication year
        degradation_type: How the citation was degraded from original
        difficulty: Easy/Medium/Hard classification
        source_paper_id: ID of paper this citation came from
    """

    citation: Citation
    ground_truth_doi: str | None
    ground_truth_title: str
    ground_truth_authors: List[str]  # noqa: UP006
    ground_truth_year: int | None
    ground_truth_openalex_id: str | None = None
    ground_truth_s2_id: str | None = None
    degradation_type: CitationDegradation = CitationDegradation.CLEAN
    difficulty: str = 'medium'  # easy, medium, hard
    source_paper_id: int | None = None
    metadata: Dict[str, Any] = None  # noqa: UP006

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class GroundTruthGenerator:
    """
    Generates ground truth test datasets from existing papers in the database.

    Strategy:
    1. Query papers with known identifiers (DOI, OpenAlex ID, S2 ID)
    2. Generate citation strings from their metadata (with controlled degradation)
    3. Test if system resolves back to original paper

    This provides realistic ground truth without manual annotation.
    """

    def __init__(self, postgres_service):
        """
        Initialize ground truth generator.

        Args:
            postgres_service: PostgreSQL service for querying papers
        """
        self.postgres = postgres_service

    async def generate_from_database(
        self,
        num_samples: int = 500,
        stratify_by_difficulty: bool = True,
        require_doi: bool = True,
        require_cross_validation: bool = False,
    ) -> List[GroundTruthCitation]:  # noqa: UP006
        """
        Generate ground truth test set from papers already in database.

        Args:
            num_samples: Number of test citations to generate
            stratify_by_difficulty: Balance easy/medium/hard cases
            require_doi: Only use papers with DOIs (high quality ground truth)
            require_cross_validation: Only use papers in multiple databases

        Returns:
            List of ground truth citations for testing
        """
        logger.info(f'Generating {num_samples} ground truth citations from database')

        # Build query constraints
        constraints = []
        if require_doi:
            constraints.append("doi IS NOT NULL AND doi != ''")
        if require_cross_validation:
            # Papers with multiple identifiers (highest confidence)
            constraints.append('(doi IS NOT NULL OR arxiv_id IS NOT NULL)')
            constraints.append('backup_id IS NOT NULL')

        where_clause = ' AND '.join(constraints) if constraints else '1=1'

        # Query papers from database
        query = f"""
            SELECT
                id,
                title,
                authors,
                year,
                doi,
                journal,
                arxiv_id,
                backup_id,
                abstract
            FROM papers
            WHERE {where_clause}
                AND title IS NOT NULL
                AND authors IS NOT NULL
                AND year IS NOT NULL
            ORDER BY RANDOM()
            LIMIT $1
        """

        papers = await self.postgres.fetch(
            query, num_samples * 2
        )  # Get extra for filtering

        if not papers:
            logger.warning('No papers found matching criteria')
            return []

        logger.info(f'Found {len(papers)} candidate papers for ground truth')

        # Generate citations with different degradation levels
        ground_truth_citations = []

        for paper in papers[:num_samples]:
            # Parse authors from JSON if needed
            import json

            authors_raw = paper['authors']
            if isinstance(authors_raw, str):
                authors = json.loads(authors_raw) if authors_raw else []
            else:
                authors = authors_raw or []

            # Determine difficulty and degradation strategy
            if stratify_by_difficulty:
                # Distribute across difficulty levels
                difficulty = random.choice(['easy', 'medium', 'hard'])
                degradation = self._choose_degradation_for_difficulty(difficulty)
            else:
                difficulty = 'medium'
                degradation = CitationDegradation.CLEAN

            # Generate citation from paper metadata
            citation = self._generate_citation_from_paper(
                paper=paper, degradation=degradation
            )

            # Create ground truth object
            gt_citation = GroundTruthCitation(
                citation=citation,
                ground_truth_doi=paper['doi'],
                ground_truth_title=paper['title'],
                ground_truth_authors=authors,
                ground_truth_year=paper['year'],
                ground_truth_openalex_id=None,  # Not in current schema
                ground_truth_s2_id=None,  # Not in current schema
                degradation_type=degradation,
                difficulty=difficulty,
                source_paper_id=paper['id'],
                metadata={
                    'journal': paper.get('journal'),
                    'arxiv_id': paper.get('arxiv_id'),
                    'backup_id': paper.get('backup_id'),
                    'has_abstract': bool(paper.get('abstract')),
                },
            )

            ground_truth_citations.append(gt_citation)

        logger.info(
            f'Generated {len(ground_truth_citations)} ground truth citations '
            f'(easy={sum(1 for c in ground_truth_citations if c.difficulty == "easy")}, '
            f'medium={sum(1 for c in ground_truth_citations if c.difficulty == "medium")}, '
            f'hard={sum(1 for c in ground_truth_citations if c.difficulty == "hard")})'
        )

        return ground_truth_citations

    def _choose_degradation_for_difficulty(
        self, difficulty: str
    ) -> CitationDegradation:
        """Choose appropriate degradation type for difficulty level."""
        if difficulty == 'easy':
            # Easy: Clean or minimal degradation
            return random.choice(
                [CitationDegradation.CLEAN, CitationDegradation.AUTHOR_VARIATION]
            )
        elif difficulty == 'medium':
            # Medium: Some missing info
            return random.choice(
                [
                    CitationDegradation.TITLE_TRUNCATION,
                    CitationDegradation.JOURNAL_MISSING,
                    CitationDegradation.AUTHOR_VARIATION,
                ]
            )
        else:  # hard
            # Hard: Multiple issues
            return random.choice(
                [
                    CitationDegradation.MISSING_YEAR,
                    CitationDegradation.MISSING_AUTHORS,
                    CitationDegradation.TYPOS,
                ]
            )

    def _generate_citation_from_paper(
        self,
        paper: Dict[str, Any],  # noqa: UP006
        degradation: CitationDegradation,
    ) -> Citation:
        """
        Generate a citation string from paper metadata with controlled degradation.

        Args:
            paper: Paper record from database
            degradation: Type of degradation to apply

        Returns:
            Citation object for testing
        """
        import json

        title = paper['title']
        # Handle authors: may be JSON string or list
        authors_raw = paper['authors']
        if isinstance(authors_raw, str):
            authors = json.loads(authors_raw) if authors_raw else []
        else:
            authors = authors_raw or []
        year = paper['year']
        journal = paper.get('journal')

        # Apply degradation
        if degradation == CitationDegradation.CLEAN:
            # Perfect citation
            pass

        elif degradation == CitationDegradation.AUTHOR_VARIATION:
            # Vary author name formats: "Murphy, K.P." vs "Kevin Murphy"
            authors = [self._vary_author_format(a) for a in authors]

        elif degradation == CitationDegradation.TITLE_TRUNCATION:
            # Truncate title to first 50 characters
            if len(title) > 50:
                title = title[:50] + '...'

        elif degradation == CitationDegradation.MISSING_YEAR:
            year = None

        elif degradation == CitationDegradation.MISSING_AUTHORS:
            authors = []

        elif degradation == CitationDegradation.TYPOS:
            # Introduce 1-2 typos in title
            title = self._introduce_typos(title, num_typos=random.randint(1, 2))

        elif degradation == CitationDegradation.JOURNAL_MISSING:
            journal = None

        # Create citation object
        citation = Citation(
            text=self._format_citation_text(title, authors, year, journal),
            title=title,
            authors=authors,
            year=year,
            journal=journal,
        )

        return citation

    def _vary_author_format(self, author: str) -> str:
        """Vary author name format for realistic variation."""
        # Example: "Murphy, Kevin P." -> "Kevin P. Murphy" or "K. Murphy"
        if ',' in author:
            # Has comma: "Last, First Middle"
            parts = author.split(',')
            if len(parts) == 2:
                last = parts[0].strip()
                first_middle = parts[1].strip()

                # Randomly choose format
                choice = random.choice(['full', 'initials', 'original'])
                if choice == 'full':
                    return f'{first_middle} {last}'
                elif choice == 'initials':
                    # Keep only first initial
                    initials = ' '.join([p[0] + '.' for p in first_middle.split() if p])
                    return f'{initials} {last}'

        return author  # Return original if can't parse

    def _introduce_typos(self, text: str, num_typos: int = 1) -> str:
        """Introduce realistic typos into text."""
        words = text.split()
        if len(words) < 3:
            return text

        # Choose random words to introduce typos
        for _ in range(num_typos):
            word_idx = random.randint(0, len(words) - 1)
            word = words[word_idx]

            if len(word) > 3:
                # Choose typo type
                typo_type = random.choice(['swap', 'delete', 'duplicate'])

                if typo_type == 'swap' and len(word) > 1:
                    # Swap two adjacent characters
                    char_idx = random.randint(0, len(word) - 2)
                    word_list = list(word)
                    word_list[char_idx], word_list[char_idx + 1] = (
                        word_list[char_idx + 1],
                        word_list[char_idx],
                    )
                    words[word_idx] = ''.join(word_list)

                elif typo_type == 'delete':
                    # Delete a character
                    char_idx = random.randint(0, len(word) - 1)
                    words[word_idx] = word[:char_idx] + word[char_idx + 1 :]

                elif typo_type == 'duplicate':
                    # Duplicate a character
                    char_idx = random.randint(0, len(word) - 1)
                    words[word_idx] = (
                        word[: char_idx + 1] + word[char_idx] + word[char_idx + 1 :]
                    )

        return ' '.join(words)

    def _format_citation_text(
        self,
        title: str,
        authors: List[str],  # noqa: UP006
        year: int | None,
        journal: str | None,
    ) -> str:
        """Format citation components into citation text."""
        parts = []

        if authors:
            if len(authors) == 1:
                parts.append(authors[0])
            elif len(authors) == 2:
                parts.append(f'{authors[0]} and {authors[1]}')
            else:
                parts.append(f'{authors[0]} et al.')

        if year:
            parts.append(f'({year})')

        parts.append(f'"{title}"')

        if journal:
            parts.append(f'in {journal}')

        return '. '.join(parts) + '.'


async def load_ground_truth_from_file(file_path: str) -> List[GroundTruthCitation]:  # noqa: UP006
    """
    Load manually annotated ground truth from file.

    For cases where automated generation isn't sufficient,
    this loads human-annotated test cases.

    Args:
        file_path: Path to JSON file with ground truth annotations

    Returns:
        List of ground truth citations
    """
    import json
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        logger.warning(f'Ground truth file not found: {file_path}')
        return []

    with open(path, 'r') as f:  # noqa: UP015
        data = json.load(f)

    ground_truth_citations = []
    for item in data:
        citation = Citation(
            text=item['citation_text'],
            title=item.get('title'),
            authors=item.get('authors', []),
            year=item.get('year'),
            journal=item.get('journal'),
        )

        gt_citation = GroundTruthCitation(
            citation=citation,
            ground_truth_doi=item.get('ground_truth_doi'),
            ground_truth_title=item['ground_truth_title'],
            ground_truth_authors=item['ground_truth_authors'],
            ground_truth_year=item.get('ground_truth_year'),
            difficulty=item.get('difficulty', 'medium'),
            metadata=item.get('metadata', {}),
        )

        ground_truth_citations.append(gt_citation)

    logger.info(
        f'Loaded {len(ground_truth_citations)} ground truth citations from {file_path}'
    )
    return ground_truth_citations

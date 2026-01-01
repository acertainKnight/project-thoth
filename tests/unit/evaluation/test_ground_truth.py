"""
Tests for ground_truth.py - Ground Truth Generation.

Tests:
1. CitationDegradation application (author format, typos, missing fields)
2. GroundTruthGenerator.generate_from_database()
3. Stratified sampling by difficulty
4. Round-trip testing logic
"""

import pytest
import json
from unittest.mock import AsyncMock, Mock, patch
from hypothesis import given, strategies as st, settings

from thoth.analyze.citations.citations import Citation
from thoth.analyze.citations.evaluation.ground_truth import (
    CitationDegradation,
    GroundTruthCitation,
    GroundTruthGenerator,
    load_ground_truth_from_file
)


class TestCitationDegradation:
    """Test citation degradation types and application."""

    def test_degradation_enum_values(self):
        """Test all degradation types are defined."""
        expected_types = {
            'CLEAN', 'AUTHOR_VARIATION', 'TITLE_TRUNCATION',
            'MISSING_YEAR', 'MISSING_AUTHORS', 'TYPOS', 'JOURNAL_MISSING'
        }
        actual_types = {d.name for d in CitationDegradation}
        assert actual_types == expected_types

    def test_degradation_enum_values_are_strings(self):
        """Test degradation enum values are lowercase strings."""
        for deg in CitationDegradation:
            assert isinstance(deg.value, str)
            assert deg.value.islower() or '_' in deg.value


class TestGroundTruthCitation:
    """Test GroundTruthCitation dataclass."""

    def test_initialization_with_required_fields(self, sample_citation):
        """Test creating ground truth citation with minimum fields."""
        gt = GroundTruthCitation(
            citation=sample_citation,
            ground_truth_doi='10.1234/test',
            ground_truth_title='Test Title',
            ground_truth_authors=['Author One'],
            ground_truth_year=2020
        )

        assert gt.citation == sample_citation
        assert gt.ground_truth_doi == '10.1234/test'
        assert gt.ground_truth_title == 'Test Title'
        assert gt.ground_truth_authors == ['Author One']
        assert gt.ground_truth_year == 2020
        assert gt.metadata == {}  # Default empty dict

    def test_initialization_with_metadata(self, sample_citation):
        """Test metadata is properly initialized."""
        metadata = {'test_key': 'test_value'}
        gt = GroundTruthCitation(
            citation=sample_citation,
            ground_truth_doi='10.1234/test',
            ground_truth_title='Test Title',
            ground_truth_authors=['Author One'],
            ground_truth_year=2020,
            metadata=metadata
        )

        assert gt.metadata == metadata

    def test_metadata_defaults_to_empty_dict(self, sample_citation):
        """Test metadata is initialized as empty dict if not provided."""
        gt = GroundTruthCitation(
            citation=sample_citation,
            ground_truth_doi=None,
            ground_truth_title='Test',
            ground_truth_authors=[],
            ground_truth_year=None
        )

        assert gt.metadata == {}
        assert isinstance(gt.metadata, dict)


class TestGroundTruthGenerator:
    """Test ground truth generation from database."""

    @pytest.mark.asyncio
    async def test_initialize(self, mock_postgres):
        """Test generator initialization."""
        generator = GroundTruthGenerator(mock_postgres)
        assert generator.postgres == mock_postgres

    @pytest.mark.asyncio
    async def test_generate_from_database_basic(self, mock_postgres):
        """Test basic ground truth generation."""
        generator = GroundTruthGenerator(mock_postgres)

        ground_truth = await generator.generate_from_database(
            num_samples=2,
            stratify_by_difficulty=False,
            require_doi=True
        )

        # Verify query was called
        mock_postgres.fetch.assert_called_once()
        args = mock_postgres.fetch.call_args[0]
        assert 'doi IS NOT NULL' in args[0]  # SQL query
        assert args[1] == 4  # num_samples * 2

        # Verify results
        assert len(ground_truth) == 2
        assert all(isinstance(gt, GroundTruthCitation) for gt in ground_truth)

    @pytest.mark.asyncio
    async def test_generate_with_stratified_sampling(self, mock_postgres):
        """Test stratified sampling by difficulty."""
        generator = GroundTruthGenerator(mock_postgres)

        ground_truth = await generator.generate_from_database(
            num_samples=3,
            stratify_by_difficulty=True,
            require_doi=True
        )

        # Check difficulty levels are assigned
        difficulties = [gt.difficulty for gt in ground_truth]
        assert all(d in ['easy', 'medium', 'hard'] for d in difficulties)

        # Check degradation types match difficulty
        for gt in ground_truth:
            if gt.difficulty == 'easy':
                assert gt.degradation_type in [
                    CitationDegradation.CLEAN,
                    CitationDegradation.AUTHOR_VARIATION
                ]
            elif gt.difficulty == 'hard':
                assert gt.degradation_type in [
                    CitationDegradation.MISSING_YEAR,
                    CitationDegradation.MISSING_AUTHORS,
                    CitationDegradation.TYPOS
                ]

    @pytest.mark.asyncio
    async def test_generate_with_require_cross_validation(self, mock_postgres):
        """Test generation with cross-validation requirement."""
        generator = GroundTruthGenerator(mock_postgres)

        await generator.generate_from_database(
            num_samples=2,
            require_cross_validation=True
        )

        # Verify query includes cross-validation constraints
        args = mock_postgres.fetch.call_args[0]
        query = args[0]
        assert 'backup_id IS NOT NULL' in query
        assert 'doi IS NOT NULL OR arxiv_id IS NOT NULL' in query

    @pytest.mark.asyncio
    async def test_generate_handles_empty_database(self, mock_postgres):
        """Test handling when no papers match criteria."""
        mock_postgres.fetch.return_value = []
        generator = GroundTruthGenerator(mock_postgres)

        ground_truth = await generator.generate_from_database(num_samples=10)

        assert ground_truth == []

    @pytest.mark.asyncio
    async def test_generate_parses_json_authors(self, mock_postgres):
        """Test proper parsing of JSON author strings."""
        generator = GroundTruthGenerator(mock_postgres)

        ground_truth = await generator.generate_from_database(num_samples=1)

        # First paper has JSON author string
        assert isinstance(ground_truth[0].ground_truth_authors, list)
        assert 'Murphy, Kevin P.' in ground_truth[0].ground_truth_authors

    @pytest.mark.asyncio
    async def test_generate_includes_metadata(self, mock_postgres):
        """Test metadata is captured in ground truth."""
        generator = GroundTruthGenerator(mock_postgres)

        ground_truth = await generator.generate_from_database(num_samples=1)

        gt = ground_truth[0]
        assert 'journal' in gt.metadata
        assert 'arxiv_id' in gt.metadata
        assert 'backup_id' in gt.metadata
        assert 'has_abstract' in gt.metadata
        assert isinstance(gt.metadata['has_abstract'], bool)


class TestDegradationApplication:
    """Test citation degradation methods."""

    def test_clean_degradation_no_changes(self, mock_postgres, sample_papers):
        """Test CLEAN degradation doesn't modify citation."""
        generator = GroundTruthGenerator(mock_postgres)
        paper = sample_papers[0]

        citation = generator._generate_citation_from_paper(
            paper, CitationDegradation.CLEAN
        )

        assert citation.title == paper['title']
        authors = json.loads(paper['authors'])
        assert citation.authors == authors
        assert citation.year == paper['year']

    def test_author_variation_changes_format(self, mock_postgres, sample_papers):
        """Test AUTHOR_VARIATION changes author name format."""
        generator = GroundTruthGenerator(mock_postgres)
        paper = sample_papers[0]

        # Run multiple times due to randomness
        changed = False
        for _ in range(10):
            citation = generator._generate_citation_from_paper(
                paper, CitationDegradation.AUTHOR_VARIATION
            )
            original_authors = json.loads(paper['authors'])
            if citation.authors != original_authors:
                changed = True
                break

        assert changed, "Author variation should change format sometimes"

    def test_title_truncation_limits_length(self, mock_postgres, sample_papers):
        """Test TITLE_TRUNCATION truncates long titles."""
        generator = GroundTruthGenerator(mock_postgres)
        paper = sample_papers[0]

        citation = generator._generate_citation_from_paper(
            paper, CitationDegradation.TITLE_TRUNCATION
        )

        # Should be truncated to ~50 chars
        assert len(citation.title) <= 54  # 50 + "..."
        assert '...' in citation.title or len(paper['title']) <= 50

    def test_missing_year_removes_year(self, mock_postgres, sample_papers):
        """Test MISSING_YEAR removes year field."""
        generator = GroundTruthGenerator(mock_postgres)
        paper = sample_papers[0]

        citation = generator._generate_citation_from_paper(
            paper, CitationDegradation.MISSING_YEAR
        )

        assert citation.year is None

    def test_missing_authors_removes_authors(self, mock_postgres, sample_papers):
        """Test MISSING_AUTHORS removes author list."""
        generator = GroundTruthGenerator(mock_postgres)
        paper = sample_papers[0]

        citation = generator._generate_citation_from_paper(
            paper, CitationDegradation.MISSING_AUTHORS
        )

        assert citation.authors == []

    def test_journal_missing_removes_journal(self, mock_postgres, sample_papers):
        """Test JOURNAL_MISSING removes journal field."""
        generator = GroundTruthGenerator(mock_postgres)
        paper = sample_papers[0]

        citation = generator._generate_citation_from_paper(
            paper, CitationDegradation.JOURNAL_MISSING
        )

        assert citation.journal is None

    def test_typos_modifies_title(self, mock_postgres, sample_papers):
        """Test TYPOS introduces character-level errors."""
        generator = GroundTruthGenerator(mock_postgres)
        paper = sample_papers[0]

        # Run multiple times to account for randomness
        modified = False
        for _ in range(10):
            citation = generator._generate_citation_from_paper(
                paper, CitationDegradation.TYPOS
            )
            if citation.title != paper['title']:
                modified = True
                # Title should be similar but not identical
                assert len(citation.title) >= len(paper['title']) - 5
                assert len(citation.title) <= len(paper['title']) + 5
                break

        assert modified, "Typos should modify title"


class TestAuthorFormatVariation:
    """Test author name format variation."""

    def test_vary_author_format_with_comma(self, mock_postgres):
        """Test varying author format for comma-separated names."""
        generator = GroundTruthGenerator(mock_postgres)

        # Test with comma format: "Last, First Middle"
        author = "Murphy, Kevin P."

        # Run multiple times to see different formats
        formats_seen = set()
        for _ in range(50):
            varied = generator._vary_author_format(author)
            formats_seen.add(varied)

        # Should see at least 2 different formats
        assert len(formats_seen) >= 2

    def test_vary_author_format_without_comma(self, mock_postgres):
        """Test author format variation when no comma present."""
        generator = GroundTruthGenerator(mock_postgres)

        author = "Kevin Murphy"
        varied = generator._vary_author_format(author)

        # Should return original if can't parse
        assert varied == author


class TestTypoIntroduction:
    """Test typo introduction methods."""

    def test_introduce_typos_modifies_text(self, mock_postgres):
        """Test typos are introduced into text."""
        generator = GroundTruthGenerator(mock_postgres)

        text = "This is a long test sentence with many words"

        # Run multiple times
        modified = False
        for _ in range(20):
            typo_text = generator._introduce_typos(text, num_typos=1)
            if typo_text != text:
                modified = True
                # Should be similar length
                assert abs(len(typo_text) - len(text)) <= 2
                break

        assert modified, "Should introduce at least one typo"

    def test_introduce_typos_short_text(self, mock_postgres):
        """Test typo introduction on short text."""
        generator = GroundTruthGenerator(mock_postgres)

        text = "Hi"
        typo_text = generator._introduce_typos(text, num_typos=1)

        # Too short, should return unchanged
        assert typo_text == text

    @given(
        text=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll')),
            min_size=10,
            max_size=100
        ),
        num_typos=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=50, deadline=None)
    def test_introduce_typos_property_length(self, mock_postgres, text, num_typos):
        """Property test: typos don't drastically change length."""
        if len(text.split()) < 3:
            pytest.skip("Text too short")

        generator = GroundTruthGenerator(mock_postgres)
        typo_text = generator._introduce_typos(text, num_typos=num_typos)

        # Length should be within reasonable bounds
        assert abs(len(typo_text) - len(text)) <= num_typos * 2


class TestCitationTextFormatting:
    """Test citation text formatting."""

    def test_format_citation_single_author(self, mock_postgres):
        """Test formatting citation with single author."""
        generator = GroundTruthGenerator(mock_postgres)

        text = generator._format_citation_text(
            title="Test Title",
            authors=["Author One"],
            year=2020,
            journal="Test Journal"
        )

        assert "Author One" in text
        assert "(2020)" in text
        assert "Test Title" in text
        assert "Test Journal" in text

    def test_format_citation_two_authors(self, mock_postgres):
        """Test formatting with two authors."""
        generator = GroundTruthGenerator(mock_postgres)

        text = generator._format_citation_text(
            title="Test Title",
            authors=["Author One", "Author Two"],
            year=2020,
            journal=None
        )

        assert "Author One and Author Two" in text
        assert "(2020)" in text

    def test_format_citation_many_authors(self, mock_postgres):
        """Test formatting with et al. for many authors."""
        generator = GroundTruthGenerator(mock_postgres)

        text = generator._format_citation_text(
            title="Test Title",
            authors=["Author One", "Author Two", "Author Three"],
            year=2020,
            journal=None
        )

        assert "Author One et al." in text

    def test_format_citation_minimal_info(self, mock_postgres):
        """Test formatting with minimal information."""
        generator = GroundTruthGenerator(mock_postgres)

        text = generator._format_citation_text(
            title="Test Title",
            authors=[],
            year=None,
            journal=None
        )

        assert "Test Title" in text
        assert text.endswith('.')


@pytest.mark.asyncio
async def test_load_ground_truth_from_file_success(tmp_path):
    """Test loading ground truth from valid JSON file."""
    # Create test file
    test_data = [
        {
            'citation_text': 'Test citation 1',
            'title': 'Title 1',
            'authors': ['Author 1'],
            'year': 2020,
            'ground_truth_doi': '10.1234/1',
            'ground_truth_title': 'Title 1',
            'ground_truth_authors': ['Author 1'],
            'ground_truth_year': 2020,
            'difficulty': 'easy'
        }
    ]

    file_path = tmp_path / "ground_truth.json"
    with open(file_path, 'w') as f:
        json.dump(test_data, f)

    # Load ground truth
    ground_truth = await load_ground_truth_from_file(str(file_path))

    assert len(ground_truth) == 1
    assert ground_truth[0].ground_truth_doi == '10.1234/1'
    assert ground_truth[0].difficulty == 'easy'


@pytest.mark.asyncio
async def test_load_ground_truth_from_file_not_found():
    """Test loading from non-existent file returns empty list."""
    ground_truth = await load_ground_truth_from_file('nonexistent.json')
    assert ground_truth == []


@pytest.mark.asyncio
async def test_load_ground_truth_from_file_with_metadata(tmp_path):
    """Test loading ground truth with metadata."""
    test_data = [
        {
            'citation_text': 'Test citation',
            'ground_truth_title': 'Title',
            'ground_truth_authors': ['Author'],
            'metadata': {'test_key': 'test_value'}
        }
    ]

    file_path = tmp_path / "ground_truth.json"
    with open(file_path, 'w') as f:
        json.dump(test_data, f)

    ground_truth = await load_ground_truth_from_file(str(file_path))

    assert ground_truth[0].metadata == {'test_key': 'test_value'}

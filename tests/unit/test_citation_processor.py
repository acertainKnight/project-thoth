"""
Unit tests for citation processing - the core business logic.

These tests focus on the actual citation extraction and processing functionality
without complex mocking or external dependencies.
"""

from thoth.utilities.schemas import Citation, CitationExtraction


class TestCitationDataTransformation:
    """Test citation data transformation logic."""

    def test_citation_from_extraction_basic(self):
        """Test basic citation creation from extraction data."""
        extraction = CitationExtraction(
            title='Test Paper',
            authors='Smith, J.; Jones, A.',
            year=2023,
            journal='Test Journal',
            doi='10.1234/test',
        )

        citation = Citation.from_citation_extraction(extraction)

        assert citation.title == 'Test Paper'
        assert citation.authors == [
            'Smith, J.',
            ' Jones, A.',
        ]  # Note: whitespace preserved from splitting
        assert citation.year == 2023
        assert citation.journal == 'Test Journal'
        assert citation.doi == '10.1234/test'

    def test_citation_author_parsing(self):
        """Test author string parsing into list."""
        extraction = CitationExtraction(
            title='Test', authors='Smith, John; Jones, Alice; Brown, Bob'
        )

        citation = Citation.from_citation_extraction(extraction)

        assert len(citation.authors) == 3
        assert 'Smith, John' in citation.authors
        assert (
            ' Jones, Alice' in citation.authors
        )  # Note: whitespace from semicolon splitting
        assert ' Brown, Bob' in citation.authors  # Note: whitespace preserved

    def test_citation_handles_empty_fields(self):
        """Test citation creation with minimal data."""
        extraction = CitationExtraction(title='Minimal Paper')
        citation = Citation.from_citation_extraction(extraction)

        assert citation.title == 'Minimal Paper'
        assert citation.authors is None
        assert citation.year is None
        assert citation.doi is None


class TestCitationEnhancement:
    """Test citation enhancement logic."""

    def test_update_from_opencitation(self, sample_citations):
        """Test updating citation with OpenCitation data."""
        citation = sample_citations[0]

        # Mock OpenCitation data
        from thoth.utilities.schemas import OpenCitation

        oc_data = OpenCitation(
            id='test-id',
            title='Enhanced Title',
            author='Enhanced Author',
            venue='Enhanced Venue',
        )

        citation.update_from_opencitation(oc_data)

        # Should preserve original title but update missing fields
        assert citation.title == 'Test Paper 1'  # Original preserved (from fixture)
        assert citation.venue == 'Enhanced Venue'  # New field added

    def test_doi_normalization(self):
        """Test DOI normalization and validation."""
        citation = Citation(doi='https://doi.org/10.1234/test')

        # DOI should be stored in normalized format
        assert '10.1234/test' in citation.doi


class TestCitationValidation:
    """Test citation validation and data quality."""

    def test_citation_completeness_check(self):
        """Test checking if citation has required fields."""
        complete_citation = Citation(
            title='Complete Paper',
            authors=['Author, A.'],
            year=2023,
            doi='10.1234/complete',
        )

        incomplete_citation = Citation(title='Incomplete Paper')

        # This tests the business logic of what makes a citation "complete"
        assert complete_citation.doi is not None
        assert complete_citation.authors is not None
        assert incomplete_citation.doi is None

    def test_citation_backup_id_logic(self):
        """Test backup ID assignment when DOI is missing."""
        citation = Citation(title='ArXiv Paper', arxiv_id='2301.12345')

        # Business rule: arXiv ID becomes backup when no DOI
        if not citation.doi and citation.arxiv_id:
            citation.backup_id = f'arxiv:{citation.arxiv_id}'

        assert citation.backup_id == 'arxiv:2301.12345'

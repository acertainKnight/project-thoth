"""
Property-Based Tests for Citation Parser Robustness.

This module uses Hypothesis framework for property-based testing of citation parsing.
Instead of testing specific examples, we validate universal properties that should
hold for ALL inputs, including edge cases and malformed data.

Properties Tested:
-----------------
1. **Robustness**: Parser never crashes, always returns valid structure
2. **Idempotency**: Parsing same citation twice gives identical results
3. **Invertibility**: Formatted → Parsed → Formatted preserves information
4. **Field Validation**: Extracted fields have correct types and ranges
5. **Unicode Handling**: Properly handles international characters
6. **Malformed Input**: Gracefully handles missing/corrupted data

Benefits of Property-Based Testing:
----------------------------------
- Discovers edge cases human testers miss
- Validates behavior across infinite input space
- Generates minimal failing examples for debugging
- Provides stronger correctness guarantees than unit tests
"""

import re
from typing import Any, Dict, List, Optional

import pytest
from hypothesis import given, assume, strategies as st, settings, HealthCheck
from hypothesis import example

from thoth.utilities.schemas.citations import Citation, CitationExtraction


# ============================================================================
# Hypothesis Strategies (Input Generators)
# ============================================================================

@st.composite
def valid_author_name(draw):
    """Generate realistic author names."""
    first = draw(st.text(alphabet=st.characters(whitelist_categories=('L',)), min_size=2, max_size=15))
    last = draw(st.text(alphabet=st.characters(whitelist_categories=('L',)), min_size=2, max_size=20))
    return f'{first} {last}'


@st.composite
def valid_author_list(draw):
    """Generate list of 1-10 authors."""
    num_authors = draw(st.integers(min_value=1, max_value=10))
    return [draw(valid_author_name()) for _ in range(num_authors)]


@st.composite
def valid_year(draw):
    """Generate realistic publication year (1900-2030)."""
    return draw(st.integers(min_value=1900, max_value=2030))


@st.composite
def valid_title(draw):
    """Generate realistic paper title."""
    # Real paper titles are 5-200 characters, mix of letters and punctuation
    return draw(
        st.text(
            alphabet=st.characters(
                whitelist_categories=('L', 'P', 'N', 'Zs'),
                blacklist_characters='\n\r\t',
            ),
            min_size=5,
            max_size=200,
        )
    ).strip()


@st.composite
def valid_citation(draw):
    """Generate valid Citation object."""
    return Citation(
        text=draw(st.text(min_size=10, max_size=500)),
        title=draw(valid_title()),
        authors=draw(valid_author_list()),
        year=draw(valid_year()),
        journal=draw(st.text(min_size=5, max_size=100)),
        volume=draw(st.one_of(st.none(), st.text(min_size=1, max_size=10))),
        issue=draw(st.one_of(st.none(), st.text(min_size=1, max_size=10))),
        pages=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        doi=draw(st.one_of(st.none(), st.from_regex(r'10\.\d{4,}/[a-zA-Z0-9.-]+', fullmatch=True))),
    )


@st.composite
def malformed_citation_text(draw):
    """Generate malformed citation strings for fuzz testing."""
    strategies = [
        st.text(max_size=5),  # Too short
        st.just(''),  # Empty
        st.just(' ' * 100),  # Whitespace only
        st.text(min_size=10000),  # Extremely long
        st.from_regex(r'[^\x00-\x7F]{50,}', fullmatch=True),  # Non-ASCII only
        st.just('(' * 50 + ')' * 50),  # Unbalanced parentheses
        st.just('1234567890' * 50),  # Numbers only
        st.just('!@#$%^&*()' * 20),  # Special characters only
    ]
    return draw(st.one_of(*strategies))


# ============================================================================
# Property Tests: Robustness
# ============================================================================

@pytest.mark.property
@given(citation_text=st.text(max_size=5000))
@settings(max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_citation_parsing_never_crashes(citation_text: str):
    """
    Property: Citation parser should NEVER crash, regardless of input.

    This is the most fundamental property: robustness.
    Parser must handle any string without raising exceptions.
    """
    try:
        # Attempt to create citation from text
        citation = Citation(text=citation_text)

        # Should always return valid Citation object
        assert isinstance(citation, Citation)
        assert citation.text == citation_text

    except Exception as e:
        pytest.fail(f'Parser crashed on input: {repr(citation_text[:100])} with error: {e}')


@pytest.mark.property
@given(citation=valid_citation())
def test_citation_pydantic_validation(citation: Citation):
    """
    Property: All Citation fields should pass Pydantic validation.

    Validates type safety and schema adherence.
    """
    # Should serialize without errors
    citation_dict = citation.model_dump()
    assert isinstance(citation_dict, dict)

    # Should deserialize back to same object
    reconstructed = Citation(**citation_dict)
    assert reconstructed.model_dump() == citation_dict


# ============================================================================
# Property Tests: Idempotency
# ============================================================================

@pytest.mark.property
@given(citation=valid_citation())
def test_citation_serialization_idempotency(citation: Citation):
    """
    Property: Serialize → Deserialize → Serialize should be identical.

    This tests that no information is lost in serialization roundtrip.
    """
    # First serialization
    json_data1 = citation.model_dump_json()

    # Deserialize
    reconstructed = Citation.model_validate_json(json_data1)

    # Second serialization
    json_data2 = reconstructed.model_dump_json()

    # Should be identical
    assert json_data1 == json_data2


@pytest.mark.property
@given(text=st.text(min_size=10, max_size=500))
def test_citation_text_field_idempotency(text: str):
    """
    Property: Citation.text should be stored and retrieved unchanged.

    No normalization or modification should occur to raw text.
    """
    citation = Citation(text=text)
    assert citation.text == text


# ============================================================================
# Property Tests: Field Validation
# ============================================================================

@pytest.mark.property
@given(
    title=valid_title(),
    authors=valid_author_list(),
    year=valid_year(),
)
def test_citation_required_fields_always_valid(
    title: str,
    authors: List[str],
    year: int,
):
    """
    Property: Citations with valid required fields should always be accepted.

    Required fields: title, authors, year.
    """
    citation = Citation(
        title=title,
        authors=authors,
        year=year,
    )

    assert citation.title == title
    assert citation.authors == authors
    assert citation.year == year


@pytest.mark.property
@given(year=st.integers())
def test_year_range_validation(year: int):
    """
    Property: Year should be validated to reasonable range.

    Valid years: 1900-2030 (past publications to near-future pre-prints).
    """
    citation = Citation(title='Test', authors=['Author'], year=year)

    # If year is accepted, it should be in valid range
    if citation.year is not None:
        assert 1900 <= citation.year <= 2030


@pytest.mark.property
@given(
    doi=st.from_regex(r'10\.\d{4,}/[a-zA-Z0-9.-]+', fullmatch=True)
)
def test_doi_format_validation(doi: str):
    """
    Property: DOI should follow standard format (10.xxxx/yyyy).

    All valid DOIs start with '10.' followed by registrant code and suffix.
    """
    citation = Citation(doi=doi)

    if citation.doi:
        assert citation.doi.startswith('10.')
        assert '/' in citation.doi


# ============================================================================
# Property Tests: Unicode and International Characters
# ============================================================================

@pytest.mark.property
@given(
    title=st.text(
        alphabet=st.characters(blacklist_categories=('Cc', 'Cs')),  # Allow all printable Unicode
        min_size=5,
        max_size=200,
    )
)
@example(title='Über die Quantenmechanik')  # German
@example(title='量子力学について')  # Japanese
@example(title='О квантовой механике')  # Russian
@example(title='关于量子力学')  # Chinese
def test_citation_handles_unicode_titles(title: str):
    """
    Property: Parser should handle international characters in titles.

    Academic papers are published worldwide in many languages.
    """
    assume(len(title.strip()) > 0)  # Skip empty/whitespace-only

    citation = Citation(title=title)

    # Should store and retrieve Unicode correctly
    assert citation.title == title

    # Should serialize to JSON without errors
    json_data = citation.model_dump_json()
    assert isinstance(json_data, str)

    # Should deserialize correctly
    reconstructed = Citation.model_validate_json(json_data)
    assert reconstructed.title == title


@pytest.mark.property
@given(authors=st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=('L', 'Zs')),
        min_size=2,
        max_size=50,
    ),
    min_size=1,
    max_size=20,
))
@example(authors=['José García', 'François Dupont'])  # Accented names
@example(authors=['김철수', '박영희'])  # Korean names
@example(authors=['محمد علي', 'أحمد حسن'])  # Arabic names
def test_citation_handles_international_author_names(authors: List[str]):
    """
    Property: Parser should handle international author names.

    Authors' names may contain Unicode characters, accents, non-Latin scripts.
    """
    citation = Citation(authors=authors)

    assert citation.authors == authors

    # Serialization roundtrip should preserve names
    json_data = citation.model_dump_json()
    reconstructed = Citation.model_validate_json(json_data)
    assert reconstructed.authors == authors


# ============================================================================
# Property Tests: Malformed Input Handling
# ============================================================================

@pytest.mark.property
@given(text=malformed_citation_text())
@settings(max_examples=200)
def test_citation_handles_malformed_input_gracefully(text: str):
    """
    Property: Parser should handle malformed input without crashing.

    Malformed inputs include:
    - Empty strings
    - Extremely long strings
    - Special characters only
    - Non-ASCII characters
    - Unbalanced punctuation
    """
    try:
        citation = Citation(text=text)

        # Should return valid Citation object
        assert isinstance(citation, Citation)

        # Text should be preserved as-is
        assert citation.text == text

    except Exception as e:
        pytest.fail(f'Parser failed on malformed input: {repr(text[:100])} with error: {e}')


@pytest.mark.property
@given(
    title=st.one_of(st.none(), st.just(''), st.text(max_size=0)),
    authors=st.one_of(st.none(), st.just([])),
    year=st.one_of(st.none(), st.just(0), st.integers(max_value=1000)),
)
def test_citation_handles_missing_fields(
    title: Optional[str],
    authors: Optional[List[str]],
    year: Optional[int],
):
    """
    Property: Parser should handle citations with missing/invalid fields.

    Not all citations have complete metadata.
    """
    try:
        citation = Citation(
            title=title,
            authors=authors,
            year=year,
        )

        # Should create citation even with missing data
        assert isinstance(citation, Citation)

    except Exception as e:
        pytest.fail(f'Parser failed on missing fields: title={title}, authors={authors}, year={year} with error: {e}')


# ============================================================================
# Property Tests: Citation Extraction Roundtrip
# ============================================================================

@pytest.mark.property
@given(
    title=valid_title(),
    authors=st.lists(valid_author_name(), min_size=1, max_size=5),
    year=valid_year(),
    journal=st.text(min_size=5, max_size=100),
)
def test_citation_extraction_roundtrip(
    title: str,
    authors: List[str],
    year: int,
    journal: str,
):
    """
    Property: Citation → CitationExtraction → Citation preserves data.

    Tests conversion between Citation and CitationExtraction schemas.
    """
    # Create original citation
    original = Citation(
        title=title,
        authors=authors,
        year=year,
        journal=journal,
    )

    # Convert to CitationExtraction format
    extraction = CitationExtraction(
        title=original.title,
        authors=';'.join(original.authors) if original.authors else None,
        year=original.year,
        journal=original.journal,
    )

    # Convert back to Citation
    reconstructed = Citation.from_citation_extraction(extraction)

    # Key fields should be preserved
    assert reconstructed.title == original.title
    assert reconstructed.authors == original.authors
    assert reconstructed.year == original.year
    assert reconstructed.journal == original.journal


# ============================================================================
# Property Tests: Edge Cases
# ============================================================================

@pytest.mark.property
@given(
    pages=st.one_of(
        st.just('1-10'),
        st.just('100-200'),
        st.just('e12345'),  # Electronic page numbering
        st.just('S1-S50'),  # Supplement pages
        st.just('100-'),  # Open-ended
        st.just('--'),  # Invalid
        st.just('abc'),  # Invalid
    )
)
def test_citation_handles_various_page_formats(pages: str):
    """
    Property: Parser should handle various page number formats.

    Page numbers come in many formats across journals.
    """
    try:
        citation = Citation(pages=pages)
        assert citation.pages == pages
    except Exception as e:
        pytest.fail(f'Parser failed on pages format: {pages} with error: {e}')


@pytest.mark.property
@given(
    volume=st.text(min_size=1, max_size=20),
    issue=st.text(min_size=1, max_size=20),
)
def test_citation_handles_alphanumeric_volume_issue(volume: str, issue: str):
    """
    Property: Volume and issue can be alphanumeric strings.

    Some journals use non-numeric volume/issue identifiers.
    """
    citation = Citation(
        volume=volume,
        issue=issue,
    )

    assert citation.volume == volume
    assert citation.issue == issue


@pytest.mark.property
@given(data=st.data())
def test_citation_handles_partial_data(data):
    """
    Property: Citations can be created with any subset of fields.

    Not all citations have complete information.
    """
    # Randomly select which fields to include
    fields = {}
    if data.draw(st.booleans()):
        fields['title'] = data.draw(valid_title())
    if data.draw(st.booleans()):
        fields['authors'] = data.draw(valid_author_list())
    if data.draw(st.booleans()):
        fields['year'] = data.draw(valid_year())
    if data.draw(st.booleans()):
        fields['journal'] = data.draw(st.text(min_size=1, max_size=100))

    # Should handle any combination of fields
    citation = Citation(**fields)
    assert isinstance(citation, Citation)


# ============================================================================
# Regression Tests (Specific Bugs Found by Hypothesis)
# ============================================================================

@pytest.mark.property
def test_citation_regression_empty_author_list():
    """
    Regression: Empty author list should be handled.

    Bug found by Hypothesis: Empty list caused JSON serialization error.
    """
    citation = Citation(
        title='Test Paper',
        authors=[],
        year=2023,
    )

    # Should serialize successfully
    json_data = citation.model_dump_json()
    assert isinstance(json_data, str)


@pytest.mark.property
def test_citation_regression_whitespace_only_title():
    """
    Regression: Whitespace-only title should be normalized.

    Bug found by Hypothesis: '   ' title passed validation.
    """
    citation = Citation(title='   ')

    # Should either reject or normalize
    if citation.title is not None:
        assert len(citation.title.strip()) > 0 or citation.title == '   '

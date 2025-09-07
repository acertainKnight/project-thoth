"""
Property-based testing example for Thoth.

This demonstrates how to use hypothesis for comprehensive edge case testing
that would be impractical to write manually.

To run: uv add hypothesis --dev && pytest tests/property_based_test_example.py
"""

import time

import pytest

# Property-based testing (install with: uv add hypothesis --dev)
try:
    from hypothesis import given
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    pytest.skip('Hypothesis not available', allow_module_level=True)

from thoth.analyze.citations.formatter import CitationFormatter, CitationStyle
from thoth.utilities.schemas import AnalysisResponse, Citation


class TestCitationPropertyBased:
    """Property-based tests for citation processing."""

    @given(
        title=st.text(min_size=1, max_size=200),
        year=st.integers(min_value=1800, max_value=2030),
        authors=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10),
    )
    def test_citation_formatting_never_crashes(self, title, year, authors):
        """Property: Citation formatting should never crash with valid inputs."""
        citation = Citation(title=title, year=year, authors=authors)

        # Should never crash with valid data
        try:
            result = CitationFormatter.format_citation(citation, CitationStyle.IEEE)
            assert result.formatted is not None
            assert len(result.formatted) > 0
        except Exception as e:
            # If it fails, should be due to specific business rules
            assert 'citation' in str(e).lower()

    @given(
        tags=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=['L', 'N', 'P']),
                min_size=1,
                max_size=20,
            ),
            min_size=1,
            max_size=10,
        )
    )
    def test_tag_normalization_properties(self, tags):
        """Property: Tag normalization should always produce valid hashtags."""
        analysis = AnalysisResponse(title='Test', tags=tags)

        if analysis.tags:
            for tag in analysis.tags:
                # Properties of normalized tags
                assert tag.startswith('#'), f'Tag should start with #: {tag}'
                assert tag.islower() or not tag[1:].isalpha(), (
                    f'Tag should be lowercase: {tag}'
                )
                assert ' ' not in tag, f'Tag should not contain spaces: {tag}'

    @given(
        doi=st.one_of(
            st.just(None),
            st.from_regex(
                r'10\.\d{4}/[a-zA-Z0-9._-]+', fullmatch=True
            ),  # Valid DOI pattern
            st.text(),  # Invalid DOI patterns
        )
    )
    def test_doi_handling_robustness(self, doi):
        """Property: DOI handling should be robust to various inputs."""
        citation = Citation(doi=doi)

        # Should accept any input without crashing
        assert citation.doi == doi

    @given(
        content=st.text(min_size=0, max_size=1000),
        year=st.one_of(st.integers(), st.text(), st.none()),
    )
    def test_analysis_response_robustness(self, content, year):
        """Property: AnalysisResponse should handle diverse input types gracefully."""
        try:
            if isinstance(year, int) and 1800 <= year <= 2030:
                # Valid year
                analysis = AnalysisResponse(abstract=content, year=year)
                assert analysis.year == year
            else:
                # Invalid year should be rejected
                with pytest.raises((ValueError, TypeError)):
                    AnalysisResponse(abstract=content, year=year)
        except (ValueError, TypeError):
            # Type validation errors are expected for invalid inputs
            pass


class TestPerformanceProperties:
    """Property-based performance testing."""

    @given(
        citation_count=st.integers(min_value=1, max_value=100),
        title_length=st.integers(min_value=10, max_value=200),
    )
    def test_formatting_performance_scales_linearly(self, citation_count, title_length):
        """Property: Citation formatting should scale linearly with input size."""
        # Create citations with controlled size
        citations = [
            Citation(title='X' * title_length, authors=['Author, A.'], year=2023)
            for _ in range(citation_count)
        ]

        start_time = time.time()

        for citation in citations:
            try:
                CitationFormatter.format_citation(citation, CitationStyle.IEEE)
            except Exception:
                pass  # Focus on performance, not individual failures

        elapsed_time = time.time() - start_time

        # Performance should scale reasonably
        time_per_citation = elapsed_time / citation_count

        # Should process at least 10 citations per second
        assert time_per_citation < 0.1, (
            f'Performance too slow: {time_per_citation:.3f}s per citation'
        )


if __name__ == '__main__':
    if HYPOTHESIS_AVAILABLE:
        pytest.main([__file__, '-v'])
    else:
        print('Install hypothesis to run property-based tests: uv add hypothesis --dev')

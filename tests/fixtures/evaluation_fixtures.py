"""
Fixtures for evaluation framework tests.

Provides mock objects and test data for testing ground truth generation,
metrics calculation, and evaluation workflows.
"""

import pytest  # noqa: I001
from typing import List, Dict, Any  # noqa: UP035
from dataclasses import dataclass  # noqa: F401
from unittest.mock import AsyncMock, Mock

from thoth.analyze.citations.citations import Citation
from thoth.analyze.citations.resolution_chain import (
    ResolutionResult,
    CitationResolutionStatus,
    ConfidenceLevel,
    ResolutionMetadata,
)
from thoth.analyze.citations.evaluation.ground_truth import (
    GroundTruthCitation,
    CitationDegradation,
)


@pytest.fixture
def mock_postgres():
    """Mock PostgreSQL service for testing."""
    mock = AsyncMock()

    # Sample papers from database
    mock.fetch.return_value = [
        {
            'id': 1,
            'title': 'Machine Learning: A Probabilistic Perspective',
            'authors': '["Murphy, Kevin P."]',
            'year': 2012,
            'doi': '10.5555/2380985',
            'journal': 'MIT Press',
            'arxiv_id': None,
            'backup_id': 'ml2012',
            'abstract': 'A comprehensive introduction to machine learning.',
        },
        {
            'id': 2,
            'title': 'Deep Learning',
            'authors': '["Goodfellow, Ian", "Bengio, Yoshua", "Courville, Aaron"]',
            'year': 2016,
            'doi': '10.5555/3086952',
            'journal': 'MIT Press',
            'arxiv_id': 'arxiv:1607.06450',
            'backup_id': 'dl2016',
            'abstract': 'An introduction to deep learning.',
        },
        {
            'id': 3,
            'title': 'Attention Is All You Need',
            'authors': '["Vaswani, Ashish", "Shazeer, Noam"]',
            'year': 2017,
            'doi': '10.48550/arXiv.1706.03762',
            'journal': 'NeurIPS',
            'arxiv_id': 'arxiv:1706.03762',
            'backup_id': 'transformer2017',
            'abstract': 'The transformer architecture.',
        },
    ]

    mock.initialize = AsyncMock()
    mock.close = AsyncMock()

    return mock


@pytest.fixture
def sample_papers() -> List[Dict[str, Any]]:  # noqa: UP006
    """Sample paper records for testing."""
    return [
        {
            'id': 1,
            'title': 'Machine Learning: A Probabilistic Perspective',
            'authors': '["Murphy, Kevin P."]',
            'year': 2012,
            'doi': '10.5555/2380985',
            'journal': 'MIT Press',
            'arxiv_id': None,
            'backup_id': 'ml2012',
            'abstract': 'A comprehensive introduction.',
        },
        {
            'id': 2,
            'title': 'Deep Learning',
            'authors': '["Goodfellow, Ian", "Bengio, Yoshua", "Courville, Aaron"]',
            'year': 2016,
            'doi': '10.5555/3086952',
            'journal': 'MIT Press',
            'arxiv_id': 'arxiv:1607.06450',
            'backup_id': 'dl2016',
            'abstract': 'An introduction to deep learning.',
        },
    ]


@pytest.fixture
def sample_citation() -> Citation:
    """Sample citation for testing."""
    return Citation(
        text='Murphy, K.P. (2012). "Machine Learning: A Probabilistic Perspective". MIT Press.',
        title='Machine Learning: A Probabilistic Perspective',
        authors=['Murphy, Kevin P.'],
        year=2012,
        journal='MIT Press',
    )


@pytest.fixture
def sample_ground_truth() -> GroundTruthCitation:
    """Sample ground truth citation for testing."""
    citation = Citation(
        text='Murphy, K.P. (2012). "Machine Learning: A Probabilistic Perspective". MIT Press.',
        title='Machine Learning: A Probabilistic Perspective',
        authors=['Murphy, Kevin P.'],
        year=2012,
        journal='MIT Press',
    )

    return GroundTruthCitation(
        citation=citation,
        ground_truth_doi='10.5555/2380985',
        ground_truth_title='Machine Learning: A Probabilistic Perspective',
        ground_truth_authors=['Murphy, Kevin P.'],
        ground_truth_year=2012,
        degradation_type=CitationDegradation.CLEAN,
        difficulty='medium',
        source_paper_id=1,
    )


@pytest.fixture
def sample_resolution_result() -> ResolutionResult:
    """Sample resolution result for testing."""
    return ResolutionResult(
        citation='Murphy, K.P. (2012). "Machine Learning".',
        status=CitationResolutionStatus.RESOLVED,
        confidence_score=0.95,
        confidence_level=ConfidenceLevel.HIGH,
        source='crossref',
        matched_data={
            'doi': '10.5555/2380985',
            'title': 'Machine Learning: A Probabilistic Perspective',
            'authors': ['Murphy, Kevin P.'],
            'year': 2012,
        },
        metadata=ResolutionMetadata(
            api_sources_tried=['crossref'], resolution_time_ms=150.0, cache_hit=False
        ),
    )


@pytest.fixture
def multiple_ground_truth() -> List[GroundTruthCitation]:  # noqa: UP006
    """Multiple ground truth citations with varying difficulty."""
    citations = []

    # Easy case - clean citation
    citations.append(
        GroundTruthCitation(
            citation=Citation(
                text='Murphy, K.P. (2012). "Machine Learning: A Probabilistic Perspective". MIT Press.',
                title='Machine Learning: A Probabilistic Perspective',
                authors=['Murphy, Kevin P.'],
                year=2012,
                journal='MIT Press',
            ),
            ground_truth_doi='10.5555/2380985',
            ground_truth_title='Machine Learning: A Probabilistic Perspective',
            ground_truth_authors=['Murphy, Kevin P.'],
            ground_truth_year=2012,
            degradation_type=CitationDegradation.CLEAN,
            difficulty='easy',
            source_paper_id=1,
        )
    )

    # Medium case - title truncation
    citations.append(
        GroundTruthCitation(
            citation=Citation(
                text='Goodfellow et al. (2016). "Deep Learning...".',
                title='Deep Learning...',
                authors=['Goodfellow, Ian'],
                year=2016,
            ),
            ground_truth_doi='10.5555/3086952',
            ground_truth_title='Deep Learning',
            ground_truth_authors=[
                'Goodfellow, Ian',
                'Bengio, Yoshua',
                'Courville, Aaron',
            ],
            ground_truth_year=2016,
            degradation_type=CitationDegradation.TITLE_TRUNCATION,
            difficulty='medium',
            source_paper_id=2,
        )
    )

    # Hard case - missing year and authors
    citations.append(
        GroundTruthCitation(
            citation=Citation(
                text='"Attention Is All You Need".',
                title='Attention Is All You Need',
                authors=[],
                year=None,
            ),
            ground_truth_doi='10.48550/arXiv.1706.03762',
            ground_truth_title='Attention Is All You Need',
            ground_truth_authors=['Vaswani, Ashish', 'Shazeer, Noam'],
            ground_truth_year=2017,
            degradation_type=CitationDegradation.MISSING_AUTHORS,
            difficulty='hard',
            source_paper_id=3,
        )
    )

    return citations


@pytest.fixture
def multiple_resolution_results() -> List[ResolutionResult]:  # noqa: UP006
    """Multiple resolution results matching multiple_ground_truth."""
    return [
        # Correct resolution (TP)
        ResolutionResult(
            citation='Murphy, K.P. (2012). "Machine Learning: A Probabilistic Perspective". MIT Press.',
            status=CitationResolutionStatus.RESOLVED,
            confidence_score=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            source='crossref',
            matched_data={
                'doi': '10.5555/2380985',
                'title': 'Machine Learning: A Probabilistic Perspective',
                'authors': ['Murphy, Kevin P.'],
                'year': 2012,
            },
            metadata=ResolutionMetadata(
                api_sources_tried=['crossref'],
                resolution_time_ms=150.0,
                cache_hit=False,
            ),
        ),
        # Incorrect resolution (FP)
        ResolutionResult(
            citation='Goodfellow et al. (2016). "Deep Learning...".',
            status=CitationResolutionStatus.RESOLVED,
            confidence_score=0.70,
            confidence_level=ConfidenceLevel.MEDIUM,
            source='crossref',
            matched_data={
                'doi': '10.9999/wrong.doi',  # Wrong DOI
                'title': 'Deep Learning Basics',
                'authors': ['Goodfellow, Ian'],
                'year': 2016,
            },
            metadata=ResolutionMetadata(
                api_sources_tried=['crossref', 'semantic_scholar'],
                resolution_time_ms=300.0,
                cache_hit=False,
            ),
        ),
        # Failed resolution (FN)
        ResolutionResult(
            citation='"Attention Is All You Need".',
            status=CitationResolutionStatus.FAILED,
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            source='crossref',  # Tried crossref but failed
            matched_data=None,
            metadata=ResolutionMetadata(
                api_sources_tried=['crossref', 'semantic_scholar', 'openalex'],
                resolution_time_ms=500.0,
                cache_hit=False,
            ),
        ),
    ]


@pytest.fixture
def edge_case_empty_results() -> List[ResolutionResult]:  # noqa: UP006
    """All empty/unresolved results for edge case testing."""
    return [
        ResolutionResult(
            citation='Citation 1',
            status=CitationResolutionStatus.FAILED,
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            source='crossref',
            matched_data=None,
        ),
        ResolutionResult(
            citation='Citation 2',
            status=CitationResolutionStatus.FAILED,
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            source='crossref',
            matched_data=None,
        ),
    ]


@pytest.fixture
def edge_case_all_correct() -> tuple:
    """All resolutions are correct (perfect system)."""
    ground_truth = [
        GroundTruthCitation(
            citation=Citation(
                text='Citation 1', title='Title 1', authors=['Author 1'], year=2020
            ),
            ground_truth_doi='10.1234/1',
            ground_truth_title='Title 1',
            ground_truth_authors=['Author 1'],
            ground_truth_year=2020,
            difficulty='easy',
        ),
        GroundTruthCitation(
            citation=Citation(
                text='Citation 2', title='Title 2', authors=['Author 2'], year=2021
            ),
            ground_truth_doi='10.1234/2',
            ground_truth_title='Title 2',
            ground_truth_authors=['Author 2'],
            ground_truth_year=2021,
            difficulty='easy',
        ),
    ]

    results = [
        ResolutionResult(
            citation=ground_truth[0].citation.text,
            status=CitationResolutionStatus.RESOLVED,
            confidence_score=0.99,
            confidence_level=ConfidenceLevel.HIGH,
            source='crossref',
            matched_data={
                'doi': '10.1234/1',
                'title': 'Title 1',
                'authors': ['Author 1'],
                'year': 2020,
            },
        ),
        ResolutionResult(
            citation=ground_truth[1].citation.text,
            status=CitationResolutionStatus.RESOLVED,
            confidence_score=0.98,
            confidence_level=ConfidenceLevel.HIGH,
            source='crossref',
            matched_data={
                'doi': '10.1234/2',
                'title': 'Title 2',
                'authors': ['Author 2'],
                'year': 2021,
            },
        ),
    ]

    return ground_truth, results


@pytest.fixture
def mock_matplotlib_plt(monkeypatch):  # noqa: ARG001
    """Mock matplotlib.pyplot for testing visualization functions."""
    mock_plt = Mock()
    mock_plt.figure = Mock()
    mock_plt.plot = Mock()
    mock_plt.bar = Mock()
    mock_plt.xlabel = Mock()
    mock_plt.ylabel = Mock()
    mock_plt.title = Mock()
    mock_plt.legend = Mock()
    mock_plt.grid = Mock()
    mock_plt.xlim = Mock()
    mock_plt.ylim = Mock()
    mock_plt.tight_layout = Mock()
    mock_plt.savefig = Mock()
    mock_plt.close = Mock()
    mock_plt.annotate = Mock()
    mock_plt.text = Mock()
    mock_plt.fill_between = Mock()
    mock_plt.subplots = Mock(return_value=(Mock(), Mock()))

    return mock_plt


def create_ground_truth_with_confidence(confidence: float, is_correct: bool) -> tuple:
    """Helper to create ground truth and result with specific confidence/correctness."""
    gt = GroundTruthCitation(
        citation=Citation(
            text='Test citation', title='Test Title', authors=['Test Author'], year=2020
        ),
        ground_truth_doi='10.1234/test',
        ground_truth_title='Test Title',
        ground_truth_authors=['Test Author'],
        ground_truth_year=2020,
        difficulty='medium',
    )

    result = ResolutionResult(
        citation=gt.citation.text,
        status=CitationResolutionStatus.RESOLVED,  # Always RESOLVED (correct or incorrect match)
        confidence_score=confidence,
        confidence_level=ConfidenceLevel.HIGH,
        source='crossref',
        matched_data={
            'doi': '10.1234/test'
            if is_correct
            else '10.9999/wrong',  # Wrong DOI when incorrect
            'title': 'Test Title',
            'authors': ['Test Author'],
            'year': 2020,
        },  # Always provide matched_data (correct or incorrect)
    )

    return gt, result

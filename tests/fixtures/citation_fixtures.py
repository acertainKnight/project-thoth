"""
Test fixtures for citation resolution tests.

Provides realistic test data for citation matching, including:
- Valid citations with complete metadata
- Citations with missing fields
- Mock API responses from external services
- Edge cases and error scenarios
"""

from typing import Any, Dict, List
from datetime import datetime

from thoth.utilities.schemas.citations import Citation
from thoth.analyze.citations.resolution_types import (
    APISource,
    CitationResolutionStatus,
    ConfidenceLevel,
    ResolutionResult,
    ResolutionMetadata,
)


# Valid citations with complete metadata
CITATION_WITH_DOI = Citation(
    text="Smith, J., & Doe, A. (2023). Deep Learning for Image Recognition. Nature, 612(7940), 123-145.",
    title="Deep Learning for Image Recognition",
    authors=["Smith, J.", "Doe, A."],
    year=2023,
    doi="10.1038/nature12345",
    journal="Nature",
    volume="612",
    issue="7940",
    pages="123-145"
)

CITATION_WITH_ARXIV = Citation(
    text="Johnson, B. et al. (2024). Attention Is All You Need. arXiv preprint arXiv:2401.12345.",
    title="Attention Is All You Need",
    authors=["Johnson, B.", "Williams, C.", "Brown, D."],
    year=2024,
    arxiv_id="2401.12345",
    backup_id="arxiv:2401.12345"
)

CITATION_WITHOUT_IDENTIFIERS = Citation(
    text="Lee, K., & Park, S. (2022). Machine Learning Applications in Healthcare. Journal of Medical AI, 15(3), 45-67.",
    title="Machine Learning Applications in Healthcare",
    authors=["Lee, K.", "Park, S."],
    year=2022,
    journal="Journal of Medical AI",
    volume="15",
    issue="3",
    pages="45-67"
)

CITATION_MINIMAL = Citation(
    text="Wilson, T. (2021). A Brief Survey of Neural Networks.",
    title="A Brief Survey of Neural Networks",
    authors=["Wilson, T."],
    year=2021
)

CITATION_TITLE_ONLY = Citation(
    title="Transformers for Natural Language Processing"
)

# Citations with variations (for fuzzy matching tests)
CITATION_VARIANT_SUBTITLE = Citation(
    title="Deep Learning for Image Recognition: A Comprehensive Survey",
    authors=["Smith, John", "Doe, Alice"],
    year=2023,
    journal="Nature"
)

CITATION_VARIANT_AUTHOR_FORMAT = Citation(
    title="Deep Learning for Image Recognition",
    authors=["John Smith", "Alice Doe"],
    year=2023,
    journal="Nature"
)

CITATION_VARIANT_YEAR_OFF_BY_ONE = Citation(
    title="Deep Learning for Image Recognition",
    authors=["Smith, J.", "Doe, A."],
    year=2024,  # Off by 1 year
    journal="Nature"
)

# Mock API responses

MOCK_CROSSREF_RESPONSE: Dict[str, Any] = {
    "status": "ok",
    "message-type": "work-list",
    "message": {
        "items": [
            {
                "DOI": "10.1038/nature12345",
                "title": ["Deep Learning for Image Recognition"],
                "author": [
                    {"given": "John", "family": "Smith"},
                    {"given": "Alice", "family": "Doe"}
                ],
                "published-print": {
                    "date-parts": [[2023, 6, 15]]
                },
                "container-title": ["Nature"],
                "volume": "612",
                "issue": "7940",
                "page": "123-145",
                "score": 95.5,
                "URL": "https://doi.org/10.1038/nature12345",
                "abstract": "This paper presents a deep learning approach...",
                "publisher": "Nature Publishing Group",
                "is-referenced-by-count": 156
            },
            {
                "DOI": "10.1109/cvpr.2023.98765",
                "title": ["Deep Learning for Visual Recognition"],
                "author": [
                    {"given": "Jane", "family": "Smith"}
                ],
                "published-print": {
                    "date-parts": [[2023, 8, 1]]
                },
                "container-title": ["IEEE CVPR"],
                "score": 72.3
            }
        ]
    }
}

MOCK_OPENALEX_RESPONSE: Dict[str, Any] = {
    "results": [
        {
            "id": "https://openalex.org/W4123456789",
            "doi": "https://doi.org/10.1038/nature12345",
            "title": "Deep Learning for Image Recognition",
            "display_name": "Deep Learning for Image Recognition",
            "authorships": [
                {"author": {"display_name": "John Smith"}},
                {"author": {"display_name": "Alice Doe"}}
            ],
            "publication_year": 2023,
            "primary_location": {
                "source": {"display_name": "Nature"}
            },
            "open_access": {
                "is_oa": True,
                "oa_url": "https://arxiv.org/pdf/2301.12345.pdf"
            },
            "cited_by_count": 156,
            "abstract_inverted_index": {
                "This": [0],
                "paper": [1],
                "presents": [2],
                "a": [3],
                "deep": [4],
                "learning": [5],
                "approach": [6]
            },
            "topics": [
                {"display_name": "Computer Vision"},
                {"display_name": "Machine Learning"}
            ]
        }
    ]
}

MOCK_SEMANTIC_SCHOLAR_PAPER: Dict[str, Any] = {
    "paperId": "abc123def456",
    "title": "Deep Learning for Image Recognition",
    "abstract": "This paper presents a deep learning approach for image recognition...",
    "year": 2023,
    "venue": "Nature",
    "authors": [
        {"name": "John Smith"},
        {"name": "Alice Doe"}
    ],
    "externalIds": {
        "DOI": "10.1038/nature12345",
        "ArXiv": "2301.12345"
    },
    "citationCount": 156,
    "influentialCitationCount": 42,
    "url": "https://www.semanticscholar.org/paper/abc123",
    "openAccessPdf": {
        "url": "https://arxiv.org/pdf/2301.12345.pdf"
    },
    "fieldsOfStudy": ["Computer Science", "Artificial Intelligence"]
}

MOCK_ARXIV_RESPONSE: str = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v1</id>
    <updated>2024-01-15T00:00:00Z</updated>
    <published>2024-01-15T00:00:00Z</published>
    <title>Attention Is All You Need</title>
    <summary>We propose a new architecture based entirely on attention mechanisms...</summary>
    <author>
      <name>Johnson, B.</name>
    </author>
    <author>
      <name>Williams, C.</name>
    </author>
    <author>
      <name>Brown, D.</name>
    </author>
    <arxiv:doi xmlns:arxiv="http://arxiv.org/schemas/atom">10.1145/arxiv.2401.12345</arxiv:doi>
    <link title="pdf" href="http://arxiv.org/pdf/2401.12345v1" type="application/pdf"/>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>"""

# Expected resolution results for testing

EXPECTED_HIGH_CONFIDENCE_RESULT = ResolutionResult(
    citation="Smith, J., & Doe, A. (2023). Deep Learning for Image Recognition.",
    status=CitationResolutionStatus.RESOLVED,
    confidence_score=0.92,
    confidence_level=ConfidenceLevel.HIGH,
    source=APISource.CROSSREF,
    matched_data={
        "doi": "10.1038/nature12345",
        "title": "Deep Learning for Image Recognition",
        "authors": ["John Smith", "Alice Doe"],
        "year": 2023,
        "journal": "Nature",
        "volume": "612",
        "issue": "7940",
        "pages": "123-145"
    },
    metadata=ResolutionMetadata(
        api_sources_tried=[APISource.CROSSREF],
        processing_time_ms=150.5
    )
)

EXPECTED_UNRESOLVED_RESULT = ResolutionResult(
    citation="Unknown citation without sufficient metadata",
    status=CitationResolutionStatus.UNRESOLVED,
    confidence_score=0.0,
    confidence_level=ConfidenceLevel.LOW,
    source=None,
    matched_data=None,
    metadata=ResolutionMetadata(
        api_sources_tried=[APISource.CROSSREF, APISource.OPENALEX, APISource.SEMANTIC_SCHOLAR],
        processing_time_ms=450.2
    )
)

# Error scenarios

RATE_LIMIT_ERROR_RESPONSE = {
    "status_code": 429,
    "message": "Too Many Requests",
    "headers": {
        "Retry-After": "60"
    }
}

SERVER_ERROR_RESPONSE = {
    "status_code": 503,
    "message": "Service Unavailable"
}

TIMEOUT_ERROR = {
    "error": "RequestTimeout",
    "message": "Request timed out after 30 seconds"
}

# Batch test data

BATCH_CITATIONS: List[Citation] = [
    CITATION_WITH_DOI,
    CITATION_WITH_ARXIV,
    CITATION_WITHOUT_IDENTIFIERS,
    CITATION_MINIMAL,
    CITATION_TITLE_ONLY
]

# Edge cases

CITATION_EMPTY_TITLE = Citation(
    title="",
    authors=["Smith, J."],
    year=2023
)

CITATION_VERY_LONG_TITLE = Citation(
    title="A" * 500,  # 500 character title
    authors=["Doe, J."],
    year=2022
)

CITATION_SPECIAL_CHARACTERS = Citation(
    title="Machine Learning: A Survey (Part I) — Foundations & Applications!",
    authors=["Smith, J.", "O'Brien, K.", "González, M."],
    year=2023,
    journal="AI Review"
)

CITATION_UNICODE = Citation(
    title="深度学习在图像识别中的应用",
    authors=["李明", "王芳"],
    year=2023
)

# Cache test data
CACHE_TEST_CITATIONS = [
    Citation(
        title=f"Test Paper {i}",
        authors=[f"Author {i}"],
        year=2023,
        doi=f"10.1234/test{i:04d}"
    )
    for i in range(10)
]


def create_mock_crossref_match(
    doi: str = "10.1234/test",
    title: str = "Test Paper",
    score: float = 85.0
) -> Dict[str, Any]:
    """Create a mock Crossref match for testing."""
    return {
        "DOI": doi,
        "title": [title],
        "author": [{"given": "Test", "family": "Author"}],
        "published-print": {"date-parts": [[2023, 1, 1]]},
        "container-title": ["Test Journal"],
        "score": score
    }


def create_mock_openalex_match(
    doi: str = "10.1234/test",
    title: str = "Test Paper",
    openalex_id: str = "W123456"
) -> Dict[str, Any]:
    """Create a mock OpenAlex match for testing."""
    return {
        "id": f"https://openalex.org/{openalex_id}",
        "doi": f"https://doi.org/{doi}",
        "display_name": title,
        "authorships": [{"author": {"display_name": "Test Author"}}],
        "publication_year": 2023,
        "primary_location": {"source": {"display_name": "Test Journal"}},
        "open_access": {"is_oa": False},
        "cited_by_count": 10
    }


def create_mock_semantic_scholar_paper(
    doi: str = "10.1234/test",
    title: str = "Test Paper",
    paper_id: str = "abc123"
) -> Dict[str, Any]:
    """Create a mock Semantic Scholar paper for testing."""
    return {
        "paperId": paper_id,
        "title": title,
        "year": 2023,
        "authors": [{"name": "Test Author"}],
        "externalIds": {"DOI": doi},
        "citationCount": 10,
        "abstract": "Test abstract"
    }

"""
Citation Resolution Type Definitions

This module defines the core types and data structures used throughout the citation
resolution system. These types provide type safety and clear contracts for citation
matching, confidence scoring, and API integration.

Key Types:
    - CitationResolutionStatus: Resolution outcome states
    - ConfidenceLevel: Confidence classification levels
    - APISource: Supported external API sources
    - ResolutionResult: Complete resolution outcome with metadata
    - MatchCandidate: Individual candidate match with scoring
    - ResolutionMetadata: Resolution attempt tracking and diagnostics
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional  # noqa: UP035

from pydantic import BaseModel, Field, field_validator


class CitationResolutionStatus(str, Enum):
    """
    Status of a citation resolution attempt.

    Attributes:
        RESOLVED: Successfully resolved with high confidence
        PARTIAL: Resolved with lower confidence or incomplete data
        MANUAL_REVIEW: Requires human review due to ambiguity
        UNRESOLVED: Could not be resolved with available data
        FAILED: Resolution attempt failed due to errors
        PENDING: Resolution not yet attempted or in progress
    """

    RESOLVED = 'resolved'
    PARTIAL = 'partial'
    MANUAL_REVIEW = 'manual_review'
    UNRESOLVED = 'unresolved'
    FAILED = 'failed'
    PENDING = 'pending'


class ConfidenceLevel(str, Enum):
    """
    Confidence level classification for resolution results.

    Typically maps to score ranges:
        HIGH: 0.85-1.0
        MEDIUM: 0.60-0.84
        LOW: 0.0-0.59
    """

    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'


class APISource(str, Enum):
    """
    External API sources supported for citation resolution.

    Attributes:
        CROSSREF: CrossRef API for DOI and metadata
        OPENALEX: OpenAlex API for open citation data
        SEMANTIC_SCHOLAR: Semantic Scholar API for ML-enhanced matching
        ARXIV: arXiv API for preprints and technical papers
    """

    CROSSREF = 'crossref'
    OPENALEX = 'openalex'
    SEMANTIC_SCHOLAR = 'semantic_scholar'
    ARXIV = 'arxiv'


class MatchCandidate(BaseModel):
    """
    A candidate match from an external API source.

    Represents a potential match for a citation, including the raw candidate
    data, overall matching score, and detailed component scores for debugging
    and refinement.

    Attributes:
        candidate_data: Raw data from the API source
        raw_score: Overall matching score (0.0-1.0)
        component_scores: Breakdown of individual matching component scores
        source: API source that provided this candidate
        matched_at: Timestamp when match was evaluated
    """

    candidate_data: Dict[str, Any] = Field(  # noqa: UP006
        description='Raw candidate data from the API source'
    )
    raw_score: float = Field(
        ge=0.0, le=1.0, description='Overall matching score between 0.0 and 1.0'
    )
    component_scores: Dict[str, float] = Field(  # noqa: UP006
        default_factory=dict,
        description='Individual component scores (title, author, year, etc.)',
    )
    source: APISource = Field(description='API source that provided this candidate')
    matched_at: datetime = Field(
        default_factory=datetime.utcnow,
        description='Timestamp when match was evaluated',
    )

    @field_validator('component_scores')
    @classmethod
    def validate_component_scores(cls, v: Dict[str, float]) -> Dict[str, float]:  # noqa: UP006
        """Validate that all component scores are in valid range [0.0, 1.0]."""
        for component, score in v.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"Component score '{component}' must be between 0.0 and 1.0, "
                    f'got {score}'
                )
        return v

    class Config:
        json_schema_extra = {  # noqa: RUF012
            'example': {
                'candidate_data': {
                    'doi': '10.1234/example',
                    'title': 'Example Research Paper',
                    'authors': ['Smith, J.', 'Doe, A.'],
                },
                'raw_score': 0.87,
                'component_scores': {'title': 0.92, 'author': 0.85, 'year': 1.0},
                'source': 'crossref',
                'matched_at': '2025-12-29T10:30:00Z',
            }
        }


class ResolutionMetadata(BaseModel):
    """
    Metadata tracking resolution attempts and diagnostics.

    Provides detailed information about resolution attempts, including retry
    count, timing, errors, and which API sources were consulted.

    Attributes:
        attempt_count: Number of resolution attempts made
        last_attempt_time: Timestamp of most recent attempt
        error_message: Error details if resolution failed
        api_sources_tried: List of API sources consulted
        processing_time_ms: Time taken for resolution in milliseconds
        additional_info: Arbitrary additional diagnostic information
    """

    attempt_count: int = Field(
        default=0, ge=0, description='Number of resolution attempts made'
    )
    last_attempt_time: Optional[datetime] = Field(  # noqa: UP007
        default=None, description='Timestamp of most recent resolution attempt'
    )
    error_message: Optional[str] = Field(  # noqa: UP007
        default=None, description='Error message if resolution failed'
    )
    api_sources_tried: List[APISource] = Field(  # noqa: UP006
        default_factory=list,
        description='List of API sources consulted during resolution',
    )
    processing_time_ms: Optional[float] = Field(  # noqa: UP007
        default=None, ge=0.0, description='Processing time in milliseconds'
    )
    additional_info: Dict[str, Any] = Field(  # noqa: UP006
        default_factory=dict,
        description='Additional diagnostic or contextual information',
    )

    class Config:
        json_schema_extra = {  # noqa: RUF012
            'example': {
                'attempt_count': 2,
                'last_attempt_time': '2025-12-29T10:30:00Z',
                'error_message': None,
                'api_sources_tried': ['crossref', 'openalex'],
                'processing_time_ms': 245.3,
                'additional_info': {'cache_hit': False, 'rate_limited': False},
            }
        }


class ResolutionResult(BaseModel):
    """
    Complete result of a citation resolution attempt.

    Encapsulates all information about a citation resolution, including the
    original citation text, resolution status, matched data, confidence metrics,
    and diagnostic metadata.

    Attributes:
        citation: Original citation text that was resolved
        status: Resolution outcome status
        confidence_score: Numerical confidence score (0.0-1.0)
        confidence_level: Categorized confidence level
        source: Primary API source used for resolution
        matched_data: Resolved citation data if successful
        candidates: List of all candidate matches considered
        metadata: Resolution attempt metadata and diagnostics
        resolved_at: Timestamp when resolution completed
    """

    citation: str = Field(description='Original citation text to be resolved')
    status: CitationResolutionStatus = Field(description='Resolution outcome status')
    confidence_score: float = Field(
        ge=0.0, le=1.0, description='Numerical confidence score between 0.0 and 1.0'
    )
    confidence_level: ConfidenceLevel = Field(
        description='Categorized confidence level (HIGH/MEDIUM/LOW)'
    )
    source: Optional[APISource] = Field(  # noqa: UP007
        default=None, description='Primary API source used for resolution'
    )
    matched_data: Optional[Dict[str, Any]] = Field(  # noqa: UP006, UP007
        default=None, description='Resolved citation data if successful'
    )
    candidates: List[MatchCandidate] = Field(  # noqa: UP006
        default_factory=list,
        description='All candidate matches considered during resolution',
    )
    metadata: ResolutionMetadata = Field(
        default_factory=ResolutionMetadata,
        description='Resolution attempt metadata and diagnostics',
    )
    resolved_at: datetime = Field(
        default_factory=datetime.utcnow,
        description='Timestamp when resolution completed',
    )

    @field_validator('confidence_level', mode='before')
    @classmethod
    def derive_confidence_level(cls, v: Any, info) -> ConfidenceLevel:
        """
        Automatically derive confidence level from confidence score if not provided.

        Uses standard thresholds:
            >= 0.85: HIGH
            >= 0.60: MEDIUM
            < 0.60: LOW
        """
        if isinstance(v, ConfidenceLevel):
            return v

        # Access confidence_score from validation info
        confidence_score = info.data.get('confidence_score', 0.0)

        if confidence_score >= 0.85:
            return ConfidenceLevel.HIGH
        elif confidence_score >= 0.60:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    class Config:
        json_schema_extra = {  # noqa: RUF012
            'example': {
                'citation': 'Smith, J. et al. (2024). Example Paper. Nature 123:456-789.',
                'status': 'resolved',
                'confidence_score': 0.87,
                'confidence_level': 'high',
                'source': 'crossref',
                'matched_data': {
                    'doi': '10.1038/nature12345',
                    'title': 'Example Paper',
                    'authors': ['Smith, J.', 'Doe, A.', 'Johnson, B.'],
                    'year': 2024,
                    'journal': 'Nature',
                    'volume': '123',
                    'pages': '456-789',
                },
                'candidates': [],
                'metadata': {
                    'attempt_count': 1,
                    'api_sources_tried': ['crossref'],
                    'processing_time_ms': 180.5,
                },
                'resolved_at': '2025-12-29T10:30:00Z',
            }
        }


# Type aliases for common use cases
CitationDict = Dict[str, Any]  # noqa: UP006
"""Type alias for citation dictionaries"""

ScoreDict = Dict[str, float]  # noqa: UP006
"""Type alias for score dictionaries"""

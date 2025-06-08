"""Pydantic schemas for Thoth."""

from .analysis import AnalysisResponse, AnalysisState
from .citations import (
    ArxivPaper,
    Citation,
    CitationExtraction,
    CitationExtractionResponse,
    OpenCitation,
    OpenCitationsResponse,
    ReferencesSection,
)
from .discovery import (
    BrowserRecording,
    ChromeExtensionConfig,
    DiscoveryResult,
    DiscoverySource,
    ScheduleConfig,
    ScrapeConfiguration,
    ScrapedArticleMetadata,
)
from .queries import (
    FilterLogEntry,
    PreDownloadEvaluationResponse,
    QueryEvaluationResponse,
    QueryRefinementSuggestion,
    ResearchAgentState,
    ResearchQuery,
)
from .search import SearchResponse, SearchResult
from .tags import (
    ConsolidatedTagsResponse,
    SingleTagMappingResponse,
    TagConsolidationResponse,
    TagSuggestionResponse,
)

__all__ = [
    'AnalysisResponse',
    'AnalysisState',
    'ArxivPaper',
    'BrowserRecording',
    'ChromeExtensionConfig',
    'Citation',
    'CitationExtraction',
    'CitationExtractionResponse',
    'ConsolidatedTagsResponse',
    'DiscoveryResult',
    'DiscoverySource',
    'FilterLogEntry',
    'OpenCitation',
    'OpenCitationsResponse',
    'PreDownloadEvaluationResponse',
    'QueryEvaluationResponse',
    'QueryRefinementSuggestion',
    'ReferencesSection',
    'ResearchAgentState',
    'ResearchQuery',
    'ScheduleConfig',
    'ScrapeConfiguration',
    'ScrapedArticleMetadata',
    'SearchResponse',
    'SearchResult',
    'SingleTagMappingResponse',
    'TagConsolidationResponse',
    'TagSuggestionResponse',
]

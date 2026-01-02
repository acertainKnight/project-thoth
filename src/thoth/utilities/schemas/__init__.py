"""Pydantic schemas for Thoth."""

from .analysis import AnalysisResponse, AnalysisState
from .browser_workflow import (
    ActionType,
    BrowserWorkflow,
    BrowserWorkflowCreate,
    BrowserWorkflowUpdate,
    CredentialType,
    ElementSelector,
    ExecutionParameters,
    ExecutionStatus,
    ExecutionTrigger,
    FilterType,
    HealthStatus,
    KeywordsFormat,
    SearchFilter,
    SearchType,
    SelectorStrategy,
    WaitCondition,
    WorkflowAction,
    WorkflowCredentials,
    WorkflowExecution,
    WorkflowSearchConfig,
)
from .citations import (
    ArxivPaper,
    Citation,
    CitationExtraction,
    CitationExtractionResponse,
    Citations,
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
    Recommendation,
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

__all__ = [  # noqa: RUF022
    # Analysis
    'AnalysisResponse',
    'AnalysisState',
    # Browser Workflow
    'ActionType',
    'BrowserWorkflow',
    'BrowserWorkflowCreate',
    'BrowserWorkflowUpdate',
    'CredentialType',
    'ElementSelector',
    'ExecutionParameters',
    'ExecutionStatus',
    'ExecutionTrigger',
    'FilterType',
    'HealthStatus',
    'KeywordsFormat',
    'SearchFilter',
    'SearchType',
    'SelectorStrategy',
    'WaitCondition',
    'WorkflowAction',
    'WorkflowCredentials',
    'WorkflowExecution',
    'WorkflowSearchConfig',
    # Citations
    'ArxivPaper',
    'Citation',
    'CitationExtraction',
    'CitationExtractionResponse',
    'Citations',
    'OpenCitation',
    'OpenCitationsResponse',
    'ReferencesSection',
    # Discovery
    'BrowserRecording',
    'ChromeExtensionConfig',
    'DiscoveryResult',
    'DiscoverySource',
    'ScheduleConfig',
    'ScrapeConfiguration',
    'ScrapedArticleMetadata',
    # Queries
    'FilterLogEntry',
    'PreDownloadEvaluationResponse',
    'QueryEvaluationResponse',
    'QueryRefinementSuggestion',
    'Recommendation',
    'ResearchAgentState',
    'ResearchQuery',
    # Search
    'SearchResponse',
    'SearchResult',
    # Tags
    'ConsolidatedTagsResponse',
    'SingleTagMappingResponse',
    'TagConsolidationResponse',
    'TagSuggestionResponse',
]

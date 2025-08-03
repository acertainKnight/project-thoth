"""
MCP Tools Package

This package contains all MCP-compliant tools for the Thoth research assistant.
"""

# Import the base classes from the parent base_tools module
from ..base_tools import MCPTool, MCPToolCallResult, MCPToolRegistry
from .advanced_rag_tools import (
    CreateCustomIndexMCPTool,
    OptimizeSearchMCPTool,
    ReindexCollectionMCPTool,
)
from .analysis_tools import (
    AnalyzeTopicMCPTool,
    EvaluateArticleMCPTool,
    FindRelatedPapersMCPTool,
    GenerateResearchSummaryMCPTool,
)
from .article_tools import (
    DeleteArticleMCPTool,
    SearchArticlesMCPTool,
    UpdateArticleMetadataMCPTool,
)
from .citation_tools import (
    ExportBibliographyMCPTool,
    ExtractCitationsMCPTool,
    FormatCitationsMCPTool,
)
from .data_management_tools import (
    BackupCollectionMCPTool,
    ExportArticleDataMCPTool,
    GenerateReadingListMCPTool,
    SyncWithObsidianMCPTool,
)
from .discovery_tools import (
    CreateArxivSourceMCPTool,
    CreateBiorxivSourceMCPTool,
    CreateCrossrefSourceMCPTool,
    CreateOpenalexSourceMCPTool,
    CreatePubmedSourceMCPTool,
    DeleteDiscoverySourceMCPTool,
    GetDiscoverySourceMCPTool,
    ListDiscoverySourcesMCPTool,
    RunDiscoveryMCPTool,
)
from .download_pdf_tool import (
    DownloadPdfMCPTool,
)
from .pdf_content_tools import (
    ExtractPdfMetadataMCPTool,
    LocatePdfMCPTool,
    ValidatePdfSourcesMCPTool,
)
from .processing_tools import (
    BatchProcessPdfsMCPTool,
    CollectionStatsMCPTool,
    GetArticleDetailsMCPTool,
    ListArticlesMCPTool,
    ProcessPdfMCPTool,
)
from .query_tools import (
    CreateQueryMCPTool,
    DeleteQueryMCPTool,
    GetQueryMCPTool,
    ListQueriesMCPTool,
    UpdateQueryMCPTool,
)
from .tag_tools import (
    ConsolidateAndRetagMCPTool,
    ConsolidateTagsMCPTool,
    ManageTagVocabularyMCPTool,
    SuggestTagsMCPTool,
)
from .web_search_tool import (
    WebSearchMCPTool,
)

# List of all available MCP tool classes
MCP_TOOL_CLASSES = [
    # Query management tools
    ListQueriesMCPTool,
    CreateQueryMCPTool,
    GetQueryMCPTool,
    UpdateQueryMCPTool,
    DeleteQueryMCPTool,
    # Discovery source tools
    ListDiscoverySourcesMCPTool,
    CreateArxivSourceMCPTool,
    CreatePubmedSourceMCPTool,
    CreateCrossrefSourceMCPTool,
    CreateOpenalexSourceMCPTool,
    CreateBiorxivSourceMCPTool,
    GetDiscoverySourceMCPTool,
    RunDiscoveryMCPTool,
    DeleteDiscoverySourceMCPTool,
    # Processing tools
    ProcessPdfMCPTool,
    BatchProcessPdfsMCPTool,
    GetArticleDetailsMCPTool,
    ListArticlesMCPTool,
    CollectionStatsMCPTool,
    # Article search and management tools
    SearchArticlesMCPTool,
    UpdateArticleMetadataMCPTool,
    DeleteArticleMCPTool,
    # Tag management tools
    ConsolidateTagsMCPTool,
    SuggestTagsMCPTool,
    ManageTagVocabularyMCPTool,
    ConsolidateAndRetagMCPTool,
    # Citation and bibliography tools
    FormatCitationsMCPTool,
    ExportBibliographyMCPTool,
    ExtractCitationsMCPTool,
    # Analysis and intelligence tools
    EvaluateArticleMCPTool,
    AnalyzeTopicMCPTool,
    FindRelatedPapersMCPTool,
    GenerateResearchSummaryMCPTool,
    # Data management and export tools
    BackupCollectionMCPTool,
    ExportArticleDataMCPTool,
    GenerateReadingListMCPTool,
    SyncWithObsidianMCPTool,
    # PDF and content tools
    LocatePdfMCPTool,
    ValidatePdfSourcesMCPTool,
    ExtractPdfMetadataMCPTool,
    DownloadPdfMCPTool,
    # Web search tools
    WebSearchMCPTool,
    # Advanced RAG tools
    ReindexCollectionMCPTool,
    OptimizeSearchMCPTool,
    CreateCustomIndexMCPTool,
]


def register_all_mcp_tools(registry: MCPToolRegistry) -> None:
    """
    Register all MCP tools with the registry.

    Args:
        registry: MCPToolRegistry instance to register tools with
    """
    for tool_class in MCP_TOOL_CLASSES:
        registry.register_class(tool_class)


__all__ = [
    'MCP_TOOL_CLASSES',
    'AnalyzeTopicMCPTool',
    'BackupCollectionMCPTool',
    'BatchProcessPdfsMCPTool',
    'CollectionStatsMCPTool',
    'ConsolidateAndRetagMCPTool',
    'ConsolidateTagsMCPTool',
    'CreateArxivSourceMCPTool',
    'CreateBiorxivSourceMCPTool',
    'CreateCrossrefSourceMCPTool',
    'CreateCustomIndexMCPTool',
    'CreateOpenalexSourceMCPTool',
    'CreatePubmedSourceMCPTool',
    'CreateQueryMCPTool',
    'DeleteArticleMCPTool',
    'DeleteDiscoverySourceMCPTool',
    'DeleteQueryMCPTool',
    'DownloadPdfMCPTool',
    'EvaluateArticleMCPTool',
    'ExportArticleDataMCPTool',
    'ExportBibliographyMCPTool',
    'ExtractCitationsMCPTool',
    'ExtractPdfMetadataMCPTool',
    'FindRelatedPapersMCPTool',
    'FormatCitationsMCPTool',
    'GenerateReadingListMCPTool',
    'GenerateResearchSummaryMCPTool',
    'GetArticleDetailsMCPTool',
    'GetDiscoverySourceMCPTool',
    'GetQueryMCPTool',
    'ListArticlesMCPTool',
    'ListDiscoverySourcesMCPTool',
    'ListQueriesMCPTool',
    'LocatePdfMCPTool',
    'MCPTool',
    'MCPToolCallResult',
    'MCPToolRegistry',
    'ManageTagVocabularyMCPTool',
    'OptimizeSearchMCPTool',
    'ProcessPdfMCPTool',
    'ReindexCollectionMCPTool',
    'RunDiscoveryMCPTool',
    'SearchArticlesMCPTool',
    'SuggestTagsMCPTool',
    'SyncWithObsidianMCPTool',
    'UpdateArticleMetadataMCPTool',
    'UpdateQueryMCPTool',
    'ValidatePdfSourcesMCPTool',
    'WebSearchMCPTool',
    'register_all_mcp_tools',
]

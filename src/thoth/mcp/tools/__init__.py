"""
MCP Tools Package

This package contains all MCP-compliant tools for the Thoth research assistant.
"""

# Import the base classes from the parent base_tools module
from ..base_tools import MCPTool, MCPToolCallResult, MCPToolRegistry  # noqa: I001
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
    GetTaskStatusMCPTool,
    ManageTagVocabularyMCPTool,
    SuggestTagsMCPTool,
)
from .web_search_tool import (
    WebSearchMCPTool,
)
from .browser_workflow_tools import (
    CreateBrowserWorkflowMCPTool,
    AddWorkflowActionMCPTool,
    ConfigureSearchMCPTool,
    ExecuteWorkflowMCPTool,
    ListWorkflowsMCPTool,
    GetWorkflowDetailsMCPTool,
    UpdateWorkflowStatusMCPTool,
    DeleteWorkflowMCPTool,
)
from .schema_tools import (
    GetSchemaInfoTool,
    ListSchemaPresetsTool,
    SetSchemaPresetTool,
    GetPresetDetailsTool,
    ValidateSchemaFileTool,
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
    GetTaskStatusMCPTool,
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
    # Browser workflow tools
    CreateBrowserWorkflowMCPTool,
    AddWorkflowActionMCPTool,
    ConfigureSearchMCPTool,
    ExecuteWorkflowMCPTool,
    ListWorkflowsMCPTool,
    GetWorkflowDetailsMCPTool,
    UpdateWorkflowStatusMCPTool,
    DeleteWorkflowMCPTool,
    # Schema management tools
    GetSchemaInfoTool,
    ListSchemaPresetsTool,
    SetSchemaPresetTool,
    GetPresetDetailsTool,
    ValidateSchemaFileTool,
]


def register_all_mcp_tools(registry: MCPToolRegistry) -> None:
    """
    Register all MCP tools with the registry.

    Args:
        registry: MCPToolRegistry instance to register tools with
    """
    for tool_class in MCP_TOOL_CLASSES:
        registry.register_class(tool_class)


__all__ = [  # noqa: RUF022
    'MCP_TOOL_CLASSES',
    'AddWorkflowActionMCPTool',
    'AnalyzeTopicMCPTool',
    'BackupCollectionMCPTool',
    'BatchProcessPdfsMCPTool',
    'CollectionStatsMCPTool',
    'ConfigureSearchMCPTool',
    'ConsolidateAndRetagMCPTool',
    'ConsolidateTagsMCPTool',
    'CreateBrowserWorkflowMCPTool',
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
    'DeleteWorkflowMCPTool',
    'DownloadPdfMCPTool',
    'EvaluateArticleMCPTool',
    'ExecuteWorkflowMCPTool',
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
    'GetTaskStatusMCPTool',
    'GetWorkflowDetailsMCPTool',
    'ListArticlesMCPTool',
    'ListDiscoverySourcesMCPTool',
    'ListQueriesMCPTool',
    'ListWorkflowsMCPTool',
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
    'UpdateWorkflowStatusMCPTool',
    'ValidatePdfSourcesMCPTool',
    'WebSearchMCPTool',
    'register_all_mcp_tools',
]

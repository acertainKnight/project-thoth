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
# REMOVED: discovery_tools.py - deprecated in favor of research_question_tools.py
# Old tools incorrectly treated ArXiv/PubMed as user-created "sources"
# New research question tools properly separate concerns:
#   - Built-in APIs (arxiv, pubmed) are sources you SELECT from
#   - Research questions define WHAT to search for and WHICH sources to use
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
from .research_question_tools import (
    CreateResearchQuestionMCPTool,
    DeleteResearchQuestionMCPTool,
    GetResearchQuestionMCPTool,
    ListAvailableSourcesMCPTool,
    ListResearchQuestionsMCPTool,
    RunDiscoveryForQuestionMCPTool,
    UpdateResearchQuestionMCPTool,
)
from .research_qa_tools import (
    AnswerResearchQuestionMCPTool,
    ExploreCitationNetworkMCPTool,
    CompareArticlesMCPTool,
    ExtractArticleInsightsMCPTool,
    SearchByTopicMCPTool,
    GetArticleFullContentMCPTool,
    FindArticlesByAuthorsMCPTool,
    GetCitationContextMCPTool,
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
    # Research question tools (NEW - replaces old discovery source tools)
    ListAvailableSourcesMCPTool,
    CreateResearchQuestionMCPTool,
    ListResearchQuestionsMCPTool,
    GetResearchQuestionMCPTool,
    UpdateResearchQuestionMCPTool,
    DeleteResearchQuestionMCPTool,
    RunDiscoveryForQuestionMCPTool,
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
    # Research Q&A tools (NEW - comprehensive research and analysis)
    AnswerResearchQuestionMCPTool,
    ExploreCitationNetworkMCPTool,
    CompareArticlesMCPTool,
    ExtractArticleInsightsMCPTool,
    SearchByTopicMCPTool,
    GetArticleFullContentMCPTool,
    FindArticlesByAuthorsMCPTool,
    GetCitationContextMCPTool,
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
    'AnswerResearchQuestionMCPTool',
    'BackupCollectionMCPTool',
    'BatchProcessPdfsMCPTool',
    'CollectionStatsMCPTool',
    'CompareArticlesMCPTool',
    'ConfigureSearchMCPTool',
    'ConsolidateAndRetagMCPTool',
    'ConsolidateTagsMCPTool',
    'CreateBrowserWorkflowMCPTool',
    'CreateCustomIndexMCPTool',
    'CreateQueryMCPTool',
    'CreateResearchQuestionMCPTool',
    'DeleteArticleMCPTool',
    'DeleteQueryMCPTool',
    'DeleteResearchQuestionMCPTool',
    'DeleteWorkflowMCPTool',
    'DownloadPdfMCPTool',
    'EvaluateArticleMCPTool',
    'ExecuteWorkflowMCPTool',
    'ExportArticleDataMCPTool',
    'ExploreCitationNetworkMCPTool',
    'ExportBibliographyMCPTool',
    'ExtractArticleInsightsMCPTool',
    'ExtractCitationsMCPTool',
    'ExtractPdfMetadataMCPTool',
    'FindArticlesByAuthorsMCPTool',
    'FindRelatedPapersMCPTool',
    'FormatCitationsMCPTool',
    'GenerateReadingListMCPTool',
    'GenerateResearchSummaryMCPTool',
    'GetArticleDetailsMCPTool',
    'GetArticleFullContentMCPTool',
    'GetCitationContextMCPTool',
    'GetQueryMCPTool',
    'GetResearchQuestionMCPTool',
    'GetTaskStatusMCPTool',
    'GetWorkflowDetailsMCPTool',
    'ListArticlesMCPTool',
    'ListAvailableSourcesMCPTool',
    'ListResearchQuestionsMCPTool',
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
    'RunDiscoveryForQuestionMCPTool',
    'SearchArticlesMCPTool',
    'SearchByTopicMCPTool',
    'SuggestTagsMCPTool',
    'SyncWithObsidianMCPTool',
    'UpdateArticleMetadataMCPTool',
    'UpdateQueryMCPTool',
    'UpdateResearchQuestionMCPTool',
    'UpdateWorkflowStatusMCPTool',
    'ValidatePdfSourcesMCPTool',
    'WebSearchMCPTool',
    'register_all_mcp_tools',
]

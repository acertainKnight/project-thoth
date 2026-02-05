"""
MCP Tools Package

This package contains all MCP-compliant tools for the Thoth research assistant.

DEPRECATED TOOLS (code kept for backwards compatibility, not registered):
- process_pdf, batch_process_pdfs, extract_pdf_metadata: Use PDF monitor service
- analyze_topic, search_by_topic, generate_research_summary: Redundant with answer_research_question
- extract_article_insights, get_article_full_content: Merged into get_article_details
- find_articles_by_authors: Use search_articles with author filter
- extract_citations: Merged into explore_citation_network
- suggest_tags: Low value, rarely used
- backup_collection, restore_collection_backup, export_article_data, delete_article: Admin tasks
- thoth_web_search: Use Letta's built-in web search
- All browser workflow tools: Complex, rarely used
- Legacy query tools: Replaced by research_question tools
"""

# Import the base classes from the parent base_tools module
from ..base_tools import MCPTool, MCPToolCallResult, MCPToolRegistry  # noqa: I001

# Active tools
from .advanced_rag_tools import (
    CreateCustomIndexMCPTool,
    OptimizeSearchMCPTool,
    ReindexCollectionMCPTool,
)
from .analysis_tools import (
    EvaluateArticleMCPTool,
    FindRelatedPapersMCPTool,
    # DEPRECATED: AnalyzeTopicMCPTool - redundant with answer_research_question
    # DEPRECATED: GenerateResearchSummaryMCPTool - redundant with answer_research_question
    AnalyzeTopicMCPTool,  # Keep import for backwards compatibility
    GenerateResearchSummaryMCPTool,  # Keep import for backwards compatibility
)
from .article_tools import (
    SearchArticlesMCPTool,
    UpdateArticleMetadataMCPTool,
    # DEPRECATED: DeleteArticleMCPTool - too risky for agent use
    DeleteArticleMCPTool,  # Keep import for backwards compatibility
)
from .citation_tools import (
    ExportBibliographyMCPTool,
    FormatCitationsMCPTool,
    # DEPRECATED: ExtractCitationsMCPTool - merged into explore_citation_network
    ExtractCitationsMCPTool,  # Keep import for backwards compatibility
)
from .custom_index_tools import (
    ListCustomIndexesMCPTool,
    SearchCustomIndexMCPTool,
)
from .data_management_tools import (
    GenerateReadingListMCPTool,
    SyncWithObsidianMCPTool,
    # DEPRECATED: Admin tasks, not agent-facing
    BackupCollectionMCPTool,  # Keep import for backwards compatibility
    ExportArticleDataMCPTool,  # Keep import for backwards compatibility
    RestoreCollectionBackupMCPTool,  # Keep import for backwards compatibility
)
from .download_pdf_tool import (
    DownloadPdfMCPTool,
)
from .pdf_content_tools import (
    LocatePdfMCPTool,
    # DEPRECATED: Use PDF monitor service
    ExtractPdfMetadataMCPTool,  # Keep import for backwards compatibility
    ValidatePdfSourcesMCPTool,  # Keep import for backwards compatibility
)
from .processing_tools import (
    CollectionStatsMCPTool,
    GetArticleDetailsMCPTool,
    ListArticlesMCPTool,
    # DEPRECATED: Use PDF monitor service
    ProcessPdfMCPTool,  # Keep import for backwards compatibility
    BatchProcessPdfsMCPTool,  # Keep import for backwards compatibility
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
    CompareArticlesMCPTool,
    ExploreCitationNetworkMCPTool,
    GetCitationContextMCPTool,
    # DEPRECATED: Redundant tools
    ExtractArticleInsightsMCPTool,  # Keep import for backwards compatibility
    FindArticlesByAuthorsMCPTool,  # Keep import for backwards compatibility
    GetArticleFullContentMCPTool,  # Keep import for backwards compatibility
    SearchByTopicMCPTool,  # Keep import for backwards compatibility
)
from .schema_tools import (
    GetPresetDetailsTool,
    GetSchemaInfoTool,
    ListSchemaPresetsTool,
    SetSchemaPresetTool,
    ValidateSchemaFileTool,
)
from .settings_tools import (
    MigrateSettingsMCPTool,
    ResetSettingsMCPTool,
    UpdateSettingsMCPTool,
    ValidateSettingsMCPTool,
    ViewSettingsMCPTool,
)
from .skill_tools import (
    ListSkillsMCPTool,
    LoadSkillMCPTool,
    UnloadSkillMCPTool,
)
from .tag_tools import (
    ConsolidateAndRetagMCPTool,
    ConsolidateTagsMCPTool,
    GetTaskStatusMCPTool,
    ManageTagVocabularyMCPTool,
    # DEPRECATED: SuggestTagsMCPTool - low value
    SuggestTagsMCPTool,  # Keep import for backwards compatibility
)

# DEPRECATED: Keep imports for backwards compatibility only
from .browser_workflow_tools import (
    AddWorkflowActionMCPTool,
    ConfigureSearchMCPTool,
    CreateBrowserWorkflowMCPTool,
    DeleteWorkflowMCPTool,
    ExecuteWorkflowMCPTool,
    GetWorkflowDetailsMCPTool,
    ListWorkflowsMCPTool,
    UpdateWorkflowStatusMCPTool,
)
from .query_tools import (
    CreateQueryMCPTool,
    DeleteQueryMCPTool,
    GetQueryMCPTool,
    ListQueriesMCPTool,
    UpdateQueryMCPTool,
)
from .web_search_tool import (
    WebSearchMCPTool,
)

# List of ACTIVE MCP tool classes (deprecated tools excluded)
MCP_TOOL_CLASSES = [
    # Discovery and research questions
    ListAvailableSourcesMCPTool,
    CreateResearchQuestionMCPTool,
    ListResearchQuestionsMCPTool,
    GetResearchQuestionMCPTool,
    UpdateResearchQuestionMCPTool,
    DeleteResearchQuestionMCPTool,
    RunDiscoveryForQuestionMCPTool,
    # Collection management
    GetArticleDetailsMCPTool,
    ListArticlesMCPTool,
    CollectionStatsMCPTool,
    SearchArticlesMCPTool,
    UpdateArticleMetadataMCPTool,
    # Analysis tools
    AnswerResearchQuestionMCPTool,
    ExploreCitationNetworkMCPTool,
    CompareArticlesMCPTool,
    EvaluateArticleMCPTool,
    FindRelatedPapersMCPTool,
    GetCitationContextMCPTool,
    # PDF tools
    DownloadPdfMCPTool,
    LocatePdfMCPTool,
    # Citation and bibliography
    FormatCitationsMCPTool,
    ExportBibliographyMCPTool,
    # Tag management
    ConsolidateTagsMCPTool,
    ManageTagVocabularyMCPTool,
    ConsolidateAndRetagMCPTool,
    GetTaskStatusMCPTool,
    # Data management
    GenerateReadingListMCPTool,
    SyncWithObsidianMCPTool,
    # Advanced RAG tools (loaded via skill)
    ReindexCollectionMCPTool,
    OptimizeSearchMCPTool,
    CreateCustomIndexMCPTool,
    SearchCustomIndexMCPTool,
    ListCustomIndexesMCPTool,
    # Schema management
    GetSchemaInfoTool,
    ListSchemaPresetsTool,
    SetSchemaPresetTool,
    GetPresetDetailsTool,
    ValidateSchemaFileTool,
    # Settings management (loaded via skill)
    ViewSettingsMCPTool,
    UpdateSettingsMCPTool,
    ValidateSettingsMCPTool,
    MigrateSettingsMCPTool,
    ResetSettingsMCPTool,
    # Skill management
    ListSkillsMCPTool,
    LoadSkillMCPTool,
    UnloadSkillMCPTool,
]

# Deprecated tools - kept for backwards compatibility, not registered
DEPRECATED_TOOL_CLASSES = [
    # Query tools - replaced by research_question_tools
    ListQueriesMCPTool,
    CreateQueryMCPTool,
    GetQueryMCPTool,
    UpdateQueryMCPTool,
    DeleteQueryMCPTool,
    # PDF processing - use PDF monitor service
    ProcessPdfMCPTool,
    BatchProcessPdfsMCPTool,
    ExtractPdfMetadataMCPTool,
    ValidatePdfSourcesMCPTool,
    # Analysis - redundant with answer_research_question
    AnalyzeTopicMCPTool,
    GenerateResearchSummaryMCPTool,
    ExtractArticleInsightsMCPTool,
    SearchByTopicMCPTool,
    GetArticleFullContentMCPTool,
    FindArticlesByAuthorsMCPTool,
    # Citation - merged into explore_citation_network
    ExtractCitationsMCPTool,
    # Tags - low value
    SuggestTagsMCPTool,
    # Data management - admin tasks
    BackupCollectionMCPTool,
    ExportArticleDataMCPTool,
    RestoreCollectionBackupMCPTool,
    DeleteArticleMCPTool,
    # Web search - use Letta's built-in
    WebSearchMCPTool,
    # Browser workflow - complex, rarely used
    CreateBrowserWorkflowMCPTool,
    AddWorkflowActionMCPTool,
    ConfigureSearchMCPTool,
    ExecuteWorkflowMCPTool,
    ListWorkflowsMCPTool,
    GetWorkflowDetailsMCPTool,
    UpdateWorkflowStatusMCPTool,
    DeleteWorkflowMCPTool,
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
    # Lists
    'DEPRECATED_TOOL_CLASSES',
    'MCP_TOOL_CLASSES',
    # Base classes
    'MCPTool',
    'MCPToolCallResult',
    'MCPToolRegistry',
    # Active tools (alphabetical)
    'AnswerResearchQuestionMCPTool',
    'CollectionStatsMCPTool',
    'CompareArticlesMCPTool',
    'ConsolidateAndRetagMCPTool',
    'ConsolidateTagsMCPTool',
    'CreateCustomIndexMCPTool',
    'CreateResearchQuestionMCPTool',
    'DeleteResearchQuestionMCPTool',
    'DownloadPdfMCPTool',
    'EvaluateArticleMCPTool',
    'ExploreCitationNetworkMCPTool',
    'ExportBibliographyMCPTool',
    'FindRelatedPapersMCPTool',
    'FormatCitationsMCPTool',
    'GenerateReadingListMCPTool',
    'GetArticleDetailsMCPTool',
    'GetCitationContextMCPTool',
    'GetPresetDetailsTool',
    'GetResearchQuestionMCPTool',
    'GetSchemaInfoTool',
    'GetTaskStatusMCPTool',
    'ListArticlesMCPTool',
    'ListAvailableSourcesMCPTool',
    'ListCustomIndexesMCPTool',
    'ListResearchQuestionsMCPTool',
    'ListSchemaPresetsTool',
    'ListSkillsMCPTool',
    'LoadSkillMCPTool',
    'LocatePdfMCPTool',
    'ManageTagVocabularyMCPTool',
    'MigrateSettingsMCPTool',
    'OptimizeSearchMCPTool',
    'ReindexCollectionMCPTool',
    'ResetSettingsMCPTool',
    'RunDiscoveryForQuestionMCPTool',
    'SearchArticlesMCPTool',
    'SearchCustomIndexMCPTool',
    'SetSchemaPresetTool',
    'SyncWithObsidianMCPTool',
    'UnloadSkillMCPTool',
    'UpdateArticleMetadataMCPTool',
    'UpdateResearchQuestionMCPTool',
    'UpdateSettingsMCPTool',
    'ValidateSchemaFileTool',
    'ValidateSettingsMCPTool',
    'ViewSettingsMCPTool',
    # Deprecated tools (kept for backwards compatibility)
    'AddWorkflowActionMCPTool',
    'AnalyzeTopicMCPTool',
    'BackupCollectionMCPTool',
    'BatchProcessPdfsMCPTool',
    'ConfigureSearchMCPTool',
    'CreateBrowserWorkflowMCPTool',
    'CreateQueryMCPTool',
    'DeleteArticleMCPTool',
    'DeleteQueryMCPTool',
    'DeleteWorkflowMCPTool',
    'ExecuteWorkflowMCPTool',
    'ExportArticleDataMCPTool',
    'ExtractArticleInsightsMCPTool',
    'ExtractCitationsMCPTool',
    'ExtractPdfMetadataMCPTool',
    'FindArticlesByAuthorsMCPTool',
    'GenerateResearchSummaryMCPTool',
    'GetArticleFullContentMCPTool',
    'GetQueryMCPTool',
    'GetWorkflowDetailsMCPTool',
    'ListQueriesMCPTool',
    'ListWorkflowsMCPTool',
    'ProcessPdfMCPTool',
    'RestoreCollectionBackupMCPTool',
    'SearchByTopicMCPTool',
    'SuggestTagsMCPTool',
    'UpdateQueryMCPTool',
    'UpdateWorkflowStatusMCPTool',
    'ValidatePdfSourcesMCPTool',
    'WebSearchMCPTool',
    # Functions
    'register_all_mcp_tools',
]

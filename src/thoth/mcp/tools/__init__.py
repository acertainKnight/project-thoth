"""
MCP-compliant tools for Thoth.

This module provides all MCP-compliant tools organized by category.
"""

# Import all tools from their respective modules
from .analysis_tools import (
    AnalyzeTopicMCPTool,
    EvaluateArticleMCPTool,
    FindRelatedPapersMCPTool,
    GenerateResearchSummaryMCPTool,
)
from .article_tools import (
    CiteArticleMCPTool,
    GetArticleDetailsMCPTool,
    GetRelatedArticlesMCPTool,
    ListArticlesMCPTool,
    SearchArticlesMCPTool,
    UpdateArticleMetadataMCPTool,
)
from .citation_tools import (
    ExportBibliographyMCPTool,
    ExtractCitationsMCPTool,
    FormatCitationsMCPTool,
)
from .data import (
    BackupCollectionMCPTool,
    ExportArticleDataMCPTool,
    GenerateReadingListMCPTool,
    SyncWithObsidianMCPTool,
)
from .discovery import (
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
from .download_pdf_tool import DownloadArticlePdfMCPTool
from .pdf_content_tools import (
    ExtractImagesFromPdfMCPTool,
    ExtractSectionFromPdfMCPTool,
    ExtractTablesFromPdfMCPTool,
    GetPdfStructureMCPTool,
    SearchInPdfMCPTool,
)
from .processing_tools import (
    AutoTagArticlesMCPTool,
    GenerateNotesMCPTool,
    ProcessArticleMCPTool,
    ProcessPdfMCPTool,
    RegenerateNotesMCPTool,
    SummarizeArticleMCPTool,
)
from .query_tools import (
    CreateQueryMCPTool,
    DeleteQueryMCPTool,
    GetQueryMCPTool,
    ListQueriesMCPTool,
    RunQueryMCPTool,
    UpdateQueryMCPTool,
)
from .advanced_rag_tools import (
    AdvancedSearchMCPTool,
    CompareArticlesMCPTool,
    IndexDocumentMCPTool,
    RagStatusMCPTool,
    ReindexCollectionMCPTool,
    SearchByEmbeddingMCPTool,
    SearchWithContextMCPTool,
)
from .tag_tools import (
    AddTagsMCPTool,
    GetPopularTagsMCPTool,
    ListTagsMCPTool,
    MergeTagsMCPTool,
    RemoveTagsMCPTool,
    RenameTagMCPTool,
    SearchByTagsMCPTool,
)
from .web_search_tool import WebSearchMCPTool

# Tool registry
TOOL_REGISTRY = {
    # Article Tools
    'list_articles': ListArticlesMCPTool,
    'search_articles': SearchArticlesMCPTool,
    'get_article_details': GetArticleDetailsMCPTool,
    'get_related_articles': GetRelatedArticlesMCPTool,
    'cite_article': CiteArticleMCPTool,
    'update_article_metadata': UpdateArticleMetadataMCPTool,
    
    # Analysis Tools
    'evaluate_article': EvaluateArticleMCPTool,
    'analyze_topic': AnalyzeTopicMCPTool,
    'find_related_papers': FindRelatedPapersMCPTool,
    'generate_research_summary': GenerateResearchSummaryMCPTool,
    
    # Citation Tools
    'format_citations': FormatCitationsMCPTool,
    'export_bibliography': ExportBibliographyMCPTool,
    'extract_citations': ExtractCitationsMCPTool,
    
    # Data Management Tools
    'backup_collection': BackupCollectionMCPTool,
    'export_article_data': ExportArticleDataMCPTool,
    'generate_reading_list': GenerateReadingListMCPTool,
    'sync_with_obsidian': SyncWithObsidianMCPTool,
    
    # Discovery Tools
    'list_discovery_sources': ListDiscoverySourcesMCPTool,
    'create_arxiv_source': CreateArxivSourceMCPTool,
    'create_pubmed_source': CreatePubmedSourceMCPTool,
    'create_crossref_source': CreateCrossrefSourceMCPTool,
    'create_openalex_source': CreateOpenalexSourceMCPTool,
    'create_biorxiv_source': CreateBiorxivSourceMCPTool,
    'get_discovery_source': GetDiscoverySourceMCPTool,
    'run_discovery': RunDiscoveryMCPTool,
    'delete_discovery_source': DeleteDiscoverySourceMCPTool,
    
    # PDF Tools
    'download_article_pdf': DownloadArticlePdfMCPTool,
    'get_pdf_structure': GetPdfStructureMCPTool,
    'search_in_pdf': SearchInPdfMCPTool,
    'extract_section_from_pdf': ExtractSectionFromPdfMCPTool,
    'extract_tables_from_pdf': ExtractTablesFromPdfMCPTool,
    'extract_images_from_pdf': ExtractImagesFromPdfMCPTool,
    
    # Processing Tools
    'process_pdf': ProcessPdfMCPTool,
    'process_article': ProcessArticleMCPTool,
    'summarize_article': SummarizeArticleMCPTool,
    'generate_notes': GenerateNotesMCPTool,
    'regenerate_notes': RegenerateNotesMCPTool,
    'auto_tag_articles': AutoTagArticlesMCPTool,
    
    # Query Tools
    'list_queries': ListQueriesMCPTool,
    'create_query': CreateQueryMCPTool,
    'get_query': GetQueryMCPTool,
    'update_query': UpdateQueryMCPTool,
    'delete_query': DeleteQueryMCPTool,
    'run_query': RunQueryMCPTool,
    
    # RAG Tools
    'rag_status': RagStatusMCPTool,
    'search_with_context': SearchWithContextMCPTool,
    'advanced_search': AdvancedSearchMCPTool,
    'search_by_embedding': SearchByEmbeddingMCPTool,
    'compare_articles': CompareArticlesMCPTool,
    'index_document': IndexDocumentMCPTool,
    'reindex_collection': ReindexCollectionMCPTool,
    
    # Tag Tools
    'list_tags': ListTagsMCPTool,
    'add_tags': AddTagsMCPTool,
    'remove_tags': RemoveTagsMCPTool,
    'rename_tag': RenameTagMCPTool,
    'merge_tags': MergeTagsMCPTool,
    'get_popular_tags': GetPopularTagsMCPTool,
    'search_by_tags': SearchByTagsMCPTool,
    
    # Web Tools
    'web_search': WebSearchMCPTool,
}

__all__ = [
    'TOOL_REGISTRY',
    # Article Tools
    'ListArticlesMCPTool',
    'SearchArticlesMCPTool',
    'GetArticleDetailsMCPTool',
    'GetRelatedArticlesMCPTool',
    'CiteArticleMCPTool',
    'UpdateArticleMetadataMCPTool',
    # Analysis Tools
    'EvaluateArticleMCPTool',
    'AnalyzeTopicMCPTool',
    'FindRelatedPapersMCPTool',
    'GenerateResearchSummaryMCPTool',
    # Citation Tools
    'FormatCitationsMCPTool',
    'ExportBibliographyMCPTool',
    'ExtractCitationsMCPTool',
    # Data Management Tools
    'BackupCollectionMCPTool',
    'ExportArticleDataMCPTool',
    'GenerateReadingListMCPTool',
    'SyncWithObsidianMCPTool',
    # Discovery Tools
    'ListDiscoverySourcesMCPTool',
    'CreateArxivSourceMCPTool',
    'CreatePubmedSourceMCPTool',
    'CreateCrossrefSourceMCPTool',
    'CreateOpenalexSourceMCPTool',
    'CreateBiorxivSourceMCPTool',
    'GetDiscoverySourceMCPTool',
    'RunDiscoveryMCPTool',
    'DeleteDiscoverySourceMCPTool',
    # PDF Tools
    'DownloadArticlePdfMCPTool',
    'GetPdfStructureMCPTool',
    'SearchInPdfMCPTool',
    'ExtractSectionFromPdfMCPTool',
    'ExtractTablesFromPdfMCPTool',
    'ExtractImagesFromPdfMCPTool',
    # Processing Tools
    'ProcessPdfMCPTool',
    'ProcessArticleMCPTool',
    'SummarizeArticleMCPTool',
    'GenerateNotesMCPTool',
    'RegenerateNotesMCPTool',
    'AutoTagArticlesMCPTool',
    # Query Tools
    'ListQueriesMCPTool',
    'CreateQueryMCPTool',
    'GetQueryMCPTool',
    'UpdateQueryMCPTool',
    'DeleteQueryMCPTool',
    'RunQueryMCPTool',
    # RAG Tools
    'RagStatusMCPTool',
    'SearchWithContextMCPTool',
    'AdvancedSearchMCPTool',
    'SearchByEmbeddingMCPTool',
    'CompareArticlesMCPTool',
    'IndexDocumentMCPTool',
    'ReindexCollectionMCPTool',
    # Tag Tools
    'ListTagsMCPTool',
    'AddTagsMCPTool',
    'RemoveTagsMCPTool',
    'RenameTagMCPTool',
    'MergeTagsMCPTool',
    'GetPopularTagsMCPTool',
    'SearchByTagsMCPTool',
    # Web Tools
    'WebSearchMCPTool',
]

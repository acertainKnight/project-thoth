"""
Tool categories for role-based filtering.

This module defines which tools are available to each agent role,
enabling the MCP server to expose only relevant tools per agent.

DEPRECATED TOOLS (code kept but removed from registration):
- process_pdf: Use PDF monitor service instead (download to monitored folder)
- batch_process_pdfs: Use PDF monitor service instead
- extract_pdf_metadata: Use PDF monitor service instead
- analyze_topic: Redundant with answer_research_question
- search_by_topic: Use search_articles instead
- extract_article_insights: Redundant with get_article_details
- get_article_full_content: Merged into get_article_details
- find_articles_by_authors: Use search_articles with author filter
- extract_citations: Merged into explore_citation_network
- suggest_tags: Low value, rarely used
- generate_research_summary: Redundant with answer_research_question
- backup_collection: Admin task, not agent-facing
- restore_collection_backup: Admin task, not agent-facing
- export_article_data: Admin task, not agent-facing
- delete_article: Too risky for agent use
- thoth_web_search: Use Letta's built-in web search
- All browser workflow tools: Complex, rarely used
- Legacy query tools: Replaced by research_question tools
"""

# Tool categories by function
TOOL_CATEGORIES = {
    # Discovery and search
    'discovery': [
        'list_available_sources',
        'create_research_question',
        'list_research_questions',
        'get_research_question',
        'update_research_question',
        'delete_research_question',
        'run_discovery_for_question',
    ],
    # Workflow builder (custom source auto-detection)
    'workflow_builder': [
        'analyze_source_url',
        'refine_source_selectors',
        'confirm_source_workflow',
    ],
    # Collection management
    'collection': [
        'list_articles',
        'search_articles',
        'get_article_details',
        'collection_stats',
        'update_article_metadata',
        # DEPRECATED: "delete_article" - too risky for agent use
    ],
    # Deep analysis
    'analysis': [
        'answer_research_question',
        'explore_citation_network',
        'compare_articles',
        'find_related_papers',
        'evaluate_article',
        'get_citation_context',
        # DEPRECATED: "extract_article_insights" - redundant with get_article_details
        # DEPRECATED: "get_article_full_content" - merged into get_article_details
        # DEPRECATED: "analyze_topic" - redundant with answer_research_question
        # DEPRECATED: "generate_research_summary" - redundant with
        #             answer_research_question
        # DEPRECATED: "search_by_topic" - use search_articles instead
        # DEPRECATED: "find_articles_by_authors" - use search_articles with
        #             author filter
    ],
    # Document processing
    'processing': [
        'download_pdf',
        'locate_pdf',
        # DEPRECATED: "process_pdf" - use PDF monitor service
        # DEPRECATED: "batch_process_pdfs" - use PDF monitor service
        # DEPRECATED: "validate_pdf_sources" - admin task
        # DEPRECATED: "extract_pdf_metadata" - use PDF monitor service
    ],
    # Citation management
    'citation': [
        'format_citations',
        'export_bibliography',
        # DEPRECATED: "extract_citations" - merged into explore_citation_network
    ],
    # Tag management
    'tagging': [
        'consolidate_tags',
        'manage_tag_vocabulary',
        'consolidate_and_retag',
        'get_task_status',
        # DEPRECATED: "suggest_tags" - low value
    ],
    # Data management
    'data': [
        'generate_reading_list',
        'sync_with_obsidian',
        # DEPRECATED: "backup_collection" - admin task
        # DEPRECATED: "export_article_data" - admin task
    ],
    # Advanced RAG (loaded via skill only)
    'rag': [
        'reindex_collection',
        'optimize_search',
        'create_custom_index',
        'search_custom_index',
        'list_custom_indexes',
    ],
    # Schema management
    'schema': [
        'get_schema_info',
        'list_schema_presets',
        'set_schema_preset',
        'get_preset_details',
        'validate_schema_file',
    ],
    # Settings management (loaded via skill only)
    'settings': [
        'view_settings',
        'update_settings',
        'reset_settings',
    ],
    # Skills
    'skills': [
        'list_skills',
        'load_skill',
        'unload_skill',
        # Skill creation (loaded via skill-creation-workshop skill)
        'create_skill',
        'update_skill',
    ],
    # DEPRECATED CATEGORIES (code kept but not registered):
    # "query": Legacy query management - replaced by research_question tools
    # "workflow": Browser workflow tools - complex, rarely used
    # "web": thoth_web_search - use Letta's built-in web search
}

# Role-to-categories mapping
ROLE_TOOL_CATEGORIES = {
    # Research Orchestrator: User-facing, coordinates, delegates complex work
    'orchestrator': [
        'skills',  # Core: load skills for guidance
        'discovery',  # Find papers
        'collection',  # Browse collection
        'processing',  # Download PDFs
        'tagging',  # Tag management
        'data',  # Reading lists, obsidian sync
    ],
    # Research Analyst: Deep analysis, synthesis, quality assessment
    'analyst': [
        'analysis',  # All deep analysis tools
        'collection',  # Need to access papers
        'citation',  # Citation formatting
    ],
    # Full access (for backward compatibility or admin)
    'full': list(TOOL_CATEGORIES.keys()),
}


def get_tools_for_role(role: str) -> list[str]:
    """
    Get the list of tool names for a specific role.

    Args:
        role: Agent role (orchestrator, analyst, full)

    Returns:
        List of tool names this role should have access to
    """
    categories = ROLE_TOOL_CATEGORIES.get(role, ROLE_TOOL_CATEGORIES['full'])
    tools = []
    for category in categories:
        if category in TOOL_CATEGORIES:
            tools.extend(TOOL_CATEGORIES[category])
    return tools


def get_all_tools() -> list[str]:
    """Get all available tool names."""
    tools = []
    for category_tools in TOOL_CATEGORIES.values():
        tools.extend(category_tools)
    return tools


def get_category_for_tool(tool_name: str) -> str | None:
    """Get the category for a specific tool."""
    for category, tools in TOOL_CATEGORIES.items():
        if tool_name in tools:
            return category
    return None


# Summary for documentation
ROLE_SUMMARY = {
    'orchestrator': {
        'description': 'User-facing coordinator with skill-guided tool usage',
        'categories': ROLE_TOOL_CATEGORIES['orchestrator'],
        'tool_count': len(get_tools_for_role('orchestrator')),
    },
    'analyst': {
        'description': 'Deep analysis specialist for complex research tasks',
        'categories': ROLE_TOOL_CATEGORIES['analyst'],
        'tool_count': len(get_tools_for_role('analyst')),
    },
    'full': {
        'description': 'Full access to all tools (admin/legacy)',
        'categories': ROLE_TOOL_CATEGORIES['full'],
        'tool_count': len(get_all_tools()),
    },
}

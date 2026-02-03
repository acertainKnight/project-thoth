"""
Tool categories for role-based filtering.

This module defines which tools are available to each agent role,
enabling the MCP server to expose only relevant tools per agent.
"""

# Tool categories by function
TOOL_CATEGORIES = {
    # Discovery and search
    "discovery": [
        "list_available_sources",
        "create_research_question",
        "list_research_questions",
        "get_research_question",
        "update_research_question",
        "delete_research_question",
        "run_discovery_for_question",
    ],
    
    # Collection management
    "collection": [
        "list_articles",
        "search_articles",
        "get_article_details",
        "collection_stats",
        "delete_article",
        "update_article_metadata",
    ],
    
    # Deep analysis
    "analysis": [
        "answer_research_question",
        "explore_citation_network",
        "compare_articles",
        "extract_article_insights",
        "get_article_full_content",
        "find_related_papers",
        "analyze_topic",
        "generate_research_summary",
        "evaluate_article",
        "get_citation_context",
        "search_by_topic",
        "find_articles_by_authors",
    ],
    
    # Document processing
    "processing": [
        "process_pdf",
        "batch_process_pdfs",
        "download_pdf",
        "locate_pdf",
        "validate_pdf_sources",
        "extract_pdf_metadata",
    ],
    
    # Citation management
    "citation": [
        "format_citations",
        "export_bibliography",
        "extract_citations",
    ],
    
    # Tag management
    "tagging": [
        "consolidate_tags",
        "suggest_tags",
        "manage_tag_vocabulary",
        "consolidate_and_retag",
        "get_task_status",
    ],
    
    # Data management
    "data": [
        "backup_collection",
        "export_article_data",
        "generate_reading_list",
        "sync_with_obsidian",
    ],
    
    # Query management (legacy)
    "query": [
        "list_queries",
        "create_query",
        "get_query",
        "update_query",
        "delete_query",
    ],
    
    # Browser workflows
    "workflow": [
        "create_browser_workflow",
        "add_workflow_action",
        "configure_search",
        "execute_workflow",
        "list_workflows",
        "get_workflow_details",
        "update_workflow_status",
        "delete_workflow",
    ],
    
    # Advanced RAG
    "rag": [
        "reindex_collection",
        "optimize_search",
        "create_custom_index",
    ],
    
    # Schema management
    "schema": [
        "get_schema_info",
        "list_schema_presets",
        "set_schema_preset",
        "get_preset_details",
        "validate_schema_file",
    ],
    
    # Web search
    "web": [
        "web_search",
    ],
    
    # Skills
    "skills": [
        "list_skills",
        "load_skill",
        "unload_skill",
    ],
}

# Role-to-categories mapping
ROLE_TOOL_CATEGORIES = {
    # Research Orchestrator: User-facing, coordinates, delegates complex work
    "orchestrator": [
        "skills",        # Core: load skills for guidance
        "discovery",     # Find papers
        "collection",    # Browse collection
        "query",         # Legacy query management
    ],
    
    # Research Analyst: Deep analysis, synthesis, quality assessment
    "analyst": [
        "analysis",      # All deep analysis tools
        "collection",    # Need to access papers
        "citation",      # Citation network
    ],
    
    # Full access (for backward compatibility or admin)
    "full": list(TOOL_CATEGORIES.keys()),
}


def get_tools_for_role(role: str) -> list[str]:
    """
    Get the list of tool names for a specific role.
    
    Args:
        role: Agent role (orchestrator, analyst, full)
    
    Returns:
        List of tool names this role should have access to
    """
    categories = ROLE_TOOL_CATEGORIES.get(role, ROLE_TOOL_CATEGORIES["full"])
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
    "orchestrator": {
        "description": "User-facing coordinator with skill-guided tool usage",
        "categories": ROLE_TOOL_CATEGORIES["orchestrator"],
        "tool_count": len(get_tools_for_role("orchestrator")),
    },
    "analyst": {
        "description": "Deep analysis specialist for complex research tasks",
        "categories": ROLE_TOOL_CATEGORIES["analyst"],
        "tool_count": len(get_tools_for_role("analyst")),
    },
    "full": {
        "description": "Full access to all tools (admin/legacy)",
        "categories": ROLE_TOOL_CATEGORIES["full"],
        "tool_count": len(get_all_tools()),
    },
}

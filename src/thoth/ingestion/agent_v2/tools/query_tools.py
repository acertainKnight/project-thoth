"""
Query management tools for the research assistant.

This module provides tools for creating, listing, editing, and deleting
research queries used to filter articles.
"""

import json
from typing import Any

from pydantic import BaseModel, Field

from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool
from thoth.utilities.models import ResearchQuery


class ListQueriesTool(BaseThothTool):
    """List all available research queries."""

    name: str = 'list_queries'
    description: str = 'List all available research queries in the system'

    def _run(self) -> str:
        """List all research queries."""
        try:
            queries = self.pipeline.filter.agent.list_queries()
            if not queries:
                return "No research queries found. Use 'create_query' to create one."

            return 'Available research queries:\n' + '\n'.join(
                f'- {q}' for q in queries
            )
        except Exception as e:
            return self.handle_error(e, 'listing queries')


class CreateResearchQueryInput(BaseModel):
    research_question: str = Field(description='Main research question to investigate')
    keywords: list[str] = Field(
        description='List of keywords related to the research question'
    )
    required_topics: list[str] | None = Field(
        default=None,
        description='Topics that must be covered in the research (optional)',
    )
    preferred_topics: list[str] | None = Field(
        default=None,
        description='Topics that are preferred but not mandatory (optional)',
    )
    excluded_topics: list[str] | None = Field(
        default=None, description='Topics to be excluded from the research (optional)'
    )
    methodology_preferences: list[str] | None = Field(
        default=None, description='Preferred research methodologies (optional)'
    )


class CreateResearchQueryTool(BaseThothTool):
    """Create a new research query."""

    name: str = 'create_query'
    description: str = (
        'Create a new research query to filter articles. Provide a structured query '
        'with name, description, research question, keywords, and topic preferences.'
    )
    args_schema: type[BaseModel] = CreateResearchQueryInput

    def _run(
        self,
        name: str,
        description: str,
        research_question: str,
        keywords: list[str],
        required_topics: list[str] | None = None,
        preferred_topics: list[str] | None = None,
        excluded_topics: list[str] | None = None,
        methodology_preferences: list[str] | None = None,
    ) -> str:
        """Create a new research query."""
        try:
            query = ResearchQuery(
                name=name,
                description=description,
                research_question=research_question,
                keywords=keywords,
                required_topics=required_topics or [],
                preferred_topics=preferred_topics or [],
                excluded_topics=excluded_topics or [],
                methodology_preferences=methodology_preferences or [],
            )

            if self.pipeline.filter.agent.create_query(query):
                return (
                    f"✅ Successfully created research query '{name}'!\n\n"
                    f'**Description:** {description}\n'
                    f'**Research Question:** {research_question}\n'
                    f'**Keywords:** {", ".join(keywords)}\n'
                    f'**Required Topics:** {", ".join(required_topics or [])}\n'
                    f'**Preferred Topics:** {", ".join(preferred_topics or [])}'
                )
            else:
                return f"❌ Failed to create query '{name}'"

        except Exception as e:
            return self.handle_error(e, 'creating query')


class GetQueryInput(BaseModel):
    """Input schema for getting a query."""

    query_name: str = Field(description='Name of the query to retrieve')


class GetQueryTool(BaseThothTool):
    """Get details of a specific research query."""

    name: str = 'get_query'
    description: str = 'Get detailed information about a specific research query'
    args_schema: type[BaseModel] = GetQueryInput

    def _run(self, query_name: str) -> str:
        """Get query details."""
        try:
            query = self.pipeline.filter.agent.get_query(query_name)
            if not query:
                return f"Query '{query_name}' not found."

            return json.dumps(query.model_dump(), indent=2)
        except Exception as e:
            return self.handle_error(e, f"getting query '{query_name}'")


class EditQueryInput(BaseModel):
    """Input schema for editing a query."""

    query_name: str = Field(description='Name of the query to edit')
    updates: dict[str, Any] = Field(description='Dictionary of fields to update')


class EditQueryTool(BaseThothTool):
    """Edit an existing research query."""

    name: str = 'edit_query'
    description: str = (
        'Edit an existing research query. Provide the query name and a dictionary '
        "of fields to update (e.g., {'keywords': ['new', 'keywords']})"
    )
    args_schema: type[BaseModel] = EditQueryInput

    def _run(self, query_name: str, updates: dict[str, Any]) -> str:
        """Edit a research query."""
        try:
            query = self.pipeline.filter.agent.get_query(query_name)
            if not query:
                return f"Query '{query_name}' not found."

            # Update query fields
            for field, value in updates.items():
                if hasattr(query, field):
                    setattr(query, field, value)
                else:
                    return f"❌ Invalid field '{field}' for query"

            if self.pipeline.filter.agent.create_query(
                query
            ):  # This overwrites existing
                return f"✅ Successfully updated query '{query_name}'"
            else:
                return f"❌ Failed to update query '{query_name}'"

        except Exception as e:
            return self.handle_error(e, f"editing query '{query_name}'")


class DeleteQueryInput(BaseModel):
    """Input schema for deleting a query."""

    query_name: str = Field(description='Name of the query to delete')


class DeleteQueryTool(BaseThothTool):
    """Delete a research query."""

    name: str = 'delete_query'
    description: str = 'Delete a research query'
    args_schema: type[BaseModel] = DeleteQueryInput

    def _run(self, query_name: str) -> str:
        """Delete a research query."""
        try:
            if self.pipeline.filter.agent.delete_query(query_name):
                return f"✅ Successfully deleted query '{query_name}'"
            else:
                return f"❌ Failed to delete query '{query_name}' (may not exist)"
        except Exception as e:
            return self.handle_error(e, f"deleting query '{query_name}'")

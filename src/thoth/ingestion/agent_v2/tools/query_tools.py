"""
Query management tools for the research agent.

This module provides tools for managing research queries within the agent.
It uses the service layer through adapters to maintain backward compatibility
while leveraging the consolidated business logic.
"""

from pydantic import BaseModel, Field

from thoth.ingestion.agent_v2.tools.base_tool import (
    BaseThothTool,
    QueryNameInput,
)
from thoth.ingestion.agent_v2.tools.decorators import tool
from thoth.utilities.schemas import ResearchQuery


@tool
class ListQueriesTool(BaseThothTool):
    """Tool for listing all research queries."""

    name: str = 'list_queries'
    description: str = 'List all research queries with their details'

    def _run(self) -> str:
        """List all queries."""
        try:
            queries = self.service_manager.query.get_all_queries()
            if not queries:
                return '📋 No research queries found. Create one with create_query!'

            output = '📋 **Research Queries:**\n\n'
            for query in queries:
                output += f'**{query.name}**\n'
                output += f'  - Description: {query.description}\n'
                output += f'  - Created: {query.created_at}\n'
                if query.keywords:
                    output += f'  - Keywords: {", ".join(query.keywords)}\n'
                if query.required_topics:
                    output += (
                        f'  - Required Topics: {", ".join(query.required_topics)}\n'
                    )
                if query.preferred_topics:
                    output += (
                        f'  - Preferred Topics: {", ".join(query.preferred_topics)}\n'
                    )
                if query.excluded_topics:
                    output += (
                        f'  - Excluded Topics: {", ".join(query.excluded_topics)}\n'
                    )
                output += '\n'
            return output.strip()
        except Exception as e:
            return self.handle_error(e)


class CreateQueryInput(BaseModel):
    """Input schema for creating a query."""

    name: str = Field(description='Unique name for the query')
    description: str = Field(description='Description of what this query searches for')
    research_question: str = Field(
        description='Main research question this query addresses'
    )
    keywords: list[str] = Field(
        default_factory=list, description='Keywords to search for'
    )
    required_topics: list[str] = Field(
        default_factory=list, description='Topics that must be present'
    )
    preferred_topics: list[str] = Field(
        default_factory=list, description='Topics that are preferred but not required'
    )
    excluded_topics: list[str] = Field(
        default_factory=list, description='Topics that should exclude the article'
    )


@tool
class CreateQueryTool(BaseThothTool):
    """Tool for creating a new research query."""

    name: str = 'create_query'
    description: str = 'Create a new research query to filter articles'
    args_schema: type[BaseModel] = CreateQueryInput

    def _run(
        self,
        name: str,
        description: str,
        research_question: str,
        keywords: list[str] | None = None,
        required_topics: list[str] | None = None,
        preferred_topics: list[str] | None = None,
        excluded_topics: list[str] | None = None,
    ) -> str:
        """Create a new research query."""
        try:
            query = ResearchQuery(
                name=name,
                description=description,
                research_question=research_question,
                keywords=keywords or [],
                required_topics=required_topics or [],
                preferred_topics=preferred_topics or [],
                excluded_topics=excluded_topics or [],
            )

            success = self.service_manager.query.create_query(query)
            if success:
                return f"✅ Successfully created query '{name}'"
            else:
                return f"❌ Failed to create query '{name}' - it may already exist"
        except Exception as e:
            return self.handle_error(e, f"creating query '{name}'")


@tool
class GetQueryTool(BaseThothTool):
    """Tool for getting details of a specific query."""

    name: str = 'get_query'
    description: str = 'Get details of a specific research query'
    args_schema: type[BaseModel] = QueryNameInput

    def _run(self, query_name: str) -> str:
        """Get query details."""
        try:
            query = self.service_manager.query.get_query(query_name)
            if not query:
                return f"❌ Query '{query_name}' not found"

            output = f'📋 **Query: {query.name}**\n\n'
            output += f'**Description:** {query.description}\n'
            output += f'**Research Question:** {query.research_question}\n'
            output += f'**Created:** {query.created_at}\n'

            if query.keywords:
                output += f'**Keywords:** {", ".join(query.keywords)}\n'
            if query.required_topics:
                output += f'**Required Topics:** {", ".join(query.required_topics)}\n'
            if query.preferred_topics:
                output += f'**Preferred Topics:** {", ".join(query.preferred_topics)}\n'
            if query.excluded_topics:
                output += f'**Excluded Topics:** {", ".join(query.excluded_topics)}\n'

            return output
        except Exception as e:
            return self.handle_error(e, f"getting query '{query_name}'")


class EditQueryInput(BaseModel):
    """Input schema for editing a query."""

    query_name: str = Field(description='Name of the query to edit')
    description: str | None = Field(None, description='New description')
    research_question: str | None = Field(None, description='New research question')
    keywords: list[str] | None = Field(None, description='New keywords list')
    required_topics: list[str] | None = Field(
        None, description='New required topics list'
    )
    preferred_topics: list[str] | None = Field(
        None, description='New preferred topics list'
    )
    excluded_topics: list[str] | None = Field(
        None, description='New excluded topics list'
    )


@tool
class EditQueryTool(BaseThothTool):
    """Tool for editing an existing research query."""

    name: str = 'edit_query'
    description: str = 'Edit an existing research query'
    args_schema: type[BaseModel] = EditQueryInput

    def _run(
        self,
        query_name: str,
        description: str | None = None,
        research_question: str | None = None,
        keywords: list[str] | None = None,
        required_topics: list[str] | None = None,
        preferred_topics: list[str] | None = None,
        excluded_topics: list[str] | None = None,
    ) -> str:
        """Edit a query."""
        try:
            # Build updates dict
            updates = {}
            if description is not None:
                updates['description'] = description
            if research_question is not None:
                updates['research_question'] = research_question
            if keywords is not None:
                updates['keywords'] = keywords
            if required_topics is not None:
                updates['required_topics'] = required_topics
            if preferred_topics is not None:
                updates['preferred_topics'] = preferred_topics
            if excluded_topics is not None:
                updates['excluded_topics'] = excluded_topics

            if not updates:
                return '❌ No updates provided'

            success = self.service_manager.query.update_query(query_name, updates)
            if success:
                return f"✅ Successfully updated query '{query_name}'"
            else:
                return f"❌ Failed to update query '{query_name}' - it may not exist"
        except Exception as e:
            return self.handle_error(e, f"updating query '{query_name}'")


@tool
class DeleteQueryTool(BaseThothTool):
    """Tool for deleting a research query."""

    name: str = 'delete_query'
    description: str = 'Delete a research query'
    args_schema: type[BaseModel] = QueryNameInput

    def _run(self, query_name: str) -> str:
        """Delete a query."""
        try:
            success = self.service_manager.query.delete_query(query_name)
            if success:
                return f"✅ Successfully deleted query '{query_name}'"
            else:
                return f"❌ Failed to delete query '{query_name}' - it may not exist"
        except Exception as e:
            return self.handle_error(e, f"deleting query '{query_name}'")

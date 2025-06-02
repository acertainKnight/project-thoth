"""
Query management tools for the research agent.

This module provides tools for managing research queries within the agent.
It uses the service layer through adapters to maintain backward compatibility
while leveraging the consolidated business logic.
"""

from pydantic import BaseModel, Field

from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool, QueryNameInput
from thoth.utilities.models import ResearchQuery


class ListQueriesTool(BaseThothTool):
    """Tool for listing all research queries."""

    name: str = 'list_queries'
    description: str = 'List all research queries with their details'

    def _run(self) -> str:
        """List all queries."""
        try:
            queries = self.adapter.list_queries()
            if not queries:
                return '📋 No research queries found. Create one with create_query!'

            output = '📋 **Research Queries:**\n\n'
            for query in queries:
                output += f'**{query.name}**\n'
                output += f'  - Description: {query.description}\n'
                output += f'  - Created: {query.created_at}\n'
                if query.keywords:
                    output += f'  - Keywords: {", ".join(query.keywords)}\n'
                if query.tags:
                    output += f'  - Tags: {", ".join(query.tags)}\n'
                output += '\n'
            return output.strip()
        except Exception as e:
            return self.handle_error(e)


class CreateQueryInput(BaseModel):
    """Input schema for creating a query."""

    name: str = Field(description='Unique name for the query')
    description: str = Field(description='Description of what this query searches for')
    evaluation_criteria: str = Field(
        description='Criteria for evaluating articles against this query'
    )
    keywords: list[str] = Field(
        default_factory=list, description='Keywords to search for'
    )
    exclusion_keywords: list[str] = Field(
        default_factory=list, description='Keywords to exclude'
    )


class CreateQueryTool(BaseThothTool):
    """Tool for creating a new research query."""

    name: str = 'create_query'
    description: str = 'Create a new research query to filter articles'
    args_schema: type[BaseModel] = CreateQueryInput

    def _run(
        self,
        name: str,
        description: str,
        evaluation_criteria: str,
        keywords: list[str] | None = None,
        exclusion_keywords: list[str] | None = None,
    ) -> str:
        """Create a new research query."""
        try:
            query = ResearchQuery(
                name=name,
                description=description,
                evaluation_criteria=evaluation_criteria,
                keywords=keywords or [],
                exclusion_keywords=exclusion_keywords or [],
            )

            success = self.adapter.create_query(query)
            if success:
                return f"✅ Successfully created query '{name}'"
            else:
                return f"❌ Failed to create query '{name}' - it may already exist"
        except Exception as e:
            return self.handle_error(e, f"creating query '{name}'")


class GetQueryTool(BaseThothTool):
    """Tool for getting details of a specific query."""

    name: str = 'get_query'
    description: str = 'Get details of a specific research query'
    args_schema: type[BaseModel] = QueryNameInput

    def _run(self, query_name: str) -> str:
        """Get query details."""
        try:
            query = self.adapter.get_query(query_name)
            if not query:
                return f"❌ Query '{query_name}' not found"

            output = f'📋 **Query: {query.name}**\n\n'
            output += f'**Description:** {query.description}\n'
            output += f'**Evaluation Criteria:** {query.evaluation_criteria}\n'
            output += f'**Created:** {query.created_at}\n'

            if query.keywords:
                output += f'**Keywords:** {", ".join(query.keywords)}\n'
            if query.exclusion_keywords:
                output += f'**Exclusions:** {", ".join(query.exclusion_keywords)}\n'
            if query.tags:
                output += f'**Tags:** {", ".join(query.tags)}\n'

            return output
        except Exception as e:
            return self.handle_error(e, f"getting query '{query_name}'")


class EditQueryInput(BaseModel):
    """Input schema for editing a query."""

    query_name: str = Field(description='Name of the query to edit')
    description: str | None = Field(None, description='New description')
    evaluation_criteria: str | None = Field(None, description='New evaluation criteria')
    keywords: list[str] | None = Field(None, description='New keywords list')
    exclusion_keywords: list[str] | None = Field(
        None, description='New exclusion keywords'
    )


class EditQueryTool(BaseThothTool):
    """Tool for editing an existing research query."""

    name: str = 'edit_query'
    description: str = 'Edit an existing research query'
    args_schema: type[BaseModel] = EditQueryInput

    def _run(
        self,
        query_name: str,
        description: str | None = None,
        evaluation_criteria: str | None = None,
        keywords: list[str] | None = None,
        exclusion_keywords: list[str] | None = None,
    ) -> str:
        """Edit a query."""
        try:
            # Build updates dict
            updates = {}
            if description is not None:
                updates['description'] = description
            if evaluation_criteria is not None:
                updates['evaluation_criteria'] = evaluation_criteria
            if keywords is not None:
                updates['keywords'] = keywords
            if exclusion_keywords is not None:
                updates['exclusion_keywords'] = exclusion_keywords

            if not updates:
                return '❌ No updates provided'

            success = self.adapter.update_query(query_name, updates)
            if success:
                return f"✅ Successfully updated query '{query_name}'"
            else:
                return f"❌ Failed to update query '{query_name}' - it may not exist"
        except Exception as e:
            return self.handle_error(e, f"updating query '{query_name}'")


class DeleteQueryTool(BaseThothTool):
    """Tool for deleting a research query."""

    name: str = 'delete_query'
    description: str = 'Delete a research query'
    args_schema: type[BaseModel] = QueryNameInput

    def _run(self, query_name: str) -> str:
        """Delete a query."""
        try:
            success = self.adapter.delete_query(query_name)
            if success:
                return f"✅ Successfully deleted query '{query_name}'"
            else:
                return f"❌ Failed to delete query '{query_name}' - it may not exist"
        except Exception as e:
            return self.handle_error(e, f"deleting query '{query_name}'")

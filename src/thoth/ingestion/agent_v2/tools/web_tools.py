"""Tools for general web search."""

from __future__ import annotations

from pydantic import BaseModel, Field

from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool


class WebSearchInput(BaseModel):
    """Input schema for web search."""

    query: str = Field(description='Search query')
    num_results: int = Field(default=5, description='Number of results to return')
    provider: str | None = Field(
        default=None,
        description='Preferred search provider (serper, duckduckgo, scrape)',
    )


class WebSearchTool(BaseThothTool):
    """Tool that performs a general web search."""

    name: str = 'web_search'
    description: str = 'Search the web using the configured search API'
    args_schema: type[BaseModel] = WebSearchInput

    def _run(
        self, query: str, num_results: int = 5, provider: str | None = None
    ) -> str:
        try:
            results = self.service_manager.web_search.search(
                query, num_results, provider
            )
            if not results:
                return '❌ No search results found or API key not configured.'

            output = f'🔎 **Web Search Results for:** "{query}"\n\n'
            for r in results:
                output += f'**{r.position}. {r.title}**\n{r.link}\n{r.snippet}\n\n'
            return output.strip()
        except Exception as e:
            return self.handle_error(e, 'web search')

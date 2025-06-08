from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Schema for a single search result from Google Search API."""

    title: str = Field(description='Title of the search result')
    link: str = Field(description='URL of the search result')
    snippet: str = Field(description='Text snippet from the search result')
    position: int = Field(description='Position in search results')


class SearchResponse(BaseModel):
    """Schema for the Google Search API response."""

    results: list[SearchResult] = Field(description='List of search results')

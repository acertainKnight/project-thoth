from typing import Literal, TypedDict

from pydantic import BaseModel, Field, field_validator

from .analysis import AnalysisResponse
from .discovery import ScrapedArticleMetadata


class ResearchQuery(BaseModel):
    """Schema for a research query that defines what kinds of articles to collect."""

    name: str = Field(description='Unique name/identifier for this query')
    description: str = Field(
        description='Human-readable description of what this query is looking for'
    )
    research_question: str = Field(
        description='The main research question or interest area'
    )
    keywords: list[str] = Field(default_factory=list)
    required_topics: list[str] = Field(default_factory=list)
    preferred_topics: list[str] = Field(default_factory=list)
    excluded_topics: list[str] = Field(default_factory=list)
    methodology_preferences: list[str] = Field(default_factory=list)
    publication_date_range: dict[str, str] | None = Field(default=None)
    minimum_relevance_score: float = Field(default=0.7, ge=0.0, le=1.0)
    created_at: str | None = Field(default=None)
    updated_at: str | None = Field(default=None)
    is_active: bool = Field(default=True)

    @field_validator('name')
    def validate_name(cls, name: str) -> str:  # noqa: N805
        import re

        return re.sub(r'[^\w\-_.]', '_', name.lower())


class QueryEvaluationResponse(BaseModel):
    """Schema for evaluating how well an article matches a research query."""

    relevance_score: float = Field(ge=0.0, le=1.0)
    meets_criteria: bool
    keyword_matches: list[str] = Field(default_factory=list)
    topic_analysis: str
    methodology_match: str | None = None
    reasoning: str
    recommendation: Literal['keep', 'reject', 'review']
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class QueryRefinementSuggestion(BaseModel):
    """Schema for suggestions on how to improve a research query."""

    suggested_keywords: list[str] = Field(default_factory=list)
    suggested_topics: list[str] = Field(default_factory=list)
    refinement_reasoning: str
    query_improvements: str | None = None
    methodology_suggestions: list[str] = Field(default_factory=list)


class ResearchAgentState(TypedDict):
    """Represents the state of the research query agent conversation."""

    user_message: str | None
    agent_response: str | None
    conversation_history: list[dict[str, str]] | None
    current_query: ResearchQuery | None
    query_name: str | None
    available_queries: list[str] | None
    current_article: AnalysisResponse | None
    evaluation_result: QueryEvaluationResponse | None
    action: (
        Literal[
            'create_query',
            'edit_query',
            'evaluate_article',
            'refine_query',
            'list_queries',
            'delete_query',
            'chat',
            'end',
        ]
        | None
    )
    needs_user_input: bool | None
    error_message: str | None


class PreDownloadEvaluationResponse(BaseModel):
    """Schema for evaluating scraped article metadata before PDF download."""

    relevance_score: float = Field(ge=0.0, le=1.0)
    should_download: bool
    keyword_matches: list[str] = Field(default_factory=list)
    topic_analysis: str
    reasoning: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    matching_queries: list[str] = Field(default_factory=list)


class FilterLogEntry(BaseModel):
    """Schema for logging article filtering decisions."""

    timestamp: str
    article_metadata: ScrapedArticleMetadata
    evaluation_result: PreDownloadEvaluationResponse
    decision: Literal['download', 'skip']
    queries_evaluated: list[str] = Field(default_factory=list)
    pdf_downloaded: bool = Field(default=False)
    pdf_path: str | None = None
    error_message: str | None = None

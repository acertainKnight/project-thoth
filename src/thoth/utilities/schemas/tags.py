from pydantic import BaseModel, Field


class TagConsolidationResponse(BaseModel):
    """Schema for tag consolidation response from LLM."""

    tag_mappings: dict[str, str] = Field(default_factory=dict)
    consolidated_tags: list[str]
    reasoning: str = Field(default='')


class ConsolidatedTagsResponse(BaseModel):
    """Schema for getting the consolidated list of canonical tags (first step)."""

    consolidated_tags: list[str]
    suggested_category_tags: list[str] = Field(default_factory=list)
    suggested_aggregate_tags: list[str] = Field(default_factory=list)
    reasoning: str = Field(default='')


class SingleTagMappingResponse(BaseModel):
    """Schema for mapping a single tag to its canonical form (second step)."""

    canonical_tag: str


class TagSuggestionResponse(BaseModel):
    """Schema for additional tag suggestions response from LLM."""

    suggested_tags: list[str] = Field(default_factory=list)
    reasoning: str = Field(default='')

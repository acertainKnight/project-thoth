from typing import Any, Literal, Union

from pydantic import BaseModel, Field, field_validator

from .analysis import AnalysisResponse


class DiscoverySource(BaseModel):
    """Schema for a discovery source configuration."""

    name: str = Field(description='Unique name for this discovery source')
    source_type: Literal['api', 'scraper', 'emulator'] = Field(
        description='Type of source'
    )
    description: str = Field(description='Human-readable description of the source')
    is_active: bool = Field(default=True)
    schedule_config: 'ScheduleConfig'
    api_config: dict[str, Any] | None = Field(default=None)
    scraper_config: Union['ScrapeConfiguration', None] = Field(default=None)
    browser_recording: 'BrowserRecording | None' = Field(default=None)
    query_filters: list[str] = Field(default_factory=list)
    last_run: str | None = Field(default=None)
    created_at: str | None = Field(default=None)
    updated_at: str | None = Field(default=None)

    @field_validator('name')
    def validate_name(cls, name: str) -> str:  # noqa: N805
        import re

        return re.sub(r'[^\w\-_.]', '_', name.lower())


class ScheduleConfig(BaseModel):
    """Schema for scheduling configuration."""

    interval_minutes: int = Field(default=60)
    max_articles_per_run: int = Field(default=50)
    enabled: bool = Field(default=True)
    time_of_day: str | None = Field(default=None)
    days_of_week: list[int] | None = Field(default=None)


class ScrapeConfiguration(BaseModel):
    """Schema for web scraping configuration."""

    base_url: str
    navigation_rules: dict[str, Any] = Field(default_factory=dict)
    extraction_rules: dict[str, Any]
    pagination_config: dict[str, Any] = Field(default_factory=dict)
    rate_limiting: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)


class DiscoveryResult(BaseModel):
    """Schema for a discovery result."""

    source_name: str
    run_timestamp: str
    articles_found: int
    articles_filtered: int
    articles_downloaded: int
    errors: list[str] = Field(default_factory=list)
    execution_time_seconds: float = Field(default=0.0)


class ChromeExtensionConfig(BaseModel):
    """Schema for Chrome extension scraper configuration."""

    site_name: str
    base_url: str
    selectors: dict[str, str]
    navigation_steps: list[dict[str, Any]] = Field(default_factory=list)
    test_data: dict[str, Any] = Field(default_factory=dict)


class BrowserRecording(BaseModel):
    """Recorded browser session for dynamic sites."""

    start_url: str
    end_url: str
    cookies: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)


class ScrapedArticleMetadata(BaseModel):
    """Schema for scraped article metadata before PDF download."""

    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    publication_date: str | None = None
    journal: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    keywords: list[str] = Field(default_factory=list)
    source: str
    scrape_timestamp: str | None = None
    additional_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_analysis_response(self) -> 'AnalysisResponse':
        return AnalysisResponse(
            abstract=self.abstract,
            summary=self.abstract,
            tags=self.keywords if self.keywords else None,
        )

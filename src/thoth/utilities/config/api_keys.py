"""
API keys configuration for external services.

This module contains all API key configurations needed for various
external services integrated with Thoth.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIKeys(BaseSettings):
    """API keys for external services."""

    model_config = SettingsConfigDict(
        env_prefix='API_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # Make case-insensitive to handle env vars
        extra='allow',
    )
    mistral_key: str | None = Field(
        None, description='Mistral API key for OCR (optional)'
    )
    openrouter_key: str | None = Field(None, description='OpenRouter API key for LLM')
    openai_key: str | None = Field(None, description='OpenAI API key for LLM')
    anthropic_key: str | None = Field(None, description='Anthropic API key for LLM')
    opencitations_key: str | None = Field(None, description='OpenCitations API key')
    google_api_key: str | None = Field(
        None, description='Google API key for web search (legacy)'
    )
    google_search_engine_id: str | None = Field(
        None, description='Google Custom Search Engine ID (legacy)'
    )
    semanticscholar_api_key: str | None = Field(
        None, description='Semantic Scholar API key'
    )
    web_search_key: str | None = Field(
        None, description='Serper.dev API key for general web search'
    )
    web_search_providers: list[str] = Field(
        default_factory=lambda: ['serper'],
        description='Comma-separated list of enabled web search providers '
        '(serper, duckduckgo, scrape)',
    )
    unpaywall_email: str | None = Field(
        None,
        description='Email address for Unpaywall API (required for OA PDF lookups)',
    )

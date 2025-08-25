"""
LLM model configurations for various components.

This module contains all LLM-related configuration classes for different
components that use language models in Thoth.
"""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from .base import BaseLLMConfig


class LLMConfig(BaseLLMConfig):
    """Configuration for primary LLM."""

    model_config = SettingsConfigDict(
        env_prefix='LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
        env_nested_delimiter='_',
    )

    # Primary LLM requires model field
    model: str = Field(..., description='Primary LLM model identifier')

    chunk_size: int = Field(4000, description='Chunk size for splitting documents')
    chunk_overlap: int = Field(200, description='Chunk overlap for splitting documents')
    refine_threshold_multiplier: float = Field(
        1.2, description='Multiplier for max_context_length to choose refine strategy'
    )
    map_reduce_threshold_multiplier: float = Field(
        3.0,
        description='Multiplier for max_context_length to choose map_reduce strategy',
    )


class QueryBasedRoutingConfig(BaseLLMConfig):
    """Configuration for query-based model routing."""

    model_config = SettingsConfigDict(
        env_prefix='ROUTING_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )
    enabled: bool = Field(False, description='Enable query-based routing')
    routing_model: str = Field(
        'openai/gpt-4o-mini',
        description='The model used to select the best model for a query',
    )
    use_dynamic_prompt: bool = Field(
        True, description='Use a dynamic Jinja2 template for the routing prompt'
    )


class CitationLLMConfig(BaseLLMConfig):
    """Configuration for citation processing LLM."""

    model_config = SettingsConfigDict(
        env_prefix='CITATION_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )

    # Citation LLM requires model field
    model: str = Field(..., description='Default citation LLM model')

    # Override defaults for citation-specific use case
    max_output_tokens: int = Field(
        10000, description='Max tokens for citation processing (focused outputs)'
    )
    max_context_length: int = Field(
        4000, description='Max context length (smaller for focused citation inputs)'
    )

    # Citation-specific models
    document_citation_model: str | None = Field(
        None, description='Model for extracting document citations'
    )
    reference_cleaning_model: str | None = Field(
        None, description='Model for cleaning references section'
    )
    structured_extraction_model: str | None = Field(
        None, description='Model for structured citation extraction (single mode)'
    )
    batch_structured_extraction_model: str | None = Field(
        None, description='Model for structured citation extraction (batch mode)'
    )


class TagConsolidatorLLMConfig(BaseLLMConfig):
    """Configuration for tag consolidation LLM."""

    model_config = SettingsConfigDict(
        env_prefix='TAG_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )

    # Override defaults for tag processing
    max_output_tokens: int = Field(
        10000, description='Max tokens for tag processing (focused outputs)'
    )

    # Tag-specific models (base model field is optional for this config)
    consolidate_model: str = Field(..., description='Tag consolidator LLM model')
    suggest_model: str = Field(..., description='Tag suggestor LLM model')
    map_model: str = Field(..., description='Tag mapper LLM model')


class ResearchAgentLLMConfig(BaseLLMConfig):
    """Configuration for research agent LLM."""

    model_config = SettingsConfigDict(
        env_prefix='RESEARCH_AGENT_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )

    # Override model field to support multiple models
    model: str | list[str] = Field(..., description='Research agent LLM model(s)')

    # Override defaults for research agent (needs larger context)
    max_context_length: int = Field(
        100000, description='Max context length for research tasks'
    )

    # Research agent specific features
    use_auto_model_selection: bool = Field(
        False, description='Whether to use auto model selection'
    )
    auto_model_require_tool_calling: bool = Field(
        False, description='Auto-selected model must support tool calling'
    )
    auto_model_require_structured_output: bool = Field(
        False, description='Auto-selected model must support structured output'
    )


class ScrapeFilterLLMConfig(BaseLLMConfig):
    """Configuration for scrape filtering LLM."""

    model_config = SettingsConfigDict(
        env_prefix='SCRAPE_FILTER_LLM_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
    )

    # Scrape filter LLM requires model field
    model: str = Field(..., description='Scrape filter LLM model')

    # Override defaults for scrape filtering (needs larger context for web content)
    max_output_tokens: int = Field(10000, description='Max tokens for scrape filtering')
    max_context_length: int = Field(
        50000, description='Max context length for web content filtering'
    )

"""
Configuration module for Thoth.
"""

from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIKeys(BaseSettings):
    """API keys for external services."""

    mistral: str | None = Field(None, description="Mistral API key for OCR")
    openrouter: str | None = Field(None, description="OpenRouter API key for LLM")

    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Allow extra fields to be ignored
        env_ignore_empty=True,  # Ignore empty environment variables
    )


class ThothSettings(BaseSettings):
    """Configuration for Thoth."""

    # Base paths
    workspace_dir: Path = Field(Path("."), description="Base workspace directory")
    pdf_dir: Path | None = Field(None, description="Directory for PDF files")
    markdown_dir: Path | None = Field(None, description="Directory for Markdown files")
    notes_dir: Path | None = Field(None, description="Directory for Obsidian notes")
    templates_dir: Path | None = Field(None, description="Directory for templates")

    # Logging
    log_level: str = Field("INFO", description="Logging level")
    log_file: Path | None = Field(None, description="Log file path")

    # File monitoring
    watch_interval: Annotated[int, Field(ge=1)] = Field(
        5, description="Interval for file watching in seconds"
    )
    bulk_process_chunk_size: Annotated[int, Field(ge=1)] = Field(
        10, description="Chunk size for bulk processing"
    )

    # API keys
    mistral_key: str = Field("", description="Mistral API key for OCR")
    openrouter_key: str = Field("", description="OpenRouter API key for LLM")

    # LLM settings
    llm_model: str = Field(
        "google/gemini-2.0-flash-001", description="LLM model to use"
    )
    llm_temperature: float = Field(0.1, description="Temperature for LLM generation")
    use_llm_for_citations: bool = Field(
        True, description="Whether to use LLM for citation extraction"
    )

    # Citation settings
    citation_format: str = Field(
        "uri", description="Format for citations (uri, wikilink, etc.)"
    )
    uri_scheme: str = Field("thoth", description="URI scheme for citation links")
    download_timeout: int = Field(
        60, description="Timeout for downloading citations in seconds"
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        validate_default=True,
        extra="ignore",
    )

    @classmethod
    @field_validator(
        "pdf_dir", "markdown_dir", "notes_dir", "templates_dir", "log_file"
    )
    def set_default_paths(cls, v: Path | None, info) -> Path:
        """Set default paths based on workspace_dir if not explicitly provided."""
        if v is not None:
            return v

        field_name = info.field_name
        workspace_dir = info.data.get("workspace_dir", Path("."))

        if field_name == "pdf_dir":
            return workspace_dir / "data" / "pdfs"
        elif field_name == "markdown_dir":
            return workspace_dir / "data" / "markdown"
        elif field_name == "notes_dir":
            return workspace_dir / "data" / "notes"
        elif field_name == "templates_dir":
            return workspace_dir / "templates"
        elif field_name == "log_file":
            return workspace_dir / "logs" / "thoth.log"

        return v

    @classmethod
    @field_validator(
        "workspace_dir",
        "pdf_dir",
        "markdown_dir",
        "notes_dir",
        "templates_dir",
        "log_file",
    )
    def ensure_path_exists(cls, v: Path) -> Path:
        """Validate that the path exists and create it if it doesn't."""
        if not v.exists():
            v.mkdir(parents=True, exist_ok=True)
        return v

    @property
    def api_keys(self) -> APIKeys:
        """Get API keys as an APIKeys object."""
        # Create a new APIKeys object with only the required fields
        return APIKeys(
            mistral=self.mistral_key,
            openrouter=self.openrouter_key,
        )


def load_config() -> ThothSettings:
    """Load configuration from environment variables."""
    # Load environment variables from .env file
    load_dotenv()

    # Create and return settings
    return ThothSettings()

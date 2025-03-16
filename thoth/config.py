"""
Configuration module for Thoth.
"""
import os
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


class APIKeys(BaseModel):
    """API keys for external services."""

    mistral: str = Field(..., description="Mistral API key for OCR")
    openrouter: str = Field(..., description="OpenRouter API key for LLM")


class ThothConfig(BaseModel):
    """Configuration for Thoth."""

    # Base paths
    workspace_dir: Path = Field(..., description="Base workspace directory")
    pdf_dir: Path = Field(..., description="Directory for PDF files")
    markdown_dir: Path = Field(..., description="Directory for Markdown files")
    notes_dir: Path = Field(..., description="Directory for Obsidian notes")
    templates_dir: Path = Field(..., description="Directory for templates")

    # Logging
    log_level: str = Field("INFO", description="Logging level")
    log_file: Path = Field(..., description="Log file path")

    # File monitoring
    watch_interval: int = Field(5, description="Interval for file watching in seconds")
    bulk_process_chunk_size: int = Field(10, description="Chunk size for bulk processing")

    # API keys
    api_keys: APIKeys = Field(..., description="API keys for external services")

    @field_validator("workspace_dir", "pdf_dir", "markdown_dir", "notes_dir", "templates_dir", "log_file")
    @classmethod
    def validate_path(cls, v: Path) -> Path:
        """Validate that the path exists and create it if it doesn't."""
        if not v.exists():
            v.mkdir(parents=True, exist_ok=True)
        return v


def load_config() -> ThothConfig:
    """Load configuration from environment variables."""
    # Load environment variables from .env file
    load_dotenv()

    # Get base workspace directory
    workspace_dir = Path(os.getenv("WORKSPACE_DIR", "."))

    # Construct paths
    pdf_dir = Path(os.getenv("PDF_DIR", workspace_dir / "data" / "pdfs"))
    markdown_dir = Path(os.getenv("MARKDOWN_DIR", workspace_dir / "data" / "markdown"))
    notes_dir = Path(os.getenv("NOTES_DIR", workspace_dir / "data" / "notes"))
    templates_dir = Path(os.getenv("TEMPLATES_DIR", workspace_dir / "templates"))
    log_file = Path(os.getenv("LOG_FILE", workspace_dir / "logs" / "thoth.log"))

    # Get API keys
    api_keys = APIKeys(
        mistral=os.getenv("API_MISTRAL_KEY", ""),
        openrouter=os.getenv("API_OPENROUTER_KEY", ""),
    )

    # Create configuration
    config = ThothConfig(
        workspace_dir=workspace_dir,
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        notes_dir=notes_dir,
        templates_dir=templates_dir,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=log_file,
        watch_interval=int(os.getenv("WATCH_INTERVAL", "5")),
        bulk_process_chunk_size=int(os.getenv("BULK_PROCESS_CHUNK_SIZE", "10")),
        api_keys=api_keys,
    )

    return config

"""
Note generator module for Thoth.

This module handles the generation of Obsidian notes from processed content.
"""

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from thoth.utils.file import ensure_directory

logger = logging.getLogger(__name__)


class NoteGenerator:
    """
    Generates Obsidian notes from processed content using templates.

    This class handles the creation of structured Obsidian notes from
    processed content using Jinja2 templates.
    """

    def __init__(self, templates_dir: Path, notes_dir: Path):
        """
        Initialize the note generator.

        Args:
            templates_dir (Path): Directory containing note templates.
            notes_dir (Path): Directory where generated notes will be saved.
        """
        self.templates_dir = templates_dir
        self.notes_dir = notes_dir

        # Ensure directories exist
        ensure_directory(self.templates_dir)
        ensure_directory(self.notes_dir)

        # Set up Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=False,  # No HTML escaping for Markdown
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def create_note(
        self, content: dict[str, Any], template_name: str = "note_template.md"
    ) -> Path:
        """
        Create an Obsidian note from processed content using a template.

        Args:
            content (Dict[str, Any]): Processed content including metadata,
                analysis, and citations.
            template_name (str): Name of the template file to use.

        Returns:
            Path: Path to the generated note file.

        Raises:
            FileNotFoundError: If the template file doesn't exist.
            ValueError: If required content fields are missing.
        """
        # Validate content
        self._validate_content(content)

        # Get the template
        template = self.env.get_template(template_name)

        # Generate note content
        note_content = template.render(**content)

        # Determine note filename
        note_filename = self._get_note_filename(content)
        note_path = self.notes_dir / note_filename

        # Write note to file
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(note_content)

        logger.info(f"Created note: {note_path}")
        return note_path

    def create_basic_note(
        self, metadata: dict[str, Any], pdf_path: Path, markdown_path: Path
    ) -> Path:
        """
        Create a basic note with just metadata when LLM processing fails.

        Args:
            metadata (Dict[str, Any]): Paper metadata.
            pdf_path (Path): Path to the PDF file.
            markdown_path (Path): Path to the Markdown file.

        Returns:
            Path: Path to the generated note file.
        """
        # Create minimal content
        content = {
            "title": metadata.get("title", "Unknown Title"),
            "authors": metadata.get("authors", []),
            "year": metadata.get("year"),
            "doi": metadata.get("doi"),
            "journal": metadata.get("journal"),
            "abstract": metadata.get("abstract", ""),
            "summary": "Note: LLM processing failed. Basic note created.",
            "key_points": [],
            "citations": [],
            "source_files": {"pdf": str(pdf_path), "markdown": str(markdown_path)},
        }

        return self.create_note(content)

    def _validate_content(self, content: dict[str, Any]) -> None:
        """
        Validate that the content contains required fields.

        Args:
            content (Dict[str, Any]): Content to validate.

        Raises:
            ValueError: If required fields are missing.
        """
        required_fields = ["title", "authors"]
        missing_fields = [field for field in required_fields if field not in content]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        # Ensure source_files is present
        if "source_files" not in content:
            raise ValueError("Missing source_files in content")

        # Ensure source_files contains pdf and markdown
        source_files = content["source_files"]
        if not isinstance(source_files, dict):
            raise ValueError("source_files must be a dictionary")

        missing_source_files = [
            field for field in ["pdf", "markdown"] if field not in source_files
        ]

        if missing_source_files:
            raise ValueError(
                f"Missing required source files: {', '.join(missing_source_files)}"
            )

    def _get_note_filename(self, content: dict[str, Any]) -> str:
        """
        Generate a filename for the note based on content metadata.

        Args:
            content (Dict[str, Any]): Content with metadata.

        Returns:
            str: Generated filename.
        """
        # Use title for filename, with fallback
        title = content.get("title", "Unknown Title")

        # Add year if available
        year = content.get("year")
        if year:
            filename = f"{year} - {title}.md"
        else:
            filename = f"{title}.md"

        # Clean filename
        filename = self._clean_filename(filename)

        return filename

    def _clean_filename(self, filename: str) -> str:
        """
        Clean a filename to ensure it's valid.

        Args:
            filename (str): Original filename.

        Returns:
            str: Cleaned filename.
        """
        # Replace invalid characters
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Limit length
        if len(filename) > 255:
            base, ext = filename.rsplit('.', 1)
            filename = f"{base[:250]}.{ext}"

        return filename

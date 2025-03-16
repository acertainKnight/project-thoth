"""
Markdown Processor for Thoth.

This module handles the processing of Markdown files and extraction of metadata.
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MarkdownProcessingError(Exception):
    """Exception raised for errors in the Markdown processing."""

    pass


class MarkdownProcessor:
    """
    Processes Markdown files and extracts metadata.

    This class handles the cleaning and processing of Markdown files
    generated from OCR, and extracts metadata such as title, authors,
    and publication details.
    """

    def __init__(self):
        """Initialize the Markdown Processor."""
        logger.debug("Markdown Processor initialized")

    def process_markdown(self, markdown_path: Path) -> dict[str, Any]:
        """
        Process a Markdown file and extract structured data.

        Args:
            markdown_path (Path): The path to the Markdown file.

        Returns:
            Dict[str, Any]: A dictionary containing structured data with keys:
                - metadata: Dict containing paper metadata
                - text: The cleaned Markdown content
                - sections: Dict mapping section names to content

        Raises:
            MarkdownProcessingError: If the processing fails.
            FileNotFoundError: If the Markdown file does not exist.
        """
        # Validate input
        if not markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        logger.info(f"Processing Markdown file: {markdown_path}")

        try:
            # Read the Markdown content
            with open(markdown_path, encoding="utf-8") as md_file:
                content = md_file.read()

            # Extract metadata
            metadata = self.extract_metadata(content)

            # Extract sections
            sections = self.extract_sections(content)

            # Clean content (remove OCR artifacts, fix formatting issues)
            cleaned_content = self.clean_content(content)

            result = {
                "metadata": metadata,
                "text": cleaned_content,
                "sections": sections,
            }

            logger.info(f"Successfully processed Markdown file: {markdown_path}")
            return result

        except Exception as e:
            error_msg = f"Markdown processing failed: {e!s}"
            logger.error(error_msg)
            raise MarkdownProcessingError(error_msg) from e

    def extract_metadata(self, content: str) -> dict[str, Any]:
        """
        Extract paper metadata from Markdown content.

        Args:
            content (str): The Markdown content.

        Returns:
            Dict[str, Any]: A dictionary containing metadata with keys:
                - title: The paper title
                - authors: List of author names
                - year: Publication year (if available)
                - journal: Journal name (if available)
                - doi: DOI identifier (if available)
                - abstract: Paper abstract (if available)
        """
        metadata = {
            "title": None,
            "authors": [],
            "year": None,
            "journal": None,
            "doi": None,
            "abstract": None,
        }

        # Extract title (first heading)
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            metadata["title"] = title_match.group(1).strip()

        # Extract authors
        authors_match = re.search(
            r"\*\*Authors?:\*\*\s+(.+?)(?:\n\n|\n\*\*)", content, re.DOTALL
        )
        if authors_match:
            authors_text = authors_match.group(1).strip()
            # Split by commas or 'and'
            authors = re.split(r",\s*|\s+and\s+", authors_text)
            metadata["authors"] = [author.strip() for author in authors]

        # Extract year
        year_match = re.search(r"\*\*Year:\*\*\s+(\d{4})", content)
        if year_match:
            try:
                metadata["year"] = int(year_match.group(1))
            except ValueError:
                logger.warning(f"Could not parse year: {year_match.group(1)}")

        # Extract journal
        journal_match = re.search(
            r"\*\*Journal:\*\*\s+(.+?)(?:\n\n|\n\*\*)", content, re.DOTALL
        )
        if journal_match:
            metadata["journal"] = journal_match.group(1).strip()

        # Extract DOI
        doi_match = re.search(r"\*\*DOI:\*\*\s+([\w./]+)", content)
        if doi_match:
            metadata["doi"] = doi_match.group(1).strip()

        # Extract abstract
        abstract_match = re.search(
            r"##\s+Abstract\s*\n\n(.*?)(?:\n\n##|\Z)", content, re.DOTALL
        )
        if abstract_match:
            metadata["abstract"] = abstract_match.group(1).strip()

        return metadata

    def extract_sections(self, content: str) -> dict[str, str]:
        """
        Extract sections from Markdown content.

        Args:
            content (str): The Markdown content.

        Returns:
            Dict[str, str]: A dictionary mapping section names to content.
        """
        sections = {}

        # Find all level 2 headings (##)
        section_matches = re.finditer(
            r"##\s+([^\n]+)\s*\n\n(.*?)(?=\n\n##|\Z)", content, re.DOTALL
        )

        for match in section_matches:
            # Extract the section name and remove any numbering
            # (e.g., "1. Introduction" -> "Introduction")
            full_section_name = match.group(1).strip()
            # Remove section numbering (e.g., "1. ", "1.1 ", etc.)
            section_name = re.sub(r"^\d+(?:\.\d+)*\.\s+", "", full_section_name)
            section_content = match.group(2).strip()
            sections[section_name] = section_content

        return sections

    def clean_content(self, content: str) -> str:
        """
        Clean Markdown content by removing OCR artifacts and fixing formatting.

        Args:
            content (str): The original Markdown content.

        Returns:
            str: The cleaned Markdown content.
        """
        # Remove common OCR artifacts
        cleaned = content

        # Fix multiple consecutive newlines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        # Fix spacing around headings
        # Ensure there are two newlines before headings
        cleaned = re.sub(r"([^\n])\n(#+\s)", r"\1\n\n\2", cleaned)
        # Ensure there are two newlines after headings
        cleaned = re.sub(r"(#+\s.+)\n([^\n])", r"\1\n\n\2", cleaned)

        # Fix list formatting
        # Ensure there are two newlines after the last item in a list
        # before non-list content
        cleaned = re.sub(r"(\n[*-]\s.+)\n([^\s*\-])", r"\1\n\n\2", cleaned)

        return cleaned

    def extract_citations(self, content: str) -> list[dict[str, Any]]:
        """
        Extract citation references from Markdown content.

        Args:
            content (str): The Markdown content.

        Returns:
            List[Dict[str, Any]]: A list of citation dictionaries with
                basic information.
                Each dictionary contains:
                - ref_id: The reference identifier (e.g., "[1]")
                - text: The full citation text
        """
        citations = []

        # Look for references section
        references_match = re.search(
            r"##\s+References\s*\n\n(.*?)(?=\n\n##|\Z)", content, re.DOTALL
        )
        if not references_match:
            return citations

        references_content = references_match.group(1)

        # Extract individual references
        citation_matches = re.finditer(
            r"\[([\d]+)\]\s+(.+?)(?=\n\[[\d]|\Z)", references_content, re.DOTALL
        )

        for match in citation_matches:
            ref_id = match.group(1)
            citation_text = match.group(2).strip()

            citations.append({"ref_id": f"[{ref_id}]", "text": citation_text})

        return citations

"""
Link manager module for Thoth.

This module handles the management of citation links between notes.
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LinkManager:
    """
    Manages citation links between Obsidian notes.

    This class handles the creation and updating of citation links between
    notes, ensuring that citations are properly linked with wikilinks.
    """

    def __init__(self, notes_dir: Path):
        """
        Initialize the link manager.

        Args:
            notes_dir: Directory containing Obsidian notes.
        """
        self.notes_dir = notes_dir

    def update_citation_links(
        self, new_paper: dict[str, Any], notes_dir: Path | None = None
    ) -> None:
        """
        Update citation links in existing notes for a new paper.

        This method finds citations to the new paper in existing notes and
        updates them with proper wikilinks.

        Args:
            new_paper: Dictionary containing paper metadata and path.
            notes_dir: Optional override for notes directory.

        Example:
            >>> link_manager = LinkManager(Path("/path/to/notes"))
            >>> new_paper = {
            ...     "path": Path("/path/to/notes/paper.md"),
            ...     "title": "New Paper Title",
            ...     "authors": ["Author One", "Author Two"],
            ...     "year": 2023
            ... }
            >>> link_manager.update_citation_links(new_paper)
        """
        if notes_dir is None:
            notes_dir = self.notes_dir

        # Validate new_paper
        self._validate_new_paper(new_paper)

        # Find citations to the new paper
        citations_to_paper = self.find_citations_to_paper(new_paper, notes_dir)

        # Update each note with proper wikilinks
        for note_path, citations in citations_to_paper:
            self._update_note_citations(note_path, citations, new_paper)

        # Fix line length issue by breaking the string
        num_notes = len(citations_to_paper)
        paper_title = new_paper["title"]
        logger.info(f"Updated citation links for '{paper_title}' in {num_notes} notes")

    def find_citations_to_paper(
        self, paper: dict[str, Any], notes_dir: Path | None = None
    ) -> list[tuple[Path, list[dict[str, Any]]]]:
        """
        Find citations to a paper in existing notes.

        This method searches through all notes in the notes directory to find
        citations that match the given paper.

        Args:
            paper: Dictionary containing paper metadata.
            notes_dir: Optional override for notes directory.

        Returns:
            List of tuples containing note path and list of citations.

        Example:
            >>> link_manager = LinkManager(Path("/path/to/notes"))
            >>> paper = {
            ...     "title": "Paper Title",
            ...     "authors": ["Author One", "Author Two"],
            ...     "year": 2023
            ... }
            >>> citations = link_manager.find_citations_to_paper(paper)
        """
        if notes_dir is None:
            notes_dir = self.notes_dir

        # Validate paper
        self._validate_paper(paper)

        result = []

        # Get paper title and normalize it for comparison
        paper_title = paper["title"].lower()
        paper_authors = [author.lower() for author in paper["authors"]]
        paper_year = paper.get("year")

        # Iterate through all markdown files in notes_dir
        for note_path in notes_dir.glob("*.md"):
            # Skip the paper's own note
            if "path" in paper and note_path == paper["path"]:
                continue

            # Read the note content
            with open(note_path, encoding="utf-8") as f:
                content = f.read()

            # Find citation sections
            citations = self._extract_citations_from_content(content)

            # Filter citations that match the paper
            matching_citations = []
            for citation in citations:
                if self._citation_matches_paper(
                    citation, paper_title, paper_authors, paper_year
                ):
                    matching_citations.append(citation)

            if matching_citations:
                result.append((note_path, matching_citations))

        return result

    def _update_note_citations(
        self, note_path: Path, citations: list[dict[str, Any]], paper: dict[str, Any]
    ) -> bool:
        """
        Update citations in a note with proper wikilinks.

        Args:
            note_path: Path to the note file.
            citations: List of citations to update.
            paper: Dictionary containing paper metadata and path.

        Returns:
            True if the note was updated, False otherwise.
        """
        # Read the note content
        with open(note_path, encoding="utf-8") as f:
            content = f.read()

        # Create wikilink for the paper
        paper_filename = Path(paper["path"]).name
        wikilink = f"[[{paper_filename.rsplit('.', 1)[0]}]]"

        # Update each citation
        updated_content = content
        for citation in citations:
            if "text" in citation and "start" in citation and "end" in citation:
                # Replace the citation text with a wikilink
                citation_text = citation["text"]
                updated_citation = f"{citation_text} {wikilink}"

                # Replace in content
                updated_content = updated_content.replace(
                    citation_text, updated_citation
                )

        # Write updated content if changes were made
        if updated_content != content:
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
            return True

        return False

    def _extract_citations_from_content(self, content: str) -> list[dict[str, Any]]:
        """
        Extract citations from note content.

        Args:
            content: Note content.

        Returns:
            List of dictionaries containing citation information.
        """
        citations = []

        # Look for citation sections
        citation_sections = re.findall(
            r"## Citations\s+(.+?)(?=##|\Z)", content, re.DOTALL
        )

        if not citation_sections:
            return citations

        for section in citation_sections:
            # Extract individual citations
            citation_entries = re.findall(
                r"\d+\.\s+(.+?)(?=\d+\.\s+|\Z)", section + "\n0. ", re.DOTALL
            )

            for i, entry in enumerate(citation_entries):
                entry = entry.strip()
                if not entry:
                    continue

                # Extract citation details
                title_match = re.search(r'"([^"]+)"', entry)
                # Fix the regex to correctly extract authors
                authors_match = re.match(r'^(.*?),\s*"', entry)
                year_match = re.search(r'(\d{4})', entry)

                if title_match:
                    title = title_match.group(1)
                    authors = []
                    if authors_match:
                        authors_text = authors_match.group(1)
                        authors = [a.strip() for a in authors_text.split(",")]

                    year = None
                    if year_match:
                        try:
                            year = int(year_match.group(1))
                        except ValueError:
                            pass

                    citations.append(
                        {
                            "text": entry,
                            "title": title,
                            "authors": authors,
                            "year": year,
                            "index": i + 1,
                            "start": content.find(entry),
                            "end": content.find(entry) + len(entry),
                        }
                    )

        return citations

    def _citation_matches_paper(
        self,
        citation: dict[str, Any],
        paper_title: str,
        paper_authors: list[str],
        paper_year: int | None,
    ) -> bool:
        """
        Check if a citation matches a paper.

        Args:
            citation: Dictionary containing citation information.
            paper_title: Normalized paper title.
            paper_authors: List of normalized paper authors.
            paper_year: Paper publication year.

        Returns:
            True if the citation matches the paper, False otherwise.
        """
        # Check title similarity
        citation_title = citation.get("title", "").lower()
        title_match = self._is_title_match(citation_title, paper_title)

        if not title_match:
            return False

        # Check authors
        citation_authors = [author.lower() for author in citation.get("authors", [])]
        author_match = self._is_author_match(citation_authors, paper_authors)

        # Check year if available
        year_match = True
        if paper_year is not None and citation.get("year") is not None:
            year_match = citation.get("year") == paper_year

        # Title must match, and either authors or year must match
        return title_match and (author_match or year_match)

    def _is_title_match(self, citation_title: str, paper_title: str) -> bool:
        """
        Check if two titles match.

        Args:
            citation_title: Normalized citation title.
            paper_title: Normalized paper title.

        Returns:
            True if the titles match, False otherwise.
        """
        # Simple string similarity check
        # In a real implementation, we would use more sophisticated
        # string similarity algorithms
        return citation_title in paper_title or paper_title in citation_title

    def _is_author_match(
        self, citation_authors: list[str], paper_authors: list[str]
    ) -> bool:
        """
        Check if two author lists match.

        Args:
            citation_authors: List of normalized citation authors.
            paper_authors: List of normalized paper authors.

        Returns:
            True if the author lists match, False otherwise.
        """
        # Check if at least one author matches
        for author in citation_authors:
            for paper_author in paper_authors:
                if author in paper_author or paper_author in author:
                    return True
        return False

    def _validate_new_paper(self, paper: dict[str, Any]) -> None:
        """
        Validate that a new paper dictionary contains required fields.

        Args:
            paper: Dictionary containing paper metadata.

        Raises:
            ValueError: If required fields are missing.
        """
        required_fields = ["path", "title", "authors"]
        missing_fields = [field for field in required_fields if field not in paper]

        if missing_fields:
            raise ValueError(
                f"Missing required fields in paper: {', '.join(missing_fields)}"
            )

    def _validate_paper(self, paper: dict[str, Any]) -> None:
        """
        Validate that a paper dictionary contains required fields.

        Args:
            paper: Dictionary containing paper metadata.

        Raises:
            ValueError: If required fields are missing.
        """
        required_fields = ["title", "authors"]
        missing_fields = [field for field in required_fields if field not in paper]

        if missing_fields:
            raise ValueError(
                f"Missing required fields in paper: {', '.join(missing_fields)}"
            )

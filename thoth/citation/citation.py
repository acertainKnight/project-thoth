"""
Citation data model for Thoth.

This module defines the Citation class for representing citations extracted from papers.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class Citation:
    """
    Represents a citation extracted from a paper.

    This class stores all relevant information about a citation, including
    bibliographic details and the context in which it appears.

    Attributes:
        title: The title of the cited work.
        authors: List of author names.
        year: The publication year.
        doi: Digital Object Identifier.
        url: URL to the cited work.
        journal: The journal name.
        volume: The journal volume.
        issue: The journal issue.
        pages: The page range.
        context: The context in which the citation appears in the source paper.
    """

    title: str
    authors: list[str]
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    journal: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    context: str | None = None

    def to_ieee_format(self) -> str:
        """
        Format citation in IEEE style.

        Returns:
            str: The citation formatted in IEEE style.

        Example:
            >>> citation = Citation(
            ...     title="Sample Paper",
            ...     authors=["J. Smith", "A. Jones"],
            ...     year=2023,
            ...     journal="Journal of Research",
            ...     volume="10",
            ...     issue="2",
            ...     pages="123-145",
            ...     doi="10.1234/5678"
            ... )
            >>> citation.to_ieee_format()
            'J. Smith, A. Jones, "Sample Paper", Journal of Research, 2023. '
            'DOI: 10.1234/5678'
        """
        # Basic implementation
        authors = ", ".join(self.authors)
        result = f"{authors}, \"{self.title}\""

        if self.journal:
            result += f", {self.journal}"

            # Add volume, issue, and pages if available
            if self.volume:
                result += f", vol. {self.volume}"
                if self.issue:
                    result += f", no. {self.issue}"
            if self.pages:
                result += f", pp. {self.pages}"

        if self.year:
            result += f", {self.year}"

        if self.doi:
            result += f". DOI: {self.doi}"

        return result

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the citation to a dictionary.

        Returns:
            dict[str, Any]: Dictionary representation of the citation.

        Example:
            >>> citation = Citation(title="Sample Paper", authors=["J. Smith"])
            >>> citation.to_dict()
            {'title': 'Sample Paper', 'authors': ['J. Smith'], 'year': None, ...}
        """
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "doi": self.doi,
            "url": self.url,
            "journal": self.journal,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Citation":
        """
        Create a Citation instance from a dictionary.

        Args:
            data: Dictionary containing citation data.

        Returns:
            Citation: A new Citation instance.

        Example:
            >>> data = {"title": "Sample Paper", "authors": ["J. Smith"]}
            >>> citation = Citation.from_dict(data)
            >>> citation.title
            'Sample Paper'
        """
        return cls(
            title=data["title"],
            authors=data["authors"],
            year=data.get("year"),
            doi=data.get("doi"),
            url=data.get("url"),
            journal=data.get("journal"),
            volume=data.get("volume"),
            issue=data.get("issue"),
            pages=data.get("pages"),
            context=data.get("context"),
        )

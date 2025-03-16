"""
Citation Formatter for Thoth.

This module handles the formatting of citations in different styles.
"""

import logging
from enum import Enum, auto

from thoth.citation.citation import Citation

logger = logging.getLogger(__name__)


class CitationStyle(Enum):
    """Enumeration of supported citation styles."""

    IEEE = auto()
    APA = auto()
    MLA = auto()
    CHICAGO = auto()
    HARVARD = auto()


class CitationFormatError(Exception):
    """Exception raised for errors in the citation formatting process."""

    pass


class CitationFormatter:
    """
    Formats citations in different academic styles.

    This class provides methods to format Citation objects in various
    academic citation styles, such as IEEE, APA, MLA, Chicago, and Harvard.
    """

    @staticmethod
    def format_citation(
        citation: Citation, style: CitationStyle = CitationStyle.IEEE
    ) -> str:
        """
        Format a citation according to the specified style.

        Args:
            citation: The Citation object to format.
            style: The citation style to use.

        Returns:
            str: The formatted citation string.

        Raises:
            CitationFormatError: If the formatting fails or the style is not supported.

        Example:
            >>> formatter = CitationFormatter()
            >>> citation = Citation(
            ...     title="Sample Paper",
            ...     authors=["J. Smith", "A. Jones"],
            ...     year=2023,
            ...     journal="Journal of Research"
            ... )
            >>> formatter.format_citation(citation, CitationStyle.IEEE)
            'J. Smith, A. Jones, "Sample Paper", Journal of Research, 2023'
        """
        try:
            if style == CitationStyle.IEEE:
                return citation.to_ieee_format()
            elif style == CitationStyle.APA:
                return CitationFormatter._format_apa(citation)
            elif style == CitationStyle.MLA:
                return CitationFormatter._format_mla(citation)
            elif style == CitationStyle.CHICAGO:
                return CitationFormatter._format_chicago(citation)
            elif style == CitationStyle.HARVARD:
                return CitationFormatter._format_harvard(citation)
            else:
                raise CitationFormatError(f"Unsupported citation style: {style}")
        except Exception as e:
            if isinstance(e, CitationFormatError):
                raise
            error_msg = f"Failed to format citation: {e}"
            logger.error(error_msg)
            raise CitationFormatError(error_msg) from e

    @staticmethod
    def _format_apa(citation: Citation) -> str:
        """
        Format a citation in APA style.

        Args:
            citation: The Citation object to format.

        Returns:
            str: The citation formatted in APA style.

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
            >>> CitationFormatter._format_apa(citation)
            'Smith, J., & Jones, A. (2023). Sample Paper. Journal of Research, '
            '10(2), 123-145. https://doi.org/10.1234/5678'
        """
        # Format authors in APA style (Last, F. M., & Last, F. M.)
        authors_formatted = []
        for author in citation.authors:
            parts = author.split()
            if len(parts) > 1:
                last_name = parts[-1]
                initials = "".join(f"{name[0]}." for name in parts[:-1])
                authors_formatted.append(f"{last_name}, {initials}")
            else:
                authors_formatted.append(author)

        # Join authors with commas and ampersand
        if len(authors_formatted) > 1:
            authors_str = (
                ", ".join(authors_formatted[:-1]) + ", & " + authors_formatted[-1]
            )
        else:
            authors_str = authors_formatted[0] if authors_formatted else ""

        # Start building the citation
        result = authors_str

        # Add year if available
        if citation.year:
            result += f" ({citation.year})."
        else:
            result += "."

        # Add title
        result += f" {citation.title}."

        # Add journal and volume/issue/pages if available
        if citation.journal:
            result += f" {citation.journal}"
            if citation.volume:
                result += f", {citation.volume}"
                if citation.issue:
                    result += f"({citation.issue})"
            if citation.pages:
                result += f", {citation.pages}"
            result += "."

        # Add DOI if available
        if citation.doi:
            result += f" https://doi.org/{citation.doi}"

        return result

    @staticmethod
    def _format_mla(citation: Citation) -> str:
        """
        Format a citation in MLA style.

        Args:
            citation: The Citation object to format.

        Returns:
            str: The citation formatted in MLA style.

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
            >>> CitationFormatter._format_mla(citation)
            'Smith, J., and A. Jones. "Sample Paper." Journal of Research, '
            'vol. 10, no. 2, 2023, pp. 123-145. DOI: 10.1234/5678.'
        """
        # Format authors in MLA style (Last, First M., and First M. Last)
        authors_formatted = []
        for i, author in enumerate(citation.authors):
            parts = author.split()
            if len(parts) > 1:
                if i == 0:  # First author: Last, First
                    last_name = parts[-1]
                    first_names = " ".join(parts[:-1])
                    authors_formatted.append(f"{last_name}, {first_names}")
                else:  # Subsequent authors: First Last
                    authors_formatted.append(author)
            else:
                authors_formatted.append(author)

        # Join authors
        if len(authors_formatted) > 1:
            authors_str = (
                authors_formatted[0] + ", and " + ", and ".join(authors_formatted[1:])
            )
        else:
            authors_str = authors_formatted[0] if authors_formatted else ""

        # Start building the citation
        result = authors_str + "."

        # Add title in quotes
        result += f' "{citation.title}."'

        # Add journal and volume/issue/pages if available
        if citation.journal:
            result += f" {citation.journal}"
            if citation.volume:
                result += f", vol. {citation.volume}"
            if citation.issue:
                result += f", no. {citation.issue}"
            if citation.year:
                result += f", {citation.year}"
            if citation.pages:
                result += f", pp. {citation.pages}"
            result += "."

        # Add DOI if available
        if citation.doi:
            result += f" DOI: {citation.doi}."

        return result

    @staticmethod
    def _format_chicago(citation: Citation) -> str:
        """
        Format a citation in Chicago style.

        Args:
            citation: The Citation object to format.

        Returns:
            str: The citation formatted in Chicago style.

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
            >>> CitationFormatter._format_chicago(citation)
            'Smith, J., and A. Jones. "Sample Paper." Journal of Research 10, '
            'no. 2 (2023): 123-145. https://doi.org/10.1234/5678.'
        """
        # Format authors in Chicago style (Last, First, and First Last)
        authors_formatted = []
        for i, author in enumerate(citation.authors):
            parts = author.split()
            if len(parts) > 1:
                if i == 0:  # First author: Last, First
                    last_name = parts[-1]
                    first_names = " ".join(parts[:-1])
                    authors_formatted.append(f"{last_name}, {first_names}")
                else:  # Subsequent authors: First Last
                    authors_formatted.append(author)
            else:
                authors_formatted.append(author)

        # Join authors
        if len(authors_formatted) > 1:
            authors_str = (
                authors_formatted[0] + ", and " + ", and ".join(authors_formatted[1:])
            )
        else:
            authors_str = authors_formatted[0] if authors_formatted else ""

        # Start building the citation
        result = authors_str + "."

        # Add title in quotes
        result += f' "{citation.title}."'

        # Add journal and volume/issue/pages if available
        if citation.journal:
            result += f" {citation.journal}"
            if citation.volume:
                result += f" {citation.volume}"
                if citation.issue:
                    result += f", no. {citation.issue}"
            if citation.year:
                result += f" ({citation.year})"
            if citation.pages:
                result += f": {citation.pages}"
            result += "."

        # Add DOI if available
        if citation.doi:
            result += f" https://doi.org/{citation.doi}."

        return result

    @staticmethod
    def _format_harvard(citation: Citation) -> str:
        """
        Format a citation in Harvard style.

        Args:
            citation: The Citation object to format.

        Returns:
            str: The citation formatted in Harvard style.

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
            >>> CitationFormatter._format_harvard(citation)
            'Smith, J. and Jones, A. (2023) "Sample Paper", Journal of Research, '
            '10(2), pp. 123-145. doi: 10.1234/5678.'
        """
        # Format authors in Harvard style (Last, F. and Last, F.)
        authors_formatted = []
        for author in citation.authors:
            parts = author.split()
            if len(parts) > 1:
                last_name = parts[-1]
                initials = "".join(f"{name[0]}." for name in parts[:-1])
                authors_formatted.append(f"{last_name}, {initials}")
            else:
                authors_formatted.append(author)

        # Join authors with commas and 'and'
        if len(authors_formatted) > 1:
            authors_str = (
                ", ".join(authors_formatted[:-1]) + " and " + authors_formatted[-1]
            )
        else:
            authors_str = authors_formatted[0] if authors_formatted else ""

        # Start building the citation
        result = authors_str

        # Add year if available
        if citation.year:
            result += f" ({citation.year})"

        # Add title in quotes
        result += f' "{citation.title}"'

        # Add journal and volume/issue/pages if available
        if citation.journal:
            result += f", {citation.journal}"
            if citation.volume:
                result += f", {citation.volume}"
                if citation.issue:
                    result += f"({citation.issue})"
            if citation.pages:
                result += f", pp. {citation.pages}"

        # Add DOI if available
        if citation.doi:
            result += f". doi: {citation.doi}"

        result += "."
        return result


def format_citation(citation: Citation, style: str = "ieee") -> str:
    """
    Format a citation according to the specified style.

    This is a convenience function that wraps the CitationFormatter class.

    Args:
        citation: The Citation object to format.
        style: The citation style to use (ieee, apa, mla, chicago, harvard).

    Returns:
        str: The formatted citation string.

    Raises:
        CitationFormatError: If the formatting fails or the style is not supported.

    Example:
        >>> citation = Citation(
        ...     title="Sample Paper",
        ...     authors=["J. Smith", "A. Jones"],
        ...     year=2023,
        ...     journal="Journal of Research"
        ... )
        >>> format_citation(citation, "apa")
        'Smith, J., & Jones, A. (2023). Sample Paper. Journal of Research.'
    """
    style_map = {
        "ieee": CitationStyle.IEEE,
        "apa": CitationStyle.APA,
        "mla": CitationStyle.MLA,
        "chicago": CitationStyle.CHICAGO,
        "harvard": CitationStyle.HARVARD,
    }

    try:
        citation_style = style_map.get(style.lower())
        if citation_style is None:
            raise CitationFormatError(f"Unsupported citation style: {style}")
        return CitationFormatter.format_citation(citation, citation_style)
    except Exception as e:
        if isinstance(e, CitationFormatError):
            raise
        error_msg = f"Failed to format citation: {e}"
        logger.error(error_msg)
        raise CitationFormatError(error_msg) from e

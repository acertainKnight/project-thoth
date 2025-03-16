"""
URI Generator for Thoth.

This module generates custom URIs for citations in Obsidian.
"""

import logging
import urllib.parse

from thoth.citation.citation import Citation

logger = logging.getLogger(__name__)


class URIGenerator:
    """
    Generates custom URIs for citations in Obsidian.

    This class is responsible for generating custom URIs that can be used
    in Obsidian to link to cited papers.
    """

    # URI scheme for Thoth citations
    URI_SCHEME = "thoth"

    def generate_uri(self, citation: Citation) -> str:
        """
        Generate a custom URI for a citation.

        Args:
            citation: The Citation object.

        Returns:
            str: The generated URI.

        Example:
            >>> citation = Citation(
            ...     title="Sample Paper",
            ...     authors=["J. Smith"],
            ...     doi="10.1234/5678"
            ... )
            >>> generator = URIGenerator()
            >>> generator.generate_uri(citation)
            'thoth://doi:10.1234/5678'
        """
        # Prefer DOI if available
        if citation.doi:
            return f"{self.URI_SCHEME}://doi:{citation.doi}"

        # Fall back to URL if available
        if citation.url:
            # Encode the URL to ensure it's valid in a URI
            encoded_url = urllib.parse.quote(citation.url, safe=":/?&=")
            return f"{self.URI_SCHEME}://url:{encoded_url}"

        # If neither DOI nor URL is available, use the title and authors
        # This is less reliable but better than nothing
        title_part = urllib.parse.quote(citation.title)
        authors_part = urllib.parse.quote(",".join(citation.authors))
        return f"{self.URI_SCHEME}://search?title={title_part}&authors={authors_part}"

    def generate_markdown_link(
        self, citation: Citation, link_text: str | None = None
    ) -> str:
        """
        Generate a Markdown link with a custom URI for a citation.

        Args:
            citation: The Citation object.
            link_text: Optional text to use for the link. If None, uses the
                citation title.

        Returns:
            str: The generated Markdown link.

        Example:
            >>> citation = Citation(
            ...     title="Sample Paper",
            ...     authors=["J. Smith"],
            ...     doi="10.1234/5678"
            ... )
            >>> generator = URIGenerator()
            >>> generator.generate_markdown_link(citation)
            '[Sample Paper](thoth://doi:10.1234/5678)'
        """
        uri = self.generate_uri(citation)
        text = link_text if link_text is not None else citation.title
        return f"[{text}]({uri})"


def generate_uri(citation: Citation) -> str:
    """
    Generate a custom URI for a citation.

    This is a convenience function that creates a URIGenerator and generates a URI.

    Args:
        citation: The Citation object.

    Returns:
        str: The generated URI.

    Example:
        >>> citation = Citation(
        ...     title="Sample Paper",
        ...     authors=["J. Smith"],
        ...     doi="10.1234/5678"
        ... )
        >>> generate_uri(citation)
        'thoth://doi:10.1234/5678'
    """
    generator = URIGenerator()
    return generator.generate_uri(citation)


def generate_markdown_link(citation: Citation, link_text: str | None = None) -> str:
    """
    Generate a Markdown link with a custom URI for a citation.

    This is a convenience function that creates a URIGenerator and generates a
    Markdown link.

    Args:
        citation: The Citation object.
        link_text: Optional text to use for the link. If None, uses the citation title.

    Returns:
        str: The generated Markdown link.

    Example:
        >>> citation = Citation(
        ...     title="Sample Paper",
        ...     authors=["J. Smith"],
        ...     doi="10.1234/5678"
        ... )
        >>> generate_markdown_link(citation)
        '[Sample Paper](thoth://doi:10.1234/5678)'
    """
    generator = URIGenerator()
    return generator.generate_markdown_link(citation, link_text)

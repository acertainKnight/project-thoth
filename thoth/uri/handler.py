"""
URI Handler for Thoth.

This module handles custom URIs for citations in Obsidian.
"""

import logging
import re
import urllib.parse

from thoth.citation.citation import Citation
from thoth.citation.downloader import download_citation
from thoth.config import ThothConfig

logger = logging.getLogger(__name__)


class URIHandlerError(Exception):
    """Exception raised for errors in the URI handling process."""

    pass


class URIHandler:
    """
    Handles custom URIs for citations in Obsidian.

    This class is responsible for processing custom URIs when clicked in Obsidian,
    which typically trigger the download and processing of cited papers.
    """

    # URI scheme for Thoth citations
    URI_SCHEME = "thoth"

    # URI patterns
    DOI_PATTERN = re.compile(r"doi:(?P<doi>10\.\d+/[^/\s]+)")
    URL_PATTERN = re.compile(r"url:(?P<url>https?://[^\s]+)")

    def __init__(self, config: ThothConfig):
        """
        Initialize the URIHandler.

        Args:
            config: The Thoth configuration.
        """
        self.config = config
        self.pdf_dir = config.pdf_dir

    def process_uri(self, uri: str) -> bool:
        """
        Process a custom URI and trigger appropriate actions.

        Args:
            uri: The URI to process.

        Returns:
            bool: True if the URI was processed successfully, False otherwise.

        Example:
            >>> handler = URIHandler(config)
            >>> handler.process_uri("thoth://doi:10.1234/5678")
            True
        """
        try:
            # Parse the URI
            parsed_uri = urllib.parse.urlparse(uri)

            # Check if this is a Thoth URI
            if parsed_uri.scheme != self.URI_SCHEME:
                logger.warning(f"Not a Thoth URI: {uri}")
                return False

            # Extract the path (removing leading slash if present)
            path = parsed_uri.netloc + parsed_uri.path
            if path.startswith("/"):
                path = path[1:]

            # Process based on the path
            if doi_match := self.DOI_PATTERN.search(path):
                return self._process_doi(doi_match.group("doi"))
            elif url_match := self.URL_PATTERN.search(path):
                return self._process_url(url_match.group("url"))
            else:
                logger.warning(f"Unrecognized Thoth URI format: {uri}")
                return False

        except Exception as e:
            logger.error(f"Error processing URI {uri}: {e!s}")
            return False

    def _process_doi(self, doi: str) -> bool:
        """
        Process a DOI URI.

        Args:
            doi: The DOI to process.

        Returns:
            bool: True if the DOI was processed successfully, False otherwise.
        """
        logger.info(f"Processing DOI: {doi}")

        # Create a minimal citation with just the DOI
        citation = Citation(
            title=f"Unknown Title (DOI: {doi})", authors=["Unknown Author"], doi=doi
        )

        # Download the citation
        pdf_path = download_citation(citation, self.pdf_dir)

        # Return success if the PDF was downloaded
        return pdf_path is not None

    def _process_url(self, url: str) -> bool:
        """
        Process a URL URI.

        Args:
            url: The URL to process.

        Returns:
            bool: True if the URL was processed successfully, False otherwise.
        """
        logger.info(f"Processing URL: {url}")

        # Create a minimal citation with just the URL
        citation = Citation(
            title=f"Unknown Title (URL: {url})", authors=["Unknown Author"], url=url
        )

        # Download the citation
        pdf_path = download_citation(citation, self.pdf_dir)

        # Return success if the PDF was downloaded
        return pdf_path is not None


def process_uri(uri: str, config: ThothConfig) -> bool:
    """
    Process a custom URI and trigger appropriate actions.

    This is a convenience function that creates a URIHandler and processes the URI.

    Args:
        uri: The URI to process.
        config: The Thoth configuration.

    Returns:
        bool: True if the URI was processed successfully, False otherwise.

    Example:
        >>> process_uri("thoth://doi:10.1234/5678", config)
        True
    """
    handler = URIHandler(config)
    return handler.process_uri(uri)

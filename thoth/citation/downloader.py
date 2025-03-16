"""
Citation Downloader for Thoth.

This module handles the downloading of cited papers from DOI or URL.
"""

import logging
import re
import urllib.parse
from pathlib import Path

import requests
from requests.exceptions import RequestException

from thoth.citation.citation import Citation
from thoth.utils.file import ensure_directory

logger = logging.getLogger(__name__)


class CitationDownloadError(Exception):
    """Exception raised for errors in the citation download process."""

    pass


class CitationDownloader:
    """
    Downloads cited papers from DOI or URL.

    This class is responsible for downloading papers referenced in citations,
    using either DOI or direct URL links.
    """

    def __init__(self, output_dir: Path):
        """
        Initialize the CitationDownloader.

        Args:
            output_dir: Directory where downloaded PDFs will be saved.
        """
        self.output_dir = output_dir
        ensure_directory(self.output_dir)

    def download_citation(self, citation: Citation) -> Path | None:
        """
        Download a cited paper and return the path to the PDF.

        Args:
            citation: The Citation object containing DOI or URL.

        Returns:
            Optional[Path]: Path to the downloaded PDF, or None if download failed.

        Raises:
            CitationDownloadError: If the download fails.

        Example:
            >>> downloader = CitationDownloader(Path("/path/to/pdfs"))
            >>> citation = Citation(
            ...     title="Sample Paper",
            ...     authors=["J. Smith"],
            ...     doi="10.1234/5678"
            ... )
            >>> pdf_path = downloader.download_citation(citation)
        """
        try:
            result = None

            # Try DOI first if available
            if citation.doi:
                logger.info(
                    f"Attempting to download citation using DOI: {citation.doi}"
                )
                result = self._download_from_doi(citation.doi, citation.title)

            # Fall back to URL if DOI failed or not available
            if result is None and citation.url:
                logger.info(
                    f"Attempting to download citation using URL: {citation.url}"
                )
                result = self._download_from_url(citation.url, citation.title)

            # If both DOI and URL failed or not available, try to search for the paper
            if result is None:
                logger.info(
                    f"No DOI/URL available or download failed, searching: "
                    f"{citation.title}"
                )
                result = self._search_and_download(citation)

            return result

        except Exception as e:
            if isinstance(e, CitationDownloadError):
                raise
            error_msg = f"Failed to download citation: {e}"
            logger.error(error_msg)
            raise CitationDownloadError(error_msg) from e

    def _download_from_doi(self, doi: str, title: str) -> Path | None:
        """
        Download a paper using its DOI.

        Args:
            doi: The DOI of the paper.
            title: The title of the paper (used for filename if not in response).

        Returns:
            Optional[Path]: Path to the downloaded PDF, or None if download failed.
        """
        # Clean the DOI
        doi = doi.strip()

        # Construct the DOI URL
        doi_url = f"https://doi.org/{doi}"

        # Try to resolve the DOI to get the actual paper URL
        try:
            headers = {
                "Accept": "application/pdf, text/html",
                "User-Agent": "Thoth Research Assistant (https://thoth.ai)",
            }

            # First make a HEAD request to check if we can get a direct PDF
            response = requests.head(
                doi_url,
                headers=headers,
                allow_redirects=True,
                timeout=30,
            )

            final_url = response.url

            # If the final URL ends with .pdf, download it directly
            if final_url.lower().endswith(".pdf"):
                return self._download_pdf(final_url, title)

            # Otherwise, try to find a PDF link on the landing page
            response = requests.get(
                final_url,
                headers=headers,
                timeout=30,
            )

            # Look for PDF links in the HTML
            pdf_links = re.findall(r'href="([^"]+\.pdf)"', response.text)
            if pdf_links:
                # Convert relative URLs to absolute
                pdf_url = urllib.parse.urljoin(final_url, pdf_links[0])
                return self._download_pdf(pdf_url, title)

            logger.warning(f"Could not find PDF link for DOI: {doi}")
            return None

        except RequestException as e:
            logger.warning(f"Failed to resolve DOI {doi}: {e}")
            return None

    def _download_from_url(self, url: str, title: str) -> Path | None:
        """
        Download a paper from a direct URL.

        Args:
            url: The URL of the paper.
            title: The title of the paper (used for filename if not in response).

        Returns:
            Optional[Path]: Path to the downloaded PDF, or None if download failed.
        """
        # Clean the URL
        url = url.strip()

        # If the URL already points to a PDF, download it directly
        if url.lower().endswith(".pdf"):
            return self._download_pdf(url, title)

        # Otherwise, try to find a PDF link on the page
        try:
            headers = {
                "Accept": "application/pdf, text/html",
                "User-Agent": "Thoth Research Assistant (https://thoth.ai)",
            }

            response = requests.get(
                url,
                headers=headers,
                timeout=30,
            )

            # Look for PDF links in the HTML
            pdf_links = re.findall(r'href="([^"]+\.pdf)"', response.text)
            if pdf_links:
                # Convert relative URLs to absolute
                pdf_url = urllib.parse.urljoin(url, pdf_links[0])
                return self._download_pdf(pdf_url, title)

            logger.warning(f"Could not find PDF link at URL: {url}")
            return None

        except RequestException as e:
            logger.warning(f"Failed to access URL {url}: {e}")
            return None

    def _search_and_download(self, citation: Citation) -> Path | None:
        """
        Search for a paper based on its metadata and download it.

        Args:
            citation: The Citation object containing metadata.

        Returns:
            Optional[Path]: Path to the downloaded PDF, or None if download failed.
        """
        # Construct a search query
        authors = citation.authors[0].split()[-1] if citation.authors else ""
        year = f" {citation.year}" if citation.year else ""
        query = f"{citation.title} {authors}{year}"

        # Try to search using Semantic Scholar API
        try:
            headers = {
                "Accept": "application/json",
                "User-Agent": "Thoth Research Assistant (https://thoth.ai)",
            }

            # Search for the paper
            search_url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={urllib.parse.quote(query)}&limit=1"
            response = requests.get(
                search_url,
                headers=headers,
                timeout=30,
            )

            if response.status_code != 200:
                logger.warning(
                    f"Semantic Scholar API returned error: {response.status_code}"
                )
                return None

            data = response.json()
            if not data.get("data") or len(data["data"]) == 0:
                logger.warning(f"No results found for query: {query}")
                return None

            # Get the paper ID
            paper_id = data["data"][0]["paperId"]

            # Get the paper details
            paper_url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}?fields=openAccessPdf"
            response = requests.get(
                paper_url,
                headers=headers,
                timeout=30,
            )

            if response.status_code != 200:
                logger.warning(
                    f"Semantic Scholar API returned error: {response.status_code}"
                )
                return None

            data = response.json()
            if data.get("openAccessPdf") and data["openAccessPdf"].get("url"):
                pdf_url = data["openAccessPdf"]["url"]
                return self._download_pdf(pdf_url, citation.title)

            logger.warning(f"No open access PDF found for paper: {citation.title}")
            return None

        except RequestException as e:
            logger.warning(f"Failed to search for paper: {e}")
            return None

    def _download_pdf(self, url: str, title: str) -> Path:
        """
        Download a PDF from a URL.

        Args:
            url: The URL of the PDF.
            title: The title of the paper (used for filename).

        Returns:
            Path: Path to the downloaded PDF.

        Raises:
            CitationDownloadError: If the download fails.
        """
        try:
            # Create a safe filename from the title
            safe_title = re.sub(r'[^\w\-\.]', '_', title)
            if len(safe_title) > 100:
                safe_title = safe_title[:100]  # Limit filename length

            # Add a timestamp to avoid filename collisions
            filename = f"{safe_title}.pdf"
            output_path = self.output_dir / filename

            # Download the PDF
            headers = {
                "User-Agent": "Thoth Research Assistant (https://thoth.ai)",
            }

            response = requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=60,  # Longer timeout for PDF downloads
            )

            if response.status_code != 200:
                raise CitationDownloadError(
                    f"Failed to download PDF: HTTP {response.status_code}"
                )

            # Check if the response is actually a PDF
            content_type = response.headers.get("Content-Type", "").lower()
            if "application/pdf" not in content_type and not url.lower().endswith(
                ".pdf"
            ):
                raise CitationDownloadError(
                    f"URL does not point to a PDF: {content_type}"
                )

            # Save the PDF
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Successfully downloaded PDF to {output_path}")
            return output_path

        except RequestException as e:
            raise CitationDownloadError(f"Failed to download PDF: {e}") from e


def download_citation(citation: Citation, output_dir: Path) -> Path | None:
    """
    Download a cited paper and return the path to the PDF.

    This is a convenience function that creates a CitationDownloader and uses it
    to download the cited paper.

    Args:
        citation: The Citation object containing DOI or URL.
        output_dir: Directory where downloaded PDFs will be saved.

    Returns:
        Optional[Path]: Path to the downloaded PDF, or None if download failed.

    Raises:
        CitationDownloadError: If the download fails.

    Example:
        >>> citation = Citation(
        ...     title="Sample Paper",
        ...     authors=["J. Smith"],
        ...     doi="10.1234/5678"
        ... )
        >>> pdf_path = download_citation(citation, Path("/path/to/pdfs"))
    """
    downloader = CitationDownloader(output_dir)
    return downloader.download_citation(citation)

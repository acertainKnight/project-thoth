"""
Web search utilities for finding missing citation information.

This module provides functionality to search for academic papers and extract
citation information using the Scholarly library, which interfaces with
Google Scholar without requiring API keys.
"""

import re
import time
from collections.abc import Callable
from typing import Any, TypeVar

import httpx
from loguru import logger
from scholarly import scholarly
from scholarly._proxy_generator import (
    MaxTriesExceededException as ScholarlyMaxTriesExceededException,
)

from thoth.utilities.schemas import Citation, SearchResult

# Define a generic type variable for the return type of the wrapped scholarly function
R = TypeVar('R')


class ScholarlyAPI:
    """Client for interacting with Google Scholar via Scholarly library."""

    def __init__(
        self,
        timeout: int = 10,
        max_retries: int = 0,
        initial_delay_seconds: float = 2.0,
    ):
        """
        Initialize Google Scholar client using Scholarly library.

        Args:
            timeout: Timeout for individual scholarly operations if applicable (scholarly manages its own timeouts internally mostly).
            max_retries: Maximum number of retry attempts for failed scholarly calls.
            initial_delay_seconds: Initial delay for exponential backoff in seconds.
        """  # noqa: W505
        self.timeout = timeout
        self.max_retries = max_retries
        self.initial_delay_seconds = initial_delay_seconds
        self.client = httpx.Client(timeout=timeout)

    def _call_scholarly_with_retry(
        self, func: Callable[..., R], *args: Any, **kwargs: Any
    ) -> R:
        """
        Wrap a scholarly library call with retry logic and exponential backoff.

        Args:
            func: The scholarly function to call (e.g., scholarly.search_pubs, scholarly.fill).
            *args: Positional arguments for the scholarly function.
            **kwargs: Keyword arguments for the scholarly function.

        Returns:
            R: The result of the scholarly function call.

        Raises:
            Exception: Re-raises the last exception if all retries fail.
        """  # noqa: W505
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f'Calling scholarly function {func.__name__} (Attempt {attempt + 1}/{self.max_retries + 1})'
                )
                return func(*args, **kwargs)
            except ScholarlyMaxTriesExceededException as e:
                logger.warning(
                    f'Scholarly call {func.__name__} failed with MaxTriesExceededException (Attempt {attempt + 1}): {e}'
                )
                if attempt < self.max_retries:
                    sleep_duration = self.initial_delay_seconds * (2**attempt)
                    logger.info(f'Retrying after {sleep_duration:.2f} seconds.')
                    time.sleep(sleep_duration)
                else:
                    logger.error(
                        f'Scholarly call {func.__name__} failed after {self.max_retries + 1} attempts.'
                    )
                    raise
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                status_code = (
                    e.response.status_code
                    if isinstance(e, httpx.HTTPStatusError)
                    else 'N/A'
                )
                logger.warning(
                    f'Scholarly call {func.__name__} failed with HTTP/Request error (Status: {status_code}) (Attempt {attempt + 1}): {e}'
                )
                if attempt < self.max_retries:
                    should_retry = True
                    if isinstance(e, httpx.HTTPStatusError) and status_code == 429:
                        logger.info(
                            'Rate limit (429) likely from underlying HTTP call.'
                        )
                    elif (
                        isinstance(e, httpx.HTTPStatusError)
                        and 400 <= status_code < 500
                        and status_code != 429
                    ):
                        logger.error(
                            f'Client error {status_code} from underlying HTTP call, not retrying.'
                        )
                        raise

                    if should_retry:
                        sleep_duration = self.initial_delay_seconds * (2**attempt)
                        logger.info(f'Retrying after {sleep_duration:.2f} seconds.')
                        time.sleep(sleep_duration)
                else:
                    logger.error(
                        f'Scholarly call {func.__name__} failed after {self.max_retries + 1} attempts due to HTTP/Request error.'
                    )
                    raise
            except Exception as e:
                logger.warning(
                    f'Scholarly call {func.__name__} failed with an unexpected error (Attempt {attempt + 1}): {type(e).__name__} - {e}'
                )
                if attempt < self.max_retries:
                    sleep_duration = self.initial_delay_seconds * (2**attempt)
                    logger.info(f'Retrying after {sleep_duration:.2f} seconds.')
                    time.sleep(sleep_duration)
                else:
                    logger.error(
                        f'Scholarly call {func.__name__} failed after {self.max_retries + 1} attempts due to an unexpected error.'
                    )
                    raise
        raise Exception(f'Scholarly call {func.__name__} failed exhaustively.')

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        """
        Perform a search using the Google Scholar API via Scholarly, with retries.

        Args:
            query: Search query string.
            num_results: Number of results to return.

        Returns:
            list[SearchResult]: List of search results.

        Example:
            >>> api.search('Smith J, Jones K. Title of paper. Journal. 2023')
            [{"title": "...", "link": "...", "snippet": "...", "position": 1}, ...]
        """
        try:
            search_query_gen = self._call_scholarly_with_retry(
                scholarly.search_pubs, query
            )

            results = []
            for i in range(num_results):
                try:
                    pub = next(search_query_gen)

                    # Extract relevant information
                    title = pub.get('bib', {}).get('title', '')
                    snippet = f'{pub.get("bib", {}).get("abstract", "")} {pub.get("bib", {}).get("venue", "")}'

                    # Get URL (either direct URL or DOI URL)
                    link = pub.get('pub_url', '')
                    if not link and 'doi' in pub:
                        link = f'https://doi.org/{pub["doi"]}'

                    result = SearchResult(
                        title=title, link=link, snippet=snippet, position=i + 1
                    )
                    results.append(result)
                except StopIteration:
                    break
                except Exception as e:
                    logger.error(f'Error processing search result: {e}')

            return results
        except Exception as e:
            logger.error(f"Failed to search for query '{query}': {e}")
            return []

    def find_doi_sync(self, citation: Citation) -> str | None:
        """
        Find a DOI for a citation using Google Scholar.

        Args:
            citation: The citation to find a DOI for.

        Returns:
            Optional[str]: The DOI if found, None otherwise.
        """
        # Construct a search query using available citation information
        query_parts = []

        # Add title if available (most important for Scholar search)
        if citation.title:
            query_parts.append(f'"{citation.title}"')

        # Add authors if available
        if citation.authors:
            authors_str = ' '.join(citation.authors)
            query_parts.append(authors_str)

        # Add year if available
        if citation.year:
            query_parts.append(str(citation.year))

        # Add journal if available
        if citation.journal:
            query_parts.append(citation.journal)

        # Construct the query
        query = ' '.join(query_parts)

        # Perform the search
        results = self.search(query, num_results=3)

        # First try to find DOI in the search results
        for result in results:
            # Try to extract DOI from URL
            if 'doi.org/' in result.link:
                doi = result.link.split('doi.org/')[-1]
                return doi

        # If not found in URLs, try to get details of the first result
        if results:
            try:
                # Get the full publication details for the first result
                # We need to search again to get the publication ID, then fill
                # This is potentially fragile if search results are not stable.
                search_query_gen = self._call_scholarly_with_retry(
                    scholarly.search_pubs, query
                )
                try:
                    first_pub_from_search = next(search_query_gen)
                    if first_pub_from_search:
                        # `scholarly.fill` makes network calls and should be retried
                        # It modifies the publication object in-place.
                        filled_pub = self._call_scholarly_with_retry(
                            scholarly.fill, first_pub_from_search
                        )
                        if filled_pub.get('doi'):
                            return filled_pub['doi']
                except StopIteration:
                    logger.debug(
                        'No results from scholarly.search_pubs in find_doi_sync for detailed fill.'
                    )
                except Exception as e:
                    logger.warning(
                        f'Error during the fill process in find_doi_sync: {e}'
                    )

            except Exception as e:
                logger.error(f'Error retrieving detailed publication for DOI: {e}')

        # If still not found, look for DOI patterns in snippets
        doi_pattern = r'10\.\d{4,9}/[-._;()/:\w]+'
        for result in results:
            matches = re.findall(doi_pattern, result.snippet)
            if matches:
                return matches[0]

        return None

    # Alias for backward compatibility
    find_doi = find_doi_sync

    def find_pdf_url_sync(self, citation: Citation) -> str | None:
        """
        Find a PDF URL for a citation using Google Scholar.

        Args:
            citation: The citation to find a PDF URL for.

        Returns:
            Optional[str]: The PDF URL if found, None otherwise.
        """
        # Construct a search query using available citation information
        query_parts = []

        # Add title if available (most important for Scholar search)
        if citation.title:
            query_parts.append(f'"{citation.title}"')

        # Add authors if available
        if citation.authors:
            authors_str = ' '.join(citation.authors)
            query_parts.append(authors_str)

        # Add year if available
        if citation.year:
            query_parts.append(str(citation.year))

        # Add journal if available
        if citation.journal:
            query_parts.append(citation.journal)

        # Add "pdf" to the query to prioritize PDF results
        query_parts.append('pdf')

        # Construct the query
        query = ' '.join(query_parts)

        # Perform the search
        results = self.search(query, num_results=5)

        # Look for PDF URLs in the search results
        for result in results:
            if result.link and (result.link.endswith('.pdf') or '/pdf/' in result.link):
                return result.link

        # If no direct PDF link found but we have a DOI, try to use that
        if citation.doi:
            try:
                # Try unpaywall.org or similar services
                # For now, just return the DOI link as a fallback
                return f'https://doi.org/{citation.doi}'
            except Exception as e:
                logger.error(f'Error finding PDF from DOI: {e}')

        return None

    # Alias for backward compatibility
    find_pdf_url = find_pdf_url_sync

    def find_alternative_id_sync(self, citation: Citation) -> str | None:
        """
        Find an alternative identifier (e.g., arXiv ID) for a citation when DOI is not available.

        Args:
            citation: The citation to find an alternative ID for.

        Returns:
            Optional[str]: The alternative ID if found, None otherwise.
        """  # noqa: W505
        # Construct a search query using available citation information
        query_parts = []

        # Add title if available (most important for Scholar search)
        if citation.title:
            query_parts.append(f'"{citation.title}"')

        # Add authors if available
        if citation.authors:
            authors_str = ' '.join(citation.authors)
            query_parts.append(authors_str)

        # Add year if available
        if citation.year:
            query_parts.append(str(citation.year))

        # Add journal if available
        if citation.journal:
            query_parts.append(citation.journal)

        # Construct the query
        query = ' '.join(query_parts)

        # Perform the search
        results = self.search(query, num_results=3)

        # Try to find arXiv ID patterns in URLs and snippets
        arxiv_pattern = r'(?:arxiv:)?([\d\.]+(?:v\d+)?)'  # noqa: F841
        for result in results:
            # Check URL for arXiv pattern
            if 'arxiv.org' in result.link:
                arxiv_matches = re.search(
                    r'arxiv\.org/(?:abs|pdf)/([^/]+)', result.link
                )
                if arxiv_matches:
                    arxiv_id = arxiv_matches.group(1)
                    return f'arxiv:{arxiv_id}'

            # Check snippet for arXiv mentions
            arxiv_text_matches = re.search(
                r'(?:arxiv:?|arxiv\.org/(?:abs|pdf)/)([^/\s]+)',
                result.snippet,
                re.IGNORECASE,
            )
            if arxiv_text_matches:
                arxiv_id = arxiv_text_matches.group(1)
                return f'arxiv:{arxiv_id}'

        # If not found in URLs or snippets, try to get details of the first result
        if results:
            try:
                # Get the full publication details for the first result
                search_query_gen = self._call_scholarly_with_retry(
                    scholarly.search_pubs, query
                )
                try:
                    first_pub_from_search = next(search_query_gen)
                    pub_id = first_pub_from_search.get('pub_id')  # noqa: F841
                    if first_pub_from_search:
                        # `scholarly.fill` makes network calls and should be retried
                        # It modifies the publication object in-place.
                        detailed_pub = self._call_scholarly_with_retry(
                            scholarly.fill, first_pub_from_search
                        )

                        # Look for arXiv ID in various fields
                        if (
                            'eprint_url' in detailed_pub
                            and detailed_pub['eprint_url']
                            and 'arxiv.org' in detailed_pub['eprint_url']
                        ):
                            arxiv_matches = re.search(
                                r'arxiv\.org/(?:abs|pdf)/([^/]+)',
                                detailed_pub['eprint_url'],
                            )
                            if arxiv_matches:
                                return f'arxiv:{arxiv_matches.group(1)}'
                        if detailed_pub.get('eprint'):
                            # Check if it looks like an arXiv ID (common pattern)
                            if (
                                re.match(
                                    r'^\d{4}\.\d{4,5}(v\d+)?$', detailed_pub['eprint']
                                )
                                or 'arxiv' in detailed_pub['eprint'].lower()
                            ):
                                return f'arxiv:{detailed_pub["eprint"].replace("arxiv:", "", 1).strip()}'

                        # Check URL and other fields for arXiv patterns
                        for field in ['url', 'pub_url']:
                            value = detailed_pub.get(field, '')
                            if value and 'arxiv.org' in value:
                                arxiv_matches = re.search(
                                    r'arxiv\.org/(?:abs|pdf)/([^/]+)', value
                                )
                                if arxiv_matches:
                                    return f'arxiv:{arxiv_matches.group(1)}'
                except StopIteration:
                    logger.debug(
                        'No results from scholarly.search_pubs in find_alternative_id_sync for detailed fill.'
                    )
                except Exception as e:
                    logger.warning(
                        f'Error during the fill process in find_alternative_id_sync: {e}'
                    )
            except Exception as e:
                logger.error(
                    f'Error retrieving detailed publication for alternative ID: {e}'
                )

        # Try to find ISBN patterns for books
        isbn_pattern = r'(?:ISBN[-:]?\s*)?(?:13[-:]?\s*)?(?=[0-9]{13}|(?=[0-9X]{10}))'
        for result in results:
            isbn_matches = re.search(isbn_pattern, result.snippet)
            if isbn_matches:
                isbn = isbn_matches.group(0)
                # Remove any non-alphanumeric characters
                isbn = re.sub(r'[^0-9X]', '', isbn)
                return f'isbn:{isbn}'

        return None

    # Alias for backward compatibility
    find_alternative_id = find_alternative_id_sync

    def close(self) -> None:
        """Close the client session."""
        try:
            if self.client:
                self.client.close()
                self.client = None
        except Exception as e:
            logger.error(f'Failed to close client: {e}')

    def __del__(self):
        """Ensure client is closed on deletion."""
        try:
            self.close()
        except Exception:
            pass

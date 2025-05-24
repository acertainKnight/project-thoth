"""
Citation utilities for interacting with Semantic Scholar API.
"""

import time
import urllib.parse
from typing import Any

import httpx
from loguru import logger

from thoth.utilities.models import Citation


class SemanticScholarAPI:
    """Client for interacting with Semantic Scholar API to retrieve citation metadata."""  # noqa: W505

    def __init__(
        self,
        base_url: str = 'https://api.semanticscholar.org/graph/v1',
        api_key: str | None = None,
        timeout: int = 10,
        delay_seconds: float = 1.0,
        max_retries: int = 9,
    ):
        """
        Initialize Semantic Scholar API client.

        Args:
            base_url: Base URL for the Semantic Scholar API.
            api_key: Semantic Scholar API key for authentication (recommended for higher rate limits).
            timeout: Timeout for API requests in seconds.
            delay_seconds: Delay between API requests to avoid rate limiting.
            max_retries: Maximum number of retry attempts for failed requests.
        """  # noqa: W505
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries

        self.client = httpx.Client(timeout=timeout)
        self.last_request_time = 0

        if not api_key:
            logger.warning(
                'No Semantic Scholar API key provided. Using public API access with lower rate limits.'
            )

    def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Make a request to the Semantic Scholar API with rate limiting and retries.

        Args:
            endpoint: API endpoint to call.
            params: API query parameters.

        Returns:
            dict | None: JSON response data or None if the request failed.

        Raises:
            httpx.HTTPError: If the request fails after retries.
        """
        # Implement rate limiting
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.delay_seconds:
            sleep_time = self.delay_seconds - time_since_last_request
            logger.debug(
                f'Rate limiting: sleeping for {sleep_time:.2f} seconds before request.'
            )
            time.sleep(sleep_time)

        # Prepare headers
        headers = {'Accept': 'application/json'}
        if self.api_key:
            headers['x-api-key'] = self.api_key

        # Prepare URL with parameters
        url = f'{self.base_url}/{endpoint}'
        if params:
            url = f'{url}?{urllib.parse.urlencode(params)}'

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f'Making request to Semantic Scholar API: {url} (Attempt {attempt + 1}/{self.max_retries + 1})'
                )
                response = self.client.get(url, headers=headers)
                self.last_request_time = (
                    time.time()
                )  # Update last request time after the call
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f'Semantic Scholar API request failed (Attempt {attempt + 1}/{self.max_retries + 1}): '
                    f'Status {e.response.status_code} - {e.response.text}'
                )
                if attempt < self.max_retries:
                    if e.response.status_code == 429:  # Too Many Requests
                        # Respect Retry-After header if present
                        retry_after_str = e.response.headers.get('Retry-After')
                        if retry_after_str:
                            try:
                                sleep_duration = int(retry_after_str)
                                logger.info(
                                    f'Rate limit hit (429). Retrying after {sleep_duration} seconds (from Retry-After header).'
                                )
                            except ValueError:
                                # Default to exponential backoff if Retry-After is not an int  # noqa: W505
                                sleep_duration = self.delay_seconds * (2**attempt)
                                logger.info(
                                    f'Rate limit hit (429). Retrying after {sleep_duration:.2f} seconds (exponential backoff).'
                                )
                        else:
                            sleep_duration = self.delay_seconds * (
                                2**attempt
                            )  # Exponential backoff
                            logger.info(
                                f'Rate limit hit (429). Retrying after {sleep_duration:.2f} seconds (exponential backoff).'
                            )
                        time.sleep(sleep_duration)
                    elif e.response.status_code >= 500:  # Server-side errors
                        sleep_duration = self.delay_seconds * (
                            2**attempt
                        )  # Exponential backoff
                        logger.warning(
                            f'Server error ({e.response.status_code}). Retrying after {sleep_duration:.2f} seconds.'
                        )
                        time.sleep(sleep_duration)
                    else:  # Other client-side errors that might not be worth retrying or need different strategy
                        raise  # Re-raise immediately for other client errors
                else:
                    logger.error(
                        f'Failed to make Semantic Scholar API request after {self.max_retries + 1} attempts: {e}'
                    )
                    raise
            except httpx.RequestError as e:  # Includes network errors, timeouts etc.
                logger.warning(
                    f'Semantic Scholar API request failed due to network/request error (Attempt {attempt + 1}/{self.max_retries + 1}): {e}'
                )
                if attempt < self.max_retries:
                    sleep_duration = self.delay_seconds * (
                        2**attempt
                    )  # Exponential backoff
                    logger.info(f'Retrying after {sleep_duration:.2f} seconds.')
                    time.sleep(sleep_duration)
                else:
                    logger.error(
                        f'Failed to make Semantic Scholar API request after {self.max_retries + 1} attempts due to network/request error: {e}'
                    )
                    raise
            except Exception as e:  # Catch any other unexpected errors
                logger.error(
                    f'An unexpected error occurred while processing Semantic Scholar API response (Attempt {attempt + 1}): {e}'
                )
                if attempt == self.max_retries:  # if it's the last attempt
                    raise  # Re-raise the caught exception
                # For unexpected errors, a simple delay might be enough before retry
                sleep_duration = self.delay_seconds * (2**attempt)
                logger.info(
                    f'Retrying after {sleep_duration:.2f} seconds due to unexpected error.'
                )
                time.sleep(sleep_duration)
        return None  # Should be unreachable if max_retries is handled correctly

    def paper_lookup_by_doi(
        self, doi: str, fields: list[str] | None = None
    ) -> dict[str, Any] | None:
        """
        Look up a paper by DOI.

        Args:
            doi: The DOI of the paper to look up.
            fields: Specific fields to return in the response.

        Returns:
            dict | None: Paper metadata or None if not found.
        """
        params = {}
        if fields:
            params['fields'] = ','.join(fields)

        try:
            endpoint = f'paper/DOI:{doi}'
            return self._make_request(endpoint, params)
        except Exception as e:
            logger.error(f'Failed to look up paper by DOI {doi}: {e}')
            return None

    def paper_lookup_by_arxiv(
        self, arxiv_id: str, fields: list[str] | None = None
    ) -> dict[str, Any] | None:
        """
        Look up a paper by arXiv ID.

        Args:
            arxiv_id: The arXiv ID of the paper to look up.
            fields: Specific fields to return in the response.

        Returns:
            dict | None: Paper metadata or None if not found.
        """
        params = {}
        if fields:
            params['fields'] = ','.join(fields)

        try:
            endpoint = f'paper/arXiv:{arxiv_id}'
            return self._make_request(endpoint, params)
        except Exception as e:
            logger.error(f'Failed to look up paper by arXiv ID {arxiv_id}: {e}')
            return None

    def paper_search(
        self,
        query: str,
        fields: list[str] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Search for papers matching the query.

        Args:
            query: Search query (title, authors, etc.).
            fields: Specific fields to return in the response.
            limit: Maximum number of results to return.
            offset: Offset for pagination.

        Returns:
            list: List of papers matching the search criteria.
        """
        params = {
            'query': query,
            'limit': limit,
            'offset': offset,
        }
        if fields:
            params['fields'] = ','.join(fields)

        try:
            endpoint = 'paper/search'
            response = self._make_request(endpoint, params)
            if response and 'data' in response:
                return response['data']
            return []
        except Exception as e:
            logger.error(f"Failed to search papers with query '{query}': {e}")
            return []

    def paper_lookup_batch(
        self,
        paper_ids: list[str],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Look up multiple papers by their IDs in a single batch request.

        Args:
            paper_ids: List of paper IDs with prefixes (e.g., ["DOI:10.1234/xyz", "arXiv:1234.5678"]).
            fields: Specific fields to return in the response.

        Returns:
            list: List of paper metadata records.
        """  # noqa: W505
        params = {}
        if fields:
            params['fields'] = ','.join(fields)

        try:
            # Convert the list to the required format for the Semantic Scholar API
            ids_payload = {'ids': paper_ids}

            # Use POST for batch requests
            headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
            if self.api_key:
                headers['x-api-key'] = self.api_key

            url = f'{self.base_url}/paper/batch'
            if params:
                url = f'{url}?{urllib.parse.urlencode(params)}'

            response = self.client.post(url, json=ids_payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            if 'data' in data:
                return data['data']
            return []
        except Exception as e:
            logger.error(f'Failed to look up papers in batch: {e}')
            return []

    def author_search(
        self,
        query: str,
        fields: list[str] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Search for authors matching the query.

        Args:
            query: Search query (author name).
            fields: Specific fields to return in the response.
            limit: Maximum number of results to return.
            offset: Offset for pagination.

        Returns:
            list: List of authors matching the search criteria.
        """
        params = {
            'query': query,
            'limit': limit,
            'offset': offset,
        }
        if fields:
            params['fields'] = ','.join(fields)

        try:
            endpoint = 'author/search'
            response = self._make_request(endpoint, params)
            if response and 'data' in response:
                return response['data']
            return []
        except Exception as e:
            logger.error(f"Failed to search authors with query '{query}': {e}")
            return []

    def update_citation_from_semantic_scholar(
        self, citation: Citation, paper_data: dict[str, Any]
    ) -> None:
        """
        Update a Citation object with data from Semantic Scholar.

        Args:
            citation: The Citation object to update.
            paper_data: Paper data from Semantic Scholar API.
        """
        if not paper_data:
            return

        # Update basic metadata
        if not citation.title and 'title' in paper_data:
            citation.title = paper_data['title']

        if (
            not citation.doi
            and 'externalIds' in paper_data
            and 'DOI' in paper_data['externalIds']
        ):
            citation.doi = paper_data['externalIds']['DOI']

        # Update authors if available
        if not citation.authors and 'authors' in paper_data:
            citation.authors = [
                author['name'] for author in paper_data['authors'] if 'name' in author
            ]

        # Update abstract
        if not citation.abstract and 'abstract' in paper_data:
            citation.abstract = paper_data['abstract']

        # Update journal information
        if not citation.journal and 'journal' in paper_data:
            citation.journal = (
                paper_data['journal']['name']
                if 'name' in paper_data['journal']
                else None
            )

        # Update publication year
        if not citation.year and 'year' in paper_data:
            citation.year = paper_data['year']

        # Update publication venue
        if not citation.venue and 'venue' in paper_data:
            citation.venue = paper_data['venue']

        # Update URL
        if not citation.url and 'url' in paper_data:
            citation.url = paper_data['url']
        elif (
            not citation.url
            and 'openAccessPdf' in paper_data
            and paper_data['openAccessPdf']
        ):
            citation.url = paper_data['openAccessPdf']['url']

        # Update citation count
        if citation.citation_count is None and 'citationCount' in paper_data:
            citation.citation_count = paper_data['citationCount']

        # Update fields of study
        if not citation.fields_of_study and 'fieldsOfStudy' in paper_data:
            citation.fields_of_study = paper_data['fieldsOfStudy']
        # Map any additional Semantic Scholar attributes to Citation if present
        if (
            'referenceCount' in paper_data
            and getattr(citation, 'reference_count', None) is None
        ):
            citation.reference_count = paper_data['referenceCount']
        if (
            'influentialCitationCount' in paper_data
            and getattr(citation, 'influential_citation_count', None) is None
        ):
            citation.influential_citation_count = paper_data['influentialCitationCount']
        if (
            'isOpenAccess' in paper_data
            and getattr(citation, 'is_open_access', None) is None
        ):
            citation.is_open_access = paper_data['isOpenAccess']
        if (
            's2FieldsOfStudy' in paper_data
            and getattr(citation, 's2_fields_of_study', None) is None
        ):
            citation.s2_fields_of_study = paper_data['s2FieldsOfStudy']

    def semantic_scholar_lookup(self, citations: list[Citation]) -> list[Citation]:
        """
        Look up citations in Semantic Scholar and enhance with additional metadata.

        Args:
            citations: List of citations to enhance.

        Returns:
            list[Citation]: The citations with enhanced information from Semantic Scholar.
        """  # noqa: W505
        logger.debug(f'Looking up {len(citations)} citations in Semantic Scholar')

        # Fields to request from Semantic Scholar API
        fields = [
            'title',
            'abstract',
            'authors',
            'year',
            'venue',
            'journal',
            'url',
            'externalIds',
            'citationCount',
            'openAccessPdf',
            'fieldsOfStudy',
        ]

        for citation in citations:
            try:
                # Try to look up by DOI first if available
                paper_data = None
                if citation.doi:
                    paper_data = self.paper_lookup_by_doi(citation.doi, fields)

                # If DOI lookup failed or no DOI, try arXiv ID if available
                if (
                    not paper_data
                    and citation.backup_id
                    and citation.backup_id.startswith('arxiv:')
                ):
                    arxiv_id = citation.backup_id.split(':', 1)[1]
                    paper_data = self.paper_lookup_by_arxiv(arxiv_id, fields)

                # If both failed or neither available, search by title
                if not paper_data and citation.title:
                    search_results = self.paper_search(
                        f'"{citation.title}"', fields, limit=1
                    )
                    if search_results:
                        paper_data = search_results[0]

                # Update citation with retrieved data
                if paper_data:
                    self.update_citation_from_semantic_scholar(citation, paper_data)

            except Exception as e:
                logger.error(f'Error enhancing citation with Semantic Scholar: {e}')

        return citations

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

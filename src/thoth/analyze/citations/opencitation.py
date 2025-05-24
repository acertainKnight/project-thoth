"""
Citation utilities for interacting with OpenCitations API.
"""

import time
from typing import Any

import httpx
from loguru import logger

from thoth.utilities.models import OpenCitation


class OpenCitationsAPI:
    """Client for interacting with OpenCitations Meta REST API."""

    def __init__(
        self,
        base_url: str = 'https://opencitations.net/meta/api/v1',
        access_token: str | None = None,
        timeout: int = 10,
        delay_seconds: float = 1.0,
        max_retries: int = 9,
    ):
        """
        Initialize OpenCitations API client.

        Args:
            base_url: Base URL for the OpenCitations Meta API.
            access_token: OpenCitations access token (recommended).
            timeout: Timeout for API requests in seconds.
            delay_seconds: Initial delay between retry attempts in seconds.
            max_retries: Maximum number of retry attempts for failed requests.
        """
        self.base_url = base_url
        self.access_token = access_token
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries

        self.client = httpx.Client(timeout=timeout)
        self.last_request_time = 0

        if not access_token:
            logger.warning(
                "No OpenCitations access token provided. It's recommended to get one from "
                'https://opencitations.net/accesstoken'
            )

    def _make_request_sync(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        require: list[str] | None = None,
        filters: list[tuple[str, str, str]] | None = None,
        sort: tuple[str, str] | None = None,
        format_type: str = 'json',
    ) -> dict | list:
        """
        Make a synchronous authenticated request to the OpenCitations API with retries and backoff.

        Args:
            endpoint: API endpoint to call.
            params: Base query parameters.
            require: Fields that must not be empty.
            filters: List of (field, operator, value) tuples for filtering.
            sort: Tuple of (order, field) for sorting.
            format_type: Response format ("json" or "csv").

        Returns:
            dict | list: API response data.

        Raises:
            httpx.HTTPError: If the request fails after retries.
        """  # noqa: W505
        headers = {'Accept': 'application/json'}
        if self.access_token:
            headers['authorization'] = self.access_token

        # Build query parameters
        query_params = params or {}

        # Add require parameters
        if require:
            for field in require:
                query_params[f'require={field}'] = ''

        # Add filter parameters
        if filters:
            for field, op, value in filters:
                query_params[f'filter={field}:{op}{value}'] = ''

        # Add sort parameter
        if sort:
            order, field = sort
            query_params[f'sort={order}({field})'] = ''

        # Add format parameter
        query_params['format'] = format_type

        # Basic rate limiting between distinct calls
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        # Using a fixed delay of 0.1s as OpenCitations might be more sensitive
        # This is separate from retry backoff.
        opencitations_inter_call_delay = 0.1
        if time_since_last_request < opencitations_inter_call_delay:
            sleep_time = opencitations_inter_call_delay - time_since_last_request
            logger.debug(
                f'OpenCitations inter-call delay: sleeping for {sleep_time:.2f} seconds.'
            )
            time.sleep(sleep_time)

        url = f'{self.base_url}/{endpoint}'

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f'Making request to OpenCitations API: {url} with params {query_params} (Attempt {attempt + 1}/{self.max_retries + 1})'
                )
                response = self.client.get(
                    url,
                    params=query_params,
                    headers=headers,
                )
                self.last_request_time = time.time()
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f'OpenCitations API request failed (Attempt {attempt + 1}/{self.max_retries + 1}): '
                    f'Status {e.response.status_code} - {e.response.text}'
                )
                if attempt < self.max_retries:
                    if e.response.status_code == 429:  # Too Many Requests
                        retry_after_str = e.response.headers.get('Retry-After')
                        if retry_after_str:
                            try:
                                sleep_duration = int(retry_after_str)
                                logger.info(
                                    f'Rate limit hit (429). Retrying after {sleep_duration} seconds (from Retry-After header).'
                                )
                            except ValueError:
                                sleep_duration = self.delay_seconds * (2**attempt)
                                logger.info(
                                    f'Rate limit hit (429). Retrying after {sleep_duration:.2f} seconds (exponential backoff).'
                                )
                        else:
                            sleep_duration = self.delay_seconds * (2**attempt)
                            logger.info(
                                f'Rate limit hit (429). Retrying after {sleep_duration:.2f} seconds (exponential backoff).'
                            )
                        time.sleep(sleep_duration)
                    elif e.response.status_code >= 500:  # Server-side errors
                        sleep_duration = self.delay_seconds * (2**attempt)
                        logger.warning(
                            f'Server error ({e.response.status_code}). Retrying after {sleep_duration:.2f} seconds.'
                        )
                        time.sleep(sleep_duration)
                    else:  # Other client errors, not retrying
                        raise
                else:
                    logger.error(
                        f'Failed to make OpenCitations API request after {self.max_retries + 1} attempts: {e}'
                    )
                    raise
            except httpx.RequestError as e:  # Network errors, timeouts
                logger.warning(
                    f'OpenCitations API request failed due to network/request error (Attempt {attempt + 1}/{self.max_retries + 1}): {e}'
                )
                if attempt < self.max_retries:
                    sleep_duration = self.delay_seconds * (2**attempt)
                    logger.info(f'Retrying after {sleep_duration:.2f} seconds.')
                    time.sleep(sleep_duration)
                else:
                    logger.error(
                        f'Failed to make OpenCitations API request after {self.max_retries + 1} attempts due to network/request error: {e}'
                    )
                    raise
            except Exception as e:
                logger.error(
                    f'An unexpected error occurred during OpenCitations API request (Attempt {attempt + 1}): {e}'
                )
                if attempt == self.max_retries:
                    raise
                sleep_duration = self.delay_seconds * (2**attempt)
                logger.info(
                    f'Retrying after {sleep_duration:.2f} seconds due to unexpected error.'
                )
                time.sleep(sleep_duration)
        # This line should not be reached if logic is correct
        raise httpx.HTTPError(
            f'OpenCitations API request failed after {self.max_retries + 1} attempts (exhausted retries).'
        )

    def lookup_metadata_sync(self, ids: list[str]) -> list[OpenCitation]:
        """
        Look up bibliographic metadata for one or more IDs (synchronous version).

        Args:
            ids: List of IDs with prefixes (e.g., ["doi:10.1234/xyz", "pmid:12345"]).
                Supported prefixes: doi, issn, isbn, omid, openalex, pmid, pmcid

        Returns:
            list[OpenCitation]: List of metadata records.

        Example:
            >>> api.lookup_metadata_sync(['doi:10.1007/s11192-022-04367-w'])
            [{"id": "...", "title": "...", "author": "...", ...}]
        """
        try:
            # Join IDs with double underscore as per API spec
            id_str = '__'.join(ids)
            data = self._make_request_sync(f'metadata/{id_str}')
            # Parse the response data into OpenCitation objects
            results = []
            if isinstance(data, list):
                for item in data:
                    try:
                        results.append(OpenCitation(**item))
                    except Exception as e:
                        logger.error(f'Failed to parse citation data: {e}')
            return results
        except Exception as e:
            logger.error(f'Failed to look up metadata for IDs {ids}: {e}')
            return []

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

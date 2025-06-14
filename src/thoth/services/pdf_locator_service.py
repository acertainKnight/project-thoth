"""
PDF Locator Service for finding open-access PDFs.

This service attempts to locate PDF URLs for academic articles through multiple
sources including Crossref, Unpaywall, arXiv, Semantic Scholar, and DOI content
negotiation.
"""

from __future__ import annotations

import re
import time
from typing import Any

import requests
from pydantic import BaseModel, Field

from thoth.services.base import BaseService, ServiceError


class PdfLocation(BaseModel):
    """
    Represents a located PDF with metadata.

    Attributes:
        url: Direct URL to the PDF file
        source: Source that provided the PDF (crossref, unpaywall, arxiv, s2, doi-head)
        licence: License information if available (e.g., 'cc-by')
        is_oa: Whether the PDF is open access
    """

    url: str
    source: str = Field(
        ...,
        description="Source: 'crossref' | 'unpaywall' | 'arxiv' | 's2' | 'doi-head'",
    )
    licence: str | None = None
    is_oa: bool = True


class PdfLocatorService(BaseService):
    """
    Service for locating PDF URLs for academic articles.

    This service tries multiple sources in sequence to find the best available
    PDF URL for a given DOI or arXiv ID. It implements rate limiting and
    caching to be respectful to API providers.
    """

    # API endpoints
    CROSSREF_ENDPOINT = 'https://api.crossref.org/works/{doi}'
    UNPAYWALL_ENDPOINT = 'https://api.unpaywall.org/v2/{doi}?email={email}'
    S2_ENDPOINT = (
        'https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf'
    )
    ARXIV_PDF = 'https://arxiv.org/pdf/{id}.pdf'

    def __init__(self, config=None):
        """
        Initialize the PDF Locator Service.

        Args:
            config: Optional configuration object
        """
        super().__init__(config)
        self.email = getattr(self.config.api_keys, 'unpaywall_email', None)
        self.user_agent = (
            f'Thoth/0.3 (+mailto:{self.email})' if self.email else 'Thoth/0.3'
        )

        # Initialize request session with default headers
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})

        # Initialize cache for PDF locations
        self._location_cache = {}

    def initialize(self) -> None:
        """Initialize the PDF locator service."""
        if not self.email:
            self.logger.warning(
                'No Unpaywall email configured. Some PDF sources may be unavailable.'
            )
        self.logger.info('PDF Locator service initialized')

    def locate(
        self, doi: str | None = None, arxiv_id: str | None = None
    ) -> PdfLocation | None:
        """
        Locate a PDF URL for the given identifiers.

        Tries multiple sources in sequence, returning the first valid PDF found.

        Args:
            doi: DOI identifier
            arxiv_id: arXiv identifier

        Returns:
            PdfLocation object if found, None otherwise
        """
        if not doi and not arxiv_id:
            raise ServiceError('Either DOI or arXiv ID must be provided')

        # Check cache
        cache_key = (doi, arxiv_id)
        if cache_key in self._location_cache:
            return self._location_cache[cache_key]

        try:
            # Try sources in order of preference
            if doi:
                # Try Crossref first (no auth needed, fast)
                result = self._from_crossref(doi)
                if result:
                    self._location_cache[cache_key] = result
                    return result

                # Try Unpaywall (comprehensive OA database)
                if self.email:
                    result = self._from_unpaywall(doi)
                    if result:
                        self._location_cache[cache_key] = result
                        return result

                # Try arXiv (if DOI is an arXiv DOI)
                result = self._from_arxiv(doi, arxiv_id)
                if result:
                    self._location_cache[cache_key] = result
                    return result

                # Try Semantic Scholar
                result = self._from_semanticscholar(doi)
                if result:
                    self._location_cache[cache_key] = result
                    return result

                # Try DOI content negotiation as last resort
                result = self._from_doi_head(doi)
                if result:
                    self._location_cache[cache_key] = result
                    return result
            elif arxiv_id:
                # If only arXiv ID provided, try direct arXiv PDF
                result = self._from_arxiv(None, arxiv_id)
                if result:
                    self._location_cache[cache_key] = result
                    return result

            # Cache None result to avoid repeated lookups
            self._location_cache[cache_key] = None
            return None

        except Exception as e:
            self.logger.error(
                self.handle_error(e, f'locating PDF for DOI: {doi}, arXiv: {arxiv_id}')
            )
            return None

    def _get_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        accept: str = 'application/json',
    ) -> requests.Response | None:
        """
        Make a polite HTTP GET request with retry and backoff.

        Args:
            url: URL to request
            headers: Optional headers
            accept: Accept header value

        Returns:
            Response object if successful, None otherwise
        """
        request_headers = headers or {}
        request_headers['Accept'] = accept

        for delay in (0, 1, 3, 7):
            if delay:
                time.sleep(delay)
            try:
                response = self.session.get(url, headers=request_headers, timeout=15)
                if response.status_code in (200, 404):
                    return response
                self.logger.debug(f'HTTP {response.status_code} for {url}, retrying...')
            except requests.RequestException as e:
                self.logger.debug(f'Request failed for {url}: {e}, retrying...')
                continue

        self.logger.warning(f'Failed to fetch {url} after 4 attempts')
        return None

    def _from_crossref(self, doi: str) -> PdfLocation | None:
        """
        Try to get PDF URL from Crossref.

        Args:
            doi: DOI identifier

        Returns:
            PdfLocation if found, None otherwise
        """
        try:
            url = self.CROSSREF_ENDPOINT.format(doi=doi)
            response = self._get_json(url)
            if not response or response.status_code != 200:
                return None

            data = response.json()
            message = data.get('message', {})

            # Look for PDF links in the link array
            for link in message.get('link', []):
                if link.get('content-type') == 'application/pdf':
                    pdf_url = link.get('URL')
                    if pdf_url:
                        self.log_operation(
                            'pdf_found', source='crossref', doi=doi, url=pdf_url
                        )
                        return PdfLocation(
                            url=pdf_url,
                            source='crossref',
                            licence=self._extract_license(message),
                            is_oa=True,
                        )

            return None

        except Exception as e:
            self.logger.debug(f'Crossref lookup failed for {doi}: {e}')
            return None

    def _from_unpaywall(self, doi: str) -> PdfLocation | None:
        """
        Try to get PDF URL from Unpaywall.

        Args:
            doi: DOI identifier

        Returns:
            PdfLocation if found, None otherwise
        """
        if not self.email:
            return None

        try:
            url = self.UNPAYWALL_ENDPOINT.format(doi=doi, email=self.email)
            response = self._get_json(url)
            if not response or response.status_code != 200:
                return None

            data = response.json()
            if not data.get('is_oa'):
                return None

            # Get best OA location
            best_location = data.get('best_oa_location')
            if best_location and best_location.get('url_for_pdf'):
                pdf_url = best_location['url_for_pdf']
                self.log_operation(
                    'pdf_found', source='unpaywall', doi=doi, url=pdf_url
                )
                return PdfLocation(
                    url=pdf_url,
                    source='unpaywall',
                    licence=best_location.get('license'),
                    is_oa=True,
                )

            return None

        except Exception as e:
            self.logger.debug(f'Unpaywall lookup failed for {doi}: {e}')
            return None

    def _from_arxiv(self, doi: str | None, arxiv_id: str | None) -> PdfLocation | None:
        """
        Try to get PDF URL from arXiv.

        Args:
            doi: DOI identifier (optional)
            arxiv_id: arXiv identifier (optional)

        Returns:
            PdfLocation if found, None otherwise
        """
        # Extract arXiv ID from DOI if needed
        aid = arxiv_id or (self._doi_to_arxiv(doi) if doi else None)
        if not aid:
            return None

        # arXiv PDFs are deterministic
        pdf_url = self.ARXIV_PDF.format(id=aid)
        self.log_operation('pdf_found', source='arxiv', arxiv_id=aid, url=pdf_url)
        return PdfLocation(url=pdf_url, source='arxiv', licence='arXiv', is_oa=True)

    def _from_semanticscholar(self, doi: str) -> PdfLocation | None:
        """
        Try to get PDF URL from Semantic Scholar.

        Args:
            doi: DOI identifier

        Returns:
            PdfLocation if found, None otherwise
        """
        try:
            url = self.S2_ENDPOINT.format(doi=doi)

            # Add S2 API key if available
            headers = {}
            s2_key = getattr(self.config.api_keys, 'semanticscholar_api_key', None)
            if s2_key:
                headers['x-api-key'] = s2_key

            response = self._get_json(url, headers=headers)
            if not response or response.status_code != 200:
                return None

            data = response.json()
            open_access_pdf = data.get('openAccessPdf')
            if open_access_pdf and open_access_pdf.get('url'):
                pdf_url = open_access_pdf['url']
                self.log_operation('pdf_found', source='s2', doi=doi, url=pdf_url)
                return PdfLocation(
                    url=pdf_url,
                    source='s2',
                    licence=None,  # S2 doesn't provide license info
                    is_oa=True,
                )

            return None

        except Exception as e:
            self.logger.debug(f'Semantic Scholar lookup failed for {doi}: {e}')
            return None

    def _from_doi_head(self, doi: str) -> PdfLocation | None:
        """
        Try to get PDF URL via DOI content negotiation.

        This is a fallback that may return paywalled content.

        Args:
            doi: DOI identifier

        Returns:
            PdfLocation if found, None otherwise
        """
        try:
            headers = {'Accept': 'application/pdf'}
            response = requests.head(
                f'https://doi.org/{doi}',
                allow_redirects=True,
                headers=headers,
                timeout=15,
            )

            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'application/pdf' in content_type:
                    pdf_url = response.url
                    self.log_operation(
                        'pdf_found', source='doi-head', doi=doi, url=pdf_url
                    )
                    return PdfLocation(
                        url=pdf_url,
                        source='doi-head',
                        licence=None,
                        is_oa=False,  # Might be paywalled
                    )

            return None

        except Exception as e:
            self.logger.debug(f'DOI HEAD lookup failed for {doi}: {e}')
            return None

    @staticmethod
    def _doi_to_arxiv(doi: str) -> str | None:
        """
        Extract arXiv ID from DOI.

        Args:
            doi: DOI string

        Returns:
            arXiv ID if found, None otherwise
        """
        match = re.match(r'10\.48550/arXiv\.(?P<id>.+)', doi)
        return match.group('id') if match else None

    def _extract_license(self, crossref_message: dict[str, Any]) -> str | None:
        """
        Extract license information from Crossref metadata.

        Args:
            crossref_message: Crossref message object

        Returns:
            License string if found, None otherwise
        """
        licenses = crossref_message.get('license', [])
        for license_info in licenses:
            if license_info.get('URL'):
                # Extract common license abbreviations
                url = license_info['URL'].lower()
                if 'creativecommons.org/licenses/by/' in url:
                    return 'cc-by'
                elif 'creativecommons.org/licenses/by-nc/' in url:
                    return 'cc-by-nc'
                elif 'creativecommons.org/licenses/by-sa/' in url:
                    return 'cc-by-sa'
                elif 'creativecommons.org/licenses/by-nd/' in url:
                    return 'cc-by-nd'

        return None

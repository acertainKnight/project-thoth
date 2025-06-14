"""
API sources for article discovery.

This module provides API source classes for discovering articles from
various research databases like ArXiv and PubMed.
"""

import time
import urllib.parse
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
import warnings

import feedparser
import httpx
import requests
from bs4 import BeautifulSoup
from loguru import logger

from thoth.utilities.schemas import ArxivPaper, Citation, ScrapedArticleMetadata


class APISourceError(Exception):
    """Exception raised for errors in API sources."""

    pass


class ArxivClient:
    """Client for interacting with arXiv API to retrieve citation metadata."""

    def __init__(
        self,
        base_url: str = 'https://export.arxiv.org/api/query',
        timeout: int = 10,
        delay_seconds: float = 3.0,
        max_retries: int = 9,
    ):
        """
        Initialize arXiv API client.

        Args:
            base_url: Base URL for the arXiv API.
            timeout: Timeout for API requests in seconds.
            delay_seconds: Delay between API requests to avoid rate limiting.
            max_retries: Maximum number of retry attempts for failed requests.
        """
        self.base_url = base_url
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries

        headers = {
            'User-Agent': 'Thoth/1.0 (https://github.com/nick-ghafari/project-thoth)'
        }
        self.client = httpx.Client(timeout=timeout, headers=headers)
        self.last_request_time = 0

    def _make_request(
        self,
        params: dict[str, Any],
    ) -> str:
        """
        Make a request to the arXiv API with rate limiting.

        Args:
            params: API query parameters.

        Returns:
            str: Raw XML response from the arXiv API.

        Raises:
            httpx.HTTPError: If the request fails after retries.
        """
        # Implement rate limiting
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.delay_seconds:
            sleep_time = self.delay_seconds - time_since_last_request
            logger.debug(f'Rate limiting: sleeping for {sleep_time:.2f} seconds')
            time.sleep(sleep_time)

        url = f'{self.base_url}?{urllib.parse.urlencode(params)}'

        retries = 0
        while retries <= self.max_retries:
            try:
                logger.debug(f'Making request to arXiv API: {url}')
                response = self.client.get(url)
                response.raise_for_status()
                self.last_request_time = time.time()

                return response.text
            except httpx.HTTPError as e:
                retries += 1
                if retries > self.max_retries:
                    logger.error(
                        f'Failed to make arXiv API request after {self.max_retries} retries: {e}'
                    )
                    raise
                logger.warning(
                    f'arXiv API request failed (attempt {retries}/{self.max_retries}): {e}'
                )
                time.sleep(self.delay_seconds * retries)  # Exponential backoff

    def search(
        self,
        query: str,
        start: int = 0,
        max_results: int = 10,
        sort_by: str = 'relevance',
        sort_order: str = 'descending',
        search_field: str | None = None,
    ) -> list[ArxivPaper]:
        """
        Search arXiv for papers matching the query.

        Args:
            query: Search query.
            start: Starting index for results.
            max_results: Maximum number of results to return.
            sort_by: Sort criteria ("relevance", "lastUpdatedDate", "submittedDate").
            sort_order: Sort order ("ascending" or "descending").
            search_field: Field to search in ("all", "title", "abstract", "author", etc.)

        Returns:
            List[ArxivPaper]: List of arXiv papers matching the search criteria.
        """  # noqa: W505
        if search_field:
            search_query = f'{search_field}:{query}'
        else:
            search_query = query

        params = {
            'search_query': search_query,
            'start': start,
            'max_results': max_results,
            'sortBy': sort_by,
            'sortOrder': sort_order,
        }

        xml_response = self._make_request(params)

        # Parse the XML response
        return self._parse_arxiv_response(xml_response)

    def get_by_id(self, paper_id: str | list[str]) -> list[ArxivPaper]:
        """
        Get arXiv papers by their IDs.

        Args:
            paper_id: Single arXiv ID or list of IDs.

        Returns:
            List[ArxivPaper]: List of papers with the specified IDs.
        """
        if isinstance(paper_id, str):
            id_list = paper_id
        else:
            id_list = ','.join(paper_id)

        params = {
            'id_list': id_list,
            'max_results': len(paper_id) if isinstance(paper_id, list) else 1,
        }

        xml_response = self._make_request(params)

        # Parse the XML response
        return self._parse_arxiv_response(xml_response)

    def _parse_arxiv_response(self, xml_response: str) -> list[ArxivPaper]:
        """
        Parse arXiv API response XML into ArxivPaper objects.

        Args:
            xml_response: XML response from arXiv API.

        Returns:
            List[ArxivPaper]: List of parsed ArxivPaper objects.
        """
        results = []

        # Use BeautifulSoup to parse XML
        soup = BeautifulSoup(xml_response, 'xml')

        # Find all entry elements (each represents a paper)
        entries = soup.find_all('entry')

        for entry in entries:
            try:
                # Extract basic metadata
                entry_id = entry.find('id').text if entry.find('id') else ''
                arxiv_id = (
                    entry_id.split('/abs/')[-1] if '/abs/' in entry_id else entry_id
                )

                title = entry.find('title').text.strip() if entry.find('title') else ''
                abstract = (
                    entry.find('summary').text.strip() if entry.find('summary') else ''
                )

                # Extract authors
                authors = []
                author_elements = entry.find_all('author')
                for author_elem in author_elements:
                    name_elem = author_elem.find('name')
                    if name_elem:
                        authors.append(name_elem.text.strip())

                # Extract PDF link
                pdf_url = None
                for link in entry.find_all('link'):
                    if (
                        link.get('title') == 'pdf'
                        or link.get('type') == 'application/pdf'
                    ):
                        pdf_url = link.get('href')
                        break

                # Extract DOI if available
                doi = None
                arxiv_doi = entry.find('arxiv:doi')
                if arxiv_doi:
                    doi = arxiv_doi.text.strip()

                # Extract published/updated dates
                published = (
                    entry.find('published').text if entry.find('published') else None
                )
                updated = entry.find('updated').text if entry.find('updated') else None

                # Extract comment if available
                comment = None
                arxiv_comment = entry.find('arxiv:comment')
                if arxiv_comment:
                    comment = arxiv_comment.text.strip()

                # Extract journal reference if available
                journal_ref = None
                arxiv_journal_ref = entry.find('arxiv:journal_ref')
                if arxiv_journal_ref:
                    journal_ref = arxiv_journal_ref.text.strip()

                # Extract categories
                categories = []
                for category in entry.find_all('category'):
                    term = category.get('term')
                    if term:
                        categories.append(term)

                paper = ArxivPaper(
                    id=arxiv_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    categories=categories,
                    pdf_url=pdf_url,
                    published=published,
                    updated=updated,
                    comment=comment,
                    journal_ref=journal_ref,
                    doi=doi,
                )
                results.append(paper)
            except Exception as e:
                logger.error(f'Error parsing arXiv entry: {e}')

        return results

    def arxiv_lookup(self, citations: list[Citation]) -> list[Citation]:
        """
        Lookup citations in arXiv and enhance with additional metadata.

        Args:
            citations: List of citations to enhance.

        Returns:
            List[Citation]: The citations with enhanced information from arXiv.
        """
        logger.debug(f'Looking up {len(citations)} citations in arXiv')

        for citation in citations:
            # Skip if there's no title or if there's already a DOI
            if not citation.title:
                continue

            # Search for the paper by title
            query = f'"{citation.title}"'
            try:
                search_results = self.search(query, max_results=1, search_field='ti')

                if not search_results:
                    logger.debug(f'No arXiv results found for title: {citation.title}')
                    continue

                paper = search_results[0]

                # Update citation with arXiv data
                self._update_citation_from_arxiv(citation, paper)

                # If we found an arXiv ID but no DOI, set it as a backup_id
                if not citation.doi and not citation.backup_id:
                    citation.backup_id = f'arxiv:{paper.id}'

                # Get citation count if needed
                if citation.citation_count is None:
                    citation.citation_count = self.get_citation_count(paper.id)

            except Exception as e:
                logger.error(f'Error enhancing citation with arXiv: {e}')

        return citations

    def _update_citation_from_arxiv(
        self, citation: Citation, paper: ArxivPaper
    ) -> None:
        """
        Update citation with information from ArxivPaper.

        Args:
            citation: The citation to update.
            paper: ArxivPaper with source information.
        """
        # Update citation with arXiv paper data if fields are missing
        if not citation.doi and paper.doi:
            citation.doi = paper.doi

        if not citation.url and paper.pdf_url:
            citation.url = paper.pdf_url

        if not citation.journal and paper.journal_ref:
            citation.journal = paper.journal_ref

        if not citation.authors and paper.authors:
            citation.authors = paper.authors

        # If we have a year in the paper metadata or can extract from published date
        if not citation.year and paper.published:
            try:
                # Parse the date string and extract the year
                date = datetime.fromisoformat(paper.published.replace('Z', '+00:00'))
                citation.year = date.year
            except Exception:
                # If parsing fails, don't update the year
                pass

        if not citation.abstract and paper.abstract:
            citation.abstract = paper.abstract
        if not citation.venue and hasattr(paper, 'venue') and paper.venue:
            citation.venue = paper.venue
        if (
            citation.citation_count is None
            and hasattr(paper, 'citation_count')
            and paper.citation_count is not None
        ):
            citation.citation_count = paper.citation_count

    def get_citation_count(self, paper_id: str) -> int | None:
        """
        Get the citation count for an arXiv paper by querying Semantic Scholar.

        Args:
            paper_id: The arXiv ID of the paper.

        Returns:
            Optional[int]: The citation count if found, None otherwise.
        """
        try:
            # Use Semantic Scholar to get citation counts for arXiv papers
            semantic_url = f'https://api.semanticscholar.org/v1/paper/arXiv:{paper_id}'
            response = self.client.get(semantic_url)
            response.raise_for_status()
            data = response.json()

            citation_count = data.get('citationCount')
            return citation_count
        except Exception as e:
            logger.error(f'Failed to get citation count for arXiv:{paper_id}: {e}')
            return None

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()


class BaseAPISource(ABC):
    """
    Base class for API sources.

    This abstract class defines the interface for API sources that can
    search for articles and return standardized metadata.
    """

    @abstractmethod
    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """
        Search for articles using the API.

        Args:
            config: Configuration dictionary for the search.
            max_results: Maximum number of results to return.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.
        """
        pass


class ArxivAPISource(BaseAPISource):
    """Deprecated ArXiv API source.

    This class remains for backwards compatibility and will be removed in a
    future release. Use :class:`thoth.discovery.plugins.arxiv_plugin.ArxivPlugin`
    instead.
    """

    def __init__(self, rate_limit_delay: float = 3.0):
        """
        Initialize the ArXiv API source.

        Args:
            rate_limit_delay: Delay between API requests in seconds.
        """
        warnings.warn(
            'ArxivAPISource is deprecated and will be removed in a future release. '
            'Use ArxivPlugin instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        self.base_url = 'https://export.arxiv.org/api/query'
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """
        Search ArXiv for papers.

        Args:
            config: Configuration dictionary containing search parameters.
                   Expected keys:
                   - categories: List of ArXiv categories (e.g., ['cs.LG', 'cs.AI'])
                   - keywords: List of keywords to search for
                   - start_date: Start date for search (YYYY-MM-DD)
                   - end_date: End date for search (YYYY-MM-DD)
                   - sort_by: Sort order ('relevance', 'lastUpdatedDate', 'submittedDate')
                   - sort_order: Sort direction ('ascending', 'descending')
            max_results: Maximum number of results to return.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.

        Example:
            >>> source = ArxivAPISource()
            >>> config = {
            ...     'categories': ['cs.LG', 'cs.AI'],
            ...     'keywords': ['machine learning', 'neural networks'],
            ...     'max_results': 10,
            ... }
            >>> articles = source.search(config, max_results=10)
        """  # noqa: W505
        try:
            # Build search query
            query_parts = []

            # Add category filters
            categories = config.get('categories', [])
            if categories:
                cat_queries = [f'cat:{cat}' for cat in categories]
                query_parts.append(f'({" OR ".join(cat_queries)})')

            # Add keyword searches
            keywords = config.get('keywords', [])
            if keywords:
                # Search in title, abstract, and comments
                keyword_queries = []
                for keyword in keywords:
                    keyword_queries.append(f'(ti:"{keyword}" OR abs:"{keyword}")')
                query_parts.append(f'({" OR ".join(keyword_queries)})')

            # Combine query parts
            if not query_parts:
                # Default to recent papers in computer science if no specific criteria
                query = 'cat:cs.*'
            else:
                query = ' AND '.join(query_parts)

            # Build parameters
            params = {
                'search_query': query,
                'start': 0,
                'max_results': min(max_results, 1000),  # ArXiv API limit
                'sortBy': config.get('sort_by', 'lastUpdatedDate'),
                'sortOrder': config.get('sort_order', 'descending'),
            }

            logger.info(f'Searching ArXiv with query: {query}')

            # Rate limiting
            self._rate_limit()

            # Make API request
            headers = {
                'User-Agent': 'Thoth/1.0 (https://github.com/nick-ghafari/project-thoth)'
            }
            response = requests.get(
                self.base_url, params=params, timeout=30, headers=headers
            )
            response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(f'ArXiv feed parsing warning: {feed.bozo_exception}')

            articles = []
            for entry in feed.entries:
                try:
                    article = self._parse_arxiv_entry(entry)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f'Error parsing ArXiv entry: {e}')

            logger.info(f'Found {len(articles)} articles from ArXiv')
            return articles

        except Exception as e:
            raise APISourceError(f'ArXiv search failed: {e}') from e

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _parse_arxiv_entry(self, entry) -> ScrapedArticleMetadata | None:
        """
        Parse an ArXiv feed entry into ScrapedArticleMetadata.

        Args:
            entry: ArXiv feed entry from feedparser.

        Returns:
            ScrapedArticleMetadata: Parsed article metadata, or None if parsing fails.
        """
        try:
            # Extract ArXiv ID from the entry ID
            arxiv_id = entry.id.split('/')[-1]

            # Extract authors
            authors = []
            if hasattr(entry, 'authors'):
                authors = [author.name for author in entry.authors]
            elif hasattr(entry, 'author'):
                authors = [entry.author]

            # Extract categories
            categories = []
            if hasattr(entry, 'tags'):
                categories = [tag.term for tag in entry.tags]

            # Extract publication date
            pub_date = None
            if hasattr(entry, 'published'):
                pub_date = entry.published

            # Build PDF URL
            pdf_url = f'https://arxiv.org/pdf/{arxiv_id}.pdf'

            # Extract DOI if available
            doi = None
            if hasattr(entry, 'arxiv_doi'):
                doi = entry.arxiv_doi

            return ScrapedArticleMetadata(
                title=entry.title.strip(),
                authors=authors,
                abstract=entry.summary.strip() if hasattr(entry, 'summary') else None,
                publication_date=pub_date,
                journal='arXiv',
                doi=doi,
                arxiv_id=arxiv_id,
                url=entry.link,
                pdf_url=pdf_url,
                keywords=categories,
                source='arxiv',
                scrape_timestamp=datetime.now().isoformat(),
                additional_metadata={
                    'categories': categories,
                    'updated': entry.updated if hasattr(entry, 'updated') else None,
                    'comment': entry.arxiv_comment
                    if hasattr(entry, 'arxiv_comment')
                    else None,
                },
            )

        except Exception as e:
            logger.error(f'Error parsing ArXiv entry: {e}')
            return None


class PubMedAPISource(BaseAPISource):
    """
    PubMed API source for discovering biomedical research papers.

    This class provides functionality to search PubMed for papers based on
    keywords, MeSH terms, and other criteria.
    """

    def __init__(self, rate_limit_delay: float = 0.34):
        """
        Initialize the PubMed API source.

        Args:
            rate_limit_delay: Delay between API requests in seconds (NCBI recommends
                3 requests/second).
        """
        self.base_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """
        Search PubMed for papers.

        Args:
            config: Configuration dictionary containing search parameters.
                   Expected keys:
                   - keywords: List of keywords to search for
                   - mesh_terms: List of MeSH terms
                   - authors: List of author names
                   - journal: Journal name
                   - start_date: Start date for search (YYYY/MM/DD)
                   - end_date: End date for search (YYYY/MM/DD)
                   - publication_types: List of publication types
            max_results: Maximum number of results to return.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.

        Example:
            >>> source = PubMedAPISource()
            >>> config = {
            ...     'keywords': ['machine learning', 'healthcare'],
            ...     'mesh_terms': ['Artificial Intelligence'],
            ...     'max_results': 10,
            ... }
            >>> articles = source.search(config, max_results=10)
        """
        try:
            # Build search query
            query_parts = []

            # Add keyword searches
            keywords = config.get('keywords', [])
            for keyword in keywords:
                query_parts.append(f'"{keyword}"[Title/Abstract]')

            # Add MeSH terms
            mesh_terms = config.get('mesh_terms', [])
            for mesh_term in mesh_terms:
                query_parts.append(f'"{mesh_term}"[MeSH Terms]')

            # Add author searches
            authors = config.get('authors', [])
            for author in authors:
                query_parts.append(f'"{author}"[Author]')

            # Add journal filter
            journal = config.get('journal')
            if journal:
                query_parts.append(f'"{journal}"[Journal]')

            # Add date range
            start_date = config.get('start_date')
            end_date = config.get('end_date')
            if start_date and end_date:
                query_parts.append(
                    f'("{start_date}"[Date - Publication] : "{end_date}"[Date - Publication])'
                )

            # Add publication types
            pub_types = config.get('publication_types', [])
            for pub_type in pub_types:
                query_parts.append(f'"{pub_type}"[Publication Type]')

            # Combine query parts
            if not query_parts:
                # Default search for recent papers
                query = 'hasabstract[text] AND "last 30 days"[PDat]'
            else:
                query = ' AND '.join(query_parts)

            logger.info(f'Searching PubMed with query: {query}')

            # Step 1: Search for PMIDs
            pmids = self._search_pmids(query, max_results)

            if not pmids:
                logger.info('No PMIDs found for PubMed search')
                return []

            # Step 2: Fetch detailed information for PMIDs
            articles = self._fetch_article_details(pmids)

            logger.info(f'Found {len(articles)} articles from PubMed')
            return articles

        except Exception as e:
            raise APISourceError(f'PubMed search failed: {e}') from e

    def _search_pmids(self, query: str, max_results: int) -> list[str]:
        """
        Search PubMed for PMIDs matching the query.

        Args:
            query: Search query string.
            max_results: Maximum number of results.

        Returns:
            list[str]: List of PMIDs.
        """
        self._rate_limit()

        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': min(max_results, 10000),  # PubMed API limit
            'retmode': 'json',
            'sort': 'pub_date',
            'tool': 'thoth',
            'email': 'research@example.com',  # Should be configurable
        }

        response = requests.get(
            f'{self.base_url}/esearch.fcgi', params=params, timeout=30
        )
        response.raise_for_status()

        data = response.json()
        return data.get('esearchresult', {}).get('idlist', [])

    def _fetch_article_details(self, pmids: list[str]) -> list[ScrapedArticleMetadata]:
        """
        Fetch detailed article information for a list of PMIDs.

        Args:
            pmids: List of PubMed IDs.

        Returns:
            list[ScrapedArticleMetadata]: List of article metadata.
        """
        articles = []

        # Process PMIDs in batches to avoid overwhelming the API
        batch_size = 200  # PubMed recommended batch size
        for i in range(0, len(pmids), batch_size):
            batch_pmids = pmids[i : i + batch_size]

            try:
                batch_articles = self._fetch_batch_details(batch_pmids)
                articles.extend(batch_articles)
            except Exception as e:
                logger.error(f'Error fetching batch {i // batch_size + 1}: {e}')

        return articles

    def _fetch_batch_details(self, pmids: list[str]) -> list[ScrapedArticleMetadata]:
        """
        Fetch details for a batch of PMIDs.

        Args:
            pmids: List of PubMed IDs for this batch.

        Returns:
            list[ScrapedArticleMetadata]: List of article metadata.
        """
        self._rate_limit()

        params = {
            'db': 'pubmed',
            'id': ','.join(pmids),
            'retmode': 'xml',
            'tool': 'thoth',
            'email': 'research@example.com',  # Should be configurable
        }

        response = requests.get(
            f'{self.base_url}/efetch.fcgi', params=params, timeout=60
        )
        response.raise_for_status()

        # Parse XML response
        import xml.etree.ElementTree as ET

        root = ET.fromstring(response.content)

        articles = []
        for article_elem in root.findall('.//PubmedArticle'):
            try:
                article = self._parse_pubmed_article(article_elem)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.error(f'Error parsing PubMed article: {e}')

        return articles

    def _parse_pubmed_article(self, article_elem) -> ScrapedArticleMetadata | None:
        """
        Parse a PubMed article XML element into ScrapedArticleMetadata.

        Args:
            article_elem: XML element containing article data.

        Returns:
            ScrapedArticleMetadata: Parsed article metadata, or None if parsing fails.
        """
        try:
            # Extract basic information
            medline_citation = article_elem.find('.//MedlineCitation')
            article_info = medline_citation.find('.//Article')

            # Title
            title_elem = article_info.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else 'No title'

            # Abstract
            abstract_elem = article_info.find('.//Abstract/AbstractText')
            abstract = abstract_elem.text if abstract_elem is not None else None

            # Authors
            authors = []
            author_list = article_info.find('.//AuthorList')
            if author_list is not None:
                for author_elem in author_list.findall('.//Author'):
                    last_name = author_elem.find('.//LastName')
                    first_name = author_elem.find('.//ForeName')
                    if last_name is not None:
                        author_name = last_name.text
                        if first_name is not None:
                            author_name += f', {first_name.text}'
                        authors.append(author_name)

            # Journal
            journal_elem = article_info.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None else None

            # Publication date
            pub_date_elem = article_info.find('.//Journal/JournalIssue/PubDate')
            pub_date = None
            if pub_date_elem is not None:
                year_elem = pub_date_elem.find('.//Year')
                month_elem = pub_date_elem.find('.//Month')
                day_elem = pub_date_elem.find('.//Day')

                if year_elem is not None:
                    year = year_elem.text
                    month = month_elem.text if month_elem is not None else '01'
                    day = day_elem.text if day_elem is not None else '01'

                    # Convert month name to number if necessary
                    month_map = {
                        'Jan': '01',
                        'Feb': '02',
                        'Mar': '03',
                        'Apr': '04',
                        'May': '05',
                        'Jun': '06',
                        'Jul': '07',
                        'Aug': '08',
                        'Sep': '09',
                        'Oct': '10',
                        'Nov': '11',
                        'Dec': '12',
                    }
                    if month in month_map:
                        month = month_map[month]

                    pub_date = f'{year}-{month.zfill(2)}-{day.zfill(2)}'

            # PMID
            pmid_elem = medline_citation.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else None

            # DOI
            doi = None
            article_id_list = article_info.find('.//ELocationID[@EIdType="doi"]')
            if article_id_list is not None:
                doi = article_id_list.text

            # Keywords/MeSH terms
            keywords = []
            mesh_heading_list = medline_citation.find('.//MeshHeadingList')
            if mesh_heading_list is not None:
                for mesh_heading in mesh_heading_list.findall('.//MeshHeading'):
                    descriptor_name = mesh_heading.find('.//DescriptorName')
                    if descriptor_name is not None:
                        keywords.append(descriptor_name.text)

            # Build URL
            url = f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/' if pmid else None

            return ScrapedArticleMetadata(
                title=title.strip(),
                authors=authors,
                abstract=abstract.strip() if abstract else None,
                publication_date=pub_date,
                journal=journal,
                doi=doi,
                url=url,
                keywords=keywords,
                source='pubmed',
                scrape_timestamp=datetime.now().isoformat(),
                additional_metadata={
                    'pmid': pmid,
                    'mesh_terms': keywords,
                },
            )

        except Exception as e:
            logger.error(f'Error parsing PubMed article: {e}')
            return None

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()


class CrossRefAPISource(BaseAPISource):
    """CrossRef API source for discovering scholarly works."""

    def __init__(self, rate_limit_delay: float = 1.0):
        """Initialize the CrossRef API source."""
        self.base_url = "https://api.crossref.org/works"
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """Search CrossRef for works."""
        try:
            params = {
                "rows": min(max_results, 100),
                "sort": config.get("sort_by", "relevance"),
                "order": config.get("sort_order", "desc"),
            }

            # Build query string
            keywords = config.get("keywords", [])
            if keywords:
                params["query"] = " ".join(keywords)

            # Date filters
            start_date = config.get("start_date")
            end_date = config.get("end_date")
            filters = []
            if start_date:
                filters.append(f"from-pub-date:{start_date}")
            if end_date:
                filters.append(f"until-pub-date:{end_date}")
            if filters:
                params["filter"] = ",".join(filters)

            logger.info(f"Searching CrossRef with params: {params}")

            self._rate_limit()
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            items = data.get("message", {}).get("items", [])
            articles: list[ScrapedArticleMetadata] = []

            for item in items:
                try:
                    article = self._parse_item(item)
                    if article:
                        articles.append(article)
                except Exception as e:  # pragma: no cover - log and continue
                    logger.error(f"Error parsing CrossRef item: {e}")

            logger.info(f"Found {len(articles)} articles from CrossRef")
            return articles

        except Exception as e:
            raise APISourceError(f"CrossRef search failed: {e}") from e

    def _parse_item(self, item: dict[str, Any]) -> ScrapedArticleMetadata | None:
        """Parse a single CrossRef item."""
        title_list = item.get("title", [])
        title = title_list[0] if title_list else None
        if not title:
            return None

        authors = []
        for a in item.get("author", []):
            given = a.get("given")
            family = a.get("family")
            if given and family:
                authors.append(f"{family}, {given}")
            elif family:
                authors.append(family)

        abstract = item.get("abstract")

        pub_date_parts = item.get("published-print") or item.get("published-online")
        pub_date = None
        if pub_date_parts and "date-parts" in pub_date_parts:
            parts = pub_date_parts["date-parts"][0]
            pub_date = "-".join(str(p) for p in parts)

        journal_list = item.get("container-title", [])
        journal = journal_list[0] if journal_list else None

        doi = item.get("DOI")
        url = item.get("URL")

        pdf_url = None
        for link in item.get("link", []):
            if link.get("content-type") == "application/pdf":
                pdf_url = link.get("URL")
                break

        keywords = item.get("subject", [])

        return ScrapedArticleMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            publication_date=pub_date,
            journal=journal,
            doi=doi,
            url=url,
            pdf_url=pdf_url,
            keywords=keywords,
            source="crossref",
            scrape_timestamp=datetime.now().isoformat(),
            additional_metadata={"type": item.get("type")},
        )

    def _rate_limit(self) -> None:
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()


class OpenAlexAPISource(BaseAPISource):
    """OpenAlex API source for discovering scholarly works."""

    def __init__(self, rate_limit_delay: float = 1.0):
        self.base_url = "https://api.openalex.org/works"
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """Search OpenAlex for works."""
        try:
            params = {
                "per-page": min(max_results, 200),
                "sort": config.get("sort_by", "relevance"),
            }

            keywords = config.get("keywords", [])
            if keywords:
                params["search"] = " ".join(keywords)

            filters = []
            start_date = config.get("start_date")
            end_date = config.get("end_date")
            if start_date:
                filters.append(f"from_publication_date:{start_date}")
            if end_date:
                filters.append(f"to_publication_date:{end_date}")
            if filters:
                params["filter"] = ",".join(filters)

            logger.info(f"Searching OpenAlex with params: {params}")

            self._rate_limit()
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            items = data.get("results", [])
            articles: list[ScrapedArticleMetadata] = []

            for item in items:
                try:
                    article = self._parse_item(item)
                    if article:
                        articles.append(article)
                except Exception as e:  # pragma: no cover - log and continue
                    logger.error(f"Error parsing OpenAlex item: {e}")

            logger.info(f"Found {len(articles)} articles from OpenAlex")
            return articles

        except Exception as e:
            raise APISourceError(f"OpenAlex search failed: {e}") from e

    def _parse_item(self, item: dict[str, Any]) -> ScrapedArticleMetadata | None:
        title = item.get("title") or item.get("display_name")
        if not title:
            return None

        authors = []
        for a in item.get("authorships", []):
            name = a.get("author", {}).get("display_name")
            if name:
                authors.append(name)

        abstract = item.get("abstract")
        pub_date = item.get("publication_date")

        journal = None
        container = item.get("host_venue") or {}
        if container:
            journal = container.get("display_name")

        doi = item.get("doi")
        url = container.get("url") if container else None
        pdf_url = container.get("pdf_url") if container else None

        keywords = [c.get("display_name") for c in item.get("concepts", []) if c.get("display_name")]

        return ScrapedArticleMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            publication_date=pub_date,
            journal=journal,
            doi=doi,
            url=url,
            pdf_url=pdf_url,
            keywords=keywords,
            source="openalex",
            scrape_timestamp=datetime.now().isoformat(),
            additional_metadata={"id": item.get("id")},
        )

    def _rate_limit(self) -> None:
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()


class BioRxivAPISource(BaseAPISource):
    """bioRxiv API source for preprint articles."""

    def __init__(self, rate_limit_delay: float = 1.0):
        self.base_url = "https://api.biorxiv.org/details/biorxiv"
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """Search bioRxiv for preprints."""
        try:
            start_date = config.get("start_date") or datetime.now().strftime("%Y-%m-%d")
            end_date = config.get("end_date") or start_date

            url = f"{self.base_url}/{start_date}/{end_date}"
            params = {"cursor": 0}

            logger.info(f"Searching bioRxiv with URL: {url}")

            self._rate_limit()
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            items = data.get("collection", [])[:max_results]
            articles: list[ScrapedArticleMetadata] = []

            for item in items:
                try:
                    article = self._parse_item(item)
                    if article:
                        articles.append(article)
                except Exception as e:  # pragma: no cover - log and continue
                    logger.error(f"Error parsing bioRxiv item: {e}")

            logger.info(f"Found {len(articles)} articles from bioRxiv")
            return articles

        except Exception as e:
            raise APISourceError(f"bioRxiv search failed: {e}") from e

    def _parse_item(self, item: dict[str, Any]) -> ScrapedArticleMetadata | None:
        title = item.get("title")
        if not title:
            return None

        authors = []
        author_str = item.get("authors")
        if author_str:
            authors = [a.strip() for a in author_str.split(";") if a.strip()]

        abstract = item.get("abstract")
        pub_date = item.get("date")
        journal = item.get("journal")
        doi = item.get("doi")
        url = item.get("biorxiv_url")
        pdf_url = item.get("biorxiv_pdf")

        return ScrapedArticleMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            publication_date=pub_date,
            journal=journal,
            doi=doi,
            url=url,
            pdf_url=pdf_url,
            keywords=[],
            source="biorxiv",
            scrape_timestamp=datetime.now().isoformat(),
            additional_metadata={"version": item.get("version")},
        )

    def _rate_limit(self) -> None:
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()

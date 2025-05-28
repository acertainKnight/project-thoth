"""
API sources for article discovery.

This module provides API source classes for discovering articles from
various research databases like ArXiv and PubMed.
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import feedparser
import requests
from loguru import logger

from thoth.utilities.models import ScrapedArticleMetadata


class APISourceError(Exception):
    """Exception raised for errors in API sources."""

    pass


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
    """
    ArXiv API source for discovering research papers.

    This class provides functionality to search ArXiv for papers based on
    categories, keywords, and other criteria.
    """

    def __init__(self, rate_limit_delay: float = 3.0):
        """
        Initialize the ArXiv API source.

        Args:
            rate_limit_delay: Delay between API requests in seconds.
        """
        self.base_url = 'http://export.arxiv.org/api/query'
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
            response = requests.get(self.base_url, params=params, timeout=30)
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

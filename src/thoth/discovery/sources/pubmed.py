"""
PubMed API source for biomedical research paper discovery.

This module provides the PubMed API source implementation for discovering
biomedical research papers from the NCBI PubMed database.
"""

import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from loguru import logger

from thoth.utilities.schemas import ScrapedArticleMetadata

from .base import APISourceError, BaseAPISource


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

        response = httpx.get(
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

        response = httpx.get(
            f'{self.base_url}/efetch.fcgi', params=params, timeout=60
        )
        response.raise_for_status()

        # Parse XML response
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
                tags=keywords,
                source='pubmed',
                metadata={
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

    def get_required_config_keys(self) -> list[str]:
        """Get required configuration keys."""
        return []  # No required keys for PubMed

    def get_optional_config_keys(self) -> list[str]:
        """Get optional configuration keys."""
        return [
            'keywords',
            'mesh_terms',
            'authors',
            'journal',
            'start_date',
            'end_date',
            'publication_types',
        ]

"""
Web scraper for article discovery.

This module provides a flexible web scraping system that can extract
article metadata from various websites using configurable selectors
and navigation rules.
"""

import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger

from thoth.utilities.schemas import ScrapeConfiguration, ScrapedArticleMetadata


class WebScraperError(Exception):
    """Exception raised for errors in web scraping."""

    pass


class WebScraper:
    """
    Flexible web scraper for article discovery.

    This class provides functionality to scrape articles from websites
    using configurable selectors and navigation rules. It supports
    pagination, rate limiting, and custom headers.
    """

    def __init__(self, default_delay: float = 1.0):
        """
        Initialize the web scraper.

        Args:
            default_delay: Default delay between requests in seconds.
        """
        self.default_delay = default_delay
        self.session = requests.Session()

        # Set default headers to appear more like a regular browser
        self.session.headers.update(
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )

    def scrape(
        self, config: ScrapeConfiguration, max_articles: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """
        Scrape articles from a website using the provided configuration.

        Args:
            config: ScrapeConfiguration containing scraping rules.
            max_articles: Maximum number of articles to scrape.

        Returns:
            list[ScrapedArticleMetadata]: List of scraped articles.

        Raises:
            WebScraperError: If scraping fails.

        Example:
            >>> scraper = WebScraper()
            >>> config = ScrapeConfiguration(
            ...     base_url='https://example-journal.com/latest',
            ...     extraction_rules={
            ...         'title': {'selector': 'h2.article-title', 'attribute': 'text'},
            ...         'authors': {
            ...             'selector': '.author-list .author',
            ...             'attribute': 'text',
            ...             'multiple': True,
            ...         },
            ...         'abstract': {'selector': '.abstract p', 'attribute': 'text'},
            ...     },
            ... )
            >>> articles = scraper.scrape(config, max_articles=10)
        """
        try:
            logger.info(f'Starting scrape of {config.base_url}')

            # Apply custom headers and cookies
            self._apply_config_settings(config)

            articles = []
            current_url = config.base_url
            page_count = 0
            max_pages = config.pagination_config.get('max_pages', 10)

            while (
                current_url and len(articles) < max_articles and page_count < max_pages
            ):
                try:
                    logger.info(f'Scraping page {page_count + 1}: {current_url}')

                    # Get page content
                    page_articles = self._scrape_page(current_url, config)
                    articles.extend(page_articles)

                    logger.info(
                        f'Found {len(page_articles)} articles on page {page_count + 1}'
                    )

                    # Check if we have enough articles
                    if len(articles) >= max_articles:
                        articles = articles[:max_articles]
                        break

                    # Get next page URL
                    current_url = self._get_next_page_url(current_url, config)
                    page_count += 1

                    # Apply rate limiting
                    self._apply_rate_limiting(config)

                except Exception as e:
                    logger.error(f'Error scraping page {current_url}: {e}')
                    break

            logger.info(f'Scraping completed: {len(articles)} articles found')
            return articles

        except Exception as e:
            raise WebScraperError(f'Scraping failed: {e}') from e

    def _apply_config_settings(self, config: ScrapeConfiguration) -> None:
        """
        Apply configuration settings to the session.

        Args:
            config: ScrapeConfiguration containing settings.
        """
        # Apply custom headers
        if config.headers:
            self.session.headers.update(config.headers)

        # Apply cookies
        if config.cookies:
            self.session.cookies.update(config.cookies)

    def _scrape_page(
        self, url: str, config: ScrapeConfiguration
    ) -> list[ScrapedArticleMetadata]:
        """
        Scrape articles from a single page.

        Args:
            url: URL of the page to scrape.
            config: ScrapeConfiguration containing extraction rules.

        Returns:
            list[ScrapedArticleMetadata]: List of articles found on the page.
        """
        try:
            # Get page content
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find article containers
            article_containers = self._find_article_containers(soup, config)

            articles = []
            for container in article_containers:
                try:
                    article = self._extract_article_metadata(container, config, url)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f'Error extracting article metadata: {e}')

            return articles

        except Exception as e:
            logger.error(f'Error scraping page {url}: {e}')
            return []

    def _find_article_containers(
        self, soup: BeautifulSoup, config: ScrapeConfiguration
    ) -> list:
        """
        Find article containers on the page.

        Args:
            soup: BeautifulSoup object of the page.
            config: ScrapeConfiguration containing navigation rules.

        Returns:
            list: List of article container elements.
        """
        # Check if there's a specific container selector
        container_selector = config.navigation_rules.get('article_container')

        if container_selector:
            containers = soup.select(container_selector)
        else:
            # Try to find common article container patterns
            common_selectors = [
                'article',
                '.article',
                '.paper',
                '.publication',
                '.result',
                '.item',
                '[class*="article"]',
                '[class*="paper"]',
            ]

            containers = []
            for selector in common_selectors:
                found = soup.select(selector)
                if found:
                    containers = found
                    break

            # If no containers found, treat the whole page as one container
            if not containers:
                containers = [soup]

        return containers

    def _extract_article_metadata(
        self, container, config: ScrapeConfiguration, base_url: str
    ) -> ScrapedArticleMetadata | None:
        """
        Extract article metadata from a container element.

        Args:
            container: BeautifulSoup element containing article data.
            config: ScrapeConfiguration containing extraction rules.
            base_url: Base URL for resolving relative links.

        Returns:
            ScrapedArticleMetadata: Extracted article metadata, or None if extraction fails.
        """  # noqa: W505
        try:
            extracted_data = {}

            # Extract data using configured rules
            for field, rule in config.extraction_rules.items():
                try:
                    value = self._extract_field(container, rule, base_url)
                    if value:
                        extracted_data[field] = value
                except Exception as e:
                    logger.debug(f'Error extracting field {field}: {e}')

            # Ensure we have at least a title
            if 'title' not in extracted_data or not extracted_data['title']:
                logger.debug('No title found, skipping article')
                return None

            # Build ScrapedArticleMetadata
            return ScrapedArticleMetadata(
                title=extracted_data.get('title', '').strip(),
                authors=self._normalize_authors(extracted_data.get('authors', [])),
                abstract=extracted_data.get('abstract', '').strip()
                if extracted_data.get('abstract')
                else None,
                publication_date=extracted_data.get('publication_date'),
                journal=extracted_data.get('journal'),
                doi=extracted_data.get('doi'),
                url=extracted_data.get('url'),
                pdf_url=extracted_data.get('pdf_url'),
                keywords=extracted_data.get('keywords', []),
                source=urlparse(base_url).netloc,
                scrape_timestamp=datetime.now().isoformat(),
                additional_metadata={
                    'scraped_from': base_url,
                    'extraction_rules_used': list(config.extraction_rules.keys()),
                },
            )

        except Exception as e:
            logger.error(f'Error extracting article metadata: {e}')
            return None

    def _extract_field(self, container, rule: dict[str, Any], base_url: str) -> Any:
        """
        Extract a single field using the provided rule.

        Args:
            container: BeautifulSoup element to extract from.
            rule: Extraction rule dictionary.
            base_url: Base URL for resolving relative links.

        Returns:
            Any: Extracted value.
        """
        selector = rule.get('selector')
        attribute = rule.get('attribute', 'text')
        multiple = rule.get('multiple', False)
        transform = rule.get('transform')

        if not selector:
            return None

        # Find elements
        elements = container.select(selector)

        if not elements:
            return None

        # Extract values
        values = []
        for element in elements:
            if attribute == 'text':
                value = element.get_text(strip=True)
            elif attribute == 'href':
                value = element.get('href')
                if value:
                    value = urljoin(base_url, value)  # Resolve relative URLs
            else:
                value = element.get(attribute)

            if value:
                # Apply transformation if specified
                if transform:
                    value = self._apply_transform(value, transform)
                values.append(value)

        # Return single value or list based on multiple flag
        if multiple:
            return values
        else:
            return values[0] if values else None

    def _apply_transform(self, value: str, transform: dict[str, Any]) -> str:
        """
        Apply transformation to extracted value.

        Args:
            value: Value to transform.
            transform: Transformation configuration.

        Returns:
            str: Transformed value.
        """
        transform_type = transform.get('type')

        if transform_type == 'regex':
            import re

            pattern = transform.get('pattern')
            replacement = transform.get('replacement', '')
            if pattern:
                value = re.sub(pattern, replacement, value)

        elif transform_type == 'strip':
            chars = transform.get('chars')
            if chars:
                value = value.strip(chars)
            else:
                value = value.strip()

        elif transform_type == 'replace':
            old = transform.get('old')
            new = transform.get('new', '')
            if old:
                value = value.replace(old, new)

        elif transform_type == 'lower':
            value = value.lower()

        elif transform_type == 'upper':
            value = value.upper()

        return value

    def _normalize_authors(self, authors: list[str] | str) -> list[str]:
        """
        Normalize author names to a consistent format.

        Args:
            authors: Author names as list or string.

        Returns:
            list[str]: Normalized author names.
        """
        if isinstance(authors, str):
            # Split by common separators
            import re

            authors = re.split(r'[,;]|\sand\s', authors)

        if not isinstance(authors, list):
            return []

        normalized = []
        for author in authors:
            if isinstance(author, str):
                author = author.strip()
                if author:
                    normalized.append(author)

        return normalized

    def _get_next_page_url(
        self, current_url: str, config: ScrapeConfiguration
    ) -> str | None:
        """
        Get the URL of the next page for pagination.

        Args:
            current_url: Current page URL.
            config: ScrapeConfiguration containing pagination rules.

        Returns:
            str: Next page URL, or None if no next page.
        """
        pagination_config = config.pagination_config

        if not pagination_config.get('enabled', False):
            return None

        pagination_type = pagination_config.get('type', 'link')

        if pagination_type == 'link':
            # Find next page link on current page
            try:
                response = self.session.get(current_url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')

                next_selector = pagination_config.get('next_selector', 'a[rel="next"]')
                next_element = soup.select_one(next_selector)

                if next_element:
                    next_url = next_element.get('href')
                    if next_url:
                        return urljoin(current_url, next_url)

            except Exception as e:
                logger.error(f'Error finding next page link: {e}')

        elif pagination_type == 'parameter':
            # Increment page parameter
            from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

            parsed = urlparse(current_url)
            query_params = parse_qs(parsed.query)

            page_param = pagination_config.get('page_parameter', 'page')
            current_page = int(query_params.get(page_param, [1])[0])

            query_params[page_param] = [str(current_page + 1)]

            new_query = urlencode(query_params, doseq=True)
            new_parsed = parsed._replace(query=new_query)

            return urlunparse(new_parsed)

        return None

    def _apply_rate_limiting(self, config: ScrapeConfiguration) -> None:
        """
        Apply rate limiting between requests.

        Args:
            config: ScrapeConfiguration containing rate limiting settings.
        """
        rate_config = config.rate_limiting
        delay = rate_config.get('delay', self.default_delay)

        if delay > 0:
            time.sleep(delay)

    def test_configuration(self, config: ScrapeConfiguration) -> dict[str, Any]:
        """
        Test a scraping configuration and return sample data.

        Args:
            config: ScrapeConfiguration to test.

        Returns:
            dict[str, Any]: Test results including sample extracted data.

        Example:
            >>> scraper = WebScraper()
            >>> test_result = scraper.test_configuration(config)
            >>> print(f'Found {test_result["articles_found"]} articles')
        """
        try:
            logger.info(f'Testing scraping configuration for {config.base_url}')

            # Apply configuration settings
            self._apply_config_settings(config)

            # Scrape first page only
            articles = self._scrape_page(config.base_url, config)

            # Prepare test results
            result = {
                'success': True,
                'articles_found': len(articles),
                'sample_articles': articles[:3],  # Return first 3 as samples
                'extraction_fields': list(config.extraction_rules.keys()),
                'errors': [],
            }

            # Validate extracted data
            for i, article in enumerate(articles[:3]):
                if not article.title:
                    result['errors'].append(f'Article {i + 1}: No title extracted')
                if not article.authors:
                    result['errors'].append(f'Article {i + 1}: No authors extracted')

            logger.info(f'Configuration test completed: {len(articles)} articles found')
            return result

        except Exception as e:
            logger.error(f'Configuration test failed: {e}')
            return {
                'success': False,
                'articles_found': 0,
                'sample_articles': [],
                'extraction_fields': [],
                'errors': [str(e)],
            }

    def parse_html(
        self, html: str, base_url: str, config: ScrapeConfiguration
    ) -> list[ScrapedArticleMetadata]:
        """Parse HTML content using existing extraction rules."""
        soup = BeautifulSoup(html, 'html.parser')
        containers = self._find_article_containers(soup, config)
        articles = []
        for container in containers:
            article = self._extract_article_metadata(container, config, base_url)
            if article:
                articles.append(article)
        return articles

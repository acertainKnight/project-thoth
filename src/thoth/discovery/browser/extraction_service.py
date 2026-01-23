"""
Extraction Service for extracting article metadata from web pages.

This module handles article extraction using configured rules, pagination,
deduplication, and error handling for browser-based discovery workflows.
"""

from __future__ import annotations  # noqa: I001

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional  # noqa: UP035

from loguru import logger

# Make playwright imports optional to avoid blocking if not installed
if TYPE_CHECKING:
    from playwright.async_api import ElementHandle, Page
    PlaywrightTimeoutError = TimeoutError
else:
    try:
        from playwright.async_api import (
            ElementHandle,
            Page,
            TimeoutError as PlaywrightTimeoutError,
        )
    except ImportError:
        # Playwright not installed - create placeholders
        ElementHandle = None  # type: ignore
        Page = None  # type: ignore
        PlaywrightTimeoutError = TimeoutError  # type: ignore

from thoth.utilities.schemas import ScrapedArticleMetadata


class ExtractionServiceError(Exception):
    """Exception raised for extraction service errors."""

    pass


class ExtractionService:
    """
    Service for extracting article metadata from web pages using Playwright.

    This service:
    - Applies extraction rules from workflow configuration (JSONB)
    - Extracts article fields: title, authors, abstract, url, doi, published_date
    - Handles pagination to navigate through result pages
    - Maps extracted data to ScrapedArticleMetadata schema
    - Provides deduplication support (check by DOI/title)
    - Handles errors gracefully, continuing extraction even if some articles fail

    Example:
        >>> service = ExtractionService(page)
        >>> articles = await service.extract_articles(
        ...     extraction_rules={
        ...         'article_container': '.article-item',
        ...         'selectors': {
        ...             'title': 'h3.title',
        ...             'authors': '.author-list .author',
        ...             'abstract': '.abstract-text',
        ...         },
        ...     },
        ...     max_articles=100,
        ... )
    """

    def __init__(
        self,
        page: Page,
        source_name: str = 'browser_extraction',
        existing_dois: Optional[set] = None,  # noqa: UP007
        existing_titles: Optional[set] = None,  # noqa: UP007
    ):
        """
        Initialize the ExtractionService.

        Args:
            page: Playwright Page instance for browser interaction
            source_name: Name of the discovery source for metadata
            existing_dois: Set of DOIs already in database (for deduplication)
            existing_titles: Set of normalized titles already in database
        """
        self.page = page
        self.source_name = source_name
        self.existing_dois = existing_dois or set()
        self.existing_titles = existing_titles or set()
        self._extracted_count = 0
        self._skipped_count = 0
        self._error_count = 0

    async def extract_articles(
        self,
        extraction_rules: Dict[str, Any],  # noqa: UP006
        max_articles: int = 100,
    ) -> List[ScrapedArticleMetadata]:  # noqa: UP006
        """
        Extract articles using configured extraction rules.

        This method:
        1. Finds article list container using configured selector
        2. Extracts each article's metadata using field selectors
        3. Handles pagination if configured
        4. Returns list of articles up to max_articles limit

        Args:
            extraction_rules: Dictionary containing:
                - article_container: CSS selector for article elements
                - selectors: Dict of field name to CSS selector
                - pagination: Optional pagination config
                - wait_for: Optional element to wait for before extraction
            max_articles: Maximum number of articles to extract

        Returns:
            List of ScrapedArticleMetadata objects

        Raises:
            ExtractionServiceError: If extraction fails critically
        """
        articles = []
        self._extracted_count = 0
        self._skipped_count = 0
        self._error_count = 0

        try:
            # Wait for page to be ready
            wait_for = extraction_rules.get('wait_for', 'body')
            try:
                await self.page.wait_for_selector(wait_for, timeout=10000)
            except PlaywrightTimeoutError:
                logger.warning(f'Timeout waiting for selector: {wait_for}')

            # Extract articles from current page
            page_num = 1
            while len(articles) < max_articles:
                logger.info(
                    f'Extracting from page {page_num} '
                    f'(collected {len(articles)}/{max_articles})'
                )

                # Extract articles from current page
                page_articles = await self._extract_articles_from_page(
                    extraction_rules, max_articles - len(articles)
                )

                if not page_articles:
                    logger.info(
                        'No articles found on current page, stopping extraction'
                    )
                    break

                articles.extend(page_articles)

                # Check if we have enough articles
                if len(articles) >= max_articles:
                    break

                # Try to navigate to next page
                pagination_config = extraction_rules.get('pagination')
                if not pagination_config:
                    logger.debug('No pagination config, stopping after first page')
                    break

                has_next = await self._navigate_to_next_page(pagination_config)
                if not has_next:
                    logger.info('No more pages available')
                    break

                page_num += 1

            logger.info(
                f'Extraction complete: extracted={self._extracted_count}, '
                f'skipped={self._skipped_count}, errors={self._error_count}'
            )

            return articles[:max_articles]

        except Exception as e:
            logger.error(f'Critical error during article extraction: {e}')
            raise ExtractionServiceError(f'Extraction failed: {e}') from e

    async def _extract_articles_from_page(
        self,
        extraction_rules: Dict[str, Any],  # noqa: UP006
        max_articles: int,
    ) -> List[ScrapedArticleMetadata]:  # noqa: UP006
        """
        Extract articles from the current page.

        Args:
            extraction_rules: Extraction configuration
            max_articles: Maximum articles to extract from this page

        Returns:
            List of extracted articles
        """
        articles = []
        container_selector = extraction_rules.get('article_container', 'article')

        try:
            # Wait for article container
            await self.page.wait_for_selector(container_selector, timeout=5000)

            # Get all article elements
            article_elements = await self.page.query_selector_all(container_selector)
            logger.debug(f'Found {len(article_elements)} article elements')

            # Extract each article
            for element in article_elements[:max_articles]:
                article = await self._extract_single_article(element, extraction_rules)

                if article:
                    # Check for duplicates
                    if self._is_duplicate(article):
                        self._skipped_count += 1
                        logger.debug(f'Skipped duplicate: {article.title[:60]}...')
                        continue

                    articles.append(article)
                    self._extracted_count += 1

                    # Update deduplication tracking
                    if article.doi:
                        self.existing_dois.add(article.doi)
                    if article.title:
                        self.existing_titles.add(self._normalize_title(article.title))

        except PlaywrightTimeoutError:
            logger.warning(f'No articles found with selector: {container_selector}')
        except Exception as e:
            logger.error(f'Error extracting articles from page: {e}')
            self._error_count += 1

        return articles

    async def _extract_single_article(
        self,
        article_element: ElementHandle,
        rules: Dict[str, Any],  # noqa: UP006
    ) -> Optional[ScrapedArticleMetadata]:  # noqa: UP007
        """
        Extract metadata from a single article element.

        Args:
            article_element: Playwright ElementHandle for article container
            rules: Extraction rules containing selectors dict

        Returns:
            ScrapedArticleMetadata if extraction successful, None otherwise
        """
        try:
            selectors = rules.get('selectors', {})

            # Extract title (required)
            title = await self._extract_text(article_element, selectors.get('title'))
            if not title:
                logger.debug('Skipped article: no title found')
                return None

            # Extract optional fields
            authors_raw = await self._extract_multiple_text(
                article_element, selectors.get('authors')
            )
            authors = (
                [a.strip() for a in authors_raw if a.strip()] if authors_raw else []
            )

            abstract = await self._extract_text(
                article_element, selectors.get('abstract')
            )
            doi = await self._extract_text(article_element, selectors.get('doi'))
            arxiv_id = await self._extract_text(
                article_element, selectors.get('arxiv_id')
            )
            journal = await self._extract_text(
                article_element, selectors.get('journal')
            )
            publication_date = await self._extract_text(
                article_element, selectors.get('publication_date')
            )

            # Extract URLs
            url = await self._extract_attribute(
                article_element, selectors.get('url'), 'href'
            )
            pdf_url = await self._extract_attribute(
                article_element, selectors.get('pdf_url'), 'href'
            )

            # Extract keywords if configured
            keywords_raw = await self._extract_multiple_text(
                article_element, selectors.get('keywords')
            )
            keywords = (
                [k.strip() for k in keywords_raw if k.strip()] if keywords_raw else []
            )

            # Clean and normalize DOI
            if doi:
                doi = self._clean_doi(doi)

            # Make URLs absolute if they're relative
            if url and not url.startswith('http'):
                url = self.page.url.rstrip('/') + '/' + url.lstrip('/')
            if pdf_url and not pdf_url.startswith('http'):
                pdf_url = self.page.url.rstrip('/') + '/' + pdf_url.lstrip('/')

            # Create metadata object
            metadata = ScrapedArticleMetadata(
                title=title.strip(),
                authors=authors,
                abstract=abstract.strip() if abstract else None,
                publication_date=publication_date.strip() if publication_date else None,
                journal=journal.strip() if journal else None,
                doi=doi,
                arxiv_id=arxiv_id.strip() if arxiv_id else None,
                url=url,
                pdf_url=pdf_url,
                keywords=keywords,
                source=self.source_name,
                scrape_timestamp=datetime.utcnow().isoformat(),
            )

            return metadata

        except Exception as e:
            logger.debug(f'Error extracting article: {e}')
            self._error_count += 1
            return None

    async def _extract_text(
        self,
        element: ElementHandle,
        selector: Optional[str],  # noqa: UP007
    ) -> Optional[str]:  # noqa: UP007
        """
        Extract text content from an element using a selector.

        Args:
            element: Parent element to search within
            selector: CSS selector for target element

        Returns:
            Text content or None if not found
        """
        if not selector:
            return None

        try:
            target = await element.query_selector(selector)
            if target:
                text = await target.text_content()
                return text.strip() if text else None
        except Exception as e:
            logger.debug(f"Error extracting text with selector '{selector}': {e}")

        return None

    async def _extract_multiple_text(
        self,
        element: ElementHandle,
        selector: Optional[str],  # noqa: UP007
    ) -> List[str]:  # noqa: UP006
        """
        Extract text from multiple elements matching a selector.

        Args:
            element: Parent element to search within
            selector: CSS selector for target elements

        Returns:
            List of text contents
        """
        if not selector:
            return []

        try:
            targets = await element.query_selector_all(selector)
            texts = []
            for target in targets:
                text = await target.text_content()
                if text:
                    texts.append(text.strip())
            return texts
        except Exception as e:
            logger.debug(
                f"Error extracting multiple text with selector '{selector}': {e}"
            )

        return []

    async def _extract_attribute(
        self,
        element: ElementHandle,
        selector: Optional[str],  # noqa: UP007
        attribute: str,
    ) -> Optional[str]:  # noqa: UP007
        """
        Extract an attribute value from an element.

        Args:
            element: Parent element to search within
            selector: CSS selector for target element
            attribute: Attribute name to extract

        Returns:
            Attribute value or None if not found
        """
        if not selector:
            return None

        try:
            target = await element.query_selector(selector)
            if target:
                value = await target.get_attribute(attribute)
                return value.strip() if value else None
        except Exception as e:
            logger.debug(
                f"Error extracting attribute '{attribute}' with selector '{selector}': {e}"
            )

        return None

    async def _navigate_to_next_page(
        self,
        pagination_config: Dict[str, Any],  # noqa: UP006
    ) -> bool:
        """
        Navigate to the next page using pagination configuration.

        Supports:
        - next_button: Click a "Next" button selector
        - next_link: Click a link to next page
        - page_param: URL parameter for page number

        Args:
            pagination_config: Dict with pagination strategy
                - type: "button" | "link" | "url_param"
                - selector: CSS selector for button/link
                - param_name: URL parameter name (for url_param type)

        Returns:
            True if navigation successful, False if no next page
        """
        try:
            pagination_type = pagination_config.get('type', 'button')

            if pagination_type == 'button':
                selector = pagination_config.get('selector', 'button.next, a.next')
                next_button = await self.page.query_selector(selector)

                if not next_button:
                    return False

                # Check if button is disabled
                is_disabled = await next_button.is_disabled()
                if is_disabled:
                    return False

                # Click and wait for navigation
                async with self.page.expect_navigation(timeout=10000):
                    await next_button.click()

                return True

            elif pagination_type == 'link':
                selector = pagination_config.get('selector', "a[rel='next']")
                next_link = await self.page.query_selector(selector)

                if not next_link:
                    return False

                # Click and wait for navigation
                async with self.page.expect_navigation(timeout=10000):
                    await next_link.click()

                return True

            else:
                logger.warning(f'Unsupported pagination type: {pagination_type}')
                return False

        except PlaywrightTimeoutError:
            logger.debug('Timeout during pagination navigation')
            return False
        except Exception as e:
            logger.debug(f'Error navigating to next page: {e}')
            return False

    def _is_duplicate(self, article: ScrapedArticleMetadata) -> bool:
        """
        Check if article is a duplicate using DOI or title.

        Args:
            article: Article metadata to check

        Returns:
            True if duplicate, False otherwise
        """
        # Check DOI first (most reliable)
        if article.doi and article.doi in self.existing_dois:
            return True

        # Check normalized title
        if article.title:
            normalized = self._normalize_title(article.title)
            if normalized in self.existing_titles:
                return True

        return False

    @staticmethod
    def _normalize_title(title: str) -> str:
        """
        Normalize title for deduplication comparison.

        Args:
            title: Article title

        Returns:
            Normalized title (lowercase, no punctuation/whitespace)
        """
        import re

        # Remove punctuation and extra whitespace, lowercase
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    @staticmethod
    def _clean_doi(doi: str) -> str:
        """
        Clean and normalize DOI string.

        Args:
            doi: Raw DOI string

        Returns:
            Cleaned DOI
        """
        import re

        # Remove common prefixes
        doi = re.sub(r'^(doi:|DOI:)\s*', '', doi, flags=re.IGNORECASE)
        doi = re.sub(r'^https?://.*?/(10\.\d+/.*)', r'\1', doi)

        return doi.strip()

    @property
    def extraction_stats(self) -> Dict[str, int]:  # noqa: UP006
        """Get extraction statistics."""
        return {
            'extracted': self._extracted_count,
            'skipped': self._skipped_count,
            'errors': self._error_count,
        }

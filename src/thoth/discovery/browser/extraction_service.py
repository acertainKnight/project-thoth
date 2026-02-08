"""
Extraction Service for extracting article metadata from web pages.

This module handles article extraction using configured rules, pagination,
deduplication, incremental discovery (early-stop), and post-processing
cleanup for browser-based discovery workflows.

Supports two selector formats:
- **Simple**: ``{'title': 'h3.title', 'authors': '.author'}`` (legacy)
- **Rich**: ``{'title': {'css_selector': 'h3.title', 'attribute': 'text', 'is_multiple': false}}``
  (produced by the LLM-powered WorkflowBuilder)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

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
        )
        from playwright.async_api import (
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


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------

_TRAILING_PUNCT = re.compile(r'[,;&\s]+$')
_LEADING_PUNCT = re.compile(r'^[,;&\s]+')


def _clean_author_name(name: str) -> str:
    """Strip trailing commas, ampersands, semicolons, and whitespace from a name.

    Args:
        name: Raw author name string.

    Returns:
        Cleaned author name.
    """
    name = _TRAILING_PUNCT.sub('', name)
    name = _LEADING_PUNCT.sub('', name)
    return name.strip()


def _clean_text_field(text: str | None) -> str | None:
    """Clean a generic text field by normalizing whitespace.

    Args:
        text: Raw text value.

    Returns:
        Cleaned text or None.
    """
    if not text:
        return None
    cleaned = re.sub(r'\s+', ' ', text).strip()
    return cleaned if cleaned else None


# ---------------------------------------------------------------------------
# Selector normalization
# ---------------------------------------------------------------------------


def _normalize_selector(raw: str | dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert a selector to the rich format regardless of input shape.

    Handles both simple string selectors (legacy) and rich dict selectors
    from the WorkflowBuilder.

    Args:
        raw: Either a CSS string or a dict with css_selector/attribute/is_multiple.

    Returns:
        Normalized dict or None if no selector.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        return {'css_selector': raw, 'attribute': 'text', 'is_multiple': False}
    if isinstance(raw, dict):
        return {
            'css_selector': raw.get('css_selector', raw.get('selector', '')),
            'attribute': raw.get('attribute', 'text'),
            'is_multiple': raw.get('is_multiple', False),
        }
    return None


class ExtractionService:
    """
    Service for extracting article metadata from web pages using Playwright.

    This service:
    - Accepts both simple string selectors and rich dict selectors (from WorkflowBuilder)
    - Extracts article fields: title, authors, abstract, url, doi, published_date
    - Post-processes extracted data (cleans trailing commas, normalizes whitespace)
    - Handles pagination (button click, link click, or URL parameter)
    - Performs incremental discovery: stops processing when consecutive known articles
      are encountered (for chronologically-ordered sources)
    - Provides deduplication support (check by DOI/title)

    Example:
        >>> service = ExtractionService(page, stop_on_known=True)
        >>> articles = await service.extract_articles(
        ...     extraction_rules={
        ...         'article_container': '.article-item',
        ...         'fields': {
        ...             'title': {'css_selector': 'h3.title', 'attribute': 'text'},
        ...             'authors': {
        ...                 'css_selector': '.author',
        ...                 'attribute': 'text',
        ...                 'is_multiple': True,
        ...             },
        ...         },
        ...     },
        ...     max_articles=100,
        ... )
    """

    # Number of consecutive known articles before stopping (incremental discovery)
    KNOWN_ARTICLE_STOP_THRESHOLD = 3

    def __init__(
        self,
        page: Page,
        source_name: str = 'browser_extraction',
        existing_dois: set[str] | None = None,
        existing_titles: set[str] | None = None,
        stop_on_known: bool = True,
    ):
        """
        Initialize the ExtractionService.

        Args:
            page: Playwright Page instance for browser interaction.
            source_name: Name of the discovery source for metadata.
            existing_dois: Set of DOIs already in database (for deduplication).
            existing_titles: Set of normalized titles already in database.
            stop_on_known: If True, stop paginating when consecutive known
                articles are encountered (incremental discovery).
        """
        self.page = page
        self.source_name = source_name
        self.existing_dois = existing_dois or set()
        self.existing_titles = existing_titles or set()
        self.stop_on_known = stop_on_known
        self._extracted_count = 0
        self._skipped_count = 0
        self._error_count = 0
        self._consecutive_known = 0
        self._hit_known_boundary = False

    async def extract_articles(
        self,
        extraction_rules: dict[str, Any],
        max_articles: int = 100,
    ) -> list[ScrapedArticleMetadata]:
        """
        Extract articles using configured extraction rules.

        This method:
        1. Finds article containers using the configured selector
        2. Extracts each article's metadata using field selectors
        3. Handles pagination if configured
        4. Stops early when hitting already-discovered articles (incremental)
        5. Returns list of articles up to max_articles limit

        Args:
            extraction_rules: Dictionary containing:
                - article_container: CSS selector for article elements
                - fields (or selectors): Dict of field name to selector config
                - pagination (or pagination_config): Pagination config
                - wait_for: Optional element to wait for before extraction
            max_articles: Maximum number of articles to extract.

        Returns:
            List of ScrapedArticleMetadata objects.

        Raises:
            ExtractionServiceError: If extraction fails critically.
        """
        articles: list[ScrapedArticleMetadata] = []
        self._extracted_count = 0
        self._skipped_count = 0
        self._error_count = 0
        self._consecutive_known = 0
        self._hit_known_boundary = False

        try:
            # Wait for page to be ready
            wait_for = extraction_rules.get('wait_for', 'body')
            try:
                await self.page.wait_for_selector(wait_for, timeout=10000)
            except PlaywrightTimeoutError:
                logger.warning(f'Timeout waiting for selector: {wait_for}')

            page_num = 1
            while len(articles) < max_articles:
                logger.info(
                    f'Extracting from page {page_num} '
                    f'(collected {len(articles)}/{max_articles})'
                )

                page_articles = await self._extract_articles_from_page(
                    extraction_rules,
                    max_articles - len(articles),
                )

                if not page_articles:
                    logger.info('No new articles found on current page, stopping')
                    break

                articles.extend(page_articles)

                # Incremental discovery: stop if we hit the known boundary
                if self._hit_known_boundary:
                    logger.info(
                        f'Hit known article boundary after {self._consecutive_known} '
                        'consecutive known articles — stopping pagination'
                    )
                    break

                if len(articles) >= max_articles:
                    break

                # Try pagination
                pagination_config = extraction_rules.get(
                    'pagination'
                ) or extraction_rules.get('pagination_config')
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

    # ------------------------------------------------------------------
    # Page-level extraction
    # ------------------------------------------------------------------

    async def _extract_articles_from_page(
        self,
        extraction_rules: dict[str, Any],
        max_articles: int,
    ) -> list[ScrapedArticleMetadata]:
        """
        Extract articles from the current page.

        Args:
            extraction_rules: Extraction configuration.
            max_articles: Maximum articles to extract from this page.

        Returns:
            List of extracted articles (new ones only).
        """
        articles: list[ScrapedArticleMetadata] = []
        container_selector = extraction_rules.get('article_container', 'article')

        try:
            await self.page.wait_for_selector(container_selector, timeout=5000)
            article_elements = await self.page.query_selector_all(container_selector)
            logger.debug(f'Found {len(article_elements)} article elements')

            for element in article_elements[:max_articles]:
                article = await self._extract_single_article(element, extraction_rules)

                if not article:
                    continue

                # Deduplication / incremental-stop check
                if self._is_duplicate(article):
                    self._skipped_count += 1
                    self._consecutive_known += 1
                    logger.debug(
                        f'Skipped known article ({self._consecutive_known}): '
                        f'{article.title[:60]}'
                    )
                    if (
                        self.stop_on_known
                        and self._consecutive_known >= self.KNOWN_ARTICLE_STOP_THRESHOLD
                    ):
                        self._hit_known_boundary = True
                        break
                    continue

                # Reset consecutive-known counter on a new article
                self._consecutive_known = 0

                articles.append(article)
                self._extracted_count += 1

                # Track for within-session deduplication
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

    # ------------------------------------------------------------------
    # Single-article extraction
    # ------------------------------------------------------------------

    async def _extract_single_article(
        self,
        article_element: ElementHandle,
        rules: dict[str, Any],
    ) -> ScrapedArticleMetadata | None:
        """
        Extract metadata from a single article element.

        Supports both the legacy ``selectors`` key and the builder's ``fields`` key.

        Args:
            article_element: Playwright ElementHandle for article container.
            rules: Extraction rules dict.

        Returns:
            ScrapedArticleMetadata if extraction successful, None otherwise.
        """
        try:
            # Support both "fields" (builder) and "selectors" (legacy)
            raw_selectors = rules.get('fields') or rules.get('selectors', {})

            # Normalize every selector to the rich format
            selectors: dict[str, dict[str, Any] | None] = {
                name: _normalize_selector(sel) for name, sel in raw_selectors.items()
            }

            # --- Title (required) ---
            title = await self._extract_field(article_element, selectors.get('title'))
            if not title or not isinstance(title, str):
                logger.debug('Skipped article: no title found')
                return None
            title = _clean_text_field(title) or ''

            # --- Authors ---
            authors_raw = await self._extract_field(
                article_element,
                selectors.get('authors'),
            )
            if isinstance(authors_raw, list):
                authors = [_clean_author_name(a) for a in authors_raw if a.strip()]
            elif isinstance(authors_raw, str):
                # Single string — split on commas
                authors = [
                    _clean_author_name(a) for a in authors_raw.split(',') if a.strip()
                ]
            else:
                authors = []

            # --- Optional text fields ---
            abstract = _clean_text_field(
                await self._extract_field(article_element, selectors.get('abstract'))
            )
            doi = await self._extract_field(article_element, selectors.get('doi'))
            arxiv_id = await self._extract_field(
                article_element,
                selectors.get('arxiv_id'),
            )
            journal = _clean_text_field(
                await self._extract_field(article_element, selectors.get('journal')),
            )
            publication_date = _clean_text_field(
                await self._extract_field(
                    article_element,
                    selectors.get('publication_date'),
                ),
            )

            # --- URL fields ---
            url = await self._extract_field(article_element, selectors.get('url'))
            pdf_url = await self._extract_field(
                article_element,
                selectors.get('pdf_url'),
            )

            # --- Keywords ---
            keywords_raw = await self._extract_field(
                article_element,
                selectors.get('keywords'),
            )
            if isinstance(keywords_raw, list):
                keywords = [k.strip() for k in keywords_raw if k.strip()]
            elif isinstance(keywords_raw, str):
                keywords = [k.strip() for k in keywords_raw.split(',') if k.strip()]
            else:
                keywords = []

            # --- Clean and normalize ---
            if isinstance(doi, str):
                doi = self._clean_doi(doi)
            if isinstance(arxiv_id, str):
                arxiv_id = arxiv_id.strip()

            # Make URLs absolute
            if isinstance(url, str):
                url = self._make_absolute(url)
            if isinstance(pdf_url, str):
                pdf_url = self._make_absolute(pdf_url)

            return ScrapedArticleMetadata(
                title=title,
                authors=authors,
                abstract=abstract,
                publication_date=publication_date,
                journal=journal,
                doi=doi if isinstance(doi, str) else None,
                arxiv_id=arxiv_id if isinstance(arxiv_id, str) else None,
                url=url if isinstance(url, str) else None,
                pdf_url=pdf_url if isinstance(pdf_url, str) else None,
                keywords=keywords,
                source=self.source_name,
                scrape_timestamp=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            logger.debug(f'Error extracting article: {e}')
            self._error_count += 1
            return None

    # ------------------------------------------------------------------
    # Unified field extraction (supports simple + rich selectors)
    # ------------------------------------------------------------------

    async def _extract_field(
        self,
        element: ElementHandle,
        selector: dict[str, Any] | None,
    ) -> str | list[str] | None:
        """
        Extract a field value using a normalized selector config.

        Args:
            element: Parent element to search within.
            selector: Normalized selector dict (css_selector, attribute, is_multiple).

        Returns:
            Extracted value: a single string, list of strings, or None.
        """
        if not selector:
            return None

        css = selector.get('css_selector', '')
        attribute = selector.get('attribute', 'text')
        is_multiple = selector.get('is_multiple', False)

        if not css:
            return None

        try:
            if is_multiple:
                targets = await element.query_selector_all(css)
                values = []
                for target in targets:
                    val = await self._get_element_value(target, attribute)
                    if val:
                        values.append(val.strip())
                return values

            target = await element.query_selector(css)
            if not target:
                return None
            val = await self._get_element_value(target, attribute)
            return val.strip() if val else None

        except Exception as e:
            logger.debug(f"Error extracting field with selector '{css}': {e}")
            return None

    async def _get_element_value(self, element: ElementHandle, attribute: str) -> str:
        """Get value from an element based on the attribute type.

        Args:
            element: Playwright ElementHandle.
            attribute: 'text' for text_content, otherwise get_attribute.

        Returns:
            Extracted string value.
        """
        if attribute == 'text':
            return await element.text_content() or ''
        return await element.get_attribute(attribute) or ''

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    async def _navigate_to_next_page(
        self,
        pagination_config: dict[str, Any],
    ) -> bool:
        """
        Navigate to the next page using pagination configuration.

        Supports multiple config shapes:
        - ``{'type': 'button', 'selector': '...'}``
        - ``{'type': 'link', 'selector': '...'}``
        - ``{'next_page_selector': '...'}`` (from WorkflowBuilder)
        - ``{'next_button_selector': '...'}`` (shorthand)

        Args:
            pagination_config: Dict with pagination strategy.

        Returns:
            True if navigation successful, False if no next page.
        """
        try:
            # Normalize the various config shapes
            pagination_type = pagination_config.get('type', 'button')
            selector = (
                pagination_config.get('selector')
                or pagination_config.get('next_page_selector')
                or pagination_config.get('next_button_selector')
            )

            if not selector:
                # Fallback defaults
                selector = 'button.next, a.next, a[rel="next"]'

            if pagination_type in ('button', 'link'):
                target = await self.page.query_selector(selector)
                if not target:
                    return False

                # Check if it's disabled
                try:
                    is_disabled = await target.is_disabled()
                    if is_disabled:
                        return False
                except Exception:
                    pass  # Not all elements support is_disabled

                # Click and wait for new content
                try:
                    async with self.page.expect_navigation(timeout=15000):
                        await target.click()
                except PlaywrightTimeoutError:
                    # Some SPAs don't trigger navigation events;
                    # wait for network idle instead
                    await target.click()
                    await self.page.wait_for_load_state('networkidle', timeout=10000)

                return True

            logger.warning(f'Unsupported pagination type: {pagination_type}')
            return False

        except PlaywrightTimeoutError:
            logger.debug('Timeout during pagination navigation')
            return False
        except Exception as e:
            logger.debug(f'Error navigating to next page: {e}')
            return False

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def _make_absolute(self, url: str) -> str:
        """Convert a relative URL to absolute using the current page URL.

        Args:
            url: Possibly relative URL.

        Returns:
            Absolute URL.
        """
        if not url or url.startswith('http'):
            return url
        parsed = urlparse(self.page.url)
        base = f'{parsed.scheme}://{parsed.netloc}'
        if url.startswith('/'):
            return base + url
        return self.page.url.rstrip('/') + '/' + url.lstrip('/')

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _is_duplicate(self, article: ScrapedArticleMetadata) -> bool:
        """
        Check if article is a duplicate using DOI or title.

        Args:
            article: Article metadata to check.

        Returns:
            True if duplicate, False otherwise.
        """
        if article.doi and article.doi in self.existing_dois:
            return True
        if article.title:
            normalized = self._normalize_title(article.title)
            if normalized in self.existing_titles:
                return True
        return False

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize title for deduplication comparison.

        Args:
            title: Article title.

        Returns:
            Normalized title (lowercase, no punctuation/whitespace).
        """
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    @staticmethod
    def _clean_doi(doi: str) -> str:
        """Clean and normalize DOI string.

        Args:
            doi: Raw DOI string.

        Returns:
            Cleaned DOI.
        """
        doi = re.sub(r'^(doi:|DOI:)\s*', '', doi, flags=re.IGNORECASE)
        doi = re.sub(r'^https?://.*?/(10\.\d+/.*)', r'\1', doi)
        return doi.strip()

    @property
    def extraction_stats(self) -> dict[str, int]:
        """Get extraction statistics."""
        return {
            'extracted': self._extracted_count,
            'skipped': self._skipped_count,
            'errors': self._error_count,
        }

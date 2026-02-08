"""
LLM-powered workflow builder for automatic article source configuration.

This module provides intelligent auto-detection of article elements on any
webpage using Playwright for DOM extraction and an LLM for structural analysis.

Flow:
    1. User provides a URL
    2. Playwright loads the page and extracts a simplified DOM representation
    3. LLM analyzes the structure and proposes CSS selectors
    4. Selectors are tested against the live page
    5. Sample results are returned for user confirmation
    6. If wrong, screenshots + user feedback refine via LLM
    7. Confirmed selectors are saved as a workflow
"""

from __future__ import annotations

import asyncio
import base64
import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from thoth.config import Config, config
from thoth.discovery.browser.browser_manager import BrowserManager
from thoth.services.llm_service import LLMService

# ---------------------------------------------------------------------------
# Pydantic schemas for structured LLM output
# ---------------------------------------------------------------------------


class ProposedSelector(BaseModel):
    """A single CSS selector proposed by the LLM for a metadata field."""

    field_name: str = Field(
        description='Metadata field: title, authors, abstract, url, pdf_url, doi, publication_date, keywords, journal'
    )
    css_selector: str = Field(
        description='CSS selector relative to the article container'
    )
    attribute: str = Field(
        default='text',
        description='How to extract value: text, href, src, or a specific attribute name',
    )
    is_multiple: bool = Field(
        default=False,
        description='True if selector returns multiple values (e.g. list of authors)',
    )
    confidence: float = Field(default=0.5, description='Confidence score 0.0-1.0')


class SearchFilterInfo(BaseModel):
    """Information about a detected search or filter UI element."""

    element_type: str = Field(
        description='Type: search_input, date_filter, subject_filter, sort_dropdown, keyword_input'
    )
    css_selector: str = Field(description='CSS selector for the element')
    submit_selector: str | None = Field(
        default=None,
        description='CSS selector for the submit/search button, if separate from input',
    )
    filter_type: str = Field(
        default='text_input',
        description='How to interact: text_input, dropdown, date_input, checkbox, radio',
    )
    description: str = Field(default='', description='What this filter does')


class PageAnalysisResult(BaseModel):
    """Structured output from LLM page analysis."""

    page_type: str = Field(
        description='Type of page: article_listing, search_results, journal_toc, conference_proceedings, single_article, unknown'
    )
    article_container_selector: str = Field(
        description='CSS selector for each article/paper element in the listing'
    )
    selectors: list[ProposedSelector] = Field(
        description='Proposed CSS selectors for each metadata field'
    )
    pagination_selector: str | None = Field(
        default=None,
        description='CSS selector for next-page button/link, if pagination exists',
    )
    search_filters: list[SearchFilterInfo] = Field(
        default_factory=list,
        description='Detected search/filter UI elements on the page',
    )
    notes: str = Field(
        default='', description='Any observations about the page structure'
    )


class SelectorRefinement(BaseModel):
    """Structured output from LLM selector refinement."""

    article_container_selector: str = Field(
        description='Refined CSS selector for article container'
    )
    selectors: list[ProposedSelector] = Field(description='Refined CSS selectors')
    pagination_selector: str | None = Field(default=None)
    search_filters: list[SearchFilterInfo] = Field(
        default_factory=list, description='Detected search/filter UI elements'
    )
    notes: str = Field(default='')


# ---------------------------------------------------------------------------
# Data classes for builder results
# ---------------------------------------------------------------------------


@dataclass
class SampleArticle:
    """A sample article extracted during testing."""

    title: str = ''
    authors: list[str] = field(default_factory=list)
    abstract: str = ''
    url: str = ''
    pdf_url: str = ''
    doi: str = ''
    publication_date: str = ''
    keywords: list[str] = field(default_factory=list)
    journal: str = ''


@dataclass
class AnalysisOutput:
    """Complete output from the workflow builder analysis."""

    url: str
    page_title: str
    page_type: str
    article_container_selector: str
    selectors: dict[str, dict[str, Any]]
    pagination_selector: str | None
    sample_articles: list[SampleArticle]
    total_articles_found: int
    search_filters: list[dict[str, Any]] = field(default_factory=list)
    screenshot_base64: str | None = None
    notes: str = ''
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'url': self.url,
            'page_title': self.page_title,
            'page_type': self.page_type,
            'article_container_selector': self.article_container_selector,
            'selectors': self.selectors,
            'pagination_selector': self.pagination_selector,
            'search_filters': self.search_filters,
            'sample_articles': [
                {k: v for k, v in a.__dict__.items() if v} for a in self.sample_articles
            ],
            'total_articles_found': self.total_articles_found,
            'screenshot_base64': self.screenshot_base64,
            'notes': self.notes,
            'confidence': self.confidence,
        }


# ---------------------------------------------------------------------------
# DOM extraction helpers
# ---------------------------------------------------------------------------

_EXTRACT_DOM_JS = """
() => {
    // Extract a simplified DOM representation focused on repeated structures
    // that likely represent article listings.

    function getSelector(el) {
        if (el.id) return '#' + el.id;
        let s = el.tagName.toLowerCase();
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.trim().split(/\\s+/).slice(0, 3).join('.');
            if (classes) s += '.' + classes;
        }
        return s;
    }

    function summarizeElement(el, depth, maxDepth) {
        if (depth > maxDepth) return null;
        const tag = el.tagName.toLowerCase();
        const text = el.textContent?.trim().substring(0, 120) || '';
        const href = el.getAttribute('href') || '';
        const children = [];

        for (const child of el.children) {
            const summary = summarizeElement(child, depth + 1, maxDepth);
            if (summary) children.push(summary);
        }

        return {
            tag,
            id: el.id || undefined,
            classes: el.className && typeof el.className === 'string'
                ? el.className.trim().split(/\\s+/).slice(0, 5)
                : [],
            text: text.substring(0, 120),
            href: href ? href.substring(0, 200) : undefined,
            childCount: el.children.length,
            children: children.length <= 8 ? children : children.slice(0, 8),
        };
    }

    // Find repeated sibling patterns (likely article listings)
    function findRepeatedPatterns() {
        const patterns = [];
        const allElements = document.querySelectorAll('*');
        const checked = new Set();

        for (const el of allElements) {
            if (checked.has(el) || !el.parentElement) continue;
            const parent = el.parentElement;
            if (checked.has(parent)) continue;

            // Find siblings with same tag+class pattern
            const siblings = Array.from(parent.children);
            if (siblings.length < 3) continue;

            const sig = getSelector(siblings[0]);
            const matching = siblings.filter(s => getSelector(s) === sig);

            if (matching.length >= 3) {
                checked.add(parent);
                const parentSel = getSelector(parent);
                const itemSel = sig;

                // Get sample items (first 3)
                const samples = matching.slice(0, 3).map(m => summarizeElement(m, 0, 3));

                patterns.push({
                    parentSelector: parentSel,
                    itemSelector: itemSel,
                    fullSelector: parentSel + ' > ' + itemSel,
                    count: matching.length,
                    samples,
                });
            }
        }

        // Sort by count (most repeated = most likely articles)
        patterns.sort((a, b) => b.count - a.count);
        return patterns.slice(0, 5);
    }

    const patterns = findRepeatedPatterns();
    const title = document.title;
    const metaDesc = document.querySelector('meta[name="description"]')?.content || '';

    // Also get basic page structure
    const bodyOutline = summarizeElement(document.body, 0, 2);

    return {
        title,
        metaDescription: metaDesc,
        url: window.location.href,
        repeatedPatterns: patterns,
        bodyOutline,
    };
}
"""


# ---------------------------------------------------------------------------
# WorkflowBuilder
# ---------------------------------------------------------------------------


class WorkflowBuilder:
    """
    LLM-powered workflow builder that auto-detects article elements on webpages.

    This class orchestrates:
    1. Page loading via Playwright
    2. DOM extraction (simplified structure for LLM context)
    3. LLM analysis to propose CSS selectors
    4. Selector testing against the live page
    5. Screenshot capture for fallback refinement

    Example:
        >>> builder = WorkflowBuilder()
        >>> await builder.initialize()
        >>> result = await builder.analyze_url(
        ...     'https://proceedings.neurips.cc/paper/2023'
        ... )
        >>> print(result.sample_articles)
        >>> await builder.shutdown()
    """

    def __init__(self, thoth_config: Config | None = None):
        """
        Initialize the WorkflowBuilder.

        Args:
            thoth_config: Thoth configuration. Uses global config if None.
        """
        self.config = thoth_config or config
        self.llm_service = LLMService(self.config)
        self.browser_manager = BrowserManager(
            thoth_config=self.config,
            max_concurrent_browsers=2,
            default_timeout=30000,
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Playwright browser manager."""
        if not self._initialized:
            await self.browser_manager.initialize()
            self._initialized = True
            logger.info('WorkflowBuilder initialized')

    async def shutdown(self) -> None:
        """Shutdown browser manager."""
        if self._initialized:
            await self.browser_manager.shutdown()
            self._initialized = False

    async def analyze_url(
        self,
        url: str,
        include_screenshot: bool = True,
    ) -> AnalysisOutput:
        """
        Analyze a URL to auto-detect article listing structure.

        This is the main entry point. It loads the page, extracts DOM info,
        sends it to the LLM, tests the proposed selectors, and returns
        sample results for user confirmation.

        Args:
            url: The URL to analyze.
            include_screenshot: Whether to capture a screenshot.

        Returns:
            AnalysisOutput: Analysis results with proposed selectors and samples.
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f'Analyzing URL: {url}')

        async with self.browser_manager.browser_context(headless=True) as context:
            page = await context.new_page()

            # 1. Load the page
            await page.goto(url, wait_until='domcontentloaded')
            # Wait a bit for JS-rendered content
            await asyncio.sleep(2)
            await page.wait_for_load_state('networkidle', timeout=10000)

            page_title = await page.title()
            logger.info(f'Page loaded: "{page_title}"')

            # 2. Extract simplified DOM
            dom_data = await page.evaluate(_EXTRACT_DOM_JS)
            logger.info(
                f'DOM extracted: {len(dom_data.get("repeatedPatterns", []))} repeated patterns found'
            )

            # 3. Take screenshot (for fallback and user reference)
            screenshot_b64 = None
            if include_screenshot:
                screenshot_bytes = await page.screenshot(
                    full_page=False,
                    type='png',
                )
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')

            # 4. Ask LLM to analyze the page structure
            analysis = await self._llm_analyze_page(url, dom_data)

            # 5. Test proposed selectors against the live page
            sample_articles, total_found = await self._test_selectors(
                page,
                analysis,
                max_samples=5,
            )

            # Calculate confidence based on what we found
            confidence = self._calculate_confidence(
                analysis, sample_articles, total_found
            )

            logger.info(
                f'Analysis complete: type={analysis.page_type}, '
                f'articles={total_found}, confidence={confidence:.2f}'
            )

            # Build selectors dict for the output
            selectors_dict = {}
            for sel in analysis.selectors:
                selectors_dict[sel.field_name] = {
                    'css_selector': sel.css_selector,
                    'attribute': sel.attribute,
                    'is_multiple': sel.is_multiple,
                    'confidence': sel.confidence,
                }

            # Build search_filters list for the output
            search_filters = [sf.model_dump() for sf in analysis.search_filters]

            return AnalysisOutput(
                url=url,
                page_title=page_title,
                page_type=analysis.page_type,
                article_container_selector=analysis.article_container_selector,
                selectors=selectors_dict,
                pagination_selector=analysis.pagination_selector,
                sample_articles=sample_articles,
                total_articles_found=total_found,
                search_filters=search_filters,
                screenshot_base64=screenshot_b64,
                notes=analysis.notes,
                confidence=confidence,
            )

    async def refine_selectors(
        self,
        url: str,
        current_selectors: dict[str, Any],
        user_feedback: str,
        include_screenshot: bool = True,
    ) -> AnalysisOutput:
        """
        Refine selectors based on user feedback.

        This is the fallback flow. The user sees the current results (possibly
        with a screenshot) and describes what's wrong. The LLM uses the feedback
        to propose better selectors.

        Args:
            url: The URL being analyzed.
            current_selectors: Current selector configuration.
            user_feedback: User's description of what's wrong.
            include_screenshot: Whether to capture a fresh screenshot.

        Returns:
            AnalysisOutput: Updated analysis with refined selectors.
        """
        if not self._initialized:
            await self.initialize()

        logger.info(
            f'Refining selectors for {url} with feedback: {user_feedback[:100]}'
        )

        async with self.browser_manager.browser_context(headless=True) as context:
            page = await context.new_page()
            await page.goto(url, wait_until='domcontentloaded')
            await asyncio.sleep(2)

            page_title = await page.title()

            # Re-extract DOM for context
            dom_data = await page.evaluate(_EXTRACT_DOM_JS)

            # Screenshot for reference
            screenshot_b64 = None
            if include_screenshot:
                screenshot_bytes = await page.screenshot(full_page=False, type='png')
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')

            # Ask LLM to refine
            refinement = await self._llm_refine_selectors(
                url,
                dom_data,
                current_selectors,
                user_feedback,
            )

            # Test refined selectors
            sample_articles, total_found = await self._test_selectors(
                page,
                refinement,
                max_samples=5,
            )

            confidence = self._calculate_confidence(
                refinement, sample_articles, total_found
            )

            selectors_dict = {}
            for sel in refinement.selectors:
                selectors_dict[sel.field_name] = {
                    'css_selector': sel.css_selector,
                    'attribute': sel.attribute,
                    'is_multiple': sel.is_multiple,
                    'confidence': sel.confidence,
                }

            search_filters = [sf.model_dump() for sf in refinement.search_filters]

            return AnalysisOutput(
                url=url,
                page_title=page_title,
                page_type='refined',
                article_container_selector=refinement.article_container_selector,
                selectors=selectors_dict,
                pagination_selector=refinement.pagination_selector,
                sample_articles=sample_articles,
                total_articles_found=total_found,
                search_filters=search_filters,
                screenshot_base64=screenshot_b64,
                notes=refinement.notes,
                confidence=confidence,
            )

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    async def _llm_analyze_page(
        self,
        url: str,
        dom_data: dict[str, Any],
    ) -> PageAnalysisResult:
        """
        Send page DOM structure to LLM for analysis.

        Args:
            url: The page URL.
            dom_data: Simplified DOM data extracted by JavaScript.

        Returns:
            PageAnalysisResult: LLM's proposed selectors and page classification.
        """
        # Build a concise DOM summary for the LLM
        dom_summary = self._format_dom_for_llm(dom_data)

        prompt = f"""You are an expert web scraper. Analyze this webpage and identify how to extract academic articles/papers from it.

## Page Information
- URL: {url}
- Title: {dom_data.get('title', 'Unknown')}
- Meta Description: {dom_data.get('metaDescription', 'None')}

## Page Structure (Repeated Patterns Found)
{dom_summary}

## Your Task
Identify CSS selectors to extract article metadata from this page. The page likely contains a list of academic papers/articles.

For each article, I need selectors for these fields (relative to the article container element):
- **title**: The paper/article title (usually a link or heading)
- **url**: Link to the article detail page (usually the href of the title link)
- **authors**: Author names (may be a list of elements)
- **abstract**: Abstract or summary text (may not be visible on listing pages)
- **pdf_url**: Direct link to PDF (if available on listing page)
- **doi**: DOI identifier (if visible)
- **publication_date**: Publication date (if visible)
- **keywords**: Keywords or tags (if visible)
- **journal**: Journal or venue name (if visible)

Additionally, identify any **search/filter UI elements** on the page:
- **search_input**: A text input for searching/filtering papers by keyword
- **date_filter**: A date picker, date range selector, or year filter
- **subject_filter**: A dropdown or input for filtering by subject/category/topic
- **sort_dropdown**: A dropdown for changing sort order

For each search/filter element found, provide:
- element_type: what kind of filter it is
- css_selector: how to target it
- submit_selector: the search/submit button selector (if the search input needs a separate button click)
- filter_type: how to interact with it (text_input, dropdown, date_input)
- description: what it does

Important:
- The article_container_selector should match EACH individual article/paper element
- Field selectors are RELATIVE to the article container (use child/descendant selectors)
- For the URL field, use attribute="href" to extract the link
- For pdf_url, use attribute="href"
- Only include selectors for fields you can actually identify in the DOM
- Set confidence scores honestly based on how certain you are
- If pagination exists (next page button/link), identify its selector
- If search or filter inputs exist, identify them so we can inject keywords and date filters"""

        try:
            client = self.llm_service.get_client(
                model=self.config.llm_config.default.model,
            )
            structured = client.with_structured_output(
                PageAnalysisResult,
                method='json_schema',
            )
            result = structured.invoke(prompt)
            logger.info(
                f'LLM analysis: page_type={result.page_type}, {len(result.selectors)} selectors proposed'
            )
            return result

        except Exception as e:
            logger.error(f'LLM analysis failed: {e}')
            # Return a minimal fallback based on DOM patterns
            return self._fallback_analysis(dom_data)

    async def _llm_refine_selectors(
        self,
        url: str,
        dom_data: dict[str, Any],
        current_selectors: dict[str, Any],
        user_feedback: str,
    ) -> SelectorRefinement:
        """
        Ask LLM to refine selectors based on user feedback.

        Args:
            url: The page URL.
            dom_data: Simplified DOM data.
            current_selectors: Current selector configuration that needs fixing.
            user_feedback: User's description of what's wrong.

        Returns:
            SelectorRefinement: Refined selectors.
        """
        dom_summary = self._format_dom_for_llm(dom_data)

        # Format current selectors for the prompt (skip _container key)
        current_str = '\n'.join(
            f'  - {k}: selector="{v.get("css_selector", "")}", attribute="{v.get("attribute", "text")}"'
            for k, v in current_selectors.items()
            if isinstance(v, dict)
        )

        prompt = f"""You are an expert web scraper. The user tried to auto-detect article selectors on a page but the results were wrong. Fix the selectors based on their feedback.

## Page Information
- URL: {url}
- Title: {dom_data.get('title', 'Unknown')}

## Current Selectors (WRONG - need fixing)
  - article_container: "{current_selectors.get('_container', '')}"
{current_str}

## User Feedback
"{user_feedback}"

## Page Structure
{dom_summary}

## Your Task
Based on the user's feedback and the page structure, provide corrected CSS selectors.
- Fix whatever the user says is wrong
- Keep selectors that were working correctly
- The article_container_selector should match EACH individual article element
- Field selectors are RELATIVE to the article container"""

        try:
            client = self.llm_service.get_client(
                model=self.config.llm_config.default.model,
            )
            structured = client.with_structured_output(
                SelectorRefinement,
                method='json_schema',
            )
            return structured.invoke(prompt)

        except Exception as e:
            logger.error(f'LLM refinement failed: {e}')
            # Return current selectors unchanged
            return SelectorRefinement(
                article_container_selector=current_selectors.get(
                    '_container', 'article'
                ),
                selectors=[
                    ProposedSelector(
                        field_name=k,
                        css_selector=v.get('css_selector', ''),
                        attribute=v.get('attribute', 'text'),
                    )
                    for k, v in current_selectors.items()
                    if k != '_container'
                ],
                notes=f'Refinement failed: {e}',
            )

    # ------------------------------------------------------------------
    # DOM formatting
    # ------------------------------------------------------------------

    def _format_dom_for_llm(self, dom_data: dict[str, Any]) -> str:
        """
        Format extracted DOM data into a concise string for the LLM prompt.

        Args:
            dom_data: Raw DOM data from JavaScript extraction.

        Returns:
            str: Formatted DOM summary.
        """
        lines = []

        patterns = dom_data.get('repeatedPatterns', [])
        if patterns:
            for i, pattern in enumerate(patterns):
                lines.append(
                    f'### Pattern {i + 1}: {pattern["count"]} repeated elements'
                )
                lines.append(f'Selector: `{pattern["fullSelector"]}`')
                lines.append('')

                for j, sample in enumerate(pattern.get('samples', [])[:3]):
                    lines.append(f'  Sample {j + 1}:')
                    lines.append(self._format_element(sample, indent=4))
                    lines.append('')
        else:
            lines.append('No clear repeated patterns found.')
            outline = dom_data.get('bodyOutline')
            if outline:
                lines.append('\nPage outline:')
                lines.append(self._format_element(outline, indent=2))

        return '\n'.join(lines)

    def _format_element(self, el: dict[str, Any], indent: int = 0) -> str:
        """Recursively format a DOM element summary."""
        if not el:
            return ''

        prefix = ' ' * indent
        tag = el.get('tag', '?')
        classes = '.'.join(el.get('classes', [])[:3])
        el_id = el.get('id', '')
        text = el.get('text', '')[:80]
        href = el.get('href', '')

        parts = [f'{prefix}<{tag}']
        if el_id:
            parts.append(f' id="{el_id}"')
        if classes:
            parts.append(f' class="{classes}"')
        parts.append('>')

        line = ''.join(parts)
        if href:
            line += f' href="{href[:100]}"'
        if text:
            # Clean up text (remove newlines, excess spaces)
            clean_text = re.sub(r'\s+', ' ', text).strip()[:80]
            line += f' → "{clean_text}"'

        lines = [line]

        for child in el.get('children', [])[:5]:
            child_str = self._format_element(child, indent + 2)
            if child_str:
                lines.append(child_str)

        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # Selector testing
    # ------------------------------------------------------------------

    async def _test_selectors(
        self,
        page: Any,
        analysis: PageAnalysisResult | SelectorRefinement,
        max_samples: int = 5,
    ) -> tuple[list[SampleArticle], int]:
        """
        Test proposed selectors against the live page.

        Args:
            page: Playwright page instance.
            analysis: LLM analysis result with proposed selectors.
            max_samples: Maximum sample articles to extract.

        Returns:
            Tuple of (sample_articles, total_articles_found).
        """
        container_sel = analysis.article_container_selector

        try:
            # Find all article containers
            containers = await page.query_selector_all(container_sel)
            total_found = len(containers)
            logger.info(f'Selector "{container_sel}" matched {total_found} elements')

            if total_found == 0:
                return [], 0

            # Build selector map
            selector_map = {sel.field_name: sel for sel in analysis.selectors}

            # Extract sample articles
            samples = []
            for container in containers[:max_samples]:
                article = await self._extract_sample(container, selector_map, page)
                if article.title:  # At minimum we need a title
                    samples.append(article)

            return samples, total_found

        except Exception as e:
            logger.error(f'Selector testing failed: {e}')
            return [], 0

    async def _extract_sample(
        self,
        container: Any,
        selector_map: dict[str, ProposedSelector],
        page: Any,
    ) -> SampleArticle:
        """
        Extract a single sample article from a container element.

        Args:
            container: Playwright ElementHandle for the article container.
            selector_map: Map of field names to ProposedSelector.
            page: Playwright page (for URL resolution).

        Returns:
            SampleArticle: Extracted sample data.
        """
        article = SampleArticle()

        # Fields that should always be lists
        list_fields = {'authors', 'keywords'}

        for field_name, selector in selector_map.items():
            try:
                value = await self._extract_field(container, selector, page)
                if value:
                    # Ensure list fields are always lists
                    if field_name in list_fields and isinstance(value, str):
                        # Split comma-separated string into a list
                        value = [v.strip() for v in value.split(',') if v.strip()]
                    setattr(article, field_name, value)
            except Exception as e:
                logger.debug(f'Failed to extract {field_name}: {e}')

        return article

    async def _extract_field(
        self,
        container: Any,
        selector: ProposedSelector,
        page: Any,
    ) -> str | list[str]:
        """
        Extract a single field value from a container using a selector.

        Args:
            container: Playwright ElementHandle.
            selector: ProposedSelector with CSS and attribute info.
            page: Playwright page for URL resolution.

        Returns:
            Extracted value (string or list of strings).
        """
        css = selector.css_selector
        if not css:
            return ''

        if selector.is_multiple:
            # Extract multiple values (e.g., authors)
            elements = await container.query_selector_all(css)
            values = []
            for el in elements:
                val = await self._get_element_value(el, selector.attribute)
                if val:
                    values.append(val.strip())
            return values

        # Single value
        element = await container.query_selector(css)
        if not element:
            return ''

        value = await self._get_element_value(element, selector.attribute)

        # Make relative URLs absolute
        if value and selector.attribute == 'href' and not value.startswith('http'):
            base_url = page.url
            if value.startswith('/'):
                # Extract domain from base URL
                from urllib.parse import urlparse

                parsed = urlparse(base_url)
                value = f'{parsed.scheme}://{parsed.netloc}{value}'
            else:
                value = base_url.rstrip('/') + '/' + value

        return value.strip() if isinstance(value, str) else value

    async def _get_element_value(self, element: Any, attribute: str) -> str:
        """Get value from an element based on the attribute type."""
        if attribute == 'text':
            return await element.text_content() or ''
        return await element.get_attribute(attribute) or ''

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        analysis: PageAnalysisResult | SelectorRefinement,
        samples: list[SampleArticle],
        total_found: int,
    ) -> float:
        """
        Calculate confidence score for the analysis results.

        Args:
            analysis: LLM analysis result.
            samples: Sample articles extracted.
            total_found: Total article containers found.

        Returns:
            float: Confidence score 0.0-1.0.
        """
        score = 0.0

        # Found a reasonable number of articles
        if total_found >= 3:
            score += 0.2
        if total_found >= 10:
            score += 0.1

        # Samples have titles
        titled = sum(1 for s in samples if s.title)
        if samples:
            score += 0.3 * (titled / len(samples))

        # Samples have URLs
        with_urls = sum(1 for s in samples if s.url)
        if samples:
            score += 0.2 * (with_urls / len(samples))

        # Samples have authors or abstracts (rich metadata)
        with_authors = sum(1 for s in samples if s.authors)
        with_abstracts = sum(1 for s in samples if s.abstract)
        if samples:
            richness = (with_authors + with_abstracts) / (2 * len(samples))
            score += 0.2 * richness

        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Fallback analysis
    # ------------------------------------------------------------------

    def _fallback_analysis(self, dom_data: dict[str, Any]) -> PageAnalysisResult:
        """
        Create a basic analysis from DOM patterns when LLM fails.

        Args:
            dom_data: DOM data with repeated patterns.

        Returns:
            PageAnalysisResult: Best-effort analysis.
        """
        patterns = dom_data.get('repeatedPatterns', [])

        if patterns:
            best = patterns[0]
            container = best['fullSelector']
            return PageAnalysisResult(
                page_type='unknown',
                article_container_selector=container,
                selectors=[
                    ProposedSelector(
                        field_name='title',
                        css_selector='a',
                        attribute='text',
                        confidence=0.3,
                    ),
                    ProposedSelector(
                        field_name='url',
                        css_selector='a',
                        attribute='href',
                        confidence=0.3,
                    ),
                ],
                notes='LLM analysis failed, using heuristic fallback.',
            )

        return PageAnalysisResult(
            page_type='unknown',
            article_container_selector='article',
            selectors=[
                ProposedSelector(
                    field_name='title',
                    css_selector='h2 a, h3 a, a',
                    attribute='text',
                    confidence=0.1,
                ),
            ],
            notes='LLM analysis failed and no repeated patterns found.',
        )

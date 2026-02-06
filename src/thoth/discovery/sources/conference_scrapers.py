"""Pre-configured web scraper configurations for major ML/AI conferences.

This module provides factory functions that create ScrapeConfiguration objects
for well-known ML/AI conferences and journals like NeurIPS, ICML, JMLR, and AAAI.
"""

from __future__ import annotations

from thoth.utilities.schemas import ScrapeConfiguration


def neurips_scrape_config(year: int = 2024) -> ScrapeConfiguration:
    """Create scraper configuration for NeurIPS proceedings.
    
    Args:
        year: Year of the conference (e.g., 2024).
        
    Returns:
        ScrapeConfiguration for NeurIPS proceedings.
        
    Example:
        >>> config = neurips_scrape_config(2024)
        >>> scraper = WebScraper()
        >>> results = scraper.scrape(config, max_articles=10)
    """
    return ScrapeConfiguration(
        base_url=f'https://proceedings.neurips.cc/paper/{year}',
        navigation_rules={
            'article_container': 'li.conference',  # Papers in <li class="conference">
        },
        extraction_rules={
            'title': {
                'selector': '.paper-content a',
                'attribute': 'text',
            },
            'url': {
                'selector': '.paper-content a',
                'attribute': 'href',
            },
            'authors': {
                'selector': '.paper-authors',
                'attribute': 'text',
            },
        },
        pagination_config={
            'type': 'none',  # Single page with all papers
        },
        rate_limiting={
            'delay': 2.0,
            'randomize': True,
        },
        headers={
            'User-Agent': 'Thoth/1.0 (Research Paper Discovery)',
        },
    )


def icml_pmlr_scrape_config(volume: int = 235) -> ScrapeConfiguration:
    """Create scraper configuration for ICML/PMLR proceedings.
    
    PMLR (Proceedings of Machine Learning Research) hosts ICML and other conferences.
    Each conference has a volume number (e.g., v235 for ICML 2024).
    
    Args:
        volume: PMLR volume number (e.g., 235 for ICML 2024, 267 for ICML 2025).
        
    Returns:
        ScrapeConfiguration for ICML/PMLR proceedings.
        
    Example:
        >>> config = icml_pmlr_scrape_config(volume=235)  # ICML 2024
        >>> scraper = WebScraper(config)
        >>> results = scraper.scrape(max_results=10)
    
    Volume mappings:
        - ICML 2024: v235
        - ICML 2025: v267
        - AISTATS 2024: v238
        - CoRL 2023: v229
    """
    return ScrapeConfiguration(
        base_url=f'https://proceedings.mlr.press/v{volume}/',
        navigation_rules={
            'article_container': 'div.paper',  # Each paper in a div with class 'paper'
        },
        extraction_rules={
            'title': {
                'selector': 'p.title',
                'attribute': 'text',
            },
            'authors': {
                'selector': 'span.author',
                'attribute': 'text',
                'multiple': True,  # Multiple author spans
            },
            'abstract': {
                'selector': 'p.abstract',
                'attribute': 'text',
            },
            'url': {
                'selector': 'a.pdf',
                'attribute': 'href',
            },
            'pdf_url': {
                'selector': 'a.pdf',
                'attribute': 'href',
            },
        },
        pagination_config={
            'type': 'none',  # Single page with all papers
        },
        rate_limiting={
            'delay': 2.0,
            'randomize': True,
        },
        headers={
            'User-Agent': 'Thoth/1.0 (Research Paper Discovery)',
        },
    )


def jmlr_scrape_config(volume: int = 26) -> ScrapeConfiguration:
    """Create scraper configuration for JMLR (Journal of Machine Learning Research).
    
    Args:
        volume: JMLR volume number (e.g., 26 for 2025).
        
    Returns:
        ScrapeConfiguration for JMLR papers.
        
    Example:
        >>> config = jmlr_scrape_config(volume=26)
        >>> scraper = WebScraper(config)
        >>> results = scraper.scrape(max_results=10)
    """
    return ScrapeConfiguration(
        base_url=f'https://jmlr.org/papers/v{volume}/',
        navigation_rules={
            'article_container': 'dl',  # Papers are in <dt>/<dd> pairs within <dl>
        },
        extraction_rules={
            'title': {
                'selector': 'dt',
                'attribute': 'text',  # Title is in bold within <dt>
            },
            'authors': {
                'selector': 'dd',
                'attribute': 'text',
                'post_process': 'extract_authors_from_dd',  # Extract italic text
            },
            'abstract_url': {
                'selector': 'dd a[href*="html"]',
                'attribute': 'href',
            },
            'pdf_url': {
                'selector': 'dd a[href*=".pdf"]',
                'attribute': 'href',
            },
            'url': {
                'selector': 'dd a[href*="html"]',
                'attribute': 'href',
            },
        },
        pagination_config={
            'type': 'none',  # Single page per volume
        },
        rate_limiting={
            'delay': 2.0,
            'randomize': True,
        },
        headers={
            'User-Agent': 'Thoth/1.0 (Research Paper Discovery)',
        },
    )


def aaai_scrape_config(year: int = 2024) -> ScrapeConfiguration:
    """Create scraper configuration for AAAI proceedings.
    
    AAAI proceedings are hosted on Open Journal Systems (OJS).
    
    Args:
        year: Year of the conference (e.g., 2024).
        
    Returns:
        ScrapeConfiguration for AAAI proceedings.
        
    Example:
        >>> config = aaai_scrape_config(2024)
        >>> scraper = WebScraper(config)
        >>> results = scraper.scrape(max_results=10)
    """
    # AAAI uses OJS, need to find the correct issue URL for the year
    # Example: https://ojs.aaai.org/index.php/AAAI/issue/view/569 (AAAI-24)
    return ScrapeConfiguration(
        base_url=f'https://ojs.aaai.org/index.php/AAAI/issue/archive',
        navigation_rules={
            'article_container': 'div.obj_article_summary',  # OJS article summary divs
        },
        extraction_rules={
            'title': {
                'selector': 'h3.title a',
                'attribute': 'text',
            },
            'authors': {
                'selector': 'div.authors',
                'attribute': 'text',
            },
            'url': {
                'selector': 'h3.title a',
                'attribute': 'href',
            },
            'pdf_url': {
                'selector': 'a.obj_galley_link.pdf',
                'attribute': 'href',
            },
        },
        pagination_config={
            'type': 'link',
            'next_button_selector': 'a.next',
        },
        rate_limiting={
            'delay': 2.5,
            'randomize': True,
        },
        headers={
            'User-Agent': 'Thoth/1.0 (Research Paper Discovery)',
        },
    )


def ijcai_scrape_config(year: int = 2024) -> ScrapeConfiguration:
    """Create scraper configuration for IJCAI proceedings.
    
    Args:
        year: Year of the conference (e.g., 2024).
        
    Returns:
        ScrapeConfiguration for IJCAI proceedings.
        
    Example:
        >>> config = ijcai_scrape_config(2024)
        >>> scraper = WebScraper(config)
        >>> results = scraper.scrape(max_results=10)
    """
    return ScrapeConfiguration(
        base_url=f'https://www.ijcai.org/proceedings/{year}/',
        navigation_rules={
            'article_container': 'div.paper_wrapper',
        },
        extraction_rules={
            'title': {
                'selector': 'div.title',
                'attribute': 'text',
            },
            'authors': {
                'selector': 'div.authors',
                'attribute': 'text',
            },
            'abstract': {
                'selector': 'div.abstract',
                'attribute': 'text',
            },
            'url': {
                'selector': 'a.btn_paper',
                'attribute': 'href',
            },
            'pdf_url': {
                'selector': 'a.btn_paper[href*=".pdf"]',
                'attribute': 'href',
            },
        },
        pagination_config={
            'type': 'none',  # Single page with all papers
        },
        rate_limiting={
            'delay': 2.0,
            'randomize': True,
        },
        headers={
            'User-Agent': 'Thoth/1.0 (Research Paper Discovery)',
        },
    )


def springer_ml_journal_scrape_config(
    journal: str = 'machine-learning',
) -> ScrapeConfiguration:
    """Create scraper configuration for Springer Machine Learning journal.
    
    Args:
        journal: Journal URL slug (default: 'machine-learning').
        
    Returns:
        ScrapeConfiguration for Springer ML journal.
        
    Example:
        >>> config = springer_ml_journal_scrape_config()
        >>> scraper = WebScraper(config)
        >>> results = scraper.scrape(max_results=10)
    """
    return ScrapeConfiguration(
        base_url=f'https://link.springer.com/journal/10994/articles',
        navigation_rules={
            'article_container': 'li.c-list-group__item',
        },
        extraction_rules={
            'title': {
                'selector': 'h3.c-card__title a',
                'attribute': 'text',
            },
            'authors': {
                'selector': 'ul.c-article-author-list li',
                'attribute': 'text',
                'multiple': True,
            },
            'abstract': {
                'selector': 'div.c-card__summary',
                'attribute': 'text',
            },
            'url': {
                'selector': 'h3.c-card__title a',
                'attribute': 'href',
            },
            'doi': {
                'selector': 'h3.c-card__title a',
                'attribute': 'href',
                'post_process': 'extract_doi_from_url',
            },
        },
        pagination_config={
            'type': 'parameter',
            'page_param': 'page',
            'start_page': 1,
        },
        rate_limiting={
            'delay': 3.0,
            'randomize': True,
        },
        headers={
            'User-Agent': 'Thoth/1.0 (Research Paper Discovery)',
        },
    )


# Volume mappings for ICML and other PMLR conferences
PMLR_VOLUME_MAP = {
    'icml': {
        2025: 267,
        2024: 235,
        2023: 202,
        2022: 162,
    },
    'aistats': {
        2024: 238,
        2023: 206,
        2022: 151,
    },
    'corl': {
        2023: 229,
        2022: 205,
        2021: 164,
    },
}


def get_pmlr_volume(conference: str, year: int) -> int | None:
    """Get PMLR volume number for a conference and year.
    
    Args:
        conference: Conference name (e.g., 'icml', 'aistats', 'corl').
        year: Year of the conference.
        
    Returns:
        Volume number or None if not found.
        
    Example:
        >>> volume = get_pmlr_volume('icml', 2024)
        >>> print(volume)  # 235
    """
    conference_lower = conference.lower()
    if conference_lower in PMLR_VOLUME_MAP:
        return PMLR_VOLUME_MAP[conference_lower].get(year)
    return None

"""ICML/PMLR discovery plugin with two-level scraping for complete metadata.

This plugin scrapes PMLR (Proceedings of Machine Learning Research) by:
1. Getting paper listings from the volume page
2. Visiting each individual paper page to extract full metadata

Works for ICML, AISTATS, CoRL, and other conferences hosted on PMLR.
"""

from __future__ import annotations

import time
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from thoth.utilities.schemas import ResearchQuery, ScrapedArticleMetadata

from .base import BaseDiscoveryPlugin


class ICMLPlugin(BaseDiscoveryPlugin):
    """Discovery plugin for ICML and other PMLR-hosted conferences with full metadata extraction."""

    # Volume mappings for major conferences
    VOLUME_MAP = {
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

    def __init__(self, config: dict | None = None) -> None:
        """Initialize the ICML/PMLR plugin.
        
        Args:
            config: Configuration dictionary with optional keys:
                - conference: Conference name ('icml', 'aistats', 'corl')
                - year: Year of conference
                - volume: PMLR volume number (overrides conference/year)
                - rate_limit_delay: Delay between requests in seconds (default: 2.0)
        """
        super().__init__(config)
        
        # Determine volume
        if 'volume' in self.config:
            self.volume = self.config['volume']
        else:
            conference = self.config.get('conference', 'icml').lower()
            year = self.config.get('year', 2024)
            self.volume = self._get_volume(conference, year)
        
        self.rate_limit_delay = self.config.get('rate_limit_delay', 2.0)
        self.last_request_time = 0.0
        
        # Initialize HTTP client
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                'User-Agent': 'Thoth/1.0 (Research Paper Discovery)',
            },
            follow_redirects=True,
        )
    
    def _get_volume(self, conference: str, year: int) -> int:
        """Get PMLR volume number for conference and year.
        
        Args:
            conference: Conference name.
            year: Year.
            
        Returns:
            Volume number.
        """
        if conference in self.VOLUME_MAP:
            volume = self.VOLUME_MAP[conference].get(year)
            if volume:
                return volume
        
        # Default to ICML 2024 if not found
        self.logger.warning(
            f"Volume not found for {conference} {year}, defaulting to ICML 2024 (v235)"
        )
        return 235
    
    def discover(
        self, query: ResearchQuery, max_results: int
    ) -> list[ScrapedArticleMetadata]:
        """Discover papers from PMLR proceedings.
        
        Args:
            query: Research query with keywords and topics.
            max_results: Maximum number of papers to return.
            
        Returns:
            List of discovered papers as ScrapedArticleMetadata.
        """
        keywords = query.keywords or []
        
        self.logger.info(
            f"Searching PMLR v{self.volume}, keywords={keywords}, "
            f"max_results={max_results}"
        )
        
        results: list[ScrapedArticleMetadata] = []
        
        try:
            # Step 1: Get paper listings from volume page
            main_url = f'https://proceedings.mlr.press/v{self.volume}/'
            self._rate_limit()
            response = self.client.get(main_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all paper containers
            paper_containers = soup.find_all('div', class_='paper')
            self.logger.info(f"Found {len(paper_containers)} papers on main page")
            
            # Step 2: Process each paper
            for container in paper_containers[:max_results * 2]:  # Get extra to filter
                try:
                    # Get basic info from listing
                    title_elem = container.find('p', class_='title')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # Filter by keywords if provided
                    if keywords and not self._matches_keywords(title, keywords):
                        continue
                    
                    # Get authors from listing
                    authors_elem = container.find('span', class_='authors')
                    authors = []
                    if authors_elem:
                        authors_text = authors_elem.get_text(strip=True)
                        authors = [a.strip() for a in authors_text.split(',')]
                    
                    # Get abstract link
                    links = container.find('p', class_='links')
                    paper_url = None
                    if links:
                        abs_link = links.find('a', string='abs')
                        if abs_link:
                            paper_url = urljoin(main_url, abs_link.get('href', ''))
                    
                    if not paper_url:
                        continue
                    
                    # Step 3: Visit individual paper page for full metadata
                    self.logger.debug(f"Fetching details for: {title[:50]}...")
                    self._rate_limit()
                    
                    full_metadata = self._get_paper_details(
                        paper_url, title, authors
                    )
                    
                    if full_metadata:
                        results.append(full_metadata)
                    
                    # Stop if we have enough results
                    if len(results) >= max_results:
                        break
                        
                except Exception as e:
                    self.logger.warning(f"Error processing paper: {e}")
                    continue
            
            self.logger.info(f"Found {len(results)} papers from PMLR v{self.volume}")
            return results
            
        except Exception as e:
            self.logger.error(f"PMLR search failed: {e}")
            return []
    
    def _get_paper_details(
        self, url: str, title: str, authors: list[str]
    ) -> ScrapedArticleMetadata | None:
        """Fetch full metadata from individual paper page.
        
        Args:
            url: URL to paper page.
            title: Paper title from listing.
            authors: Authors from listing.
            
        Returns:
            ScrapedArticleMetadata with full details or None.
        """
        try:
            response = self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract abstract
            abstract = None
            abstract_div = soup.find('div', id='abstract')
            if abstract_div:
                abstract = abstract_div.get_text(strip=True)
            
            # Extract metadata from meta tags
            meta_tags = soup.find_all('meta')
            meta_data = {}
            
            for tag in meta_tags:
                name = tag.get('name', '')
                content = tag.get('content', '')
                if name and content:
                    if name == 'citation_author':
                        # Multiple author tags
                        if 'citation_author' not in meta_data:
                            meta_data['citation_author'] = []
                        meta_data['citation_author'].append(content)
                    else:
                        meta_data[name] = content
            
            # Extract PDF URL
            pdf_url = meta_data.get('citation_pdf_url')
            
            # Extract publication date
            pub_date = meta_data.get('citation_publication_date')
            
            # Extract conference/journal name
            journal = meta_data.get('citation_inbook_title')
            
            # Extract page numbers
            first_page = meta_data.get('citation_firstpage')
            last_page = meta_data.get('citation_lastpage')
            
            # Use authors from meta tags if available (more complete)
            if 'citation_author' in meta_data:
                authors = meta_data['citation_author']
            
            # Build additional metadata
            additional_metadata = {
                'pmlr_volume': self.volume,
                'publisher': meta_data.get('citation_publisher', 'PMLR'),
            }
            
            if first_page and last_page:
                additional_metadata['pages'] = f"{first_page}-{last_page}"
            
            return ScrapedArticleMetadata(
                title=title,
                authors=authors,
                abstract=abstract,
                publication_date=pub_date,
                journal=journal or f"PMLR v{self.volume}",
                url=url,
                pdf_url=pdf_url,
                keywords=[],  # PMLR doesn't provide keywords
                source='pmlr',
                scrape_timestamp=datetime.now().isoformat(),
                additional_metadata=additional_metadata,
            )
            
        except Exception as e:
            self.logger.error(f"Error fetching paper details from {url}: {e}")
            return None
    
    def _matches_keywords(self, title: str, keywords: list[str]) -> bool:
        """Check if title matches any of the provided keywords.
        
        Args:
            title: Paper title.
            keywords: List of keywords to match.
            
        Returns:
            True if title matches any keyword, False otherwise.
        """
        title_lower = title.lower()
        for keyword in keywords:
            if keyword.lower() in title_lower:
                return True
        return False
    
    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def validate_config(self, config: dict) -> bool:
        """Validate the configuration.
        
        Args:
            config: Configuration dictionary to validate.
            
        Returns:
            True if valid, False otherwise.
        """
        return True
    
    def get_name(self) -> str:
        """Return the plugin name."""
        return 'icml'

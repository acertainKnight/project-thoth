"""NeurIPS discovery plugin with two-level scraping for complete metadata.

This plugin scrapes NeurIPS proceedings by:
1. Getting paper listings from the main proceedings page
2. Visiting each individual paper page to extract full metadata
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


class NeurIPSPlugin(BaseDiscoveryPlugin):
    """Discovery plugin for NeurIPS conference proceedings with full metadata extraction."""

    def __init__(self, config: dict | None = None) -> None:
        """Initialize the NeurIPS plugin.
        
        Args:
            config: Configuration dictionary with optional keys:
                - year: Year of conference (default: 2024)
                - rate_limit_delay: Delay between requests in seconds (default: 2.0)
        """
        super().__init__(config)
        self.year = self.config.get('year', 2024)
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
    
    def discover(
        self, query: ResearchQuery, max_results: int
    ) -> list[ScrapedArticleMetadata]:
        """Discover papers from NeurIPS proceedings.
        
        Args:
            query: Research query with keywords and topics.
            max_results: Maximum number of papers to return.
            
        Returns:
            List of discovered papers as ScrapedArticleMetadata.
        """
        keywords = query.keywords or []
        
        self.logger.info(
            f"Searching NeurIPS {self.year}, keywords={keywords}, "
            f"max_results={max_results}"
        )
        
        results: list[ScrapedArticleMetadata] = []
        
        try:
            # Step 1: Get paper listings from main page
            main_url = f'https://proceedings.neurips.cc/paper/{self.year}'
            self._rate_limit()
            response = self.client.get(main_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all paper containers
            paper_containers = soup.select('li.conference')
            self.logger.info(f"Found {len(paper_containers)} papers on main page")
            
            # Step 2: Process each paper
            for container in paper_containers[:max_results * 2]:  # Get extra to filter
                try:
                    # Get basic info from listing
                    title_elem = container.select_one('.paper-content a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    paper_url = urljoin(main_url, title_elem.get('href', ''))
                    
                    # Filter by keywords if provided
                    if keywords and not self._matches_keywords(title, keywords):
                        continue
                    
                    # Get authors from listing
                    authors_elem = container.select_one('.paper-authors')
                    authors = []
                    if authors_elem:
                        authors_text = authors_elem.get_text(strip=True)
                        authors = [a.strip() for a in authors_text.split(',')]
                    
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
            
            self.logger.info(f"Found {len(results)} papers from NeurIPS")
            return results
            
        except Exception as e:
            self.logger.error(f"NeurIPS search failed: {e}")
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
            
            # Extract metadata from meta tags
            meta_tags = soup.find_all('meta')
            meta_data = {}
            
            for tag in meta_tags:
                name = tag.get('name', '')
                content = tag.get('content', '')
                if name and content:
                    meta_data[name] = content
            
            # Extract DOI
            doi = meta_data.get('citation_doi')
            
            # Extract PDF URL
            pdf_url = meta_data.get('citation_pdf_url')
            if pdf_url and not pdf_url.startswith('http'):
                pdf_url = urljoin(url, pdf_url)
            
            # Extract journal/volume info
            journal = meta_data.get('citation_journal_title')
            volume = meta_data.get('citation_volume')
            if journal and volume:
                journal = f"{journal} {volume}"
            
            # Extract abstract - look for longest paragraph
            abstract = None
            paragraphs = soup.find_all('p')
            longest_p = None
            max_length = 0
            
            for p in paragraphs:
                text = p.get_text(strip=True)
                # Abstract is typically the longest paragraph (>200 chars)
                if len(text) > max_length and len(text) > 200:
                    max_length = len(text)
                    longest_p = text
            
            if longest_p:
                abstract = longest_p
            
            # Build additional metadata
            additional_metadata = {
                'neurips_year': self.year,
                'pages': f"{meta_data.get('citation_firstpage', '')}-{meta_data.get('citation_lastpage', '')}",
            }
            
            return ScrapedArticleMetadata(
                title=title,
                authors=authors,
                abstract=abstract,
                publication_date=str(self.year),
                journal=journal or f"NeurIPS {self.year}",
                doi=doi,
                url=url,
                pdf_url=pdf_url,
                keywords=[],  # NeurIPS doesn't provide keywords on pages
                source='neurips',
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
        return 'neurips'

"""
ArXiv API resolver for citation resolution.

Provides direct integration with arXiv API for resolving citations to preprints
and published papers available on arXiv.
"""

import re
from typing import List, Optional
from dataclasses import dataclass
import httpx
from loguru import logger

from thoth.utilities.schemas import Citation


@dataclass
class ArxivMatch:
    """
    Represents a match from arXiv API.

    Attributes:
        arxiv_id: ArXiv identifier (e.g., "2103.15348")
        doi: DOI if available
        title: Paper title
        authors: List of author names
        year: Publication year
        abstract: Paper abstract
        pdf_url: URL to PDF
        categories: ArXiv categories (e.g., ["cs.LG", "cs.AI"])
        published: Publication date
        updated: Last update date
    """
    arxiv_id: str
    doi: Optional[str]
    title: str
    authors: List[str]
    year: Optional[int]
    abstract: Optional[str]
    pdf_url: str
    categories: List[str]
    published: str
    updated: str


class ArxivResolver:
    """
    Resolver for arXiv API.

    Searches arXiv for citations and returns structured match data.
    Free API with no authentication required.
    """

    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self, timeout: int = 30):
        """
        Initialize ArXiv resolver.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        logger.info(f"Initialized ArXivResolver with timeout={timeout}s")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def _extract_arxiv_id(self, url: str) -> Optional[str]:
        """
        Extract arXiv ID from URL.

        Args:
            url: ArXiv URL

        Returns:
            ArXiv ID or None
        """
        patterns = [
            r'arxiv\.org/abs/(\d+\.\d+)',
            r'arxiv\.org/pdf/(\d+\.\d+)',
            r'arXiv:(\d+\.\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _parse_entry(self, entry_xml: str) -> Optional[ArxivMatch]:
        """
        Parse arXiv API entry XML to ArxivMatch.

        Args:
            entry_xml: XML entry from arXiv API

        Returns:
            ArxivMatch or None if parsing fails
        """
        try:
            # Extract ID
            id_match = re.search(r'<id>(.*?)</id>', entry_xml)
            if not id_match:
                return None

            arxiv_url = id_match.group(1)
            arxiv_id = self._extract_arxiv_id(arxiv_url)
            if not arxiv_id:
                return None

            # Extract title
            title_match = re.search(r'<title>(.*?)</title>', entry_xml, re.DOTALL)
            title = title_match.group(1).strip().replace('\n', ' ') if title_match else ""

            # Extract authors
            authors = []
            for author_match in re.finditer(r'<author>.*?<name>(.*?)</name>.*?</author>', entry_xml, re.DOTALL):
                authors.append(author_match.group(1).strip())

            # Extract published date
            published_match = re.search(r'<published>(.*?)</published>', entry_xml)
            published = published_match.group(1).strip() if published_match else ""
            year = int(published[:4]) if published else None

            # Extract updated date
            updated_match = re.search(r'<updated>(.*?)</updated>', entry_xml)
            updated = updated_match.group(1).strip() if updated_match else ""

            # Extract abstract
            abstract_match = re.search(r'<summary>(.*?)</summary>', entry_xml, re.DOTALL)
            abstract = abstract_match.group(1).strip().replace('\n', ' ') if abstract_match else None

            # Extract DOI if available
            doi = None
            doi_match = re.search(r'<arxiv:doi.*?>(.*?)</arxiv:doi>', entry_xml)
            if doi_match:
                doi = doi_match.group(1).strip()

            # Extract categories
            categories = []
            for cat_match in re.finditer(r'<category term="(.*?)"', entry_xml):
                categories.append(cat_match.group(1))

            # Build PDF URL
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            return ArxivMatch(
                arxiv_id=arxiv_id,
                doi=doi,
                title=title,
                authors=authors,
                year=year,
                abstract=abstract,
                pdf_url=pdf_url,
                categories=categories,
                published=published,
                updated=updated,
            )

        except Exception as e:
            logger.error(f"Error parsing arXiv entry: {e}")
            return None

    async def resolve_citation(self, citation: Citation) -> List[ArxivMatch]:
        """
        Resolve citation using arXiv API.

        Args:
            citation: Citation to resolve

        Returns:
            List of ArxivMatch objects
        """
        if not citation.title:
            logger.debug("No title provided, cannot search arXiv")
            return []

        try:
            # Build search query
            # Use title as primary search field
            title_query = f'ti:"{citation.title}"'

            # Add author to query if available
            if citation.authors and len(citation.authors) > 0:
                first_author = citation.authors[0]
                # Extract last name (assumes "First Last" format)
                author_parts = first_author.split()
                if author_parts:
                    last_name = author_parts[-1]
                    title_query += f' AND au:"{last_name}"'

            params = {
                'search_query': title_query,
                'start': 0,
                'max_results': 5,
                'sortBy': 'relevance',
                'sortOrder': 'descending',
            }

            logger.debug(f"Searching arXiv with query: {title_query}")

            response = await self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()

            # Parse XML response
            xml_content = response.text

            # Split by entry tags
            entries = re.findall(r'<entry>(.*?)</entry>', xml_content, re.DOTALL)

            if not entries:
                logger.debug(f"No arXiv results found for: {citation.title}")
                return []

            matches = []
            for entry_xml in entries:
                match = self._parse_entry(f"<entry>{entry_xml}</entry>")
                if match:
                    matches.append(match)

            logger.info(f"Found {len(matches)} arXiv matches for: {citation.title[:50]}...")
            return matches

        except httpx.HTTPError as e:
            logger.error(f"HTTP error querying arXiv: {e}")
            return []
        except Exception as e:
            logger.error(f"Error resolving citation via arXiv: {e}")
            return []

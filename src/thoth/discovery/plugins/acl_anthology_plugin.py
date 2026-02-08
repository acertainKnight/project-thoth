"""ACL Anthology discovery plugin for NLP research papers.

This plugin uses the acl-anthology Python package to access papers from
ACL, EMNLP, NAACL, CoNLL, and 50+ other NLP conferences and journals.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from thoth.utilities.schemas import ResearchQuery, ScrapedArticleMetadata

from .base import BaseDiscoveryPlugin


class ACLAnthologyPlugin(BaseDiscoveryPlugin):
    """Discovery plugin for ACL Anthology.

    Requires acl-anthology package: pip install acl-anthology
    """

    def __init__(self, config: dict | None = None) -> None:
        """Initialize the ACL Anthology plugin.

        Args:
            config: Configuration dictionary with optional keys:
                - venues: List of venue codes to search (e.g., ['acl', 'emnlp', 'naacl'])
                - years: List of years to search (e.g., [2024, 2023])
                - anthology_dir: Path to anthology XML data (auto-downloads if not set)
        """
        super().__init__(config)

        try:
            from anthology import Anthology

            self.anthology_cls = Anthology

            # Initialize anthology (downloads data if needed)
            anthology_dir = self.config.get('anthology_dir')
            if anthology_dir:
                self.anthology = Anthology(importdir=Path(anthology_dir))
            else:
                # Will auto-download to default location
                self.anthology = Anthology()

        except ImportError as e:
            raise ImportError(
                'acl-anthology is required for ACL Anthology plugin. '
                'Install with: pip install acl-anthology'
            ) from e
        except Exception as e:
            self.logger.warning(
                f'Could not initialize ACL Anthology: {e}. '
                'Will attempt lazy initialization.'
            )
            self.anthology = None

    def discover(
        self, query: ResearchQuery, max_results: int
    ) -> list[ScrapedArticleMetadata]:
        """Discover papers from ACL Anthology.

        Args:
            query: Research query with keywords and topics.
            max_results: Maximum number of papers to return.

        Returns:
            List of discovered papers as ScrapedArticleMetadata.
        """
        if not self.anthology:
            self.logger.error('ACL Anthology not initialized')
            return []

        venues = self.config.get('venues', ['acl', 'emnlp', 'naacl', 'eacl'])
        years = self.config.get('years', [])
        keywords = query.keywords or []

        self.logger.info(
            f'Searching ACL Anthology: venues={venues}, years={years}, '
            f'keywords={keywords}, max_results={max_results}'
        )

        results: list[ScrapedArticleMetadata] = []

        try:
            # Iterate through all papers in the anthology
            for paper_id, paper in self.anthology.papers.items():
                try:
                    # Filter by venue if specified
                    if venues:
                        venue_from_id = self._extract_venue_from_id(paper_id)
                        if venue_from_id not in venues:
                            continue

                    # Filter by year if specified
                    if years:
                        year_from_id = self._extract_year_from_id(paper_id)
                        if year_from_id and int(year_from_id) not in years:
                            continue

                    # Filter by keywords if provided
                    if keywords and not self._matches_keywords(paper, keywords):
                        continue

                    # Convert to metadata
                    metadata = self._paper_to_metadata(paper)
                    if metadata:
                        results.append(metadata)

                    # Stop if we have enough results
                    if len(results) >= max_results:
                        break

                except Exception as e:
                    self.logger.debug(f'Error processing ACL paper {paper_id}: {e}')
                    continue

            self.logger.info(f'Found {len(results)} papers from ACL Anthology')
            return results

        except Exception as e:
            self.logger.error(f'ACL Anthology search failed: {e}')
            return []

    def _extract_venue_from_id(self, paper_id: str) -> str:
        """Extract venue code from paper ID.

        Args:
            paper_id: Paper ID like 'P19-1234' or '2023.acl-long.123'.

        Returns:
            Venue code (e.g., 'acl', 'emnlp').
        """
        try:
            # Modern format: 2023.acl-long.123
            if '.' in paper_id:
                parts = paper_id.split('.')
                if len(parts) >= 2:
                    venue_part = parts[1]
                    # Extract venue before track suffix (e.g., 'acl-long' -> 'acl')
                    return venue_part.split('-')[0].lower()

            # Legacy format: P19-1234 (P=ACL, D=EMNLP, N=NAACL, etc.)
            if paper_id and len(paper_id) > 0:
                prefix = paper_id[0].upper()
                legacy_map = {
                    'P': 'acl',
                    'D': 'emnlp',
                    'N': 'naacl',
                    'E': 'eacl',
                    'W': 'ws',
                    'C': 'coling',
                }
                return legacy_map.get(prefix, paper_id[0].lower())
        except Exception:
            pass

        return ''

    def _extract_year_from_id(self, paper_id: str) -> str | None:
        """Extract year from paper ID.

        Args:
            paper_id: Paper ID like 'P19-1234' or '2023.acl-long.123'.

        Returns:
            Year as string (e.g., '2023') or None.
        """
        try:
            # Modern format: 2023.acl-long.123
            if paper_id and paper_id[0].isdigit():
                year = paper_id.split('.')[0]
                if year.isdigit() and len(year) == 4:
                    return year

            # Legacy format: P19-1234
            if len(paper_id) >= 3 and paper_id[1:3].isdigit():
                year_short = paper_id[1:3]
                # Convert to full year (assume 2000s for now)
                full_year = (
                    f'20{year_short}' if int(year_short) < 50 else f'19{year_short}'
                )
                return full_year
        except Exception:
            pass

        return None

    def _matches_keywords(self, paper, keywords: list[str]) -> bool:
        """Check if paper matches any of the provided keywords.

        Args:
            paper: ACL Anthology paper object.
            keywords: List of keywords to match.

        Returns:
            True if paper matches any keyword, False otherwise.
        """
        try:
            title = paper.get_title('text').lower()
            abstract = paper.get_abstract('text', '').lower()

            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in title or keyword_lower in abstract:
                    return True

            return False
        except Exception:
            return False

    def _paper_to_metadata(self, paper) -> ScrapedArticleMetadata | None:
        """Convert ACL Anthology paper to ScrapedArticleMetadata.

        Args:
            paper: ACL Anthology paper object.

        Returns:
            ScrapedArticleMetadata or None if conversion fails.
        """
        try:
            # Extract title
            title = paper.get_title('text')
            if not title:
                return None

            # Extract authors
            authors = []
            for author in paper.get_authors():
                name = author.get_full_name()
                if name:
                    authors.append(name)

            # Extract abstract
            abstract = paper.get_abstract('text', None)

            # Extract publication year
            year = paper.get_year()
            pub_date = str(year) if year else None

            # Extract venue
            venue_name = paper.get_venue()

            # Extract DOI
            doi = paper.get_doi()

            # Extract URLs
            paper_url = paper.get_url()
            pdf_url = paper.get_pdf_url()

            # Extract paper ID
            paper_id = paper.full_id

            # Build additional metadata
            additional_metadata = {
                'acl_id': paper_id,
                'venue_full': venue_name,
            }

            # Try to extract citation count if available
            try:
                if hasattr(paper, 'citation_count'):
                    additional_metadata['citation_count'] = paper.citation_count
            except Exception:
                pass

            return ScrapedArticleMetadata(
                title=title,
                authors=authors,
                abstract=abstract,
                publication_date=pub_date,
                journal=venue_name,
                doi=doi,
                url=paper_url,
                pdf_url=pdf_url,
                keywords=[],  # ACL Anthology doesn't provide keywords
                source='acl_anthology',
                scrape_timestamp=datetime.now().isoformat(),
                additional_metadata=additional_metadata,
            )

        except Exception as e:
            self.logger.error(f'Error converting ACL Anthology paper: {e}')
            return None

    def validate_config(self, config: dict) -> bool:
        """Validate the configuration.

        Args:
            config: Configuration dictionary to validate.

        Returns:
            True if valid, False otherwise.
        """
        # No required fields
        return True

    def get_name(self) -> str:
        """Return the plugin name."""
        return 'acl_anthology'

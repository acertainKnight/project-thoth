"""ACL Anthology discovery plugin for NLP research papers.

Uses the acl-anthology v1.0+ Python package to access papers from
ACL, EMNLP, NAACL, CoNLL, and 50+ other NLP conferences and journals.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from thoth.utilities.schemas import ResearchQuery, ScrapedArticleMetadata

from .base import BaseDiscoveryPlugin


class ACLAnthologyPlugin(BaseDiscoveryPlugin):
    """Discovery plugin for ACL Anthology.

    Requires acl-anthology package: pip install acl-anthology
    The first run clones the ACL Anthology git repo (~2GB) and caches it locally.
    """

    def __init__(self, config: dict | None = None) -> None:
        """Initialize the ACL Anthology plugin.

        Args:
            config: Configuration dictionary with optional keys:
                - venues: Venue codes to search (e.g. acl, emnlp, naacl)
                - years: Years to search (e.g. 2024, 2023)
                - data_dir: Path to cached anthology repo (auto-clones if not set)
        """
        super().__init__(config)
        self.anthology = None

        try:
            from acl_anthology import Anthology

            self._anthology_cls = Anthology

            data_dir = self.config.get('data_dir') or self.config.get('anthology_dir')
            if data_dir and Path(data_dir).exists():
                self.anthology = Anthology(datadir=Path(data_dir))
            else:
                # Clone the ACL Anthology repo. Cached after first run if
                # the container volume persists.
                default_cache = Path(tempfile.gettempdir()) / 'acl-anthology-data'
                cache_path = Path(self.config.get('data_dir', default_cache))
                self.anthology = Anthology.from_repo(path=cache_path)

        except ImportError as e:
            raise ImportError(
                'acl-anthology is required for ACL Anthology plugin. '
                'Install with: pip install acl-anthology'
            ) from e
        except Exception as e:
            self.logger.warning(
                f'Could not initialize ACL Anthology: {e}. '
                'Will attempt lazy initialization on first query.'
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
            for paper in self.anthology.papers():
                try:
                    paper_id = str(paper.full_id)

                    if venues:
                        venue_from_id = self._extract_venue_from_id(paper_id)
                        if venue_from_id not in venues:
                            continue

                    if years:
                        year_from_id = self._extract_year_from_id(paper_id)
                        if year_from_id and int(year_from_id) not in years:
                            continue

                    if keywords and not self._matches_keywords(paper, keywords):
                        continue

                    metadata = self._paper_to_metadata(paper)
                    if metadata:
                        results.append(metadata)

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
            if paper_id and paper_id[0].isdigit():
                year = paper_id.split('.')[0]
                if year.isdigit() and len(year) == 4:
                    return year

            if len(paper_id) >= 3 and paper_id[1:3].isdigit():
                year_short = paper_id[1:3]
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
            paper: acl_anthology Paper object.
            keywords: List of keywords to match.

        Returns:
            True if paper matches any keyword, False otherwise.
        """
        try:
            title = ''
            if paper.title:
                title = paper.title.as_text().lower()

            abstract = ''
            if paper.abstract:
                abstract = paper.abstract.as_text().lower()

            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in title or keyword_lower in abstract:
                    return True

            return False
        except Exception:
            return False

    def _paper_to_metadata(self, paper) -> ScrapedArticleMetadata | None:
        """Convert acl_anthology Paper to ScrapedArticleMetadata.

        Args:
            paper: acl_anthology Paper object.

        Returns:
            ScrapedArticleMetadata or None if conversion fails.
        """
        try:
            title = paper.title.as_text() if paper.title else None
            if not title:
                return None

            # Authors are NameSpecification objects with first/last attributes
            authors = []
            if paper.authors:
                for author_spec in paper.authors:
                    name = f'{author_spec.first or ""} {author_spec.last or ""}'.strip()
                    if name:
                        authors.append(name)

            abstract = None
            if paper.abstract:
                abstract = paper.abstract.as_text()

            year = paper.year
            pub_date = str(year) if year else None

            doi = paper.doi if paper.doi else None

            paper_url = None
            try:
                paper_url = paper.web_url
            except Exception:
                pass

            pdf_url = None
            if paper.pdf:
                try:
                    pdf_url = paper.pdf.url
                except Exception:
                    pass

            paper_id = str(paper.full_id)
            venue_name = None
            if paper.venue_ids:
                venue_name = ', '.join(str(v) for v in paper.venue_ids)

            additional_metadata = {
                'acl_id': paper_id,
            }
            if venue_name:
                additional_metadata['venue_full'] = venue_name

            return ScrapedArticleMetadata(
                title=title,
                authors=authors,
                abstract=abstract,
                publication_date=pub_date,
                journal=venue_name,
                doi=doi,
                url=paper_url,
                pdf_url=pdf_url,
                keywords=[],
                source='acl_anthology',
                scrape_timestamp=datetime.now().isoformat(),
                additional_metadata=additional_metadata,
            )

        except Exception as e:
            self.logger.error(f'Error converting ACL Anthology paper: {e}')
            return None

    def validate_config(self, _config: dict) -> bool:
        """Validate the configuration.

        Args:
            _config: Configuration dictionary to validate.

        Returns:
            True if valid, False otherwise.
        """
        return True

    def get_name(self) -> str:
        """Return the plugin name."""
        return 'acl_anthology'

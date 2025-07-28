from __future__ import annotations

from datetime import datetime

from thoth.utilities.schemas import ResearchQuery, ScrapedArticleMetadata

from ..api_sources import ArxivClient
from .base import BaseDiscoveryPlugin


class ArxivPlugin(BaseDiscoveryPlugin):
    """Discovery plugin for searching arXiv."""

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        rate_limit = self.config.get('rate_limit_delay', 3.0)
        self.client = ArxivClient(delay_seconds=rate_limit)

    def discover(
        self, query: ResearchQuery, max_results: int
    ) -> list[ScrapedArticleMetadata]:
        """Discover articles on arXiv for the given query."""
        keywords = query.keywords or []
        categories = self.config.get('categories', [])
        sort_by = self.config.get('sort_by', 'lastUpdatedDate')
        sort_order = self.config.get('sort_order', 'descending')

        query_parts = []
        if categories:
            cat_queries = [f'cat:{c}' for c in categories]
            query_parts.append('(' + ' OR '.join(cat_queries) + ')')
        if keywords:
            kw_queries = [f'(ti:"{k}" OR abs:"{k}")' for k in keywords]
            query_parts.append('(' + ' OR '.join(kw_queries) + ')')
        search_query = ' AND '.join(query_parts) if query_parts else 'cat:cs.*'

        papers = self.client.search(
            search_query,
            start=0,
            max_results=min(max_results, 1000),
            sort_by=sort_by,
            sort_order=sort_order,
        )

        results: list[ScrapedArticleMetadata] = []
        for paper in papers:
            metadata = ScrapedArticleMetadata(
                title=paper.title,
                authors=paper.authors,
                abstract=paper.abstract,
                publication_date=paper.published,
                journal='arXiv',
                doi=paper.doi,
                arxiv_id=paper.id,
                url=f'https://arxiv.org/abs/{paper.id}',
                pdf_url=paper.pdf_url,
                keywords=paper.categories,
                source='arxiv',
                scrape_timestamp=datetime.now().isoformat(),
                additional_metadata={
                    'categories': paper.categories,
                    'updated': paper.updated,
                    'comment': paper.comment,
                    'journal_ref': paper.journal_ref,
                    'citation_count': paper.citation_count,
                },
            )
            results.append(metadata)
        return results

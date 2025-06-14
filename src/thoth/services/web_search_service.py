"""Service for performing general web searches."""

from __future__ import annotations

from typing import Any

from thoth.services.base import BaseService, ServiceError
from thoth.utilities.schemas import SearchResult
from thoth.utilities.web_search import (
    DuckDuckGoClient,
    ScrapeSearchClient,
    SerperClient,
)


class WebSearchService(BaseService):
    """Service wrapping search clients for agent use."""

    def __init__(self, config=None):
        super().__init__(config)
        self._clients: dict[str, Any] = {}

    def _get_client(self, provider: str):
        if provider in self._clients:
            return self._clients[provider]

        if provider == 'serper':
            api_key = self.config.api_keys.web_search_key
            if not api_key:
                raise ServiceError(
                    'Web search API key is not configured. Set API_WEB_SEARCH_KEY.'
                )
            client = SerperClient(api_key=api_key)
        elif provider == 'duckduckgo':
            client = DuckDuckGoClient()
        elif provider == 'scrape':
            client = ScrapeSearchClient()
        else:
            raise ServiceError(f"Unknown web search provider '{provider}'")

        self._clients[provider] = client
        return client

    def initialize(self) -> None:
        self.logger.info('Web search service initialized')

    def search(
        self, query: str, num_results: int = 5, provider: str | None = None
    ) -> list[SearchResult]:
        """Perform a web search."""
        try:
            self.validate_input(query=query)

            providers = (
                provider if provider else None
            ) or self.config.api_keys.web_search_providers

            if isinstance(providers, str):
                providers = [p.strip() for p in providers.split(',') if p]

            for prov in providers or ['serper']:
                try:
                    client = self._get_client(prov)
                except ServiceError as e:
                    self.logger.warning(f'Provider {prov} unavailable: {e}')
                    continue
                try:
                    results = client.search(query, num_results)
                    if results:
                        self.log_operation(
                            'web_search',
                            query=query,
                            provider=prov,
                            results=len(results),
                        )
                        return results
                except Exception as e:
                    self.logger.warning(f'Provider {prov} failed: {e}')

            raise ServiceError('No available web search providers')
        except Exception as e:
            raise ServiceError(self.handle_error(e, 'web searching')) from e

    def health_check(self) -> dict[str, str]:
        """Basic health status for the WebSearchService."""
        return super().health_check()

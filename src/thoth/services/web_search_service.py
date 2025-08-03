"""Service for performing general web searches."""

from __future__ import annotations

from thoth.services.base import BaseService, ClientManagerMixin, ServiceError
from thoth.utilities.schemas import SearchResult
from thoth.utilities.web_search import (
    DuckDuckGoClient,
    ScrapeSearchClient,
    SerperClient,
)


class WebSearchService(ClientManagerMixin, BaseService):
    """Service wrapping search clients for agent use."""

    def __init__(self, config=None):
        super().__init__(config)

    def _create_client(self, provider: str):
        """Factory function to create clients."""
        if provider == 'serper':
            api_key = self.config.api_keys.web_search_key
            if not api_key:
                raise ServiceError(
                    'Web search API key is not configured. Set API_WEB_SEARCH_KEY.'
                )
            return SerperClient(api_key=api_key)
        elif provider == 'duckduckgo':
            return DuckDuckGoClient()
        elif provider == 'scrape':
            return ScrapeSearchClient()
        else:
            raise ServiceError(f"Unknown web search provider '{provider}'")

    def _get_client(self, provider: str):
        """Get or create client for provider."""
        return self.get_or_create_client(
            provider, lambda: self._create_client(provider)
        )

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

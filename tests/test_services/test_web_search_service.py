import pytest

from thoth.services.web_search_service import WebSearchService, ServiceError
from thoth.utilities.config import ThothConfig
from thoth.utilities.models import SearchResult


def test_missing_api_key(monkeypatch):
    config = ThothConfig()
    config.api_keys.web_search_key = None
    config.api_keys.web_search_providers = ["serper"]
    service = WebSearchService(config=config)
    with pytest.raises(ServiceError):
        service.search("test")


def test_fallback_to_duckduckgo(monkeypatch):
    config = ThothConfig()
    config.api_keys.web_search_key = None
    config.api_keys.web_search_providers = ["serper", "duckduckgo"]

    service = WebSearchService(config=config)

    def mock_search(self, query, num_results):
        return [SearchResult(title="t", link="u", snippet="s", position=1)]

    monkeypatch.setattr(
        "thoth.utilities.web_search.DuckDuckGoClient.search", mock_search
    )

    results = service.search("test")
    assert len(results) == 1


def test_invalid_provider():
    config = ThothConfig()
    config.api_keys.web_search_providers = ["bad"]
    service = WebSearchService(config=config)
    with pytest.raises(ServiceError):
        service.search("test")

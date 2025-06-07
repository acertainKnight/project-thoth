"""Web search clients for multiple providers."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from thoth.utilities.models import SearchResult


class SerperClient:
    """Client for performing web searches via the Serper.dev API."""

    def __init__(self, api_key: str, base_url: str = "https://google.serper.dev"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=10)

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        """Perform a web search and return results."""
        try:
            response = self.client.post(
                f"{self.base_url}/search",
                headers={"X-API-KEY": self.api_key},
                json={"q": query, "num": num_results},
            )
            response.raise_for_status()
            data = response.json()
            results: list[SearchResult] = []
            for i, item in enumerate(data.get("organic", [])[:num_results]):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        link=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        position=i + 1,
                    )
                )
            return results
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []

    def close(self) -> None:
        self.client.close()


class DuckDuckGoClient:
    """Client for performing searches via DuckDuckGo."""

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results: list[SearchResult] = []
                for i, r in enumerate(ddgs.text(query, max_results=num_results)):
                    results.append(
                        SearchResult(
                            title=r.get("title", ""),
                            link=r.get("href", ""),
                            snippet=r.get("body", ""),
                            position=i + 1,
                        )
                    )
                return results
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return []


class ScrapeSearchClient:
    """Fallback client that scrapes DuckDuckGo HTML results."""

    def __init__(self, base_url: str = "https://duckduckgo.com/html/"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=10)

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        try:
            resp = self.client.get(self.base_url, params={"q": query})
            resp.raise_for_status()
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")
            results: list[SearchResult] = []
            for i, res in enumerate(soup.select("div.result")[:num_results]):
                link_el = res.select_one("a.result__a")
                snippet_el = res.select_one("a.result__snippet")
                results.append(
                    SearchResult(
                        title=link_el.text if link_el else "",
                        link=link_el["href"] if link_el else "",
                        snippet=snippet_el.text if snippet_el else "",
                        position=i + 1,
                    )
                )
            return results
        except Exception as e:
            logger.error(f"Scrape search failed: {e}")
            return []

    def close(self) -> None:
        self.client.close()

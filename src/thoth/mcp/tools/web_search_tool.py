"""
MCP-compliant web search tool.

This module provides comprehensive web search functionality using multiple
backends including DuckDuckGo, SearXNG, and Brave Search API with fallback support.
"""

from datetime import datetime
from typing import Any

from loguru import logger

from ..base_tools import MCPTool, MCPToolCallResult


class WebSearchMCPTool(MCPTool):
    """
    MCP tool for searching the web using multiple search backends.

    **DEPRECATED**: This tool is deprecated. Use Letta's built-in `web_search`
    tool instead, which provides better integration with the agent framework.
    This tool is no longer registered in the MCP tool registry.
    """

    @property
    def name(self) -> str:
        # Renamed to avoid conflict with Letta's built-in web_search
        return 'thoth_web_search'

    @property
    def description(self) -> str:
        return 'Search the web using multiple search engines and return structured results with titles, URLs, snippets, and relevance scores'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'Search query to find on the web',
                },
                'max_results': {
                    'type': 'integer',
                    'description': 'Maximum number of search results to return',
                    'default': 10,
                    'minimum': 1,
                    'maximum': 50,
                },
                'search_engine': {
                    'type': 'string',
                    'enum': ['auto', 'duckduckgo', 'searxng', 'brave'],
                    'description': 'Preferred search engine (auto tries multiple with fallback)',
                    'default': 'auto',
                },
                'safe_search': {
                    'type': 'string',
                    'enum': ['on', 'moderate', 'off'],
                    'description': 'Safe search filter level',
                    'default': 'moderate',
                },
                'region': {
                    'type': 'string',
                    'description': "Search region/country code (e.g. 'us', 'uk', 'de')",
                    'default': 'us',
                },
                'time_range': {
                    'type': 'string',
                    'enum': ['any', 'day', 'week', 'month', 'year'],
                    'description': 'Time range for search results',
                    'default': 'any',
                },
            },
            'required': ['query'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute web search."""
        try:
            query = arguments['query']
            max_results = arguments.get('max_results', 10)
            search_engine = arguments.get('search_engine', 'auto')
            safe_search = arguments.get('safe_search', 'moderate')
            region = arguments.get('region', 'us')
            time_range = arguments.get('time_range', 'any')

            response_text = '**Web Search Results**\n\n'
            response_text += f'**Query:** {query}\n'
            response_text += f'**Max Results:** {max_results}\n'
            response_text += f'**Search Engine:** {search_engine}\n\n'

            # Perform search with selected or automatic backend
            search_results = await self._perform_search(
                query=query,
                max_results=max_results,
                search_engine=search_engine,
                safe_search=safe_search,
                region=region,
                time_range=time_range,
            )

            if not search_results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'{response_text}**No Results Found**\n\n'
                            f'Try:\n'
                            f'- Different search terms\n'
                            f'- Broader query\n'
                            f'- Different search engine\n'
                            f'- Check internet connectivity',
                        }
                    ],
                    isError=True,
                )

            # Display results
            response_text += f'**Found {len(search_results)} Results**\n'
            response_text += (
                f'**Search Backend:** {search_results[0].get("backend", "Unknown")}\n'
            )
            response_text += (
                f'**Search Time:** {search_results[0].get("search_time", "N/A")}\n\n'
            )

            response_text += '---\n\n'

            # Format search results
            for i, result in enumerate(search_results, 1):
                title = result.get('title', 'Untitled')
                url = result.get('url', '')
                snippet = result.get('snippet', 'No description available')
                relevance_score = result.get('relevance_score', 0.0)

                response_text += f'## {i}. {title}\n\n'
                response_text += f'**URL:** {url}\n'

                if relevance_score > 0:
                    response_text += f'**Relevance:** {relevance_score:.3f}\n'

                response_text += f'**Description:** {snippet}\n\n'
                response_text += '---\n\n'

            # Add search tips
            response_text += '**Search Tips:**\n'
            response_text += '- Use quotes for exact phrases: `"machine learning"`\n'
            response_text += '- Use - to exclude terms: `python -snake`\n'
            response_text += (
                '- Use site: to search specific sites: `site:arxiv.org quantum`\n'
            )
            response_text += '- Try different search engines for varied results\n\n'

            response_text += '**Next Steps:**\n'
            response_text += '- Click URLs to visit pages\n'
            response_text += '- Use `download_pdf` if PDFs are found\n'
            response_text += '- Use `process_pdf` to add content to knowledge base'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)

    async def _perform_search(
        self,
        query: str,
        max_results: int,
        search_engine: str,
        safe_search: str,
        region: str,
        time_range: str,
    ) -> list[dict[str, Any]]:
        """Perform search using selected backend with fallback support."""

        search_start_time = datetime.now()

        # Define search order based on preference
        if search_engine == 'auto':
            search_order = ['duckduckgo', 'searxng', 'brave']
        else:
            search_order = [search_engine]

        last_error = None

        for backend in search_order:
            try:
                if backend == 'duckduckgo':
                    results = await self._search_duckduckgo(
                        query, max_results, safe_search, region, time_range
                    )
                elif backend == 'searxng':
                    results = await self._search_searxng(
                        query, max_results, safe_search, region, time_range
                    )
                elif backend == 'brave':
                    results = await self._search_brave(
                        query, max_results, safe_search, region, time_range
                    )
                else:
                    continue

                if results:
                    # Add metadata to results
                    search_time = (datetime.now() - search_start_time).total_seconds()
                    for result in results:
                        result['backend'] = backend
                        result['search_time'] = f'{search_time:.3f}s'

                    return results

            except Exception as e:
                last_error = e
                logger.warning(f'Search backend {backend} failed: {e!s}')
                continue

        # If all backends failed, raise the last error
        if last_error:
            raise last_error

        return []

    async def _search_duckduckgo(
        self,
        query: str,
        max_results: int,
        safe_search: str,
        region: str,
        time_range: str,
    ) -> list[dict[str, Any]]:
        """Search using DuckDuckGo Search library."""
        try:
            from duckduckgo_search import DDGS

            # Map safe search settings
            safesearch_map = {'on': 'strict', 'moderate': 'moderate', 'off': 'off'}

            # Map time range settings
            timelimit_map = {
                'any': None,
                'day': 'd',
                'week': 'w',
                'month': 'm',
                'year': 'y',
            }

            # Perform search
            ddgs = DDGS()
            ddgs_results = ddgs.text(
                keywords=query,
                region=region,
                safesearch=safesearch_map.get(safe_search, 'moderate'),
                timelimit=timelimit_map.get(time_range),
                max_results=max_results,
            )

            # Convert to standard format
            results = []
            for i, result in enumerate(ddgs_results):
                results.append(
                    {
                        'title': result.get('title', ''),
                        'url': result.get('href', ''),
                        'snippet': result.get('body', ''),
                        'relevance_score': 1.0 - (i * 0.1),  # Simple relevance scoring
                    }
                )

            return results

        except ImportError as e:
            raise Exception(
                'DuckDuckGo Search library not installed. Run: pip install duckduckgo-search'
            ) from e
        except Exception as e:
            raise Exception(f'DuckDuckGo search failed: {e!s}') from e

    async def _search_searxng(
        self,
        query: str,
        max_results: int,
        safe_search: str,
        region: str,
        time_range: str,
    ) -> list[dict[str, Any]]:
        """Search using SearXNG instance."""
        try:
            import aiohttp

            # Default to localhost SearXNG instance
            searxng_url = 'http://localhost:8888'

            # Map safe search settings
            safesearch_map = {'on': '2', 'moderate': '1', 'off': '0'}

            # Prepare search parameters
            params = {
                'q': query,
                'format': 'json',
                'safesearch': safesearch_map.get(safe_search, '1'),
                'pageno': '1',
                'language': region,
                'time_range': time_range if time_range != 'any' else None,
            }

            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'{searxng_url}/search', params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        results = []
                        search_results = data.get('results', [])[:max_results]

                        for i, result in enumerate(search_results):
                            results.append(
                                {
                                    'title': result.get('title', ''),
                                    'url': result.get('url', ''),
                                    'snippet': result.get('content', ''),
                                    'relevance_score': 1.0 - (i * 0.1),
                                }
                            )

                        return results
                    else:
                        raise Exception(f'SearXNG returned status {response.status}')

        except ImportError as e:
            raise Exception(
                'aiohttp library required for SearXNG. Run: pip install aiohttp'
            ) from e
        except Exception as e:
            raise Exception(
                f'SearXNG search failed: {e!s}. Is SearXNG running on localhost:8888?'
            ) from e

    async def _search_brave(
        self,
        query: str,
        max_results: int,
        safe_search: str,
        region: str,
        time_range: str,
    ) -> list[dict[str, Any]]:
        """Search using Brave Search API."""
        try:
            import os

            import aiohttp

            # Get API key from environment
            api_key = os.getenv('BRAVE_SEARCH_API_KEY')
            if not api_key:
                raise Exception('BRAVE_SEARCH_API_KEY environment variable not set')

            # Map safe search settings
            safesearch_map = {'on': 'strict', 'moderate': 'moderate', 'off': 'off'}

            # Map time range settings
            freshness_map = {
                'any': None,
                'day': 'pd',
                'week': 'pw',
                'month': 'pm',
                'year': 'py',
            }

            # Prepare search parameters
            params = {
                'q': query,
                'count': min(max_results, 20),  # Brave API limit
                'safesearch': safesearch_map.get(safe_search, 'moderate'),
                'country': region.upper(),
                'freshness': freshness_map.get(time_range),
            }

            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}

            headers = {
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip',
                'X-Subscription-Token': api_key,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://api.search.brave.com/res/v1/web/search',
                    params=params,
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        results = []
                        web_results = data.get('web', {}).get('results', [])

                        for i, result in enumerate(web_results):
                            results.append(
                                {
                                    'title': result.get('title', ''),
                                    'url': result.get('url', ''),
                                    'snippet': result.get('description', ''),
                                    'relevance_score': 1.0
                                    - (i * 0.05),  # Better scoring for Brave
                                }
                            )

                        return results
                    else:
                        raise Exception(f'Brave API returned status {response.status}')

        except ImportError as e:
            raise Exception(
                'aiohttp library required for Brave Search. Run: pip install aiohttp'
            ) from e
        except Exception as e:
            raise Exception(f'Brave Search failed: {e!s}') from e

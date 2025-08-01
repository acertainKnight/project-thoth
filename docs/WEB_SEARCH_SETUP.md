# Web Search Tool Setup Guide

The new WebSearchMCPTool provides comprehensive web search capabilities with multiple backend options and intelligent fallback support.

## Quick Start (No Setup Required)

The easiest way to get started is with DuckDuckGo search, which requires no API keys or configuration:

```bash
pip install duckduckgo-search
```

The tool will automatically use DuckDuckGo as the default search backend.

## Available Search Backends

### 1. DuckDuckGo (Recommended for beginners)
- **Cost**: Free
- **Setup**: `pip install duckduckgo-search`
- **Pros**: No API keys, instant setup, good privacy
- **Cons**: Rate limiting, web scraping approach

### 2. SearXNG (Recommended for privacy & control)
- **Cost**: Free (self-hosted)
- **Setup**: Deploy SearXNG instance
- **Pros**: Aggregates 70+ engines, complete privacy, no rate limits
- **Cons**: Requires server setup

#### SearXNG Docker Setup:
```bash
docker run -d --name searxng -p 8888:8080 searxng/searxng
```

### 3. Brave Search API (Recommended for production)
- **Cost**: 2,000 free queries/month, then $3 per 1,000 queries
- **Setup**: Get API key from https://api.search.brave.com/
- **Pros**: Independent index, fast, reliable
- **Cons**: Paid after free tier

#### Brave API Setup:
```bash
export BRAVE_SEARCH_API_KEY="your_api_key_here"
```

## Required Dependencies

Install the core requirements:

```bash
# For DuckDuckGo (required)
pip install duckduckgo-search

# For SearXNG and Brave (optional)
pip install aiohttp
```

## Usage Examples

### Basic Search
```python
# Uses automatic backend selection (DuckDuckGo → SearXNG → Brave)
await web_search_tool.execute({
    "query": "machine learning papers 2024",
    "max_results": 10
})
```

### Specific Search Engine
```python
# Force specific backend
await web_search_tool.execute({
    "query": "quantum computing",
    "max_results": 15,
    "search_engine": "duckduckgo",
    "safe_search": "moderate",
    "region": "us"
})
```

### Advanced Options
```python
await web_search_tool.execute({
    "query": "artificial intelligence research",
    "max_results": 20,
    "search_engine": "auto",
    "safe_search": "on",
    "region": "uk",
    "time_range": "month"
})
```

## Search Features

### Intelligent Fallback
The tool automatically tries multiple backends in order of preference:
1. Your specified engine (if set)
2. DuckDuckGo (default, no setup)
3. SearXNG (if running on localhost:8888)
4. Brave (if API key is set)

### Structured Results
Each search returns:
- **Title**: Page title
- **URL**: Direct link
- **Snippet**: Content preview
- **Relevance Score**: 0.0-1.0 relevance rating
- **Backend**: Which search engine was used
- **Search Time**: Query execution time

### Search Options
- **Safe Search**: `on`, `moderate`, `off`
- **Region**: Country codes (`us`, `uk`, `de`, etc.)
- **Time Range**: `any`, `day`, `week`, `month`, `year`
- **Max Results**: 1-50 results per query

## Integration with Thoth

The web search tool seamlessly integrates with other Thoth tools:

1. **Search → Download**: Find PDFs and use `download_pdf` tool
2. **Search → Process**: Use `process_pdf` to add content to knowledge base
3. **Search → Citation**: Use `extract_citations` for academic papers
4. **Search → Export**: Include web results in research exports

## Troubleshooting

### DuckDuckGo Issues
```bash
# Update to latest version
pip install --upgrade duckduckgo-search

# If rate limited, try:
# - Adding delays between requests
# - Using VPN or proxy
# - Switch to SearXNG
```

### SearXNG Issues
```bash
# Check if SearXNG is running
curl http://localhost:8888/

# Start SearXNG container
docker start searxng
```

### Brave API Issues
```bash
# Verify API key is set
echo $BRAVE_SEARCH_API_KEY

# Check quota usage at: https://api.search.brave.com/app/dashboard
```

## Performance Tips

1. **Start Simple**: Begin with DuckDuckGo, add other backends as needed
2. **Use Caching**: Results are automatically cached during sessions
3. **Batch Queries**: Make multiple searches efficiently
4. **Monitor Usage**: Track API quotas for paid services
5. **Optimize Queries**: Use specific terms for better results

## Security & Privacy

- **DuckDuckGo**: No tracking, but queries go through DDG servers
- **SearXNG**: Complete privacy when self-hosted
- **Brave**: Privacy-focused, but requires API account

Choose the backend that best fits your privacy and performance requirements.

## Advanced Configuration

For power users, you can customize the search backends by modifying the `WebSearchMCPTool` class:

- Add new search engines
- Modify fallback order
- Customize result scoring
- Add result filtering
- Implement caching strategies

The tool is designed to be extensible and can easily accommodate additional search providers.

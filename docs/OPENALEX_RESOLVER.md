# OpenAlex Resolver

## Overview

The OpenAlexResolver is an async citation matching and enrichment tool that uses the OpenAlex API to resolve citations with high-quality fuzzy matching. OpenAlex provides better matching capabilities than Crossref and comprehensive metadata for academic papers.

## Features

- **Async HTTP Requests**: Uses `httpx` for high-performance async I/O
- **Rate Limiting**: Configurable rate limiting (default: 10 req/sec)
- **Polite Pool Access**: Email-based authentication for 10x higher rate limits
- **Smart Query Construction**: Title-based search with year filtering (±1 year)
- **Confidence Scoring**: Multi-factor match scoring based on title, year, and author similarity
- **Error Handling**: Exponential backoff with configurable retries
- **Batch Processing**: Parallel resolution of multiple citations with rate limit respect
- **Rich Metadata**: Extracts DOI, authors, abstract, citation counts, and open access PDFs

## Architecture

### Classes

#### `MatchCandidate`
Represents a potential match for a citation from OpenAlex.

**Fields:**
- `openalex_id`: OpenAlex ID (e.g., W1234567890)
- `doi`: DOI of the matched paper
- `title`: Title of the matched paper
- `authors`: List of author names
- `year`: Publication year
- `venue`: Publication venue/journal
- `abstract`: Paper abstract (reconstructed from inverted index)
- `citation_count`: Number of citations
- `confidence_score`: Match confidence score (0-1)
- `url`: OpenAlex URL
- `pdf_url`: Open access PDF URL
- `is_open_access`: Open access status
- `fields_of_study`: Academic fields

**Methods:**
- `to_citation()`: Convert match candidate to Citation object

#### `OpenAlexResolver`
Main resolver class for async citation matching.

**Constructor Parameters:**
- `email`: Email for polite pool (gets 10x higher rate limit) - **Recommended**
- `requests_per_second`: Rate limit for API requests (default: 10.0)
- `max_retries`: Maximum number of retry attempts (default: 3)
- `timeout`: Request timeout in seconds (default: 30)
- `backoff_factor`: Exponential backoff multiplier (default: 2.0)
- `max_backoff`: Maximum backoff time in seconds (default: 60.0)

**Methods:**
- `resolve_citation(citation)`: Resolve a single citation to match candidates
- `batch_resolve(citations)`: Resolve multiple citations in parallel
- `get_statistics()`: Get resolver statistics

## Usage

### Basic Single Citation Resolution

```python
import asyncio
from thoth.analyze.citations.openalex_resolver import OpenAlexResolver
from thoth.utilities.schemas import Citation

async def resolve_single():
    # Initialize resolver with email for polite pool
    resolver = OpenAlexResolver(
        email='your-email@example.com',
        requests_per_second=10.0
    )

    # Create citation
    citation = Citation(
        title='Attention Is All You Need',
        authors=['Vaswani', 'Shazeer', 'Parmar'],
        year=2017,
    )

    # Resolve
    candidates = await resolver.resolve_citation(citation)

    # Use best match
    if candidates:
        best_match = candidates[0]
        print(f'Best match: {best_match.title}')
        print(f'Confidence: {best_match.confidence_score:.2f}')
        print(f'DOI: {best_match.doi}')

        # Convert to Citation object
        enriched = best_match.to_citation()

asyncio.run(resolve_single())
```

### Batch Resolution

```python
async def batch_resolve():
    resolver = OpenAlexResolver(email='your-email@example.com')

    citations = [
        Citation(title='BERT: Pre-training of Deep Bidirectional Transformers', year=2019),
        Citation(title='Deep Residual Learning for Image Recognition', year=2016),
        Citation(title='ImageNet Classification with Deep CNNs', year=2012),
    ]

    # Batch resolve with automatic rate limiting
    results = await resolver.batch_resolve(citations)

    for citation, candidates in results.items():
        if candidates:
            print(f'{citation.title}: {candidates[0].confidence_score:.2f}')

asyncio.run(batch_resolve())
```

### Integration with Citation Enhancer

```python
from thoth.analyze.citations.enhancer import CitationEnhancer
from thoth.analyze.citations.openalex_resolver import OpenAlexResolver

class EnhancedCitationEnhancer(CitationEnhancer):
    """Citation enhancer with OpenAlex resolution."""

    def __init__(self, config):
        super().__init__(config)
        self.openalex_resolver = OpenAlexResolver(
            email=config.api_keys.openalex_email,
            requests_per_second=10.0
        )

    async def enhance_with_openalex(self, citations: list[Citation]) -> list[Citation]:
        """Enhance citations using OpenAlex resolver."""
        results = await self.openalex_resolver.batch_resolve(citations)

        for citation, candidates in results.items():
            if candidates and candidates[0].confidence_score > 0.7:
                # Use high-confidence matches
                match = candidates[0]
                if not citation.doi and match.doi:
                    citation.doi = match.doi
                if not citation.abstract and match.abstract:
                    citation.abstract = match.abstract
                # Update other fields...

        return citations
```

## Query Construction

The resolver builds OpenAlex queries using the following strategy:

1. **Title Search**: Uses `title.search:` filter for fuzzy matching
2. **Year Filtering**: Adds `publication_year:` filter with ±1 year range
3. **Field Selection**: Requests specific fields to minimize response size

Example query:
```
filter=title.search:attention+is+all+you+need,publication_year:2016-2018
&per-page=5
&select=id,doi,title,display_name,authorships,publication_year,...
```

## Confidence Scoring

Match confidence is calculated using multiple factors:

### Scoring Weights

1. **DOI Match** (1.0): If DOIs match, confidence is 1.0 (definitive)
2. **Title Similarity** (0.5): Jaccard similarity of title words
3. **Year Match** (0.2):
   - Exact match: +0.2
   - ±1 year: +0.1
4. **Author Overlap** (0.3): Overlap of author last names

### Example Scores

| Match Type | Title Sim | Year Match | Author Overlap | Score |
|------------|-----------|------------|----------------|-------|
| Perfect    | 1.0       | Exact      | 100%           | 1.0   |
| Very Good  | 0.9       | Exact      | 80%            | 0.89  |
| Good       | 0.8       | ±1 year    | 50%            | 0.65  |
| Fair       | 0.6       | Exact      | 0%             | 0.50  |
| Poor       | 0.4       | Different  | 0%             | 0.20  |

## Rate Limiting

### Standard vs Polite Pool

| Pool     | Rate Limit      | Authentication |
|----------|-----------------|----------------|
| Standard | 10 req/sec      | None           |
| Polite   | 100 req/sec     | Email required |

**Recommendation**: Always provide an email to access the polite pool.

### Implementation

Rate limiting is enforced using:
1. **Async Lock**: Thread-safe rate limit tracking
2. **Minimum Interval**: Calculated from `requests_per_second`
3. **Automatic Backoff**: Exponential backoff on rate limit errors (429)

```python
# Rate limit is automatically enforced
async with self._rate_lock:
    time_since_last = current_time - self._last_request_time
    if time_since_last < self._min_interval:
        await asyncio.sleep(self._min_interval - time_since_last)
    self._last_request_time = time.monotonic()
```

## Error Handling

### Retry Strategy

The resolver implements exponential backoff with retries:

1. **HTTP Status Errors**:
   - 429 (Rate Limit): Respect `Retry-After` header or use backoff
   - 5xx (Server Error): Retry with exponential backoff
   - 4xx (Client Error): No retry (likely bad request)

2. **Network Errors**: Retry with exponential backoff

3. **Backoff Calculation**:
   ```python
   backoff = min(backoff_factor ** attempt, max_backoff)
   ```

### Example Error Handling

```python
try:
    candidates = await resolver.resolve_citation(citation)
    if not candidates:
        logger.warning(f'No matches found for: {citation.title}')
except Exception as e:
    logger.error(f'Error resolving citation: {e}')
    # Fallback to other resolvers...
```

## Response Parsing

### OpenAlex Work Format

OpenAlex returns works in this format:
```json
{
  "id": "https://openalex.org/W2741809807",
  "doi": "https://doi.org/10.18653/v1/d19-1410",
  "display_name": "BERT: Pre-training of Deep Bidirectional Transformers",
  "authorships": [
    {"author": {"display_name": "Jacob Devlin"}}
  ],
  "publication_year": 2019,
  "cited_by_count": 45678,
  "open_access": {
    "is_oa": true,
    "oa_url": "https://arxiv.org/pdf/1810.04805"
  },
  "abstract_inverted_index": {
    "We": [0], "introduce": [1], ...
  }
}
```

### Abstract Reconstruction

Abstracts are stored as inverted indexes for efficiency. The resolver reconstructs them:

```python
def _reconstruct_abstract(self, inverted_index: dict[str, list[int]]) -> str:
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort(key=lambda x: x[0])
    return ' '.join(word for _, word in word_positions)
```

## Statistics

Track resolver performance:

```python
stats = resolver.get_statistics()
print(stats)
# {
#     'requests_made': 42,
#     'matches_found': 38,
#     'rate_limit_hits': 2,
#     'requests_per_second': 10.0
# }
```

## Performance Tips

1. **Use Polite Pool**: Provide email for 10x higher rate limits
2. **Batch Resolution**: Use `batch_resolve()` for multiple citations
3. **Adjust Rate Limit**: Increase if using API key or decrease if hitting limits
4. **Cache Results**: Consider caching OpenAlex responses (not built-in)
5. **Filter Low Confidence**: Only use matches with score > 0.7

## Comparison with Other Resolvers

| Feature              | OpenAlex    | Semantic Scholar | Crossref    |
|----------------------|-------------|------------------|-------------|
| Fuzzy Matching       | ★★★★★       | ★★★★☆            | ★★★☆☆       |
| Metadata Coverage    | ★★★★★       | ★★★★☆            | ★★★★☆       |
| Rate Limit (Free)    | 10 req/sec  | Variable         | 50 req/sec  |
| Rate Limit (Polite)  | 100 req/sec | N/A              | N/A         |
| Open Access PDFs     | ★★★★★       | ★★★★☆            | ★★☆☆☆       |
| Abstract Quality     | ★★★★☆       | ★★★★★            | ★★☆☆☆       |
| Citation Counts      | ★★★★★       | ★★★★★            | ★★★☆☆       |

**Recommendation**: Use OpenAlex as primary resolver, fallback to Semantic Scholar for abstracts and citations.

## API Reference

### OpenAlex API Documentation

- Base URL: `https://api.openalex.org`
- Documentation: https://docs.openalex.org/
- Works endpoint: `/works`
- Filters: https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/filter-entity-lists

### Key Filters

- `title.search:query` - Fuzzy title search
- `publication_year:2020-2022` - Year range filter
- `doi:10.1234/xyz` - DOI lookup
- `authorships.author.id:A1234` - Author filter

### Key Fields

- `id` - OpenAlex ID
- `doi` - Digital Object Identifier
- `title` / `display_name` - Paper title
- `authorships` - Author information
- `publication_year` - Year published
- `cited_by_count` - Citation count
- `open_access` - OA status and PDF URL
- `abstract_inverted_index` - Abstract (inverted)
- `topics` - Fields of study

## Examples

See `examples/openalex_resolver_example.py` for complete working examples.

## Testing

```python
import pytest
from thoth.analyze.citations.openalex_resolver import OpenAlexResolver, MatchCandidate
from thoth.utilities.schemas import Citation

@pytest.mark.asyncio
async def test_resolve_citation():
    resolver = OpenAlexResolver()
    citation = Citation(
        title='Attention Is All You Need',
        year=2017
    )

    candidates = await resolver.resolve_citation(citation)

    assert len(candidates) > 0
    assert candidates[0].confidence_score > 0.8
    assert candidates[0].doi is not None

@pytest.mark.asyncio
async def test_batch_resolve():
    resolver = OpenAlexResolver()
    citations = [
        Citation(title='BERT Pre-training', year=2019),
        Citation(title='ResNet', year=2016),
    ]

    results = await resolver.batch_resolve(citations)

    assert len(results) == 2
    for citation, candidates in results.items():
        assert len(candidates) > 0
```

## Future Enhancements

1. **Persistent Caching**: Add SQLite cache like Semantic Scholar
2. **Author Disambiguation**: Use OpenAlex author IDs for better matching
3. **Concept Matching**: Match by OpenAlex concepts/topics
4. **Bulk Export**: Use OpenAlex bulk data exports for offline processing
5. **Graph Features**: Leverage citation network data
6. **Works Filters**: Add more sophisticated filtering options

## License

This module is part of the Thoth project and follows the project's license.

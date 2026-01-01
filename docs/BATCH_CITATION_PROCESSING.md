# Batch Citation Processing Guide

This guide covers the usage of the `BatchCitationProcessor` for large-scale citation resolution operations.

## Overview

The `BatchCitationProcessor` provides efficient processing of large citation datasets (1000s-100,000s of citations) with features including:

- **Chunked Processing**: Process citations in manageable batches
- **Parallel Execution**: Configure concurrency for optimal throughput
- **Rate Limiting**: Respect API rate limits (Crossref: 50/s, OpenAlex: 10/s, S2: 100/s)
- **Checkpointing**: Save progress and resume from interruptions
- **Progress Tracking**: Comprehensive statistics and logging
- **Caching**: Avoid duplicate API calls for efficiency

## Quick Start

### Basic Usage

```python
import asyncio
from pathlib import Path
from thoth.analyze.citations.batch_processor import (
    BatchCitationProcessor,
    BatchConfig
)
from thoth.utilities.schemas import Citation

# Create configuration
config = BatchConfig(
    chunk_size=100,          # Process 100 citations per chunk
    max_concurrent=10,       # 10 concurrent API requests
    checkpoint_interval=500, # Save checkpoint every 500 citations
    checkpoint_path=Path("checkpoints/citations.json"),
    enable_caching=True
)

# Initialize processor
processor = BatchCitationProcessor(config, resolver=your_resolver)

# Load citations
citations = [
    Citation(title="Paper 1", authors=["Author A"], year=2024),
    Citation(title="Paper 2", authors=["Author B"], year=2023),
    # ... more citations
]

# Process batch
async def main():
    results = await processor.process_batch(citations)

    # Access statistics
    stats = processor.get_statistics()
    print(f"Success rate: {stats.successful_resolutions / stats.total_citations * 100:.1f}%")
    print(f"Processing time: {stats.processing_time_seconds:.2f}s")

    return results

# Run
results = asyncio.run(main())
```

## Configuration Options

### BatchConfig Parameters

```python
@dataclass
class BatchConfig:
    # Core settings
    chunk_size: int = 100              # Citations per chunk (100-500 recommended)
    max_concurrent: int = 10           # Concurrent requests (10-20 recommended)

    # Checkpointing
    checkpoint_interval: int = 500     # Save every N citations (0 = disabled)
    checkpoint_path: Path | None       # Where to save checkpoints

    # Performance
    enable_caching: bool = True        # Enable in-memory caching
    timeout_seconds: float = 30.0      # Timeout per citation
    retry_attempts: int = 3            # Retry failed resolutions
    retry_delay_seconds: float = 1.0   # Delay between retries

    # Rate limits (requests per second)
    rate_limits: dict = {
        'crossref': 50.0,              # Crossref: 50/s
        'openalex': 10.0,              # OpenAlex: 10/s
        'semantic_scholar': 100.0,      # Semantic Scholar: 100/s
        'arxiv': 3.0,                  # arXiv: 3/s
    }
```

### Recommended Configurations

#### Small Batch (< 1,000 citations)
```python
config = BatchConfig(
    chunk_size=50,
    max_concurrent=5,
    checkpoint_interval=0,  # Disable checkpointing
    enable_caching=True
)
```

#### Medium Batch (1,000 - 10,000 citations)
```python
config = BatchConfig(
    chunk_size=100,
    max_concurrent=10,
    checkpoint_interval=500,
    checkpoint_path=Path("checkpoints/medium_batch.json"),
    enable_caching=True
)
```

#### Large Batch (10,000+ citations)
```python
config = BatchConfig(
    chunk_size=500,
    max_concurrent=20,
    checkpoint_interval=1000,
    checkpoint_path=Path("checkpoints/large_batch.json"),
    enable_caching=True,
    timeout_seconds=60.0,
    retry_attempts=5
)
```

## Checkpoint and Resume

### Automatic Checkpointing

Checkpoints are automatically saved at configured intervals:

```python
config = BatchConfig(
    checkpoint_interval=500,  # Save every 500 citations
    checkpoint_path=Path("checkpoints/my_batch.json")
)

processor = BatchCitationProcessor(config)
results = await processor.process_batch(citations)  # Auto-saves checkpoints
```

### Manual Checkpoint Management

```python
# Save checkpoint manually
processor.save_checkpoint(results, Path("manual_checkpoint.json"))

# Load checkpoint
loaded_results = processor.load_checkpoint(Path("manual_checkpoint.json"))
```

### Resume from Interruption

The processor automatically resumes from existing checkpoints:

```python
# First run (interrupted after 500 citations)
config = BatchConfig(checkpoint_path=Path("checkpoint.json"))
processor = BatchCitationProcessor(config)
results = await processor.process_batch(citations)  # Processes 500, then crashes

# Second run (resumes from checkpoint)
processor2 = BatchCitationProcessor(config)
results = await processor2.process_batch(citations)  # Resumes from citation 501
```

## Statistics and Progress Tracking

### Accessing Statistics

```python
# During processing
stats = processor.get_statistics()

print(f"Processed: {stats.processed_citations}/{stats.total_citations}")
print(f"Success rate: {stats.successful_resolutions / stats.processed_citations * 100:.1f}%")
print(f"Cache hit rate: {stats.cache_hits / stats.processed_citations * 100:.1f}%")

# After processing
stats.finalize()
stats_dict = stats.to_dict()

# Available metrics
print(f"Total citations: {stats_dict['total_citations']}")
print(f"Successful: {stats_dict['successful_resolutions']}")
print(f"Failed: {stats_dict['failed_resolutions']}")
print(f"Processing time: {stats_dict['processing_time_seconds']:.2f}s")
print(f"Avg per citation: {stats_dict['average_time_per_citation']:.3f}s")
print(f"API calls: {stats_dict['api_calls']}")
```

### Progress Logging

The processor automatically logs progress every chunk:

```
2025-12-29 10:30:00 | INFO | Starting batch processing of 10000 citations
2025-12-29 10:30:00 | INFO | Config: chunk_size=100, max_concurrent=10
2025-12-29 10:30:05 | INFO | Processing chunk 0-100 (100 citations)
2025-12-29 10:30:12 | INFO | Progress: 100/10000 (1.0%) - Success: 95, Failed: 5, Cache hits: 0
2025-12-29 10:30:17 | INFO | Processing chunk 100-200 (100 citations)
2025-12-29 10:30:24 | INFO | Progress: 200/10000 (2.0%) - Success: 190, Failed: 10, Cache hits: 5
...
2025-12-29 11:15:30 | INFO | Checkpoint saved: 5000 results
...
2025-12-29 12:00:00 | INFO | Batch Processing Complete - Final Statistics
2025-12-29 12:00:00 | INFO | Success rate: 94.5%, Processing time: 5400.0s
```

## Rate Limiting

### Built-in Rate Limiters

The processor includes token bucket rate limiters for each API:

```python
# Default rate limits (requests per second)
rate_limits = {
    'crossref': 50.0,       # Crossref API
    'openalex': 10.0,       # OpenAlex API
    'semantic_scholar': 100.0,  # Semantic Scholar API
    'arxiv': 3.0,           # arXiv API
}
```

### Custom Rate Limits

```python
# Adjust for your API keys/quota
custom_limits = {
    'crossref': 100.0,      # Plus subscription: 100/s
    'openalex': 10.0,       # Standard: 10/s
    'semantic_scholar': 100.0,  # Standard: 100/s
    'custom_api': 25.0      # Your custom API
}

config = BatchConfig(rate_limits=custom_limits)
```

### Rate Limiter Behavior

- **Burst Capacity**: Allows initial burst of requests up to rate limit
- **Token Refill**: Continuously refills tokens based on rate
- **Blocking**: Automatically blocks when rate limit reached
- **Per-API**: Independent rate limiting for each API source

## Caching

### In-Memory Cache

The processor maintains an in-memory cache to avoid duplicate API calls:

```python
config = BatchConfig(enable_caching=True)
processor = BatchCitationProcessor(config)

# First resolution: API call made
result1 = await processor._resolve_single_citation(citation, semaphore)

# Second resolution: Cache hit (no API call)
result2 = await processor._resolve_single_citation(citation, semaphore)

# Cache statistics
print(f"Cache size: {processor.get_cache_size()}")
print(f"Cache hits: {processor.statistics.cache_hits}")

# Clear cache if needed
processor.clear_cache()
```

### Cache Key Generation

Citations are cached based on:
- Title (normalized)
- First author (normalized)
- Publication year

This ensures identical citations use the same cache entry while avoiding false matches.

## Error Handling

### Retry Logic

Failed resolutions are automatically retried:

```python
config = BatchConfig(
    retry_attempts=3,         # Try up to 3 times
    retry_delay_seconds=1.0   # Wait 1s between retries
)
```

### Timeout Handling

Individual resolutions timeout after configured duration:

```python
config = BatchConfig(timeout_seconds=30.0)  # 30 second timeout per citation
```

### Error Statistics

Track error patterns:

```python
stats = processor.get_statistics()

# Top errors
for error_msg, count in stats.errors_by_type.items():
    print(f"{error_msg}: {count} occurrences")
```

## Performance Optimization

### Throughput Tuning

Optimize for your infrastructure:

```python
# High throughput (requires good network + API quotas)
config = BatchConfig(
    chunk_size=500,
    max_concurrent=20,
    rate_limits={'crossref': 100.0, 'openalex': 20.0}
)

# Conservative (reliable, lower rate)
config = BatchConfig(
    chunk_size=50,
    max_concurrent=5,
    rate_limits={'crossref': 20.0, 'openalex': 5.0}
)
```

### Memory Management

For very large batches (100,000+ citations):

```python
# Process in smaller sub-batches
chunk_size = 10000
for i in range(0, len(citations), chunk_size):
    batch = citations[i:i+chunk_size]

    config = BatchConfig(
        checkpoint_path=Path(f"checkpoints/batch_{i}.json")
    )

    processor = BatchCitationProcessor(config)
    results = await processor.process_batch(batch)

    # Save results incrementally
    save_results(results, f"results_{i}.json")

    # Clear cache to free memory
    processor.clear_cache()
```

## Integration Examples

### With Citation Resolver

```python
from thoth.analyze.citations.batch_processor import BatchCitationProcessor, BatchConfig
from thoth.analyze.citations.crossref_resolver import CrossrefResolver

# Initialize resolver
resolver = CrossrefResolver(api_key="your_key")

# Create processor with resolver
config = BatchConfig(max_concurrent=10)
processor = BatchCitationProcessor(config, resolver=resolver)

# Process citations
results = await processor.process_batch(citations)
```

### With Progress Bar (tqdm)

If tqdm is installed, progress bars are automatically enabled:

```bash
pip install tqdm
```

```python
# Progress bars will automatically appear
results = await processor.process_batch(citations)

# Output:
# Chunk 1: 100%|██████████| 100/100 [00:15<00:00,  6.67cit/s]
# Chunk 2: 100%|██████████| 100/100 [00:14<00:00,  7.14cit/s]
```

### With Custom Resolver

```python
class CustomResolver:
    async def resolve(self, citation: Citation) -> ResolutionResult:
        # Your custom resolution logic
        return ResolutionResult(...)

resolver = CustomResolver()
processor = BatchCitationProcessor(config, resolver=resolver)
```

## Checkpoint File Format

Checkpoint files are JSON with the following structure:

```json
{
  "timestamp": "2025-12-29T10:30:00Z",
  "count": 500,
  "results": [
    {
      "citation": "Author et al. (2024). Paper title.",
      "status": "resolved",
      "confidence_score": 0.95,
      "confidence_level": "high",
      "source": "crossref",
      "matched_data": {...},
      "metadata": {...}
    }
  ],
  "statistics": {
    "total_citations": 10000,
    "processed_citations": 500,
    "successful_resolutions": 475,
    "failed_resolutions": 25,
    "cache_hits": 50,
    "processing_time_seconds": 120.5,
    "api_calls": {
      "crossref": 450,
      "openalex": 50
    }
  }
}
```

## Best Practices

1. **Start Conservative**: Begin with lower concurrency and smaller chunks, then optimize
2. **Use Checkpointing**: Always enable for batches > 1,000 citations
3. **Monitor Rate Limits**: Check API documentation and adjust accordingly
4. **Enable Caching**: Reduces duplicate calls for similar citations
5. **Handle Interruptions**: Design workflows to resume from checkpoints
6. **Track Statistics**: Monitor success rates and adjust strategy
7. **Clear Cache Periodically**: For very long-running operations
8. **Respect API Terms**: Follow rate limits and terms of service

## Troubleshooting

### Slow Processing

```python
# Increase concurrency
config = BatchConfig(max_concurrent=20)

# Increase chunk size
config = BatchConfig(chunk_size=500)

# Check rate limits aren't too conservative
config = BatchConfig(rate_limits={'crossref': 100.0})
```

### High Failure Rate

```python
# Increase timeout
config = BatchConfig(timeout_seconds=60.0)

# More retry attempts
config = BatchConfig(retry_attempts=5, retry_delay_seconds=2.0)

# Check error statistics
stats = processor.get_statistics()
print(stats.errors_by_type)
```

### Memory Issues

```python
# Reduce chunk size
config = BatchConfig(chunk_size=50)

# Process in sub-batches and clear cache
processor.clear_cache()

# Disable caching if necessary
config = BatchConfig(enable_caching=False)
```

## API Reference

See the module docstrings for complete API documentation:

- `BatchCitationProcessor`: Main processor class
- `BatchConfig`: Configuration dataclass
- `BatchStatistics`: Statistics tracking
- `RateLimiter`: Token bucket rate limiter

## Examples

See `examples/batch_citation_processing.py` for complete working examples.

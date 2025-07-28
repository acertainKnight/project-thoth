# CLI Performance Integration Guide

This guide explains how to use the integrated performance optimizations through the Thoth CLI and monitor system.

## Installation

### Core Installation
The base Thoth installation provides standard functionality:
```bash
pip install -e .
```

### Performance Optimization Installation
For enhanced performance features, install the optional dependencies:
```bash
pip install -r requirements-performance.txt
```

This enables:
- Async I/O processing with `aiohttp` and `aiofiles`
- System monitoring with `psutil`
- Enhanced caching and parallel processing

## CLI Commands

### Performance Commands
New `performance` command group provides optimization tools:

```bash
# Show system information and performance configuration
thoth performance info

# Run optimized batch processing
thoth performance batch --input-file pdfs_to_process.json --async

# Run performance benchmark
thoth performance benchmark

# Manage cache
thoth performance cache --clear all
```

### Enhanced Monitor
The monitor now supports optimized processing:

```bash
# Standard monitor
thoth monitor --watch-dir /path/to/pdfs

# Optimized monitor (with performance enhancements)
thoth monitor --watch-dir /path/to/pdfs --optimized
```

### Enhanced System Commands
All system commands now support performance optimizations when available.

## Detailed Usage Examples

### 1. Performance Information
Get system and configuration details:

```bash
$ thoth performance info

🖥️  SYSTEM INFORMATION
==================================================
CPU:
   Cores: 8
   Usage: 15.2%

Memory:
   Total: 16.0 GB
   Available: 12.3 GB
   Usage: 23.1%

Performance Configuration:
   Auto Scale Workers: True
   Content Analysis Workers: 7
   Citation Enhancement Workers: 7
   Citation Extraction Workers: 7
   OCR Max Concurrent: 3
   Async Enabled: True
   OCR Caching: True
   Memory Optimization: True
```

### 2. Optimized Batch Processing
Process multiple PDFs with performance optimizations:

```bash
# Async batch processing (recommended)
$ thoth performance batch --input-file pdfs_to_process.json --async --max-files 10

Processing 10 PDFs with optimizations
🚀 Starting optimized async processing of 10 PDFs
Batch 1 completed: 3/3 successful in 45.2s (4.0 files/min)
Batch 2 completed: 3/3 successful in 42.1s (4.3 files/min)
...

🚀 OPTIMIZED BATCH PROCESSING COMPLETE
==========================================================
📊 Total PDFs: 10
✅ Successful: 10
❌ Failed: 0
📈 Success Rate: 100.0%
⏱️  Total Time: 280.5 seconds
⚡ Average Time per PDF: 28.1 seconds
🏃 Processing Rate: 2.1 files/minute

🔧 Performance Configuration:
   CPU Cores: 8
   Max Workers: {'content_analysis': 7, 'citation_extraction': 7, ...}
   Async Enabled: True
```

### 3. Performance Benchmark
Compare standard vs optimized processing:

```bash
$ thoth performance benchmark

Running benchmark with 5 PDFs
🐌 Running standard processing benchmark...
🚀 Running optimized processing benchmark...

📊 PERFORMANCE BENCHMARK RESULTS
==========================================================
📝 Test Files: 5 PDFs

🐌 Standard Processing:
   Total Time: 450.2 seconds
   Average per PDF: 90.0 seconds
   Successful: 5/5

🚀 Optimized Processing:
   Total Time: 187.3 seconds
   Average per PDF: 37.5 seconds
   Successful: 5/5

📈 Performance Improvement:
   Speed Improvement: 58.3% faster
   Speedup Factor: 2.4x
   Time Saved per PDF: 52.5 seconds
```

### 4. Cache Management
Monitor and manage performance caches:

```bash
$ thoth performance cache

💾 CACHE STATISTICS
==================================================
Memory Cache:
   Size: 15 items
   Limit: 100 items

Disk Cache:
   Total Files: 127
   Total Size: 2.3 MB

Cache by Type:
   Ocr: 45 files (1.8 MB)
   Analysis: 32 files (0.3 MB)
   Citations: 28 files (0.1 MB)
   Api_responses: 22 files (0.1 MB)

# Clear specific cache
$ thoth performance cache --clear ocr
✅ Cleared ocr cache

# Clear all caches
$ thoth performance cache --clear all
✅ Cleared all caches
```

### 5. Optimized Monitor
Run monitor with performance enhancements:

```bash
# Standard monitor
$ thoth monitor --watch-dir /home/user/pdfs
Monitor using standard processing pipeline

# Optimized monitor
$ thoth monitor --watch-dir /home/user/pdfs --optimized
Initializing optimized pipeline for monitor
✅ Monitor using optimized processing pipeline
Starting PDF monitor with polling interval 1.0s (recursive: False)
```

## Configuration Options

### Environment Variables
Configure performance settings via environment variables:

```bash
# Auto-scaling
export PERFORMANCE_AUTO_SCALE_WORKERS=true
export PERFORMANCE_CPU_UTILIZATION_TARGET=0.8

# Worker counts (optional overrides)
export PERFORMANCE_CONTENT_ANALYSIS_WORKERS=6
export PERFORMANCE_CITATION_ENHANCEMENT_WORKERS=8

# OCR settings
export PERFORMANCE_OCR_ENABLE_CACHING=true
export PERFORMANCE_OCR_CACHE_TTL_HOURS=24

# Async settings
export PERFORMANCE_ASYNC_ENABLED=true
export PERFORMANCE_ASYNC_TIMEOUT_SECONDS=300

# Memory management
export PERFORMANCE_MEMORY_OPTIMIZATION_ENABLED=true
export PERFORMANCE_MAX_DOCUMENT_SIZE_MB=50
```

### Configuration File
Add to your `.env` file:

```bash
# Performance optimizations
PERFORMANCE_AUTO_SCALE_WORKERS=true
PERFORMANCE_ASYNC_ENABLED=true
PERFORMANCE_OCR_ENABLE_CACHING=true
PERFORMANCE_MEMORY_OPTIMIZATION_ENABLED=true

# Custom worker counts (optional)
PERFORMANCE_CONTENT_ANALYSIS_WORKERS=4
PERFORMANCE_CITATION_ENHANCEMENT_WORKERS=6
```

## Integration Examples

### 1. Scripted Batch Processing
Create automated processing scripts:

```bash
#!/bin/bash
# automated_processing.sh

echo "Starting automated PDF processing..."

# Check system resources
thoth performance info

# Run optimized batch processing
thoth performance batch \
  --input-file /data/pdfs_to_process.json \
  --async \
  --max-files 50

# Show cache stats
thoth performance cache

echo "Processing complete!"
```

### 2. Monitor Integration
Set up continuous monitoring with optimizations:

```bash
#!/bin/bash
# start_optimized_monitor.sh

# Set performance configuration
export PERFORMANCE_AUTO_SCALE_WORKERS=true
export PERFORMANCE_ASYNC_ENABLED=true
export PERFORMANCE_OCR_ENABLE_CACHING=true

# Start optimized monitor
thoth monitor \
  --watch-dir /home/user/research/pdfs \
  --optimized \
  --recursive \
  --api-server \
  --api-host 0.0.0.0 \
  --api-port 8080
```

### 3. Development Workflow
Use performance tools during development:

```bash
# Test new optimizations
thoth performance benchmark --files test1.pdf test2.pdf test3.pdf

# Monitor cache effectiveness
thoth performance cache

# Clear cache for clean testing
thoth performance cache --clear all

# Process test files with optimizations
thoth performance batch --pdf-dir /test/pdfs --async
```

## Backward Compatibility

### Graceful Degradation
The system automatically falls back to standard processing if optimized services are unavailable:

```bash
# If aiohttp not installed
$ thoth performance batch --async
Warning: aiofiles not available, falling back to synchronous file I/O
Processing with reduced async capabilities...

# If psutil not installed
$ thoth performance info
Warning: psutil not available, system info limited
```

### Standard Commands Still Work
All existing commands work exactly as before:

```bash
# These commands work regardless of optimization installation
thoth monitor --watch-dir /pdfs
thoth process --pdf-path document.pdf
thoth rag index
```

## Performance Monitoring

### Built-in Metrics
Commands provide detailed performance feedback:

```bash
# Batch processing shows:
- Processing rate (files/minute)
- Average time per PDF
- Success/failure rates
- Cache hit rates
- Resource utilization

# System info shows:
- CPU usage and core count
- Memory usage and availability
- Current performance configuration
- Optimization status
```

### Log Analysis
Monitor performance through logs:

```bash
# Enable detailed logging
export LOG_LEVEL=DEBUG

# Monitor processing performance
tail -f logs/thoth.log | grep -E "(Processing|completed|optimized)"
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```
   Error: Optimized pipeline requested but not available
   ```
   **Solution**: Install performance dependencies:
   ```bash
   pip install -r requirements-performance.txt
   ```

2. **Memory Issues**
   ```
   Error: Process killed during processing
   ```
   **Solution**: Reduce concurrency:
   ```bash
   export PERFORMANCE_CONTENT_ANALYSIS_WORKERS=2
   export PERFORMANCE_OCR_MAX_CONCURRENT=1
   ```

3. **API Rate Limiting**
   ```
   Warning: API rate limit exceeded
   ```
   **Solution**: Adjust rate limiting:
   ```bash
   export PERFORMANCE_OCR_MAX_CONCURRENT=2
   export API_GATEWAY_RATE_LIMIT=3.0
   ```

### Performance Debugging
Use built-in tools to diagnose issues:

```bash
# Check system resources
thoth performance info

# Verify cache functionality
thoth performance cache

# Run benchmark to isolate issues
thoth performance benchmark --files problematic.pdf

# Check configuration
python -c "
from thoth.utilities.config import get_config
config = get_config()
print('Auto-scale:', config.performance_config.auto_scale_workers)
print('Async enabled:', config.performance_config.async_enabled)
"
```

## Advanced Usage

### Custom Processing Scripts
Integrate with Python scripts:

```python
#!/usr/bin/env python3
import asyncio
from pathlib import Path
from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline
from thoth.services.service_manager import ServiceManager
from thoth.utilities.config import get_config

async def process_pdfs_custom():
    config = get_config()
    service_manager = ServiceManager(config)
    service_manager.initialize()

    pipeline = OptimizedDocumentPipeline(
        config=config,
        services=service_manager,
        markdown_dir=config.markdown_dir,
        notes_dir=config.notes_dir,
    )

    pdf_paths = list(Path('/data/pdfs').glob('*.pdf'))
    results = await pipeline.batch_process_pdfs_async(pdf_paths)

    print(f"Processed {len(results)} PDFs")
    await pipeline.cleanup()

if __name__ == '__main__':
    asyncio.run(process_pdfs_custom())
```

This comprehensive integration provides a seamless upgrade path from standard to optimized processing while maintaining full backward compatibility.

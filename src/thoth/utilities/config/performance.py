"""
Performance and concurrency configuration.

This module contains configuration for performance optimization,
concurrency settings, and system resource management.
"""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PerformanceConfig(BaseSettings):
    """
    Configuration for performance and concurrency settings optimized for local
    servers.
    """

    model_config = SettingsConfigDict(
        env_prefix='PERFORMANCE_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # Auto-scaling settings
    auto_scale_workers: bool = Field(
        True,
        description='Automatically scale workers based on available CPU cores',
    )

    # Tag processing workers - optimized for local processing
    tag_mapping_workers: int = Field(
        default_factory=lambda: min(max(1, (os.cpu_count() or 4) - 1), 8),
        description='Number of parallel workers for tag mapping operations',
        ge=1,
        le=20,
    )
    article_processing_workers: int = Field(
        default_factory=lambda: min(max(1, (os.cpu_count() or 4) // 2), 6),
        description='Number of parallel workers for article tag processing',
        ge=1,
        le=10,
    )

    # Document pipeline workers - CPU-aware defaults
    content_analysis_workers: int = Field(
        default_factory=lambda: min(max(1, (os.cpu_count() or 4) - 1), 4),
        description='Number of parallel workers for content analysis and citation extraction',
        ge=1,
        le=8,
    )

    # Citation enhancement workers - I/O bound, can handle more
    citation_enhancement_workers: int = Field(
        default_factory=lambda: min(max(2, (os.cpu_count() or 4) - 1), 8),
        description='Number of parallel workers for citation enhancement APIs',
        ge=1,
        le=15,
    )
    citation_pdf_workers: int = Field(
        default_factory=lambda: min(max(2, (os.cpu_count() or 4) - 1), 10),
        description='Number of parallel workers for PDF location',
        ge=1,
        le=20,
    )

    # Citation extraction workers - parallel processing friendly
    citation_extraction_workers: int = Field(
        default_factory=lambda: min(max(2, (os.cpu_count() or 4) - 1), 8),
        description='Number of parallel workers for citation extraction from raw strings',
        ge=1,
        le=16,
    )

    # OCR processing settings
    ocr_max_concurrent: int = Field(
        3,
        description='Maximum concurrent OCR operations (API rate limited)',
        ge=1,
        le=6,
    )
    ocr_enable_caching: bool = Field(
        True,
        description='Enable OCR result caching for improved performance',
    )
    ocr_cache_ttl_hours: int = Field(
        24,
        description='OCR cache time-to-live in hours',
        ge=1,
        le=168,  # 1 week max
    )

    # Async processing settings
    async_enabled: bool = Field(
        True,
        description='Enable async I/O processing for better performance',
    )
    async_timeout_seconds: int = Field(
        300,
        description='Timeout for async operations in seconds',
        ge=30,
        le=1800,
    )

    # Memory management
    memory_optimization_enabled: bool = Field(
        True,
        description='Enable memory optimization techniques',
    )
    chunk_processing_enabled: bool = Field(
        True,
        description='Enable chunk-based processing for large documents',
    )
    max_document_size_mb: int = Field(
        50,
        description='Maximum document size in MB before switching to streaming',
        ge=5,
        le=500,
    )

    # Semantic Scholar API optimization
    semanticscholar_max_retries: int = Field(
        3, description='Maximum retries for Semantic Scholar API requests', ge=1, le=10
    )
    semanticscholar_max_backoff_seconds: float = Field(
        30.0,
        description='Maximum backoff time for Semantic Scholar API',
        ge=5.0,
        le=300.0,
    )
    semanticscholar_backoff_multiplier: float = Field(
        1.5,
        description='Backoff multiplier for Semantic Scholar exponential backoff',
        ge=1.1,
        le=3.0,
    )

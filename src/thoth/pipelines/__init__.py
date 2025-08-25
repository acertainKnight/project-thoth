"""Pipelines package for Thoth."""

from .base import BasePipeline
from .document_pipeline import DocumentPipeline as LegacyDocumentPipeline
from .knowledge_pipeline import KnowledgePipeline
from .optimized_document_pipeline import OptimizedDocumentPipeline

# Use optimized pipeline as the default DocumentPipeline for new installations
DocumentPipeline = OptimizedDocumentPipeline

__all__ = [
    'BasePipeline',
    'DocumentPipeline',
    'KnowledgePipeline',
    'LegacyDocumentPipeline',
    'OptimizedDocumentPipeline',
]

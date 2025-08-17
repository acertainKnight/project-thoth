"""Pipelines package for Thoth."""

from .base import BasePipeline
from .knowledge_pipeline import KnowledgePipeline
from .optimized_document_pipeline import OptimizedDocumentPipeline

# Alias for backward compatibility
DocumentPipeline = OptimizedDocumentPipeline

__all__ = ['BasePipeline', 'DocumentPipeline', 'KnowledgePipeline', 'OptimizedDocumentPipeline']

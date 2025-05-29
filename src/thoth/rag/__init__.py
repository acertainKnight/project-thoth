"""
RAG (Retrieval-Augmented Generation) module for Thoth.

This module provides functionality for:
- Document embedding and vector storage
- Semantic search over the knowledge base
- Context-aware question answering
"""

from .embeddings import EmbeddingManager
from .rag_manager import RAGManager
from .vector_store import VectorStoreManager

__all__ = ['EmbeddingManager', 'RAGManager', 'VectorStoreManager']

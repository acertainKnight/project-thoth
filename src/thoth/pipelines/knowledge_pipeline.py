from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from .base import BasePipeline


class KnowledgePipeline(BasePipeline):
    """Pipeline for managing knowledge base and RAG operations."""

    def _index_to_rag(self, file_path: Path) -> None:
        """Index a markdown file to the RAG system if available."""
        try:
            if file_path.exists() and file_path.suffix == ".md":
                self.services.rag.index_file(file_path)
                logger.debug(f"Indexed {file_path} to RAG system")
        except Exception as e:  # pragma: no cover - optional integration
            logger.debug(f"Failed to index {file_path} to RAG: {e}")

    def index_knowledge_base(self) -> dict[str, Any]:
        """Index all markdown and note files into the RAG system."""
        logger.info("Starting knowledge base indexing for RAG system")
        try:
            stats = self.services.rag.index_knowledge_base()
            logger.info(
                f"Knowledge base indexing completed. "
                f"Indexed {stats['total_files']} files "
                f"({stats['total_chunks']} chunks)"
            )
            return stats
        except Exception as e:
            logger.error(f"Knowledge base indexing failed: {e}")
            raise

    def search_knowledge_base(
        self, query: str, k: int = 4, filter: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Search the knowledge base for relevant documents."""
        try:
            logger.info(f"Searching knowledge base for: {query}")
            return self.services.rag.search(query, k, filter)
        except Exception as e:
            logger.error(f"Knowledge base search failed: {e}")
            raise

    def ask_knowledge_base(
        self, question: str, k: int = 4, filter: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Ask a question using the knowledge base."""
        try:
            logger.info(f"Answering question: {question}")
            return self.services.rag.ask_question(question, k, filter)
        except Exception as e:
            logger.error(f"Failed to answer question: {e}")
            raise

    def clear_rag_index(self) -> None:
        """Clear the entire RAG vector index."""
        try:
            logger.warning("Clearing RAG vector index")
            self.services.rag.clear_index()
            logger.info("RAG vector index cleared successfully")
        except Exception as e:
            logger.error(f"Failed to clear RAG index: {e}")
            raise

    def get_rag_stats(self) -> dict[str, Any]:
        """Get statistics about the RAG system."""
        try:
            return self.services.rag.get_stats()
        except Exception as e:
            logger.error(f"Failed to get RAG stats: {e}")
            raise

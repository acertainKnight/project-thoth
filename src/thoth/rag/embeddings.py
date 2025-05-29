"""
Embedding manager for Thoth RAG system.

This module handles the creation and management of embeddings for documents
in the knowledge base.
"""

from typing import Any

from langchain_openai import OpenAIEmbeddings
from loguru import logger

from thoth.utilities.config import get_config


class EmbeddingManager:
    """
    Manages document embeddings for the RAG system.

    This class provides functionality to:
    - Create embeddings from text using OpenAI models via OpenRouter
    - Handle batch embedding operations
    - Configure embedding model parameters
    """

    def __init__(
        self,
        model: str | None = None,
        openrouter_api_key: str | None = None,
        base_url: str | None = None,
    ):
        """
        Initialize the embedding manager.

        Args:
            model: The embedding model to use (defaults to config).
            openrouter_api_key: OpenRouter API key (defaults to config).
            base_url: Custom base URL for OpenRouter API.
        """
        self.config = get_config()

        # Use provided values or fall back to config
        self.model = model or self.config.rag_config.embedding_model
        self.api_key = openrouter_api_key or self.config.api_keys.openrouter_key
        self.base_url = base_url or 'https://openrouter.ai/api/v1'

        # Initialize embeddings
        self._init_embeddings()

        logger.info(f'EmbeddingManager initialized with model: {self.model}')

    def _init_embeddings(self) -> None:
        """Initialize the embeddings model."""
        try:
            # Create OpenAI-compatible embeddings using OpenRouter
            self.embeddings = OpenAIEmbeddings(
                model=self.model,
                openai_api_key=self.api_key,
                openai_api_base=self.base_url,
                show_progress_bar=True,
                chunk_size=self.config.rag_config.embedding_batch_size,
            )
            logger.debug('Embeddings model initialized successfully')
        except Exception as e:
            logger.error(f'Failed to initialize embeddings: {e}')
            raise

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Create embeddings for a list of documents.

        Args:
            texts: List of document texts to embed.

        Returns:
            List of embedding vectors.
        """
        try:
            logger.debug(f'Embedding {len(texts)} documents')
            embeddings = self.embeddings.embed_documents(texts)
            logger.debug(f'Successfully embedded {len(embeddings)} documents')
            return embeddings
        except Exception as e:
            logger.error(f'Error embedding documents: {e}')
            raise

    def embed_query(self, text: str) -> list[float]:
        """
        Create embedding for a single query text.

        Args:
            text: Query text to embed.

        Returns:
            Embedding vector for the query.
        """
        try:
            logger.debug('Embedding query text')
            embedding = self.embeddings.embed_query(text)
            return embedding
        except Exception as e:
            logger.error(f'Error embedding query: {e}')
            raise

    def get_embedding_model(self) -> Any:
        """
        Get the underlying embeddings model for use with LangChain.

        Returns:
            The embeddings model instance.
        """
        return self.embeddings

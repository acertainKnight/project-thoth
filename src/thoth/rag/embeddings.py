"""
Embedding manager for Thoth RAG system.

This module handles the creation and management of embeddings for documents
in the knowledge base using sentence-transformers for local processing.
"""

from typing import Any

from langchain_huggingface import HuggingFaceEmbeddings
from loguru import logger

from thoth.utilities.config import get_config


class EmbeddingManager:
    """
    Manages document embeddings for the RAG system.

    This class provides functionality to:
    - Create embeddings from text using sentence-transformers models locally
    - Handle batch embedding operations
    - Configure embedding model parameters
    """

    def __init__(
        self,
        model: str | None = None,
        openrouter_api_key: str | None = None,  # noqa: ARG002
        base_url: str | None = None,  # noqa: ARG002
    ):
        """
        Initialize the embedding manager.

        Args:
            model: The embedding model to use (defaults to config).
            openrouter_api_key: Not used for local embeddings (kept for compatibility).
            base_url: Not used for local embeddings (kept for compatibility).
        """
        self.config = get_config()

        # Use provided model or fall back to config, with local model default
        self.model = model or self.config.rag_config.embedding_model

        # If the config still has an OpenAI model, use a good local alternative
        if 'openai/' in self.model or 'text-embedding' in self.model:
            self.model = 'all-MiniLM-L6-v2'  # Fast and efficient local model
            logger.info(
                f'Using local embedding model: {self.model} (switched from API-based model)'
            )

        # Initialize embeddings
        self._init_embeddings()

        logger.info(f'EmbeddingManager initialized with local model: {self.model}')

    def _init_embeddings(self) -> None:
        """Initialize the embeddings model using sentence-transformers."""
        try:
            # Create local embeddings using HuggingFace/sentence-transformers
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.model,
                model_kwargs={
                    'device': 'cpu'
                },  # Use CPU by default, can be changed to 'cuda' if GPU available
                encode_kwargs={
                    'normalize_embeddings': True
                },  # Normalize for better similarity search
                show_progress=True,
            )
            logger.debug(
                f'Local embeddings model initialized successfully: {self.model}'
            )
        except Exception as e:
            logger.error(f'Failed to initialize embeddings: {e}')
            # Fallback to a known working model
            logger.info('Falling back to default embedding model: all-MiniLM-L6-v2')
            try:
                self.embeddings = HuggingFaceEmbeddings(
                    model_name='all-MiniLM-L6-v2',
                    model_kwargs={'device': 'cpu'},
                    encode_kwargs={'normalize_embeddings': True},
                    show_progress=True,
                )
                self.model = 'all-MiniLM-L6-v2'
                logger.debug('Fallback embeddings model initialized successfully')
            except Exception as fallback_e:
                logger.error(f'Failed to initialize fallback embeddings: {fallback_e}')
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
            logger.debug(f'Embedding {len(texts)} documents using local model')
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
            logger.debug('Embedding query text using local model')
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

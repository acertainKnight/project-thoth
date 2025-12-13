"""
Embedding manager for Thoth RAG system.

This module handles the creation and management of embeddings for documents
in the knowledge base using either local sentence-transformers or OpenAI embeddings.
"""

import os
from typing import Any

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from loguru import logger

from thoth.config import config


class EmbeddingManager:
    """
    Manages document embeddings for the RAG system.

    This class provides functionality to:
    - Create embeddings from text using sentence-transformers models locally or OpenAI
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
        self.config = config

        # Use provided model or fall back to config
        self.model = model or self.config.rag_config.embedding_model
        self.is_openai_model = self._is_openai_model(self.model)

        if not self.is_openai_model:
            # Check environment safety before configuring
            is_safe, issues = self.check_environment_safety()
            if not is_safe:
                logger.warning(
                    f'Environment may not be safe for local embeddings: {issues}'
                )

            # Set environment variables to prevent segfaults for local models
            self._configure_safe_environment()

            # Verify configuration was applied
            is_safe_after, remaining_issues = self.check_environment_safety()
            if is_safe_after:
                logger.info('Environment configured safely for local embeddings')
            else:
                logger.warning(f'Some environment issues remain: {remaining_issues}')

        # Initialize embeddings
        self._init_embeddings()

        model_type = 'OpenAI API' if self.is_openai_model else 'local'
        logger.info(
            f'EmbeddingManager initialized with {model_type} model: {self.model}'
        )

    def _is_openai_model(self, model: str) -> bool:
        """Check if the model is an OpenAI embedding model."""
        openai_prefixes = ['openai/', 'text-embedding']
        return any(model.startswith(prefix) for prefix in openai_prefixes)

    def _configure_safe_environment(self) -> None:
        """Configure environment variables to prevent segmentation faults."""
        # Prevent threading issues that can cause segfaults
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        os.environ['OMP_NUM_THREADS'] = '1'
        os.environ['MKL_NUM_THREADS'] = '1'
        os.environ['NUMEXPR_NUM_THREADS'] = '1'

        # Set PyTorch to use single thread to avoid conflicts
        os.environ['TORCH_NUM_THREADS'] = '1'

        # Additional ChromaDB and SQLite safety settings
        os.environ['CHROMA_MAX_BATCH_SIZE'] = '100'
        os.environ['CHROMA_SUBMIT_BATCH_SIZE'] = '100'
        os.environ['SQLITE_ENABLE_PREUPDATE_HOOK'] = '0'
        os.environ['SQLITE_ENABLE_FTS5'] = '0'

        # Additional safety for memory allocation
        os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
        os.environ['KMP_INIT_AT_FORK'] = 'FALSE'

        logger.debug('Configured safe environment variables to prevent segfaults')

    def _init_embeddings(self) -> None:
        """Initialize the embeddings model using OpenAI or sentence-transformers."""
        if self.is_openai_model:
            self._init_openai_embeddings()
        else:
            self._init_local_embeddings()

    def _init_openai_embeddings(self) -> None:
        """Initialize OpenAI embeddings."""
        try:
            # Extract model name (remove 'openai/' prefix if present)
            model_name = self.model.replace('openai/', '')

            # Get API key from config
            api_key = self.config.api_keys.openai_key
            if not api_key:
                msg = 'OpenAI API key is required for OpenAI embeddings. Set API_OPENAI_KEY in .env file.'
                raise ValueError(msg)

            self.embeddings = OpenAIEmbeddings(
                model=model_name,
                openai_api_key=api_key,
                show_progress_bar=False,
            )
            logger.debug(f'OpenAI embeddings initialized successfully: {model_name}')

        except Exception as e:
            logger.error(f'Failed to initialize OpenAI embeddings: {e}')
            logger.info('Falling back to local embedding model')
            self.model = 'all-MiniLM-L6-v2'
            self.is_openai_model = False
            self._configure_safe_environment()
            self._init_local_embeddings()

    def _init_local_embeddings(self) -> None:
        """Initialize local sentence-transformers embeddings."""
        try:
            # Create local embeddings using HuggingFace/sentence-transformers
            # with safer configuration to prevent segfaults
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.model,
                model_kwargs={
                    'device': 'cpu',
                    'trust_remote_code': False,  # Security best practice
                },
                encode_kwargs={
                    'normalize_embeddings': True,
                    'batch_size': 4,  # Even smaller batch size to prevent memory issues
                    'convert_to_numpy': True,  # Convert to numpy to free torch memory
                },
                show_progress=False,  # Disable progress display
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
                    model_kwargs={
                        'device': 'cpu',
                        'trust_remote_code': False,
                    },
                    encode_kwargs={
                        'normalize_embeddings': True,
                        'batch_size': 4,
                        'convert_to_numpy': True,
                    },
                    show_progress=False,
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
            model_type = 'OpenAI API' if self.is_openai_model else 'local'
            logger.debug(f'Embedding {len(texts)} documents using {model_type} model')

            if self.is_openai_model:
                # OpenAI embeddings handle batching automatically
                embeddings = self.embeddings.embed_documents(texts)
            else:
                # Process in smaller batches to prevent memory issues for local models
                batch_size = 8
                embeddings = []

                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    batch_embeddings = self.embeddings.embed_documents(batch)
                    embeddings.extend(batch_embeddings)

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
            model_type = 'OpenAI API' if self.is_openai_model else 'local'
            logger.debug(f'Embedding query text using {model_type} model')
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

    @staticmethod
    def check_environment_safety() -> tuple[bool, list[str]]:
        """
        Check if current environment is properly configured for safe local embeddings.

        Returns:
            tuple[bool, list[str]]: (is_safe, list_of_issues)
        """
        issues = []

        # Check required environment variables
        required_env_vars = {
            'TOKENIZERS_PARALLELISM': 'false',
            'OMP_NUM_THREADS': '1',
            'MKL_NUM_THREADS': '1',
            'NUMEXPR_NUM_THREADS': '1',
            'TORCH_NUM_THREADS': '1',
        }

        for var, expected_value in required_env_vars.items():
            current_value = os.environ.get(var)
            if current_value != expected_value:
                issues.append(
                    f"{var} should be '{expected_value}', got '{current_value}'"
                )

        # Check for known problematic conditions
        try:
            import torch

            if torch.cuda.is_available():
                issues.append(
                    "CUDA is available but we're forcing CPU - may cause conflicts"
                )
        except ImportError:
            pass  # PyTorch not available, which is fine

        return len(issues) == 0, issues

"""
Vector store manager for Thoth RAG system.

This module handles the storage and retrieval of document embeddings
using ChromaDB as the vector database.
"""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from loguru import logger

from thoth.utilities.config import get_config


class VectorStoreManager:
    """
    Manages the vector store for document embeddings.

    This class provides functionality to:
    - Store document embeddings in ChromaDB
    - Perform similarity searches
    - Manage collections and indices
    """

    def __init__(
        self,
        collection_name: str | None = None,
        persist_directory: str | Path | None = None,
        embedding_function: Any | None = None,
    ):
        """
        Initialize the vector store manager.

        Args:
            collection_name: Name of the ChromaDB collection (defaults to config).
            persist_directory: Directory to persist the vector DB (defaults to config).
            embedding_function: Embedding function to use (required).
        """
        self.config = get_config()

        # Set collection name and persist directory
        self.collection_name = collection_name or self.config.rag_config.collection_name
        self.persist_directory = Path(
            persist_directory or self.config.rag_config.vector_db_path
        )

        # Create persist directory if it doesn't exist
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Store embedding function
        if embedding_function is None:
            raise ValueError('Embedding function is required')
        self.embedding_function = embedding_function

        # Initialize ChromaDB client
        self._init_client()

        # Initialize vector store
        self._init_vector_store()

        logger.info(
            f'VectorStoreManager initialized with collection: {self.collection_name}'
        )

    def _init_client(self) -> None:
        """Initialize the ChromaDB client."""
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
            logger.debug('ChromaDB client initialized')
        except Exception as e:
            logger.error(f'Failed to initialize ChromaDB client: {e}')
            raise

    def _init_vector_store(self) -> None:
        """Initialize the vector store."""
        try:
            self.vector_store = Chroma(
                client=self.client,
                collection_name=self.collection_name,
                embedding_function=self.embedding_function,
                persist_directory=str(self.persist_directory),
            )
            logger.debug(
                f'Vector store initialized for collection: {self.collection_name}'
            )
        except Exception as e:
            logger.error(f'Failed to initialize vector store: {e}')
            raise

    def add_documents(
        self,
        documents: list[Document],
        ids: list[str] | None = None,
    ) -> list[str]:
        """
        Add documents to the vector store.

        Args:
            documents: List of LangChain Document objects to add.
            ids: Optional list of IDs for the documents.

        Returns:
            List of IDs for the added documents.
        """
        try:
            logger.info(f'Adding {len(documents)} documents to vector store')

            # Add documents with progress tracking
            doc_ids = self.vector_store.add_documents(
                documents=documents,
                ids=ids,
            )

            logger.info(f'Successfully added {len(doc_ids)} documents')
            return doc_ids

        except Exception as e:
            logger.error(f'Error adding documents to vector store: {e}')
            raise

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """
        Perform similarity search on the vector store.

        Args:
            query: Query text to search for.
            k: Number of results to return.
            filter: Optional metadata filter.

        Returns:
            List of similar documents.
        """
        try:
            logger.debug(f'Performing similarity search for query: {query[:100]}...')

            results = self.vector_store.similarity_search(
                query=query,
                k=k,
                filter=filter,
            )

            logger.debug(f'Found {len(results)} similar documents')
            return results

        except Exception as e:
            logger.error(f'Error performing similarity search: {e}')
            raise

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
    ) -> list[tuple[Document, float]]:
        """
        Perform similarity search with relevance scores.

        Args:
            query: Query text to search for.
            k: Number of results to return.
            filter: Optional metadata filter.

        Returns:
            List of tuples (document, score).
        """
        try:
            logger.debug(
                f'Performing similarity search with scores for query: {query[:100]}...'
            )

            results = self.vector_store.similarity_search_with_score(
                query=query,
                k=k,
                filter=filter,
            )

            logger.debug(f'Found {len(results)} similar documents with scores')
            return results

        except Exception as e:
            logger.error(f'Error performing similarity search with scores: {e}')
            raise

    def delete_documents(self, ids: list[str]) -> None:
        """
        Delete documents from the vector store by ID.

        Args:
            ids: List of document IDs to delete.
        """
        try:
            logger.info(f'Deleting {len(ids)} documents from vector store')
            self.vector_store.delete(ids=ids)
            logger.info('Documents deleted successfully')
        except Exception as e:
            logger.error(f'Error deleting documents: {e}')
            raise

    def get_all_documents(self) -> list[Document]:
        """
        Get all documents from the vector store.

        Returns:
            List of all documents in the store.
        """
        try:
            # Get all documents by doing a large similarity search
            # This is a workaround as ChromaDB doesn't have a direct "get all"
            # method in LangChain
            collection = self.client.get_collection(self.collection_name)
            results = collection.get()

            # Convert to LangChain documents
            documents = []
            if results and 'documents' in results:
                for i, doc_text in enumerate(results['documents']):
                    metadata = results.get('metadatas', [{}])[i] or {}
                    doc = Document(page_content=doc_text, metadata=metadata)
                    documents.append(doc)

            logger.debug(f'Retrieved {len(documents)} documents from vector store')
            return documents

        except Exception as e:
            logger.error(f'Error getting all documents: {e}')
            raise

    def clear_collection(self) -> None:
        """Clear all documents from the current collection."""
        try:
            logger.warning(
                f'Clearing all documents from collection: {self.collection_name}'
            )
            self.client.delete_collection(self.collection_name)
            self._init_vector_store()  # Reinitialize empty collection
            logger.info('Collection cleared successfully')
        except Exception as e:
            logger.error(f'Error clearing collection: {e}')
            raise

    def get_collection_stats(self) -> dict[str, Any]:
        """
        Get statistics about the current collection.

        Returns:
            Dictionary with collection statistics.
        """
        try:
            collection = self.client.get_collection(self.collection_name)
            count = collection.count()

            stats = {
                'collection_name': self.collection_name,
                'document_count': count,
                'persist_directory': str(self.persist_directory),
            }

            logger.debug(f'Collection stats: {stats}')
            return stats

        except Exception as e:
            logger.error(f'Error getting collection stats: {e}')
            raise

    def get_retriever(self, **kwargs) -> Any:
        """
        Get a retriever instance for use with LangChain.

        Args:
            **kwargs: Additional arguments for the retriever.

        Returns:
            A LangChain retriever instance.
        """
        return self.vector_store.as_retriever(**kwargs)

"""
RAG Manager for Thoth.

This module provides the main interface for the Retrieval-Augmented Generation
system, coordinating embeddings, vector storage, and question answering.
"""

from pathlib import Path
from typing import Any

from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from loguru import logger

from thoth.rag.embeddings import EmbeddingManager
from thoth.rag.vector_store import VectorStoreManager
from thoth.utilities.config import get_config
from thoth.utilities.openrouter import OpenRouterClient


class RAGManager:
    """
    Main manager for the RAG system.

    This class coordinates:
    - Document processing and chunking
    - Embedding generation
    - Vector storage and retrieval
    - Question answering with context
    """

    def __init__(
        self,
        embedding_model: str | None = None,
        llm_model: str | None = None,
        collection_name: str | None = None,
        vector_db_path: str | Path | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        openrouter_api_key: str | None = None,
    ):
        """
        Initialize the RAG manager.

        Args:
            embedding_model: Model to use for embeddings (defaults to config).
            llm_model: Model to use for question answering (defaults to config).
            collection_name: Name of the vector DB collection (defaults to config).
            vector_db_path: Path to persist vector DB (defaults to config).
            chunk_size: Size of text chunks (defaults to config).
            chunk_overlap: Overlap between chunks (defaults to config).
            openrouter_api_key: API key for OpenRouter (defaults to config).
        """
        self.config = get_config()

        # Set parameters from config or arguments
        self.embedding_model = embedding_model or self.config.rag_config.embedding_model
        self.llm_model = llm_model or self.config.rag_config.qa_model
        self.collection_name = collection_name or self.config.rag_config.collection_name
        self.vector_db_path = Path(
            vector_db_path or self.config.rag_config.vector_db_path
        )
        self.chunk_size = chunk_size or self.config.rag_config.chunk_size
        self.chunk_overlap = chunk_overlap or self.config.rag_config.chunk_overlap
        self.api_key = openrouter_api_key or self.config.api_keys.openrouter_key

        # Initialize components
        self._init_components()

        logger.info('RAGManager initialized successfully')

    def _init_components(self) -> None:
        """Initialize all RAG components."""
        # Initialize embedding manager
        self.embedding_manager = EmbeddingManager(
            model=self.embedding_model,
            openrouter_api_key=self.api_key,
        )

        # Initialize vector store manager
        self.vector_store_manager = VectorStoreManager(
            collection_name=self.collection_name,
            persist_directory=self.vector_db_path,
            embedding_function=self.embedding_manager.get_embedding_model(),
        )

        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=['\n\n', '\n', ' ', ''],
        )

        # Initialize LLM for QA
        self.llm = OpenRouterClient(
            api_key=self.api_key,
            model=self.llm_model,
            temperature=self.config.rag_config.qa_temperature,
            max_tokens=self.config.rag_config.qa_max_tokens,
        )

        logger.debug('All RAG components initialized')

    def index_markdown_file(self, file_path: Path) -> list[str]:
        """
        Index a markdown file into the vector store.

        Args:
            file_path: Path to the markdown file.

        Returns:
            List of document IDs that were indexed.
        """
        try:
            logger.info(f'Indexing markdown file: {file_path}')

            # Read the file
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            # Extract metadata from file
            metadata = self._extract_metadata_from_path(file_path)

            # Split into chunks
            chunks = self.text_splitter.split_text(content)
            logger.debug(f'Split document into {len(chunks)} chunks')

            # Create documents with metadata
            documents = []
            for i, chunk in enumerate(chunks):
                doc_metadata = {
                    **metadata,
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                }
                doc = Document(
                    page_content=chunk,
                    metadata=doc_metadata,
                )
                documents.append(doc)

            # Index documents
            doc_ids = self.vector_store_manager.add_documents(documents)
            logger.info(f'Successfully indexed {len(doc_ids)} chunks from {file_path}')

            return doc_ids

        except Exception as e:
            logger.error(f'Error indexing markdown file {file_path}: {e}')
            raise

    def index_directory(
        self,
        directory: Path,
        pattern: str = '*.md',
        recursive: bool = True,
    ) -> dict[str, list[str]]:
        """
        Index all markdown files in a directory.

        Args:
            directory: Directory containing markdown files.
            pattern: File pattern to match (default: "*.md").
            recursive: Whether to search recursively.

        Returns:
            Dictionary mapping file paths to their document IDs.
        """
        try:
            logger.info(f'Indexing directory: {directory}')

            # Find all markdown files
            if recursive:
                files = list(directory.rglob(pattern))
            else:
                files = list(directory.glob(pattern))

            logger.info(f'Found {len(files)} files to index')

            # Index each file
            results = {}
            for file_path in files:
                try:
                    doc_ids = self.index_markdown_file(file_path)
                    results[str(file_path)] = doc_ids
                except Exception as e:
                    logger.error(f'Failed to index {file_path}: {e}')
                    continue

            logger.info(f'Successfully indexed {len(results)} files')
            return results

        except Exception as e:
            logger.error(f'Error indexing directory {directory}: {e}')
            raise

    def search(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        return_scores: bool = False,
    ) -> list[Document] | list[tuple[Document, float]]:
        """
        Search for relevant documents.

        Args:
            query: Search query.
            k: Number of results to return.
            filter: Optional metadata filter.
            return_scores: Whether to return relevance scores.

        Returns:
            List of documents or tuples of (document, score).
        """
        try:
            if return_scores:
                return self.vector_store_manager.similarity_search_with_score(
                    query=query,
                    k=k,
                    filter=filter,
                )
            else:
                return self.vector_store_manager.similarity_search(
                    query=query,
                    k=k,
                    filter=filter,
                )
        except Exception as e:
            logger.error(f'Error searching documents: {e}')
            raise

    def answer_question(
        self,
        question: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
        return_sources: bool = True,
    ) -> dict[str, Any]:
        """
        Answer a question using the RAG system.

        Args:
            question: The question to answer.
            k: Number of documents to retrieve for context.
            filter: Optional metadata filter for retrieval.
            return_sources: Whether to return source documents.

        Returns:
            Dictionary containing the answer and optionally source documents.
        """
        try:
            logger.info(f'Answering question: {question}')

            # Get retriever
            retriever = self.vector_store_manager.get_retriever(
                search_kwargs={
                    'k': k,
                    'filter': filter,
                }
            )

            # Create QA chain
            qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type='stuff',
                retriever=retriever,
                return_source_documents=return_sources,
            )

            # Get answer
            result = qa_chain({'query': question})

            # Format response
            response = {
                'question': question,
                'answer': result['result'],
            }

            if return_sources and 'source_documents' in result:
                response['sources'] = []
                for doc in result['source_documents']:
                    source_info = {
                        'content': doc.page_content[:200] + '...',  # Preview
                        'metadata': doc.metadata,
                    }
                    response['sources'].append(source_info)

            logger.info('Successfully generated answer')
            return response

        except Exception as e:
            logger.error(f'Error answering question: {e}')
            raise

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the RAG system.

        Returns:
            Dictionary with system statistics.
        """
        try:
            vector_stats = self.vector_store_manager.get_collection_stats()

            stats = {
                'embedding_model': self.embedding_model,
                'qa_model': self.llm_model,
                'chunk_size': self.chunk_size,
                'chunk_overlap': self.chunk_overlap,
                **vector_stats,
            }

            return stats

        except Exception as e:
            logger.error(f'Error getting RAG stats: {e}')
            raise

    def clear_index(self) -> None:
        """Clear the entire vector index."""
        try:
            logger.warning('Clearing entire vector index')
            self.vector_store_manager.clear_collection()
            logger.info('Vector index cleared')
        except Exception as e:
            logger.error(f'Error clearing index: {e}')
            raise

    def _extract_metadata_from_path(self, file_path: Path) -> dict[str, Any]:
        """
        Extract metadata from file path and name.

        Args:
            file_path: Path to the file.

        Returns:
            Dictionary of metadata.
        """
        metadata = {
            'source': str(file_path),
            'filename': file_path.name,
            'file_type': file_path.suffix,
        }

        # Check if it's a note or markdown
        if 'notes' in file_path.parts:
            metadata['document_type'] = 'note'
        elif 'markdown' in file_path.parts:
            metadata['document_type'] = 'article'
        else:
            metadata['document_type'] = 'other'

        # Try to extract title from filename
        title = file_path.stem.replace('_', ' ').replace('-', ' ')
        metadata['title'] = title

        return metadata

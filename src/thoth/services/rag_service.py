"""
RAG service for managing the knowledge base and retrieval operations.

This module consolidates all RAG-related operations that were previously
scattered across RAGManager, Pipeline, and agent tools.
"""

from pathlib import Path
from typing import Any

from thoth.rag.rag_manager import RAGManager
from thoth.services.base import BaseService, ServiceError


class RAGService(BaseService):
    """
    Service for managing RAG (Retrieval-Augmented Generation) operations.

    This service consolidates all RAG-related operations including:
    - Indexing documents
    - Searching the knowledge base
    - Answering questions
    - Managing the vector store
    """

    def __init__(self, config=None, rag_manager: RAGManager | None = None):
        """
        Initialize the RAGService.

        Args:
            config: Optional configuration object
            rag_manager: Optional RAGManager instance
        """
        super().__init__(config)
        self._rag_manager = rag_manager
        self._index_stats: dict[str, Any] = {}

    def initialize(self) -> None:
        """Initialize the RAG service."""
        self.logger.info('RAG service initialized')

    @property
    def rag_manager(self) -> RAGManager:
        """Get or create the RAG manager."""
        if self._rag_manager is None:
            self._rag_manager = RAGManager(
                embedding_model=self.config.rag_config.embedding_model,
                llm_model=self.config.rag_config.qa_model,
                collection_name=self.config.rag_config.collection_name,
                vector_db_path=self.config.rag_config.vector_db_path,
                chunk_size=self.config.rag_config.chunk_size,
                chunk_overlap=self.config.rag_config.chunk_overlap,
                openrouter_api_key=self.config.api_keys.openrouter_key,
            )
        return self._rag_manager

    def index_file(self, file_path: Path) -> list[str]:
        """
        Index a single file into the knowledge base.

        Args:
            file_path: Path to the file to index

        Returns:
            list[str]: List of document IDs created

        Raises:
            ServiceError: If indexing fails
        """
        try:
            self.validate_input(file_path=file_path)

            if not file_path.exists():
                raise ServiceError(f'File does not exist: {file_path}')

            if file_path.suffix != '.md':
                raise ServiceError(
                    f'Only markdown files are supported, got: {file_path.suffix}'
                )

            doc_ids = self.rag_manager.index_markdown_file(file_path)

            self.log_operation(
                'file_indexed',
                file=str(file_path),
                chunks=len(doc_ids),
            )

            return doc_ids

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f'indexing file {file_path}')
            ) from e

    def index_directory(
        self,
        directory: Path,
        pattern: str = '*.md',
        recursive: bool = True,
    ) -> dict[str, list[str]]:
        """
        Index all matching files in a directory.

        Args:
            directory: Directory to index
            pattern: File pattern to match
            recursive: Whether to search recursively

        Returns:
            dict[str, list[str]]: Mapping of file paths to document IDs

        Raises:
            ServiceError: If indexing fails
        """
        try:
            self.validate_input(directory=directory)

            if not directory.exists():
                raise ServiceError(f'Directory does not exist: {directory}')

            results = self.rag_manager.index_directory(
                directory=directory,
                pattern=pattern,
                recursive=recursive,
            )

            self.log_operation(
                'directory_indexed',
                directory=str(directory),
                files=len(results),
                total_chunks=sum(len(ids) for ids in results.values()),
            )

            return results

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f'indexing directory {directory}')
            ) from e

    def search(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search the knowledge base for relevant documents.

        Args:
            query: Search query
            k: Number of results to return
            filter: Optional metadata filter

        Returns:
            list[dict[str, Any]]: Search results with content and metadata

        Raises:
            ServiceError: If search fails
        """
        try:
            self.validate_input(query=query)

            # Search with scores
            results_with_scores = self.rag_manager.search(
                query=query,
                k=k,
                filter=filter,
                return_scores=True,
            )

            # Format results
            formatted_results = []
            for doc, score in results_with_scores:
                result = {
                    'content': doc.page_content,
                    'score': score,
                    'metadata': doc.metadata,
                    'title': doc.metadata.get('title', 'Unknown'),
                    'source': doc.metadata.get('source', 'Unknown'),
                    'document_type': doc.metadata.get('document_type', 'Unknown'),
                }
                formatted_results.append(result)

            self.log_operation(
                'search_completed',
                query=query,
                results=len(formatted_results),
            )

            return formatted_results

        except Exception as e:
            raise ServiceError(self.handle_error(e, f"searching for '{query}'")) from e

    def ask_question(
        self,
        question: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ask a question and get an answer based on the knowledge base.

        Args:
            question: The question to ask
            k: Number of documents to retrieve for context
            filter: Optional metadata filter

        Returns:
            dict[str, Any]: Answer with sources and metadata

        Raises:
            ServiceError: If question answering fails
        """
        try:
            self.validate_input(question=question)

            response = self.rag_manager.answer_question(
                question=question,
                k=k,
                filter=filter,
                return_sources=True,
            )

            self.log_operation(
                'question_answered',
                question=question,
                sources=len(response.get('sources', [])),
            )

            return response

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f"answering question '{question}'")
            ) from e

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about the RAG system.

        Returns:
            dict[str, Any]: RAG system statistics

        Raises:
            ServiceError: If getting stats fails
        """
        try:
            stats = self.rag_manager.get_stats()
            return stats

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'getting RAG statistics')) from e

    def clear_index(self) -> None:
        """
        Clear the entire vector index.

        WARNING: This will delete all indexed documents.

        Raises:
            ServiceError: If clearing fails
        """
        try:
            self.rag_manager.clear_index()
            self.log_operation('index_cleared')

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'clearing RAG index')) from e

    def index_knowledge_base(
        self,
        markdown_dir: Path | None = None,
        notes_dir: Path | None = None,
    ) -> dict[str, Any]:
        """
        Index the entire knowledge base including markdown and notes.

        Args:
            markdown_dir: Directory containing markdown files
            notes_dir: Directory containing note files

        Returns:
            dict[str, Any]: Indexing statistics

        Raises:
            ServiceError: If indexing fails
        """
        try:
            markdown_dir = markdown_dir or self.config.markdown_dir
            notes_dir = notes_dir or self.config.notes_dir

            stats = {
                'markdown_files': 0,
                'note_files': 0,
                'total_files': 0,
                'total_chunks': 0,
                'errors': [],
            }

            # Index markdown files
            self.logger.info(f'Indexing markdown files from {markdown_dir}')
            try:
                markdown_results = self.index_directory(
                    directory=markdown_dir,
                    pattern='*.md',
                    recursive=True,
                )
                stats['markdown_files'] = len(markdown_results)
                for doc_ids in markdown_results.values():
                    stats['total_chunks'] += len(doc_ids)
            except Exception as e:
                error_msg = f'Error indexing markdown directory: {e}'
                self.logger.error(error_msg)
                stats['errors'].append(error_msg)

            # Index note files
            self.logger.info(f'Indexing note files from {notes_dir}')
            try:
                notes_results = self.index_directory(
                    directory=notes_dir,
                    pattern='*.md',
                    recursive=True,
                )
                stats['note_files'] = len(notes_results)
                for doc_ids in notes_results.values():
                    stats['total_chunks'] += len(doc_ids)
            except Exception as e:
                error_msg = f'Error indexing notes directory: {e}'
                self.logger.error(error_msg)
                stats['errors'].append(error_msg)

            stats['total_files'] = stats['markdown_files'] + stats['note_files']

            # Get current vector store stats
            rag_stats = self.get_statistics()
            stats['vector_store'] = rag_stats

            self.log_operation(
                'knowledge_base_indexed',
                total_files=stats['total_files'],
                total_chunks=stats['total_chunks'],
                errors=len(stats['errors']),
            )

            return stats

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'indexing knowledge base')) from e

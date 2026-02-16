"""
Knowledge service for managing external knowledge documents and collections.

This service orchestrates the complete workflow for external knowledge:
- Collection management
- File conversion and upload
- Database entry creation
- RAG indexing
"""

from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger

from thoth.repositories.knowledge_collection_repository import (
    KnowledgeCollectionRepository,
)
from thoth.services.file_converter import FileConverter


class KnowledgeService:
    """
    Service for managing external knowledge documents and collections.

    Coordinates between FileConverter, repositories, and RAG indexing.
    """

    def __init__(
        self,
        postgres_service,
        rag_service,
        config=None,
    ):
        """
        Initialize the knowledge service.

        Args:
            postgres_service: PostgreSQL service instance
            rag_service: RAG service instance
            config: Configuration object (optional)
        """
        self.db = postgres_service
        self.rag_service = rag_service
        self.config = config
        self.collection_repo = KnowledgeCollectionRepository(postgres_service)
        self.file_converter = FileConverter(config)

    def health_check(self) -> dict[str, str]:
        """Return basic health status."""
        return {
            'status': 'healthy',
            'service': self.__class__.__name__,
        }

    async def is_document_uploaded(self, title: str, collection_name: str) -> bool:
        """
        Check if a document with the given title already exists in a collection.

        Args:
            title: Document title to check.
            collection_name: Collection name.

        Returns:
            True if document already uploaded, False otherwise.
        """
        collection = await self.collection_repo.get_by_name(collection_name)
        if not collection:
            return False

        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id FROM paper_metadata
                WHERE title_normalized = normalize_title($1)
                AND collection_id = $2
                AND document_category = 'external'
                """,
                title,
                collection['id'],
            )
            return row is not None

    async def create_collection(
        self, name: str, description: str | None = None
    ) -> dict[str, Any]:
        """
        Create a new knowledge collection.

        Args:
            name: Collection name
            description: Optional description

        Returns:
            Collection dictionary

        Raises:
            ValueError: If collection name already exists
        """
        return await self.collection_repo.create(name, description)

    async def get_collection(
        self, collection_id: UUID | None = None, name: str | None = None
    ) -> dict[str, Any] | None:
        """
        Get a collection by ID or name.

        Args:
            collection_id: Collection UUID
            name: Collection name

        Returns:
            Collection dictionary or None
        """
        if collection_id:
            return await self.collection_repo.get_by_id(collection_id)
        elif name:
            return await self.collection_repo.get_by_name(name)
        else:
            raise ValueError('Must provide either collection_id or name')

    async def list_collections(self) -> list[dict[str, Any]]:
        """
        List all collections with document counts.

        Returns:
            List of collection dictionaries
        """
        return await self.collection_repo.list_all()

    async def delete_collection(
        self, collection_id: UUID, delete_documents: bool = False
    ) -> bool:
        """
        Delete a collection.

        Args:
            collection_id: Collection UUID
            delete_documents: If True, also delete documents in collection

        Returns:
            True if deleted, False if not found
        """
        return await self.collection_repo.delete(collection_id, delete_documents)

    async def upload_document(
        self,
        file_path: Path,
        collection_name: str,
        title: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a document to a collection.

        Complete workflow:
        1. Verify collection exists
        2. Convert file to markdown
        3. Create paper_metadata entry
        4. Create processed_papers entry
        5. Index to RAG

        Args:
            file_path: Path to file to upload
            collection_name: Collection name
            title: Document title (defaults to filename)

        Returns:
            Dictionary with paper_id and upload stats

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If collection doesn't exist or file format unsupported
        """
        if not file_path.exists():
            raise FileNotFoundError(f'File not found: {file_path}')

        if not self.file_converter.is_supported(file_path):
            supported = ', '.join(self.file_converter.get_supported_extensions())
            raise ValueError(
                f'Unsupported file format: {file_path.suffix}. Supported: {supported}'
            )

        # Get collection
        collection = await self.collection_repo.get_by_name(collection_name)
        if not collection:
            raise ValueError(f'Collection not found: {collection_name}')

        collection_id = collection['id']

        # Convert to markdown
        logger.info(f'Converting {file_path.name} to markdown...')
        markdown_content, conversion_metadata = self.file_converter.convert_to_markdown(
            file_path
        )

        # Generate title
        if not title:
            title = file_path.stem.replace('_', ' ').replace('-', ' ').title()

        # Create paper_metadata entry
        async with self.db.acquire() as conn:
            paper_row = await conn.fetchrow(
                """
                INSERT INTO paper_metadata (
                    title,
                    title_normalized,
                    collection_id,
                    document_category
                )
                VALUES ($1, normalize_title($1), $2, 'external')
                RETURNING id, title, collection_id, document_category, created_at
                """,
                title,
                collection_id,
            )

            paper_id = paper_row['id']

            # Create processed_papers entry
            await conn.execute(
                """
                INSERT INTO processed_papers (
                    paper_id,
                    markdown_content,
                    processing_status,
                    processed_at
                )
                VALUES ($1, $2, 'completed', NOW())
                """,
                paper_id,
                markdown_content,
            )

        logger.success(f'Created database entries for {title} (paper_id: {paper_id})')

        # Index to RAG
        try:
            await self.rag_service.index_paper_by_id_async(
                str(paper_id), markdown_content
            )
            logger.success(f'Indexed {title} to RAG system')
        except Exception as e:
            logger.warning(f'RAG indexing failed for {title}: {e}')

        return {
            'paper_id': str(paper_id),
            'title': title,
            'collection_id': str(collection_id),
            'collection_name': collection_name,
            'file_type': conversion_metadata.get('file_type'),
            'markdown_length': len(markdown_content),
        }

    async def bulk_upload(
        self,
        directory: Path,
        collection_name: str,
        recursive: bool = True,
    ) -> dict[str, Any]:
        """
        Upload all supported files in a directory to a collection.

        Args:
            directory: Directory containing files
            collection_name: Collection name
            recursive: Whether to search recursively

        Returns:
            Dictionary with upload statistics and errors

        Raises:
            FileNotFoundError: If directory doesn't exist
            ValueError: If collection doesn't exist
        """
        if not directory.exists():
            raise FileNotFoundError(f'Directory not found: {directory}')

        if not directory.is_dir():
            raise ValueError(f'Not a directory: {directory}')

        # Verify collection exists
        collection = await self.collection_repo.get_by_name(collection_name)
        if not collection:
            raise ValueError(f'Collection not found: {collection_name}')

        # Find all supported files
        files = []
        if recursive:
            for ext in self.file_converter.get_supported_extensions():
                files.extend(directory.rglob(f'*{ext}'))
        else:
            for ext in self.file_converter.get_supported_extensions():
                files.extend(directory.glob(f'*{ext}'))

        if not files:
            logger.warning(f'No supported files found in {directory}')
            return {
                'total_files': 0,
                'successful': 0,
                'failed': 0,
                'errors': [],
            }

        logger.info(f'Found {len(files)} files to upload to {collection_name}')

        successful = 0
        failed = 0
        errors = []

        for file_path in files:
            try:
                await self.upload_document(file_path, collection_name)
                successful += 1
                logger.info(f'[{successful}/{len(files)}] Uploaded: {file_path.name}')
            except Exception as e:
                failed += 1
                error_msg = f'{file_path.name}: {e!s}'
                errors.append(error_msg)
                logger.error(f'Failed to upload {file_path.name}: {e}')

        logger.success(
            f'Bulk upload complete: {successful} successful, {failed} failed'
        )

        return {
            'total_files': len(files),
            'successful': successful,
            'failed': failed,
            'errors': errors,
        }

    async def search_external_knowledge(
        self,
        query: str,
        collection_name: str | None = None,
        k: int = 4,
    ) -> list[dict[str, Any]]:
        """
        Search within external knowledge documents.

        Args:
            query: Search query
            collection_name: Optional collection to search within
            k: Number of results

        Returns:
            List of search results
        """
        # Build filter
        filter_dict = {'document_category': 'external'}

        if collection_name:
            collection = await self.collection_repo.get_by_name(collection_name)
            if collection:
                filter_dict['collection_id'] = str(collection['id'])

        # Search using RAG service
        results = await self.rag_service.search_async(
            query=query,
            k=k,
            filter=filter_dict,
        )

        return results

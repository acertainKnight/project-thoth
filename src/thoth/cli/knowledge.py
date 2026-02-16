"""CLI commands for external knowledge management."""

from pathlib import Path

from loguru import logger

from thoth.config import config
from thoth.services.knowledge_service import KnowledgeService
from thoth.services.postgres_service import PostgresService
from thoth.services.rag_service import RAGService


def configure_subparser(subparsers):
    """Configure the knowledge subparser."""
    knowledge_parser = subparsers.add_parser(
        'knowledge',
        help='Manage external knowledge collections and documents',
    )

    knowledge_subparsers = knowledge_parser.add_subparsers(
        dest='knowledge_command',
        help='Knowledge management command',
        required=True,
    )

    # Collections command
    collections_parser = knowledge_subparsers.add_parser(
        'collections',
        help='List all knowledge collections',
    )
    collections_parser.set_defaults(func=list_collections_cmd)

    # Create collection command
    create_parser = knowledge_subparsers.add_parser(
        'create',
        help='Create a new knowledge collection',
    )
    create_parser.add_argument('name', help='Collection name')
    create_parser.add_argument(
        '--description',
        help='Collection description',
    )
    create_parser.set_defaults(func=create_collection_cmd)

    # Delete collection command
    delete_parser = knowledge_subparsers.add_parser(
        'delete',
        help='Delete a knowledge collection',
    )
    delete_parser.add_argument('name', help='Collection name')
    delete_parser.add_argument(
        '--delete-documents',
        action='store_true',
        help='Also delete all documents in the collection',
    )
    delete_parser.set_defaults(func=delete_collection_cmd)

    # Upload command
    upload_parser = knowledge_subparsers.add_parser(
        'upload',
        help='Upload documents to a collection',
    )
    upload_parser.add_argument('path', help='File or directory path')
    upload_parser.add_argument('--collection', required=True, help='Collection name')
    upload_parser.add_argument(
        '--recursive',
        action='store_true',
        help='Recursively process directories',
    )
    upload_parser.set_defaults(func=upload_cmd)


def _get_knowledge_service() -> KnowledgeService:
    """Get initialized knowledge service."""
    postgres_service = PostgresService(config)
    rag_service = RAGService(config)
    return KnowledgeService(postgres_service, rag_service, config)


async def list_collections_cmd(_args):
    """List all knowledge collections."""
    try:
        knowledge_service = _get_knowledge_service()
        collections = await knowledge_service.list_collections()

        if not collections:
            logger.info('No knowledge collections found')
            logger.info('Create one with: thoth knowledge create <name>')
            return

        logger.info(f'Found {len(collections)} knowledge collection(s):\n')

        for collection in collections:
            logger.info(f'  {collection["name"]}')
            if collection.get('description'):
                logger.info(f'    Description: {collection["description"]}')
            logger.info(f'    Documents: {collection["document_count"]}')
            logger.info(f'    ID: {collection["id"]}')
            logger.info('')

    except Exception as e:
        logger.error(f'Failed to list collections: {e}')
        raise


async def create_collection_cmd(args):
    """Create a new knowledge collection."""
    try:
        knowledge_service = _get_knowledge_service()

        collection = await knowledge_service.create_collection(
            args.name,
            args.description,
        )

        logger.success(f'Created collection: {collection["name"]}')
        logger.info(f'  ID: {collection["id"]}')
        if collection.get('description'):
            logger.info(f'  Description: {collection["description"]}')

        logger.info(
            f'\nUpload documents with: thoth knowledge upload <path> --collection "{args.name}"'
        )

    except ValueError as e:
        logger.error(f'Failed to create collection: {e}')
        raise
    except Exception as e:
        logger.error(f'Failed to create collection: {e}')
        raise


async def delete_collection_cmd(args):
    """Delete a knowledge collection."""
    try:
        knowledge_service = _get_knowledge_service()

        # Get collection first
        collection = await knowledge_service.get_collection(name=args.name)
        if not collection:
            logger.error(f'Collection not found: {args.name}')
            return

        doc_count = collection.get('document_count', 0)

        # Confirm deletion if it has documents
        if doc_count > 0 and not args.delete_documents:
            logger.warning(f'Collection "{args.name}" contains {doc_count} documents')
            logger.info('Documents will remain but will no longer be in a collection')
            logger.info('Use --delete-documents to also delete the documents')

        from uuid import UUID

        collection_id = UUID(collection['id'])
        deleted = await knowledge_service.delete_collection(
            collection_id, args.delete_documents
        )

        if deleted:
            if args.delete_documents:
                logger.success(
                    f'Deleted collection "{args.name}" and {doc_count} documents'
                )
            else:
                logger.success(f'Deleted collection "{args.name}"')
        else:
            logger.error(f'Failed to delete collection: {args.name}')

    except Exception as e:
        logger.error(f'Failed to delete collection: {e}')
        raise


async def upload_cmd(args):
    """Upload documents to a collection."""
    try:
        path = Path(args.path)

        if not path.exists():
            logger.error(f'Path not found: {path}')
            return

        knowledge_service = _get_knowledge_service()

        if path.is_file():
            # Upload single file
            logger.info(f'Uploading {path.name} to collection "{args.collection}"...')

            result = await knowledge_service.upload_document(
                path,
                args.collection,
            )

            logger.success(f'Uploaded: {result["title"]}')
            logger.info(f'  Paper ID: {result["paper_id"]}')
            logger.info(f'  File Type: {result["file_type"]}')
            logger.info(f'  Content Length: {result["markdown_length"]:,} characters')

        elif path.is_dir():
            # Bulk upload directory
            logger.info(
                f'Uploading files from {path} to collection "{args.collection}"...'
            )
            if args.recursive:
                logger.info('Searching recursively...')

            result = await knowledge_service.bulk_upload(
                path,
                args.collection,
                args.recursive,
            )

            logger.success(
                f'\nUpload complete: {result["successful"]}/{result["total_files"]} files'
            )

            if result['failed'] > 0:
                logger.warning(f'\n{result["failed"]} file(s) failed:')
                for error in result['errors'][:10]:  # Show first 10 errors
                    logger.warning(f'  - {error}')
                if len(result['errors']) > 10:
                    logger.warning(f'  ... and {len(result["errors"]) - 10} more')

        else:
            logger.error(f'Invalid path: {path}')

    except ValueError as e:
        logger.error(f'Upload failed: {e}')
        raise
    except Exception as e:
        logger.error(f'Upload failed: {e}')
        raise

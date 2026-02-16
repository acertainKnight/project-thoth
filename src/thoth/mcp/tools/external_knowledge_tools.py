"""
MCP tools for managing external knowledge collections and documents.

Provides tools for creating collections, uploading documents, and searching
external knowledge sources (textbooks, background material, etc.).
"""

from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger

from ..base_tools import MCPTool, MCPToolCallResult


class CreateKnowledgeCollectionMCPTool(MCPTool):
    """Create a new knowledge collection for organizing external documents."""

    @property
    def name(self) -> str:
        return 'create_knowledge_collection'

    @property
    def description(self) -> str:
        return (
            'Create a new knowledge collection to organize external documents like '
            'textbooks, lecture notes, and background material. Collections help '
            'group related documents by topic or subject area.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': 'Collection name (must be unique)',
                },
                'description': {
                    'type': 'string',
                    'description': 'Optional description of the collection',
                },
            },
            'required': ['name'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create a knowledge collection."""
        try:
            name = arguments['name']
            description = arguments.get('description')

            knowledge_service = self.service_manager.knowledge

            collection = await knowledge_service.create_collection(name, description)

            response = f'**Collection Created: {name}**\n\n'
            response += f'- ID: {collection["id"]}\n'
            response += f'- Name: {collection["name"]}\n'
            if description:
                response += f'- Description: {collection["description"]}\n'
            response += f'- Created: {collection["created_at"]}\n\n'
            response += 'You can now upload documents to this collection using upload_external_knowledge.'

            return MCPToolCallResult(content=[{'type': 'text', 'text': response}])

        except ValueError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error: {e!s}'}],
                isError=True,
            )
        except Exception as e:
            return self.handle_error(e)


class ListKnowledgeCollectionsMCPTool(MCPTool):
    """List all knowledge collections with document counts."""

    @property
    def name(self) -> str:
        return 'list_knowledge_collections'

    @property
    def description(self) -> str:
        return (
            'List all available knowledge collections with document counts. '
            'Use this to see what external knowledge is available.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {'type': 'object', 'properties': {}}

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """List all collections."""
        try:
            knowledge_service = self.service_manager.knowledge

            collections = await knowledge_service.list_collections()

            if not collections:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'No knowledge collections found. Create one using create_knowledge_collection.',
                        }
                    ]
                )

            response = f'**Knowledge Collections ({len(collections)} total)**\n\n'

            for collection in collections:
                response += f'**{collection["name"]}**\n'
                response += f'- ID: {collection["id"]}\n'
                response += f'- Documents: {collection["document_count"]}\n'
                if collection.get('description'):
                    response += f'- Description: {collection["description"]}\n'
                response += '\n'

            return MCPToolCallResult(content=[{'type': 'text', 'text': response}])

        except Exception as e:
            return self.handle_error(e)


class DeleteKnowledgeCollectionMCPTool(MCPTool):
    """Delete a knowledge collection."""

    @property
    def name(self) -> str:
        return 'delete_knowledge_collection'

    @property
    def description(self) -> str:
        return (
            'Delete a knowledge collection. You can choose whether to delete the '
            'documents in it or keep them (they will no longer be part of any collection).'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'collection_name': {
                    'type': 'string',
                    'description': 'Name of the collection to delete',
                },
                'delete_documents': {
                    'type': 'boolean',
                    'description': 'If true, also delete all documents in the collection',
                    'default': False,
                },
            },
            'required': ['collection_name'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Delete a knowledge collection."""
        try:
            collection_name = arguments['collection_name']
            delete_documents = arguments.get('delete_documents', False)

            knowledge_service = self.service_manager.knowledge

            collection = await knowledge_service.get_collection(name=collection_name)
            if not collection:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Collection not found: {collection_name}',
                        }
                    ],
                    isError=True,
                )

            collection_id = UUID(collection['id'])
            doc_count = collection.get('document_count', 0)

            deleted = await knowledge_service.delete_collection(
                collection_id, delete_documents
            )

            if deleted:
                response = f'**Collection Deleted: {collection_name}**\n\n'
                if delete_documents:
                    response += f'- Deleted collection and {doc_count} documents\n'
                else:
                    response += f'- Deleted collection (kept {doc_count} documents)\n'
                return MCPToolCallResult(content=[{'type': 'text', 'text': response}])
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Failed to delete collection: {collection_name}',
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class UploadExternalKnowledgeMCPTool(MCPTool):
    """Upload a document to a knowledge collection."""

    @property
    def name(self) -> str:
        return 'upload_external_knowledge'

    @property
    def description(self) -> str:
        return (
            'Upload a document (PDF, Markdown, TXT, HTML, EPUB, or DOCX) to a knowledge '
            'collection. The document will be converted to markdown, indexed into the RAG '
            'system, and become searchable. Supports textbooks, lecture notes, background '
            'material, and other external knowledge sources.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'file_path': {
                    'type': 'string',
                    'description': 'Path to the file to upload (must exist in the vault)',
                },
                'collection_name': {
                    'type': 'string',
                    'description': 'Name of the collection to add the document to',
                },
                'title': {
                    'type': 'string',
                    'description': 'Optional title for the document (defaults to filename)',
                },
            },
            'required': ['file_path', 'collection_name'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Upload a document to a collection."""
        try:
            file_path_str = arguments['file_path']
            collection_name = arguments['collection_name']
            title = arguments.get('title')

            file_path = Path(file_path_str)

            if not file_path.exists():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'File not found: {file_path}\n\n'
                            'Make sure the file exists in your vault or provide the full path.',
                        }
                    ],
                    isError=True,
                )

            knowledge_service = self.service_manager.knowledge

            logger.info(
                f'Uploading {file_path.name} to collection {collection_name}...'
            )

            result = await knowledge_service.upload_document(
                file_path, collection_name, title
            )

            response = '**Document Uploaded Successfully**\n\n'
            response += f'- Title: {result["title"]}\n'
            response += f'- Collection: {result["collection_name"]}\n'
            response += f'- File Type: {result["file_type"]}\n'
            response += f'- Paper ID: {result["paper_id"]}\n'
            response += (
                f'- Content Length: {result["markdown_length"]:,} characters\n\n'
            )
            response += 'The document has been indexed and is now searchable using search_external_knowledge.'

            return MCPToolCallResult(content=[{'type': 'text', 'text': response}])

        except ValueError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error: {e!s}'}],
                isError=True,
            )
        except Exception as e:
            return self.handle_error(e)


class SearchExternalKnowledgeMCPTool(MCPTool):
    """Search within external knowledge documents."""

    @property
    def name(self) -> str:
        return 'search_external_knowledge'

    @property
    def description(self) -> str:
        return (
            'Search within external knowledge sources (textbooks, lecture notes, etc.). '
            'Can search across all external knowledge or within a specific collection. '
            'Returns relevant chunks with context and citations.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'Search query (natural language question or keywords)',
                },
                'collection_name': {
                    'type': 'string',
                    'description': 'Optional: limit search to a specific collection',
                },
                'max_results': {
                    'type': 'integer',
                    'description': 'Maximum number of results to return (default 4)',
                    'default': 4,
                    'minimum': 1,
                    'maximum': 20,
                },
            },
            'required': ['query'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Search external knowledge."""
        try:
            query = arguments['query']
            collection_name = arguments.get('collection_name')
            max_results = arguments.get('max_results', 4)

            knowledge_service = self.service_manager.knowledge

            results = await knowledge_service.search_external_knowledge(
                query, collection_name, max_results
            )

            if not results:
                scope = (
                    f'collection "{collection_name}"'
                    if collection_name
                    else 'external knowledge'
                )
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'No results found for "{query}" in {scope}',
                        }
                    ]
                )

            scope_msg = f' in collection "{collection_name}"' if collection_name else ''
            response = f'**Search Results for "{query}"{scope_msg}**\n\n'
            response += f'Found {len(results)} relevant chunks:\n\n'

            for i, result in enumerate(results, 1):
                content = result.get('content', '')
                metadata = result.get('metadata', {})

                response += f'**Result {i}:**\n'
                response += f'- Source: {metadata.get("title", "Unknown")}\n'
                if metadata.get('collection_name'):
                    response += f'- Collection: {metadata["collection_name"]}\n'
                if metadata.get('similarity'):
                    response += f'- Relevance: {metadata["similarity"]:.3f}\n'
                response += f'\n{content}\n\n'
                response += '---\n\n'

            return MCPToolCallResult(content=[{'type': 'text', 'text': response}])

        except Exception as e:
            return self.handle_error(e)

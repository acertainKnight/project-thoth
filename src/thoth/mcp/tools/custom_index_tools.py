"""
MCP-compliant custom index search tools.

This module provides tools for searching and managing custom indexes.
"""

from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult, normalize_authors


class SearchCustomIndexMCPTool(MCPTool):
    """MCP tool for searching within custom indexes."""

    @property
    def name(self) -> str:
        return 'search_custom_index'

    @property
    def description(self) -> str:
        return 'Search within a specific custom index for more focused results'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'index_name': {
                    'type': 'string',
                    'description': 'Name of the custom index to search',
                },
                'query': {
                    'type': 'string',
                    'description': 'Search query',
                },
                'max_results': {
                    'type': 'integer',
                    'description': 'Maximum number of results to return',
                    'default': 10,
                    'minimum': 1,
                    'maximum': 100,
                },
                'include_content': {
                    'type': 'boolean',
                    'description': 'Include document content in results',
                    'default': False,
                },
            },
            'required': ['index_name', 'query'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Search custom index."""
        try:
            index_name = arguments['index_name']
            query = arguments['query']
            max_results = arguments.get('max_results', 10)
            include_content = arguments.get('include_content', False)

            # Load custom index
            try:
                custom_indexes_dir = (
                    self.service_manager.config.data_dir / 'custom_indexes'
                )
                index_file = custom_indexes_dir / f'{index_name}.json'

                if not index_file.exists():
                    available_indexes = (
                        [f.stem for f in custom_indexes_dir.glob('*.json')]
                        if custom_indexes_dir.exists()
                        else []
                    )
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f"Custom index '{index_name}' not found.\n\nAvailable indexes: {', '.join(available_indexes) if available_indexes else 'None'}",
                            }
                        ],
                        isError=True,
                    )

                with open(index_file) as f:
                    import json

                    custom_index = json.load(f)

            except Exception as load_error:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Failed to load custom index: {load_error}',
                        }
                    ],
                    isError=True,
                )

            response_text = f'**Custom Index Search: {index_name}**\n\n'
            response_text += f'**Query:** {query}\n'
            response_text += '**Index Info:**\n'
            response_text += (
                f'- Created: {custom_index.get("created_date", "Unknown")}\n'
            )
            response_text += f'- Topic: {custom_index.get("topic_filter", "N/A")}\n'
            response_text += f'- Documents: {custom_index.get("document_count", 0)}\n\n'

            # Search within custom index documents
            documents = custom_index.get('documents', [])

            # Simple text-based filtering (more sophisticated search would use
            # embeddings)
            query_lower = query.lower()
            matching_docs = []

            for doc in documents:
                # Score based on title match, content preview match
                score = 0
                title = doc.get('title', '').lower()
                content_preview = doc.get('content_preview', '').lower()

                # Title matches get higher score
                if query_lower in title:
                    score += 2
                elif any(word in title for word in query_lower.split()):
                    score += 1

                # Content matches
                if query_lower in content_preview:
                    score += 1
                elif any(word in content_preview for word in query_lower.split()):
                    score += 0.5

                if score > 0:
                    doc['search_score'] = score
                    matching_docs.append(doc)

            # Sort by search score
            matching_docs.sort(key=lambda x: x.get('search_score', 0), reverse=True)
            matching_docs = matching_docs[:max_results]

            if not matching_docs:
                response_text += f"**No Results Found**\n\nNo documents in the '{index_name}' index match your query: '{query}'"
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text}]
                )

            response_text += (
                f'**Search Results:** {len(matching_docs)} documents found\n\n'
            )

            # Display results
            for i, doc in enumerate(matching_docs, 1):
                title = doc.get('title', 'Untitled')
                doc_type = doc.get('document_type', 'unknown')
                original_score = doc.get('score', 0)
                search_score = doc.get('search_score', 0)

                response_text += f'**{i}. {title}**\n'
                response_text += f'- Type: {doc_type}\n'
                response_text += f'- Relevance: {original_score:.3f} (original), {search_score:.1f} (search)\n'

                # Include metadata if available
                metadata = doc.get('metadata', {})
                authors = normalize_authors(metadata.get('authors'))
                if authors:
                    authors_str = ', '.join(authors[:3])
                    if len(authors) > 3:
                        authors_str += ' et al.'
                    response_text += f'- Authors: {authors_str}\n'

                if metadata.get('publication_date'):
                    response_text += f'- Date: {metadata["publication_date"]}\n'

                # Include content preview
                content_preview = doc.get('content_preview', 'No preview available')
                response_text += f'- Preview: {content_preview}\n'

                if include_content and 'content' in doc:
                    response_text += f'- Full Content: {doc["content"][:500]}...\n'

                response_text += '\n'

            response_text += f"**Search completed in custom index '{index_name}'**\n"
            response_text += (
                f'Showing {len(matching_docs)} of {len(documents)} documents in index.'
            )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class ListCustomIndexesMCPTool(MCPTool):
    """MCP tool for listing all custom indexes."""

    @property
    def name(self) -> str:
        return 'list_custom_indexes'

    @property
    def description(self) -> str:
        return 'List all available custom indexes with their details'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {'type': 'object', 'properties': {}}

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:  # noqa: ARG002
        """List custom indexes."""
        try:
            custom_indexes_dir = self.service_manager.config.data_dir / 'custom_indexes'

            if not custom_indexes_dir.exists():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '**No Custom Indexes Found**\n\nThe custom indexes directory does not exist yet.\n\nUse `create_custom_index` to create your first specialized index.',
                        }
                    ]
                )

            index_files = list(custom_indexes_dir.glob('*.json'))

            if not index_files:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '**No Custom Indexes Found**\n\nNo custom indexes have been created yet.\n\nUse `create_custom_index` to create your first specialized index.',
                        }
                    ]
                )

            response_text = f'**Custom Indexes ({len(index_files)} found)**\n\n'

            total_documents = 0

            for index_file in sorted(index_files):
                try:
                    with open(index_file) as f:
                        import json

                        custom_index = json.load(f)

                    index_name = custom_index.get('name', index_file.stem)
                    topic_filter = custom_index.get('topic_filter', 'N/A')
                    document_count = custom_index.get('document_count', 0)
                    created_date = custom_index.get('created_date', 'Unknown')
                    document_types = custom_index.get('document_types', [])

                    total_documents += document_count

                    response_text += f'**{index_name}**\n'
                    response_text += f'- Topic: {topic_filter}\n'
                    response_text += f'- Documents: {document_count}\n'
                    response_text += f'- Created: {created_date[:10] if created_date != "Unknown" else "Unknown"}\n'

                    if document_types:
                        response_text += f'- Types: {", ".join(document_types)}\n'

                    response_text += f'- File: {index_file.name}\n\n'

                except Exception as read_error:
                    response_text += (
                        f'**{index_file.stem}** (Error reading: {read_error})\n\n'
                    )

            response_text += '**Summary:**\n'
            response_text += f'- Total custom indexes: {len(index_files)}\n'
            response_text += f'- Total indexed documents: {total_documents}\n'
            response_text += f'- Storage location: {custom_indexes_dir}\n\n'

            response_text += '**Usage:**\n'
            response_text += (
                '- Use `search_custom_index` to search within a specific index\n'
            )
            response_text += (
                '- Use `create_custom_index` to create new specialized indexes'
            )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)

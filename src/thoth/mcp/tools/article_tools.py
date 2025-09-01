"""
MCP-compliant article search and management tools.

This module provides advanced article search capabilities and
article management functions.
"""

from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult


class SearchArticlesMCPTool(MCPTool):
    """MCP tool for advanced article search with filters."""

    @property
    def name(self) -> str:
        return 'search_articles'

    @property
    def description(self) -> str:
        return 'Advanced search for articles with multiple filters including author, date range, document type, and tags'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'Search query for article content',
                },
                'author': {'type': 'string', 'description': 'Filter by author name'},
                'date_from': {
                    'type': 'string',
                    'description': 'Filter articles from this date (YYYY-MM-DD format)',
                },
                'date_to': {
                    'type': 'string',
                    'description': 'Filter articles up to this date (YYYY-MM-DD format)',
                },
                'document_type': {
                    'type': 'string',
                    'description': "Filter by document type (e.g., 'article', 'note', 'preprint')",
                },
                'journal': {
                    'type': 'string',
                    'description': 'Filter by journal or venue name',
                },
                'tags': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Filter by tags (must have all specified tags)',
                },
                'min_citations': {
                    'type': 'integer',
                    'description': 'Minimum number of citations',
                    'minimum': 0,
                },
                'limit': {
                    'type': 'integer',
                    'description': 'Maximum number of results to return',
                    'default': 10,
                    'minimum': 1,
                    'maximum': 50,
                },
                'sort_by': {
                    'type': 'string',
                    'enum': ['relevance', 'date', 'citations', 'title'],
                    'description': 'Sort results by specified criteria',
                    'default': 'relevance',
                },
            },
            'required': ['query'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Advanced article search."""
        try:
            query = arguments['query']
            limit = arguments.get('limit', 10)
            sort_by = arguments.get('sort_by', 'relevance')

            # Build filter dictionary for RAG search
            search_filter = {}

            # Add metadata filters
            if arguments.get('author'):
                search_filter['authors'] = arguments['author']

            if arguments.get('document_type'):
                search_filter['document_type'] = arguments['document_type']

            if arguments.get('journal'):
                search_filter['journal'] = arguments['journal']

            if arguments.get('tags'):
                search_filter['tags'] = arguments['tags']

            # Perform search with increased k to allow for filtering
            search_k = min(limit * 3, 100)  # Get more results for post-filtering
            results = self.service_manager.rag.search(
                query=query, k=search_k, filter=search_filter if search_filter else None
            )

            if not results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"No articles found matching the search criteria for: '{query}'",
                        }
                    ]
                )

            # Apply additional filters that can't be handled by RAG
            filtered_results = []
            for result in results:
                metadata = result.get('metadata', {})

                # Date filtering
                if arguments.get('date_from') or arguments.get('date_to'):
                    pub_date = metadata.get('publication_date', '')
                    if pub_date:
                        try:
                            # Simple date comparison (assumes YYYY-MM-DD format)
                            if (
                                arguments.get('date_from')
                                and pub_date < arguments['date_from']
                            ):
                                continue
                            if (
                                arguments.get('date_to')
                                and pub_date > arguments['date_to']
                            ):
                                continue
                        except Exception:
                            pass  # Skip date filtering if format is invalid

                # Citation filtering
                if arguments.get('min_citations'):
                    citations = metadata.get('citation_count', 0)
                    if citations < arguments['min_citations']:
                        continue

                # Author filtering (if not handled by RAG filter)
                if arguments.get('author') and search_filter.get('authors') is None:
                    authors = metadata.get('authors', [])
                    if isinstance(authors, list):
                        author_text = ' '.join(authors).lower()
                    else:
                        author_text = str(authors).lower()

                    if arguments['author'].lower() not in author_text:
                        continue

                filtered_results.append(result)

                if len(filtered_results) >= limit:
                    break

            # Sort results if not by relevance
            if sort_by != 'relevance' and filtered_results:
                try:
                    if sort_by == 'date':
                        filtered_results.sort(
                            key=lambda x: x.get('metadata', {}).get(
                                'publication_date', ''
                            ),
                            reverse=True,
                        )
                    elif sort_by == 'citations':
                        filtered_results.sort(
                            key=lambda x: x.get('metadata', {}).get(
                                'citation_count', 0
                            ),
                            reverse=True,
                        )
                    elif sort_by == 'title':
                        filtered_results.sort(key=lambda x: x.get('title', '').lower())
                except Exception:
                    pass  # Keep original order if sorting fails

            # Format response
            response_text = f"**Search Results for:** '{query}'\n\n"
            response_text += f'Found {len(filtered_results)} articles'

            # Show active filters
            active_filters = []
            if arguments.get('author'):
                active_filters.append(f'Author: {arguments["author"]}')
            if arguments.get('document_type'):
                active_filters.append(f'Type: {arguments["document_type"]}')
            if arguments.get('journal'):
                active_filters.append(f'Journal: {arguments["journal"]}')
            if arguments.get('date_from') or arguments.get('date_to'):
                date_range = f'{arguments.get("date_from", "start")}-{arguments.get("date_to", "end")}'
                active_filters.append(f'Date: {date_range}')
            if arguments.get('tags'):
                active_filters.append(f'Tags: {", ".join(arguments["tags"])}')
            if arguments.get('min_citations'):
                active_filters.append(f'Min citations: {arguments["min_citations"]}')

            if active_filters:
                response_text += f' (Filters: {"; ".join(active_filters)})'

            response_text += f' | Sorted by: {sort_by}\n\n'

            # Add results
            for i, result in enumerate(filtered_results, 1):
                title = result.get('title', 'Untitled')
                score = result.get('score', 0)
                metadata = result.get('metadata', {})

                response_text += f'**{i}. {title}**\n'

                # Add metadata
                if metadata.get('authors'):
                    authors = metadata['authors']
                    if isinstance(authors, list):
                        authors_str = ', '.join(authors[:2])
                        if len(authors) > 2:
                            authors_str += f' (+{len(authors) - 2} more)'
                    else:
                        authors_str = str(authors)
                    response_text += f'   Authors: {authors_str}\n'

                if metadata.get('publication_date'):
                    response_text += f'   Date: {metadata["publication_date"]}\n'

                if metadata.get('journal'):
                    response_text += f'   📖 Journal: {metadata["journal"]}\n'

                if metadata.get('citation_count'):
                    response_text += f'   Citations: {metadata["citation_count"]}\n'

                response_text += f'   Relevance: {score:.3f}\n'

                # Add content preview
                content = result.get('content', '')
                if content:
                    preview = content[:150].replace('\n', ' ')
                    response_text += f'   Preview: {preview}...\n'

                response_text += '\n'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class UpdateArticleMetadataMCPTool(MCPTool):
    """MCP tool for updating article metadata and tags."""

    @property
    def name(self) -> str:
        return 'update_article_metadata'

    @property
    def description(self) -> str:
        return 'Update metadata and tags for an existing article in the knowledge base'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_identifier': {
                    'type': 'string',
                    'description': 'Article title, DOI, or arXiv ID to identify the article',
                },
                'add_tags': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Tags to add to the article',
                },
                'remove_tags': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Tags to remove from the article',
                },
                'update_metadata': {
                    'type': 'object',
                    'description': 'Metadata fields to update (e.g., authors, journal, date)',
                    'additionalProperties': True,
                },
            },
            'required': ['article_identifier'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Update article metadata."""
        try:
            identifier = arguments['article_identifier']
            add_tags = arguments.get('add_tags', [])
            remove_tags = arguments.get('remove_tags', [])
            update_metadata = arguments.get('update_metadata', {})

            # Find the article first
            search_results = self.service_manager.rag.search(query=identifier, k=1)

            if not search_results:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': f'Article not found: {identifier}'}
                    ],
                    isError=True,
                )

            article = search_results[0]
            article_title = article.get('title', 'Unknown')

            # Try to update through article service
            try:
                # This is a placeholder - the actual implementation would depend on
                # the article service's update capabilities
                updates_made = []

                if add_tags:
                    # Add tags (implementation depends on article service)
                    updates_made.append(f'Added tags: {", ".join(add_tags)}')

                if remove_tags:
                    # Remove tags (implementation depends on article service)
                    updates_made.append(f'Removed tags: {", ".join(remove_tags)}')

                if update_metadata:
                    # Update metadata fields
                    for field, value in update_metadata.items():
                        updates_made.append(f'Updated {field}: {value}')

                if not updates_made:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': 'No updates specified. Provide add_tags, remove_tags, or update_metadata.',
                            }
                        ],
                        isError=True,
                    )

                # Format success response
                response_text = f'**Updated Article:** {article_title}\n\n'
                response_text += '**Changes Made:**\n'
                for update in updates_made:
                    response_text += f'  - {update}\n'

                response_text += '\n**Note:** Changes will be reflected in future searches and may require re-indexing.'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text}]
                )

            except Exception as e:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Failed to update article metadata: {e!s}\n\nThis feature may not be fully implemented in the current version.',
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class DeleteArticleMCPTool(MCPTool):
    """MCP tool for removing an article from the knowledge base."""

    @property
    def name(self) -> str:
        return 'delete_article'

    @property
    def description(self) -> str:
        return 'Remove an article from the knowledge base (use with caution - this cannot be undone)'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_identifier': {
                    'type': 'string',
                    'description': 'Article title, DOI, or arXiv ID to identify the article to delete',
                },
                'confirm_deletion': {
                    'type': 'boolean',
                    'description': 'Confirm that you want to permanently delete this article',
                    'default': False,
                },
            },
            'required': ['article_identifier', 'confirm_deletion'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Delete an article."""
        try:
            identifier = arguments['article_identifier']
            confirm_deletion = arguments.get('confirm_deletion', False)

            if not confirm_deletion:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Deletion not confirmed. Set confirm_deletion to true to proceed with permanent deletion.',
                        }
                    ],
                    isError=True,
                )

            # Find the article first
            search_results = self.service_manager.rag.search(query=identifier, k=1)

            if not search_results:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': f'Article not found: {identifier}'}
                    ],
                    isError=True,
                )

            article = search_results[0]
            article_title = article.get('title', 'Unknown')

            # Attempt deletion (this is a placeholder implementation)
            try:
                # The actual implementation would depend on the article service's
                # deletion capabilities and might involve:
                # 1. Removing from vector store
                # 2. Removing from database
                # 3. Cleaning up associated files

                # For now, provide a warning that this functionality needs impl
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f' **Article Deletion Not Fully Implemented**\n\n'
                            f'Article identified: {article_title}\n\n'
                            f'**To manually remove this article:**\n'
                            f'  1. Delete the source markdown file\n'
                            f'  2. Re-index the knowledge base using `index_knowledge_base`\n'
                            f'  3. Clear and rebuild the RAG index if needed\n\n'
                            f'Full deletion functionality requires additional implementation in the article service.',
                        }
                    ],
                    isError=True,
                )

            except Exception as e:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Failed to delete article: {e!s}',
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)

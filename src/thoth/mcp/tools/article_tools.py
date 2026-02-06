"""
MCP-compliant article search and management tools.

This module provides advanced article search capabilities and
article management functions.
"""

from typing import Any

from loguru import logger

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
            results = await self.service_manager.rag.search_async(
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
                    response_text += f'    Journal: {metadata["journal"]}\n'

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
                    'description': 'Metadata fields to update (e.g., authors, journal, abstract)',
                    'properties': {
                        'title': {'type': 'string', 'description': 'Updated title'},
                        'authors': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'List of author names',
                        },
                        'abstract': {'type': 'string', 'description': 'Updated abstract'},
                        'journal': {'type': 'string', 'description': 'Journal or venue name'},
                        'publication_date': {
                            'type': 'string',
                            'description': 'Publication date (YYYY-MM-DD)',
                        },
                        'doi': {'type': 'string', 'description': 'Digital Object Identifier'},
                        'arxiv_id': {'type': 'string', 'description': 'arXiv identifier'},
                        'url': {'type': 'string', 'description': 'URL to the article'},
                        'citation_count': {'type': 'integer', 'description': 'Number of citations'},
                    },
                    'additionalProperties': False,
                },
            },
            'required': ['article_identifier'],
            'additionalProperties': False,
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Update article metadata."""
        try:
            identifier = arguments['article_identifier']
            add_tags = arguments.get('add_tags', [])
            remove_tags = arguments.get('remove_tags', [])
            update_metadata = arguments.get('update_metadata', {})

            # Check if any updates are specified
            if not add_tags and not remove_tags and not update_metadata:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'No updates specified. Provide add_tags, remove_tags, or update_metadata.',
                        }
                    ],
                    isError=True,
                )

            # Import PaperRepository for direct database access
            from thoth.repositories.paper_repository import PaperRepository

            postgres_service = self.service_manager.postgres
            paper_repo = PaperRepository(postgres_service)

            # Try to find the paper by different identifiers
            paper = None
            paper_id = None

            # Check if identifier looks like a DOI
            if identifier.startswith('10.') or 'doi.org' in identifier:
                doi = identifier.replace('https://doi.org/', '').replace('http://doi.org/', '')
                paper = await paper_repo.get_by_doi(doi)
                if paper:
                    paper_id = paper.get('id')
                    logger.info(f'Found paper by DOI: {doi}')

            # Check if identifier looks like an arXiv ID
            elif any(c.isdigit() for c in identifier) and (
                'arxiv' in identifier.lower() or '.' in identifier
            ):
                arxiv_id = identifier.replace('arXiv:', '').replace('arxiv:', '').strip()
                paper = await paper_repo.get_by_arxiv_id(arxiv_id)
                if paper:
                    paper_id = paper.get('id')
                    logger.info(f'Found paper by arXiv ID: {arxiv_id}')

            # Try title search if not found by ID
            if not paper:
                title_results = await paper_repo.search_by_title(identifier, limit=1)
                if title_results:
                    paper = title_results[0]
                    paper_id = paper.get('id')
                    logger.info(f'Found paper by title search: {identifier}')

            # Also try RAG search as fallback
            if not paper:
                rag_results = await self.service_manager.rag.search_async(
                    query=identifier, k=1
                )
                if rag_results:
                    # Try to extract paper ID from RAG result metadata
                    rag_result = rag_results[0]
                    metadata = rag_result.get('metadata', {})
                    if metadata.get('paper_id'):
                        paper = await paper_repo.get(metadata['paper_id'])
                        if paper:
                            paper_id = paper.get('id')
                            logger.info(f'Found paper via RAG search: {identifier}')

            if not paper or not paper_id:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Article not found: {identifier}\n\n'
                            'Try using the exact DOI, arXiv ID, or full title.',
                        }
                    ],
                    isError=True,
                )

            article_title = paper.get('title', 'Unknown')
            current_tags = paper.get('tags', []) or []
            updates_made = []

            # Process tag updates
            new_tags = list(current_tags)  # Copy current tags

            if add_tags:
                for tag in add_tags:
                    tag_clean = tag.strip().lower()
                    if tag_clean and tag_clean not in new_tags:
                        new_tags.append(tag_clean)
                updates_made.append(f'Added tags: {", ".join(add_tags)}')

            if remove_tags:
                removed = []
                for tag in remove_tags:
                    tag_clean = tag.strip().lower()
                    if tag_clean in new_tags:
                        new_tags.remove(tag_clean)
                        removed.append(tag_clean)
                if removed:
                    updates_made.append(f'Removed tags: {", ".join(removed)}')

            # Update tags if changed
            if new_tags != current_tags:
                success = await paper_repo.update_tags(paper_id, new_tags)
                if not success:
                    logger.warning(f'Failed to update tags for paper {paper_id}')

            # Process metadata updates
            if update_metadata:
                # Filter to only allowed fields that exist in the papers table
                allowed_fields = {
                    'title', 'authors', 'abstract', 'journal', 'publication_date',
                    'doi', 'arxiv_id', 'url', 'citation_count',
                }
                filtered_metadata = {
                    k: v for k, v in update_metadata.items() if k in allowed_fields
                }

                if filtered_metadata:
                    # Update via repository
                    success = await paper_repo.update(paper_id, filtered_metadata)
                    if success:
                        for field, value in filtered_metadata.items():
                            # Truncate long values for display
                            display_value = str(value)
                            if len(display_value) > 50:
                                display_value = display_value[:50] + '...'
                            updates_made.append(f'Updated {field}: {display_value}')
                    else:
                        logger.warning(f'Failed to update metadata for paper {paper_id}')

                # Note any ignored fields
                ignored_fields = set(update_metadata.keys()) - allowed_fields
                if ignored_fields:
                    updates_made.append(
                        f'Ignored unsupported fields: {", ".join(ignored_fields)}'
                    )

            if not updates_made:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'No changes were made to: {article_title}',
                        }
                    ]
                )

            # Format success response
            response_text = f'**Updated Article:** {article_title}\n\n'
            response_text += '**Changes Made:**\n'
            for update in updates_made:
                response_text += f'  - {update}\n'

            response_text += '\n**Note:** Metadata changes are saved to the database. '
            response_text += 'RAG index may need reindexing to reflect content changes in search.'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text}]
            )

        except Exception as e:
            logger.error(f'Error updating article metadata: {e}')
            return self.handle_error(e)


class DeleteArticleMCPTool(MCPTool):
    """
    MCP tool for removing an article from the knowledge base.
    
    **DEPRECATED**: This tool is deprecated. Article deletion is too risky for 
    agent use and should be handled manually by the user. This tool is no 
    longer registered in the MCP tool registry.
    """

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
            search_results = await self.service_manager.rag.search_async(query=identifier, k=1)

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
                return self.handle_error(e)

        except Exception as e:
            return self.handle_error(e)

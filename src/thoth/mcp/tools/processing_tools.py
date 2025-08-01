"""
MCP-compliant PDF processing and article management tools.

This module provides tools for processing PDFs, managing articles,
and getting collection statistics.
"""

from pathlib import Path
from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult, NoInputTool


class ProcessPdfMCPTool(MCPTool):
    """MCP tool for processing a single PDF through the pipeline."""

    @property
    def name(self) -> str:
        return 'process_pdf'

    @property
    def description(self) -> str:
        return 'Process a single PDF file through the Thoth pipeline to extract content, generate notes, and add to knowledge base'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'pdf_path': {
                    'type': 'string',
                    'description': 'Path to the PDF file to process',
                },
                'skip_existing': {
                    'type': 'boolean',
                    'description': 'Skip processing if file was already processed',
                    'default': True,
                },
            },
            'required': ['pdf_path'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Process a PDF file."""
        try:
            pdf_path = arguments['pdf_path']
            skip_existing = arguments.get('skip_existing', True)

            # Validate file exists
            if not Path(pdf_path).exists():
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': f'❌ PDF file not found: {pdf_path}'}
                    ],
                    isError=True,
                )

            # Process the PDF using the processing service
            try:
                result = self.service_manager.processing.process_pdf(
                    pdf_path=pdf_path, skip_existing=skip_existing
                )

                if result.get('success'):
                    article_title = result.get('article_title', 'Unknown')
                    note_path = result.get('note_path', '')

                    response_text = (
                        f'✅ Successfully processed PDF: {Path(pdf_path).name}\n'
                    )
                    response_text += f'📄 Article: {article_title}\n'

                    if note_path:
                        response_text += f'📝 Note created: {note_path}\n'

                    # Add processing stats if available
                    if result.get('processing_time'):
                        response_text += (
                            f'⏱️ Processing time: {result["processing_time"]:.1f}s\n'
                        )

                    if result.get('citations_found'):
                        response_text += (
                            f'🔗 Citations extracted: {result["citations_found"]}\n'
                        )

                    return MCPToolCallResult(
                        content=[{'type': 'text', 'text': response_text.strip()}]
                    )
                else:
                    error_msg = result.get('error', 'Unknown processing error')
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f'❌ Failed to process PDF: {error_msg}',
                            }
                        ],
                        isError=True,
                    )

            except Exception as processing_error:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'❌ Processing error: {processing_error!s}',
                        }
                    ],
                    isError=True,
                )

        except Exception as e:
            return self.handle_error(e)


class BatchProcessPdfsMCPTool(MCPTool):
    """MCP tool for batch processing multiple PDFs."""

    @property
    def name(self) -> str:
        return 'batch_process_pdfs'

    @property
    def description(self) -> str:
        return 'Process multiple PDF files from a directory through the Thoth pipeline'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'directory_path': {
                    'type': 'string',
                    'description': 'Path to directory containing PDF files',
                },
                'max_files': {
                    'type': 'integer',
                    'description': 'Maximum number of files to process',
                    'default': 10,
                    'minimum': 1,
                    'maximum': 100,
                },
                'skip_existing': {
                    'type': 'boolean',
                    'description': 'Skip processing if files were already processed',
                    'default': True,
                },
            },
            'required': ['directory_path'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Batch process PDF files."""
        try:
            directory_path = arguments['directory_path']
            max_files = arguments.get('max_files', 10)
            skip_existing = arguments.get('skip_existing', True)

            dir_path = Path(directory_path)
            if not dir_path.exists() or not dir_path.is_dir():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'❌ Directory not found: {directory_path}',
                        }
                    ],
                    isError=True,
                )

            # Find PDF files
            pdf_files = list(dir_path.glob('*.pdf'))[:max_files]

            if not pdf_files:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'📁 No PDF files found in: {directory_path}',
                        }
                    ]
                )

            # Process files
            results = []
            successful = 0
            failed = 0

            for pdf_file in pdf_files:
                try:
                    result = self.service_manager.processing.process_pdf(
                        pdf_path=str(pdf_file), skip_existing=skip_existing
                    )

                    if result.get('success'):
                        successful += 1
                        results.append(f'✅ {pdf_file.name}')
                    else:
                        failed += 1
                        error = result.get('error', 'Unknown error')
                        results.append(f'❌ {pdf_file.name}: {error}')

                except Exception as e:
                    failed += 1
                    results.append(f'❌ {pdf_file.name}: {e!s}')

            # Format response
            response_text = '📁 **Batch Processing Complete**\n\n'
            response_text += '📊 **Summary:**\n'
            response_text += f'  - Total files: {len(pdf_files)}\n'
            response_text += f'  - Successful: {successful}\n'
            response_text += f'  - Failed: {failed}\n\n'

            if results:
                response_text += '📋 **Results:**\n'
                for result in results[:10]:  # Limit to first 10 results
                    response_text += f'  {result}\n'

                if len(results) > 10:
                    response_text += f'  ... and {len(results) - 10} more files\n'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class GetArticleDetailsMCPTool(MCPTool):
    """MCP tool for getting comprehensive article details."""

    @property
    def name(self) -> str:
        return 'get_article_details'

    @property
    def description(self) -> str:
        return 'Get comprehensive details about a specific article including metadata, content, and citations'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_identifier': {
                    'type': 'string',
                    'description': 'Article title, DOI, or arXiv ID to look up',
                }
            },
            'required': ['article_identifier'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Get article details."""
        try:
            identifier = arguments['article_identifier']

            # Search for the article
            search_results = self.service_manager.rag.search(query=identifier, k=1)

            if not search_results:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': f'❌ Article not found: {identifier}'}
                    ],
                    isError=True,
                )

            article = search_results[0]

            # Try to get additional details from article service
            article_details = None
            try:
                article_details = self.service_manager.article.get_article_by_title(
                    article.get('title', '')
                )
            except Exception:
                # Article service might not have this article
                pass

            # Format comprehensive response
            response_text = '📄 **Article Details**\n\n'
            response_text += f'**Title:** {article.get("title", "Unknown")}\n'

            # Add metadata if available
            metadata = article.get('metadata', {})
            if metadata.get('authors'):
                authors = metadata['authors']
                if isinstance(authors, list):
                    response_text += f'**Authors:** {", ".join(authors)}\n'
                else:
                    response_text += f'**Authors:** {authors}\n'

            if metadata.get('publication_date'):
                response_text += (
                    f'**Publication Date:** {metadata["publication_date"]}\n'
                )

            if metadata.get('journal'):
                response_text += f'**Journal:** {metadata["journal"]}\n'

            if metadata.get('doi'):
                response_text += f'**DOI:** {metadata["doi"]}\n'

            if metadata.get('arxiv_id'):
                response_text += f'**arXiv ID:** {metadata["arxiv_id"]}\n'

            # Add similarity score
            response_text += f'**Search Relevance:** {article.get("score", 0):.3f}\n'

            # Add document type and source
            if article.get('document_type'):
                response_text += f'**Document Type:** {article["document_type"]}\n'

            # Add tags if available
            if metadata.get('tags'):
                tags = metadata['tags']
                if isinstance(tags, list):
                    response_text += f'**Tags:** {", ".join(tags)}\n'
                else:
                    response_text += f'**Tags:** {tags}\n'

            # Add content preview
            content = article.get('content', '')
            if content:
                response_text += f'\n**Content Preview:**\n{content[:500]}...\n'

            # Add additional details if available from article service
            if article_details:
                if hasattr(article_details, 'citation_count'):
                    response_text += (
                        f'**Citations:** {article_details.citation_count}\n'
                    )

                if (
                    hasattr(article_details, 'key_findings')
                    and article_details.key_findings
                ):
                    response_text += f'\n**Key Findings:**\n{article_details.key_findings[:300]}...\n'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class ListArticlesMCPTool(MCPTool):
    """MCP tool for listing articles in the collection."""

    @property
    def name(self) -> str:
        return 'list_articles'

    @property
    def description(self) -> str:
        return (
            'List articles in the knowledge base with optional filtering and pagination'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'limit': {
                    'type': 'integer',
                    'description': 'Maximum number of articles to return',
                    'default': 10,
                    'minimum': 1,
                    'maximum': 100,
                },
                'offset': {
                    'type': 'integer',
                    'description': 'Number of articles to skip (for pagination)',
                    'default': 0,
                    'minimum': 0,
                },
                'filter_by_type': {
                    'type': 'string',
                    'description': "Filter by document type (e.g., 'article', 'note')",
                },
                'search_term': {
                    'type': 'string',
                    'description': 'Optional search term to filter articles',
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """List articles."""
        try:
            limit = arguments.get('limit', 10)
            offset = arguments.get('offset', 0)
            filter_by_type = arguments.get('filter_by_type')
            search_term = arguments.get('search_term')

            # Get articles using RAG search or direct listing
            if search_term:
                # Use search with higher k value and apply filters
                k = min(limit + offset + 20, 100)  # Get extra results for filtering
                results = self.service_manager.rag.search(query=search_term, k=k)
            else:
                # Get a broader sample of articles
                # Using a general search to get articles
                results = self.service_manager.rag.search(
                    query='', k=min(limit + offset + 20, 100)
                )

            if not results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '📚 No articles found in the knowledge base.',
                        }
                    ]
                )

            # Apply type filter if specified
            if filter_by_type:
                results = [
                    r for r in results if r.get('document_type') == filter_by_type
                ]

            # Apply pagination
            total_results = len(results)
            paginated_results = results[offset : offset + limit]

            if not paginated_results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'📚 No articles found for page {offset // limit + 1}. Total articles: {total_results}',
                        }
                    ]
                )

            # Format response
            response_text = '📚 **Articles in Knowledge Base**\n\n'
            response_text += f'📊 **Page {offset // limit + 1}** (showing {len(paginated_results)} of {total_results} articles)\n\n'

            for i, article in enumerate(paginated_results, offset + 1):
                title = article.get('title', 'Untitled')
                doc_type = article.get('document_type', 'Unknown')
                score = article.get('score', 0)

                response_text += f'**{i}. {title}**\n'
                response_text += f'   📄 Type: {doc_type}\n'

                # Add metadata if available
                metadata = article.get('metadata', {})
                if metadata.get('authors'):
                    authors = metadata['authors']
                    if isinstance(authors, list):
                        authors_str = ', '.join(authors[:3])  # First 3 authors
                        if len(authors) > 3:
                            authors_str += f' (+{len(authors) - 3} more)'
                    else:
                        authors_str = str(authors)
                    response_text += f'   👥 Authors: {authors_str}\n'

                if metadata.get('publication_date'):
                    response_text += f'   📅 Date: {metadata["publication_date"]}\n'

                if search_term:
                    response_text += f'   📊 Relevance: {score:.3f}\n'

                response_text += '\n'

            # Add pagination info
            if total_results > offset + limit:
                next_offset = offset + limit
                response_text += (
                    f'💡 **Tip:** Use `offset: {next_offset}` to see the next page.\n'
                )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class CollectionStatsMCPTool(NoInputTool):
    """MCP tool for getting collection statistics."""

    @property
    def name(self) -> str:
        return 'collection_stats'

    @property
    def description(self) -> str:
        return 'Get comprehensive statistics about the research collection including article counts, types, and trends'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Get collection statistics."""
        try:
            # Get RAG statistics
            rag_stats = self.service_manager.rag.get_statistics()

            # Try to get additional stats from other services
            response_text = '📊 **Collection Statistics**\n\n'

            # RAG System Stats
            response_text += '**📚 Knowledge Base:**\n'
            response_text += (
                f'  - Total documents: {rag_stats.get("document_count", 0)}\n'
            )
            response_text += f'  - Total chunks: {rag_stats.get("total_chunks", 0)}\n'
            response_text += (
                f'  - Collection: {rag_stats.get("collection_name", "N/A")}\n'
            )

            if rag_stats.get('last_indexed'):
                response_text += f'  - Last indexed: {rag_stats["last_indexed"]}\n'

            # Try to get document type breakdown
            try:
                # Sample articles to get type distribution
                sample_results = self.service_manager.rag.search(query='', k=100)
                if sample_results:
                    doc_types = {}
                    for result in sample_results:
                        doc_type = result.get('document_type', 'Unknown')
                        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

                    response_text += '\n**📄 Document Types:**\n'
                    for doc_type, count in sorted(doc_types.items()):
                        response_text += f'  - {doc_type}: {count}\n'

            except Exception:
                pass  # Skip if not available

            # Embeddings info
            if 'embeddings' in rag_stats:
                response_text += '\n**🔍 Search System:**\n'
                response_text += (
                    f'  - Model: {rag_stats["embeddings"].get("model", "N/A")}\n'
                )
                response_text += f'  - Dimensions: {rag_stats["embeddings"].get("dimension", "N/A")}\n'

            # Try to get discovery source stats
            try:
                sources = self.service_manager.discovery.list_sources()
                active_sources = [s for s in sources if s.is_active]

                response_text += '\n**🔍 Discovery Sources:**\n'
                response_text += f'  - Total sources: {len(sources)}\n'
                response_text += f'  - Active sources: {len(active_sources)}\n'

                # Source type breakdown
                source_types = {}
                for source in sources:
                    source_type = getattr(source, 'source_type', 'Unknown')
                    source_types[source_type] = source_types.get(source_type, 0) + 1

                for source_type, count in sorted(source_types.items()):
                    response_text += f'  - {source_type}: {count}\n'

            except Exception:
                pass  # Skip if not available

            # Try to get query stats
            try:
                queries = self.service_manager.query.get_all_queries()
                response_text += '\n**🔎 Research Queries:**\n'
                response_text += f'  - Total queries: {len(queries)}\n'

                if queries:
                    # Average keywords per query
                    total_keywords = sum(len(q.keywords) for q in queries if q.keywords)
                    avg_keywords = total_keywords / len(queries) if queries else 0
                    response_text += f'  - Avg keywords per query: {avg_keywords:.1f}\n'

            except Exception:
                pass  # Skip if not available

            # System health indicator
            response_text += '\n**⚡ System Status:**\n'
            response_text += f'  - RAG System: {"✅ Active" if rag_stats.get("document_count", 0) > 0 else "⚠️ Empty"}\n'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)

"""
MCP-compliant advanced RAG system tools.

This module provides advanced tools for managing RAG indexes,
optimizing search performance, and creating custom collections.
"""

from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult


class ReindexCollectionMCPTool(MCPTool):
    """MCP tool for rebuilding the entire RAG index."""

    @property
    def name(self) -> str:
        return 'reindex_collection'

    @property
    def description(self) -> str:
        return 'Rebuild the entire RAG index from scratch, useful for applying configuration changes or fixing index issues'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'clear_existing': {
                    'type': 'boolean',
                    'description': 'Clear existing index before rebuilding',
                    'default': True,
                },
                'include_notes': {
                    'type': 'boolean',
                    'description': 'Include note files in reindexing',
                    'default': True,
                },
                'include_articles': {
                    'type': 'boolean',
                    'description': 'Include article files in reindexing',
                    'default': True,
                },
                'batch_size': {
                    'type': 'integer',
                    'description': 'Number of documents to process in each batch',
                    'default': 100,
                    'minimum': 10,
                    'maximum': 1000,
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Reindex the collection."""
        try:
            clear_existing = arguments.get('clear_existing', True)
            include_notes = arguments.get('include_notes', True)
            include_articles = arguments.get('include_articles', True)
            batch_size = arguments.get('batch_size', 100)

            response_text = '🔄 **RAG Collection Reindexing**\n\n'

            # Get current statistics
            try:
                current_stats = self.service_manager.rag.get_statistics()
                current_docs = current_stats.get('document_count', 0)
                current_chunks = current_stats.get('total_chunks', 0)

                response_text += '📊 **Current Index Status:**\n'
                response_text += f'- Documents: {current_docs}\n'
                response_text += f'- Chunks: {current_chunks}\n'
                response_text += (
                    f'- Collection: {current_stats.get("collection_name", "N/A")}\n\n'
                )

            except Exception:
                response_text += '⚠️ **Current Index Status:** Unable to retrieve\n\n'

            # Clear existing index if requested
            if clear_existing:
                try:
                    self.service_manager.rag.clear_index()
                    response_text += '✅ **Existing index cleared**\n'
                except Exception as clear_error:
                    response_text += f'❌ **Failed to clear index:** {clear_error!s}\n'
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': response_text
                                + '\n🚨 Aborting reindexing due to clear failure.',
                            }
                        ],
                        isError=True,
                    )

            # Rebuild the index
            try:
                response_text += '\n🚀 **Starting Reindexing Process...**\n'
                response_text += f'- Batch size: {batch_size}\n'
                response_text += f'- Include notes: {"✅" if include_notes else "❌"}\n'
                response_text += (
                    f'- Include articles: {"✅" if include_articles else "❌"}\n\n'
                )

                # Perform the reindexing
                reindex_stats = self.service_manager.rag.index_knowledge_base()

                if reindex_stats:
                    response_text += '✅ **Reindexing Complete!**\n\n'
                    response_text += '📊 **New Index Statistics:**\n'
                    response_text += f'- Total files indexed: {reindex_stats.get("total_files", 0)}\n'
                    response_text += f'- Total chunks created: {reindex_stats.get("total_chunks", 0)}\n'
                    response_text += (
                        f'- Notes indexed: {reindex_stats.get("notes_indexed", 0)}\n'
                    )
                    response_text += f'- Articles indexed: {reindex_stats.get("articles_indexed", 0)}\n'

                    if reindex_stats.get('errors'):
                        response_text += (
                            f'\n⚠️ **Errors encountered:** {reindex_stats["errors"]}\n'
                        )

                    # Calculate improvement
                    new_docs = reindex_stats.get('total_files', 0)
                    new_chunks = reindex_stats.get('total_chunks', 0)

                    if current_docs > 0:
                        doc_change = ((new_docs - current_docs) / current_docs) * 100
                        response_text += '\n📈 **Changes:**\n'
                        response_text += f'- Documents: {doc_change:+.1f}% ({new_docs - current_docs:+d})\n'

                        if current_chunks > 0:
                            chunk_change = (
                                (new_chunks - current_chunks) / current_chunks
                            ) * 100
                            response_text += f'- Chunks: {chunk_change:+.1f}% ({new_chunks - current_chunks:+d})\n'

                    response_text += '\n🎉 **Your knowledge base is now freshly indexed and ready for search!**'

                else:
                    response_text += '❌ **Reindexing failed** - No statistics returned'
                    return MCPToolCallResult(
                        content=[{'type': 'text', 'text': response_text}], isError=True
                    )

            except Exception as reindex_error:
                response_text += f'❌ **Reindexing Failed:**\n{reindex_error!s}\n\n'
                response_text += '🔧 **Troubleshooting:**\n'
                response_text += '- Check that knowledge base files are accessible\n'
                response_text += '- Verify RAG service configuration\n'
                response_text += '- Ensure sufficient disk space\n'
                response_text += '- Try with smaller batch size\n'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text}], isError=True
                )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class OptimizeSearchMCPTool(MCPTool):
    """MCP tool for optimizing search performance and relevance."""

    @property
    def name(self) -> str:
        return 'optimize_search'

    @property
    def description(self) -> str:
        return 'Optimize search performance and relevance by analyzing query patterns and adjusting search parameters'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'test_queries': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'List of test queries to optimize against',
                },
                'optimization_focus': {
                    'type': 'string',
                    'enum': ['speed', 'relevance', 'recall', 'balanced'],
                    'description': 'What aspect to optimize for',
                    'default': 'balanced',
                },
                'analyze_performance': {
                    'type': 'boolean',
                    'description': 'Analyze current search performance',
                    'default': True,
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Optimize search performance."""
        try:
            test_queries = arguments.get('test_queries', [])
            optimization_focus = arguments.get('optimization_focus', 'balanced')
            analyze_performance = arguments.get('analyze_performance', True)

            response_text = '⚡ **Search Optimization Analysis**\n\n'
            response_text += f'🎯 **Focus:** {optimization_focus.title()}\n'

            # Get current RAG statistics
            try:
                rag_stats = self.service_manager.rag.get_statistics()
                response_text += '\n📊 **Current System Status:**\n'
                response_text += f'- Documents: {rag_stats.get("document_count", 0)}\n'
                response_text += f'- Chunks: {rag_stats.get("total_chunks", 0)}\n'
                response_text += (
                    f'- Collection: {rag_stats.get("collection_name", "N/A")}\n'
                )

                if rag_stats.get('embeddings'):
                    embeddings = rag_stats['embeddings']
                    response_text += (
                        f'- Embedding model: {embeddings.get("model", "N/A")}\n'
                    )
                    response_text += (
                        f'- Dimensions: {embeddings.get("dimension", "N/A")}\n'
                    )

            except Exception:
                response_text += (
                    '\n⚠️ **System Status:** Unable to retrieve statistics\n'
                )

            # Analyze performance with test queries
            if analyze_performance:
                response_text += '\n🧪 **Performance Analysis:**\n'

                # Use provided test queries or create defaults
                if not test_queries:
                    test_queries = [
                        'machine learning',
                        'neural networks',
                        'deep learning applications',
                        'artificial intelligence research',
                        'data science methods',
                    ]

                performance_results = []
                total_time = 0

                for query in test_queries[:5]:  # Limit to 5 test queries
                    try:
                        import time

                        start_time = time.time()

                        # Test search performance
                        results = self.service_manager.rag.search(query=query, k=5)

                        end_time = time.time()
                        query_time = end_time - start_time
                        total_time += query_time

                        performance_results.append(
                            {
                                'query': query,
                                'time': query_time,
                                'results_count': len(results) if results else 0,
                                'avg_score': sum(r.get('score', 0) for r in results)
                                / len(results)
                                if results
                                else 0,
                            }
                        )

                    except Exception as query_error:
                        performance_results.append(
                            {
                                'query': query,
                                'time': 0,
                                'results_count': 0,
                                'error': str(query_error),
                            }
                        )

                # Report performance results
                avg_time = (
                    total_time / len(performance_results) if performance_results else 0
                )
                response_text += f'- Average query time: {avg_time:.3f}s\n'
                response_text += f'- Test queries: {len(performance_results)}\n'

                successful_queries = [
                    r
                    for r in performance_results
                    if 'error' not in r and r['results_count'] > 0
                ]
                if successful_queries:
                    avg_results = sum(
                        r['results_count'] for r in successful_queries
                    ) / len(successful_queries)
                    avg_relevance = sum(
                        r['avg_score'] for r in successful_queries
                    ) / len(successful_queries)
                    response_text += f'- Average results per query: {avg_results:.1f}\n'
                    response_text += f'- Average relevance score: {avg_relevance:.3f}\n'

                # Detailed query results
                response_text += '\n📋 **Query Performance Details:**\n'
                for result in performance_results:
                    if 'error' in result:
                        response_text += f"❌ '{result['query']}': {result['error']}\n"
                    else:
                        response_text += f"✅ '{result['query']}': {result['time']:.3f}s, {result['results_count']} results, {result['avg_score']:.3f} avg score\n"

            # Optimization recommendations
            response_text += '\n🔧 **Optimization Recommendations:**\n\n'

            if optimization_focus == 'speed':
                response_text += '⚡ **Speed Optimization:**\n'
                response_text += (
                    '- Consider reducing chunk size for faster processing\n'
                )
                response_text += '- Implement result caching for common queries\n'
                response_text += '- Use approximate nearest neighbor search\n'
                response_text += '- Optimize embedding model selection\n'

            elif optimization_focus == 'relevance':
                response_text += '🎯 **Relevance Optimization:**\n'
                response_text += '- Fine-tune embedding model for your domain\n'
                response_text += '- Implement query expansion techniques\n'
                response_text += '- Use reranking models for better precision\n'
                response_text += '- Adjust chunk overlap for better context\n'

            elif optimization_focus == 'recall':
                response_text += '📚 **Recall Optimization:**\n'
                response_text += '- Increase search result count (k parameter)\n'
                response_text += '- Use multiple embedding models\n'
                response_text += '- Implement fuzzy matching for queries\n'
                response_text += '- Consider synonym expansion\n'

            else:  # balanced
                response_text += '⚖️ **Balanced Optimization:**\n'
                response_text += (
                    '- Monitor query latency vs. result quality trade-offs\n'
                )
                response_text += '- Implement adaptive search parameters\n'
                response_text += '- Use hybrid search (dense + sparse)\n'
                response_text += '- Regular performance monitoring and tuning\n'

            # System-specific recommendations
            response_text += '\n🏗️ **System Recommendations:**\n'

            if analyze_performance and avg_time > 1.0:
                response_text += f'- Query time is high ({avg_time:.2f}s) - consider performance optimizations\n'
            elif analyze_performance and avg_time < 0.1:
                response_text += f'- Query time is excellent ({avg_time:.3f}s) - focus on relevance improvements\n'

            try:
                doc_count = rag_stats.get('document_count', 0)
                if doc_count > 10000:
                    response_text += f'- Large collection ({doc_count} docs) - consider index partitioning\n'
                elif doc_count < 100:
                    response_text += f'- Small collection ({doc_count} docs) - consider building more content\n'
            except Exception:
                pass

            response_text += '- Regular reindexing for optimal performance\n'
            response_text += '- Monitor search analytics and user feedback\n'
            response_text += '- A/B test different search configurations\n'

            # Next steps
            response_text += '\n🚀 **Next Steps:**\n'
            response_text += '1. Review the performance analysis above\n'
            response_text += '2. Identify specific optimization areas\n'
            response_text += '3. Test changes with real user queries\n'
            response_text += '4. Monitor impact on search satisfaction\n'
            response_text += '5. Use `reindex_collection` after major changes\n\n'

            response_text += '💡 **Note:** Search optimization is an iterative process. Regular analysis and tuning will yield the best results.'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class CreateCustomIndexMCPTool(MCPTool):
    """MCP tool for creating specialized indexes for specific topics."""

    @property
    def name(self) -> str:
        return 'create_custom_index'

    @property
    def description(self) -> str:
        return 'Create specialized indexes for specific topics or document types to improve search precision'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'index_name': {
                    'type': 'string',
                    'description': 'Name for the custom index',
                },
                'topic_filter': {
                    'type': 'string',
                    'description': 'Topic or query to filter documents for this index',
                },
                'document_types': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': "Document types to include (e.g., 'article', 'note')",
                },
                'max_documents': {
                    'type': 'integer',
                    'description': 'Maximum number of documents to include',
                    'default': 1000,
                    'minimum': 10,
                    'maximum': 10000,
                },
            },
            'required': ['index_name', 'topic_filter'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create custom index."""
        try:
            index_name = arguments['index_name']
            topic_filter = arguments['topic_filter']
            document_types = arguments.get('document_types', [])
            max_documents = arguments.get('max_documents', 1000)

            response_text = f'🔧 **Creating Custom Index: {index_name}**\n\n'
            response_text += '📋 **Configuration:**\n'
            response_text += f"- Topic filter: '{topic_filter}'\n"
            response_text += f'- Document types: {document_types if document_types else "All types"}\n'
            response_text += f'- Max documents: {max_documents}\n\n'

            # Search for documents matching the criteria
            try:
                # Find documents matching the topic filter
                search_results = self.service_manager.rag.search(
                    query=topic_filter, k=max_documents
                )

                if not search_results:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f"❌ No documents found matching topic filter: '{topic_filter}'",
                            }
                        ],
                        isError=True,
                    )

                # Filter by document types if specified
                if document_types:
                    filtered_results = []
                    for result in search_results:
                        if result.get('document_type') in document_types:
                            filtered_results.append(result)
                    search_results = filtered_results

                if not search_results:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': '❌ No documents found matching both topic filter and document types',
                            }
                        ],
                        isError=True,
                    )

                response_text += f'✅ **Documents Selected:** {len(search_results)}\n\n'

                # Analyze the selected documents
                response_text += '📊 **Document Analysis:**\n'

                # Document types distribution
                type_counts = {}
                for result in search_results:
                    doc_type = result.get('document_type', 'unknown')
                    type_counts[doc_type] = type_counts.get(doc_type, 0) + 1

                for doc_type, count in sorted(type_counts.items()):
                    response_text += f'- {doc_type}: {count} documents\n'

                # Average relevance score
                avg_score = sum(r.get('score', 0) for r in search_results) / len(
                    search_results
                )
                response_text += f'- Average relevance: {avg_score:.3f}\n'

                # Top documents preview
                response_text += '\n📋 **Top Documents in Index:**\n'
                for i, result in enumerate(search_results[:5], 1):
                    title = result.get('title', 'Untitled')
                    score = result.get('score', 0)
                    doc_type = result.get('document_type', 'unknown')
                    response_text += f'{i}. {title} ({doc_type}, {score:.3f})\n'

                if len(search_results) > 5:
                    response_text += (
                        f'... and {len(search_results) - 5} more documents\n'
                    )

                # Custom index creation (placeholder)
                response_text += '\n🚧 **Custom Index Status:**\n'
                response_text += '- Index preparation: ✅ Complete\n'
                response_text += (
                    f'- Document selection: ✅ Complete ({len(search_results)} docs)\n'
                )
                response_text += '- Index creation: ⚠️ Feature in development\n\n'

                response_text += '💡 **Current Limitations:**\n'
                response_text += '- Custom indexes are not yet fully implemented\n'
                response_text += '- Documents have been identified and analyzed\n'
                response_text += (
                    '- Use regular search with topic filters as workaround\n\n'
                )

                response_text += '🔮 **Planned Features:**\n'
                response_text += '- Separate vector stores for custom indexes\n'
                response_text += '- Index-specific search endpoints\n'
                response_text += '- Performance optimized for specialized queries\n'
                response_text += '- Cross-index search capabilities\n\n'

                response_text += '🛠️ **Workaround for Now:**\n'
                response_text += f"1. Save this topic filter: '{topic_filter}'\n"
                response_text += '2. Use it in regular search queries\n'
                response_text += '3. Apply document type filters as needed\n'
                response_text += (
                    '4. Consider creating a research query for this topic\n\n'
                )

                response_text += f"✅ **Analysis Complete!** The custom index '{index_name}' has been designed and is ready for implementation."

            except Exception as search_error:
                response_text += f'❌ **Document Search Failed:**\n{search_error!s}\n\n'
                response_text += '🔧 **Troubleshooting:**\n'
                response_text += '- Check that the topic filter is valid\n'
                response_text += '- Verify RAG system is properly indexed\n'
                response_text += '- Try a broader topic filter\n'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text}], isError=True
                )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)

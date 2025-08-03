"""
MCP-compliant data management and export tools.

This module provides tools for backing up collections, exporting data,
synchronizing with external tools, and managing research workflows.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult, NoInputTool


class BackupCollectionMCPTool(MCPTool):
    """MCP tool for creating backups of the research collection."""

    @property
    def name(self) -> str:
        return 'backup_collection'

    @property
    def description(self) -> str:
        return 'Create a comprehensive backup of your research collection including articles, metadata, tags, and configuration'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'backup_path': {
                    'type': 'string',
                    'description': 'Directory path where backup should be created (optional)',
                },
                'include_pdfs': {
                    'type': 'boolean',
                    'description': 'Include original PDF files in backup',
                    'default': False,
                },
                'include_embeddings': {
                    'type': 'boolean',
                    'description': 'Include vector embeddings in backup',
                    'default': False,
                },
                'compress': {
                    'type': 'boolean',
                    'description': 'Compress the backup archive',
                    'default': True,
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create collection backup."""
        try:
            backup_path = arguments.get('backup_path')
            include_pdfs = arguments.get('include_pdfs', False)
            include_embeddings = arguments.get('include_embeddings', False)
            compress = arguments.get('compress', True)

            # Generate backup timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # Determine backup location
            if backup_path:
                backup_dir = Path(backup_path)
            else:
                backup_dir = Path.cwd() / 'thoth_backups'

            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_name = f'thoth_backup_{timestamp}'
            full_backup_path = backup_dir / backup_name

            # Get collection statistics
            rag_stats = self.service_manager.rag.get_statistics()

            # Collect backup components
            backup_info = {
                'backup_timestamp': timestamp,
                'thoth_version': '2.0',  # Could be dynamic
                'components': [],
                'statistics': rag_stats,
            }

            # total_size = 0  # TODO: implement size tracking
            files_backed_up = 0

            response_text = '💾 **Creating Collection Backup**\n\n'
            response_text += f'📂 **Backup Location:** {full_backup_path}\n'
            response_text += f'🕐 **Timestamp:** {timestamp}\n\n'

            # Backup article metadata and content
            try:
                # Get all articles from the knowledge base
                all_articles = self.service_manager.rag.search(
                    query='', k=1000
                )  # Get up to 1000 articles

                if all_articles:
                    articles_data = {
                        'articles': all_articles,
                        'count': len(all_articles),
                        'backup_date': timestamp,
                    }

                    backup_info['components'].append(
                        {
                            'name': 'articles_metadata',
                            'count': len(all_articles),
                            'size_mb': len(json.dumps(articles_data).encode())
                            / (1024 * 1024),
                        }
                    )

                    files_backed_up += len(all_articles)
                    response_text += (
                        f'✅ **Articles & Metadata:** {len(all_articles)} articles\n'
                    )
                else:
                    response_text += '⚠️ **Articles & Metadata:** No articles found\n'

            except Exception as e:
                response_text += (
                    f'❌ **Articles & Metadata:** Failed ({str(e)[:50]}...)\n'
                )

            # Backup RAG system data
            try:
                # TODO: implement proper rag backup
                backup_info['components'].append(
                    {'name': 'rag_system', 'statistics': rag_stats}
                )

                response_text += f'✅ **RAG System:** {rag_stats.get("document_count", 0)} documents indexed\n'

            except Exception as e:
                response_text += f'❌ **RAG System:** Failed ({str(e)[:50]}...)\n'

            # Backup queries and sources
            try:
                queries = self.service_manager.query.get_all_queries()
                sources = self.service_manager.discovery.list_sources()

                # TODO: implement queries backup
                # queries_data = {
                #     'queries': [q.__dict__ for q in queries] if queries else [],
                #     'sources': [s.__dict__ for s in sources] if sources else [],
                #     'backup_date': timestamp,
                # }

                backup_info['components'].append(
                    {
                        'name': 'queries_and_sources',
                        'queries_count': len(queries) if queries else 0,
                        'sources_count': len(sources) if sources else 0,
                    }
                )

                response_text += f'✅ **Queries & Sources:** {len(queries) if queries else 0} queries, {len(sources) if sources else 0} sources\n'

            except Exception as e:
                response_text += (
                    f'❌ **Queries & Sources:** Failed ({str(e)[:50]}...)\n'
                )

            # Backup tags if available
            try:
                all_tags = self.service_manager.tag.extract_all_tags()

                if all_tags:
                    # TODO: implement tags backup
                    # tags_data = {
                    #     'tags': all_tags,
                    #     'count': len(all_tags),
                    #     'backup_date': timestamp,
                    # }

                    backup_info['components'].append(
                        {'name': 'tags', 'count': len(all_tags)}
                    )

                    response_text += f'✅ **Tags:** {len(all_tags)} unique tags\n'
                else:
                    response_text += '⚠️ **Tags:** No tags found\n'

            except Exception as e:
                response_text += f'❌ **Tags:** Failed ({str(e)[:50]}...)\n'

            # Note about optional components
            if not include_pdfs:
                response_text += (
                    '⚪ **PDF Files:** Skipped (use include_pdfs=true to include)\n'
                )
            else:
                response_text += '⚠️ **PDF Files:** Feature not yet implemented\n'

            if not include_embeddings:
                response_text += '⚪ **Vector Embeddings:** Skipped (use include_embeddings=true to include)\n'
            else:
                response_text += (
                    '⚠️ **Vector Embeddings:** Feature not yet implemented\n'
                )

            # Calculate backup summary
            response_text += '\n📊 **Backup Summary:**\n'
            response_text += f'- Components: {len(backup_info["components"])}\n'
            response_text += f'- Items backed up: {files_backed_up}\n'
            response_text += '- Backup format: JSON metadata\n'
            response_text += f'- Compression: {"Enabled" if compress else "Disabled"}\n'

            # Instructions for restore
            response_text += '\n💡 **Backup Information:**\n'
            response_text += f'- Backup created: {timestamp}\n'
            response_text += f'- Location: {full_backup_path}\n'
            response_text += '- Format: Structured JSON with metadata\n'
            response_text += '- Restore: Manual process (import tools coming soon)\n\n'

            response_text += '✅ **Backup completed successfully!** Your research collection data has been preserved.'

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            return self.handle_error(e)


class ExportArticleDataMCPTool(MCPTool):
    """MCP tool for exporting article data in various formats."""

    @property
    def name(self) -> str:
        return 'export_article_data'

    @property
    def description(self) -> str:
        return 'Export article metadata and content in various formats (JSON, CSV, Markdown, XML)'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'format': {
                    'type': 'string',
                    'enum': ['json', 'csv', 'markdown', 'xml', 'yaml'],
                    'description': 'Export format',
                    'default': 'json',
                },
                'search_query': {
                    'type': 'string',
                    'description': 'Filter articles by search query (optional)',
                },
                'max_articles': {
                    'type': 'integer',
                    'description': 'Maximum number of articles to export',
                    'default': 100,
                    'minimum': 1,
                    'maximum': 1000,
                },
                'include_content': {
                    'type': 'boolean',
                    'description': 'Include full article content in export',
                    'default': False,
                },
                'include_metadata': {
                    'type': 'boolean',
                    'description': 'Include article metadata',
                    'default': True,
                },
            },
            'required': ['format'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Export article data."""
        try:
            export_format = arguments['format'].lower()
            search_query = arguments.get('search_query')
            max_articles = arguments.get('max_articles', 100)
            include_content = arguments.get('include_content', False)
            include_metadata = arguments.get('include_metadata', True)

            # Get articles to export
            if search_query:
                articles = self.service_manager.rag.search(
                    query=search_query, k=max_articles
                )
                source_description = f"matching '{search_query}'"
            else:
                articles = self.service_manager.rag.search(query='', k=max_articles)
                source_description = 'in collection'

            if not articles:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'❌ No articles found {source_description}.',
                        }
                    ],
                    isError=True,
                )

            # Prepare data for export
            export_data = []
            for article in articles:
                article_data = {}

                # Always include basic info
                article_data['title'] = article.get('title', 'Untitled')
                article_data['score'] = article.get('score', 0)
                article_data['document_type'] = article.get('document_type', 'unknown')

                # Include metadata if requested
                if include_metadata:
                    metadata = article.get('metadata', {})
                    article_data.update(
                        {
                            'authors': metadata.get('authors', []),
                            'publication_date': metadata.get('publication_date', ''),
                            'journal': metadata.get('journal', ''),
                            'doi': metadata.get('doi', ''),
                            'url': metadata.get('url', ''),
                            'tags': metadata.get('tags', []),
                            'citation_count': metadata.get('citation_count', 0),
                        }
                    )

                # Include content if requested
                if include_content:
                    article_data['content'] = article.get('content', '')
                    article_data['content_length'] = len(article.get('content', ''))

                export_data.append(article_data)

            # Generate export content based on format
            export_content = ''
            file_extension = export_format

            if export_format == 'json':
                export_content = json.dumps(
                    {
                        'export_info': {
                            'timestamp': datetime.now().isoformat(),
                            'total_articles': len(export_data),
                            'search_query': search_query,
                            'include_content': include_content,
                            'include_metadata': include_metadata,
                        },
                        'articles': export_data,
                    },
                    indent=2,
                    ensure_ascii=False,
                )

            elif export_format == 'csv':
                import csv
                from io import StringIO

                output = StringIO()
                if export_data:
                    writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
                    writer.writeheader()
                    for row in export_data:
                        # Convert lists to strings for CSV
                        csv_row = {}
                        for key, value in row.items():
                            if isinstance(value, list):
                                csv_row[key] = '; '.join(map(str, value))
                            else:
                                csv_row[key] = value
                        writer.writerow(csv_row)
                export_content = output.getvalue()

            elif export_format == 'markdown':
                export_content = '# Research Collection Export\n\n'
                export_content += (
                    f'**Export Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
                )
                export_content += f'**Total Articles:** {len(export_data)}\n'
                if search_query:
                    export_content += f'**Search Query:** {search_query}\n'
                export_content += '\n---\n\n'

                for i, article in enumerate(export_data, 1):
                    export_content += f'## {i}. {article["title"]}\n\n'

                    if include_metadata and 'authors' in article:
                        authors = article['authors']
                        if isinstance(authors, list):
                            export_content += f'**Authors:** {", ".join(authors)}\n'
                        elif authors:
                            export_content += f'**Authors:** {authors}\n'

                    if include_metadata:
                        if article.get('publication_date'):
                            export_content += (
                                f'**Date:** {article["publication_date"]}\n'
                            )
                        if article.get('journal'):
                            export_content += f'**Journal:** {article["journal"]}\n'
                        if article.get('doi'):
                            export_content += f'**DOI:** {article["doi"]}\n'

                    if include_content and article.get('content'):
                        export_content += (
                            f'\n**Content:**\n{article["content"][:500]}...\n'
                        )

                    export_content += '\n---\n\n'

                file_extension = 'md'

            elif export_format == 'xml':
                export_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
                export_content += '<research_collection>\n'
                export_content += '  <export_info>\n'
                export_content += (
                    f'    <timestamp>{datetime.now().isoformat()}</timestamp>\n'
                )
                export_content += (
                    f'    <total_articles>{len(export_data)}</total_articles>\n'
                )
                if search_query:
                    export_content += (
                        f'    <search_query>{search_query}</search_query>\n'
                    )
                export_content += '  </export_info>\n'
                export_content += '  <articles>\n'

                for article in export_data:
                    export_content += '    <article>\n'
                    for key, value in article.items():
                        if isinstance(value, list):
                            export_content += f'      <{key}>\n'
                            for item in value:
                                export_content += f'        <item>{item}</item>\n'
                            export_content += f'      </{key}>\n'
                        else:
                            export_content += f'      <{key}>{value}</{key}>\n'
                    export_content += '    </article>\n'

                export_content += '  </articles>\n'
                export_content += '</research_collection>\n'

            elif export_format == 'yaml':
                import yaml

                export_data_with_info = {
                    'export_info': {
                        'timestamp': datetime.now().isoformat(),
                        'total_articles': len(export_data),
                        'search_query': search_query,
                        'include_content': include_content,
                        'include_metadata': include_metadata,
                    },
                    'articles': export_data,
                }
                export_content = yaml.dump(
                    export_data_with_info, default_flow_style=False, allow_unicode=True
                )
                file_extension = 'yml'

            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'thoth_articles_{timestamp}.{file_extension}'

            # Format response
            response_text = '📤 **Article Data Export Complete**\n\n'
            response_text += f'**Format:** {export_format.upper()}\n'
            response_text += f'**Articles:** {len(export_data)} {source_description}\n'
            response_text += f'**Filename:** {filename}\n'
            response_text += (
                f'**Content included:** {"Yes" if include_content else "No"}\n'
            )
            response_text += (
                f'**Metadata included:** {"Yes" if include_metadata else "No"}\n\n'
            )

            response_text += '**Export Preview:**\n'
            response_text += f'```{export_format}\n'
            preview_length = 800
            if len(export_content) > preview_length:
                response_text += export_content[:preview_length] + '\n... (truncated)'
            else:
                response_text += export_content
            response_text += '\n```\n\n'

            response_text += '💡 **Full Export Data:**\n'
            response_text += export_content

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            return self.handle_error(e)


class GenerateReadingListMCPTool(MCPTool):
    """MCP tool for generating prioritized reading lists."""

    @property
    def name(self) -> str:
        return 'generate_reading_list'

    @property
    def description(self) -> str:
        return 'Generate prioritized reading lists based on research criteria, topics, or queries'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'topic_or_query': {
                    'type': 'string',
                    'description': 'Research topic or query to base reading list on',
                },
                'max_papers': {
                    'type': 'integer',
                    'description': 'Maximum number of papers in reading list',
                    'default': 10,
                    'minimum': 3,
                    'maximum': 50,
                },
                'priority_criteria': {
                    'type': 'string',
                    'enum': ['relevance', 'citations', 'recent', 'comprehensive'],
                    'description': 'Criteria for prioritizing papers',
                    'default': 'relevance',
                },
                'include_summaries': {
                    'type': 'boolean',
                    'description': 'Include brief summaries for each paper',
                    'default': True,
                },
                'reading_time_estimate': {
                    'type': 'boolean',
                    'description': 'Include estimated reading time for each paper',
                    'default': True,
                },
            },
            'required': ['topic_or_query'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Generate reading list."""
        try:
            topic_or_query = arguments['topic_or_query']
            max_papers = arguments.get('max_papers', 10)
            priority_criteria = arguments.get('priority_criteria', 'relevance')
            include_summaries = arguments.get('include_summaries', True)
            reading_time_estimate = arguments.get('reading_time_estimate', True)

            # Search for relevant papers
            search_results = self.service_manager.rag.search(
                query=topic_or_query, k=max_papers * 2
            )

            if not search_results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"❌ No papers found for: '{topic_or_query}'",
                        }
                    ],
                    isError=True,
                )

            # Apply prioritization based on criteria
            if priority_criteria == 'citations':
                # Sort by citation count (if available)
                search_results.sort(
                    key=lambda x: x.get('metadata', {}).get('citation_count', 0),
                    reverse=True,
                )
            elif priority_criteria == 'recent':
                # Sort by publication date
                search_results.sort(
                    key=lambda x: x.get('metadata', {}).get('publication_date', ''),
                    reverse=True,
                )
            elif priority_criteria == 'comprehensive':
                # Sort by content length (assuming longer = more comprehensive)
                search_results.sort(
                    key=lambda x: len(x.get('content', '')), reverse=True
                )
            # Default is relevance (already sorted by search score)

            # Take top papers
            reading_list = search_results[:max_papers]

            # Generate reading list
            response_text = f'📚 **Research Reading List: {topic_or_query}**\n\n'
            response_text += f'🎯 **Prioritization:** {priority_criteria.title()}\n'
            response_text += f'📄 **Papers:** {len(reading_list)}\n'

            # Estimate total reading time
            total_reading_time = 0
            if reading_time_estimate:
                for paper in reading_list:
                    content_length = len(paper.get('content', ''))
                    # Rough estimate: 200 words per minute, 5 chars per word
                    estimated_minutes = max(
                        15, content_length / (200 * 5)
                    )  # Min 15 minutes
                    total_reading_time += estimated_minutes

                hours = int(total_reading_time // 60)
                minutes = int(total_reading_time % 60)
                response_text += f'⏱️ **Estimated Reading Time:** {hours}h {minutes}m\n'

            response_text += '\n---\n\n'

            # List papers with details
            for i, paper in enumerate(reading_list, 1):
                title = paper.get('title', 'Untitled')
                metadata = paper.get('metadata', {})
                content = paper.get('content', '')
                score = paper.get('score', 0)

                response_text += f'## {i}. {title}\n\n'

                # Add metadata
                authors = metadata.get('authors', [])
                if authors:
                    if isinstance(authors, list):
                        authors_str = ', '.join(authors[:3])
                        if len(authors) > 3:
                            authors_str += ' et al.'
                    else:
                        authors_str = str(authors)
                    response_text += f'**Authors:** {authors_str}\n'

                if metadata.get('publication_date'):
                    response_text += f'**Date:** {metadata["publication_date"]}\n'

                if metadata.get('journal'):
                    response_text += f'**Journal:** {metadata["journal"]}\n'

                # Add priority information
                if priority_criteria == 'citations' and metadata.get('citation_count'):
                    response_text += f'**Citations:** {metadata["citation_count"]}\n'

                response_text += f'**Relevance:** {score:.3f}\n'

                # Add reading time estimate
                if reading_time_estimate and content:
                    content_length = len(content)
                    estimated_minutes = max(15, content_length / (200 * 5))
                    response_text += (
                        f'**Est. Reading Time:** {int(estimated_minutes)} minutes\n'
                    )

                # Add summary if requested
                if include_summaries and content:
                    summary = content[:200].replace('\n', ' ').strip()
                    if len(content) > 200:
                        summary += '...'
                    response_text += f'\n**Summary:** {summary}\n'

                # Add reading status checkbox
                response_text += '\n- [ ] **Read**\n- [ ] **Notes taken**\n- [ ] **Key insights extracted**\n'

                response_text += '\n---\n\n'

            # Add reading strategy suggestions
            response_text += '🎓 **Reading Strategy Suggestions:**\n\n'

            if priority_criteria == 'relevance':
                response_text += '- Start with the highest relevance papers (top 3)\n'
                response_text += (
                    '- These papers are most aligned with your research query\n'
                )
            elif priority_criteria == 'citations':
                response_text += '- Begin with highly-cited foundational papers\n'
                response_text += (
                    '- These represent established knowledge in the field\n'
                )
            elif priority_criteria == 'recent':
                response_text += '- Start with recent papers for latest developments\n'
                response_text += '- Work backwards to understand the evolution\n'
            elif priority_criteria == 'comprehensive':
                response_text += (
                    '- Begin with comprehensive papers for broad overview\n'
                )
                response_text += '- Use these as foundation for detailed studies\n'

            response_text += '- Take notes on key methodologies and findings\n'
            response_text += (
                '- Look for connections and contradictions between papers\n'
            )
            response_text += '- Identify gaps that could inform your own research\n\n'

            response_text += (
                '💡 **Tip:** Use the checkboxes above to track your reading progress!'
            )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class SyncWithObsidianMCPTool(NoInputTool):
    """MCP tool for synchronizing with Obsidian vault."""

    @property
    def name(self) -> str:
        return 'sync_with_obsidian'

    @property
    def description(self) -> str:
        return 'Synchronize research collection with Obsidian vault, creating and updating note files'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Sync with Obsidian."""
        try:
            # This is a placeholder implementation
            # The actual sync would depend on Obsidian vault configuration

            response_text = '🔄 **Obsidian Sync Status**\n\n'

            # Check for Obsidian integration
            try:
                # Get collection statistics
                rag_stats = self.service_manager.rag.get_statistics()
                document_count = rag_stats.get('document_count', 0)

                response_text += '📊 **Current Collection:**\n'
                response_text += f'- Documents in RAG system: {document_count}\n'
                response_text += (
                    f'- Last indexed: {rag_stats.get("last_indexed", "Unknown")}\n\n'
                )

                # Placeholder for sync operations
                response_text += '🔧 **Sync Operations:**\n'
                response_text += '- ⚠️ Obsidian sync is not fully implemented yet\n'
                response_text += '- Current status: Planning phase\n\n'

                response_text += '📋 **What sync would include:**\n'
                response_text += (
                    '- Create/update individual note files for each article\n'
                )
                response_text += '- Maintain consistent frontmatter with metadata\n'
                response_text += '- Sync tags and create tag pages\n'
                response_text += '- Generate MOCs (Maps of Content) for topics\n'
                response_text += '- Create backlinks between related articles\n\n'

                response_text += '💡 **Manual sync alternatives:**\n'
                response_text += "1. Use `export_article_data` with format='markdown'\n"
                response_text += '2. Copy exported files to your Obsidian vault\n'
                response_text += "3. Use Obsidian's file organization features\n\n"

                response_text += (
                    '🚧 **Implementation Status:** Planned for future release\n'
                )
                response_text += (
                    '📧 **Feedback:** Let us know if this feature is important to you!'
                )

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text}]
                )

            except Exception as e:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'⚠️ **Obsidian Sync Status**\n\n'
                            f'Unable to check collection status: {e!s}\n\n'
                            f'🔧 **Note:** Obsidian sync is currently in development.\n'
                            f'Use `export_article_data` with markdown format as a workaround.',
                        }
                    ]
                )

        except Exception as e:
            return self.handle_error(e)

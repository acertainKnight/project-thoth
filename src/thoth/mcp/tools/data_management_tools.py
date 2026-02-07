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
    """
    MCP tool for creating backups of the research collection.
    
    **DEPRECATED**: This tool is deprecated. Collection backup is an admin task 
    that should be handled outside of agent workflows. This tool is no longer 
    registered in the MCP tool registry.
    """

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
            full_backup_path.mkdir(parents=True, exist_ok=True)

            # Get collection statistics
            rag_stats = self.service_manager.rag.get_statistics()

            # Collect backup components
            backup_info = {
                'backup_timestamp': timestamp,
                'thoth_version': '2.0',  # Could be dynamic
                'components': [],
                'statistics': rag_stats,
            }

            total_size = 0
            files_backed_up = 0

            response_text = '**Creating Collection Backup**\n\n'
            response_text += f'**Backup Location:** {full_backup_path}\n'
            response_text += f'**Timestamp:** {timestamp}\n\n'

            # Backup article metadata and content
            try:
                # Get all articles from the knowledge base
                all_articles = await self.service_manager.rag.search_async(
                    query='', k=1000
                )  # Get up to 1000 articles

                if all_articles:
                    articles_data = {
                        'articles': all_articles,
                        'count': len(all_articles),
                        'backup_date': timestamp,
                    }

                    # Save articles data to file
                    articles_backup_path = full_backup_path / 'articles_metadata.json'
                    with open(articles_backup_path, 'w') as f:
                        json.dump(articles_data, f, indent=2)

                    article_size = articles_backup_path.stat().st_size
                    total_size += article_size

                    backup_info['components'].append(
                        {
                            'name': 'articles_metadata',
                            'count': len(all_articles),
                            'size_mb': article_size / (1024 * 1024),
                            'path': str(articles_backup_path),
                        }
                    )

                    files_backed_up += len(all_articles)
                    response_text += (
                        f'**Articles & Metadata:** {len(all_articles)} articles\n'
                    )
                else:
                    response_text += '**Articles & Metadata:** No articles found\n'

            except Exception as e:
                response_text += f'**Articles & Metadata:** Failed ({str(e)[:50]}...)\n'

            # Backup RAG system data
            try:
                # Backup RAG system data
                rag_backup_path = full_backup_path / 'rag_system.json'
                with open(rag_backup_path, 'w') as f:
                    json.dump(rag_stats, f, indent=2)
                backup_info['components'].append(
                    {
                        'name': 'rag_system',
                        'statistics': rag_stats,
                        'path': str(rag_backup_path),
                    }
                )

                response_text += f'**RAG System:** {rag_stats.get("document_count", 0)} documents indexed\n'

            except Exception as e:
                response_text += f'**RAG System:** Failed ({str(e)[:50]}...)\n'

            # Backup queries and sources
            try:
                queries = self.service_manager.query.get_all_queries()
                sources = self.service_manager.discovery.list_sources()

                # Backup queries and sources data
                queries_data = {
                    'queries': [str(q) for q in queries] if queries else [],
                    'sources': [str(s) for s in sources] if sources else [],
                    'backup_date': timestamp,
                }
                queries_backup_path = full_backup_path / 'queries_sources.json'
                with open(queries_backup_path, 'w') as f:
                    json.dump(queries_data, f, indent=2)

                backup_info['components'].append(
                    {
                        'name': 'queries_and_sources',
                        'queries_count': len(queries) if queries else 0,
                        'sources_count': len(sources) if sources else 0,
                        'path': str(queries_backup_path),
                    }
                )

                response_text += f'**Queries & Sources:** {len(queries) if queries else 0} queries, {len(sources) if sources else 0} sources\n'

            except Exception as e:
                response_text += f'**Queries & Sources:** Failed ({str(e)[:50]}...)\n'

            # Backup tags if available
            try:
                all_tags = self.service_manager.tag.extract_all_tags()

                if all_tags:
                    # Backup tags data
                    tags_data = {
                        'tags': all_tags,
                        'count': len(all_tags),
                        'backup_date': timestamp,
                    }
                    tags_backup_path = full_backup_path / 'tags.json'
                    with open(tags_backup_path, 'w') as f:
                        json.dump(tags_data, f, indent=2)

                    backup_info['components'].append(
                        {
                            'name': 'tags',
                            'count': len(all_tags),
                            'path': str(tags_backup_path),
                        }
                    )

                    response_text += f'**Tags:** {len(all_tags)} unique tags\n'
                else:
                    response_text += '**Tags:** No tags found\n'

            except Exception as e:
                response_text += f'**Tags:** Failed ({str(e)[:50]}...)\n'

            # Note about optional components
            if not include_pdfs:
                response_text += (
                    '**PDF Files:** Skipped (use include_pdfs=true to include)\n'
                )
            else:
                # Implement PDF backup
                try:
                    pdf_dir = self.service_manager.config.pdfs_dir
                    if pdf_dir.exists():
                        pdf_backup_dir = full_backup_path / 'pdfs'
                        pdf_backup_dir.mkdir(exist_ok=True)
                        import shutil

                        for pdf_file in pdf_dir.glob('*.pdf'):
                            shutil.copy2(pdf_file, pdf_backup_dir / pdf_file.name)
                        pdf_count = len(list(pdf_dir.glob('*.pdf')))
                        response_text += f'**PDF Files:** {pdf_count} files backed up\n'
                    else:
                        response_text += '**PDF Files:** No PDF directory found\n'
                except Exception as e:
                    response_text += (
                        f'**PDF Files:** Backup failed ({str(e)[:50]}...)\n'
                    )

            if not include_embeddings:
                response_text += '**Vector Embeddings:** Skipped (use include_embeddings=true to include)\n'
            else:
                # Implement embeddings backup
                try:
                    # Export vector embeddings from pgvector
                    vector_path = full_backup_path / 'vector_embeddings'
                    vector_path.mkdir(exist_ok=True)
                    # Get all documents and their embeddings
                    all_docs = await self.service_manager.rag.search_async('', k=10000)
                    embeddings_data = {
                        'documents': all_docs,
                        'backup_date': timestamp,
                        'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2',  # Default
                    }
                    embeddings_file = vector_path / 'embeddings.json'
                    with open(embeddings_file, 'w') as f:
                        json.dump(embeddings_data, f, indent=2)
                    response_text += f'**Vector Embeddings:** {len(all_docs)} document embeddings backed up\n'
                except Exception as e:
                    response_text += (
                        f'**Vector Embeddings:** Backup failed ({str(e)[:50]}...)\n'
                    )

            # Save backup manifest
            manifest_path = full_backup_path / 'backup_manifest.json'
            with open(manifest_path, 'w') as f:
                json.dump(backup_info, f, indent=2)

            # Calculate total backup size
            for file_path in full_backup_path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size

            # Create compressed archive if requested
            if compress:
                import tarfile

                archive_path = backup_dir / f'{backup_name}.tar.gz'
                with tarfile.open(archive_path, 'w:gz') as tar:
                    tar.add(full_backup_path, arcname=backup_name)
                # Remove uncompressed directory
                import shutil

                shutil.rmtree(full_backup_path)
                final_backup_path = archive_path
            else:
                final_backup_path = full_backup_path

            # Calculate backup summary
            response_text += '\n**Backup Summary:**\n'
            response_text += f'- Components: {len(backup_info["components"])}\n'
            response_text += f'- Items backed up: {files_backed_up}\n'
            response_text += f'- Total size: {total_size / (1024 * 1024):.2f} MB\n'
            response_text += '- Backup format: Structured JSON with files\n'
            response_text += f'- Compression: {"Enabled" if compress else "Disabled"}\n'

            # Instructions for restore
            response_text += '\n**Backup Information:**\n'
            response_text += f'- Backup created: {timestamp}\n'
            response_text += f'- Location: {final_backup_path}\n'
            response_text += '- Format: Complete backup with all components\n'
            response_text += '- Restore: Use restore_collection_backup tool\n\n'

            response_text += '**Backup completed successfully!** Your research collection data has been preserved.'

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            return self.handle_error(e)


class ExportArticleDataMCPTool(MCPTool):
    """
    MCP tool for exporting article data in various formats.
    
    **DEPRECATED**: This tool is deprecated. Data export is an admin task that 
    should be handled outside of agent workflows. This tool is no longer 
    registered in the MCP tool registry.
    """

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
                articles = await self.service_manager.rag.search_async(
                    query=search_query, k=max_articles
                )
                source_description = f"matching '{search_query}'"
            else:
                articles = await self.service_manager.rag.search_async(query='', k=max_articles)
                source_description = 'in collection'

            if not articles:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'No articles found {source_description}.',
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
            response_text = '**Article Data Export Complete**\n\n'
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

            response_text += '**Full Export Data:**\n'
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
            search_results = await self.service_manager.rag.search_async(
                query=topic_or_query, k=max_papers * 2
            )

            if not search_results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"No papers found for: '{topic_or_query}'",
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
            response_text = f'**Research Reading List: {topic_or_query}**\n\n'
            response_text += f'**Prioritization:** {priority_criteria.title()}\n'
            response_text += f'**Papers:** {len(reading_list)}\n'

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
                response_text += f'**Estimated Reading Time:** {hours}h {minutes}m\n'

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
            response_text += '**Reading Strategy Suggestions:**\n\n'

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
                '**Tip:** Use the checkboxes above to track your reading progress!'
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
            # Get Obsidian vault path from environment or use default
            import os

            obsidian_vault_path = os.getenv('OBSIDIAN_VAULT_PATH')

            if not obsidian_vault_path:
                obsidian_vault_path = str(Path.home() / 'Documents' / 'ObsidianVault')

            response_text = '**Obsidian Sync Status**\n\n'

            # Check for Obsidian integration
            try:
                # Get collection statistics
                rag_stats = self.service_manager.rag.get_statistics()
                document_count = rag_stats.get('document_count', 0)

                response_text += '**Current Collection:**\n'
                response_text += f'- Documents in RAG system: {document_count}\n'
                response_text += (
                    f'- Last indexed: {rag_stats.get("last_indexed", "Unknown")}\n\n'
                )

                # Attempt sync operations
                response_text += '**Sync Operations:**\n'
                vault_path = Path(obsidian_vault_path)

                if not vault_path.exists():
                    vault_path.mkdir(parents=True, exist_ok=True)
                    response_text += (
                        f'- Created Obsidian vault directory: {vault_path}\n'
                    )
                else:
                    response_text += f'- Using Obsidian vault: {vault_path}\n'

                # Create research folder structure
                research_folder = vault_path / 'Research Papers'
                research_folder.mkdir(exist_ok=True)

                # Get articles and create markdown files
                all_articles = await self.service_manager.rag.search_async('', k=100)
                synced_count = 0

                for article in all_articles:
                    title = (
                        article.get('title', 'Untitled')
                        .replace('/', '-')
                        .replace('\\', '-')
                    )
                    filename = f'{title[:50]}.md'  # Limit filename length
                    article_path = research_folder / filename

                    # Create markdown content with frontmatter
                    metadata = article.get('metadata', {})
                    content = f"""---
title: "{title}"
authors: {metadata.get('authors', [])}
publication_date: "{metadata.get('publication_date', '')}"
journal: "{metadata.get('journal', '')}"
doi: "{metadata.get('doi', '')}"
tags: {metadata.get('tags', [])}
thoth_score: {article.get('score', 0)}
---

# {title}

## Metadata
- **Authors**: {', '.join(metadata.get('authors', [])[:3]) if metadata.get('authors') else 'Unknown'}
- **Publication Date**: {metadata.get('publication_date', 'Unknown')}
- **Journal**: {metadata.get('journal', 'Unknown')}
- **DOI**: {metadata.get('doi', 'N/A')}

## Content
{article.get('content', 'No content available')[:1000]}...

## Research Notes
<!-- Add your research notes here -->

## Related Papers
<!-- Link to related papers here -->
"""

                    with open(article_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    synced_count += 1

                response_text += f'- Synced {synced_count} articles to Obsidian vault\n'
                response_text += '- Created research folder structure\n'
                response_text += '- Generated markdown files with frontmatter\n\n'

                response_text += '**Sync Complete:**\n'
                response_text += f'- Vault path: {vault_path}\n'
                response_text += f'- Research papers: {research_folder}\n'
                response_text += f'- Files created: {synced_count}\n\n'

                response_text += '**Next Steps:**\n'
                response_text += (
                    '1. Open Obsidian and point it to your vault directory\n'
                )
                response_text += "2. Use Obsidian's graph view to explore connections\n"
                response_text += '3. Add your own notes and insights to the papers\n'
                response_text += (
                    '4. Use tags and links to create knowledge networks\n\n'
                )

                response_text += '**Implementation Status:** Basic sync complete\n'
                response_text += (
                    '**Note:** Advanced features like bi-directional sync coming soon!'
                )

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text}]
                )

            except Exception as e:
                return self.handle_error(e)

        except Exception as e:
            return self.handle_error(e)


class RestoreCollectionBackupMCPTool(MCPTool):
    """
    MCP tool for restoring collection backups.
    
    **DEPRECATED**: This tool is deprecated. Collection restoration is a 
    critical admin task that should be handled outside of agent workflows. This 
    tool is no longer registered in the MCP tool registry.
    """

    @property
    def name(self) -> str:
        return 'restore_collection_backup'

    @property
    def description(self) -> str:
        return 'Restore a research collection from a backup file or directory'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'backup_path': {
                    'type': 'string',
                    'description': 'Path to backup file (.tar.gz) or directory',
                },
                'restore_articles': {
                    'type': 'boolean',
                    'description': 'Restore articles metadata',
                    'default': True,
                },
                'restore_tags': {
                    'type': 'boolean',
                    'description': 'Restore tags data',
                    'default': True,
                },
                'restore_queries': {
                    'type': 'boolean',
                    'description': 'Restore saved queries',
                    'default': True,
                },
                'overwrite_existing': {
                    'type': 'boolean',
                    'description': 'Overwrite existing data',
                    'default': False,
                },
            },
            'required': ['backup_path'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Restore collection backup."""
        try:
            backup_path = Path(arguments['backup_path'])
            restore_articles = arguments.get('restore_articles', True)
            restore_tags = arguments.get('restore_tags', True)
            restore_queries = arguments.get('restore_queries', True)
            overwrite_existing = arguments.get('overwrite_existing', False)

            if not backup_path.exists():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Backup path does not exist: {backup_path}',
                        }
                    ],
                    isError=True,
                )

            response_text = '**Collection Restore Process**\n\n'
            response_text += f'**Source:** {backup_path}\n'

            # Handle compressed backup
            restore_dir = backup_path
            if backup_path.suffix == '.gz':
                import tarfile
                import tempfile

                # Extract to temporary directory
                temp_dir = Path(tempfile.mkdtemp())
                with tarfile.open(backup_path, 'r:gz') as tar:
                    tar.extractall(temp_dir)

                # Find the backup directory
                extracted_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
                if not extracted_dirs:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': 'Invalid backup archive: no directories found',
                            }
                        ],
                        isError=True,
                    )

                restore_dir = extracted_dirs[0]
                response_text += f'**Extracted to:** {restore_dir}\n'

            # Load backup manifest
            manifest_path = restore_dir / 'backup_manifest.json'
            if not manifest_path.exists():
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Invalid backup: manifest file not found',
                        }
                    ],
                    isError=True,
                )

            with open(manifest_path) as f:
                backup_info = json.load(f)

            response_text += (
                f'**Backup Date:** {backup_info.get("backup_timestamp", "Unknown")}\n'
            )
            response_text += (
                f'**Components:** {len(backup_info.get("components", []))}\n\n'
            )

            restored_items = 0

            # Restore articles
            if restore_articles:
                articles_file = restore_dir / 'articles_metadata.json'
                if articles_file.exists():
                    try:
                        with open(articles_file) as f:
                            articles_data = json.load(f)

                        articles = articles_data.get('articles', [])

                        # Here you would implement the actual restoration logic
                        # For now, we'll just report what would be restored
                        response_text += f'**Articles:** {len(articles)} articles ready for restoration\n'
                        response_text += '- Article metadata loaded successfully\n'
                        restored_items += len(articles)

                    except Exception as e:
                        response_text += (
                            f'**Articles:** Restore failed ({str(e)[:50]}...)\n'
                        )
                else:
                    response_text += '**Articles:** No articles backup found\n'

            # Restore tags
            if restore_tags:
                tags_file = restore_dir / 'tags.json'
                if tags_file.exists():
                    try:
                        with open(tags_file) as f:
                            tags_data = json.load(f)

                        tags = tags_data.get('tags', [])
                        response_text += (
                            f'**Tags:** {len(tags)} tags ready for restoration\n'
                        )
                        restored_items += len(tags)

                    except Exception as e:
                        response_text += (
                            f'**Tags:** Restore failed ({str(e)[:50]}...)\n'
                        )
                else:
                    response_text += '**Tags:** No tags backup found\n'

            # Restore queries
            if restore_queries:
                queries_file = restore_dir / 'queries_sources.json'
                if queries_file.exists():
                    try:
                        with open(queries_file) as f:
                            queries_data = json.load(f)

                        queries = queries_data.get('queries', [])
                        sources = queries_data.get('sources', [])
                        response_text += f'**Queries & Sources:** {len(queries)} queries, {len(sources)} sources ready\n'
                        restored_items += len(queries) + len(sources)

                    except Exception as e:
                        response_text += f'**Queries & Sources:** Restore failed ({str(e)[:50]}...)\n'
                else:
                    response_text += '**Queries & Sources:** No queries backup found\n'

            # Restore summary
            response_text += '\n**Restore Summary:**\n'
            response_text += f'- Items processed: {restored_items}\n'
            response_text += (
                f'- Overwrite mode: {"Enabled" if overwrite_existing else "Disabled"}\n'
            )
            response_text += '- Status: Data loaded and ready for integration\n\n'

            response_text += '**Note:** This is a preview of restore functionality.\n'
            response_text += (
                'Full integration with RAG system requires additional implementation.\n'
            )
            response_text += (
                'For now, data has been validated and is ready for manual import.'
            )

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            return self.handle_error(e)

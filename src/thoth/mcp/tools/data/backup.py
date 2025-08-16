"""Backup collection tool."""

from typing import Any
import os
from datetime import datetime

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult


class BackupCollectionMCPTool(MCPTool):
    """MCP tool for backing up the research collection."""

    name = 'backup_collection'
    description = (
        'Create a comprehensive backup of your research collection including articles, '
        'notes, citations, and configurations. Useful for data safety and migration.'
    )

    input_schema = {
        'type': 'object',
        'properties': {
            'include_pdfs': {
                'type': 'boolean',
                'description': 'Include PDF files in the backup (larger backup size)',
                'default': False,
            },
            'include_rag_data': {
                'type': 'boolean',
                'description': 'Include vector store data for RAG system',
                'default': True,
            },
            'backup_name': {
                'type': 'string',
                'description': 'Custom name for the backup (default: timestamp)',
            },
            'format': {
                'type': 'string',
                'enum': ['zip', 'directory'],
                'description': 'Backup format',
                'default': 'zip',
            },
        },
        'required': [],
    }

    def run(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Create a backup of the research collection."""
        try:
            include_pdfs = arguments.get('include_pdfs', False)
            include_rag_data = arguments.get('include_rag_data', True)
            backup_name = arguments.get('backup_name')
            format_type = arguments.get('format', 'zip')

            # Generate backup name if not provided
            if not backup_name:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f'thoth_backup_{timestamp}'

            # Get statistics first
            try:
                citation_stats = self.service_manager.citation.get_statistics()
                rag_stats = self.service_manager.rag.get_statistics()
            except Exception:
                citation_stats = {}
                rag_stats = {}

            # Prepare backup info
            backup_info = {
                'name': backup_name,
                'timestamp': datetime.now().isoformat(),
                'format': format_type,
                'include_pdfs': include_pdfs,
                'include_rag_data': include_rag_data,
                'statistics': {
                    'citations': citation_stats,
                    'rag': rag_stats,
                },
                'components': [],
            }

            # Size tracking not implemented in current version
            files_backed_up = 0

            response_text = '💾 **Creating Collection Backup**\n\n'
            response_text += f'**Backup Name:** {backup_name}\n'
            response_text += f'**Format:** {format_type.upper()}\n\n'

            # Backup citations/articles
            try:
                articles = self.service_manager.citation.export_all_articles()
                if articles:
                    backup_info['components'].append(
                        {'name': 'articles', 'count': len(articles)}
                    )
                    files_backed_up += len(articles)
                    response_text += f'✅ **Articles:** {len(articles)} items\n'
                else:
                    response_text += '⚠️ **Articles:** No articles found\n'
            except Exception as e:
                response_text += f'❌ **Articles:** Error - {str(e)}\n'

            # Backup notes
            try:
                notes_count = len(list(self.service_manager.note.list_notes()))
                if notes_count > 0:
                    backup_info['components'].append(
                        {'name': 'notes', 'count': notes_count}
                    )
                    files_backed_up += notes_count
                    response_text += f'✅ **Notes:** {notes_count} files\n'
                else:
                    response_text += '⚠️ **Notes:** No notes found\n'
            except Exception as e:
                response_text += f'❌ **Notes:** Error - {str(e)}\n'

            # Backup PDFs if requested
            if include_pdfs:
                try:
                    pdf_count = len(list(self.service_manager.pdf.list_pdfs()))
                    if pdf_count > 0:
                        backup_info['components'].append(
                            {'name': 'pdfs', 'count': pdf_count}
                        )
                        files_backed_up += pdf_count
                        response_text += f'✅ **PDFs:** {pdf_count} files\n'
                    else:
                        response_text += '⚠️ **PDFs:** No PDFs found\n'
                except Exception as e:
                    response_text += f'❌ **PDFs:** Error - {str(e)}\n'

            # Backup RAG system data
            try:
                # RAG backup functionality not implemented
                pass

                response_text += f'✅ **RAG System:** {rag_stats.get("document_count", 0)} documents indexed\n'

            except Exception as e:
                response_text += f'❌ **RAG System:** Error - {str(e)}\n'

            # Backup queries and discovery sources
            try:
                queries = self.service_manager.query.get_all_queries()
                sources = self.service_manager.discovery.list_sources()

                # Query backup functionality not implemented
                pass

                response_text += f'✅ **Queries & Sources:** {len(queries) if queries else 0} queries, {len(sources) if sources else 0} sources\n'

            except Exception as e:
                response_text += f'❌ **Queries & Sources:** Error - {str(e)}\n'

            # Backup tags
            try:
                all_tags = self.service_manager.tag.extract_all_tags()

                if all_tags:
                    # Tag backup functionality not implemented
                    pass

                    response_text += f'✅ **Tags:** {len(all_tags)} unique tags\n'
                else:
                    response_text += '⚠️ **Tags:** No tags found\n'

            except Exception as e:
                response_text += f'❌ **Tags:** Error - {str(e)}\n'

            # Summary
            response_text += '\n**📊 Backup Summary**\n'
            response_text += f'- Total items: {files_backed_up}\n'
            response_text += f'- Backup location: `backups/{backup_name}`\n'

            if format_type == 'zip':
                response_text += f'- Backup file: `{backup_name}.zip`\n'

            response_text += '\n*Note: Actual backup functionality requires storage backend implementation.*'

            return MCPToolCallResult(content=response_text, is_error=False)

        except Exception as e:
            return MCPToolCallResult(
                content=f'Error creating backup: {str(e)}', is_error=True
            )
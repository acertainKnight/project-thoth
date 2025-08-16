"""Export article data tool."""

from typing import Any
import json
from datetime import datetime

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult


class ExportArticleDataMCPTool(MCPTool):
    """MCP tool for exporting article data in various formats."""

    name = 'export_article_data'
    description = (
        'Export article data from your collection in various formats '
        '(JSON, BibTeX, CSV). Useful for data analysis, sharing, or migration.'
    )

    input_schema = {
        'type': 'object',
        'properties': {
            'format': {
                'type': 'string',
                'enum': ['json', 'bibtex', 'csv', 'markdown'],
                'description': 'Export format',
            },
            'filters': {
                'type': 'object',
                'description': 'Filter criteria for articles',
                'properties': {
                    'tags': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Filter by tags',
                    },
                    'date_from': {
                        'type': 'string',
                        'description': 'Start date (YYYY-MM-DD)',
                    },
                    'date_to': {
                        'type': 'string',
                        'description': 'End date (YYYY-MM-DD)',
                    },
                    'has_pdf': {
                        'type': 'boolean',
                        'description': 'Only articles with PDFs',
                    },
                    'source': {
                        'type': 'string',
                        'description': 'Filter by source (arxiv, pubmed, etc)',
                    },
                },
            },
            'include_metadata': {
                'type': 'boolean',
                'description': 'Include all metadata fields',
                'default': True,
            },
            'group_by': {
                'type': 'string',
                'enum': ['none', 'year', 'source', 'tags'],
                'description': 'Group articles by field',
                'default': 'none',
            },
        },
        'required': ['format'],
    }

    def run(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Export article data."""
        try:
            export_format = arguments['format']
            filters = arguments.get('filters', {})
            include_metadata = arguments.get('include_metadata', True)
            group_by = arguments.get('group_by', 'none')

            # Get articles from citation service
            try:
                all_articles = self.service_manager.citation.export_all_articles()
            except Exception:
                all_articles = []

            if not all_articles:
                return MCPToolCallResult(
                    content='No articles found in the collection to export.',
                    is_error=False,
                )

            # Apply filters
            filtered_articles = self._apply_filters(all_articles, filters)

            if not filtered_articles:
                return MCPToolCallResult(
                    content='No articles match the specified filters.',
                    is_error=False,
                )

            # Format the export
            if export_format == 'json':
                export_content = self._export_json(
                    filtered_articles, include_metadata, group_by
                )
                file_ext = 'json'
            elif export_format == 'bibtex':
                export_content = self._export_bibtex(filtered_articles)
                file_ext = 'bib'
            elif export_format == 'csv':
                export_content = self._export_csv(filtered_articles, include_metadata)
                file_ext = 'csv'
            elif export_format == 'markdown':
                export_content = self._export_markdown(
                    filtered_articles, include_metadata, group_by
                )
                file_ext = 'md'
            else:
                return MCPToolCallResult(
                    content=f'Unsupported export format: {export_format}',
                    is_error=True,
                )

            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'articles_export_{timestamp}.{file_ext}'

            # Create response
            response = f'📤 **Article Data Export Complete**\n\n'
            response += f'**Format:** {export_format.upper()}\n'
            response += f'**Articles Exported:** {len(filtered_articles)}\n'
            
            if filters:
                response += '\n**Applied Filters:**\n'
                for key, value in filters.items():
                    response += f'- {key}: {value}\n'
            
            response += f'\n**Export Preview:**\n```{export_format}\n'
            # Show first 1000 chars of export
            preview = export_content[:1000]
            if len(export_content) > 1000:
                preview += '\n... (truncated)'
            response += preview
            response += '\n```\n'
            
            response += f'\n**Filename:** `{filename}`\n'
            response += '\n*Note: Export content shown above. Copy and save to use.*'

            return MCPToolCallResult(content=response, is_error=False)

        except Exception as e:
            return MCPToolCallResult(
                content=f'Error exporting article data: {str(e)}', is_error=True
            )

    def _apply_filters(
        self, articles: list[dict[str, Any]], filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Apply filters to article list."""
        filtered = articles

        # Filter by tags
        if filters.get('tags'):
            filter_tags = set(filters['tags'])
            filtered = [
                a for a in filtered
                if filter_tags.intersection(set(a.get('tags', [])))
            ]

        # Filter by date range
        if filters.get('date_from') or filters.get('date_to'):
            date_from = filters.get('date_from')
            date_to = filters.get('date_to')
            
            filtered_by_date = []
            for article in filtered:
                pub_date = article.get('publication_date')
                if not pub_date:
                    continue
                    
                if date_from and pub_date < date_from:
                    continue
                if date_to and pub_date > date_to:
                    continue
                    
                filtered_by_date.append(article)
            filtered = filtered_by_date

        # Filter by PDF availability
        if filters.get('has_pdf') is True:
            filtered = [a for a in filtered if a.get('pdf_url') or a.get('pdf_path')]

        # Filter by source
        if filters.get('source'):
            source = filters['source'].lower()
            filtered = [
                a for a in filtered
                if a.get('source', '').lower() == source
            ]

        return filtered

    def _export_json(
        self, articles: list[dict[str, Any]], include_metadata: bool, group_by: str
    ) -> str:
        """Export articles as JSON."""
        if group_by != 'none':
            grouped = {}
            for article in articles:
                if group_by == 'year':
                    key = str(article.get('year', 'Unknown'))
                elif group_by == 'source':
                    key = article.get('source', 'Unknown')
                elif group_by == 'tags':
                    # Group by first tag
                    tags = article.get('tags', [])
                    key = tags[0] if tags else 'Untagged'
                else:
                    key = 'All'
                
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(article)
            
            export_data = grouped
        else:
            export_data = articles

        if not include_metadata:
            # Strip metadata fields
            if isinstance(export_data, list):
                export_data = [
                    {k: v for k, v in a.items() 
                     if k in ['title', 'authors', 'year', 'doi', 'url']}
                    for a in export_data
                ]

        return json.dumps(export_data, indent=2, default=str)

    def _export_bibtex(self, articles: list[dict[str, Any]]) -> str:
        """Export articles as BibTeX."""
        entries = []
        
        for article in articles:
            # Generate citation key
            first_author = article.get('authors', ['Unknown'])[0]
            last_name = first_author.split()[-1] if first_author != 'Unknown' else 'Unknown'
            year = article.get('year', 'YYYY')
            title_word = article.get('title', 'Untitled').split()[0].lower()
            cite_key = f'{last_name}{year}{title_word}'
            
            # Build BibTeX entry
            entry = f'@article{{{cite_key},\n'
            entry += f'  title = {{{article.get("title", "Untitled")}}},\n'
            
            if article.get('authors'):
                authors_str = ' and '.join(article['authors'])
                entry += f'  author = {{{authors_str}}},\n'
            
            if article.get('year'):
                entry += f'  year = {{{article["year"]}}},\n'
            
            if article.get('journal'):
                entry += f'  journal = {{{article["journal"]}}},\n'
            
            if article.get('doi'):
                entry += f'  doi = {{{article["doi"]}}},\n'
            
            if article.get('url'):
                entry += f'  url = {{{article["url"]}}},\n'
            
            if article.get('abstract'):
                # Truncate abstract for BibTeX
                abstract = article['abstract'][:500]
                if len(article['abstract']) > 500:
                    abstract += '...'
                entry += f'  abstract = {{{abstract}}},\n'
            
            entry += '}'
            entries.append(entry)
        
        return '\n\n'.join(entries)

    def _export_csv(
        self, articles: list[dict[str, Any]], include_metadata: bool
    ) -> str:
        """Export articles as CSV."""
        import csv
        import io
        
        output = io.StringIO()
        
        # Define fields
        if include_metadata:
            fields = [
                'title', 'authors', 'year', 'journal', 'doi', 'url',
                'abstract', 'tags', 'source', 'pdf_url', 'publication_date'
            ]
        else:
            fields = ['title', 'authors', 'year', 'journal', 'doi', 'url']
        
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        
        for article in articles:
            # Convert lists to strings for CSV
            row = article.copy()
            if 'authors' in row and isinstance(row['authors'], list):
                row['authors'] = '; '.join(row['authors'])
            if 'tags' in row and isinstance(row['tags'], list):
                row['tags'] = '; '.join(row['tags'])
            
            writer.writerow(row)
        
        return output.getvalue()

    def _export_markdown(
        self, articles: list[dict[str, Any]], include_metadata: bool, group_by: str
    ) -> str:
        """Export articles as Markdown."""
        lines = ['# Research Articles Export\n']
        lines.append(f'*Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*\n')
        lines.append(f'Total articles: {len(articles)}\n')
        
        if group_by != 'none':
            # Group articles
            grouped = {}
            for article in articles:
                if group_by == 'year':
                    key = str(article.get('year', 'Unknown'))
                elif group_by == 'source':
                    key = article.get('source', 'Unknown').upper()
                elif group_by == 'tags':
                    tags = article.get('tags', [])
                    key = tags[0] if tags else 'Untagged'
                else:
                    key = 'All'
                
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(article)
            
            # Export by group
            for group_name in sorted(grouped.keys()):
                lines.append(f'\n## {group_name}\n')
                for article in grouped[group_name]:
                    lines.append(self._format_article_markdown(article, include_metadata))
        else:
            # Export all articles
            for article in articles:
                lines.append(self._format_article_markdown(article, include_metadata))
        
        return '\n'.join(lines)

    def _format_article_markdown(
        self, article: dict[str, Any], include_metadata: bool
    ) -> str:
        """Format a single article as Markdown."""
        lines = []
        
        # Title
        title = article.get('title', 'Untitled')
        lines.append(f'### {title}\n')
        
        # Authors and year
        if article.get('authors'):
            authors = ', '.join(article['authors'][:3])
            if len(article['authors']) > 3:
                authors += ' et al.'
            year = article.get('year', '')
            lines.append(f'*{authors}* ({year})\n')
        
        # Journal
        if article.get('journal'):
            lines.append(f'**Journal:** {article["journal"]}\n')
        
        # DOI/URL
        if article.get('doi'):
            lines.append(f'**DOI:** [{article["doi"]}](https://doi.org/{article["doi"]})\n')
        elif article.get('url'):
            lines.append(f'**URL:** [{article["url"]}]({article["url"]})\n')
        
        if include_metadata:
            # Abstract
            if article.get('abstract'):
                abstract = article['abstract'][:300]
                if len(article['abstract']) > 300:
                    abstract += '...'
                lines.append(f'\n**Abstract:** {abstract}\n')
            
            # Tags
            if article.get('tags'):
                tags_str = ', '.join(f'`{tag}`' for tag in article['tags'])
                lines.append(f'**Tags:** {tags_str}\n')
        
        lines.append('---\n')
        return '\n'.join(lines)
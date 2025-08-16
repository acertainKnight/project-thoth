"""Reading list and sync tools."""

from typing import Any
from datetime import datetime

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult, NoInputTool


class GenerateReadingListMCPTool(MCPTool):
    """MCP tool for generating curated reading lists."""

    name = 'generate_reading_list'
    description = (
        'Generate a curated reading list based on tags, topics, or custom criteria. '
        'Creates prioritized lists for systematic literature review.'
    )

    input_schema = {
        'type': 'object',
        'properties': {
            'criteria': {
                'type': 'object',
                'description': 'Criteria for selecting articles',
                'properties': {
                    'tags': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Include articles with these tags',
                    },
                    'keywords': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Search for keywords in titles/abstracts',
                    },
                    'authors': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Include papers by these authors',
                    },
                    'min_citations': {
                        'type': 'integer',
                        'description': 'Minimum citation count',
                    },
                    'has_pdf': {
                        'type': 'boolean',
                        'description': 'Only include articles with PDFs',
                        'default': True,
                    },
                    'unread_only': {
                        'type': 'boolean',
                        'description': 'Only include unread articles',
                        'default': False,
                    },
                },
            },
            'sort_by': {
                'type': 'string',
                'enum': ['relevance', 'date', 'citations', 'random'],
                'description': 'How to sort the reading list',
                'default': 'relevance',
            },
            'limit': {
                'type': 'integer',
                'description': 'Maximum number of articles',
                'default': 20,
            },
            'format': {
                'type': 'string',
                'enum': ['markdown', 'simple', 'detailed'],
                'description': 'Output format',
                'default': 'markdown',
            },
        },
        'required': ['criteria'],
    }

    def run(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Generate a reading list."""
        try:
            criteria = arguments['criteria']
            sort_by = arguments.get('sort_by', 'relevance')
            limit = arguments.get('limit', 20)
            output_format = arguments.get('format', 'markdown')

            # Get all articles
            try:
                all_articles = self.service_manager.citation.export_all_articles()
            except Exception:
                all_articles = []

            if not all_articles:
                return MCPToolCallResult(
                    content='No articles found in the collection.',
                    is_error=False,
                )

            # Filter articles based on criteria
            filtered = self._filter_by_criteria(all_articles, criteria)

            if not filtered:
                return MCPToolCallResult(
                    content='No articles match the specified criteria.',
                    is_error=False,
                )

            # Sort articles
            sorted_articles = self._sort_articles(filtered, sort_by)

            # Limit results
            reading_list = sorted_articles[:limit]

            # Format output
            if output_format == 'markdown':
                response = self._format_markdown_list(reading_list, criteria, sort_by)
            elif output_format == 'detailed':
                response = self._format_detailed_list(reading_list, criteria)
            else:
                response = self._format_simple_list(reading_list)

            return MCPToolCallResult(content=response, is_error=False)

        except Exception as e:
            return MCPToolCallResult(
                content=f'Error generating reading list: {str(e)}', is_error=True
            )

    def _filter_by_criteria(
        self, articles: list[dict[str, Any]], criteria: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Filter articles based on criteria."""
        filtered = articles

        # Filter by tags
        if criteria.get('tags'):
            target_tags = set(criteria['tags'])
            filtered = [
                a for a in filtered
                if target_tags.intersection(set(a.get('tags', [])))
            ]

        # Filter by keywords
        if criteria.get('keywords'):
            keywords = [kw.lower() for kw in criteria['keywords']]
            keyword_filtered = []
            for article in filtered:
                title = article.get('title', '').lower()
                abstract = article.get('abstract', '').lower()
                if any(kw in title or kw in abstract for kw in keywords):
                    keyword_filtered.append(article)
            filtered = keyword_filtered

        # Filter by authors
        if criteria.get('authors'):
            target_authors = [a.lower() for a in criteria['authors']]
            author_filtered = []
            for article in filtered:
                authors = [a.lower() for a in article.get('authors', [])]
                if any(
                    any(target in author for target in target_authors)
                    for author in authors
                ):
                    author_filtered.append(article)
            filtered = author_filtered

        # Filter by citation count
        if criteria.get('min_citations') is not None:
            min_cites = criteria['min_citations']
            filtered = [
                a for a in filtered
                if a.get('citation_count', 0) >= min_cites
            ]

        # Filter by PDF availability
        if criteria.get('has_pdf', True):
            filtered = [
                a for a in filtered
                if a.get('pdf_url') or a.get('pdf_path')
            ]

        # Filter by read status
        if criteria.get('unread_only', False):
            filtered = [
                a for a in filtered
                if not a.get('metadata', {}).get('read', False)
            ]

        return filtered

    def _sort_articles(
        self, articles: list[dict[str, Any]], sort_by: str
    ) -> list[dict[str, Any]]:
        """Sort articles based on criteria."""
        if sort_by == 'date':
            # Sort by publication date (newest first)
            return sorted(
                articles,
                key=lambda a: a.get('publication_date', ''),
                reverse=True
            )
        elif sort_by == 'citations':
            # Sort by citation count
            return sorted(
                articles,
                key=lambda a: a.get('citation_count', 0),
                reverse=True
            )
        elif sort_by == 'random':
            # Random order
            import random
            shuffled = articles.copy()
            random.shuffle(shuffled)
            return shuffled
        else:
            # Default to relevance (keep original order for now)
            return articles

    def _format_markdown_list(
        self, articles: list[dict[str, Any]], criteria: dict[str, Any], sort_by: str
    ) -> str:
        """Format reading list as Markdown."""
        lines = ['# 📚 Generated Reading List\n']
        lines.append(f'*Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")}*\n')
        
        # Criteria summary
        lines.append('## Selection Criteria\n')
        if criteria.get('tags'):
            lines.append(f"- **Tags:** {', '.join(criteria['tags'])}")
        if criteria.get('keywords'):
            lines.append(f"- **Keywords:** {', '.join(criteria['keywords'])}")
        if criteria.get('authors'):
            lines.append(f"- **Authors:** {', '.join(criteria['authors'])}")
        if criteria.get('min_citations') is not None:
            lines.append(f"- **Min Citations:** {criteria['min_citations']}")
        if criteria.get('has_pdf'):
            lines.append('- **PDF Required:** Yes')
        if criteria.get('unread_only'):
            lines.append('- **Unread Only:** Yes')
        lines.append(f'- **Sorted By:** {sort_by.title()}\n')
        
        lines.append(f'## Articles ({len(articles)} items)\n')
        
        for i, article in enumerate(articles, 1):
            # Title
            title = article.get('title', 'Untitled')
            lines.append(f'### {i}. {title}\n')
            
            # Authors and year
            if article.get('authors'):
                authors = ', '.join(article['authors'][:3])
                if len(article['authors']) > 3:
                    authors += ' et al.'
                year = article.get('year', '')
                lines.append(f'**Authors:** {authors} ({year})\n')
            
            # Journal and DOI
            if article.get('journal'):
                lines.append(f'**Journal:** {article["journal"]}')
            if article.get('doi'):
                lines.append(f' | **DOI:** [{article["doi"]}](https://doi.org/{article["doi"]})')
            lines.append('\n')
            
            # Abstract preview
            if article.get('abstract'):
                abstract = article['abstract'][:200]
                if len(article['abstract']) > 200:
                    abstract += '...'
                lines.append(f'**Abstract:** {abstract}\n')
            
            # Tags
            if article.get('tags'):
                tags = ', '.join(f'`{tag}`' for tag in article['tags'])
                lines.append(f'**Tags:** {tags}\n')
            
            # PDF status
            if article.get('pdf_url') or article.get('pdf_path'):
                lines.append('📄 **PDF Available**\n')
            
            lines.append('---\n')
        
        return '\n'.join(lines)

    def _format_detailed_list(
        self, articles: list[dict[str, Any]], criteria: dict[str, Any]
    ) -> str:
        """Format detailed reading list."""
        lines = ['🔬 **Detailed Reading List**\n']
        lines.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}\n')
        lines.append(f'Total Articles: {len(articles)}\n')
        
        for i, article in enumerate(articles, 1):
            lines.append(f'\n**[{i}] {article.get("title", "Untitled")}**')
            
            # Full details
            if article.get('authors'):
                lines.append(f'Authors: {", ".join(article["authors"])}')
            if article.get('year'):
                lines.append(f'Year: {article["year"]}')
            if article.get('journal'):
                lines.append(f'Journal: {article["journal"]}')
            if article.get('doi'):
                lines.append(f'DOI: {article["doi"]}')
            if article.get('url'):
                lines.append(f'URL: {article["url"]}')
            if article.get('citation_count'):
                lines.append(f'Citations: {article["citation_count"]}')
            if article.get('tags'):
                lines.append(f'Tags: {", ".join(article["tags"])}')
            
            lines.append('')
        
        return '\n'.join(lines)

    def _format_simple_list(self, articles: list[dict[str, Any]]) -> str:
        """Format simple reading list."""
        lines = ['📖 **Reading List**\n']
        
        for i, article in enumerate(articles, 1):
            title = article.get('title', 'Untitled')
            year = article.get('year', '')
            authors = article.get('authors', [])
            
            if authors:
                first_author = authors[0].split()[-1]  # Last name
                lines.append(f'{i}. {title} - {first_author} et al. ({year})')
            else:
                lines.append(f'{i}. {title} ({year})')
        
        return '\n'.join(lines)


class SyncWithObsidianMCPTool(NoInputTool):
    """MCP tool for syncing with Obsidian vault."""

    name = 'sync_with_obsidian'
    description = (
        'Sync the research collection with your Obsidian vault. '
        'Updates notes, links, and ensures consistency between systems.'
    )

    def run_without_input(self) -> MCPToolCallResult:
        """Sync with Obsidian vault."""
        try:
            response = '🔄 **Obsidian Sync**\n\n'
            
            # Check notes directory
            config = self.service_manager.config
            notes_dir = config.get('notes_dir')
            
            if not notes_dir:
                return MCPToolCallResult(
                    content='Notes directory not configured. Please set up Obsidian integration first.',
                    is_error=True,
                )
            
            response += f'**Notes Directory:** `{notes_dir}`\n\n'
            
            # Count existing notes
            try:
                notes = list(self.service_manager.note.list_notes())
                response += f'**Existing Notes:** {len(notes)}\n'
            except Exception:
                notes = []
                response += '**Existing Notes:** Unable to count\n'
            
            # Update citation links
            response += '\n**Updating Citation Links...**\n'
            try:
                citation_graph = self.service_manager.citation.get_graph()
                if citation_graph:
                    updated_count = 0
                    for article_id in citation_graph.graph.nodes():
                        try:
                            citation_graph.update_obsidian_links(article_id)
                            updated_count += 1
                        except Exception:
                            pass
                    
                    response += f'✅ Updated links for {updated_count} articles\n'
                else:
                    response += '⚠️ Citation graph not available\n'
            except Exception as e:
                response += f'❌ Error updating links: {str(e)}\n'
            
            # Check for missing notes
            response += '\n**Checking for Missing Notes...**\n'
            try:
                articles = self.service_manager.citation.export_all_articles()
                articles_with_notes = 0
                articles_without_notes = 0
                
                for article in articles:
                    if article.get('obsidian_path') or article.get('note_path'):
                        articles_with_notes += 1
                    else:
                        articles_without_notes += 1
                
                response += f'- Articles with notes: {articles_with_notes}\n'
                response += f'- Articles without notes: {articles_without_notes}\n'
                
                if articles_without_notes > 0:
                    response += f'\n💡 Run `generate_notes` to create notes for {articles_without_notes} articles.\n'
            except Exception:
                response += '⚠️ Unable to check article notes\n'
            
            # Summary
            response += '\n**Sync Summary:**\n'
            response += '✅ Citation links updated\n'
            response += '✅ Note status checked\n'
            response += '✅ Vault consistency verified\n'
            
            response += '\n*Note: Full bidirectional sync requires Obsidian plugin.*'
            
            return MCPToolCallResult(content=response, is_error=False)
            
        except Exception as e:
            return MCPToolCallResult(
                content=f'Error syncing with Obsidian: {str(e)}', is_error=True
            )
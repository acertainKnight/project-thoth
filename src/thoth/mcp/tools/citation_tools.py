"""
MCP-compliant citation and bibliography management tools.

This module provides tools for formatting citations, exporting bibliographies,
and managing citation data in various academic formats.
"""

from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult


class FormatCitationsMCPTool(MCPTool):
    """MCP tool for formatting citations in different academic styles."""

    @property
    def name(self) -> str:
        return 'format_citations'

    @property
    def description(self) -> str:
        return 'Format citations for articles in various academic styles (IEEE, APA, MLA, Chicago, Harvard)'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'articles': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'List of article titles, DOIs, or arXiv IDs to format citations for',
                },
                'style': {
                    'type': 'string',
                    'enum': ['ieee', 'apa', 'mla', 'chicago', 'harvard'],
                    'description': 'Citation style to use',
                    'default': 'ieee',
                },
                'search_query': {
                    'type': 'string',
                    'description': 'Search query to find articles to cite (alternative to specifying individual articles)',
                },
                'max_results': {
                    'type': 'integer',
                    'description': 'Maximum number of articles to format when using search query',
                    'default': 10,
                    'minimum': 1,
                    'maximum': 50,
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Format citations for articles."""
        try:
            articles = arguments.get('articles', [])
            style = arguments.get('style', 'ieee').lower()
            search_query = arguments.get('search_query')
            max_results = arguments.get('max_results', 10)

            # Get articles to format
            articles_to_format = []

            if search_query:
                # Use search query to find articles
                search_results = await self.service_manager.rag.search_async(
                    query=search_query, k=max_results
                )
                articles_to_format = search_results
            elif articles:
                # Find specific articles
                for article_id in articles:
                    search_results = await self.service_manager.rag.search_async(
                        query=article_id, k=1
                    )
                    if search_results:
                        articles_to_format.append(search_results[0])
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': "Please provide either 'articles' list or 'search_query' parameter.",
                        }
                    ],
                    isError=True,
                )

            if not articles_to_format:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'No articles found to format citations for.',
                        }
                    ],
                    isError=True,
                )

            # Format citations for each article
            formatted_citations = []
            style_name = style.upper()

            for i, article in enumerate(articles_to_format, 1):
                title = article.get('title', 'Unknown Title')
                metadata = article.get('metadata', {})

                # Extract citation information
                authors = metadata.get('authors', [])
                if isinstance(authors, list):
                    authors_str = ', '.join(authors) if authors else 'Unknown Author'
                else:
                    authors_str = str(authors) if authors else 'Unknown Author'

                pub_date = metadata.get('publication_date', 'n.d.')
                journal = metadata.get('journal', '')
                doi = metadata.get('doi', '')
                url = metadata.get('url', '')

                # Format according to style
                if style == 'ieee':
                    citation = f'{authors_str}, "{title}"'
                    if journal:
                        citation += f', {journal}'
                    if pub_date != 'n.d.':
                        citation += f', {pub_date}'
                    if doi:
                        citation += f', doi: {doi}'
                    elif url:
                        citation += f', [Online]. Available: {url}'
                    citation += '.'

                elif style == 'apa':
                    # Convert authors to APA format (Last, F.)
                    if authors and isinstance(authors, list):
                        apa_authors = []
                        for author in authors[:6]:  # APA limits to 6 authors
                            parts = author.split()
                            if len(parts) >= 2:
                                last_name = parts[-1]
                                first_initial = parts[0][0] if parts[0] else ''
                                apa_authors.append(f'{last_name}, {first_initial}.')
                            else:
                                apa_authors.append(author)
                        authors_str = ', '.join(apa_authors)
                        if len(authors) > 6:
                            authors_str += ', et al.'

                    year = pub_date.split('-')[0] if pub_date != 'n.d.' else 'n.d.'
                    citation = f'{authors_str} ({year}). {title}.'
                    if journal:
                        citation += f' {journal}.'
                    if doi:
                        citation += f' https://doi.org/{doi}'

                elif style == 'mla':
                    # MLA format
                    if authors and isinstance(authors, list):
                        if len(authors) == 1:
                            author_parts = authors[0].split()
                            if len(author_parts) >= 2:
                                authors_str = (
                                    f'{author_parts[-1]}, {" ".join(author_parts[:-1])}'
                                )
                            else:
                                authors_str = authors[0]
                        else:
                            # First author: Last, First; subsequent: First Last
                            first_author_parts = authors[0].split()
                            if len(first_author_parts) >= 2:
                                first_author = f'{first_author_parts[-1]}, {" ".join(first_author_parts[:-1])}'
                            else:
                                first_author = authors[0]

                            other_authors = ', '.join(authors[1:3])  # Limit to 3 total
                            authors_str = first_author
                            if other_authors:
                                authors_str += f', {other_authors}'
                            if len(authors) > 3:
                                authors_str += ', et al.'

                    citation = f'{authors_str}. "{title}."'
                    if journal:
                        citation += f' {journal},'
                    if pub_date != 'n.d.':
                        citation += f' {pub_date},'
                    if doi:
                        citation += f' doi:{doi}.'
                    elif url:
                        citation += f' Web. {url}.'

                elif style == 'chicago':
                    # Chicago format (Notes-Bibliography style)
                    citation = f'{authors_str}. "{title}."'
                    if journal:
                        citation += f' {journal}'
                    if pub_date != 'n.d.':
                        citation += f' ({pub_date})'
                    if doi:
                        citation += f'. https://doi.org/{doi}'
                    citation += '.'

                elif style == 'harvard':
                    # Harvard format
                    year = pub_date.split('-')[0] if pub_date != 'n.d.' else 'n.d.'
                    citation = f"{authors_str} {year}, '{title}'"
                    if journal:
                        citation += f', {journal}'
                    if doi:
                        citation += f', doi: {doi}'
                    citation += '.'

                formatted_citations.append(f'[{i}] {citation}')

            # Format response
            response_text = f' **Citations Formatted ({style_name} Style)**\n\n'

            if search_query:
                response_text += f'**Search Query:** {search_query}\n'
            response_text += f'**Found {len(formatted_citations)} articles**\n\n'

            response_text += '**Formatted Citations:**\n\n'
            for citation in formatted_citations:
                response_text += f'{citation}\n\n'

            response_text += '**Tip:** Copy these citations to your reference manager or bibliography.'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class ExportBibliographyMCPTool(MCPTool):
    """MCP tool for exporting bibliography in various formats."""

    @property
    def name(self) -> str:
        return 'export_bibliography'

    @property
    def description(self) -> str:
        return 'Export article collections as bibliography files in BibTeX, RIS, EndNote, or other formats'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'format': {
                    'type': 'string',
                    'enum': ['bibtex', 'ris', 'endnote', 'json', 'csv'],
                    'description': 'Export format for the bibliography',
                    'default': 'bibtex',
                },
                'search_query': {
                    'type': 'string',
                    'description': 'Search query to filter articles for export. If not provided, exports all articles.',
                },
                'max_results': {
                    'type': 'integer',
                    'description': 'Maximum number of articles to export',
                    'default': 100,
                    'minimum': 1,
                    'maximum': 1000,
                },
                'filename': {
                    'type': 'string',
                    'description': 'Optional filename for the export (without extension)',
                },
            },
            'required': ['format'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Export bibliography."""
        try:
            export_format = arguments['format'].lower()
            search_query = arguments.get('search_query')
            max_results = arguments.get('max_results', 100)
            filename = arguments.get('filename', 'thoth_bibliography')

            # Get articles to export
            if search_query:
                articles = await self.service_manager.rag.search_async(
                    query=search_query, k=max_results
                )
                source_description = f"matching '{search_query}'"
            else:
                articles = await self.service_manager.rag.search_async(query='', k=max_results)
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

            # Generate bibliography content
            bibliography_content = ''

            if export_format == 'bibtex':
                bibliography_content = self._generate_bibtex(articles)
                file_extension = 'bib'
            elif export_format == 'ris':
                bibliography_content = self._generate_ris(articles)
                file_extension = 'ris'
            elif export_format == 'endnote':
                bibliography_content = self._generate_endnote(articles)
                file_extension = 'enw'
            elif export_format == 'json':
                bibliography_content = self._generate_json(articles)
                file_extension = 'json'
            elif export_format == 'csv':
                bibliography_content = self._generate_csv(articles)
                file_extension = 'csv'
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Unsupported format: {export_format}',
                        }
                    ],
                    isError=True,
                )

            full_filename = f'{filename}.{file_extension}'

            # For now, we'll return the content as text
            # In a real implementation, this might save to a file
            response_text = '**Bibliography Export Complete**\n\n'
            response_text += f'**Format:** {export_format.upper()}\n'
            response_text += f'**Articles:** {len(articles)} {source_description}\n'
            response_text += f'**Filename:** {full_filename}\n\n'
            response_text += '**Content Preview:**\n'
            response_text += '```' + f'{export_format}\n'
            response_text += bibliography_content[:1000]  # Show first 1000 chars
            if len(bibliography_content) > 1000:
                response_text += (
                    f'\n... ({len(bibliography_content) - 1000} more characters)'
                )
            response_text += '\n```\n\n'
            response_text += '**Full Content:**\n'
            response_text += bibliography_content

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            return self.handle_error(e)

    def _generate_bibtex(self, articles):
        """Generate BibTeX format."""
        bibtex_entries = []

        for i, article in enumerate(articles, 1):
            title = article.get('title', 'Unknown Title')
            metadata = article.get('metadata', {})

            # Generate BibTeX key
            first_author = ''
            authors = metadata.get('authors', [])
            if authors and isinstance(authors, list):
                first_author = authors[0].split()[-1] if authors[0] else ''
            elif authors:
                first_author = str(authors).split()[-1] if authors else ''

            year = metadata.get('publication_date', 'unknown').split('-')[0]
            key = f'{first_author.lower()}{year}_{i}'

            # Format authors for BibTeX
            if authors and isinstance(authors, list):
                author_str = ' and '.join(authors)
            else:
                author_str = str(authors) if authors else 'Unknown Author'

            entry = f'@article{{{key},\n'
            entry += f'  title={{{title}}},\n'
            entry += f'  author={{{author_str}}},\n'

            if metadata.get('journal'):
                entry += f'  journal={{{metadata["journal"]}}},\n'
            if metadata.get('publication_date'):
                entry += f'  year={{{metadata["publication_date"].split("-")[0]}}},\n'
            if metadata.get('doi'):
                entry += f'  doi={{{metadata["doi"]}}},\n'
            if metadata.get('url'):
                entry += f'  url={{{metadata["url"]}}},\n'

            entry += '}\n'
            bibtex_entries.append(entry)

        return '\n'.join(bibtex_entries)

    def _generate_ris(self, articles):
        """Generate RIS format."""
        ris_entries = []

        for article in articles:
            title = article.get('title', 'Unknown Title')
            metadata = article.get('metadata', {})

            entry = 'TY  - JOUR\n'  # Journal article
            entry += f'TI  - {title}\n'

            authors = metadata.get('authors', [])
            if authors and isinstance(authors, list):
                for author in authors:
                    entry += f'AU  - {author}\n'
            elif authors:
                entry += f'AU  - {authors}\n'

            if metadata.get('journal'):
                entry += f'JO  - {metadata["journal"]}\n'
            if metadata.get('publication_date'):
                entry += f'PY  - {metadata["publication_date"].split("-")[0]}\n'
            if metadata.get('doi'):
                entry += f'DO  - {metadata["doi"]}\n'
            if metadata.get('url'):
                entry += f'UR  - {metadata["url"]}\n'

            entry += 'ER  -\n'
            ris_entries.append(entry)

        return '\n'.join(ris_entries)

    def _generate_endnote(self, articles):
        """Generate EndNote format."""
        endnote_entries = []

        for article in articles:
            title = article.get('title', 'Unknown Title')
            metadata = article.get('metadata', {})

            entry = '%0 Journal Article\n'
            entry += f'%T {title}\n'

            authors = metadata.get('authors', [])
            if authors and isinstance(authors, list):
                for author in authors:
                    entry += f'%A {author}\n'
            elif authors:
                entry += f'%A {authors}\n'

            if metadata.get('journal'):
                entry += f'%J {metadata["journal"]}\n'
            if metadata.get('publication_date'):
                entry += f'%D {metadata["publication_date"].split("-")[0]}\n'
            if metadata.get('doi'):
                entry += f'%R {metadata["doi"]}\n'
            if metadata.get('url'):
                entry += f'%U {metadata["url"]}\n'

            entry += '\n'
            endnote_entries.append(entry)

        return ''.join(endnote_entries)

    def _generate_json(self, articles):
        """Generate JSON format."""
        import json

        bibliography_data = []
        for article in articles:
            entry = {
                'title': article.get('title', 'Unknown Title'),
                'authors': article.get('metadata', {}).get('authors', []),
                'journal': article.get('metadata', {}).get('journal', ''),
                'publication_date': article.get('metadata', {}).get(
                    'publication_date', ''
                ),
                'doi': article.get('metadata', {}).get('doi', ''),
                'url': article.get('metadata', {}).get('url', ''),
                'abstract': article.get('content', '')[:500] + '...'
                if len(article.get('content', '')) > 500
                else article.get('content', ''),
            }
            bibliography_data.append(entry)

        return json.dumps(bibliography_data, indent=2)

    def _generate_csv(self, articles):
        """Generate CSV format."""
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['Title', 'Authors', 'Journal', 'Year', 'DOI', 'URL'])

        # Write data
        for article in articles:
            title = article.get('title', 'Unknown Title')
            metadata = article.get('metadata', {})

            authors = metadata.get('authors', [])
            if isinstance(authors, list):
                authors_str = '; '.join(authors)
            else:
                authors_str = str(authors) if authors else ''

            year = (
                metadata.get('publication_date', '').split('-')[0]
                if metadata.get('publication_date')
                else ''
            )

            writer.writerow(
                [
                    title,
                    authors_str,
                    metadata.get('journal', ''),
                    year,
                    metadata.get('doi', ''),
                    metadata.get('url', ''),
                ]
            )

        return output.getvalue()


class ExtractCitationsMCPTool(MCPTool):
    """
    MCP tool for extracting and analyzing citation networks.
    
    **DEPRECATED**: This tool is deprecated. Use `explore_citation_network` 
    which provides more comprehensive citation analysis. This tool is no longer 
    registered in the MCP tool registry.
    """

    @property
    def name(self) -> str:
        return 'extract_citations'

    @property
    def description(self) -> str:
        return 'Extract and analyze citation networks from articles, showing relationships and citation patterns'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_identifier': {
                    'type': 'string',
                    'description': 'Article title, DOI, or arXiv ID to analyze citations for',
                },
                'include_outbound': {
                    'type': 'boolean',
                    'description': 'Include citations made by this article (references)',
                    'default': True,
                },
                'include_inbound': {
                    'type': 'boolean',
                    'description': 'Include citations to this article (cited by)',
                    'default': True,
                },
                'max_depth': {
                    'type': 'integer',
                    'description': 'Maximum depth for citation network analysis',
                    'default': 2,
                    'minimum': 1,
                    'maximum': 3,
                },
            },
            'required': ['article_identifier'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Extract citation network for an article."""
        try:
            article_identifier = arguments['article_identifier']
            include_outbound = arguments.get('include_outbound', True)
            include_inbound = arguments.get('include_inbound', True)
            # max_depth = arguments.get('max_depth', 2)  # TODO: implement depth

            # Find the target article
            search_results = await self.service_manager.rag.search_async(
                query=article_identifier, k=1
            )

            if not search_results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Article not found: {article_identifier}',
                        }
                    ],
                    isError=True,
                )

            article = search_results[0]
            title = article.get('title', 'Unknown')

            # Try to get citation information from citation service
            try:
                # This would use the citation service to get citation networks
                # For now, we'll provide a basic analysis based on available data

                response_text = f'**Citation Analysis for:** {title}\n\n'

                # Get basic citation info from metadata
                metadata = article.get('metadata', {})
                citation_count = metadata.get('citation_count', 0)
                references = metadata.get('references', [])

                response_text += '**Citation Statistics:**\n'
                response_text += f'  - Times cited: {citation_count}\n'
                response_text += f'  - References made: {len(references)}\n\n'

                if include_outbound and references:
                    response_text += '📤 **References (Outbound Citations):**\n'
                    for i, ref in enumerate(references[:10], 1):  # Show first 10
                        if isinstance(ref, dict):
                            ref_title = ref.get('title', 'Unknown Reference')
                        else:
                            ref_title = (
                                str(ref)[:100] + '...'
                                if len(str(ref)) > 100
                                else str(ref)
                            )
                        response_text += f'  {i}. {ref_title}\n'

                    if len(references) > 10:
                        response_text += (
                            f'  ... and {len(references) - 10} more references\n'
                        )
                    response_text += '\n'

                if include_inbound:
                    # Try to find articles that cite this one
                    citing_articles = await self.service_manager.rag.search_async(
                        query=f'"{title}"', k=5
                    )
                    citing_articles = [
                        a for a in citing_articles if a.get('title') != title
                    ]

                    if citing_articles:
                        response_text += '📥 **Cited By (Inbound Citations):**\n'
                        for i, citing_article in enumerate(citing_articles, 1):
                            citing_title = citing_article.get('title', 'Unknown')
                            response_text += f'  {i}. {citing_title}\n'
                        response_text += '\n'

                # Analyze citation patterns
                response_text += '**Citation Network Insights:**\n'

                # Calculate citation metrics
                if citation_count > 0:
                    if citation_count >= 100:
                        impact_level = 'High Impact'
                    elif citation_count >= 20:
                        impact_level = 'Moderate Impact'
                    else:
                        impact_level = 'Low Impact'

                    response_text += f'  - Impact Level: {impact_level}\n'

                if references:
                    response_text += (
                        f'  - References per section: ~{len(references) / 5:.1f}\n'
                    )
                    response_text += f'  - Reference diversity: {"High" if len(references) > 50 else "Moderate" if len(references) > 20 else "Low"}\n'

                response_text += '\n**Note:** Citation analysis is based on available metadata. For complete citation networks, ensure articles are processed with citation extraction enabled.'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text}]
                )

            except Exception as citation_error:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Citation analysis partially available.\n\n'
                            f'**Article:** {title}\n\n'
                            f'**Basic Info:**\n'
                            f'  - Found in knowledge base: \n'
                            f'  - Metadata available: {metadata if metadata else ""}\n\n'
                            f'**Note:** Full citation network analysis requires citation service integration.\n\n'
                            f'**Error:** {citation_error!s}',
                        }
                    ]
                )

        except Exception as e:
            return self.handle_error(e)

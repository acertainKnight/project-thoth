"""
Enhanced Research Question-Answering MCP Tools.

This module provides comprehensive research and Q&A capabilities for agents,
enabling deep analysis of the processed articles database with citation support,
network exploration, and multi-article comparison.
"""

from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult, normalize_authors


class AnswerResearchQuestionMCPTool(MCPTool):
    """Comprehensive research question answering with citations and context."""

    @property
    def name(self) -> str:
        return 'answer_research_question'

    @property
    def description(self) -> str:
        return (
            'Answer a research question using the processed articles database. '
            'Performs semantic search across all articles, synthesizes findings, '
            'and provides citations with relevance scores. Best for comprehensive '
            'questions requiring evidence from multiple sources.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'question': {
                    'type': 'string',
                    'description': 'Research question to answer (e.g., "What are the main approaches to multi-modal learning?")',
                },
                'max_sources': {
                    'type': 'integer',
                    'description': 'Maximum number of source articles to use',
                    'default': 10,
                    'minimum': 1,
                    'maximum': 50,
                },
                'min_relevance': {
                    'type': 'number',
                    'description': 'Minimum relevance score (0.0-1.0) for including sources',
                    'default': 0.4,
                    'minimum': 0.0,
                    'maximum': 1.0,
                },
                'include_citations': {
                    'type': 'boolean',
                    'description': 'Include full citation details in response',
                    'default': True,
                },
            },
            'required': ['question'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Answer research question with comprehensive search and synthesis."""
        try:
            question = arguments['question']
            max_sources = arguments.get('max_sources', 10)
            min_relevance = arguments.get('min_relevance', 0.4)
            include_citations = arguments.get('include_citations', True)

            # Perform semantic search
            rag_service = self.service_manager.rag
            if not rag_service:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'RAG service not available (requires embeddings extras)',
                        }
                    ],
                    isError=True,
                )

            search_results = await rag_service.search_async(
                query=question,
                k=max_sources,
            )

            # Filter by minimum relevance score
            if min_relevance > 0:
                search_results = [
                    r for r in search_results if r.get('score', 0) >= min_relevance
                ]

            if not search_results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'No relevant articles found for question: "{question}"',
                        }
                    ]
                )

            # Build comprehensive response
            response_parts = []
            response_parts.append(f'# Answer to: {question}\n')
            response_parts.append(
                f'Based on {len(search_results)} relevant source(s):\n'
            )

            # Group findings by relevance
            # (adjusted thresholds for typical embedding similarity scores)
            high_relevance = [r for r in search_results if r.get('score', 0) >= 0.6]
            medium_relevance = [
                r for r in search_results if 0.5 <= r.get('score', 0) < 0.6
            ]

            if high_relevance:
                response_parts.append('\n## Primary Findings (High Relevance)\n')
                for result in high_relevance:
                    title = result.get('metadata', {}).get('title', 'Unknown')
                    authors = normalize_authors(
                        result.get('metadata', {}).get('authors')
                    )
                    year = result.get('metadata', {}).get('year', 'N/A')
                    content = result.get('content', '')[:500]
                    score = result.get('score', 0)

                    response_parts.append(f'\n### {title}')
                    response_parts.append(
                        f'**Authors**: {", ".join(authors) if authors else "N/A"}'
                    )
                    response_parts.append(
                        f'**Year**: {year} | **Relevance**: {score:.2f}'
                    )
                    response_parts.append(f'\n{content}...\n')

            if medium_relevance:
                response_parts.append('\n## Supporting Findings (Medium Relevance)\n')
                for result in medium_relevance[:5]:  # Limit medium relevance to 5
                    title = result.get('metadata', {}).get('title', 'Unknown')
                    year = result.get('metadata', {}).get('year', 'N/A')
                    score = result.get('score', 0)
                    response_parts.append(
                        f'- {title} ({year}) - Relevance: {score:.2f}'
                    )

            # Add citations section if requested
            if include_citations:
                response_parts.append('\n## Citations\n')
                for i, result in enumerate(search_results, 1):
                    metadata = result.get('metadata', {})
                    title = metadata.get('title', 'Unknown')
                    authors = normalize_authors(metadata.get('authors'))
                    year = metadata.get('year', 'N/A')
                    doi = metadata.get('doi', '')

                    author_str = ', '.join(authors[:3]) if authors else 'Unknown'
                    if len(authors) > 3:
                        author_str += ' et al.'

                    response_parts.append(f'{i}. {author_str} ({year}). {title}.')
                    if doi:
                        response_parts.append(f'   DOI: {doi}')

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(response_parts)}]
            )

        except Exception as e:
            return self.handle_error(e)


class ExploreCitationNetworkMCPTool(MCPTool):
    """Explore citation relationships and paper networks."""

    @property
    def name(self) -> str:
        return 'explore_citation_network'

    @property
    def description(self) -> str:
        return (
            'Explore the citation network around a specific article. '
            'Shows papers that cite it (forward citations), papers it cites '
            '(backward citations), and co-citation patterns. Useful for '
            'understanding research lineage and finding related work.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_id': {
                    'type': 'string',
                    'description': 'Article ID or DOI to explore',
                },
                'depth': {
                    'type': 'integer',
                    'description': 'Citation network depth (1=direct citations, 2=citations of citations)',
                    'default': 1,
                    'minimum': 1,
                    'maximum': 3,
                },
                'include_metrics': {
                    'type': 'boolean',
                    'description': 'Include citation metrics (counts, h-index, etc.)',
                    'default': True,
                },
            },
            'required': ['article_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Explore citation network around an article."""
        try:
            article_id = arguments['article_id']
            depth = arguments.get('depth', 1)
            include_metrics = arguments.get('include_metrics', True)

            citation_service = self.service_manager.citation
            if not citation_service:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Citation service not available'}
                    ],
                    isError=True,
                )

            # Get citation network
            network = await citation_service.get_citation_network(
                article_id=article_id, depth=depth
            )

            if not network:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'No citation network found for article: {article_id}',
                        }
                    ]
                )

            # Build response
            response_parts = []
            response_parts.append(f'# Citation Network for Article {article_id}\n')

            # Forward citations (papers citing this one)
            forward = network.get('citing_papers', [])
            if forward:
                response_parts.append(
                    f'\n## Papers Citing This Work ({len(forward)} total)\n'
                )
                for paper in forward[:10]:  # Limit to 10
                    title = paper.get('title', 'Unknown')
                    year = paper.get('year', 'N/A')
                    authors = normalize_authors(paper.get('authors'))
                    author_str = ', '.join(authors[:2]) if authors else 'Unknown'
                    response_parts.append(f'- {author_str} ({year}). {title}')

            # Backward citations (papers this one cites)
            backward = network.get('cited_papers', [])
            if backward:
                response_parts.append(
                    f'\n## Papers Cited by This Work ({len(backward)} total)\n'
                )
                for paper in backward[:10]:
                    title = paper.get('title', 'Unknown')
                    year = paper.get('year', 'N/A')
                    authors = normalize_authors(paper.get('authors'))
                    author_str = ', '.join(authors[:2]) if authors else 'Unknown'
                    response_parts.append(f'- {author_str} ({year}). {title}')

            # Co-citations
            co_cited = network.get('co_cited_papers', [])
            if co_cited:
                response_parts.append(
                    f'\n## Frequently Co-Cited Papers ({len(co_cited)} found)\n'
                )
                response_parts.append(
                    'Papers that are often cited together with this work:\n'
                )
                for paper in co_cited[:5]:
                    title = paper.get('title', 'Unknown')
                    count = paper.get('co_citation_count', 0)
                    response_parts.append(f'- {title} (co-cited {count} times)')

            # Add metrics if requested
            if include_metrics:
                metrics = network.get('metrics', {})
                if metrics:
                    response_parts.append('\n## Citation Metrics\n')
                    response_parts.append(
                        f'- Total citations received: {metrics.get("citation_count", 0)}'
                    )
                    response_parts.append(
                        f'- Total references: {metrics.get("reference_count", 0)}'
                    )
                    response_parts.append(
                        f'- Citation velocity: {metrics.get("citation_velocity", 0):.2f} citations/year'
                    )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(response_parts)}]
            )

        except Exception as e:
            return self.handle_error(e)


class CompareArticlesMCPTool(MCPTool):
    """Compare multiple articles side-by-side."""

    @property
    def name(self) -> str:
        return 'compare_articles'

    @property
    def description(self) -> str:
        return (
            'Compare 2-5 articles side-by-side across multiple dimensions including '
            'methodology, findings, citations, and publication metrics. Highlights '
            'similarities, differences, and unique contributions of each paper.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_ids': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'List of article IDs or DOIs to compare (2-5 articles)',
                    'minItems': 2,
                    'maxItems': 5,
                },
                'compare_dimensions': {
                    'type': 'array',
                    'items': {
                        'type': 'string',
                        'enum': [
                            'methodology',
                            'findings',
                            'citations',
                            'metrics',
                            'approach',
                        ],
                    },
                    'description': 'Dimensions to compare (default: all)',
                    'default': ['methodology', 'findings', 'citations', 'metrics'],
                },
            },
            'required': ['article_ids'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Compare multiple articles."""
        try:
            article_ids = arguments['article_ids']
            dimensions = arguments.get(
                'compare_dimensions',
                ['methodology', 'findings', 'citations', 'metrics'],
            )

            if len(article_ids) < 2 or len(article_ids) > 5:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Must provide 2-5 articles to compare'}
                    ],
                    isError=True,
                )

            article_service = self.service_manager.article
            if not article_service:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Article service not available'}],
                    isError=True,
                )

            # Fetch all articles
            articles = []
            for article_id in article_ids:
                article = await article_service.get_article(article_id)
                if article:
                    articles.append(article)

            if len(articles) < 2:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Could only retrieve {len(articles)} articles for comparison',
                        }
                    ],
                    isError=True,
                )

            # Build comparison table
            response_parts = []
            response_parts.append(f'# Comparison of {len(articles)} Articles\n')

            # Basic info comparison
            response_parts.append('## Basic Information\n')
            response_parts.append('| Article | Authors | Year | Venue |')
            response_parts.append('|---------|---------|------|-------|')
            for article in articles:
                title = article.get('title', 'Unknown')[:50]
                author_list = normalize_authors(article.get('authors'))
                authors = ', '.join(author_list[:2])
                if len(author_list) > 2:
                    authors += ' et al.'
                year = article.get('year', 'N/A')
                venue = article.get('journal', article.get('venue', 'N/A'))[:30]
                response_parts.append(f'| {title}... | {authors} | {year} | {venue} |')

            # Citations comparison
            if 'citations' in dimensions:
                response_parts.append('\n## Citation Metrics\n')
                response_parts.append('| Article | Citations | References |')
                response_parts.append('|---------|-----------|------------|')
                for article in articles:
                    title = article.get('title', 'Unknown')[:50]
                    citations = article.get('citation_count', 0)
                    references = article.get('reference_count', 0)
                    response_parts.append(
                        f'| {title}... | {citations} | {references} |'
                    )

            # Key findings
            if 'findings' in dimensions:
                response_parts.append('\n## Key Findings\n')
                for i, article in enumerate(articles, 1):
                    title = article.get('title', 'Unknown')
                    abstract = article.get('abstract', 'No abstract available')[:300]
                    response_parts.append(f'\n### Article {i}: {title}')
                    response_parts.append(abstract + '...\n')

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(response_parts)}]
            )

        except Exception as e:
            return self.handle_error(e)


class ExtractArticleInsightsMCPTool(MCPTool):
    """
    Extract deep insights from a specific article.

    **DEPRECATED**: This tool is deprecated. Use `get_article_details` to
    retrieve full article content and metadata. This tool is no longer
    registered in the MCP tool registry.
    """

    @property
    def name(self) -> str:
        return 'extract_article_insights'

    @property
    def description(self) -> str:
        return (
            'Extract comprehensive insights from a single article including key '
            'contributions, methodology, limitations, future work, and connections '
            'to other research. Provides a detailed analytical summary.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_id': {
                    'type': 'string',
                    'description': 'Article ID or DOI',
                },
                'include_sections': {
                    'type': 'array',
                    'items': {
                        'type': 'string',
                        'enum': [
                            'contributions',
                            'methodology',
                            'limitations',
                            'future_work',
                            'connections',
                        ],
                    },
                    'description': 'Sections to include in insights (default: all)',
                    'default': [
                        'contributions',
                        'methodology',
                        'limitations',
                        'future_work',
                        'connections',
                    ],
                },
            },
            'required': ['article_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Extract detailed insights from article."""
        try:
            article_id = arguments['article_id']
            sections = arguments.get(
                'include_sections',
                [
                    'contributions',
                    'methodology',
                    'limitations',
                    'future_work',
                    'connections',
                ],
            )

            article_service = self.service_manager.article
            if not article_service:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Article service not available'}],
                    isError=True,
                )

            # Get article with full content
            article = await article_service.get_article_with_content(article_id)
            if not article:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': f'Article not found: {article_id}'}
                    ],
                    isError=True,
                )

            # Build insights response
            response_parts = []
            title = article.get('title', 'Unknown')
            response_parts.append(f'# Insights: {title}\n')

            # Basic metadata
            authors = ', '.join(normalize_authors(article.get('authors')))
            year = article.get('year', 'N/A')
            venue = article.get('journal', article.get('venue', 'N/A'))
            response_parts.append(f'**Authors**: {authors}')
            response_parts.append(f'**Published**: {year} in {venue}\n')

            # Key contributions
            if 'contributions' in sections:
                response_parts.append('## Key Contributions\n')
                contributions = article.get('contributions', [])
                if contributions:
                    for contrib in contributions:
                        response_parts.append(f'- {contrib}')
                else:
                    abstract = article.get('abstract', '')
                    if abstract:
                        response_parts.append(f'{abstract[:500]}...')

            # Methodology
            if 'methodology' in sections:
                response_parts.append('\n## Methodology\n')
                methodology = article.get('methodology', 'Not explicitly documented')
                response_parts.append(methodology)

            # Limitations
            if 'limitations' in sections:
                limitations = article.get('limitations', [])
                if limitations:
                    response_parts.append('\n## Limitations\n')
                    for limit in limitations:
                        response_parts.append(f'- {limit}')

            # Future work
            if 'future_work' in sections:
                future_work = article.get('future_work', [])
                if future_work:
                    response_parts.append('\n## Future Work Directions\n')
                    for work in future_work:
                        response_parts.append(f'- {work}')

            # Connections to other research
            if 'connections' in sections:
                response_parts.append('\n## Research Connections\n')
                citation_count = article.get('citation_count', 0)
                reference_count = article.get('reference_count', 0)
                response_parts.append(f'- Cites {reference_count} papers')
                response_parts.append(f'- Cited by {citation_count} papers')

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(response_parts)}]
            )

        except Exception as e:
            return self.handle_error(e)


class SearchByTopicMCPTool(MCPTool):
    """
    Search articles by research topic with semantic understanding.

    **DEPRECATED**: This tool is deprecated. Use `search_articles` which
    supports topic filtering via tags and queries. This tool is no longer
    registered in the MCP tool registry.
    """

    @property
    def name(self) -> str:
        return 'search_by_topic'

    @property
    def description(self) -> str:
        return (
            'Search for articles by research topic using semantic understanding. '
            'Better than keyword search - understands concepts and related terms. '
            'For example, searching "neural nets" will also find "deep learning" papers.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'topic': {
                    'type': 'string',
                    'description': 'Research topic to search (e.g., "attention mechanisms", "graph neural networks")',
                },
                'year_from': {
                    'type': 'integer',
                    'description': 'Filter papers from this year onwards',
                },
                'year_to': {
                    'type': 'integer',
                    'description': 'Filter papers up to this year',
                },
                'limit': {
                    'type': 'integer',
                    'description': 'Maximum number of results',
                    'default': 20,
                    'minimum': 1,
                    'maximum': 100,
                },
                'sort_by': {
                    'type': 'string',
                    'enum': ['relevance', 'date', 'citations'],
                    'description': 'Sort results by',
                    'default': 'relevance',
                },
            },
            'required': ['topic'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Search articles by topic."""
        try:
            topic = arguments['topic']
            year_from = arguments.get('year_from')
            year_to = arguments.get('year_to')
            limit = arguments.get('limit', 20)
            # Note: sort_by parameter is not currently used in the implementation
            arguments.get('sort_by', 'relevance')

            rag_service = self.service_manager.rag
            if not rag_service:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'RAG service not available (requires embeddings extras)',
                        }
                    ],
                    isError=True,
                )

            # Build filter
            search_filter = {}
            if year_from or year_to:
                search_filter['year_range'] = {}
                if year_from:
                    search_filter['year_range']['from'] = year_from
                if year_to:
                    search_filter['year_range']['to'] = year_to

            # Perform semantic search
            results = await rag_service.search_async(
                query=topic, k=limit, filter=search_filter if search_filter else None
            )

            if not results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'No articles found for topic: "{topic}"',
                        }
                    ]
                )

            # Build response
            response_parts = []
            response_parts.append(f'# Articles on: {topic}\n')
            response_parts.append(f'Found {len(results)} relevant article(s)\n')

            for i, result in enumerate(results, 1):
                metadata = result.get('metadata', {})
                title = metadata.get('title', 'Unknown')
                authors = normalize_authors(metadata.get('authors'))
                year = metadata.get('year', 'N/A')
                score = result.get('score', 0)

                author_str = ', '.join(authors[:3]) if authors else 'Unknown'
                if len(authors) > 3:
                    author_str += ' et al.'

                response_parts.append(f'\n## {i}. {title}')
                response_parts.append(
                    f'**Authors**: {author_str} | **Year**: {year} | **Relevance**: {score:.2f}'
                )

                # Add snippet
                content = result.get('content', '')
                if content:
                    snippet = content[:300]
                    response_parts.append(f'\n{snippet}...\n')

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(response_parts)}]
            )

        except Exception as e:
            return self.handle_error(e)


class GetArticleFullContentMCPTool(MCPTool):
    """
    Retrieve complete article content including full text.

    **DEPRECATED**: This tool is deprecated. Use `get_article_details` which
    provides the same functionality with better metadata support. This tool is
    no longer registered in the MCP tool registry.
    """

    @property
    def name(self) -> str:
        return 'get_article_full_content'

    @property
    def description(self) -> str:
        return (
            'Get the complete content of an article including full text, all sections, '
            'figures, tables, and references. Use when you need to read the entire paper '
            'in detail rather than just metadata or snippets.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_id': {
                    'type': 'string',
                    'description': 'Article ID or DOI',
                },
                'include_sections': {
                    'type': 'array',
                    'items': {
                        'type': 'string',
                        'enum': [
                            'abstract',
                            'introduction',
                            'methods',
                            'results',
                            'discussion',
                            'references',
                        ],
                    },
                    'description': 'Specific sections to include (default: all)',
                },
            },
            'required': ['article_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Get full article content."""
        try:
            article_id = arguments['article_id']
            sections = arguments.get('include_sections')

            article_service = self.service_manager.article
            if not article_service:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Article service not available'}],
                    isError=True,
                )

            # Get article with full content
            article = await article_service.get_article_with_content(article_id)
            if not article:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': f'Article not found: {article_id}'}
                    ],
                    isError=True,
                )

            # Build full content response
            response_parts = []

            # Title and metadata
            title = article.get('title', 'Unknown')
            response_parts.append(f'# {title}\n')

            authors = ', '.join(normalize_authors(article.get('authors')))
            year = article.get('year', 'N/A')
            venue = article.get('journal', article.get('venue', 'N/A'))
            doi = article.get('doi', '')

            response_parts.append(f'**Authors**: {authors}')
            response_parts.append(f'**Published**: {year} in {venue}')
            if doi:
                response_parts.append(f'**DOI**: {doi}')
            response_parts.append('')

            # Content sections
            content_dict = article.get('content', {})

            if not sections:
                sections = [
                    'abstract',
                    'introduction',
                    'methods',
                    'results',
                    'discussion',
                    'references',
                ]

            for section in sections:
                section_content = content_dict.get(section, article.get(section))
                if section_content:
                    section_title = section.replace('_', ' ').title()
                    response_parts.append(f'## {section_title}\n')
                    response_parts.append(f'{section_content}\n')

            # If no structured content, include full text
            if not any(content_dict.get(s) for s in sections):
                full_text = article.get('full_text', '')
                if full_text:
                    response_parts.append('## Full Text\n')
                    response_parts.append(full_text)

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(response_parts)}]
            )

        except Exception as e:
            return self.handle_error(e)


class FindArticlesByAuthorsMCPTool(MCPTool):
    """
    Find all articles by specific author(s).

    **DEPRECATED**: This tool is deprecated. Use `search_articles` with the
    `author` parameter for author-based filtering. This tool is no longer
    registered in the MCP tool registry.
    """

    @property
    def name(self) -> str:
        return 'find_articles_by_authors'

    @property
    def description(self) -> str:
        return (
            'Find all articles by one or more authors. Supports partial name matching '
            '(e.g., "Smith" will find "John Smith", "Jane Smith", etc.). Useful for '
            "tracking an author's publications or finding collaboration patterns."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'authors': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'List of author names to search (can be partial)',
                    'minItems': 1,
                },
                'match_all': {
                    'type': 'boolean',
                    'description': 'If true, find papers co-authored by ALL listed authors',
                    'default': False,
                },
                'year_from': {
                    'type': 'integer',
                    'description': 'Filter papers from this year onwards',
                },
                'year_to': {
                    'type': 'integer',
                    'description': 'Filter papers up to this year',
                },
                'limit': {
                    'type': 'integer',
                    'description': 'Maximum number of results',
                    'default': 50,
                    'minimum': 1,
                    'maximum': 200,
                },
            },
            'required': ['authors'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Find articles by author(s)."""
        try:
            authors = arguments['authors']
            match_all = arguments.get('match_all', False)
            year_from = arguments.get('year_from')
            year_to = arguments.get('year_to')
            limit = arguments.get('limit', 50)

            article_service = self.service_manager.article
            if not article_service:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'Article service not available'}],
                    isError=True,
                )

            # Search for articles by author
            articles = await article_service.find_by_authors(
                authors=authors,
                match_all=match_all,
                year_from=year_from,
                year_to=year_to,
                limit=limit,
            )

            if not articles:
                author_str = (
                    ' AND '.join(authors) if match_all else ' OR '.join(authors)
                )
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'No articles found for author(s): {author_str}',
                        }
                    ]
                )

            # Build response
            response_parts = []
            author_str = ' & '.join(authors) if match_all else ' / '.join(authors)
            response_parts.append(f'# Articles by: {author_str}\n')
            response_parts.append(f'Found {len(articles)} article(s)\n')

            # Group by year
            by_year = {}
            for article in articles:
                year = article.get('year', 'Unknown')
                if year not in by_year:
                    by_year[year] = []
                by_year[year].append(article)

            # Sort years descending
            for year in sorted(by_year.keys(), reverse=True):
                response_parts.append(f'\n## {year}\n')
                for article in by_year[year]:
                    title = article.get('title', 'Unknown')
                    all_authors = ', '.join(normalize_authors(article.get('authors')))
                    venue = article.get('journal', article.get('venue', 'N/A'))
                    citations = article.get('citation_count', 0)

                    response_parts.append(f'### {title}')
                    response_parts.append(f'**Authors**: {all_authors}')
                    response_parts.append(
                        f'**Venue**: {venue} | **Citations**: {citations}\n'
                    )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(response_parts)}]
            )

        except Exception as e:
            return self.handle_error(e)


class GetCitationContextMCPTool(MCPTool):
    """Get context around citations between papers."""

    @property
    def name(self) -> str:
        return 'get_citation_context'

    @property
    def description(self) -> str:
        return (
            'Extract the context in which one paper cites another. Shows the actual '
            'sentences and paragraphs where the citation appears, helping understand '
            'HOW and WHY a paper was cited.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'citing_paper_id': {
                    'type': 'string',
                    'description': 'ID of the paper that contains the citation',
                },
                'cited_paper_id': {
                    'type': 'string',
                    'description': 'ID of the paper being cited',
                },
                'context_window': {
                    'type': 'integer',
                    'description': 'Number of sentences before/after citation to include',
                    'default': 2,
                    'minimum': 1,
                    'maximum': 5,
                },
            },
            'required': ['citing_paper_id', 'cited_paper_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Get citation context."""
        try:
            citing_id = arguments['citing_paper_id']
            cited_id = arguments['cited_paper_id']
            context_window = arguments.get('context_window', 2)

            citation_service = self.service_manager.citation
            if not citation_service:
                return MCPToolCallResult(
                    content=[
                        {'type': 'text', 'text': 'Citation service not available'}
                    ],
                    isError=True,
                )

            # Get citation context
            contexts = await citation_service.get_citation_context(
                citing_paper_id=citing_id,
                cited_paper_id=cited_id,
                context_window=context_window,
            )

            if not contexts:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'No citation context found between papers: {citing_id} → {cited_id}',
                        }
                    ]
                )

            # Build response
            response_parts = []
            response_parts.append('# Citation Context\n')
            response_parts.append(f'**From**: {citing_id}')
            response_parts.append(f'**To**: {cited_id}\n')

            for i, context in enumerate(contexts, 1):
                section = context.get('section', 'Unknown section')
                text = context.get('context_text', '')

                response_parts.append(f'\n## Occurrence {i} ({section})\n')
                response_parts.append(f'{text}\n')

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(response_parts)}]
            )

        except Exception as e:
            return self.handle_error(e)


class AgenticResearchQuestionMCPTool(MCPTool):
    """
    Advanced research question answering with agentic retrieval.

    Uses adaptive, self-correcting retrieval with query classification,
    expansion, document grading, query rewriting, and hallucination detection
    for higher accuracy on complex questions.
    """

    @property
    def name(self) -> str:
        return 'agentic_research_question'

    @property
    def description(self) -> str:
        return (
            'Answer complex research questions using agentic retrieval. '
            'Automatically classifies query type, expands search terms, '
            'grades document relevance, rewrites queries on low confidence, '
            'and verifies answer groundedness. Best for complex multi-hop '
            'questions requiring deep analysis across multiple sources.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'question': {
                    'type': 'string',
                    'description': 'Complex research question to answer',
                },
                'max_sources': {
                    'type': 'integer',
                    'description': 'Maximum number of source articles to use',
                    'default': 5,
                    'minimum': 1,
                    'maximum': 20,
                },
                'max_retries': {
                    'type': 'integer',
                    'description': 'Maximum number of retrieval retries on low confidence',
                    'default': 2,
                    'minimum': 0,
                    'maximum': 5,
                },
            },
            'required': ['question'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Answer research question using agentic retrieval."""
        try:
            question = arguments['question']
            max_sources = arguments.get('max_sources', 5)
            max_retries = arguments.get('max_retries', 2)

            # Get RAG service
            rag_service = self.service_manager.rag
            if not rag_service:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'RAG service not available (requires embeddings extras)',
                        }
                    ],
                    isError=True,
                )

            # Check if agentic retrieval is enabled
            if not rag_service.rag_manager.agentic_orchestrator:
                # Fall back to standard answer_research_question
                return await AnswerResearchQuestionMCPTool(
                    self.service_manager
                ).execute(
                    {
                        'question': question,
                        'max_sources': max_sources,
                        'include_citations': True,
                    }
                )

            # Create progress callback that broadcasts to WebSocket
            import uuid

            operation_id = f'agentic_rag_{uuid.uuid4().hex[:8]}'

            def progress_callback(_step: str, message: str, progress: float) -> None:
                """Broadcast retrieval step progress to WebSocket clients."""
                try:
                    from thoth.server.routers.websocket import update_operation_progress

                    update_operation_progress(
                        operation_id=operation_id,
                        status='in_progress',
                        progress=progress,
                        message=message,
                    )
                except Exception as e:
                    # Don't fail the entire operation if progress reporting fails
                    import logging

                    logging.getLogger(__name__).warning(
                        f'Failed to update progress: {e}'
                    )

            # Use agentic retrieval with progress callback
            result = await rag_service.agentic_ask_question_async(
                question=question,
                k=max_sources,
                max_retries=max_retries,
                progress_callback=progress_callback,
            )

            # Mark operation complete
            from thoth.server.routers.websocket import update_operation_progress

            update_operation_progress(
                operation_id=operation_id,
                status='completed',
                progress=100.0,
                message='Answer generated',
            )

            # Build comprehensive response
            response_parts = []
            response_parts.append(f'# Answer to: {question}\n')
            response_parts.append(f'**Confidence**: {result["confidence"]:.2f}')
            response_parts.append(
                f'**Query Type**: {result["query_type"].replace("_", " ").title()}'
            )
            response_parts.append(f'**Retrieval Rounds**: {result["retry_count"] + 1}')
            response_parts.append(
                f'**Grounded**: {"Yes" if result["is_grounded"] else "No (potential hallucination detected)"}\n'
            )

            # Add answer
            response_parts.append('## Answer\n')
            response_parts.append(result['answer'])

            # Add sources
            sources = result.get('sources', [])
            if sources:
                response_parts.append('\n## Sources\n')
                for i, source in enumerate(sources, 1):
                    title = source.get('title', 'Unknown')
                    authors = source.get('authors', [])
                    relevance = source.get('relevance_score', 0.0)

                    author_str = ', '.join(authors[:3]) if authors else 'Unknown'
                    if len(authors) > 3:
                        author_str += ' et al.'

                    response_parts.append(
                        f'{i}. **{title}** (Relevance: {relevance:.2f})'
                    )
                    response_parts.append(f'   {author_str}')

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(response_parts)}]
            )

        except Exception as e:
            return self.handle_error(e)

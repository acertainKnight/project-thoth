"""Analysis tools for article evaluation and research insights."""

from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult


class EvaluateArticleMCPTool(MCPTool):
    """MCP tool for evaluating an article against a research query."""

    @property
    def name(self) -> str:
        return 'evaluate_article'

    @property
    def description(self) -> str:
        return 'Evaluate how well an article matches a research query, providing relevance score and detailed reasoning'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_identifier': {
                    'type': 'string',
                    'description': 'Article title, DOI, or arXiv ID to evaluate',
                },
                'query_name': {
                    'type': 'string',
                    'description': 'Name of the research query to evaluate against',
                },
            },
            'required': ['article_identifier', 'query_name'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Evaluate an article against a query."""
        try:
            article_identifier = arguments['article_identifier']
            query_name = arguments['query_name']

            # Get the query
            query = self.service_manager.query.get_query(query_name)
            if not query:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Query '{query_name}' not found. Use 'list_queries' to see available queries.",
                        }
                    ],
                    isError=True,
                )

            # Find the article
            search_results = await self.service_manager.rag.search_async(
                query=article_identifier, k=1
            )

            if not search_results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Could not find article: '{article_identifier}'",
                        }
                    ],
                    isError=True,
                )

            article = search_results[0]
            title = article.get('title', 'Unknown')
            content = article.get('content', '')

            # Create a simplified article object for evaluation
            try:
                from thoth.utilities.schemas import AnalysisResponse

                analysis_response = AnalysisResponse(
                    title=title,
                    abstract=content[:500] if content else 'No abstract available',
                )

                # Evaluate against the query
                evaluation = self.service_manager.article.evaluate_against_query(
                    analysis_response, query
                )

                if not evaluation:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f"Failed to evaluate article against query '{query_name}'",
                            }
                        ],
                        isError=True,
                    )

                # Format response
                response_text = '**Article Evaluation Results**\n\n'
                response_text += f'**Article:** {title}\n'
                response_text += f'**Query:** {query_name}\n\n'
                response_text += (
                    f'**Relevance Score:** {evaluation.relevance_score}/10\n'
                )
                response_text += (
                    f'**Decision:** {evaluation.recommendation.value.upper()}\n\n'
                )
                response_text += f'**Reasoning:**\n{evaluation.reasoning}\n\n'

                if evaluation.matching_keywords:
                    response_text += f'**Matching Keywords:** {", ".join(evaluation.matching_keywords)}\n'

                if evaluation.suggested_queries:
                    response_text += f'**Also relevant to:** {", ".join(evaluation.suggested_queries)}\n'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text.strip()}]
                )

            except ImportError:
                # Fallback if AnalysisResponse is not available
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'**Basic Article Evaluation**\n\n'
                            f'**Article:** {title}\n'
                            f'**Query:** {query_name}\n\n'
                            f'**Article Found:** Yes\n'
                            f'**Query Exists:** Yes\n\n'
                            f'**Note:** Full evaluation requires article service integration. '
                            f"The article '{title}' has been located in the knowledge base and can be evaluated against your research query.",
                        }
                    ]
                )

        except Exception as e:
            return self.handle_error(e)


class AnalyzeTopicMCPTool(MCPTool):
    """
    MCP tool for analyzing a research topic across the knowledge base.
    
    **DEPRECATED**: This tool is deprecated. Use `answer_research_question` 
    instead, which provides comprehensive synthesis with citations. This tool 
    is no longer registered in the MCP tool registry.
    """

    @property
    def name(self) -> str:
        return 'analyze_topic'

    @property
    def description(self) -> str:
        return 'Analyze a research topic across your entire knowledge base, providing overview, key papers, trends, and gaps'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'topic': {'type': 'string', 'description': 'Research topic to analyze'},
                'depth': {
                    'type': 'string',
                    'enum': ['quick', 'medium', 'deep'],
                    'description': 'Analysis depth level',
                    'default': 'medium',
                },
                'max_papers': {
                    'type': 'integer',
                    'description': 'Maximum number of papers to analyze',
                    'default': 10,
                    'minimum': 3,
                    'maximum': 50,
                },
            },
            'required': ['topic'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Analyze a research topic."""
        try:
            topic = arguments['topic']
            depth = arguments.get('depth', 'medium')
            max_papers = arguments.get('max_papers', 10)

            # Determine analysis parameters based on depth
            k_values = {
                'quick': 3,
                'medium': max_papers,
                'deep': min(max_papers * 2, 50),
            }
            k = k_values.get(depth, max_papers)

            # Search for papers on this topic
            search_results = await self.service_manager.rag.search_async(query=topic, k=k)

            if not search_results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"No papers found on the topic: '{topic}'",
                        }
                    ],
                    isError=True,
                )

            # Prepare analysis question based on depth
            questions = {
                'quick': f'Provide a brief overview of research on {topic}',
                'medium': f'What are the key findings and methodologies in {topic} research?',
                'deep': f'Provide a comprehensive analysis of {topic} research including key findings, methodologies, open challenges, and future directions',
            }

            question = questions.get(depth, questions['medium'])

            # Get analysis from RAG system
            analysis_result = self.service_manager.rag.ask_question(
                question=question, k=k
            )

            # Format comprehensive response
            response_text = f'**Topic Analysis: {topic}**\n\n'
            response_text += f'**Analysis Depth:** {depth.title()}\n'
            response_text += f'**Papers Analyzed:** {len(search_results)}\n\n'

            # Add top relevant papers
            response_text += '**Most Relevant Papers:**\n'
            for i, result in enumerate(search_results[:5], 1):
                title = result.get('title', 'Untitled')
                score = result.get('score', 0)
                response_text += f'{i}. {title} (relevance: {score:.3f})\n'

            if len(search_results) > 5:
                response_text += f'... and {len(search_results) - 5} more papers\n'

            response_text += f'\n**AI Analysis:**\n{analysis_result.get("answer", "Analysis not available")}\n\n'

            # Add paper metadata insights
            authors = set()
            journals = set()
            years = []

            for result in search_results:
                metadata = result.get('metadata', {})

                # Collect authors
                paper_authors = metadata.get('authors', [])
                if isinstance(paper_authors, list):
                    authors.update(paper_authors[:3])  # Top 3 authors per paper
                elif paper_authors:
                    authors.add(str(paper_authors))

                # Collect journals
                journal = metadata.get('journal')
                if journal:
                    journals.add(journal)

                # Collect years
                pub_date = metadata.get('publication_date', '')
                if pub_date:
                    try:
                        year = int(pub_date.split('-')[0])
                        years.append(year)
                    except (ValueError, IndexError):
                        pass

            # Add insights
            if len(authors) > 3:
                top_authors = list(authors)[:5]
                response_text += f'**Key Researchers:** {", ".join(top_authors)}'
                if len(authors) > 5:
                    response_text += f' (+{len(authors) - 5} more)'
                response_text += '\n'

            if len(journals) > 2:
                top_journals = list(journals)[:3]
                response_text += f'**Main Venues:** {", ".join(top_journals)}'
                if len(journals) > 3:
                    response_text += f' (+{len(journals) - 3} more)'
                response_text += '\n'

            if years:
                year_range = (
                    f'{min(years)}-{max(years)}'
                    if len(set(years)) > 1
                    else str(years[0])
                )
                response_text += f'**Time Period:** {year_range}\n'

            # Add recommendations based on depth
            if depth == 'deep' and len(search_results) >= 10:
                response_text += '\n**Research Opportunities:**\n'
                response_text += f'- {len(search_results)} papers provide substantial foundation for further research\n'
                response_text += '- Consider exploring connections between different methodological approaches\n'
                response_text += (
                    f'- Gap analysis may reveal underexplored aspects of {topic}\n'
                )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class FindRelatedPapersMCPTool(MCPTool):
    """MCP tool for finding papers related to a specific paper."""

    @property
    def name(self) -> str:
        return 'find_related_papers'

    @property
    def description(self) -> str:
        return 'Find papers in your collection that are related to a specific paper using semantic similarity'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'paper_identifier': {
                    'type': 'string',
                    'description': 'Title, DOI, or arXiv ID of the paper to find related work for',
                },
                'max_results': {
                    'type': 'integer',
                    'description': 'Maximum number of related papers to return',
                    'default': 5,
                    'minimum': 1,
                    'maximum': 20,
                },
                'explain_connections': {
                    'type': 'boolean',
                    'description': 'Whether to explain connections between papers using AI analysis',
                    'default': False,
                },
                'similarity_threshold': {
                    'type': 'number',
                    'description': 'Minimum similarity score (0.0-1.0) for related papers',
                    'default': 0.1,
                    'minimum': 0.0,
                    'maximum': 1.0,
                },
            },
            'required': ['paper_identifier'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Find related papers."""
        try:
            paper_identifier = arguments['paper_identifier']
            max_results = arguments.get('max_results', 5)
            explain_connections = arguments.get('explain_connections', False)
            similarity_threshold = arguments.get('similarity_threshold', 0.1)

            # Find the target paper
            target_results = await self.service_manager.rag.search_async(
                query=paper_identifier, k=1
            )

            if not target_results:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Could not find paper: '{paper_identifier}'",
                        }
                    ],
                    isError=True,
                )

            target_paper = target_results[0]
            target_title = target_paper.get('title', 'Unknown')
            target_content = target_paper.get('content', '')

            # Create search query from title and content
            search_query = f'{target_title} {target_content[:500]}'

            # Search for related papers (get extra to filter out the target)
            related_results = await self.service_manager.rag.search_async(
                query=search_query,
                k=max_results + 5,  # Get extra results
            )

            # Filter out the target paper and apply similarity threshold
            related_papers = []
            for result in related_results:
                if (
                    result.get('title') != target_title
                    and result.get('score', 0) >= similarity_threshold
                    and len(related_papers) < max_results
                ):
                    related_papers.append(result)

            if not related_papers:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"No related papers found for: '{target_title}'\n\n"
                            f'Try lowering the similarity threshold or expanding your search terms.',
                        }
                    ]
                )

            # Start building response
            response_text = f'**Related Papers for:** {target_title}\n\n'
            response_text += f'**Found {len(related_papers)} related papers**\n\n'

            # Analyze connections if requested
            if explain_connections and len(related_papers) >= 2:
                try:
                    # Get top 3 related papers for connection analysis
                    top_related = related_papers[:3]
                    related_titles = [p['title'] for p in top_related]

                    connections_question = (
                        f"How do these papers relate to '{target_title}': "
                        f'{", ".join(related_titles)}? What are the key connections and themes?'
                    )

                    connections_result = self.service_manager.rag.ask_question(
                        question=connections_question, k=6
                    )

                    response_text += '**Key Relationships:**\n'
                    response_text += f'{connections_result.get("answer", "Connection analysis not available")}\n\n'

                except Exception:
                    response_text += (
                        '**Connection analysis temporarily unavailable**\n\n'
                    )

            # List related papers
            response_text += '**Related Papers:**\n\n'
            for i, paper in enumerate(related_papers, 1):
                title = paper.get('title', 'Untitled')
                score = paper.get('score', 0)
                metadata = paper.get('metadata', {})
                content = paper.get('content', '')

                response_text += f'**{i}. {title}**\n'
                response_text += f'   Similarity: {score:.3f}\n'

                # Add metadata if available
                authors = metadata.get('authors', [])
                if authors:
                    if isinstance(authors, list):
                        authors_str = ', '.join(authors[:2])
                        if len(authors) > 2:
                            authors_str += f' (+{len(authors) - 2} more)'
                    else:
                        authors_str = str(authors)
                    response_text += f'   Authors: {authors_str}\n'

                if metadata.get('publication_date'):
                    response_text += f'   Date: {metadata["publication_date"]}\n'

                # Add content preview
                if content:
                    preview = content[:150].replace('\n', ' ')
                    response_text += f'   Preview: {preview}...\n'

                response_text += '\n'

            # Add research suggestions
            if len(related_papers) >= 3:
                response_text += '**Research Suggestions:**\n'
                response_text += '- Compare methodologies across these related papers\n'
                response_text += '- Look for citation patterns and shared references\n'
                response_text += '- Consider how these papers build upon each other\n'

                if explain_connections:
                    response_text += '- Use the connection analysis above to identify research trends\n'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class GenerateResearchSummaryMCPTool(MCPTool):
    """
    MCP tool for generating comprehensive research summaries.
    
    **DEPRECATED**: This tool is deprecated. Use `answer_research_question` 
    instead, which provides better synthesis with citations. This tool is no 
    longer registered in the MCP tool registry.
    """

    @property
    def name(self) -> str:
        return 'generate_research_summary'

    @property
    def description(self) -> str:
        return 'Generate comprehensive research summaries and insights from your knowledge base on specific topics or queries'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'topic_or_query': {
                    'type': 'string',
                    'description': 'Research topic or specific question to generate summary for',
                },
                'summary_type': {
                    'type': 'string',
                    'enum': [
                        'overview',
                        'methodology',
                        'findings',
                        'gaps',
                        'comprehensive',
                    ],
                    'description': 'Type of research summary to generate',
                    'default': 'comprehensive',
                },
                'max_papers': {
                    'type': 'integer',
                    'description': 'Maximum number of papers to include in analysis',
                    'default': 15,
                    'minimum': 5,
                    'maximum': 50,
                },
                'include_citations': {
                    'type': 'boolean',
                    'description': 'Include paper citations in the summary',
                    'default': True,
                },
            },
            'required': ['topic_or_query'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Generate research summary."""
        try:
            topic_or_query = arguments['topic_or_query']
            summary_type = arguments.get('summary_type', 'comprehensive')
            max_papers = arguments.get('max_papers', 15)
            include_citations = arguments.get('include_citations', True)

            # Search for relevant papers
            search_results = await self.service_manager.rag.search_async(
                query=topic_or_query, k=max_papers
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

            # Generate different types of summaries based on type
            if summary_type == 'overview':
                question = f"Provide a comprehensive overview of research on '{topic_or_query}', including key themes and major contributions."
            elif summary_type == 'methodology':
                question = f"What are the main research methodologies and approaches used in '{topic_or_query}' research? Compare and contrast different approaches."
            elif summary_type == 'findings':
                question = f"What are the key findings and conclusions from research on '{topic_or_query}'? Highlight the most important discoveries."
            elif summary_type == 'gaps':
                question = f"What are the research gaps and future opportunities in '{topic_or_query}' research? What questions remain unanswered?"
            else:  # comprehensive
                question = f"Provide a comprehensive research summary on '{topic_or_query}' including overview, methodologies, key findings, and research gaps."

            # Get AI-generated summary
            summary_result = self.service_manager.rag.ask_question(
                question=question, k=max_papers
            )

            # Analyze paper metadata for additional insights
            publication_years = []
            authors = set()
            journals = set()
            citation_counts = []

            for result in search_results:
                metadata = result.get('metadata', {})

                # Publication years
                pub_date = metadata.get('publication_date', '')
                if pub_date:
                    try:
                        year = int(pub_date.split('-')[0])
                        publication_years.append(year)
                    except (ValueError, IndexError):
                        pass

                # Authors
                paper_authors = metadata.get('authors', [])
                if isinstance(paper_authors, list):
                    authors.update(paper_authors)
                elif paper_authors:
                    authors.add(str(paper_authors))

                # Journals
                journal = metadata.get('journal')
                if journal:
                    journals.add(journal)

                # Citation counts
                citations = metadata.get('citation_count', 0)
                if citations:
                    citation_counts.append(citations)

            # Build comprehensive summary
            response_text = f'**Research Summary: {topic_or_query}**\n\n'
            response_text += '**Analysis Overview:**\n'
            response_text += f'- Papers analyzed: {len(search_results)}\n'
            response_text += f'- Summary type: {summary_type.title()}\n'

            if publication_years:
                year_range = (
                    f'{min(publication_years)}-{max(publication_years)}'
                    if len(set(publication_years)) > 1
                    else str(publication_years[0])
                )
                response_text += f'- Publication period: {year_range}\n'

            if citation_counts:
                avg_citations = sum(citation_counts) / len(citation_counts)
                response_text += f'- Average citations: {avg_citations:.1f}\n'

            response_text += '\n'

            # Add AI-generated summary
            response_text += f'**AI-Generated Summary:**\n{summary_result.get("answer", "Summary not available")}\n\n'

            # Add key statistics
            if len(authors) > 5:
                response_text += '**Key Contributors:**\n'
                top_authors = sorted(authors)[:8]  # Show top 8 authors alphabetically
                response_text += f'- {", ".join(top_authors)}'
                if len(authors) > 8:
                    response_text += f' (+{len(authors) - 8} more researchers)'
                response_text += '\n\n'

            if len(journals) > 3:
                response_text += '**Primary Publication Venues:**\n'
                top_journals = sorted(journals)[:5]
                response_text += f'- {", ".join(top_journals)}'
                if len(journals) > 5:
                    response_text += f' (+{len(journals) - 5} more venues)'
                response_text += '\n\n'

            # Add paper citations if requested
            if include_citations:
                response_text += '**Key Papers Referenced:**\n\n'
                for i, result in enumerate(search_results[:10], 1):  # Top 10 papers
                    title = result.get('title', 'Untitled')
                    metadata = result.get('metadata', {})
                    score = result.get('score', 0)

                    response_text += f'{i}. **{title}**\n'

                    # Add authors
                    authors_list = metadata.get('authors', [])
                    if authors_list:
                        if isinstance(authors_list, list):
                            authors_str = ', '.join(authors_list[:3])
                            if len(authors_list) > 3:
                                authors_str += ' et al.'
                        else:
                            authors_str = str(authors_list)
                        response_text += f'   Authors: {authors_str}\n'

                    # Add publication info
                    if metadata.get('journal'):
                        response_text += f'   Journal: {metadata["journal"]}\n'
                    if metadata.get('publication_date'):
                        response_text += (
                            f'   Year: {metadata["publication_date"].split("-")[0]}\n'
                        )

                    response_text += f'   Relevance: {score:.3f}\n\n'

                if len(search_results) > 10:
                    response_text += (
                        f'... and {len(search_results) - 10} more papers\n\n'
                    )

            # Add research recommendations
            response_text += '**Research Recommendations:**\n'
            if summary_type in ['gaps', 'comprehensive']:
                response_text += (
                    '- Review the identified research gaps for potential future work\n'
                )
            if summary_type in ['methodology', 'comprehensive']:
                response_text += (
                    '- Consider combining methodologies from different papers\n'
                )
            if len(search_results) >= 10:
                response_text += (
                    '- Sufficient literature base for comprehensive literature review\n'
                )
            response_text += (
                '- Use citation analysis to identify seminal papers in the field\n'
            )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)

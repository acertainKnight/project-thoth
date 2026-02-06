"""
MCP tool for reading full article content from the knowledge base.

This module provides tools to load complete article content for deep reading
and iterative learning workflows.
"""

from pathlib import Path
from typing import Any

from loguru import logger

from ..base_tools import MCPTool, MCPToolCallResult


class ReadFullArticleMCPTool(MCPTool):
    """
    MCP tool for reading the full content of an article from the knowledge base.

    Use this tool when you need to read an entire article deeply, not just
    a preview. This enables iterative learning workflows where you can:
    1. Read full articles to understand a topic
    2. Identify knowledge gaps
    3. Read additional articles to fill those gaps
    4. Synthesize understanding across multiple sources
    """

    @property
    def name(self) -> str:
        return 'read_full_article'

    @property
    def description(self) -> str:
        return (
            'Read the full content of an article from the knowledge base. '
            'Use this to deeply read papers for learning and synthesis. '
            'Returns complete markdown content, not just a preview.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_identifier': {
                    'type': 'string',
                    'description': 'Article title, DOI, or arXiv ID to look up',
                },
                'max_length': {
                    'type': 'integer',
                    'description': 'Maximum characters to return (default 50000)',
                    'default': 50000,
                    'minimum': 1000,
                    'maximum': 100000,
                },
            },
            'required': ['article_identifier'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Read the full content of an article."""
        try:
            identifier = arguments['article_identifier']
            max_length = arguments.get('max_length', 50000)

            # Import PaperRepository for database access
            from thoth.repositories.paper_repository import PaperRepository

            postgres_service = self.service_manager.postgres
            paper_repo = PaperRepository(postgres_service)

            # Try to find the paper by different identifiers
            paper = None

            # Check if identifier looks like a DOI
            if identifier.startswith('10.') or 'doi.org' in identifier:
                doi = identifier.replace('https://doi.org/', '').replace(
                    'http://doi.org/', ''
                )
                paper = await paper_repo.get_by_doi(doi)
                if paper:
                    logger.info(f'Found paper by DOI: {doi}')

            # Check if identifier looks like an arXiv ID
            if not paper and (
                'arxiv' in identifier.lower()
                or (any(c.isdigit() for c in identifier) and '.' in identifier)
            ):
                arxiv_id = (
                    identifier.replace('arXiv:', '').replace('arxiv:', '').strip()
                )
                paper = await paper_repo.get_by_arxiv_id(arxiv_id)
                if paper:
                    logger.info(f'Found paper by arXiv ID: {arxiv_id}')

            # Try title search if not found by ID
            if not paper:
                title_results = await paper_repo.search_by_title(identifier, limit=1)
                if title_results:
                    paper = title_results[0]
                    logger.info(f'Found paper by title search: {identifier}')

            if not paper:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'Article not found: {identifier}\n\n'
                            'Try using the exact title, DOI, or arXiv ID.',
                        }
                    ],
                    isError=True,
                )

            # Get article content - try multiple sources
            article_content = None
            source_type = None

            # 1. Try markdown_content from database (processed_papers)
            if paper.get('markdown_content'):
                article_content = paper['markdown_content']
                source_type = 'database'
                logger.info('Using markdown_content from database')

            # 2. Try reading from note_path file
            if not article_content and paper.get('note_path'):
                note_path = Path(paper['note_path'])
                if note_path.exists():
                    try:
                        article_content = note_path.read_text(encoding='utf-8')
                        source_type = 'note_file'
                        logger.info(f'Read content from note_path: {note_path}')
                    except Exception as e:
                        logger.warning(f'Failed to read note_path: {e}')

            # 3. Try reading from markdown_path file
            if not article_content and paper.get('markdown_path'):
                markdown_path = Path(paper['markdown_path'])
                if markdown_path.exists():
                    try:
                        article_content = markdown_path.read_text(encoding='utf-8')
                        source_type = 'markdown_file'
                        logger.info(f'Read content from markdown_path: {markdown_path}')
                    except Exception as e:
                        logger.warning(f'Failed to read markdown_path: {e}')

            if not article_content:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'**Article found but content not available**\n\n'
                            f'**Title:** {paper.get("title", "Unknown")}\n'
                            f'**DOI:** {paper.get("doi", "N/A")}\n'
                            f'**arXiv ID:** {paper.get("arxiv_id", "N/A")}\n\n'
                            'The article metadata exists but the full content has not '
                            'been processed yet. Try downloading and processing the PDF first.',
                        }
                    ],
                    isError=True,
                )

            # Truncate if needed
            truncated = False
            if len(article_content) > max_length:
                article_content = article_content[:max_length]
                truncated = True

            # Build response with metadata header
            title = paper.get('title', 'Unknown')
            authors = paper.get('authors', [])
            if isinstance(authors, list):
                authors_str = ', '.join(authors[:5])
                if len(authors) > 5:
                    authors_str += f' (+{len(authors) - 5} more)'
            else:
                authors_str = str(authors) if authors else 'Unknown'

            response_text = f'# {title}\n\n'
            response_text += f'**Authors:** {authors_str}\n'

            if paper.get('doi'):
                response_text += f'**DOI:** {paper["doi"]}\n'
            if paper.get('arxiv_id'):
                response_text += f'**arXiv ID:** {paper["arxiv_id"]}\n'
            if paper.get('publication_date'):
                response_text += f'**Date:** {paper["publication_date"]}\n'
            if paper.get('journal'):
                response_text += f'**Journal:** {paper["journal"]}\n'

            response_text += f'\n---\n\n{article_content}'

            if truncated:
                response_text += (
                    f'\n\n---\n*[Content truncated at {max_length} characters. '
                    f'Use max_length parameter to read more.]*'
                )

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text}]
            )

        except Exception as e:
            logger.error(f'Error reading full article: {e}')
            return self.handle_error(e)

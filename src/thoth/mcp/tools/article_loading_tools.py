"""
MCP tool for reading full article content from the knowledge base.

This module provides tools to load complete article content for deep reading
and iterative learning workflows.

ARTICLE MEMORY MANAGEMENT:
- Maximum 3 articles can be loaded per agent at a time
- When read_full_article is called:
  1. Article content is loaded and tracked
  2. On first load (0 -> 1): unload_article tool is attached
  3. On third load (2 -> 3): read_full_article tool is detached
- When unload_article is called:
  1. Article is removed from memory
  2. On unload from 3 to 2: read_full_article tool is re-attached
  3. On unload from 1 to 0: unload_article tool is detached
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from ..base_tools import MCPTool, MCPToolCallResult

# Global registry to track which articles are loaded per agent
# Key: agent_id, Value: list of dicts with article metadata
_AGENT_LOADED_ARTICLES: dict[str, list[dict[str, Any]]] = {}


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
            'Returns complete markdown content, not just a preview. '
            'IMPORTANT: Maximum 3 articles can be loaded at a time. '
            'When you reach the limit, use unload_article to free a slot. '
            'Pass your agent_id to enable article memory tracking.'
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
                'agent_id': {
                    'type': 'string',
                    'description': 'Your agent ID (REQUIRED for article memory tracking and slot management). You can find this in your persona memory block.',
                },
            },
            'required': ['article_identifier', 'agent_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Read the full content of an article."""
        try:
            identifier = arguments['article_identifier']
            max_length = arguments.get('max_length', 50000)
            agent_id = arguments.get('agent_id')

            if not agent_id:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: agent_id is required for article memory tracking. '
                            'Pass your agent_id to enable the 3-article memory limit system.',
                        }
                    ],
                    isError=True,
                )

            # Check if agent has reached the 3-article limit
            loaded_articles = _AGENT_LOADED_ARTICLES.get(agent_id, [])
            if len(loaded_articles) >= 3:
                loaded_titles = [a['title'] for a in loaded_articles]
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '⚠️ Article Memory Full: You have reached the maximum of 3 articles loaded.\n\n'
                            'Currently loaded:\n'
                            + '\n'.join(
                                f'  {i + 1}. {title}'
                                for i, title in enumerate(loaded_titles)
                            )
                            + '\n\n'
                            'Use unload_article to free a memory slot before loading new articles.',
                        }
                    ],
                    isError=True,
                )

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

            # 1. Try markdown_content from database (processed_papers)
            if paper.get('markdown_content'):
                article_content = paper['markdown_content']
                logger.info('Using markdown_content from database')

            # 2. Try reading from note_path file
            if not article_content and paper.get('note_path'):
                note_path = Path(paper['note_path'])
                if note_path.exists():
                    try:
                        article_content = note_path.read_text(encoding='utf-8')
                        logger.info(f'Read content from note_path: {note_path}')
                    except Exception as e:
                        logger.warning(f'Failed to read note_path: {e}')

            # 3. Try reading from markdown_path file
            if not article_content and paper.get('markdown_path'):
                markdown_path = Path(paper['markdown_path'])
                if markdown_path.exists():
                    try:
                        article_content = markdown_path.read_text(encoding='utf-8')
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

            # Track this article in agent's loaded articles
            article_info = {
                'title': title,
                'identifier': identifier,
                'doi': paper.get('doi'),
                'arxiv_id': paper.get('arxiv_id'),
                'loaded_at': datetime.now().isoformat(),
            }

            # Check if article is already loaded (avoid duplicates)
            is_already_loaded = any(
                a.get('doi') == article_info.get('doi')
                or a.get('arxiv_id') == article_info.get('arxiv_id')
                or a.get('title') == article_info.get('title')
                for a in loaded_articles
                if a.get('doi') or a.get('arxiv_id') or a.get('title')
            )

            if not is_already_loaded:
                # Add to loaded articles
                if agent_id not in _AGENT_LOADED_ARTICLES:
                    _AGENT_LOADED_ARTICLES[agent_id] = []
                _AGENT_LOADED_ARTICLES[agent_id].append(article_info)
                loaded_articles = _AGENT_LOADED_ARTICLES[agent_id]

                # Import LettaService for tool management
                from thoth.services.letta_service import LettaService

                letta_service = LettaService()

                # TOOL MANAGEMENT: Attach/detach based on article count
                if len(loaded_articles) == 1:
                    # First article loaded: attach unload_article
                    logger.info(
                        f'First article loaded for agent {agent_id[:8]}, attaching unload_article'
                    )
                    attach_result = letta_service.attach_tools_to_agent(
                        agent_id=agent_id, tool_names=['unload_article']
                    )
                    if attach_result['attached'] or attach_result['already_attached']:
                        logger.info(f'Attached unload_article to agent {agent_id[:8]}')

                elif len(loaded_articles) == 3:
                    # Third article loaded: detach read_full_article
                    logger.info(
                        f'Third article loaded for agent {agent_id[:8]}, detaching read_full_article'
                    )
                    detach_result = letta_service.detach_tools_from_agent(
                        agent_id=agent_id, tool_names=['read_full_article']
                    )
                    if detach_result['detached']:
                        logger.info(
                            f'Detached read_full_article from agent {agent_id[:8]}'
                        )

            # Add memory status banner
            loaded_count = len(_AGENT_LOADED_ARTICLES.get(agent_id, []))
            loaded_titles = [
                a['title'] for a in _AGENT_LOADED_ARTICLES.get(agent_id, [])
            ]

            memory_banner = (
                f'\n\n---\n📚 **Article Memory: {loaded_count}/3 slots used**\n'
            )
            if loaded_titles:
                memory_banner += '\nCurrently loaded:\n'
                memory_banner += '\n'.join(
                    f'  {i + 1}. {title}' for i, title in enumerate(loaded_titles)
                )
            if loaded_count == 3:
                memory_banner += '\n\n⚠️ Memory full! Use unload_article to free a slot.'
            elif loaded_count > 0:
                memory_banner += (
                    '\n\n💡 Use unload_article to free slots when done with an article.'
                )

            response_text += memory_banner

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            logger.error(f'Error reading full article: {e}')
            return self.handle_error(e)


class UnloadArticleMCPTool(MCPTool):
    """
    MCP tool for unloading articles from agent memory.

    Use this tool to free up article memory slots when you're done with an
    article and need to load a different one. Each agent can have a maximum
    of 3 articles loaded at once.
    """

    @property
    def name(self) -> str:
        return 'unload_article'

    @property
    def description(self) -> str:
        return (
            'Unload an article from your working memory to free a memory slot. '
            'Use this when you are done with an article and need to load a different one. '
            'Maximum 3 articles can be loaded at a time. '
            'When you unload from 3 to 2 articles, read_full_article becomes available again. '
            'IMPORTANT: Pass your agent_id and the article identifier (title, DOI, or arXiv ID).'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_identifier': {
                    'type': 'string',
                    'description': 'Article title, DOI, or arXiv ID to unload (must match a currently loaded article)',
                },
                'agent_id': {
                    'type': 'string',
                    'description': 'Your agent ID (REQUIRED for article memory management).',
                },
            },
            'required': ['article_identifier', 'agent_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Unload an article from agent memory."""
        try:
            identifier = arguments['article_identifier']
            agent_id = arguments.get('agent_id')

            if not agent_id:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: agent_id is required to unload articles.',
                        }
                    ],
                    isError=True,
                )

            # Check if agent has any loaded articles
            if (
                agent_id not in _AGENT_LOADED_ARTICLES
                or not _AGENT_LOADED_ARTICLES[agent_id]
            ):
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '⚠️ No articles are currently loaded in memory. Nothing to unload.',
                        }
                    ],
                    isError=False,
                )

            loaded_articles = _AGENT_LOADED_ARTICLES[agent_id]

            # Find matching article (by title, DOI, or arXiv ID)
            article_to_remove = None
            identifier_lower = identifier.lower()

            for article in loaded_articles:
                # Match by title
                if article.get('title', '').lower() == identifier_lower:
                    article_to_remove = article
                    break
                # Match by DOI
                if article.get('doi'):
                    doi_clean = identifier.replace('https://doi.org/', '').replace(
                        'http://doi.org/', ''
                    )
                    if article['doi'].lower() == doi_clean.lower():
                        article_to_remove = article
                        break
                # Match by arXiv ID
                if article.get('arxiv_id'):
                    arxiv_clean = (
                        identifier.replace('arXiv:', '').replace('arxiv:', '').strip()
                    )
                    if article['arxiv_id'].lower() == arxiv_clean.lower():
                        article_to_remove = article
                        break
                # Partial title match (if no exact match found)
                if identifier_lower in article.get('title', '').lower():
                    article_to_remove = article
                    # Don't break - keep looking for exact match

            if not article_to_remove:
                loaded_titles = [a['title'] for a in loaded_articles]
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f'⚠️ Article not found in memory: {identifier}\n\n'
                            f'Currently loaded:\n'
                            + '\n'.join(
                                f'  {i + 1}. {title}'
                                for i, title in enumerate(loaded_titles)
                            )
                            + '\n\nUse one of the above titles or identifiers to unload.',
                        }
                    ],
                    isError=True,
                )

            # Track article count before removal
            articles_before = len(loaded_articles)

            # Remove the article
            _AGENT_LOADED_ARTICLES[agent_id].remove(article_to_remove)
            articles_after = len(_AGENT_LOADED_ARTICLES[agent_id])

            # Import LettaService for tool management
            from thoth.services.letta_service import LettaService

            letta_service = LettaService()

            results = [f'✅ Unloaded article: {article_to_remove["title"]}']

            # TOOL MANAGEMENT: Re-attach/detach based on article count
            if articles_before == 3 and articles_after == 2:
                # Unloaded from full: re-attach read_full_article
                logger.info(
                    f'Unloaded from 3 to 2 articles for agent {agent_id[:8]}, re-attaching read_full_article'
                )
                attach_result = letta_service.attach_tools_to_agent(
                    agent_id=agent_id, tool_names=['read_full_article']
                )
                if attach_result['attached'] or attach_result['already_attached']:
                    results.append(
                        '\n✓ Re-attached read_full_article tool (memory no longer full)'
                    )
                    logger.info(
                        f'Re-attached read_full_article to agent {agent_id[:8]}'
                    )

            if articles_after == 0:
                # Last article unloaded: detach unload_article
                logger.info(
                    f'Last article unloaded for agent {agent_id[:8]}, detaching unload_article'
                )
                detach_result = letta_service.detach_tools_from_agent(
                    agent_id=agent_id, tool_names=['unload_article']
                )
                if detach_result['detached']:
                    results.append(
                        '\n✓ Removed unload_article tool (no articles loaded)'
                    )
                    logger.info(f'Detached unload_article from agent {agent_id[:8]}')

                # Clean up the tracking dict
                del _AGENT_LOADED_ARTICLES[agent_id]
            else:
                logger.info(
                    f'Agent {agent_id[:8]} now has {articles_after} article(s) loaded'
                )

            # Add memory status
            loaded_count = articles_after
            memory_status = f'\n\n📚 **Article Memory: {loaded_count}/3 slots used**'

            if loaded_count > 0:
                loaded_titles = [a['title'] for a in _AGENT_LOADED_ARTICLES[agent_id]]
                memory_status += '\n\nCurrently loaded:\n'
                memory_status += '\n'.join(
                    f'  {i + 1}. {title}' for i, title in enumerate(loaded_titles)
                )
                memory_status += (
                    '\n\n💡 You can now load more articles or unload others.'
                )
            else:
                memory_status += '\n\n✓ All article memory slots are free.'

            results.append(memory_status)

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(results)}]
            )

        except Exception as e:
            logger.error(f'Error unloading article: {e}')
            return self.handle_error(e)

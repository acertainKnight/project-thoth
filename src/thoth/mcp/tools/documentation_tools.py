"""MCP tools for accessing Thoth's own documentation.

Documentation is indexed into thoth_docs / thoth_doc_chunks at startup
(via DocumentationService). These tools search and load those docs.

DOCUMENTATION MEMORY MANAGEMENT:
- Maximum 2 doc pages can be loaded per agent at a time
- When load_documentation is called:
  1. Doc content is fetched and returned inline
  2. On first load (0 -> 1): unload_documentation tool is attached
  3. On second load (1 -> 2 = max): load_documentation tool is detached
- When unload_documentation is called:
  1. Entry removed from tracking
  2. On unload from 2 to 1: load_documentation re-attached
  3. On unload from 1 to 0: unload_documentation detached
"""

from typing import Any

from loguru import logger

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult
from thoth.services import documentation_service

# Server-side tracking: agent_id → list of loaded doc titles
_AGENT_LOADED_DOCS: dict[str, list[str]] = {}

MAX_LOADED_DOCS = 2


class SearchDocumentationMCPTool(MCPTool):
    """Semantic search over Thoth's indexed documentation."""

    @property
    def name(self) -> str:
        return 'search_documentation'

    @property
    def description(self) -> str:
        return (
            "Search Thoth's own documentation semantically. Returns the most relevant "
            'passages from the docs/ directory for any question about how the system works. '
            "Use this when users ask 'how does X work', 'what is Y', or 'where do I find Z'. "
            'To read a full documentation page, use load_documentation.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'Question or topic to search for in the documentation.',
                },
                'k': {
                    'type': 'integer',
                    'description': 'Number of results to return (default 5)',
                    'default': 5,
                    'minimum': 1,
                    'maximum': 10,
                },
            },
            'required': ['query'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        query = (arguments.get('query') or '').strip()
        if not query:
            return MCPToolCallResult(content='Error: query is required.', is_error=True)

        k = int(arguments.get('k', 5))

        try:
            postgres = self.service_manager.postgres
            embedding_manager = self.service_manager.rag.rag_manager.embedding_manager
            results = await documentation_service.search(
                postgres, embedding_manager, query, k=k
            )
        except Exception as e:
            logger.error(f'Documentation search failed: {e}')
            return MCPToolCallResult(
                content=f'Search failed: {e}. Try load_documentation with a specific topic name.',
                is_error=True,
            )

        if not results:
            available = [d['title'] for d in documentation_service.list_available()]
            return MCPToolCallResult(
                content=(
                    f"No results found for '{query}'. "
                    f'Documentation may not be indexed yet. '
                    f'Available topics: {", ".join(available)}'
                )
            )

        lines = [f"Documentation search results for '{query}':\n"]
        seen_titles: set[str] = set()
        for r in results:
            title = r['title']
            excerpt = r['content'][:400].replace('\n', ' ').strip()
            if title not in seen_titles:
                lines.append(f'[{title}]')
                seen_titles.add(title)
            lines.append(f'  ...{excerpt}...\n')

        lines.append(
            '\nUse load_documentation(topic="<title>", agent_id="...") to read a full page.'
        )
        return MCPToolCallResult(content='\n'.join(lines))


class LoadDocumentationMCPTool(MCPTool):
    """Load a full documentation page into context."""

    @property
    def name(self) -> str:
        return 'load_documentation'

    @property
    def description(self) -> str:
        return (
            'Load a full Thoth documentation page into your context. '
            'Returns the complete markdown content of the requested doc. '
            "Use the topic name (filename stem) like 'rag-system', 'skills-system', 'usage'. "
            'Maximum 2 docs can be loaded at once. '
            'Use unload_documentation to free a slot when done. '
            'Pass your agent_id to enable slot management.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'topic': {
                    'type': 'string',
                    'description': (
                        'Documentation topic to load (filename stem). '
                        "Examples: 'rag-system', 'skills-system', 'usage', 'architecture'. "
                        'Use search_documentation to find the right topic name.'
                    ),
                },
                'agent_id': {
                    'type': 'string',
                    'description': 'Your agent ID for slot management tracking.',
                },
            },
            'required': ['topic', 'agent_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        from thoth.services.letta_service import LettaService

        topic = (arguments.get('topic') or '').strip().lower()
        agent_id = (arguments.get('agent_id') or '').strip()

        if not topic:
            return MCPToolCallResult(content='Error: topic is required.', is_error=True)
        if not agent_id:
            return MCPToolCallResult(
                content='Error: agent_id is required.', is_error=True
            )

        loaded = _AGENT_LOADED_DOCS.get(agent_id, [])
        if topic in loaded:
            return MCPToolCallResult(
                content=f"'{topic}' is already loaded. Use unload_documentation to free the slot first."
            )

        if len(loaded) >= MAX_LOADED_DOCS:
            return MCPToolCallResult(
                content=(
                    f'Documentation slot full ({MAX_LOADED_DOCS} docs loaded: {", ".join(loaded)}). '
                    'Use unload_documentation to free a slot.'
                ),
                is_error=True,
            )

        postgres = self.service_manager.postgres
        content = await documentation_service.get_doc_content(postgres, topic)

        if content is None:
            available = [d['title'] for d in documentation_service.list_available()]
            return MCPToolCallResult(
                content=(
                    f"Documentation '{topic}' not found. "
                    f'Available topics: {", ".join(available)}'
                ),
                is_error=True,
            )

        # Track the loaded doc
        docs_before = len(loaded)
        if agent_id not in _AGENT_LOADED_DOCS:
            _AGENT_LOADED_DOCS[agent_id] = []
        _AGENT_LOADED_DOCS[agent_id].append(topic)
        docs_after = len(_AGENT_LOADED_DOCS[agent_id])

        letta_service = LettaService()

        if docs_before == 0 and docs_after == 1:
            letta_service.attach_tools_to_agent(
                agent_id=agent_id, tool_names=['unload_documentation']
            )

        if docs_after >= MAX_LOADED_DOCS:
            letta_service.detach_tools_from_agent(
                agent_id=agent_id, tool_names=['load_documentation']
            )

        # Truncate very long docs to avoid overwhelming the context
        max_chars = 30_000
        truncated = len(content) > max_chars
        display_content = content[:max_chars] if truncated else content

        footer_lines = [
            '\n---',
            f'Doc: {topic} | Slots: {docs_after}/{MAX_LOADED_DOCS}',
        ]
        if truncated:
            footer_lines.append(
                f'(Content truncated at {max_chars} chars. '
                'Use search_documentation for specific sections.)'
            )
        footer_lines.append('Use unload_documentation when done to free the slot.')

        return MCPToolCallResult(content=display_content + '\n'.join(footer_lines))


class UnloadDocumentationMCPTool(MCPTool):
    """Unload a documentation page from context, freeing the slot."""

    @property
    def name(self) -> str:
        return 'unload_documentation'

    @property
    def description(self) -> str:
        return (
            'Unload a documentation page to free a slot. '
            'Call this when you are done reading a doc and want to load a different one.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'topic': {
                    'type': 'string',
                    'description': 'The topic name to unload (same as what was passed to load_documentation).',
                },
                'agent_id': {
                    'type': 'string',
                    'description': 'Your agent ID.',
                },
            },
            'required': ['topic', 'agent_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        from thoth.services.letta_service import LettaService

        topic = (arguments.get('topic') or '').strip().lower()
        agent_id = (arguments.get('agent_id') or '').strip()

        if not topic or not agent_id:
            return MCPToolCallResult(
                content='Error: both topic and agent_id are required.', is_error=True
            )

        loaded = _AGENT_LOADED_DOCS.get(agent_id, [])
        if topic not in loaded:
            return MCPToolCallResult(
                content=f"'{topic}' is not currently loaded. Loaded docs: {', '.join(loaded) or 'none'}."
            )

        docs_before = len(loaded)
        _AGENT_LOADED_DOCS[agent_id].remove(topic)
        docs_after = len(_AGENT_LOADED_DOCS[agent_id])

        letta_service = LettaService()

        if docs_before == MAX_LOADED_DOCS and docs_after < MAX_LOADED_DOCS:
            letta_service.attach_tools_to_agent(
                agent_id=agent_id, tool_names=['load_documentation']
            )

        if docs_after == 0:
            letta_service.detach_tools_from_agent(
                agent_id=agent_id, tool_names=['unload_documentation']
            )
            del _AGENT_LOADED_DOCS[agent_id]

        remaining = _AGENT_LOADED_DOCS.get(agent_id, [])
        return MCPToolCallResult(
            content=(
                f"Unloaded '{topic}'. "
                f'Slots: {docs_after}/{MAX_LOADED_DOCS}. '
                f'Still loaded: {", ".join(remaining) or "none"}.'
            )
        )

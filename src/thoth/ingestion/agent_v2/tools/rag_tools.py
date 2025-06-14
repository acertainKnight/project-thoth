"""
RAG (Retrieval-Augmented Generation) tools for the research assistant.

This module provides tools for searching and querying the knowledge base
using vector similarity search and LLM-based question answering.
"""

from typing import Any

from pydantic import BaseModel, Field

from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool


class SearchInput(BaseModel):
    """Schema for search/RAG tools."""

    query: str = Field(description='Search query or question')
    k: int = Field(default=4, description='Number of results to return')


class SearchKnowledgeTool(BaseThothTool):
    """Tool for searching the knowledge base."""

    name: str = 'search_knowledge'
    description: str = 'Search the knowledge base using semantic search'
    args_schema: type[BaseModel] = SearchInput

    def _run(self, query: str, k: int = 4, filter: dict[str, Any] | None = None) -> str:
        """Search the knowledge base."""
        try:
            results = self.service_manager.rag.search(query=query, k=k, filter=filter)

            if not results:
                return '❌ No results found for your query.'

            output = f'🔍 **Search Results for:** "{query}"\n\n'
            for i, result in enumerate(results, 1):
                output += f'**{i}. {result.get("title", "Untitled")}**\n'
                output += f'   📄 Type: {result.get("document_type", "Unknown")}\n'
                output += f'   📊 Score: {result.get("score", 0):.3f}\n'
                output += f'   📝 Content: {result.get("content", "")[:200]}...\n\n'

            return output.strip()
        except Exception as e:
            return self.handle_error(e, 'searching knowledge base')


class AskQuestionTool(BaseThothTool):
    """Tool for asking questions about the knowledge base."""

    name: str = 'ask_knowledge_base'
    description: str = 'Ask a question and get an answer based on the knowledge base'
    args_schema: type[BaseModel] = SearchInput

    def _run(self, query: str, k: int = 4, filter: dict[str, Any] | None = None) -> str:
        """Ask a question."""
        try:
            response = self.service_manager.rag.ask_question(
                question=query, k=k, filter=filter
            )

            if not response:
                return '❌ Unable to generate an answer.'

            output = f'❓ **Question:** {query}\n\n'
            output += (
                f'💡 **Answer:**\n{response.get("answer", "No answer available")}\n\n'
            )

            # Include sources if available
            if response.get('sources'):
                output += '📚 **Sources:**\n'
                for i, source in enumerate(response['sources'], 1):
                    title = source.get('metadata', {}).get('title', 'Untitled')
                    doc_type = source.get('metadata', {}).get(
                        'document_type', 'Unknown'
                    )
                    output += f'{i}. {title} ({doc_type})\n'

            return output.strip()
        except Exception as e:
            return self.handle_error(e, 'asking knowledge base')


class IndexKnowledgeBaseTool(BaseThothTool):
    """Tool for indexing the knowledge base."""

    name: str = 'index_knowledge_base'
    description: str = (
        'Index all markdown files in the knowledge base into the RAG system'
    )

    def _run(self) -> str:
        """Index the knowledge base."""
        try:
            stats = self.service_manager.rag.index_knowledge_base()

            output = '📚 **Knowledge Base Indexing Complete!**\n\n'
            output += '📊 **Statistics:**\n'
            output += f'- Total files indexed: {stats.get("total_files", 0)}\n'
            output += f'- Total chunks created: {stats.get("total_chunks", 0)}\n'
            output += f'- Notes indexed: {stats.get("notes_indexed", 0)}\n'
            output += f'- Articles indexed: {stats.get("articles_indexed", 0)}\n'

            if stats.get('errors'):
                output += f'\n⚠️ **Errors:** {stats["errors"]}'

            output += '\n\n✅ Your knowledge base is now searchable!'
            return output
        except Exception as e:
            return self.handle_error(e, 'indexing knowledge base')


class GetRAGStatsTool(BaseThothTool):
    """Tool for getting RAG system statistics."""

    name: str = 'get_rag_stats'
    description: str = (
        'Get statistics about the RAG (Retrieval-Augmented Generation) system'
    )

    def _run(self) -> str:
        """Get RAG statistics."""
        try:
            stats = self.service_manager.rag.get_statistics()

            output = '📊 **RAG System Statistics**\n\n'
            output += '**Vector Store:**\n'
            output += f'- Total documents: {stats.get("document_count", 0)}\n'
            output += f'- Total chunks: {stats.get("total_chunks", 0)}\n'
            output += f'- Collection name: {stats.get("collection_name", "N/A")}\n'

            if 'embeddings' in stats:
                output += '\n**Embeddings:**\n'
                output += f'- Model: {stats["embeddings"].get("model", "N/A")}\n'
                output += (
                    f'- Dimension: {stats["embeddings"].get("dimension", "N/A")}\n'
                )

            if stats.get('last_indexed'):
                output += f'\n**Last indexed:** {stats["last_indexed"]}'

            return output
        except Exception as e:
            return self.handle_error(e, 'getting RAG statistics')


class ClearRAGIndexTool(BaseThothTool):
    """Tool for clearing the RAG index."""

    name: str = 'clear_rag_index'
    description: str = 'Clear the entire RAG index (use with caution!)'

    def _run(self) -> str:
        """Clear the RAG index."""
        try:
            self.service_manager.rag.clear_index()
            return '✅ RAG index cleared successfully. You will need to re-index your knowledge base.'
        except Exception as e:
            return self.handle_error(e, 'clearing RAG index')


class ExplainConnectionsInput(BaseModel):
    """Input for explaining connections between papers."""

    paper1: str = Field(description='Title or ID of the first paper')
    paper2: str = Field(description='Title or ID of the second paper')


class ExplainConnectionsTool(BaseThothTool):
    """Explain connections between papers."""

    name: str = 'explain_connections'
    description: str = (
        'Explain the connections and relationships between two research papers. '
        'Analyzes how they relate, what concepts they share, and how one might '
        'build upon or reference the other.'
    )
    args_schema: type[BaseModel] = ExplainConnectionsInput

    def _run(self, paper1: str, paper2: str) -> str:
        """Explain connections between papers."""
        try:
            # First, find the papers
            results1 = self.service_manager.rag.search(
                query=paper1,
                k=1,
            )

            if not results1:
                return f'❌ Could not find paper: "{paper1}"'

            results2 = self.service_manager.rag.search(
                query=paper2,
                k=1,
            )

            if not results2:
                return f'❌ Could not find paper: "{paper2}"'

            title1 = results1[0]['title']
            title2 = results2[0]['title']

            # Ask about connections
            question = (
                f'What are the connections and relationships between these two papers: '
                f'"{title1}" and "{title2}"? How do they relate to each other?'
            )

            result = self.service_manager.rag.ask_question(
                question=question,
                k=6,  # Get more context for connection analysis
            )

            output = '🔗 **Connection Analysis**\n\n'
            output += f'**Paper 1:** {title1}\n'
            output += f'**Paper 2:** {title2}\n\n'
            output += '**Analysis:**\n'
            output += result['answer']

            return output.strip()

        except Exception as e:
            return self.handle_error(e, 'explaining connections')

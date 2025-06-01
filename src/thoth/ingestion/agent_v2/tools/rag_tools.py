"""
RAG (Retrieval-Augmented Generation) tools for the research assistant.

This module provides tools for searching the knowledge base, asking questions,
and exploring connections between research papers.
"""

from pydantic import BaseModel, Field

from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool


class SearchKnowledgeInput(BaseModel):
    """Input schema for searching knowledge base."""

    query: str = Field(description='Search query')
    k: int = Field(default=4, description='Number of results to return')
    document_type: str | None = Field(
        default=None,
        description="Filter by document type: 'note', 'article', or None for all",
    )


class SearchKnowledgeTool(BaseThothTool):
    """Search the research knowledge base."""

    name: str = 'search_knowledge'
    description: str = (
        'Search through your research papers and notes. Returns relevant excerpts '
        'from your knowledge base with similarity scores.'
    )
    args_schema: type[BaseModel] = SearchKnowledgeInput

    def _run(self, query: str, k: int = 4, document_type: str | None = None) -> str:
        """Search the knowledge base."""
        try:
            # Build filter if document type specified
            filter_dict = None
            if document_type:
                filter_dict = {'document_type': document_type}

            results = self.pipeline.search_knowledge_base(
                query=query,
                k=k,
                filter=filter_dict,
            )

            if not results:
                return f"No results found for query: '{query}'"

            response = [f"🔍 **Search results for:** '{query}'\n"]
            for i, result in enumerate(results, 1):
                response.append(f'\n**Result {i}:**')
                response.append(f'📄 Title: {result["title"]}')
                response.append(f'📊 Type: {result["document_type"]}')
                response.append(f'✨ Score: {result["score"]:.3f}')
                response.append(f'📝 Preview: {result["content"][:300]}...')

            return '\n'.join(response)

        except Exception as e:
            return self.handle_error(e, 'searching knowledge base')


class AskKnowledgeInput(BaseModel):
    """Input schema for asking questions about knowledge base."""

    question: str = Field(description='Question to ask about your research')
    k: int = Field(default=4, description='Number of context documents to use')


class AskKnowledgeTool(BaseThothTool):
    """Ask questions about the research knowledge base."""

    name: str = 'ask_knowledge'
    description: str = (
        'Ask a question about your research collection and get an answer '
        'synthesized from relevant papers and notes with citations.'
    )
    args_schema: type[BaseModel] = AskKnowledgeInput

    def _run(self, question: str, k: int = 4) -> str:
        """Ask a question about the knowledge base."""
        try:
            result = self.pipeline.ask_knowledge_base(
                question=question,
                k=k,
            )

            response = [f'❓ **Question:** {result["question"]}\n']
            response.append(f'💡 **Answer:** {result["answer"]}\n')

            if result.get('sources'):
                response.append('📚 **Sources:**')
                for i, source in enumerate(result['sources'], 1):
                    title = source['metadata'].get('title', 'Unknown')
                    doc_type = source['metadata'].get('document_type', 'Unknown')
                    response.append(f'{i}. {title} ({doc_type})')

            return '\n'.join(response)

        except Exception as e:
            return self.handle_error(e, 'answering question')


class IndexKnowledgeTool(BaseThothTool):
    """Index documents in the knowledge base."""

    name: str = 'index_knowledge'
    description: str = (
        'Index all documents in the knowledge base for RAG search. '
        'This enables semantic search and question answering across your research.'
    )

    def _run(self) -> str:
        """Index the knowledge base."""
        try:
            stats = self.pipeline.index_knowledge_base()

            response = ['✅ **Knowledge Base Indexing Complete!**\n']
            response.append(f'📊 Total files indexed: {stats["total_files"]}')
            response.append(f'📄 Markdown files: {stats["markdown_files"]}')
            response.append(f'📝 Note files: {stats["note_files"]}')
            response.append(f'🧩 Total chunks created: {stats["total_chunks"]}')

            if stats['errors']:
                response.append('\n⚠️ **Errors encountered:**')
                for error in stats['errors']:
                    response.append(f'- {error}')

            if 'vector_store' in stats:
                response.append('\n🗄️ **Vector Store Info:**')
                response.append(
                    f'- Collection: {stats["vector_store"]["collection_name"]}'
                )
                response.append(
                    f'- Documents: {stats["vector_store"]["document_count"]}'
                )

            return '\n'.join(response)

        except Exception as e:
            return self.handle_error(e, 'indexing knowledge base')


class ExplainConnectionsInput(BaseModel):
    """Input schema for explaining connections between papers."""

    paper_titles: list[str] = Field(
        description='List of paper titles to find connections between',
        min_items=2,
        max_items=5,
    )


class ExplainConnectionsTool(BaseThothTool):
    """Explain connections between research papers."""

    name: str = 'explain_connections'
    description: str = (
        'Find and explain connections between multiple research papers in your collection. '
        'Identifies shared concepts, methodologies, and how papers relate to each other.'
    )
    args_schema: type[BaseModel] = ExplainConnectionsInput

    def _run(self, paper_titles: list[str]) -> str:
        """Find connections between papers."""
        try:
            # First, search for each paper to get their content
            papers_content = []
            for title in paper_titles:
                results = self.pipeline.search_knowledge_base(
                    query=title, k=1, filter={'document_type': 'article'}
                )
                if results:
                    papers_content.append(
                        {'title': title, 'content': results[0]['content']}
                    )
                else:
                    return f"❌ Could not find paper: '{title}'"

            # Ask about connections
            question = (
                f'What are the key connections and relationships between these papers: '
                f'{", ".join(paper_titles)}? Focus on shared concepts, methodologies, '
                f'and how they build upon or relate to each other.'
            )

            result = self.pipeline.ask_knowledge_base(
                question=question, k=len(papers_content) * 2
            )

            response = ['🔗 **Connections between papers:**\n']
            response.append(f'📚 Papers analyzed: {", ".join(paper_titles)}\n')
            response.append(f'💡 **Analysis:**\n{result["answer"]}')

            return '\n'.join(response)

        except Exception as e:
            return self.handle_error(e, 'finding paper connections')


class GetRAGStatsTool(BaseThothTool):
    """Get statistics about the RAG system."""

    name: str = 'rag_stats'
    description: str = 'Get statistics about the RAG knowledge base system'

    def _run(self) -> str:
        """Get RAG statistics."""
        try:
            stats = self.pipeline.get_rag_stats()

            response = ['📊 **RAG System Statistics:**\n']
            response.append(f'📄 Documents indexed: {stats.get("document_count", 0)}')
            response.append(
                f'🏷️ Collection name: {stats.get("collection_name", "Unknown")}'
            )
            response.append(
                f'🧠 Embedding model: {stats.get("embedding_model", "Unknown")}'
            )
            response.append(f'💭 QA model: {stats.get("qa_model", "Unknown")}')
            response.append(f'📏 Chunk size: {stats.get("chunk_size", "Unknown")}')
            response.append(
                f'🔗 Chunk overlap: {stats.get("chunk_overlap", "Unknown")}'
            )

            return '\n'.join(response)

        except Exception as e:
            return self.handle_error(e, 'getting RAG stats')

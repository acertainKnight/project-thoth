"""
Analysis tools for the research assistant.

This module provides tools for evaluating articles, analyzing research topics,
and finding related work.
"""

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool


class EvaluateArticleInput(BaseModel):
    """Input schema for evaluating an article."""

    query_name: str = Field(description='Name of the query to use for evaluation')
    article_title: str = Field(description='Title of the article')
    article_abstract: str = Field(description='Abstract of the article')
    article_content: str | None = Field(
        default=None, description='Full content of the article (optional)'
    )


class EvaluateArticleTool(BaseThothTool):
    """Evaluate an article against a research query."""

    name: str = 'evaluate_article'
    description: str = (
        'Evaluate how well an article matches a research query. '
        'Provides relevance score and detailed reasoning.'
    )
    args_schema: type[BaseModel] = EvaluateArticleInput

    def _run(
        self,
        query_name: str,
        article_title: str,
        article_abstract: str,
        article_content: str | None = None,  # noqa: ARG002
    ) -> str:
        """Evaluate an article."""
        try:
            # Get the query
            query = self.pipeline.filter.agent.get_query(query_name)
            if not query:
                return f"❌ Query '{query_name}' not found."

            # Create mock article analysis for evaluation
            from thoth.utilities.models import AnalysisResponse

            mock_analysis = AnalysisResponse(
                title=article_title,
                abstract=article_abstract,
                key_findings=['Evaluation in progress...'],
                tags=[],
                summary='Evaluation in progress...',
            )

            # Evaluate the article
            evaluation = self.pipeline.filter.agent.evaluate_article(
                article=mock_analysis, query_name=query_name
            )

            if not evaluation:
                return f"❌ Failed to evaluate article against query '{query_name}'"

            response = ['📊 **Article Evaluation Results**\n']
            response.append(f'📄 Article: {article_title}')
            response.append(f'🔍 Query: {query_name}\n')
            response.append(f'✨ **Relevance Score:** {evaluation.relevance_score}/10')
            response.append(f'🎯 **Recommendation:** {evaluation.recommendation}')
            response.append(f'\n💭 **Reasoning:**\n{evaluation.reasoning}')

            if evaluation.matched_keywords:
                response.append(
                    f'\n🔤 **Matched Keywords:** {", ".join(evaluation.matched_keywords)}'
                )

            if evaluation.matched_topics:
                response.append(
                    f'\n📌 **Matched Topics:** {", ".join(evaluation.matched_topics)}'
                )

            return '\n'.join(response)

        except Exception as e:
            return self.handle_error(e, 'evaluating article')


class AnalyzeTopicInput(BaseModel):
    """Input schema for analyzing a research topic."""

    topic: str = Field(description='Research topic to analyze')
    depth: str = Field(
        default='medium', description="Analysis depth: 'quick', 'medium', or 'deep'"
    )


class AnalyzeTopicTool(BaseThothTool):
    """Analyze a research topic in your knowledge base."""

    name: str = 'analyze_topic'
    description: str = (
        'Analyze a research topic across your entire knowledge base. '
        'Provides overview, key papers, trends, and gaps.'
    )
    args_schema: type[BaseModel] = AnalyzeTopicInput

    def _run(self, topic: str, depth: str = 'medium') -> str:
        """Analyze a research topic."""
        try:
            # Determine number of papers based on depth
            k_values = {'quick': 3, 'medium': 6, 'deep': 10}
            k = k_values.get(depth, 6)

            # Search for papers on this topic
            search_results = self.pipeline.search_knowledge_base(
                query=topic, k=k, filter={'document_type': 'article'}
            )

            if not search_results:
                return f"No papers found on topic: '{topic}'"

            # Ask comprehensive questions about the topic
            questions = {
                'quick': f'What are the main findings about {topic} in my research collection?',
                'medium': f'Provide a comprehensive overview of {topic} research in my collection, including key findings, methodologies, and open questions.',
                'deep': f'Provide an in-depth analysis of {topic} in my research collection: key contributions, evolution of ideas, methodological approaches, contradictions, gaps, and future directions.',
            }

            question = questions.get(depth, questions['medium'])
            analysis = self.pipeline.ask_knowledge_base(question=question, k=k)

            response = [f'📚 **Topic Analysis: {topic}**\n']
            response.append(f'🔍 Analysis depth: {depth}')
            response.append(f'📄 Papers analyzed: {len(search_results)}\n')

            # Add top papers
            response.append('📊 **Top Relevant Papers:**')
            for i, result in enumerate(search_results[:3], 1):
                response.append(
                    f'{i}. {result["title"]} (score: {result["score"]:.3f})'
                )

            response.append(f'\n💡 **Analysis:**\n{analysis["answer"]}')

            return '\n'.join(response)

        except Exception as e:
            return self.handle_error(e, f"analyzing topic '{topic}'")


class FindRelatedInput(BaseModel):
    """Input schema for finding related work."""

    paper_title: str = Field(description='Title of the paper to find related work for')
    max_results: int = Field(
        default=5, description='Maximum number of related papers to return'
    )


class FindRelatedTool(BaseThothTool):
    """Find papers related to a specific paper."""

    name: str = 'find_related'
    description: str = (
        'Find papers in your collection that are related to a specific paper. '
        'Uses semantic similarity to identify relevant work.'
    )
    args_schema: type[BaseModel] = FindRelatedInput

    def _run(self, paper_title: str, max_results: int = 5) -> str:
        """Find related papers."""
        try:
            # First, find the target paper
            target_results = self.pipeline.search_knowledge_base(
                query=paper_title, k=1, filter={'document_type': 'article'}
            )

            if not target_results:
                return f"❌ Could not find paper: '{paper_title}'"

            target = target_results[0]

            # Extract key concepts from the target paper
            # Use a portion of the abstract/content as the search query
            search_query = target['content'][:500]  # Use first 500 chars

            # Search for related papers (excluding the target itself)
            related_results = self.pipeline.search_knowledge_base(
                query=search_query,
                k=max_results + 1,  # Get extra in case target is included
                filter={'document_type': 'article'},
            )

            # Filter out the target paper
            related_papers = [
                r
                for r in related_results
                if r['title'].lower() != target['title'].lower()
            ][:max_results]

            if not related_papers:
                return f"No related papers found for: '{paper_title}'"

            response = [f'🔗 **Related Papers for:** {paper_title}\n']

            for i, paper in enumerate(related_papers, 1):
                response.append(f'**{i}. {paper["title"]}**')
                response.append(f'   📊 Similarity: {paper["score"]:.3f}')
                response.append(f'   📝 Preview: {paper["content"][:150]}...')
                response.append('')

            # Ask about relationships
            if len(related_papers) >= 2:
                titles = [paper_title] + [p['title'] for p in related_papers[:2]]
                connections_question = (
                    f"Briefly explain how '{titles[1]}' and '{titles[2]}' "
                    f"relate to '{titles[0]}'"
                )
                connections = self.pipeline.ask_knowledge_base(
                    question=connections_question, k=3
                )
                response.append(f'💡 **Key Relationships:**\n{connections["answer"]}')

            return '\n'.join(response)

        except Exception as e:
            return self.handle_error(e, f"finding related papers for '{paper_title}'")


class ArticleAnalysisInput(BaseModel):
    """Input schema for analyzing an article."""

    article_title: str = Field(description='Title of the article')
    article_abstract: str = Field(description='Abstract of the article')
    article_content: str | None = Field(
        default=None, description='Full content of the article (optional)'
    )


class ArticleAnalysisTool(BaseThothTool):
    name: str = 'analyze_article'
    description: str = (
        'Analyzes an article to determine its relevance to a research question, '
        'evaluate its quality, and extract key information. This tool is essential '
        'for critical appraisal of literature and ensuring that only high-quality, '
        'relevant articles are included in the knowledge base.'
    )
    args_schema: type[BaseModel] = ArticleAnalysisInput

    def _run(
        self,
        article_title: str,
        article_abstract: str,
        article_content: str | None = None,  # noqa: ARG002
    ) -> str:
        """Evaluate an article."""
        client = instructor.patch(OpenAI())  # noqa: F841
        try:
            # This is a placeholder for the actual article analysis logic
            # In a real implementation, this would involve API calls to a model
            # or a more complex analysis pipeline.
            # For now, we\'ll simulate a basic relevance check.
            if not article_title or not article_abstract:
                return 'Error: Article title and abstract cannot be empty.'

            # Simulate relevance based on keywords (very basic)
            keywords = ['research', 'study', 'findings', 'analysis']
            relevant_keywords = sum(
                1
                for kw in keywords
                if kw in article_title.lower() or kw in article_abstract.lower()
            )

            if relevant_keywords > 0:
                return (
                    f"Article '{article_title}' appears relevant based on keywords. "
                    f'Abstract: {article_abstract[:200]}...'
                )
            else:
                return (
                    f"Article '{article_title}' does not seem relevant based on keywords. "
                    f'Abstract: {article_abstract[:200]}...'
                )

        except Exception as e:
            return self.handle_error(e, 'analyzing article')

    async def _arun(
        self,
        research_question: str,  # noqa: ARG002
        article_title: str,
        article_abstract: str,
        article_content: str | None = None,  # noqa: ARG002
    ) -> str:
        """Evaluate an article."""
        client = instructor.patch(OpenAI())  # noqa: F841
        try:
            # This is a placeholder for the actual article analysis logic
            # In a real implementation, this would involve API calls to a model
            # or a more complex analysis pipeline.
            # For now, we\'ll simulate a basic relevance check.
            if not article_title or not article_abstract:
                return 'Error: Article title and abstract cannot be empty.'

            # Simulate relevance based on keywords (very basic)
            keywords = ['research', 'study', 'findings', 'analysis']
            relevant_keywords = sum(
                1
                for kw in keywords
                if kw in article_title.lower() or kw in article_abstract.lower()
            )

            if relevant_keywords > 0:
                return (
                    f"Article '{article_title}' appears relevant based on keywords. "
                    f'Abstract: {article_abstract[:200]}...'
                )
            else:
                return (
                    f"Article '{article_title}' does not seem relevant based on keywords. "
                    f'Abstract: {article_abstract[:200]}...'
                )

        except Exception as e:
            return self.handle_error(e, 'analyzing article')

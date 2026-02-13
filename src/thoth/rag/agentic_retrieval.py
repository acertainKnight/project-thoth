"""
Agentic retrieval orchestrator using LangGraph.

Implements an adaptive, self-correcting retrieval pipeline that:
- Classifies queries and routes to appropriate strategies
- Expands queries for better coverage
- Decomposes complex multi-hop questions
- Grades document relevance
- Rewrites queries on low confidence
- Verifies answer groundedness
"""

import asyncio
from collections.abc import Callable
from typing import Any, Literal, TypedDict

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from loguru import logger

from thoth.rag.document_grader import DocumentGrader
from thoth.rag.hallucination_checker import HallucinationChecker
from thoth.rag.query_router import QueryRouter, QueryType
from thoth.rag.reranker import BaseReranker
from thoth.rag.vector_store import VectorStoreManager


class AgenticRAGState(TypedDict):
    """State for the agentic RAG graph."""

    # Query information
    query: str  # Original user query
    query_type: (
        str  # Classification result (DIRECT_ANSWER, STANDARD_RAG, MULTI_HOP_RAG)
    )
    sub_queries: list[str]  # Decomposed sub-queries (if multi-hop)
    expanded_queries: list[str]  # Query expansions (if enabled)
    extracted_filters: dict[str, Any]  # Metadata filters extracted from query

    # Retrieval state
    documents: list[Document]  # Retrieved documents
    graded_documents: list[Document]  # Documents that passed grading
    retrieval_k: int  # Number of documents to retrieve

    # Retry/fallback state
    retry_count: int  # Number of retrieval retries
    max_retries: int  # Max retry limit
    rewrite_reason: str  # Reason for query rewrite

    # Generation state
    answer: str  # Generated answer
    sources: list[dict[str, Any]]  # Source citations
    confidence: float  # Overall confidence score
    is_grounded: bool  # Hallucination check result
    grounding_explanation: str  # Hallucination check explanation

    # Configuration
    config: dict[str, Any]  # RAG configuration
    progress_callback: Callable[[str, str], Any] | None  # Progress update callback


class AgenticRAGOrchestrator:
    """
    LangGraph-based orchestrator for agentic retrieval.

    Coordinates adaptive retrieval strategies including query classification,
    expansion, decomposition, document grading, query rewriting, and
    hallucination detection.
    """

    def __init__(
        self,
        vector_store: VectorStoreManager,
        query_router: QueryRouter,
        document_grader: DocumentGrader,
        hallucination_checker: HallucinationChecker,
        reranker: BaseReranker,
        llm_client: Any,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize agentic RAG orchestrator.

        Args:
            vector_store: Vector store manager for retrieval
            query_router: Query router for classification and decomposition
            document_grader: Document grader for relevance filtering
            hallucination_checker: Hallucination checker for answer verification
            reranker: Reranker for result refinement
            llm_client: LLM client for generation
            config: Configuration dict with agentic retrieval settings
        """
        self.vector_store = vector_store
        self.query_router = query_router
        self.document_grader = document_grader
        self.hallucination_checker = hallucination_checker
        self.reranker = reranker
        self.llm_client = llm_client
        self.config = config or {}

        # Build the graph
        self.graph = self._build_graph()
        logger.info('Initialized AgenticRAGOrchestrator with LangGraph')

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph state machine for agentic retrieval.

        Returns:
            Compiled StateGraph
        """
        workflow = StateGraph(AgenticRAGState)

        # Add nodes
        workflow.add_node('classify_query', self._classify_query)
        workflow.add_node('expand_query', self._expand_query)
        workflow.add_node('decompose_query', self._decompose_query)
        workflow.add_node('extract_filters', self._extract_filters)
        workflow.add_node('retrieve_documents', self._retrieve_documents)
        workflow.add_node('grade_documents', self._grade_documents)
        workflow.add_node('rewrite_query', self._rewrite_query)
        workflow.add_node('rerank_documents', self._rerank_documents)
        workflow.add_node('generate_answer', self._generate_answer)
        workflow.add_node('check_hallucination', self._check_hallucination)

        # Set entry point
        workflow.set_entry_point('classify_query')

        # Add conditional edges from classify_query
        workflow.add_conditional_edges(
            'classify_query',
            self._route_after_classification,
            {
                'expand': 'expand_query',
                'decompose': 'decompose_query',
                'direct_answer': 'generate_answer',
            },
        )

        # Query expansion -> filter extraction -> retrieval
        workflow.add_edge('expand_query', 'extract_filters')
        workflow.add_edge('extract_filters', 'retrieve_documents')

        # Query decomposition -> retrieval
        workflow.add_edge('decompose_query', 'retrieve_documents')

        # Retrieval -> grading
        workflow.add_edge('retrieve_documents', 'grade_documents')

        # Add conditional edges from grade_documents
        workflow.add_conditional_edges(
            'grade_documents',
            self._route_after_grading,
            {
                'rerank': 'rerank_documents',
                'rewrite': 'rewrite_query',
                'end': END,
            },
        )

        # Query rewrite -> retrieval (retry loop)
        workflow.add_edge('rewrite_query', 'retrieve_documents')

        # Reranking -> generation
        workflow.add_edge('rerank_documents', 'generate_answer')

        # Generation -> hallucination check
        workflow.add_edge('generate_answer', 'check_hallucination')

        # Add conditional edges from check_hallucination
        workflow.add_conditional_edges(
            'check_hallucination',
            self._route_after_hallucination_check,
            {
                'accept': END,
                'retry': 'rewrite_query',
                'end': END,
            },
        )

        return workflow.compile()

    async def answer_question_async(
        self,
        query: str,
        k: int = 5,
        max_retries: int = 2,
        progress_callback: Callable[[str, str], Any] | None = None,
    ) -> dict[str, Any]:
        """
        Answer question using agentic retrieval (async).

        Args:
            query: User question
            k: Number of documents to retrieve
            max_retries: Maximum number of retrieval retries
            progress_callback: Optional callback for progress updates (step, message)

        Returns:
            Dict with answer, sources, confidence, and metadata

        Example:
            >>> result = await orchestrator.answer_question_async(
            ...     'Compare transformer and RNN architectures',
            ...     progress_callback=lambda step, msg: print(f'{step}: {msg}'),
            ... )
            >>> print(result['answer'])
        """
        # Initialize state
        initial_state: AgenticRAGState = {
            'query': query,
            'query_type': '',
            'sub_queries': [],
            'expanded_queries': [],
            'extracted_filters': {},
            'documents': [],
            'graded_documents': [],
            'retrieval_k': k,
            'retry_count': 0,
            'max_retries': max_retries,
            'rewrite_reason': '',
            'answer': '',
            'sources': [],
            'confidence': 0.0,
            'is_grounded': True,
            'grounding_explanation': '',
            'config': self.config,
            'progress_callback': progress_callback,
        }

        # Run the graph
        try:
            final_state = await asyncio.to_thread(self.graph.invoke, initial_state)

            # Format result
            result = {
                'answer': final_state['answer'],
                'sources': final_state['sources'],
                'confidence': final_state['confidence'],
                'is_grounded': final_state['is_grounded'],
                'query_type': final_state['query_type'],
                'retry_count': final_state['retry_count'],
                'num_documents': len(final_state['graded_documents']),
            }

            logger.info(
                f'Agentic RAG completed: {result["retry_count"]} retries, '
                f'{result["num_documents"]} documents'
            )

            return result

        except Exception as e:
            logger.error(f'Agentic RAG failed: {e}')
            raise

    # --- Graph Nodes ---

    def _classify_query(self, state: AgenticRAGState) -> dict[str, Any]:
        """Classify query type and route to appropriate strategy."""
        if callback := state.get('progress_callback'):
            callback('classify', 'Analyzing your question...')

        query_type = self.query_router.classify_query(state['query'])
        logger.debug(f'Query classified as: {query_type.value}')

        return {'query_type': query_type.value}

    def _expand_query(self, state: AgenticRAGState) -> dict[str, Any]:
        """Expand query with semantic variations."""
        if callback := state.get('progress_callback'):
            callback('expand', 'Expanding search terms...')

        # Check if expansion is enabled
        if not state['config'].get('query_expansion_enabled', True):
            return {'expanded_queries': [state['query']]}

        # Run expansion asynchronously but from sync node context
        try:
            asyncio.get_running_loop()
            # We're in an async context, use to_thread via executor
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.query_router.expand_query_async(
                        state['query'], self.llm_client
                    ),
                )
                expanded = future.result()
        except RuntimeError:
            # No running event loop - we can use asyncio.run directly
            # LangGraph runs nodes synchronously
            expanded = asyncio.run(
                self.query_router.expand_query_async(state['query'], self.llm_client)
            )

        logger.debug(f'Expanded to {len(expanded)} query variations')
        return {'expanded_queries': expanded}

    def _decompose_query(self, state: AgenticRAGState) -> dict[str, Any]:
        """Decompose complex query into sub-queries."""
        if callback := state.get('progress_callback'):
            callback('decompose', 'Breaking down into sub-questions...')

        # Run decomposition
        try:
            asyncio.get_running_loop()
            # We're in an async context, use executor
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.query_router.decompose_query_async(
                        state['query'], self.llm_client
                    ),
                )
                sub_queries = future.result()
        except RuntimeError:
            # No running event loop - use asyncio.run directly
            sub_queries = asyncio.run(
                self.query_router.decompose_query_async(state['query'], self.llm_client)
            )

        logger.debug(f'Decomposed into {len(sub_queries)} sub-queries')
        return {'sub_queries': sub_queries, 'expanded_queries': sub_queries}

    def _extract_filters(self, state: AgenticRAGState) -> dict[str, Any]:
        """Extract metadata filters from query."""
        # Filter extraction is optional and fast, so we do it inline
        try:
            asyncio.get_running_loop()
            # We're in an async context, use executor
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.query_router.extract_filters_async(
                        state['query'], self.llm_client
                    ),
                )
                filters = future.result()
        except RuntimeError:
            # No running event loop - use asyncio.run directly
            filters = asyncio.run(
                self.query_router.extract_filters_async(state['query'], self.llm_client)
            )

        if filters:
            logger.debug(f'Extracted filters: {filters}')

        return {'extracted_filters': filters}

    def _retrieve_documents(self, state: AgenticRAGState) -> dict[str, Any]:
        """Retrieve documents using expanded queries."""
        if callback := state.get('progress_callback'):
            callback('retrieve', 'Searching your knowledge base...')

        queries = state['expanded_queries'] or [state['query']]
        filters = state['extracted_filters']
        k = state['retrieval_k']

        # Retrieve for each query variation
        all_docs: list[Document] = []
        for query in queries:
            try:
                # Use asyncio.run since we're in sync context
                docs = asyncio.run(
                    self.vector_store.similarity_search_async(
                        query=query, k=k, filter=filters or None
                    )
                )
                all_docs.extend(docs)
            except Exception as e:
                logger.error(f'Retrieval failed for query "{query}": {e}')

        # Deduplicate by document ID or content hash
        seen = set()
        unique_docs = []
        for doc in all_docs:
            doc_id = doc.metadata.get('paper_id') or hash(doc.page_content[:200])
            if doc_id not in seen:
                seen.add(doc_id)
                unique_docs.append(doc)

        logger.info(f'Retrieved {len(unique_docs)} unique documents')
        return {'documents': unique_docs}

    def _grade_documents(self, state: AgenticRAGState) -> dict[str, Any]:
        """Grade documents for relevance."""
        if callback := state.get('progress_callback'):
            callback('grade', 'Evaluating relevance...')

        # Check if grading is enabled
        if not state['config'].get('document_grading_enabled', True):
            return {
                'graded_documents': state['documents'],
                'confidence': 1.0,
            }

        # Grade documents
        try:
            relevant, irrelevant = asyncio.run(
                self.document_grader.grade_documents_async(
                    state['query'], state['documents']
                )
            )
        except Exception as e:
            logger.error(f'Document grading failed: {e}')
            # Fail open - use all documents
            relevant = state['documents']
            irrelevant = []

        # Calculate confidence
        if state['documents']:
            confidence = len(relevant) / len(state['documents'])
        else:
            confidence = 0.0

        logger.debug(
            f'Grading: {len(relevant)} relevant, {len(irrelevant)} irrelevant (confidence={confidence:.2f})'
        )

        return {
            'graded_documents': relevant,
            'confidence': confidence,
        }

    def _rewrite_query(self, state: AgenticRAGState) -> dict[str, Any]:
        """Rewrite query based on retrieved documents."""
        if callback := state.get('progress_callback'):
            callback('rewrite', 'Refining search strategy...')

        # Get snippet of retrieved documents for context
        doc_summaries = []
        for doc in state['documents'][:3]:
            title = doc.metadata.get('title', 'Untitled')
            snippet = doc.page_content[:150]
            doc_summaries.append(f'- {title}: {snippet}...')

        context = '\n'.join(doc_summaries)

        prompt = f"""The following documents were retrieved for this query, but they may not be relevant enough.
Rewrite the query to better match relevant documents.

Original Query: {state['query']}

Retrieved Documents:
{context}

Rewritten Query:"""

        try:
            response = self.llm_client.invoke(prompt)
            rewritten = response.content.strip()
            logger.info(f'Query rewritten: "{state["query"]}" -> "{rewritten}"')
        except Exception as e:
            logger.error(f'Query rewriting failed: {e}')
            rewritten = state['query']

        # Increment retry counter
        retry_count = state['retry_count'] + 1

        return {
            'query': rewritten,
            'expanded_queries': [rewritten],
            'retry_count': retry_count,
            'rewrite_reason': 'Low relevance confidence',
        }

    def _rerank_documents(self, state: AgenticRAGState) -> dict[str, Any]:
        """Rerank documents for final result set."""
        if callback := state.get('progress_callback'):
            callback('rerank', 'Ranking best results...')

        docs = state['graded_documents']
        k = state['retrieval_k']

        try:
            reranked = asyncio.run(
                self.reranker.rerank_async(state['query'], docs, top_n=k)
            )
            logger.debug(f'Reranked {len(docs)} documents to top {len(reranked)}')
        except Exception as e:
            logger.error(f'Reranking failed: {e}')
            reranked = docs[:k]

        return {'graded_documents': reranked}

    def _generate_answer(self, state: AgenticRAGState) -> dict[str, Any]:
        """Generate answer from retrieved documents."""
        if callback := state.get('progress_callback'):
            callback('generate', 'Composing answer...')

        # For direct answer (no retrieval), generate without context
        if state['query_type'] == QueryType.DIRECT_ANSWER.value:
            prompt = ChatPromptTemplate.from_template(
                'Answer this question concisely:\n\n{query}'
            )
            chain = prompt | self.llm_client | StrOutputParser()
            answer = chain.invoke({'query': state['query']})
            return {
                'answer': answer,
                'sources': [],
                'confidence': 1.0,
            }

        # Build context from graded documents
        docs = state['graded_documents']
        if not docs:
            return {
                'answer': 'I could not find relevant documents to answer your question.',
                'sources': [],
                'confidence': 0.0,
            }

        # Format context
        context_parts = []
        sources = []
        for i, doc in enumerate(docs):
            title = doc.metadata.get('title', f'Document {i + 1}')
            content = doc.page_content
            context_parts.append(f'[Source {i + 1}] {title}\n{content}')

            sources.append(
                {
                    'title': title,
                    'paper_id': doc.metadata.get('paper_id'),
                    'authors': doc.metadata.get('authors'),
                    'relevance_score': doc.metadata.get('rerank_score', 0.0),
                }
            )

        context = '\n\n'.join(context_parts)

        # Generate answer
        prompt = ChatPromptTemplate.from_template(
            """Answer the question based on the provided context. Include relevant details and cite sources by number [Source N].

Context:
{context}

Question: {query}

Answer:"""
        )

        chain = prompt | self.llm_client | StrOutputParser()
        answer = chain.invoke({'context': context, 'query': state['query']})

        return {
            'answer': answer,
            'sources': sources,
        }

    def _check_hallucination(self, state: AgenticRAGState) -> dict[str, Any]:
        """Check if answer is grounded in retrieved documents."""
        if callback := state.get('progress_callback'):
            callback('hallucination_check', 'Verifying accuracy...')

        # Check if hallucination checking is enabled
        if not state['config'].get('hallucination_check_enabled', True):
            return {
                'is_grounded': True,
                'grounding_explanation': 'Hallucination check disabled',
            }

        # Skip check for direct answers (no retrieval)
        if state['query_type'] == QueryType.DIRECT_ANSWER.value:
            return {
                'is_grounded': True,
                'grounding_explanation': 'Direct answer without retrieval',
            }

        # Check groundedness
        try:
            is_grounded, explanation = asyncio.run(
                self.hallucination_checker.check_answer_async(
                    state['query'], state['answer'], state['graded_documents']
                )
            )
            logger.debug(f'Hallucination check: {is_grounded} - {explanation[:100]}')
        except Exception as e:
            logger.error(f'Hallucination check failed: {e}')
            # Fail open - assume grounded
            is_grounded = True
            explanation = f'Check failed: {e!s}'

        return {
            'is_grounded': is_grounded,
            'grounding_explanation': explanation,
        }

    # --- Routing Functions ---

    def _route_after_classification(
        self, state: AgenticRAGState
    ) -> Literal['expand', 'decompose', 'direct_answer']:
        """Route after query classification."""
        query_type = state['query_type']

        if query_type == QueryType.DIRECT_ANSWER.value:
            return 'direct_answer'
        elif query_type == QueryType.MULTI_HOP_RAG.value:
            return 'decompose'
        else:
            return 'expand'

    def _route_after_grading(
        self, state: AgenticRAGState
    ) -> Literal['rerank', 'rewrite', 'end']:
        """Route after document grading."""
        confidence = state['confidence']
        retry_count = state['retry_count']
        max_retries = state['max_retries']
        threshold = state['config'].get('confidence_threshold', 0.5)

        # If no documents at all, end (avoid infinite loop)
        if not state['graded_documents']:
            if retry_count >= max_retries:
                logger.warning('No relevant documents found after max retries')
                return 'end'
            else:
                return 'rewrite'

        # If confidence too low and retries remaining, rewrite
        if confidence < threshold and retry_count < max_retries:
            logger.info(
                f'Low confidence ({confidence:.2f} < {threshold}), rewriting query'
            )
            return 'rewrite'

        # Otherwise proceed to reranking
        return 'rerank'

    def _route_after_hallucination_check(
        self, state: AgenticRAGState
    ) -> Literal['accept', 'retry', 'end']:
        """Route after hallucination check."""
        is_grounded = state['is_grounded']
        retry_count = state['retry_count']
        max_retries = state['max_retries']

        # If grounded, accept answer
        if is_grounded:
            return 'accept'

        # If hallucination detected and retries remaining, retry
        if retry_count < max_retries:
            logger.warning('Hallucination detected, rewriting query')
            return 'retry'

        # Max retries reached, accept anyway with warning
        logger.warning(
            'Hallucination detected but max retries reached, accepting answer'
        )
        return 'end'

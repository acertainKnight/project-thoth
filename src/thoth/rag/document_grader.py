"""
Document relevance grading for agentic RAG.

Provides LLM-based binary relevance grading to filter retrieved documents
before generation, improving answer quality and reducing hallucination risk.
"""

import asyncio
from enum import Enum
from typing import Any

from langchain_core.documents import Document
from loguru import logger


class RetrievalConfidence(Enum):
    """
    Tri-level retrieval confidence assessment (CRAG).

    Based on the CRAG paper: uses two thresholds to classify retrieval
    quality into three levels that determine corrective actions.
    """

    CORRECT = 'correct'  # High confidence, use local retrieval
    AMBIGUOUS = 'ambiguous'  # Mixed results, supplement with web search
    INCORRECT = 'incorrect'  # Low confidence, use web search instead


class DocumentGrader:
    """
    LLM-based document relevance grader.

    Scores each retrieved document's relevance to the query using binary
    yes/no grading. Faster and more cost-effective than scoring-based
    approaches while maintaining high accuracy.
    """

    def __init__(
        self,
        llm_client: Any,
        threshold: float = 0.5,
        batch_size: int = 10,
    ):
        """
        Initialize document grader.

        Args:
            llm_client: LLM client for grading
            threshold: Minimum confidence threshold (0-1) for relevance
            batch_size: Number of documents to grade in parallel
        """
        self.llm_client = llm_client
        self.threshold = threshold
        self.batch_size = batch_size
        logger.info(f'Initialized DocumentGrader (threshold={threshold})')

    async def grade_documents_async(
        self, query: str, documents: list[Document]
    ) -> tuple[list[Document], list[Document]]:
        """
        Grade documents for relevance to query (async).

        Uses LLM to perform binary yes/no relevance grading. Documents
        are graded in parallel batches for efficiency.

        Args:
            query: Search query
            documents: Retrieved documents to grade

        Returns:
            Tuple of (relevant_documents, irrelevant_documents)

        Example:
            >>> relevant, irrelevant = await grader.grade_documents_async(
            ...     'What are transformer architectures?', retrieved_docs
            ... )
            >>> print(f'Kept {len(relevant)}/{len(documents)} relevant docs')
        """
        if not documents:
            return [], []

        logger.debug(f'Grading {len(documents)} documents for query: {query[:100]}')

        # Grade documents in parallel batches
        grading_tasks = [self._grade_single_document(query, doc) for doc in documents]

        try:
            grades = await asyncio.gather(*grading_tasks, return_exceptions=True)

            # Separate relevant and irrelevant documents
            relevant = []
            irrelevant = []

            for doc, grade in zip(documents, grades):  # noqa: B905
                if isinstance(grade, Exception):
                    logger.warning(f'Document grading failed: {grade}')
                    # On error, assume relevant (fail open)
                    grade = 'yes'

                # Add grading metadata
                doc.metadata['grading_result'] = grade
                doc.metadata['is_relevant'] = grade == 'yes'

                if grade == 'yes':
                    relevant.append(doc)
                else:
                    irrelevant.append(doc)

            logger.info(
                f'Grading complete: {len(relevant)} relevant, '
                f'{len(irrelevant)} irrelevant ({len(relevant) / len(documents) * 100:.1f}% pass rate)'
            )

            return relevant, irrelevant

        except Exception as e:
            logger.error(f'Document grading batch failed: {e}')
            # On batch failure, return all documents as relevant (fail open)
            return documents, []

    def grade_documents(
        self, query: str, documents: list[Document]
    ) -> tuple[list[Document], list[Document]]:
        """
        Grade documents for relevance to query (sync wrapper).

        Args:
            query: Search query
            documents: Retrieved documents to grade

        Returns:
            Tuple of (relevant_documents, irrelevant_documents)
        """
        try:
            asyncio.get_running_loop()
            raise RuntimeError(
                'grade_documents() called from async context. '
                'Use await grade_documents_async() instead.'
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                return asyncio.run(self.grade_documents_async(query, documents))
            else:
                raise

    async def _grade_single_document(self, query: str, document: Document) -> str:
        """
        Grade a single document's relevance to query using LLM.

        Uses a binary yes/no prompt to minimize latency and improve
        consistency. The prompt asks for ONLY 'yes' or 'no' to avoid
        verbose explanations that slow down processing.

        Args:
            query: Search query
            document: Document to grade

        Returns:
            'yes' if relevant, 'no' if irrelevant
        """
        # Truncate document to avoid context overflow (keep first 800 chars)
        content = document.page_content[:800]

        # Get document title/source if available for context
        doc_info = ''
        if title := document.metadata.get('title'):
            doc_info = f'Title: {title}\n'
        if authors := document.metadata.get('authors'):
            doc_info += f'Authors: {authors}\n'

        prompt = f"""Is this document relevant to answering the query? Answer ONLY 'yes' or 'no'.

Query: {query}

{doc_info}Document Content:
{content}

Relevant (yes/no):"""

        try:
            response = await asyncio.to_thread(self.llm_client.invoke, prompt)

            # Parse yes/no response
            result = response.content.strip().lower()

            # Extract yes/no (handles "yes.", "Yes", "no.", etc.)
            if 'yes' in result[:10]:  # Check first 10 chars only
                return 'yes'
            elif 'no' in result[:10]:
                return 'no'
            else:
                # If unclear, default to yes (fail open)
                logger.warning(
                    f'Unclear grading response: {result[:50]}, defaulting to yes'
                )
                return 'yes'

        except Exception as e:
            logger.error(f'Document grading error: {e}')
            # On error, assume relevant (fail open)
            return 'yes'

    async def filter_by_confidence_async(
        self, documents: list[Document]
    ) -> list[Document]:
        """
        Filter documents by pre-existing confidence/relevance scores.

        Useful when documents already have rerank_score or similarity
        scores attached. Filters based on configured threshold.

        Args:
            documents: Documents with scores in metadata

        Returns:
            Documents passing confidence threshold
        """
        if not documents:
            return []

        filtered = []
        for doc in documents:
            # Try rerank score first, fall back to similarity
            score = doc.metadata.get('rerank_score') or doc.metadata.get(
                'similarity', 0.0
            )

            if score >= self.threshold:
                filtered.append(doc)

        logger.debug(
            f'Confidence filter: {len(filtered)}/{len(documents)} docs passed '
            f'(threshold={self.threshold})'
        )

        return filtered

    def evaluate_retrieval_confidence(
        self,
        confidence: float,
        upper_threshold: float = 0.7,
        lower_threshold: float = 0.4,
    ) -> RetrievalConfidence:
        """
        Evaluate retrieval quality using tri-level CRAG assessment.

        Uses two thresholds to classify retrieval into three levels:
        - CORRECT: confidence >= upper_threshold (strong coverage)
        - AMBIGUOUS: lower_threshold <= confidence < upper_threshold (partial coverage)
        - INCORRECT: confidence < lower_threshold (weak coverage)

        Args:
            confidence: Document grading confidence score (0-1)
            upper_threshold: Threshold for CORRECT assessment (default 0.7)
            lower_threshold: Threshold for INCORRECT assessment (default 0.4)

        Returns:
            RetrievalConfidence level (CORRECT/AMBIGUOUS/INCORRECT)

        Example:
            >>> assessment = grader.evaluate_retrieval_confidence(0.52)
            >>> if assessment == RetrievalConfidence.AMBIGUOUS:
            ...     # Supplement with web search
        """
        if confidence >= upper_threshold:
            return RetrievalConfidence.CORRECT
        elif confidence >= lower_threshold:
            return RetrievalConfidence.AMBIGUOUS
        else:
            return RetrievalConfidence.INCORRECT

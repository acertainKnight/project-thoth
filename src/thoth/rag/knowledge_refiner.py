"""
Knowledge strip decomposition and refinement (CRAG).

Implements the knowledge refinement strategy from the CRAG paper:
decomposes documents into fine-grained factual statements (knowledge strips),
filters for relevance, and recomposes into refined documents with less noise.
"""

import asyncio
from typing import Any

from langchain_core.documents import Document
from loguru import logger


class KnowledgeRefiner:
    """
    Decompose-then-recompose knowledge refinement per CRAG paper.

    For each retrieved document chunk:
    1. Decompose into individual factual statements (knowledge strips)
    2. Score each strip for relevance to the query
    3. Filter to only relevant strips
    4. Recompose into a refined document

    This reduces noise in the context passed to generation, improving
    answer quality and reducing hallucination risk.
    """

    def __init__(
        self,
        llm_client: Any,
        max_strips_per_document: int = 20,
        batch_size: int = 10,
    ):
        """
        Initialize knowledge refiner.

        Args:
            llm_client: LLM client for decomposition and filtering
            max_strips_per_document: Max strips to extract per document
            batch_size: Number of strips to grade in parallel
        """
        self.llm_client = llm_client
        self.max_strips_per_document = max_strips_per_document
        self.batch_size = batch_size
        logger.info(
            f'Initialized KnowledgeRefiner (max_strips={max_strips_per_document})'
        )

    async def refine_documents_async(
        self, query: str, documents: list[Document]
    ) -> list[Document]:
        """
        Refine documents via knowledge strip decomposition and filtering.

        Args:
            query: User query for relevance filtering
            documents: Retrieved documents to refine

        Returns:
            Refined documents with only relevant knowledge strips

        Example:
            >>> refined = await refiner.refine_documents_async(
            ...     'What are transformer architectures?', retrieved_docs
            ... )
            >>> # Each refined doc contains only relevant factual statements
        """
        if not documents:
            return []

        logger.debug(f'Refining {len(documents)} documents for query: {query[:100]}')

        refined_docs = []
        for doc in documents:
            try:
                refined = await self._refine_single_document(query, doc)
                if refined:
                    refined_docs.append(refined)
            except Exception as e:
                logger.warning(f'Document refinement failed: {e}, using original')
                refined_docs.append(doc)

        logger.info(
            f'Refined {len(documents)} documents to {len(refined_docs)} results'
        )
        return refined_docs

    async def _refine_single_document(
        self, query: str, document: Document
    ) -> Document | None:
        """
        Refine a single document via strip decomposition.

        Args:
            query: User query
            document: Document to refine

        Returns:
            Refined document or None if no relevant strips found
        """
        # Step 1: Decompose into knowledge strips
        strips = await self._decompose_to_strips(document)

        if not strips:
            logger.debug('No strips extracted, returning original document')
            return document

        # Step 2: Filter strips for relevance
        relevant_strips = await self._filter_strips(query, strips)

        if not relevant_strips:
            logger.debug('No relevant strips found, filtering out document')
            return None

        # Step 3: Recompose into refined document
        refined_content = '\n\n'.join(relevant_strips)

        # Create new document with refined content and preserved metadata
        refined_doc = Document(
            page_content=refined_content,
            metadata={
                **document.metadata,
                'refined': True,
                'original_length': len(document.page_content),
                'refined_length': len(refined_content),
                'num_strips_original': len(strips),
                'num_strips_relevant': len(relevant_strips),
            },
        )

        return refined_doc

    async def _decompose_to_strips(self, document: Document) -> list[str]:
        """
        Decompose document into individual factual statements.

        Args:
            document: Document to decompose

        Returns:
            List of knowledge strips (factual statements)
        """
        content = document.page_content

        # Skip very short documents
        if len(content) < 50:
            return [content]

        prompt = f"""Break this text into individual factual statements. Each statement should be:
- Self-contained (understandable without other statements)
- Factual (not opinions or questions)
- Concise (one claim per statement)

Output ONLY the factual statements, one per line. No numbering, no explanations.

Text:
{content[:2000]}

Factual statements:"""

        try:
            response = await asyncio.to_thread(self.llm_client.invoke, prompt)

            # Parse statements (one per line)
            strips = [
                line.strip()
                for line in response.content.strip().split('\n')
                if line.strip() and len(line.strip()) > 10
            ]

            # Remove numbering if present (1., 2., etc.)
            import re

            strips = [re.sub(r'^\d+[\.)]\s*', '', s) for s in strips]

            # Limit to max_strips_per_document
            strips = strips[: self.max_strips_per_document]

            logger.debug(f'Decomposed document into {len(strips)} knowledge strips')
            return strips

        except Exception as e:
            logger.error(f'Strip decomposition failed: {e}')
            return [content]

    async def _filter_strips(self, query: str, strips: list[str]) -> list[str]:
        """
        Filter knowledge strips for relevance to query.

        Args:
            query: User query
            strips: Knowledge strips to filter

        Returns:
            List of relevant strips
        """
        if not strips:
            return []

        logger.debug(f'Filtering {len(strips)} strips for query: {query[:100]}')

        # Grade strips in parallel
        grading_tasks = [self._grade_strip(query, strip) for strip in strips]

        try:
            grades = await asyncio.gather(*grading_tasks, return_exceptions=True)

            relevant_strips = []
            for strip, grade in zip(strips, grades, strict=True):
                if isinstance(grade, Exception):
                    logger.warning(f'Strip grading failed: {grade}')
                    # On error, assume relevant (fail open)
                    grade = 'yes'

                if grade == 'yes':
                    relevant_strips.append(strip)

            logger.debug(
                f'Strip filtering: {len(relevant_strips)}/{len(strips)} relevant '
                f'({len(relevant_strips) / len(strips) * 100:.1f}% pass rate)'
            )

            return relevant_strips

        except Exception as e:
            logger.error(f'Strip filtering batch failed: {e}')
            # On batch failure, return all strips (fail open)
            return strips

    async def _grade_strip(self, query: str, strip: str) -> str:
        """
        Grade a single knowledge strip for relevance.

        Args:
            query: User query
            strip: Knowledge strip to grade

        Returns:
            'yes' if relevant, 'no' if irrelevant
        """
        prompt = f"""Is this statement relevant to answering the query? Answer ONLY 'yes' or 'no'.

Query: {query}

Statement: {strip}

Relevant (yes/no):"""

        try:
            response = await asyncio.to_thread(self.llm_client.invoke, prompt)

            result = response.content.strip().lower()

            # Extract yes/no
            if 'yes' in result[:10]:
                return 'yes'
            elif 'no' in result[:10]:
                return 'no'
            else:
                # Default to yes if unclear (fail open)
                return 'yes'

        except Exception as e:
            logger.error(f'Strip grading error: {e}')
            # On error, assume relevant (fail open)
            return 'yes'

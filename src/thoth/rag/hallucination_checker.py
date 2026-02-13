"""
Hallucination detection for RAG-generated answers.

Verifies that generated answers are grounded in retrieved documents,
preventing the model from generating unsupported claims or hallucinations.
"""

import asyncio
from typing import Any

from langchain_core.documents import Document
from loguru import logger


class HallucinationChecker:
    """
    LLM-based hallucination detector for RAG answers.

    Verifies that every claim in a generated answer is supported by
    the retrieved documents. Acts as a post-generation quality gate
    in agentic RAG pipelines.
    """

    def __init__(self, llm_client: Any, strict_mode: bool = False):
        """
        Initialize hallucination checker.

        Args:
            llm_client: LLM client for verification
            strict_mode: If True, reject answers with ANY unsupported claims.
                        If False, allow minor unsupported claims (more lenient)
        """
        self.llm_client = llm_client
        self.strict_mode = strict_mode
        logger.info(f'Initialized HallucinationChecker (strict_mode={strict_mode})')

    async def check_answer_async(
        self, query: str, answer: str, source_documents: list[Document]
    ) -> tuple[bool, str]:
        """
        Check if answer is grounded in source documents (async).

        Args:
            query: Original user query
            answer: Generated answer to verify
            source_documents: Retrieved documents used for generation

        Returns:
            Tuple of (is_grounded, explanation)
            - is_grounded: True if answer is supported by documents
            - explanation: Reasoning for the verdict

        Example:
            >>> is_grounded, reason = await checker.check_answer_async(
            ...     'What is a transformer?',
            ...     'Transformers use attention mechanisms...',
            ...     retrieved_docs,
            ... )
            >>> if not is_grounded:
            ...     print(f'Hallucination detected: {reason}')
        """
        if not answer or not answer.strip():
            return True, 'Empty answer, no claims to verify'

        if not source_documents:
            logger.warning('No source documents provided for hallucination check')
            # If no docs, answer must be unsupported
            return False, 'No source documents provided'

        logger.debug(f'Checking answer groundedness for query: {query[:100]}')

        # Combine source documents (truncate to avoid context overflow)
        combined_sources = self._combine_sources(source_documents, max_chars=3000)

        prompt = self._build_verification_prompt(query, answer, combined_sources)

        try:
            response = await asyncio.to_thread(self.llm_client.invoke, prompt)

            # Parse verdict
            result = response.content.strip()
            verdict_lower = result.lower()

            # Check for explicit yes/no
            if verdict_lower.startswith('yes'):
                logger.debug('Answer verified as grounded')
                return True, result
            elif verdict_lower.startswith('no'):
                logger.warning(f'Hallucination detected: {result[:200]}')
                return False, result
            else:
                # If unclear, parse for keywords
                # Look for strong negative indicators
                negative_indicators = [
                    'not supported',
                    'not grounded',
                    'hallucination',
                    'fabricated',
                    'unsupported claim',
                    'no evidence',
                ]

                has_negative = any(ind in verdict_lower for ind in negative_indicators)

                if has_negative:
                    logger.warning(f'Potential hallucination: {result[:200]}')
                    return False, result
                else:
                    # Default to grounded if unclear (fail open)
                    logger.debug(
                        f'Unclear verdict (defaulting to grounded): {result[:100]}'
                    )
                    return True, result

        except Exception as e:
            logger.error(f'Hallucination check failed: {e}')
            # On error, assume grounded (fail open)
            return True, f'Check failed due to error: {e!s}'

    def check_answer(
        self, query: str, answer: str, source_documents: list[Document]
    ) -> tuple[bool, str]:
        """
        Check if answer is grounded in source documents (sync wrapper).

        Args:
            query: Original user query
            answer: Generated answer to verify
            source_documents: Retrieved documents used for generation

        Returns:
            Tuple of (is_grounded, explanation)
        """
        try:
            asyncio.get_running_loop()
            raise RuntimeError(
                'check_answer() called from async context. '
                'Use await check_answer_async() instead.'
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                return asyncio.run(
                    self.check_answer_async(query, answer, source_documents)
                )
            else:
                raise

    def _combine_sources(self, documents: list[Document], max_chars: int = 3000) -> str:
        """
        Combine source documents into a single context string.

        Args:
            documents: Source documents
            max_chars: Maximum total character length

        Returns:
            Combined source text
        """
        combined = []
        total_chars = 0

        for i, doc in enumerate(documents):
            # Add document header
            title = doc.metadata.get('title', f'Document {i + 1}')
            header = f'[Source {i + 1}: {title}]\n'

            # Calculate space remaining
            remaining = max_chars - total_chars - len(header)
            if remaining <= 100:
                break  # Stop if less than 100 chars remaining

            # Add truncated content
            content = doc.page_content[:remaining]
            combined.append(f'{header}{content}\n')
            total_chars += len(header) + len(content)

        return '\n'.join(combined)

    def _build_verification_prompt(self, query: str, answer: str, sources: str) -> str:
        """
        Build verification prompt for hallucination checking.

        Args:
            query: Original query
            answer: Generated answer
            sources: Combined source documents

        Returns:
            Verification prompt
        """
        if self.strict_mode:
            instruction = """Verify that EVERY claim in the answer is directly supported by the source documents.
Answer 'yes' ONLY if all claims are fully supported. Answer 'no' if ANY claim lacks support."""
        else:
            instruction = """Verify that the core claims in the answer are supported by the source documents.
Minor contextual additions are acceptable. Answer 'yes' if the answer is substantially grounded.
Answer 'no' if there are major unsupported claims or factual errors."""

        prompt = f"""{instruction}

Query: {query}

Answer to Verify:
{answer}

Source Documents:
{sources}

Is the answer grounded in the source documents? Answer 'yes' or 'no' and briefly explain:"""

        return prompt

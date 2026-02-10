"""
Contextual retrieval enrichment for RAG systems.

Implements Anthropic's contextual retrieval technique: prepending LLM-generated
context to chunks before embedding to improve retrieval accuracy.

Reference: https://www.anthropic.com/news/contextual-retrieval
"""

import asyncio
from typing import Any

from langchain_core.documents import Document
from loguru import logger


class ContextualEnricher:
    """
    Enriches document chunks with contextual information.

    Uses an LLM to generate a brief context that situates each chunk within
    the overall document, improving retrieval by addressing the "lost context"
    problem when chunks are embedded independently.
    """

    def __init__(
        self,
        llm_client: Any,
        model: str | None = None,
        max_doc_tokens: int = 1000,
        batch_size: int = 10,
        enabled: bool = True,
    ):
        """
        Initialize contextual enricher.

        Args:
            llm_client: LLM client for generating context
            model: Model to use (None = use client default)
            max_doc_tokens: Maximum document tokens to include in prompt
            batch_size: Number of chunks to process in parallel
            enabled: Whether enrichment is enabled
        """
        self.llm_client = llm_client
        # OpenRouterClient stores model as model_name (inherits from ChatOpenAI)
        self.model = model or getattr(
            llm_client, 'model_name', getattr(llm_client, 'model', 'unknown')
        )
        self.max_doc_tokens = max_doc_tokens
        self.batch_size = batch_size
        self.enabled = enabled

        logger.info(
            f'Initialized ContextualEnricher '
            f'(model={self.model}, enabled={self.enabled})'
        )

    async def enrich_chunks_async(
        self,
        chunks: list[Document],
        document_text: str,
        document_title: str | None = None,
    ) -> list[Document]:
        """
        Enrich chunks with contextual information (async).

        For each chunk, generates a brief context using the LLM and prepends
        it to the chunk text before embedding.

        Args:
            chunks: List of document chunks
            document_text: Full document text (will be truncated if too long)
            document_title: Optional document title for better context

        Returns:
            Enriched chunks with context prepended
        """
        if not self.enabled or not chunks:
            return chunks

        logger.debug(f'Enriching {len(chunks)} chunks with contextual information')

        # Truncate document for prompt
        doc_excerpt = self._truncate_document(document_text)

        # Process chunks in batches
        enriched_chunks = []
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]

            # Enrich batch in parallel
            enrichment_tasks = [
                self._enrich_single_chunk(chunk, doc_excerpt, document_title)
                for chunk in batch
            ]

            try:
                enriched_batch = await asyncio.gather(
                    *enrichment_tasks, return_exceptions=True
                )

                # Handle any errors
                for orig_chunk, enriched in zip(batch, enriched_batch):  # noqa: B905
                    if isinstance(enriched, Exception):
                        logger.warning(f'Enrichment failed for chunk: {enriched}')
                        # Use original chunk if enrichment fails
                        enriched_chunks.append(orig_chunk)
                    else:
                        enriched_chunks.append(enriched)

            except Exception as e:
                logger.error(f'Batch enrichment failed: {e}')
                # Fall back to original chunks for this batch
                enriched_chunks.extend(batch)

        logger.info(
            f'Successfully enriched {len(enriched_chunks)}/{len(chunks)} chunks'
        )
        return enriched_chunks

    def enrich_chunks(
        self,
        chunks: list[Document],
        document_text: str,
        document_title: str | None = None,
    ) -> list[Document]:
        """
        Enrich chunks with contextual information (sync wrapper).

        Args:
            chunks: List of document chunks
            document_text: Full document text
            document_title: Optional document title

        Returns:
            Enriched chunks
        """
        try:
            asyncio.get_running_loop()
            raise RuntimeError(
                'enrich_chunks() called from async context. '
                'Use await enrich_chunks_async() instead.'
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                return asyncio.run(
                    self.enrich_chunks_async(chunks, document_text, document_title)
                )
            else:
                raise

    async def _enrich_single_chunk(
        self,
        chunk: Document,
        document_excerpt: str,
        document_title: str | None,
    ) -> Document:
        """
        Enrich a single chunk with contextual information.

        Args:
            chunk: Document chunk to enrich
            document_excerpt: Excerpt of full document for context
            document_title: Optional document title

        Returns:
            Enriched document chunk
        """
        # Build prompt for contextual enrichment
        prompt = self._build_enrichment_prompt(
            chunk.page_content, document_excerpt, document_title
        )

        try:
            # Generate context using LLM
            response = await asyncio.to_thread(self.llm_client.invoke, prompt)

            context = response.content.strip()

            # Validate context (should be 1-3 sentences)
            if len(context) > 500:  # Sanity check
                logger.warning('Generated context too long, truncating')
                context = context[:500] + '...'

            # Create enriched chunk
            enriched_content = f'{context}\n\n{chunk.page_content}'

            # Copy metadata and add enrichment info
            enriched_metadata = dict(chunk.metadata)
            enriched_metadata['enriched'] = True
            enriched_metadata['context'] = context
            enriched_metadata['original_content'] = chunk.page_content

            return Document(page_content=enriched_content, metadata=enriched_metadata)

        except Exception as e:
            logger.error(f'Context generation failed: {e}')
            # Return original chunk on error
            return chunk

    def _build_enrichment_prompt(
        self,
        chunk_text: str,
        document_excerpt: str,
        document_title: str | None,
    ) -> str:
        """
        Build prompt for contextual enrichment.

        Args:
            chunk_text: Chunk text to enrich
            document_excerpt: Document excerpt for context
            document_title: Optional document title

        Returns:
            Prompt string
        """
        title_part = f'\nDocument Title: {document_title}\n' if document_title else ''

        prompt = f"""You are an expert at providing context for document chunks to improve search retrieval.

Given a chunk from a document, provide a brief context (1-2 sentences) that situates this chunk within the overall document. The context should help someone searching for this information find it more easily.

Be concise and specific. Focus on what makes this chunk unique or where it fits in the document structure.
{title_part}
Document Excerpt:
{document_excerpt}

Chunk to Contextualize:
{chunk_text}

Brief Context (1-2 sentences):"""

        return prompt

    def _truncate_document(self, document_text: str) -> str:
        """
        Truncate document to fit within token limit.

        Takes first portion of document up to max_doc_tokens.

        Args:
            document_text: Full document text

        Returns:
            Truncated document text
        """
        # Rough token estimation: 1 token ≈ 4 characters
        max_chars = self.max_doc_tokens * 4

        if len(document_text) <= max_chars:
            return document_text

        # Truncate and add indicator
        truncated = document_text[:max_chars]

        # Try to end at a sentence boundary
        last_period = truncated.rfind('. ')
        if last_period > max_chars * 0.8:  # If we can keep 80%+, do it
            truncated = truncated[: last_period + 1]

        return truncated + '\n\n[Document truncated for context generation]'

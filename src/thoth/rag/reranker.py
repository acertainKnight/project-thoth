"""
Reranking strategies for RAG retrieval.

Provides pluggable rerankers to refine initial retrieval results:
- CohereReranker: Production-grade reranking via Cohere API
- LLMReranker: Zero-cost reranking using existing OpenRouter LLMs
- NoOpReranker: Passthrough when reranking is disabled
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.documents import Document
from loguru import logger


class BaseReranker(ABC):
    """
    Abstract base class for document rerankers.

    Rerankers take initial retrieval candidates and reorder them based on
    relevance to the query, typically achieving higher precision than
    the initial retrieval alone.
    """

    @abstractmethod
    async def rerank_async(
        self, query: str, documents: list[Document], top_n: int | None = None
    ) -> list[Document]:
        """
        Rerank documents by relevance to query (async).

        Args:
            query: Search query
            documents: Initial retrieval candidates
            top_n: Number of top results to return (None = return all)

        Returns:
            Documents reordered by relevance, limited to top_n if specified
        """
        pass

    def rerank(
        self, query: str, documents: list[Document], top_n: int | None = None
    ) -> list[Document]:
        """
        Rerank documents by relevance to query (sync wrapper).

        Args:
            query: Search query
            documents: Initial retrieval candidates
            top_n: Number of top results to return (None = return all)

        Returns:
            Documents reordered by relevance
        """
        try:
            asyncio.get_running_loop()
            raise RuntimeError(
                'rerank() called from async context. Use await rerank_async() instead.'
            )
        except RuntimeError as e:
            if 'no running event loop' in str(e).lower():
                return asyncio.run(self.rerank_async(query, documents, top_n))
            else:
                raise

    @abstractmethod
    def get_name(self) -> str:
        """Get reranker name for logging."""
        pass


class NoOpReranker(BaseReranker):
    """
    No-op passthrough reranker.

    Returns documents in original order. Used when reranking is disabled.
    """

    async def rerank_async(
        self,
        query: str,  # noqa: ARG002
        documents: list[Document],
        top_n: int | None = None,
    ) -> list[Document]:
        """Return documents unchanged, optionally limiting to top_n."""
        logger.debug('NoOp reranker: returning documents unchanged')
        if top_n is not None:
            return documents[:top_n]
        return documents

    def get_name(self) -> str:
        """Get reranker name."""
        return 'noop'


class CohereReranker(BaseReranker):
    """
    Cohere Rerank API-based reranker.

    Uses Cohere's production reranking models (rerank-v4.0-pro).
    Best quality but requires Cohere API key and incurs costs ($0.05/1M tokens).
    """

    def __init__(self, api_key: str, model: str = 'rerank-v3.5'):
        """
        Initialize Cohere reranker.

        Args:
            api_key: Cohere API key
            model: Reranker model name (default: rerank-v3.5)
        """
        self.api_key = api_key
        self.model = model

        # Lazy import to avoid requiring cohere as dependency
        try:
            import cohere

            self.client = cohere.AsyncClient(api_key=api_key)
            logger.info(f'Initialized CohereReranker with model={model}')
        except ImportError:
            logger.error(
                'Cohere package not installed. Install with: pip install cohere>=5.0'
            )
            raise

    async def rerank_async(
        self, query: str, documents: list[Document], top_n: int | None = None
    ) -> list[Document]:
        """
        Rerank documents using Cohere Rerank API.

        Args:
            query: Search query
            documents: Initial candidates
            top_n: Number of results to return

        Returns:
            Reranked documents
        """
        if not documents:
            return []

        # Prepare documents for Cohere API
        # Cohere expects list of strings or dicts with 'text' key
        doc_texts = [doc.page_content for doc in documents]

        try:
            # Call Cohere Rerank API
            response = await self.client.rerank(
                query=query,
                documents=doc_texts,
                model=self.model,
                top_n=top_n or len(documents),
            )

            # Reorder documents based on Cohere ranking
            reranked = []
            for result in response.results:
                idx = result.index
                doc = documents[idx]

                # Add reranking score to metadata
                doc.metadata['rerank_score'] = result.relevance_score
                doc.metadata['rerank_model'] = self.model

                reranked.append(doc)

            logger.debug(
                f'Cohere reranked {len(documents)} -> {len(reranked)} documents'
            )
            return reranked

        except Exception as e:
            logger.error(f'Cohere reranking failed: {e}')
            # Fallback: return original order
            return documents[:top_n] if top_n else documents

    def get_name(self) -> str:
        """Get reranker name."""
        return f'cohere-{self.model}'


class LLMReranker(BaseReranker):
    """
    LLM-based pointwise reranking.

    Uses an existing LLM (via OpenRouterClient) to score each document's
    relevance to the query. Zero-cost approach using models you already pay for.

    Quality: ~70-80% of dedicated reranker, but with no additional API costs.
    """

    def __init__(
        self,
        llm_client: Any,
        model: str | None = None,
        temperature: float = 0.0,
    ):
        """
        Initialize LLM reranker.

        Args:
            llm_client: OpenRouterClient or compatible LLM client
            model: Optional model override (uses client's default if None)
            temperature: Temperature for scoring (0.0 for deterministic)
        """
        self.llm_client = llm_client
        # OpenRouterClient stores model as model_name (inherits from ChatOpenAI)
        self.model = model or getattr(
            llm_client, 'model_name', getattr(llm_client, 'model', 'unknown')
        )
        self.temperature = temperature
        logger.info(f'Initialized LLMReranker with model={self.model}')

    async def rerank_async(
        self, query: str, documents: list[Document], top_n: int | None = None
    ) -> list[Document]:
        """
        Rerank documents using LLM-based relevance scoring.

        Sends each document through an LLM with a relevance scoring prompt.
        Scores in parallel using asyncio.gather for speed.

        Args:
            query: Search query
            documents: Initial candidates
            top_n: Number of results to return

        Returns:
            Documents reordered by LLM relevance scores
        """
        if not documents:
            return []

        # Score all documents in parallel
        scoring_tasks = [self._score_document(query, doc) for doc in documents]

        try:
            scores = await asyncio.gather(*scoring_tasks, return_exceptions=True)

            # Handle any errors in scoring
            doc_scores = []
            for doc, score in zip(documents, scores):  # noqa: B905
                if isinstance(score, Exception):
                    logger.warning(f'LLM scoring failed for doc: {score}')
                    # Use fallback score of 0.5
                    score = 0.5

                doc.metadata['rerank_score'] = score
                doc.metadata['rerank_model'] = self.model
                doc_scores.append((doc, score))

            # Sort by score descending
            doc_scores.sort(key=lambda x: x[1], reverse=True)
            reranked = [doc for doc, _ in doc_scores]

            logger.debug(
                f'LLM reranked {len(documents)} documents (top score: {doc_scores[0][1]:.3f})'
            )

            return reranked[:top_n] if top_n else reranked

        except Exception as e:
            logger.error(f'LLM reranking failed: {e}')
            # Fallback: return original order
            return documents[:top_n] if top_n else documents

    def get_name(self) -> str:
        """Get reranker name."""
        return f'llm-{self.model}'

    async def _score_document(self, query: str, document: Document) -> float:
        """
        Score a single document's relevance to query using LLM.

        Uses a pointwise relevance prompt that asks the LLM to rate
        relevance on a 0-1 scale.

        Args:
            query: Search query
            document: Document to score

        Returns:
            Relevance score (0.0-1.0)
        """
        # Truncate document if too long (keep first 500 chars)
        content = document.page_content[:500]

        prompt = f"""Rate how relevant this document is to the query on a scale from 0 to 1.
Output ONLY a number between 0 and 1, nothing else.

Query: {query}

Document: {content}

Relevance score (0-1):"""

        try:
            # Create a temporary client with temperature=0 for deterministic scoring
            response = await asyncio.to_thread(self.llm_client.invoke, prompt)

            # Extract score from response
            score_text = response.content.strip()

            # Try to parse as float
            try:
                score = float(score_text)
                # Clamp to 0-1 range
                score = max(0.0, min(1.0, score))
            except ValueError:
                # If parsing fails, try to extract first number
                import re

                matches = re.findall(r'0?\.\d+|[01]\.?\d*', score_text)
                if matches:
                    score = float(matches[0])
                    score = max(0.0, min(1.0, score))
                else:
                    logger.warning(f'Could not parse score from: {score_text}')
                    score = 0.5  # Default to neutral

            return score

        except Exception as e:
            logger.error(f'LLM scoring error: {e}')
            return 0.5  # Default to neutral on error


def create_reranker(
    provider: str,
    api_keys: dict[str, str],
    llm_client: Any = None,
    reranker_model: str = 'rerank-v3.5',
) -> BaseReranker:
    """
    Factory function to create appropriate reranker based on config.

    Auto-detection logic:
    1. If provider='cohere' and cohere_key is set -> CohereReranker
    2. If provider='llm' and llm_client provided -> LLMReranker
    3. If provider='auto':
       - Try Cohere if key available
       - Fall back to LLM if llm_client available
       - Fall back to NoOp if neither available
    4. If provider='none' -> NoOpReranker

    Args:
        provider: Reranker provider ('auto', 'cohere', 'llm', 'none')
        api_keys: Dict with API keys (must include 'cohere_key' if using Cohere)
        llm_client: OpenRouterClient for LLM-based reranking
        reranker_model: Model name for Cohere reranker

    Returns:
        BaseReranker instance
    """
    provider = provider.lower()

    # Explicit provider choices
    if provider == 'none':
        logger.info('Reranking disabled (provider=none)')
        return NoOpReranker()

    if provider == 'cohere':
        cohere_key = api_keys.get('cohere_key', '')
        if not cohere_key:
            logger.warning(
                'Cohere provider selected but no API key, falling back to NoOp'
            )
            return NoOpReranker()
        try:
            return CohereReranker(api_key=cohere_key, model=reranker_model)
        except ImportError:
            logger.warning('Cohere package not installed, falling back to LLM reranker')
            if llm_client:
                return LLMReranker(llm_client)
            return NoOpReranker()

    if provider == 'llm':
        if not llm_client:
            logger.warning(
                'LLM provider selected but no LLM client, falling back to NoOp'
            )
            return NoOpReranker()
        return LLMReranker(llm_client)

    # Auto-detection (provider='auto')
    if provider == 'auto':
        # Try Cohere first if key available
        cohere_key = api_keys.get('cohere_key', '')
        if cohere_key:
            try:
                logger.info('Auto-detected Cohere reranker (cohere_key present)')
                return CohereReranker(api_key=cohere_key, model=reranker_model)
            except ImportError:
                logger.warning('Cohere package not available, trying LLM reranker')

        # Fall back to LLM reranker
        if llm_client:
            logger.info('Auto-detected LLM reranker (OpenRouter available)')
            return LLMReranker(llm_client)

        # No reranking available
        logger.info('No reranker available, using NoOp (add cohere_key or llm_client)')
        return NoOpReranker()

    # Unknown provider
    logger.warning(f'Unknown reranker provider: {provider}, falling back to auto')
    return create_reranker('auto', api_keys, llm_client, reranker_model)

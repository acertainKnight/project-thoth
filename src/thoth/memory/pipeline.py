"""
Memory Pipeline Hooks

This module provides intelligent memory processing hooks for filtering,
enriching, and scoring memories before storage in the Letta memory system.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from loguru import logger


class SalienceScorer:
    """
    Calculate salience scores for memories to determine importance and retention.

    Higher scores indicate more important memories that should be retained longer.
    Score range: 0.0 (lowest) to 1.0 (highest)
    """

    def __init__(self):
        """Initialize the salience scorer with scoring criteria."""
        # Research-focused keywords get higher scores
        self.research_keywords = {
            'methodology',
            'findings',
            'results',
            'conclusion',
            'hypothesis',
            'experiment',
            'analysis',
            'discovery',
            'breakthrough',
            'novel',
            'significant',
            'important',
            'key',
            'critical',
            'essential',
            'arxiv',
            'paper',
            'study',
            'research',
            'publication',
            'journal',
            'doi',
            'citation',
            'author',
            'abstract',
            'introduction',
        }

        # Question words indicate important user interests
        self.question_indicators = {
            'what',
            'how',
            'why',
            'when',
            'where',
            'which',
            'who',
            'explain',
            'describe',
            'analyze',
            'compare',
            'evaluate',
        }

        # Action words suggest executable tasks
        self.action_keywords = {
            'create',
            'build',
            'generate',
            'analyze',
            'search',
            'find',
            'locate',
            'download',
            'process',
            'extract',
            'summarize',
        }

    def calculate_salience(
        self,
        content: str,
        role: str,
        metadata: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> float:
        """
        Calculate salience score for a memory entry.

        Args:
            content: Memory content text
            role: Message role (user, assistant, system)
            metadata: Additional metadata about the memory
            user_context: User context and preferences

        Returns:
            float: Salience score between 0.0 and 1.0
        """
        try:
            score = 0.0
            content_lower = content.lower()

            # Base score by role
            if role == 'user':
                score += 0.3  # User messages generally important
            elif role == 'assistant':
                score += 0.2  # Assistant responses moderately important
            elif role == 'system':
                score += 0.1  # System messages less important

            # Content length factor (moderate length preferred)
            length = len(content)
            if 20 <= length <= 500:
                score += 0.1
            elif 500 < length <= 1000:
                score += 0.05
            elif length > 2000:
                score -= 0.1  # Very long content may be less focused

            # Research keyword detection
            research_matches = sum(
                1 for keyword in self.research_keywords if keyword in content_lower
            )
            score += min(research_matches * 0.05, 0.2)  # Cap at 0.2

            # Question detection (indicates user interest)
            if any(q in content_lower for q in self.question_indicators):
                score += 0.15

            # Action keyword detection
            action_matches = sum(
                1 for keyword in self.action_keywords if keyword in content_lower
            )
            score += min(action_matches * 0.03, 0.1)  # Cap at 0.1

            # DOI or arXiv ID detection (academic content)
            if re.search(r'10\.\d+\/[\w\-\._]+|arXiv:\d+\.\d+', content):
                score += 0.15

            # URL detection (external references)
            if re.search(r'https?:\/\/[^\s]+', content):
                score += 0.05

            # Metadata-based scoring
            if metadata:
                # Tool calls indicate actionable content
                if metadata.get('tool_calls'):
                    score += 0.1

                # Error or failure states may be less important
                if metadata.get('error') or 'error' in content_lower:
                    score -= 0.1

                # Agent-specific metadata
                if metadata.get('agent_id'):
                    score += 0.05

            # User context considerations
            if user_context:
                # Recent activity indicates higher relevance
                last_activity = user_context.get('last_activity')
                if last_activity:
                    # Boost score for recent interactions
                    score += 0.05

                # User preferences
                preferences = user_context.get('preferences', {})
                focus_areas = preferences.get('research_focus', [])
                if focus_areas:
                    for area in focus_areas:
                        if area.lower() in content_lower:
                            score += 0.1
                            break

            # Normalize score to [0.0, 1.0] range
            final_score = max(0.0, min(1.0, score))

            logger.debug(
                f'Calculated salience score: {final_score:.3f} for {role} message'
            )
            return final_score

        except Exception as e:
            logger.error(f'Error calculating salience: {e}')
            # Return moderate score on error
            return 0.5


class MemoryFilter:
    """
    Filter memories based on various criteria before storage.
    """

    def __init__(self, min_salience: float = 0.1):
        """
        Initialize memory filter.

        Args:
            min_salience: Minimum salience score to retain memory
        """
        self.min_salience = min_salience

        # Content patterns to filter out
        self.noise_patterns = [
            r'^(ok|okay|yes|no|thanks?|thank you)\.?$',  # Simple acknowledgments
            r'^(hi|hello|hey)\.?$',  # Simple greetings
            r'^\s*$',  # Empty content
            r'^\.{3,}$',  # Just dots
            r'^-+$',  # Just dashes
        ]

    def should_store_memory(
        self,
        content: str,
        role: str,
        salience_score: float,
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> bool:
        """
        Determine if a memory should be stored.

        Args:
            content: Memory content
            role: Message role
            salience_score: Calculated salience score
            metadata: Memory metadata

        Returns:
            bool: True if memory should be stored
        """
        try:
            # Check salience threshold
            if salience_score < self.min_salience:
                logger.debug(
                    f'Memory filtered: salience {salience_score:.3f} < {self.min_salience}'
                )
                return False

            # Check content length
            if len(content.strip()) < 3:
                logger.debug('Memory filtered: content too short')
                return False

            # Check noise patterns
            content_clean = content.strip().lower()
            for pattern in self.noise_patterns:
                if re.match(pattern, content_clean):
                    logger.debug(f'Memory filtered: matches noise pattern {pattern}')
                    return False

            # Always store system errors for debugging
            if role == 'system' and (
                'error' in content.lower() or 'failed' in content.lower()
            ):
                logger.debug('Memory stored: system error/failure message')
                return True

            # Always store high-salience content
            if salience_score >= 0.8:
                logger.debug(f'Memory stored: high salience {salience_score:.3f}')
                return True

            logger.debug(f'Memory accepted: salience {salience_score:.3f}, role {role}')
            return True

        except Exception as e:
            logger.error(f'Error in memory filter: {e}')
            # Default to storing on error
            return True


class MemoryEnricher:
    """
    Enrich memories with additional metadata and context.
    """

    def enrich_metadata(
        self,
        content: str,
        role: str,  # noqa: ARG002
        existing_metadata: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Enrich memory metadata with additional context.

        Args:
            content: Memory content
            role: Message role
            existing_metadata: Existing metadata to enrich
            user_context: User context and preferences

        Returns:
            Dict containing enriched metadata
        """
        try:
            metadata = existing_metadata.copy() if existing_metadata else {}

            # Add processing timestamp
            metadata['processed_at'] = datetime.now().isoformat()

            # Content analysis
            metadata['content_length'] = len(content)
            metadata['word_count'] = len(content.split())

            # Extract and classify entities
            entities = self._extract_entities(content)
            if entities:
                metadata['entities'] = entities

            # Classify content type
            content_type = self._classify_content_type(content)
            if content_type:
                metadata['content_type'] = content_type

            # Research-specific enrichment
            research_metadata = self._extract_research_metadata(content)
            if research_metadata:
                metadata.update(research_metadata)

            # User-specific enrichment
            if user_context:
                tenant_id = user_context.get('tenant_id')
                if tenant_id:
                    metadata['tenant_id'] = tenant_id

                session_id = user_context.get('session_id')
                if session_id:
                    metadata['session_id'] = session_id

                preferences = user_context.get('preferences')
                if preferences:
                    metadata['user_preferences'] = preferences

            # Add quality indicators
            metadata['quality_indicators'] = {
                'has_questions': any(
                    q in content.lower() for q in ['?', 'what', 'how', 'why']
                ),
                'has_actions': any(
                    a in content.lower() for a in ['create', 'find', 'analyze']
                ),
                'has_references': bool(re.search(r'(doi|arxiv|http)', content.lower())),
                'has_entities': bool(entities),
            }

            logger.debug(f'Enriched metadata with {len(metadata)} fields')
            return metadata

        except Exception as e:
            logger.error(f'Error enriching metadata: {e}')
            return existing_metadata or {}

    def _extract_entities(self, content: str) -> list[dict[str, str]]:
        """Extract named entities from content."""
        entities = []

        try:
            # DOI extraction
            doi_matches = re.finditer(r'10\.\d+\/[\w\-\._]+', content)
            for match in doi_matches:
                entities.append(
                    {
                        'type': 'doi',
                        'value': match.group(),
                        'start': match.start(),
                        'end': match.end(),
                    }
                )

            # arXiv ID extraction
            arxiv_matches = re.finditer(r'arXiv:(\d{4}\.\d{4,5})', content)
            for match in arxiv_matches:
                entities.append(
                    {
                        'type': 'arxiv_id',
                        'value': match.group(),
                        'start': match.start(),
                        'end': match.end(),
                    }
                )

            # URL extraction
            url_matches = re.finditer(r'https?:\/\/[^\s]+', content)
            for match in url_matches:
                entities.append(
                    {
                        'type': 'url',
                        'value': match.group(),
                        'start': match.start(),
                        'end': match.end(),
                    }
                )

            return entities

        except Exception as e:
            logger.warning(f'Entity extraction failed: {e}')
            return []

    def _classify_content_type(self, content: str) -> str | None:
        """Classify the type of content."""
        content_lower = content.lower()

        if any(q in content_lower for q in ['?', 'what', 'how', 'why', 'explain']):
            return 'question'
        elif any(a in content_lower for a in ['create', 'build', 'generate', 'make']):
            return 'request'
        elif any(
            a in content_lower for a in ['here is', 'here are', 'found', 'results']
        ):
            return 'response'
        elif 'error' in content_lower or 'failed' in content_lower:
            return 'error'
        elif re.search(r'10\.\d+\/[\w\-\._]+|arXiv:\d+\.\d+', content):
            return 'academic_reference'
        else:
            return 'general'

    def _extract_research_metadata(self, content: str) -> dict[str, Any]:
        """Extract research-specific metadata."""
        metadata = {}

        try:
            # Extract DOIs
            dois = re.findall(r'10\.\d+\/[\w\-\._]+', content)
            if dois:
                metadata['dois'] = dois

            # Extract arXiv IDs
            arxiv_ids = re.findall(r'arXiv:(\d{4}\.\d{4,5})', content)
            if arxiv_ids:
                metadata['arxiv_ids'] = arxiv_ids

            # Research field indicators
            fields = []
            field_keywords = {
                'machine_learning': [
                    'machine learning',
                    'ml',
                    'neural',
                    'deep learning',
                ],
                'nlp': ['nlp', 'natural language', 'text processing', 'language model'],
                'computer_vision': ['computer vision', 'cv', 'image', 'vision'],
                'ai': ['artificial intelligence', 'ai', 'intelligent system'],
                'data_science': ['data science', 'analytics', 'statistics'],
            }

            content_lower = content.lower()
            for field, keywords in field_keywords.items():
                if any(keyword in content_lower for keyword in keywords):
                    fields.append(field)

            if fields:
                metadata['research_fields'] = fields

            return metadata

        except Exception as e:
            logger.warning(f'Research metadata extraction failed: {e}')
            return {}


class MemoryWritePipeline:
    """
    Complete pipeline for processing memories before storage.

    Combines salience scoring, filtering, and metadata enrichment.
    """

    def __init__(
        self,
        min_salience: float = 0.1,
        enable_filtering: bool = True,
        enable_enrichment: bool = True,
    ):
        """
        Initialize memory write pipeline.

        Args:
            min_salience: Minimum salience score for storage
            enable_filtering: Whether to filter low-quality memories
            enable_enrichment: Whether to enrich metadata
        """
        self.scorer = SalienceScorer()
        self.filter = MemoryFilter(min_salience=min_salience)
        self.enricher = MemoryEnricher()
        self.enable_filtering = enable_filtering
        self.enable_enrichment = enable_enrichment

        logger.info(
            f'Memory write pipeline initialized (filtering={enable_filtering}, enrichment={enable_enrichment})'
        )

    def process_memory(
        self,
        user_id: str,
        content: str,
        role: str = 'user',
        scope: str = 'core',
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Process a memory through the complete pipeline.

        Args:
            user_id: User identifier
            content: Memory content
            role: Message role
            scope: Memory scope
            agent_id: Agent identifier
            metadata: Initial metadata
            user_context: User context and preferences

        Returns:
            Dict with processed memory data, or None if filtered out
        """
        try:
            # Calculate salience score
            salience_score = self.scorer.calculate_salience(
                content=content, role=role, metadata=metadata, user_context=user_context
            )

            # Apply filtering if enabled
            if self.enable_filtering:
                if not self.filter.should_store_memory(
                    content=content,
                    role=role,
                    salience_score=salience_score,
                    metadata=metadata,
                ):
                    logger.debug('Memory filtered out by pipeline')
                    return None

            # Enrich metadata if enabled
            enriched_metadata = metadata.copy() if metadata else {}
            if self.enable_enrichment:
                enriched_metadata = self.enricher.enrich_metadata(
                    content=content,
                    role=role,
                    existing_metadata=enriched_metadata,
                    user_context=user_context,
                )

            # Add salience score to metadata
            enriched_metadata['salience_score'] = salience_score

            # Return processed memory data
            return {
                'user_id': user_id,
                'content': content,
                'role': role,
                'scope': scope,
                'agent_id': agent_id,
                'metadata': enriched_metadata,
                'salience_score': salience_score,
            }

        except Exception as e:
            logger.error(f'Memory pipeline processing failed: {e}')
            # Return basic memory data on error
            return {
                'user_id': user_id,
                'content': content,
                'role': role,
                'scope': scope,
                'agent_id': agent_id,
                'metadata': metadata or {},
                'salience_score': 0.5,  # Default moderate score
            }


# ==================== RETRIEVAL PIPELINE CLASSES ====================


class RelevanceScorer:
    """
    Calculate relevance scores for memory retrieval queries.

    Uses semantic similarity, contextual matching, and temporal factors
    to determine how relevant each memory is to a given query.
    """

    def __init__(self, temporal_decay_factor: float = 0.95):
        """
        Initialize the relevance scorer.

        Args:
            temporal_decay_factor: Factor for temporal decay (0.9-1.0)
        """
        self.temporal_decay_factor = temporal_decay_factor

        # Query type patterns for contextual scoring
        self.query_patterns = {
            'question': [
                r'\?$',
                r'^(what|how|why|when|where|who|which)',
                r'(explain|describe|tell me|show me)',
            ],
            'request': [
                r'^(find|search|get|retrieve)',
                r'^(can you|could you|please)',
                r'(help me|assist me)',
            ],
            'reference': [
                r'(paper|article|research|study)',
                r'(arxiv|doi|citation)',
                r'(author|researcher)',
            ],
            'analysis': [
                r'(analyze|compare|evaluate)',
                r'(trends|patterns|insights)',
                r'(methodology|approach)',
            ],
        }

    def calculate_relevance(
        self,
        query: str,
        memory_content: str,
        memory_metadata: dict[str, Any],
        query_context: dict[str, Any] | None = None,
        embedding_similarity: float | None = None,
    ) -> float:
        """
        Calculate relevance score between query and memory.

        Args:
            query: Search query
            memory_content: Memory content to score
            memory_metadata: Memory metadata
            query_context: Context about the query
            embedding_similarity: Pre-computed embedding similarity score

        Returns:
            float: Relevance score (0.0-1.0)
        """
        try:
            # Start with base semantic similarity
            relevance_score = (
                embedding_similarity if embedding_similarity is not None else 0.5
            )

            # Content-based relevance
            content_score = self._calculate_content_relevance(query, memory_content)
            relevance_score = (relevance_score * 0.6) + (content_score * 0.4)

            # Contextual matching
            context_score = self._calculate_context_relevance(
                query, memory_metadata, query_context
            )
            relevance_score = (relevance_score * 0.8) + (context_score * 0.2)

            # Temporal decay
            temporal_score = self._calculate_temporal_relevance(memory_metadata)
            relevance_score *= temporal_score

            # Salience boost
            salience_score = memory_metadata.get('salience_score', 0.5)
            relevance_score = (relevance_score * 0.85) + (salience_score * 0.15)

            return min(1.0, max(0.0, relevance_score))

        except Exception as e:
            logger.error(f'Relevance calculation failed: {e}')
            return 0.5  # Default moderate relevance

    def _calculate_content_relevance(self, query: str, content: str) -> float:
        """Calculate content-based relevance score."""
        query_lower = query.lower().strip()
        content_lower = content.lower().strip()

        if not query_lower or not content_lower:
            return 0.0

        # Exact phrase matching
        if query_lower in content_lower:
            return 0.9

        # Word overlap scoring
        query_words = set(query_lower.split())
        content_words = set(content_lower.split())

        if not query_words:
            return 0.0

        # Calculate overlap ratio
        overlap = len(query_words.intersection(content_words))
        overlap_ratio = overlap / len(query_words)

        # Boost for key terms
        key_terms = {'research', 'paper', 'study', 'analysis', 'method', 'result'}
        key_overlap = len(query_words.intersection(key_terms))
        key_boost = key_overlap * 0.1

        return min(1.0, overlap_ratio + key_boost)

    def _calculate_context_relevance(
        self,
        query: str,
        memory_metadata: dict[str, Any],
        query_context: dict[str, Any] | None,
    ) -> float:
        """Calculate contextual relevance score."""
        score = 0.5

        # Query type matching
        query_type = self._detect_query_type(query)
        memory_type = memory_metadata.get('content_type', 'general')

        # Type compatibility matrix
        type_compatibility = {
            ('question', 'question'): 0.9,
            ('question', 'general'): 0.7,
            ('request', 'academic_reference'): 0.9,
            ('reference', 'academic_reference'): 0.95,
            ('analysis', 'question'): 0.8,
        }

        compatibility = type_compatibility.get((query_type, memory_type), 0.6)
        score = (score * 0.7) + (compatibility * 0.3)

        # Context matching
        if query_context:
            research_fields = query_context.get('research_fields', [])
            memory_fields = memory_metadata.get('research_fields', [])

            if research_fields and memory_fields:
                field_overlap = len(
                    set(research_fields).intersection(set(memory_fields))
                )
                field_boost = min(0.2, field_overlap * 0.1)
                score += field_boost

        return min(1.0, score)

    def _calculate_temporal_relevance(self, memory_metadata: dict[str, Any]) -> float:
        """Calculate temporal relevance factor."""
        created_at = memory_metadata.get('created_at')
        if not created_at:
            return 1.0

        try:
            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            now = datetime.now(created_time.tzinfo)

            # Calculate days since creation
            days_old = (now - created_time).days

            # Apply exponential decay
            decay_factor = self.temporal_decay_factor ** (days_old / 30)  # Per month
            return max(0.1, decay_factor)  # Minimum 10% relevance

        except Exception:
            return 1.0  # Default to no decay on parse error

    def _detect_query_type(self, query: str) -> str:
        """Detect the type of query for contextual matching."""
        query_lower = query.lower()

        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return query_type

        return 'general'


class RetrievalRanker:
    """
    Rank and filter retrieved memories based on multiple factors.

    Combines relevance, salience, recency, and user preferences
    to produce optimal memory ranking for retrieval.
    """

    def __init__(
        self,
        relevance_weight: float = 0.4,
        salience_weight: float = 0.3,
        recency_weight: float = 0.2,
        diversity_weight: float = 0.1,
    ):
        """
        Initialize the retrieval ranker.

        Args:
            relevance_weight: Weight for relevance scores
            salience_weight: Weight for salience scores
            recency_weight: Weight for recency scores
            diversity_weight: Weight for diversity scores
        """
        self.relevance_weight = relevance_weight
        self.salience_weight = salience_weight
        self.recency_weight = recency_weight
        self.diversity_weight = diversity_weight

        # Ensure weights sum to 1.0
        total_weight = sum(
            [relevance_weight, salience_weight, recency_weight, diversity_weight]
        )
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f'Ranking weights sum to {total_weight}, normalizing to 1.0')
            self.relevance_weight /= total_weight
            self.salience_weight /= total_weight
            self.recency_weight /= total_weight
            self.diversity_weight /= total_weight

    def rank_memories(
        self,
        memories: list[dict[str, Any]],
        query: str,
        user_preferences: dict[str, Any] | None = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Rank memories by relevance and other factors.

        Args:
            memories: List of memories with relevance scores
            query: Original search query
            user_preferences: User-specific ranking preferences
            max_results: Maximum number of results to return

        Returns:
            List of ranked memories with ranking scores
        """
        if not memories:
            return []

        try:
            # Calculate composite scores for all memories
            scored_memories = []
            for memory in memories:
                composite_score = self._calculate_composite_score(
                    memory, user_preferences
                )
                memory['_ranking_score'] = composite_score
                scored_memories.append(memory)

            # Sort by composite score
            scored_memories.sort(key=lambda x: x['_ranking_score'], reverse=True)

            # Apply diversity filtering
            diverse_memories = self._apply_diversity_filter(scored_memories, query)

            # Return top results
            return diverse_memories[:max_results]

        except Exception as e:
            logger.error(f'Memory ranking failed: {e}')
            return memories[:max_results]

    def _calculate_composite_score(
        self, memory: dict[str, Any], user_preferences: dict[str, Any] | None
    ) -> float:
        """Calculate composite ranking score."""
        # Get individual scores
        relevance = memory.get('_relevance_score', 0.5)
        salience = memory.get('salience_score', 0.5)
        recency = self._calculate_recency_score(memory)
        diversity = memory.get('_diversity_score', 0.5)

        # Apply user preferences
        if user_preferences:
            relevance = self._apply_user_preferences(
                relevance, memory, user_preferences
            )

        # Calculate weighted composite score
        composite = (
            (relevance * self.relevance_weight)
            + (salience * self.salience_weight)
            + (recency * self.recency_weight)
            + (diversity * self.diversity_weight)
        )

        return min(1.0, max(0.0, composite))

    def _calculate_recency_score(self, memory: dict[str, Any]) -> float:
        """Calculate recency score based on creation time."""
        created_at = memory.get('created_at')
        if not created_at:
            return 0.5

        try:
            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            now = datetime.now(created_time.tzinfo)

            # Calculate hours since creation
            hours_old = (now - created_time).total_seconds() / 3600

            # Recent memories get higher scores
            if hours_old < 1:
                return 1.0
            elif hours_old < 24:
                return 0.9
            elif hours_old < 168:  # 1 week
                return 0.7
            elif hours_old < 720:  # 1 month
                return 0.5
            else:
                return 0.3

        except Exception:
            return 0.5

    def _apply_user_preferences(
        self, base_score: float, memory: dict[str, Any], preferences: dict[str, Any]
    ) -> float:
        """Apply user preferences to adjust scoring."""
        adjusted_score = base_score

        # Preferred content types
        preferred_types = preferences.get('content_types', [])
        memory_type = memory.get('metadata', {}).get('content_type')
        if preferred_types and memory_type in preferred_types:
            adjusted_score = min(1.0, adjusted_score * 1.1)

        # Research field preferences
        preferred_fields = preferences.get('research_fields', [])
        memory_fields = memory.get('metadata', {}).get('research_fields', [])
        if preferred_fields and any(
            field in memory_fields for field in preferred_fields
        ):
            adjusted_score = min(1.0, adjusted_score * 1.05)

        return adjusted_score

    def _apply_diversity_filter(
        self,
        memories: list[dict[str, Any]],
        query: str,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """Apply diversity filtering to avoid redundant results."""
        if len(memories) <= 3:
            return memories

        diverse_memories = []
        seen_content_hashes = set()

        for memory in memories:
            content = memory.get('content', '')
            content_hash = hash(content.lower().strip())

            # Skip very similar content
            if content_hash not in seen_content_hashes:
                diverse_memories.append(memory)
                seen_content_hashes.add(content_hash)

                # Stop if we have enough diverse results
                if len(diverse_memories) >= len(memories) * 0.8:
                    break

        return diverse_memories


class RetrievalMetrics:
    """
    Track and analyze memory retrieval performance metrics.

    Provides insights into search quality, user satisfaction,
    and system performance for continuous improvement.
    """

    def __init__(self):
        """Initialize retrieval metrics tracker."""
        self.query_metrics: dict[str, Any] = {}
        self.performance_metrics: dict[str, list[float]] = {
            'search_latency': [],
            'relevance_scores': [],
            'result_counts': [],
            'cache_hit_rate': [],
        }
        self.user_metrics: dict[str, dict[str, Any]] = {}

    def record_query(
        self,
        query: str,
        user_id: str,
        results: list[dict[str, Any]],
        search_time: float,
        cache_hit: bool = False,
    ) -> None:
        """
        Record metrics for a completed query.

        Args:
            query: Search query text
            user_id: User who performed the query
            results: Search results returned
            search_time: Time taken for search in seconds
            cache_hit: Whether result was served from cache
        """
        try:
            timestamp = datetime.now().isoformat()
            query_id = hash(f'{query}:{user_id}:{timestamp}')

            # Record query-level metrics
            self.query_metrics[query_id] = {
                'query': query,
                'user_id': user_id,
                'timestamp': timestamp,
                'result_count': len(results),
                'search_time': search_time,
                'cache_hit': cache_hit,
                'avg_relevance': self._calculate_avg_relevance(results),
                'avg_salience': self._calculate_avg_salience(results),
            }

            # Update performance metrics
            self.performance_metrics['search_latency'].append(search_time)
            self.performance_metrics['result_counts'].append(len(results))
            self.performance_metrics['cache_hit_rate'].append(1.0 if cache_hit else 0.0)

            if results:
                avg_relevance = self._calculate_avg_relevance(results)
                self.performance_metrics['relevance_scores'].append(avg_relevance)

            # Update user metrics
            if user_id not in self.user_metrics:
                self.user_metrics[user_id] = {
                    'total_queries': 0,
                    'avg_search_time': 0.0,
                    'preferred_content_types': {},
                    'query_patterns': [],
                }

            user_stats = self.user_metrics[user_id]
            user_stats['total_queries'] += 1
            user_stats['query_patterns'].append(query)

            # Update rolling averages
            current_avg = user_stats['avg_search_time']
            query_count = user_stats['total_queries']
            user_stats['avg_search_time'] = (
                current_avg * (query_count - 1) + search_time
            ) / query_count

            # Track content type preferences
            for result in results:
                content_type = result.get('metadata', {}).get('content_type', 'general')
                user_stats['preferred_content_types'][content_type] = (
                    user_stats['preferred_content_types'].get(content_type, 0) + 1
                )

            logger.debug(
                f'Recorded query metrics for user {user_id}: {len(results)} results in {search_time:.3f}s'
            )

        except Exception as e:
            logger.error(f'Failed to record query metrics: {e}')

    def get_performance_summary(self) -> dict[str, Any]:
        """Get overall performance metrics summary."""
        try:
            if not self.performance_metrics['search_latency']:
                return {'status': 'no_data'}

            summary = {
                'total_queries': len(self.query_metrics),
                'avg_search_latency': sum(self.performance_metrics['search_latency'])
                / len(self.performance_metrics['search_latency']),
                'avg_result_count': sum(self.performance_metrics['result_counts'])
                / len(self.performance_metrics['result_counts']),
                'cache_hit_rate': sum(self.performance_metrics['cache_hit_rate'])
                / len(self.performance_metrics['cache_hit_rate']),
                'avg_relevance_score': sum(self.performance_metrics['relevance_scores'])
                / len(self.performance_metrics['relevance_scores'])
                if self.performance_metrics['relevance_scores']
                else 0.0,
                'unique_users': len(self.user_metrics),
            }

            return summary

        except Exception as e:
            logger.error(f'Failed to generate performance summary: {e}')
            return {'status': 'error', 'message': str(e)}

    def get_user_insights(self, user_id: str) -> dict[str, Any]:
        """Get insights for a specific user."""
        user_stats = self.user_metrics.get(user_id)
        if not user_stats:
            return {'status': 'no_data'}

        try:
            # Analyze query patterns
            patterns = self._analyze_query_patterns(user_stats['query_patterns'])

            # Get top content types
            content_preferences = dict(
                sorted(
                    user_stats['preferred_content_types'].items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:5]
            )

            return {
                'total_queries': user_stats['total_queries'],
                'avg_search_time': user_stats['avg_search_time'],
                'content_preferences': content_preferences,
                'query_patterns': patterns,
                'activity_level': self._categorize_activity_level(
                    user_stats['total_queries']
                ),
            }

        except Exception as e:
            logger.error(f'Failed to generate user insights: {e}')
            return {'status': 'error', 'message': str(e)}

    def _calculate_avg_relevance(self, results: list[dict[str, Any]]) -> float:
        """Calculate average relevance score from results."""
        if not results:
            return 0.0

        relevance_scores = [r.get('_relevance_score', 0.5) for r in results]
        return sum(relevance_scores) / len(relevance_scores)

    def _calculate_avg_salience(self, results: list[dict[str, Any]]) -> float:
        """Calculate average salience score from results."""
        if not results:
            return 0.0

        salience_scores = [r.get('salience_score', 0.5) for r in results]
        return sum(salience_scores) / len(salience_scores)

    def _analyze_query_patterns(self, queries: list[str]) -> dict[str, Any]:
        """Analyze user query patterns."""
        if not queries:
            return {}

        # Categorize recent queries
        recent_queries = queries[-20:] if len(queries) > 20 else queries

        patterns = {
            'question_ratio': len([q for q in recent_queries if '?' in q])
            / len(recent_queries),
            'avg_query_length': sum(len(q.split()) for q in recent_queries)
            / len(recent_queries),
            'research_focused': len(
                [
                    q
                    for q in recent_queries
                    if any(
                        term in q.lower()
                        for term in ['research', 'paper', 'study', 'analysis']
                    )
                ]
            )
            / len(recent_queries),
        }

        return patterns

    def _categorize_activity_level(self, query_count: int) -> str:
        """Categorize user activity level."""
        if query_count < 5:
            return 'low'
        elif query_count < 20:
            return 'moderate'
        elif query_count < 50:
            return 'high'
        else:
            return 'very_high'


class MemoryRetrievalPipeline:
    """
    Complete pipeline for memory retrieval with semantic search and ranking.

    Orchestrates the full retrieval workflow including query processing,
    semantic search, relevance scoring, ranking, and metrics collection.
    """

    def __init__(
        self,
        rag_service=None,
        enable_semantic_search: bool = True,
        enable_caching: bool = True,
        cache_ttl: int = 300,  # 5 minutes
        max_results: int = 20,
    ):
        """
        Initialize the memory retrieval pipeline.

        Args:
            rag_service: RAG service for vector search
            enable_semantic_search: Enable semantic vector search
            enable_caching: Enable result caching
            cache_ttl: Cache time-to-live in seconds
            max_results: Maximum results to return
        """
        self.rag_service = rag_service
        self.enable_semantic_search = enable_semantic_search
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl
        self.max_results = max_results

        # Pipeline components
        self.relevance_scorer = RelevanceScorer()
        self.ranker = RetrievalRanker()
        self.metrics = RetrievalMetrics()

        # Result cache
        self.cache: dict[str, dict[str, Any]] = {}

        logger.info(
            f'Memory retrieval pipeline initialized '
            f'(semantic_search={enable_semantic_search}, caching={enable_caching})'
        )

    def search_memories(
        self,
        query: str,
        user_id: str,
        memories: list[dict[str, Any]],
        scope: str = 'core',
        user_context: dict[str, Any] | None = None,
        user_preferences: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Search and rank memories using the complete pipeline.

        Args:
            query: Search query
            user_id: User performing the search
            memories: Pool of memories to search
            scope: Memory scope being searched
            user_context: Context about the query
            user_preferences: User-specific preferences

        Returns:
            Dict with results, metrics, and metadata
        """
        start_time = datetime.now()
        cache_key = f'{hash(query)}:{user_id}:{scope}'

        try:
            # Check cache first
            if self.enable_caching and cache_key in self.cache:
                cached_result = self.cache[cache_key]
                cache_time = datetime.fromisoformat(cached_result['timestamp'])
                if (start_time - cache_time).total_seconds() < self.cache_ttl:
                    self.metrics.record_query(
                        query,
                        user_id,
                        cached_result['results'],
                        (datetime.now() - start_time).total_seconds(),
                        cache_hit=True,
                    )
                    return cached_result

            # Process query
            processed_memories = self._process_query_search(
                query, memories, user_context
            )

            # Rank results
            ranked_memories = self.ranker.rank_memories(
                processed_memories, query, user_preferences, self.max_results
            )

            # Prepare result
            search_time = (datetime.now() - start_time).total_seconds()
            result = {
                'results': ranked_memories,
                'query': query,
                'total_searched': len(memories),
                'total_results': len(ranked_memories),
                'search_time': search_time,
                'timestamp': start_time.isoformat(),
                'used_semantic_search': self.enable_semantic_search,
                'cache_hit': False,
            }

            # Cache result
            if self.enable_caching:
                self.cache[cache_key] = result

            # Record metrics
            self.metrics.record_query(query, user_id, ranked_memories, search_time)

            logger.debug(
                f'Memory search completed: {len(ranked_memories)} results '
                f'from {len(memories)} memories in {search_time:.3f}s'
            )

            return result

        except Exception as e:
            logger.error(f'Memory retrieval pipeline failed: {e}')
            search_time = (datetime.now() - start_time).total_seconds()

            # Return basic text search fallback
            return self._fallback_search(query, memories, search_time)

    def _process_query_search(
        self,
        query: str,
        memories: list[dict[str, Any]],
        user_context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Process memories through semantic search and relevance scoring."""
        processed_memories = []

        # Get semantic embeddings if available
        embedding_scores = {}
        if self.enable_semantic_search and self.rag_service:
            embedding_scores = self._get_semantic_similarities(query, memories)

        # Score each memory for relevance
        for memory in memories:
            memory_id = memory.get('id', '')
            embedding_similarity = embedding_scores.get(memory_id, None)

            relevance_score = self.relevance_scorer.calculate_relevance(
                query=query,
                memory_content=memory.get('content', ''),
                memory_metadata=memory.get('metadata', {}),
                query_context=user_context,
                embedding_similarity=embedding_similarity,
            )

            # Add relevance score to memory
            memory['_relevance_score'] = relevance_score
            processed_memories.append(memory)

        # Filter out very low relevance results
        min_relevance = 0.1
        filtered_memories = [
            m for m in processed_memories if m['_relevance_score'] >= min_relevance
        ]

        return filtered_memories

    def _get_semantic_similarities(
        self, query: str, memories: list[dict[str, Any]]
    ) -> dict[str, float]:
        """Get semantic similarity scores using RAG service."""
        try:
            if not self.rag_service:
                return {}

            # Extract memory contents for embedding
            memory_contents = [m.get('content', '') for m in memories]
            memory_ids = [m.get('id', '') for m in memories]

            # Use RAG service for semantic search
            # Note: This is a simplified approach - real implementation
            # would need proper integration with the vector store
            similarities = {}

            for i, content in enumerate(memory_contents):
                if content and memory_ids[i]:
                    # Placeholder similarity calculation
                    # Real implementation would use vector embeddings
                    similarity = self._calculate_text_similarity(query, content)
                    similarities[memory_ids[i]] = similarity

            return similarities

        except Exception as e:
            logger.error(f'Semantic similarity calculation failed: {e}')
            return {}

    def _calculate_text_similarity(self, query: str, content: str) -> float:
        """Fallback text similarity calculation."""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())

        if not query_words or not content_words:
            return 0.0

        intersection = len(query_words.intersection(content_words))
        union = len(query_words.union(content_words))

        return intersection / union if union > 0 else 0.0

    def _fallback_search(
        self, query: str, memories: list[dict[str, Any]], search_time: float
    ) -> dict[str, Any]:
        """Fallback search using basic text matching."""
        query_lower = query.lower()
        matching_memories = []

        for memory in memories:
            content = memory.get('content', '').lower()
            if query_lower in content:
                # Simple relevance score
                relevance = (
                    content.count(query_lower) / len(content.split()) if content else 0
                )
                memory['_relevance_score'] = min(1.0, relevance * 2)
                matching_memories.append(memory)

        # Sort by relevance
        matching_memories.sort(key=lambda x: x['_relevance_score'], reverse=True)

        return {
            'results': matching_memories[: self.max_results],
            'query': query,
            'total_searched': len(memories),
            'total_results': len(matching_memories[: self.max_results]),
            'search_time': search_time,
            'timestamp': datetime.now().isoformat(),
            'used_semantic_search': False,
            'cache_hit': False,
            'fallback_search': True,
        }

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get pipeline performance metrics."""
        return self.metrics.get_performance_summary()

    def get_user_insights(self, user_id: str) -> dict[str, Any]:
        """Get user-specific search insights."""
        return self.metrics.get_user_insights(user_id)

    def clear_cache(self) -> None:
        """Clear the result cache."""
        self.cache.clear()
        logger.info('Memory retrieval cache cleared')

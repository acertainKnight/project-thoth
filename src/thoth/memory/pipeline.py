"""
Memory Pipeline Hooks

This module provides intelligent memory processing hooks for filtering,
enriching, and scoring memories before storage in the Letta memory system.
"""

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

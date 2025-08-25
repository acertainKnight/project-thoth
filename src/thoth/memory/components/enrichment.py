"""
Memory enrichment components for adding metadata and context.

This module provides functionality to enrich memories with additional
metadata, entity extraction, and content classification.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from loguru import logger


class MemoryEnricher:
    """
    Enrich memories with additional metadata and context.
    """

    def enrich_metadata(
        self,
        content: str,
        role: str,
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

    def enrich_memory_batch(
        self,
        memories: list[dict[str, Any]],
        user_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Enrich a batch of memories with metadata.

        Args:
            memories: List of memory dictionaries
            user_context: User context for enrichment

        Returns:
            list[dict]: List of enriched memories
        """
        enriched_memories = []

        for memory in memories:
            content = memory.get('content', '')
            role = memory.get('role', 'unknown')
            existing_metadata = memory.get('metadata', {})

            enriched_metadata = self.enrich_metadata(
                content=content,
                role=role,
                existing_metadata=existing_metadata,
                user_context=user_context,
            )

            # Create enriched memory
            enriched_memory = memory.copy()
            enriched_memory['metadata'] = enriched_metadata
            enriched_memories.append(enriched_memory)

        logger.info(f'Enriched {len(memories)} memories with metadata')
        return enriched_memories

    def extract_topics(self, content: str) -> list[str]:
        """
        Extract potential topics from content.

        Args:
            content: Text content to analyze

        Returns:
            list[str]: List of identified topics
        """
        topics = []

        try:
            # Simple topic extraction based on keywords
            topic_patterns = {
                'research_methodology': r'\b(methodology|method|approach|technique)\b',
                'data_analysis': r'\b(analysis|analyze|data|results|findings)\b',
                'machine_learning': r'\b(machine learning|ml|neural|deep learning|ai)\b',
                'academic_paper': r'\b(paper|journal|publication|article|study)\b',
                'experiment': r'\b(experiment|test|trial|evaluation)\b',
                'citation': r'\b(citation|reference|doi|arxiv)\b',
            }

            content_lower = content.lower()
            for topic, pattern in topic_patterns.items():
                if re.search(pattern, content_lower):
                    topics.append(topic)

            return list(set(topics))  # Remove duplicates

        except Exception as e:
            logger.warning(f'Topic extraction failed: {e}')
            return []

    def calculate_content_complexity(self, content: str) -> dict[str, Any]:
        """
        Calculate various complexity metrics for content.

        Args:
            content: Content to analyze

        Returns:
            dict: Complexity metrics
        """
        try:
            words = content.split()
            sentences = re.split(r'[.!?]+', content)

            complexity = {
                'word_count': len(words),
                'sentence_count': len([s for s in sentences if s.strip()]),
                'avg_words_per_sentence': len(words)
                / max(1, len([s for s in sentences if s.strip()])),
                'unique_words': len(
                    set(word.lower() for word in words if word.isalpha())
                ),
                'lexical_diversity': len(
                    set(word.lower() for word in words if word.isalpha())
                )
                / max(1, len(words)),
                'has_technical_terms': bool(
                    re.search(
                        r'\b(algorithm|model|data|analysis|system)\b', content.lower()
                    )
                ),
                'question_count': content.count('?'),
                'url_count': len(re.findall(r'https?:\/\/[^\s]+', content)),
                'doi_count': len(re.findall(r'10\.\d+\/[\w\-\._]+', content)),
            }

            return complexity

        except Exception as e:
            logger.warning(f'Complexity calculation failed: {e}')
            return {}

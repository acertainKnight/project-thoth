"""
Memory enrichment component.

Enriches memories with additional metadata and context.
"""

import re
from datetime import datetime
from typing import Any

from loguru import logger


class MemoryEnricher:
    """
    Enrich memories with additional metadata and context before storage.
    """

    def __init__(self):
        """Initialize the memory enricher."""
        # URL pattern for detection
        self.url_pattern = re.compile(
            r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}'
            r'\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'
        )

        # Citation patterns
        self.citation_patterns = [
            # DOI pattern
            re.compile(r'10\.\d{4,}/[-._;()/:a-zA-Z0-9]+'),
            # arXiv pattern
            re.compile(r'arXiv:\d{4}\.\d{4,5}(?:v\d+)?'),
            # Author (Year) pattern
            re.compile(r'\b[A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)*\s*\(\d{4}\)'),
        ]

        # Code block pattern
        self.code_pattern = re.compile(r'```[\s\S]*?```|`[^`]+`')

    def enrich(
        self,
        content: str,
        role: str,
        metadata: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Enrich a memory with additional metadata.

        Args:
            content: Memory content
            role: Message role
            metadata: Existing metadata
            user_context: User context information

        Returns:
            dict[str, Any]: Enriched metadata
        """
        try:
            enriched = metadata.copy() if metadata else {}

            # Add timestamp if not present
            if 'timestamp' not in enriched:
                enriched['timestamp'] = datetime.now().isoformat()

            # Add role
            enriched['role'] = role

            # Content analysis
            enriched['content_features'] = self._analyze_content(content)

            # Extract entities
            entities = self._extract_entities(content)
            if entities:
                enriched['entities'] = entities

            # Add user context if available
            if user_context:
                enriched['user_context'] = {
                    'user_id': user_context.get('user_id'),
                    'session_id': user_context.get('session_id'),
                    'interaction_count': user_context.get('interaction_count', 0),
                }

            # Tool-specific enrichment
            if metadata and metadata.get('tool_name'):
                enriched['tool_metadata'] = self._enrich_tool_metadata(
                    metadata, content
                )

            # Research-specific enrichment
            if self._is_research_content(content, metadata):
                enriched['research_metadata'] = self._extract_research_metadata(
                    content, metadata
                )

            return enriched

        except Exception as e:
            logger.error(f'Error enriching memory: {e}')
            # Return original metadata on error
            return metadata or {}

    def _analyze_content(self, content: str) -> dict[str, Any]:
        """Analyze content features."""
        return {
            'length': len(content),
            'word_count': len(content.split()),
            'has_urls': bool(self.url_pattern.search(content)),
            'has_code': bool(self.code_pattern.search(content)),
            'has_citations': any(
                pattern.search(content) for pattern in self.citation_patterns
            ),
            'question_count': content.count('?'),
            'exclamation_count': content.count('!'),
        }

    def _extract_entities(self, content: str) -> dict[str, list[str]]:
        """Extract named entities from content."""
        entities = {
            'urls': [],
            'citations': [],
            'code_snippets': [],
        }

        # Extract URLs
        entities['urls'] = self.url_pattern.findall(content)

        # Extract citations
        for pattern in self.citation_patterns:
            entities['citations'].extend(pattern.findall(content))

        # Extract code snippets (just indicators, not full content)
        code_matches = self.code_pattern.findall(content)
        if code_matches:
            entities['code_snippets'] = [
                f'Code block {i+1} ({len(match)} chars)'
                for i, match in enumerate(code_matches[:5])  # Limit to 5
            ]

        # Remove empty lists
        return {k: v for k, v in entities.items() if v}

    def _enrich_tool_metadata(
        self, metadata: dict[str, Any], content: str
    ) -> dict[str, Any]:
        """Add tool-specific enrichment."""
        tool_meta = {
            'tool_name': metadata.get('tool_name'),
            'execution_time': metadata.get('execution_time'),
            'success': not metadata.get('error'),
        }

        # Tool-specific features
        tool_name = metadata.get('tool_name', '').lower()

        if 'search' in tool_name:
            # Extract search query if present
            tool_meta['search_result_count'] = content.count('\n- ')

        elif 'arxiv' in tool_name or 'paper' in tool_name:
            # Count papers mentioned
            tool_meta['papers_mentioned'] = len(
                self.citation_patterns[0].findall(content)
            )

        elif 'web' in tool_name:
            # Count URLs
            tool_meta['urls_found'] = len(self.url_pattern.findall(content))

        return tool_meta

    def _is_research_content(
        self, content: str, metadata: dict[str, Any] | None
    ) -> bool:
        """Check if content is research-related."""
        # Check metadata
        if metadata:
            tool_name = metadata.get('tool_name', '').lower()
            if any(
                term in tool_name
                for term in ['arxiv', 'paper', 'citation', 'research', 'scholar']
            ):
                return True

        # Check content
        content_lower = content.lower()
        research_indicators = [
            'paper',
            'research',
            'study',
            'arxiv',
            'methodology',
            'results',
            'abstract',
            'citation',
            'journal',
            'conference',
        ]

        return sum(1 for term in research_indicators if term in content_lower) >= 2

    def _extract_research_metadata(
        self, content: str, metadata: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Extract research-specific metadata."""
        research_meta = {}

        # Extract DOIs
        dois = self.citation_patterns[0].findall(content)
        if dois:
            research_meta['dois'] = list(set(dois))

        # Extract arXiv IDs
        arxiv_ids = self.citation_patterns[1].findall(content)
        if arxiv_ids:
            research_meta['arxiv_ids'] = list(set(arxiv_ids))

        # Extract paper titles (heuristic - lines that look like titles)
        title_pattern = re.compile(r'^[A-Z][^.!?\n]{10,100}$', re.MULTILINE)
        potential_titles = title_pattern.findall(content)
        if potential_titles:
            research_meta['potential_titles'] = potential_titles[:5]  # Limit to 5

        # Research domains mentioned
        domains = []
        domain_keywords = {
            'machine learning': ['ml', 'machine learning', 'deep learning', 'neural'],
            'natural language': ['nlp', 'natural language', 'language model', 'llm'],
            'computer vision': ['computer vision', 'image', 'visual', 'cv'],
            'robotics': ['robot', 'robotic', 'autonomous'],
        }

        content_lower = content.lower()
        for domain, keywords in domain_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                domains.append(domain)

        if domains:
            research_meta['domains'] = domains

        return research_meta
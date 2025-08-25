"""
Chat Context Analyzer for Auto-Discovery

This module analyzes conversation context to identify research topics and
automatically suggest relevant discovery sources for paper discovery.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from thoth.services.service_manager import ServiceManager


@dataclass
class ResearchTopic:
    """Represents a research topic identified from conversation context."""

    topic: str
    keywords: list[str]
    confidence: float
    context_snippets: list[str]
    suggested_categories: list[str]
    frequency: int = 1
    last_mentioned: datetime | None = None


@dataclass
class DiscoverySourceSuggestion:
    """Represents a suggested discovery source based on conversation analysis."""

    source_name: str
    source_type: str  # 'arxiv', 'pubmed', 'crossref', etc.
    keywords: list[str]
    categories: list[str] | None
    confidence: float
    reasoning: str
    topic_coverage: list[str]


class ChatContextAnalyzer:
    """
    Analyzes chat conversations to identify research topics and suggest sources.

    This analyzer uses pattern matching and keyword extraction to identify when users
    discuss research topics that could benefit from automated paper discovery.
    """

    def __init__(self, service_manager: ServiceManager):
        """
        Initialize the chat context analyzer.

        Args:
            service_manager: ServiceManager instance for accessing services
        """
        self.service_manager = service_manager

        # Research domain patterns for categorization
        self.domain_patterns = {
            'machine_learning': {
                'keywords': [
                    'machine learning',
                    'deep learning',
                    'neural network',
                    'ai',
                    'artificial intelligence',
                    'transformer',
                    'cnn',
                    'rnn',
                    'lstm',
                    'bert',
                    'gpt',
                    'llm',
                    'large language model',
                    'reinforcement learning',
                    'supervised learning',
                    'unsupervised learning',
                    'classification',
                    'regression',
                    'clustering',
                    'optimization',
                    'gradient descent',
                ],
                'arxiv_categories': ['cs.LG', 'cs.AI', 'stat.ML'],
                'pubmed_terms': [
                    'machine learning',
                    'artificial intelligence',
                    'deep learning',
                ],
            },
            'computer_vision': {
                'keywords': [
                    'computer vision',
                    'image recognition',
                    'object detection',
                    'segmentation',
                    'face recognition',
                    'optical character recognition',
                    'ocr',
                    'image processing',
                    'convolutional neural network',
                    'gan',
                    'generative adversarial network',
                    'image classification',
                    'feature extraction',
                    'edge detection',
                ],
                'arxiv_categories': ['cs.CV', 'eess.IV'],
                'pubmed_terms': [
                    'computer vision',
                    'image analysis',
                    'medical imaging',
                ],
            },
            'natural_language_processing': {
                'keywords': [
                    'nlp',
                    'natural language processing',
                    'text analysis',
                    'sentiment analysis',
                    'named entity recognition',
                    'ner',
                    'text mining',
                    'language model',
                    'text classification',
                    'text generation',
                    'summarization',
                    'translation',
                    'tokenization',
                    'embedding',
                    'word2vec',
                    'glove',
                    'attention mechanism',
                ],
                'arxiv_categories': ['cs.CL', 'cs.IR'],
                'pubmed_terms': [
                    'natural language processing',
                    'text mining',
                    'computational linguistics',
                ],
            },
            'robotics': {
                'keywords': [
                    'robotics',
                    'autonomous systems',
                    'robot navigation',
                    'path planning',
                    'slam',
                    'simultaneous localization and mapping',
                    'motion planning',
                    'robotic arm',
                    'humanoid robot',
                    'drone',
                    'uav',
                    'manipulation',
                    'sensor fusion',
                    'control systems',
                    'actuators',
                ],
                'arxiv_categories': ['cs.RO', 'cs.SY'],
                'pubmed_terms': ['robotics', 'prosthetics', 'rehabilitation robotics'],
            },
            'bioinformatics': {
                'keywords': [
                    'bioinformatics',
                    'computational biology',
                    'genomics',
                    'proteomics',
                    'sequence alignment',
                    'phylogenetics',
                    'molecular dynamics',
                    'drug discovery',
                    'systems biology',
                    'biomarker',
                    'gene expression',
                    'dna sequencing',
                    'protein structure',
                    'metabolomics',
                    'transcriptomics',
                ],
                'arxiv_categories': ['q-bio.QM', 'q-bio.GN'],
                'pubmed_terms': ['bioinformatics', 'computational biology', 'genomics'],
            },
            'cybersecurity': {
                'keywords': [
                    'cybersecurity',
                    'network security',
                    'cryptography',
                    'encryption',
                    'malware detection',
                    'intrusion detection',
                    'vulnerability assessment',
                    'penetration testing',
                    'digital forensics',
                    'blockchain security',
                    'authentication',
                    'authorization',
                    'access control',
                    'privacy',
                ],
                'arxiv_categories': ['cs.CR', 'cs.NI'],
                'pubmed_terms': [
                    'medical informatics security',
                    'healthcare cybersecurity',
                ],
            },
            'quantum_computing': {
                'keywords': [
                    'quantum computing',
                    'quantum algorithm',
                    'quantum machine learning',
                    'quantum cryptography',
                    'quantum entanglement',
                    'qubit',
                    'quantum gate',
                    'quantum circuit',
                    'quantum error correction',
                    'quantum supremacy',
                    'variational quantum',
                    'qaoa',
                    'quantum annealing',
                ],
                'arxiv_categories': ['quant-ph', 'cs.ET'],
                'pubmed_terms': ['quantum biology', 'quantum effects'],
            },
        }

        # Patterns for identifying research interest expressions
        self.interest_patterns = [
            r"i'm interested in (.+?)(?:\.|,|$)",
            r'i want to learn about (.+?)(?:\.|,|$)',
            r'can you help me with (.+?)(?:\.|,|$)',
            r"i'm working on (.+?)(?:\.|,|$)",
            r"i'm researching (.+?)(?:\.|,|$)",
            r'tell me about (.+?)(?:\.|,|$)',
            r"what's new in (.+?)(?:\.|,|$)",
            r'recent advances in (.+?)(?:\.|,|$)',
            r'state of the art in (.+?)(?:\.|,|$)',
            r'latest research on (.+?)(?:\.|,|$)',
        ]

        # Topic tracking for frequency analysis
        self.topic_history: dict[str, ResearchTopic] = {}

        logger.info('Chat context analyzer initialized')

    def analyze_conversation_context(
        self,
        messages: list[dict[str, Any]],
        user_id: str,
        session_id: str | None = None,  # noqa: ARG002
        lookback_hours: int = 24,
    ) -> list[ResearchTopic]:
        """
        Analyze a conversation to identify research topics and interests.

        Args:
            messages: List of conversation messages
            user_id: User identifier
            session_id: Session identifier (optional)
            lookback_hours: How far back to look for context

        Returns:
            List of identified research topics
        """
        try:
            logger.info(f'Analyzing conversation context for user {user_id}')

            # Filter messages within lookback window
            cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
            recent_messages = self._filter_recent_messages(messages, cutoff_time)

            if not recent_messages:
                return []

            # Extract research topics from messages
            identified_topics = []

            for message in recent_messages:
                content = message.get('content', '').lower()
                role = message.get('role', 'user')

                # Focus on user messages for topic identification
                if role == 'user':
                    topics = self._extract_topics_from_text(content, message)
                    identified_topics.extend(topics)

            # Merge and rank topics
            merged_topics = self._merge_similar_topics(identified_topics)
            ranked_topics = self._rank_topics_by_confidence(merged_topics)

            # Update topic history
            self._update_topic_history(ranked_topics, user_id)

            logger.info(
                f'Identified {len(ranked_topics)} research topics from conversation'
            )
            return ranked_topics

        except Exception as e:
            logger.error(f'Error analyzing conversation context: {e}')
            return []

    def suggest_discovery_sources(
        self, topics: list[ResearchTopic], existing_sources: list[Any] | None = None
    ) -> list[DiscoverySourceSuggestion]:
        """
        Generate discovery source suggestions based on identified topics.

        Args:
            topics: List of identified research topics
            existing_sources: List of existing discovery sources to avoid duplication

        Returns:
            List of discovery source suggestions
        """
        try:
            existing_source_names = set()
            existing_keywords = set()

            if existing_sources:
                for source in existing_sources:
                    existing_source_names.add(source.name)
                    if hasattr(source, 'api_config') and source.api_config:
                        keywords = source.api_config.get('keywords', [])
                        existing_keywords.update(k.lower() for k in keywords)

            suggestions = []

            for topic in topics:
                # Skip if topic already covered by existing sources
                if any(keyword in existing_keywords for keyword in topic.keywords):
                    continue

                # Generate suggestions for different source types
                topic_suggestions = self._generate_topic_suggestions(
                    topic, existing_source_names
                )
                suggestions.extend(topic_suggestions)

            # Remove duplicates and rank suggestions
            unique_suggestions = self._deduplicate_suggestions(suggestions)
            ranked_suggestions = sorted(
                unique_suggestions, key=lambda s: s.confidence, reverse=True
            )

            logger.info(
                f'Generated {len(ranked_suggestions)} discovery source suggestions'
            )
            return ranked_suggestions[:10]  # Limit to top 10 suggestions

        except Exception as e:
            logger.error(f'Error generating discovery source suggestions: {e}')
            return []

    def auto_create_discovery_sources(
        self,
        suggestions: list[DiscoverySourceSuggestion],
        auto_create_threshold: float = 0.8,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Automatically create discovery sources for high-confidence suggestions.

        Args:
            suggestions: List of discovery source suggestions
            auto_create_threshold: Minimum confidence threshold for auto-creation
            user_id: User ID for tracking (optional)

        Returns:
            List of creation results
        """
        try:
            results = []

            for suggestion in suggestions:
                if suggestion.confidence >= auto_create_threshold:
                    try:
                        result = self._create_discovery_source_from_suggestion(
                            suggestion, user_id
                        )
                        results.append(
                            {
                                'suggestion': suggestion,
                                'created': result.get('success', False),
                                'source_name': suggestion.source_name,
                                'message': result.get('message', ''),
                            }
                        )

                        if result.get('success'):
                            logger.info(
                                f'Auto-created discovery source: {suggestion.source_name}'
                            )
                        else:
                            logger.warning(
                                f'Failed to auto-create source {suggestion.source_name}: '
                                f'{result.get("message", "Unknown error")}'
                            )

                    except Exception as e:
                        logger.error(
                            f'Error auto-creating source {suggestion.source_name}: {e}'
                        )
                        results.append(
                            {
                                'suggestion': suggestion,
                                'created': False,
                                'source_name': suggestion.source_name,
                                'message': f'Error: {e}',
                            }
                        )

            logger.info(f'Auto-creation completed: {len(results)} sources processed')
            return results

        except Exception as e:
            logger.error(f'Error in auto-creation process: {e}')
            return []

    def get_contextual_discovery_recommendations(
        self,
        user_id: str,
        session_id: str | None = None,
        include_auto_create: bool = False,
    ) -> dict[str, Any]:
        """
        Get comprehensive discovery recommendations based on recent conversations.

        Args:
            user_id: User identifier
            session_id: Session identifier (optional)
            include_auto_create: Whether to auto-create high-confidence sources

        Returns:
            Dict with recommendations and analysis results
        """
        try:
            # Get recent conversation history from memory
            conversation_messages = self._get_recent_conversation_history(
                user_id, session_id
            )

            if not conversation_messages:
                return {
                    'status': 'no_conversation_data',
                    'message': 'No recent conversation data available for analysis',
                    'topics': [],
                    'suggestions': [],
                    'created_sources': [],
                }

            # Analyze conversation context
            identified_topics = self.analyze_conversation_context(
                conversation_messages, user_id, session_id
            )

            if not identified_topics:
                return {
                    'status': 'no_topics_identified',
                    'message': 'No research topics identified from recent conversations',
                    'topics': [],
                    'suggestions': [],
                    'created_sources': [],
                }

            # Get existing sources to avoid duplication
            existing_sources = self.service_manager.discovery.list_sources()

            # Generate suggestions
            suggestions = self.suggest_discovery_sources(
                identified_topics, existing_sources
            )

            created_sources = []
            if include_auto_create and suggestions:
                created_sources = self.auto_create_discovery_sources(
                    suggestions, user_id=user_id
                )

            return {
                'status': 'success',
                'topics': [self._topic_to_dict(topic) for topic in identified_topics],
                'suggestions': [
                    self._suggestion_to_dict(suggestion) for suggestion in suggestions
                ],
                'created_sources': created_sources,
                'analysis_summary': {
                    'topics_identified': len(identified_topics),
                    'sources_suggested': len(suggestions),
                    'sources_created': len(
                        [cs for cs in created_sources if cs.get('created', False)]
                    ),
                    'conversation_messages_analyzed': len(conversation_messages),
                },
            }

        except Exception as e:
            logger.error(f'Error getting contextual discovery recommendations: {e}')
            return {
                'status': 'error',
                'message': str(e),
                'topics': [],
                'suggestions': [],
                'created_sources': [],
            }

    def _filter_recent_messages(
        self, messages: list[dict[str, Any]], cutoff_time: datetime
    ) -> list[dict[str, Any]]:
        """Filter messages to only include recent ones within the time window."""
        recent_messages = []

        for message in messages:
            # Try to parse timestamp if available
            timestamp = message.get('timestamp') or message.get('created_at')
            if timestamp:
                try:
                    if isinstance(timestamp, str):
                        msg_time = datetime.fromisoformat(
                            timestamp.replace('Z', '+00:00')
                        )
                    else:
                        msg_time = timestamp

                    if msg_time >= cutoff_time:
                        recent_messages.append(message)
                except Exception:
                    # If timestamp parsing fails, include the message anyway
                    recent_messages.append(message)
            else:
                # If no timestamp, include the message
                recent_messages.append(message)

        return recent_messages

    def _extract_topics_from_text(
        self,
        text: str,
        message_context: dict[str, Any],  # noqa: ARG002
    ) -> list[ResearchTopic]:
        """Extract research topics from a text message."""
        topics = []

        # Check for explicit interest expressions
        for pattern in self.interest_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                topic_text = match.group(1).strip()
                if len(topic_text) > 3:  # Minimum topic length
                    topic = self._create_topic_from_text(topic_text, text, 0.7)
                    if topic:
                        topics.append(topic)

        # Check for domain-specific keywords
        for domain, config in self.domain_patterns.items():
            keyword_matches = []
            for keyword in config['keywords']:
                if keyword.lower() in text:
                    keyword_matches.append(keyword)

            if keyword_matches:
                confidence = min(0.9, len(keyword_matches) * 0.15 + 0.3)
                topic = ResearchTopic(
                    topic=domain.replace('_', ' '),
                    keywords=keyword_matches,
                    confidence=confidence,
                    context_snippets=[text[:200]],
                    suggested_categories=config.get('arxiv_categories', []),
                    last_mentioned=datetime.now(),
                )
                topics.append(topic)

        return topics

    def _create_topic_from_text(
        self, topic_text: str, context: str, base_confidence: float
    ) -> ResearchTopic | None:
        """Create a research topic from extracted text."""
        # Clean and process the topic text
        topic_clean = re.sub(r'[^\w\s]', '', topic_text).strip()
        if len(topic_clean) < 3:
            return None

        # Extract keywords from the topic text
        keywords = []
        words = topic_clean.lower().split()

        # Add individual meaningful words
        for word in words:
            if len(word) > 2 and word not in [
                'the',
                'and',
                'or',
                'of',
                'in',
                'to',
                'for',
            ]:
                keywords.append(word)

        # Add multi-word phrases
        if len(words) > 1:
            keywords.append(topic_clean.lower())

        if not keywords:
            return None

        # Try to match with known domains
        suggested_categories = []
        for _domain, config in self.domain_patterns.items():
            domain_keywords = [kw.lower() for kw in config['keywords']]
            if any(keyword in domain_keywords for keyword in keywords):
                suggested_categories = config.get('arxiv_categories', [])
                break

        return ResearchTopic(
            topic=topic_clean,
            keywords=keywords[:10],  # Limit keywords
            confidence=base_confidence,
            context_snippets=[context[:200]],
            suggested_categories=suggested_categories,
            last_mentioned=datetime.now(),
        )

    def _merge_similar_topics(self, topics: list[ResearchTopic]) -> list[ResearchTopic]:
        """Merge similar topics to avoid duplication."""
        if not topics:
            return []

        merged = {}

        for topic in topics:
            # Find similar existing topic
            similar_key = None
            for key in merged.keys():
                if self._are_topics_similar(topic, merged[key]):
                    similar_key = key
                    break

            if similar_key:
                # Merge with existing topic
                existing = merged[similar_key]
                existing.keywords = list(set(existing.keywords + topic.keywords))
                existing.context_snippets.extend(topic.context_snippets)
                existing.frequency += topic.frequency
                existing.confidence = max(existing.confidence, topic.confidence)
                if topic.suggested_categories:
                    existing.suggested_categories = list(
                        set(existing.suggested_categories + topic.suggested_categories)
                    )
            else:
                # Add as new topic
                merged[topic.topic] = topic

        return list(merged.values())

    def _are_topics_similar(self, topic1: ResearchTopic, topic2: ResearchTopic) -> bool:
        """Check if two topics are similar enough to be merged."""
        # Check topic name similarity
        if topic1.topic.lower() == topic2.topic.lower():
            return True

        # Check keyword overlap
        keywords1 = set(kw.lower() for kw in topic1.keywords)
        keywords2 = set(kw.lower() for kw in topic2.keywords)

        overlap = len(keywords1.intersection(keywords2))
        union = len(keywords1.union(keywords2))

        if union > 0 and overlap / union > 0.4:  # 40% keyword overlap
            return True

        return False

    def _rank_topics_by_confidence(
        self, topics: list[ResearchTopic]
    ) -> list[ResearchTopic]:
        """Rank topics by confidence score and frequency."""
        return sorted(
            topics,
            key=lambda t: (t.confidence * t.frequency, len(t.keywords)),
            reverse=True,
        )

    def _update_topic_history(self, topics: list[ResearchTopic], user_id: str) -> None:
        """Update the topic history for frequency tracking."""
        for topic in topics:
            key = f'{user_id}:{topic.topic.lower()}'
            if key in self.topic_history:
                existing = self.topic_history[key]
                existing.frequency += 1
                existing.last_mentioned = datetime.now()
                existing.keywords = list(set(existing.keywords + topic.keywords))
                existing.confidence = max(existing.confidence, topic.confidence)
            else:
                self.topic_history[key] = topic

    def _generate_topic_suggestions(
        self, topic: ResearchTopic, existing_names: set[str]
    ) -> list[DiscoverySourceSuggestion]:
        """Generate discovery source suggestions for a single topic."""
        suggestions = []

        # Determine best source types for this topic
        source_priorities = self._get_source_priorities_for_topic(topic)

        for source_type, priority in source_priorities.items():
            if source_type == 'arxiv':
                suggestion = self._create_arxiv_suggestion(
                    topic, existing_names, priority
                )
                if suggestion:
                    suggestions.append(suggestion)
            elif source_type == 'pubmed':
                suggestion = self._create_pubmed_suggestion(
                    topic, existing_names, priority
                )
                if suggestion:
                    suggestions.append(suggestion)
            elif source_type == 'crossref':
                suggestion = self._create_crossref_suggestion(
                    topic, existing_names, priority
                )
                if suggestion:
                    suggestions.append(suggestion)

        return suggestions

    def _get_source_priorities_for_topic(
        self, topic: ResearchTopic
    ) -> dict[str, float]:
        """Determine which source types are most appropriate for a topic."""
        priorities = {
            'arxiv': 0.3,
            'crossref': 0.5,
            'pubmed': 0.2,
        }  # Default priorities

        # Adjust based on topic characteristics
        topic_lower = topic.topic.lower()
        keywords_lower = [kw.lower() for kw in topic.keywords]

        # Boost ArXiv for CS/ML/AI topics
        cs_indicators = [
            'machine learning',
            'deep learning',
            'ai',
            'computer',
            'algorithm',
            'neural',
        ]
        if any(
            indicator in topic_lower or any(indicator in kw for kw in keywords_lower)
            for indicator in cs_indicators
        ):
            priorities['arxiv'] = 0.8
            priorities['crossref'] = 0.4

        # Boost PubMed for bio/medical topics
        bio_indicators = ['bio', 'medical', 'health', 'clinical', 'genomic', 'protein']
        if any(
            indicator in topic_lower or any(indicator in kw for kw in keywords_lower)
            for indicator in bio_indicators
        ):
            priorities['pubmed'] = 0.9
            priorities['crossref'] = 0.4
            priorities['arxiv'] = 0.2

        return priorities

    def _create_arxiv_suggestion(
        self, topic: ResearchTopic, existing_names: set[str], priority: float
    ) -> DiscoverySourceSuggestion | None:
        """Create an ArXiv discovery source suggestion."""
        source_name = f'arxiv_{topic.topic.lower().replace(" ", "_")}_auto'
        if source_name in existing_names:
            source_name = f'{source_name}_{datetime.now().strftime("%m%d")}'

        categories = topic.suggested_categories or ['cs.LG', 'cs.AI']

        return DiscoverySourceSuggestion(
            source_name=source_name,
            source_type='arxiv',
            keywords=topic.keywords[:8],  # Limit keywords
            categories=categories,
            confidence=topic.confidence * priority,
            reasoning=f'ArXiv is well-suited for {topic.topic} research with categories {", ".join(categories)}',
            topic_coverage=[topic.topic],
        )

    def _create_pubmed_suggestion(
        self, topic: ResearchTopic, existing_names: set[str], priority: float
    ) -> DiscoverySourceSuggestion | None:
        """Create a PubMed discovery source suggestion."""
        source_name = f'pubmed_{topic.topic.lower().replace(" ", "_")}_auto'
        if source_name in existing_names:
            source_name = f'{source_name}_{datetime.now().strftime("%m%d")}'

        return DiscoverySourceSuggestion(
            source_name=source_name,
            source_type='pubmed',
            keywords=topic.keywords[:8],
            categories=None,
            confidence=topic.confidence * priority,
            reasoning=f'PubMed provides comprehensive biomedical literature for {topic.topic}',
            topic_coverage=[topic.topic],
        )

    def _create_crossref_suggestion(
        self, topic: ResearchTopic, existing_names: set[str], priority: float
    ) -> DiscoverySourceSuggestion | None:
        """Create a CrossRef discovery source suggestion."""
        source_name = f'crossref_{topic.topic.lower().replace(" ", "_")}_auto'
        if source_name in existing_names:
            source_name = f'{source_name}_{datetime.now().strftime("%m%d")}'

        return DiscoverySourceSuggestion(
            source_name=source_name,
            source_type='crossref',
            keywords=topic.keywords[:8],
            categories=None,
            confidence=topic.confidence * priority,
            reasoning=f'CrossRef offers broad interdisciplinary coverage for {topic.topic} research',
            topic_coverage=[topic.topic],
        )

    def _deduplicate_suggestions(
        self, suggestions: list[DiscoverySourceSuggestion]
    ) -> list[DiscoverySourceSuggestion]:
        """Remove duplicate suggestions based on source name and keywords."""
        seen_sources = set()
        unique_suggestions = []

        for suggestion in suggestions:
            key = f'{suggestion.source_name}:{",".join(sorted(suggestion.keywords))}'
            if key not in seen_sources:
                seen_sources.add(key)
                unique_suggestions.append(suggestion)

        return unique_suggestions

    def _create_discovery_source_from_suggestion(
        self, suggestion: DiscoverySourceSuggestion, user_id: str | None = None
    ) -> dict[str, Any]:
        """Create a discovery source from a suggestion."""
        try:
            if suggestion.source_type == 'arxiv':
                source_config = {
                    'name': suggestion.source_name,
                    'source_type': 'api',
                    'description': f'Auto-generated ArXiv source for {", ".join(suggestion.topic_coverage)}',
                    'is_active': True,
                    'api_config': {
                        'source': 'arxiv',
                        'categories': suggestion.categories or ['cs.LG', 'cs.AI'],
                        'keywords': suggestion.keywords,
                        'sort_by': 'lastUpdatedDate',
                        'sort_order': 'descending',
                    },
                    'schedule_config': {
                        'interval_minutes': 24 * 60,  # Daily
                        'max_articles_per_run': 20,
                        'enabled': True,
                    },
                    'query_filters': [],
                }
            elif suggestion.source_type == 'pubmed':
                source_config = {
                    'name': suggestion.source_name,
                    'source_type': 'api',
                    'description': f'Auto-generated PubMed source for {", ".join(suggestion.topic_coverage)}',
                    'is_active': True,
                    'api_config': {
                        'source': 'pubmed',
                        'keywords': suggestion.keywords,
                        'sort_by': 'date',
                        'sort_order': 'descending',
                    },
                    'schedule_config': {
                        'interval_minutes': 48 * 60,  # Every 2 days
                        'max_articles_per_run': 15,
                        'enabled': True,
                    },
                    'query_filters': [],
                }
            elif suggestion.source_type == 'crossref':
                source_config = {
                    'name': suggestion.source_name,
                    'source_type': 'api',
                    'description': f'Auto-generated CrossRef source for {", ".join(suggestion.topic_coverage)}',
                    'is_active': True,
                    'api_config': {
                        'source': 'crossref',
                        'keywords': suggestion.keywords,
                        'sort_by': 'relevance',
                        'sort_order': 'desc',
                    },
                    'schedule_config': {
                        'interval_minutes': 24 * 60,  # Daily
                        'max_articles_per_run': 25,
                        'enabled': True,
                    },
                    'query_filters': [],
                }
            else:
                return {
                    'success': False,
                    'message': f'Unsupported source type: {suggestion.source_type}',
                }

            # Add metadata for auto-created sources
            source_config['metadata'] = {
                'auto_created': True,
                'created_by': 'context_analyzer',
                'user_id': user_id,
                'confidence': suggestion.confidence,
                'reasoning': suggestion.reasoning,
                'created_at': datetime.now().isoformat(),
            }

            from thoth.utilities.schemas import DiscoverySource

            source = DiscoverySource(**source_config)
            self.service_manager.discovery.create_source(source)

            return {
                'success': True,
                'message': f'Successfully created {suggestion.source_type} source: {suggestion.source_name}',
                'source_config': source_config,
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to create discovery source: {e}',
            }

    def _get_recent_conversation_history(
        self,
        user_id: str,
        session_id: str | None = None,  # noqa: ARG002
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get recent conversation history from memory system."""
        try:
            # Try to get conversation history from memory store
            if hasattr(self.service_manager, 'memory') and self.service_manager.memory:
                memory_store = self.service_manager.memory.get_shared_store()
                if memory_store:
                    # Get recent episodic memories that contain conversation data
                    memories = memory_store.read_memories(
                        user_id=user_id,
                        scope='episodic',
                        limit=100,  # Get recent memories
                    )

                    # Convert memories to message format
                    messages = []
                    cutoff_time = datetime.now() - timedelta(hours=hours)

                    for memory in memories:
                        created_at = memory.get('created_at')
                        if created_at:
                            try:
                                memory_time = datetime.fromisoformat(
                                    created_at.replace('Z', '+00:00')
                                )
                                if memory_time >= cutoff_time:
                                    messages.append(
                                        {
                                            'content': memory.get('content', ''),
                                            'role': memory.get('role', 'user'),
                                            'timestamp': created_at,
                                            'created_at': created_at,
                                        }
                                    )
                            except Exception:
                                continue

                    return messages

            # Fallback: return empty list if no memory system available
            return []

        except Exception as e:
            logger.error(f'Error retrieving conversation history: {e}')
            return []

    def _topic_to_dict(self, topic: ResearchTopic) -> dict[str, Any]:
        """Convert ResearchTopic to dictionary representation."""
        return {
            'topic': topic.topic,
            'keywords': topic.keywords,
            'confidence': round(topic.confidence, 3),
            'context_snippets': topic.context_snippets[:2],  # Limit snippets
            'suggested_categories': topic.suggested_categories,
            'frequency': topic.frequency,
            'last_mentioned': topic.last_mentioned.isoformat()
            if topic.last_mentioned
            else None,
        }

    def _suggestion_to_dict(
        self, suggestion: DiscoverySourceSuggestion
    ) -> dict[str, Any]:
        """Convert DiscoverySourceSuggestion to dictionary representation."""
        return {
            'source_name': suggestion.source_name,
            'source_type': suggestion.source_type,
            'keywords': suggestion.keywords,
            'categories': suggestion.categories,
            'confidence': round(suggestion.confidence, 3),
            'reasoning': suggestion.reasoning,
            'topic_coverage': suggestion.topic_coverage,
        }

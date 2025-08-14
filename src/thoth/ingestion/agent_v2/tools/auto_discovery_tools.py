"""
Auto-Discovery Tools for Chat Context Integration

This module provides tools that analyze conversation context to automatically
suggest and create discovery sources based on user research interests.
"""

from pydantic import BaseModel, Field

from thoth.discovery.context_analyzer import ChatContextAnalyzer
from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool
from thoth.ingestion.agent_v2.tools.decorators import tool


class AnalyzeResearchContextInput(BaseModel):
    """Input schema for analyzing research context."""

    user_id: str = Field(description='User identifier for context analysis')
    session_id: str | None = Field(
        default=None, description='Optional session identifier'
    )
    lookback_hours: int = Field(
        default=24, description='Hours to look back for context analysis'
    )


@tool
class AnalyzeResearchContextTool(BaseThothTool):
    """Analyze conversation context to identify research topics and interests."""

    name: str = 'analyze_research_context'
    description: str = (
        'Analyzes recent conversation history to identify research topics, interests, '
        'and potential areas for automated paper discovery. This tool examines user '
        'messages to understand what research areas they are interested in.'
    )
    args_schema: type[BaseModel] = AnalyzeResearchContextInput

    def _run(
        self,
        user_id: str,
        session_id: str | None = None,
        lookback_hours: int = 24,  # noqa: ARG002
    ) -> str:
        """Analyze research context from conversation history."""
        try:
            # Initialize context analyzer
            analyzer = ChatContextAnalyzer(self.service_manager)

            # Get contextual recommendations
            recommendations = analyzer.get_contextual_discovery_recommendations(
                user_id=user_id,
                session_id=session_id,
                include_auto_create=False,  # Don't auto-create yet, just analyze
            )

            if recommendations.get('status') == 'no_conversation_data':
                return (
                    '**No Recent Conversation Data Found**\n\n'
                    "I couldn't find any recent conversation history to analyze for research topics. "
                    "Start discussing your research interests, and I'll be able to suggest relevant "
                    'discovery sources to keep you updated with the latest papers.'
                )

            if recommendations.get('status') == 'no_topics_identified':
                return (
                    '**No Research Topics Identified**\n\n'
                    "I analyzed your recent conversations but didn't identify any specific research topics. "
                    "Try mentioning research areas you're interested in, papers you're reading, or "
                    "projects you're working on, and I'll suggest automated discovery sources."
                )

            if recommendations.get('status') != 'success':
                return f'❌ **Analysis Error**: {recommendations.get("message", "Unknown error occurred")}'

            # Format the analysis results
            topics = recommendations.get('topics', [])
            suggestions = recommendations.get('suggestions', [])
            summary = recommendations.get('analysis_summary', {})

            result = ['**🔍 Research Context Analysis Results**\n']

            # Summary stats
            result.append('**📊 Analysis Summary:**')
            result.append(
                f'- Conversation messages analyzed: {summary.get("conversation_messages_analyzed", 0)}'
            )
            result.append(
                f'- Research topics identified: {summary.get("topics_identified", 0)}'
            )
            result.append(
                f'- Discovery sources suggested: {summary.get("sources_suggested", 0)}\n'
            )

            # Identified topics
            if topics:
                result.append('**🎯 Research Topics Identified:**')
                for i, topic in enumerate(topics[:5], 1):  # Show top 5
                    confidence_bar = '●' * int(topic['confidence'] * 5)
                    result.append(f'{i}. **{topic["topic"].title()}**')
                    result.append(
                        f'   - Confidence: {confidence_bar} ({topic["confidence"]:.1%})'
                    )
                    result.append(f'   - Keywords: {", ".join(topic["keywords"][:6])}')
                    if topic.get('suggested_categories'):
                        result.append(
                            f'   - Suggested categories: {", ".join(topic["suggested_categories"][:3])}'
                        )
                result.append('')

            # Discovery source suggestions
            if suggestions:
                result.append('**🚀 Recommended Discovery Sources:**')
                for i, suggestion in enumerate(suggestions[:3], 1):  # Show top 3
                    confidence_bar = '●' * int(suggestion['confidence'] * 5)
                    result.append(
                        f'{i}. **{suggestion["source_name"]}** ({suggestion["source_type"].upper()})'
                    )
                    result.append(
                        f'   - Confidence: {confidence_bar} ({suggestion["confidence"]:.1%})'
                    )
                    result.append(
                        f'   - Keywords: {", ".join(suggestion["keywords"][:5])}'
                    )
                    result.append(f'   - Reasoning: {suggestion["reasoning"]}')
                result.append('')

                result.append('**💡 Next Steps:**')
                result.append(
                    '- Use `suggest_discovery_sources` to get detailed recommendations'
                )
                result.append(
                    '- Use `auto_create_discovery_sources` to automatically create high-confidence sources'
                )
                result.append(
                    '- Use `create_arxiv_source` or `create_pubmed_source` to manually create specific sources'
                )
            else:
                result.append('**💡 No Discovery Source Suggestions**')
                result.append(
                    'The identified topics may already be covered by existing sources, '
                )
                result.append(
                    'or may not have sufficient confidence for source creation.'
                )

            return '\n'.join(result)

        except Exception as e:
            return self.handle_error(e, 'analyzing research context')


class SuggestDiscoverySourcesInput(BaseModel):
    """Input schema for suggesting discovery sources."""

    user_id: str = Field(description='User identifier for personalized suggestions')
    session_id: str | None = Field(
        default=None, description='Optional session identifier'
    )
    min_confidence: float = Field(
        default=0.5, description='Minimum confidence threshold for suggestions'
    )


@tool
class SuggestDiscoverySourcesTool(BaseThothTool):
    """Suggest discovery sources based on conversation context analysis."""

    name: str = 'suggest_discovery_sources'
    description: str = (
        'Generates specific discovery source suggestions based on recent conversation '
        'analysis. Provides detailed recommendations for ArXiv, PubMed, and CrossRef '
        'sources tailored to identified research interests.'
    )
    args_schema: type[BaseModel] = SuggestDiscoverySourcesInput

    def _run(
        self, user_id: str, session_id: str | None = None, min_confidence: float = 0.5
    ) -> str:
        """Generate discovery source suggestions."""
        try:
            analyzer = ChatContextAnalyzer(self.service_manager)

            recommendations = analyzer.get_contextual_discovery_recommendations(
                user_id=user_id, session_id=session_id, include_auto_create=False
            )

            if recommendations.get('status') != 'success':
                return f'❌ Unable to generate suggestions: {recommendations.get("message", "Analysis failed")}'

            suggestions = recommendations.get('suggestions', [])
            filtered_suggestions = [
                s for s in suggestions if s['confidence'] >= min_confidence
            ]

            if not filtered_suggestions:
                return (
                    f'**No High-Confidence Suggestions Found**\n\n'
                    f'No discovery source suggestions found with confidence ≥ {min_confidence:.1%}. '
                    f'Try lowering the minimum confidence threshold or discuss more specific research topics.'
                )

            result = ['**🎯 Discovery Source Suggestions**\n']

            result.append(
                f'**Filter:** Showing suggestions with confidence ≥ {min_confidence:.1%}\n'
            )

            for i, suggestion in enumerate(filtered_suggestions, 1):
                confidence_stars = '★' * int(suggestion['confidence'] * 5)

                result.append(f'**{i}. {suggestion["source_name"]}**')
                result.append(
                    f'   - **Source Type:** {suggestion["source_type"].upper()}'
                )
                result.append(
                    f'   - **Confidence:** {confidence_stars} ({suggestion["confidence"]:.1%})'
                )
                result.append(f'   - **Keywords:** {", ".join(suggestion["keywords"])}')

                if suggestion.get('categories'):
                    result.append(
                        f'   - **Categories:** {", ".join(suggestion["categories"])}'
                    )

                result.append(f'   - **Why this source:** {suggestion["reasoning"]}')
                result.append(
                    f'   - **Covers topics:** {", ".join(suggestion["topic_coverage"])}'
                )
                result.append('')

            result.append('**🚀 Ready to Create Sources:**')
            result.append(
                '- Use `auto_create_discovery_sources` to create all high-confidence sources automatically'
            )
            result.append(
                '- Use `create_arxiv_source`, `create_pubmed_source`, or `create_crossref_source` for manual creation'
            )
            result.append('- Use `list_discovery_sources` to see existing sources')

            return '\n'.join(result)

        except Exception as e:
            return self.handle_error(e, 'generating discovery source suggestions')


class AutoCreateDiscoverySourcesInput(BaseModel):
    """Input schema for auto-creating discovery sources."""

    user_id: str = Field(
        description='User identifier for tracking auto-created sources'
    )
    session_id: str | None = Field(
        default=None, description='Optional session identifier'
    )
    confidence_threshold: float = Field(
        default=0.75, description='Minimum confidence threshold for automatic creation'
    )
    max_sources: int = Field(
        default=3, description='Maximum number of sources to auto-create'
    )


@tool
class AutoCreateDiscoverySourcesTool(BaseThothTool):
    """Automatically create discovery sources based on high-confidence suggestions."""

    name: str = 'auto_create_discovery_sources'
    description: str = (
        'Automatically creates discovery sources for high-confidence research topics '
        'identified from conversation context. This saves time by setting up relevant '
        'automated paper discovery without manual configuration.'
    )
    args_schema: type[BaseModel] = AutoCreateDiscoverySourcesInput

    def _run(
        self,
        user_id: str,
        session_id: str | None = None,
        confidence_threshold: float = 0.75,
        max_sources: int = 3,  # noqa: ARG002
    ) -> str:
        """Auto-create discovery sources from high-confidence suggestions."""
        try:
            analyzer = ChatContextAnalyzer(self.service_manager)

            recommendations = analyzer.get_contextual_discovery_recommendations(
                user_id=user_id,
                session_id=session_id,
                include_auto_create=True,  # Enable auto-creation
            )

            if recommendations.get('status') != 'success':
                return f'❌ Unable to auto-create sources: {recommendations.get("message", "Analysis failed")}'

            created_sources = recommendations.get('created_sources', [])

            if not created_sources:
                suggestions = recommendations.get('suggestions', [])
                high_conf_suggestions = [
                    s for s in suggestions if s['confidence'] >= confidence_threshold
                ]

                if not high_conf_suggestions:
                    return (
                        f'**No High-Confidence Sources to Create**\n\n'
                        f'No suggestions found with confidence ≥ {confidence_threshold:.1%} for automatic creation. '
                        f'Consider lowering the threshold or manually creating sources using the suggest tools.'
                    )
                else:
                    return (
                        f'**Auto-Creation Skipped**\n\n'
                        f'Found {len(high_conf_suggestions)} high-confidence suggestions but auto-creation '
                        f'was not performed. Try running this command again or check for existing sources '
                        f'that may already cover these topics.'
                    )

            result = ['**🤖 Auto-Created Discovery Sources**\n']

            successful_creates = [
                cs for cs in created_sources if cs.get('created', False)
            ]
            failed_creates = [
                cs for cs in created_sources if not cs.get('created', False)
            ]

            if successful_creates:
                result.append(
                    f'**✅ Successfully Created ({len(successful_creates)} sources):**'
                )
                for cs in successful_creates:
                    suggestion = cs['suggestion']
                    result.append(
                        f'- **{cs["source_name"]}** ({suggestion["source_type"].upper()})'
                    )
                    result.append(f'  - Keywords: {", ".join(suggestion["keywords"])}')
                    result.append(f'  - Confidence: {suggestion["confidence"]:.1%}')
                    if suggestion.get('categories'):
                        result.append(
                            f'  - Categories: {", ".join(suggestion["categories"])}'
                        )
                result.append('')

            if failed_creates:
                result.append(
                    f'**❌ Failed to Create ({len(failed_creates)} sources):**'
                )
                for cs in failed_creates:
                    result.append(
                        f'- **{cs["source_name"]}**: {cs.get("message", "Unknown error")}'
                    )
                result.append('')

            if successful_creates:
                result.append('**🎉 What Happens Next:**')
                result.append(
                    '- These sources will run automatically based on their schedules'
                )
                result.append(
                    '- New papers will be discovered, filtered, and downloaded'
                )
                result.append('- Use `list_discovery_sources` to view all your sources')
                result.append(
                    '- Use `run_discovery` to manually trigger discovery runs'
                )
                result.append('- Check `knowledge/agent/pdfs/` for downloaded papers')

            return '\n'.join(result)

        except Exception as e:
            return self.handle_error(e, 'auto-creating discovery sources')


class GetResearchInsightsInput(BaseModel):
    """Input schema for getting research insights."""

    user_id: str = Field(description='User identifier for personalized insights')
    session_id: str | None = Field(
        default=None, description='Optional session identifier'
    )
    days_back: int = Field(
        default=7, description='Number of days to look back for insights'
    )


@tool
class GetResearchInsightsTool(BaseThothTool):
    """Get insights about research patterns and discovery opportunities."""

    name: str = 'get_research_insights'
    description: str = (
        'Provides insights about research patterns, topic trends, and discovery '
        'opportunities based on conversation history and existing discovery sources. '
        'Helps identify gaps in current discovery coverage.'
    )
    args_schema: type[BaseModel] = GetResearchInsightsInput

    def _run(
        self,
        user_id: str,
        session_id: str | None = None,
        days_back: int = 7,  # noqa: ARG002
    ) -> str:
        """Generate research insights and discovery opportunities."""
        try:
            analyzer = ChatContextAnalyzer(self.service_manager)

            # Get current discovery sources
            existing_sources = self.service_manager.discovery.list_sources()

            # Analyze context with longer lookback
            recommendations = analyzer.get_contextual_discovery_recommendations(
                user_id=user_id, session_id=session_id, include_auto_create=False
            )

            result = ['**🔬 Research Insights & Discovery Analysis**\n']

            # Current discovery coverage
            result.append('**📊 Current Discovery Coverage:**')
            if existing_sources:
                active_sources = [s for s in existing_sources if s.is_active]
                result.append(f'- Total sources: {len(existing_sources)}')
                result.append(f'- Active sources: {len(active_sources)}')

                # Categorize sources by type
                source_types = {}
                for source in active_sources:
                    source_type = getattr(source, 'source_type', 'unknown')
                    api_source = None
                    if hasattr(source, 'api_config') and source.api_config:
                        api_source = source.api_config.get('source', source_type)
                    display_type = api_source or source_type
                    source_types[display_type] = source_types.get(display_type, 0) + 1

                if source_types:
                    result.append('- Source distribution:')
                    for source_type, count in source_types.items():
                        result.append(f'  - {source_type.title()}: {count} sources')
            else:
                result.append('- No discovery sources configured yet')
            result.append('')

            # Research interests analysis
            if recommendations.get('status') == 'success':
                topics = recommendations.get('topics', [])
                suggestions = recommendations.get('suggestions', [])

                if topics:
                    result.append('**🎯 Research Interest Patterns:**')
                    for i, topic in enumerate(topics[:3], 1):
                        result.append(
                            f'{i}. **{topic["topic"].title()}** (confidence: {topic["confidence"]:.1%})'
                        )
                        result.append(f'   - Frequency: {topic["frequency"]} mentions')
                        if topic.get('suggested_categories'):
                            result.append(
                                f'   - Relevant categories: {", ".join(topic["suggested_categories"][:2])}'
                            )
                    result.append('')

                # Coverage gaps
                if suggestions:
                    uncovered_topics = []
                    for suggestion in suggestions:
                        if suggestion['confidence'] >= 0.6:
                            uncovered_topics.append(suggestion)

                    if uncovered_topics:
                        result.append('**⚠️ Discovery Coverage Gaps:**')
                        result.append(
                            'These research areas might benefit from dedicated discovery sources:'
                        )
                        for topic in uncovered_topics[:3]:
                            result.append(
                                f'- **{topic["source_name"]}**: {", ".join(topic["keywords"][:4])}'
                            )
                        result.append('')

            # Discovery recommendations
            result.append('**💡 Recommendations:**')
            if not existing_sources:
                result.append(
                    '- Start by creating discovery sources for your main research interests'
                )
                result.append(
                    '- Use `analyze_research_context` to identify research topics from conversations'
                )
                result.append('- Use `auto_create_discovery_sources` for quick setup')
            else:
                result.append(
                    '- Review your existing sources to ensure they cover current interests'
                )
                result.append(
                    '- Consider running discovery manually with `run_discovery` to get fresh papers'
                )
                if recommendations.get('suggestions'):
                    result.append(
                        '- Explore additional topics with `suggest_discovery_sources`'
                    )

            result.append(
                '- Use `list_discovery_sources` to review current configuration'
            )
            result.append(
                '- Check discovery statistics to see what papers are being found'
            )

            return '\n'.join(result)

        except Exception as e:
            return self.handle_error(e, 'generating research insights')

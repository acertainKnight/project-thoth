"""
MCP-compliant tag management tools.

This module provides tools for managing tags, consolidating similar tags,
and suggesting new tags for articles.
"""

from typing import Any

from ..base_tools import MCPTool, MCPToolCallResult, NoInputTool


class ConsolidateTagsMCPTool(NoInputTool):
    """MCP tool for consolidating similar tags into canonical forms."""

    @property
    def name(self) -> str:
        return 'consolidate_tags'

    @property
    def description(self) -> str:
        return 'Consolidate similar tags into canonical forms using AI analysis to reduce tag duplication and improve organization'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Consolidate tags across the collection."""
        try:
            # Use the tag service to consolidate tags
            result = self.service_manager.tag.consolidate_only()

            response_text = '🏷️ **Tag Consolidation Complete**\n\n'
            response_text += '📊 **Summary:**\n'
            response_text += f'  - Articles processed: {result["articles_processed"]}\n'
            response_text += f'  - Articles updated: {result["articles_updated"]}\n'
            response_text += f'  - Tags consolidated: {result["tags_consolidated"]}\n'
            response_text += f'  - Original tag count: {result["original_tag_count"]}\n'
            response_text += f'  - Final tag count: {result["final_tag_count"]}\n\n'

            # Show consolidation mappings if available
            if result.get('consolidation_mappings'):
                mappings = result['consolidation_mappings']
                if mappings:
                    response_text += '🔄 **Tag Mappings Applied:**\n'
                    for old_tag, new_tag in list(mappings.items())[
                        :10
                    ]:  # Show first 10
                        response_text += f"  - '{old_tag}' → '{new_tag}'\n"

                    if len(mappings) > 10:
                        response_text += (
                            f'  ... and {len(mappings) - 10} more mappings\n'
                        )
                    response_text += '\n'

            response_text += '✅ Tag consolidation completed. Similar tags have been merged using AI analysis.'

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            return self.handle_error(e)


class SuggestTagsMCPTool(MCPTool):
    """MCP tool for suggesting additional tags for articles."""

    @property
    def name(self) -> str:
        return 'suggest_tags'

    @property
    def description(self) -> str:
        return 'Suggest additional relevant tags for articles based on content analysis and existing tag vocabulary'

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'article_identifier': {
                    'type': 'string',
                    'description': 'Article title, DOI, or arXiv ID to suggest tags for. If not provided, suggests tags for all articles.',
                },
                'force_all': {
                    'type': 'boolean',
                    'description': 'Force tag suggestions for all articles in the collection',
                    'default': False,
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Suggest tags for articles."""
        try:
            article_identifier = arguments.get('article_identifier')
            force_all = arguments.get('force_all', False)

            if article_identifier and not force_all:
                # Suggest tags for a specific article
                # First find the article
                search_results = self.service_manager.rag.search(
                    query=article_identifier, k=1
                )

                if not search_results:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': f'❌ Article not found: {article_identifier}',
                            }
                        ],
                        isError=True,
                    )

                article = search_results[0]
                title = article.get('title', 'Unknown')
                content = article.get('content', '')
                metadata = article.get('metadata', {})
                current_tags = metadata.get('tags', [])

                # Get available tag vocabulary
                available_tags = self.service_manager.tag.extract_all_tags()

                if not available_tags:
                    return MCPToolCallResult(
                        content=[
                            {
                                'type': 'text',
                                'text': '❌ No existing tag vocabulary found. Process some articles first to build a tag vocabulary.',
                            }
                        ],
                        isError=True,
                    )

                # Get tag suggestions
                suggestion_result = self.service_manager.tag.suggest_tags(
                    title=title,
                    abstract=content[:1000],  # Use first 1000 chars as abstract
                    current_tags=current_tags,
                    available_tags=available_tags,
                )

                suggested_tags = suggestion_result.get('suggested_tags', [])
                reasoning = suggestion_result.get('reasoning', '')

                response_text = f'🏷️ **Tag Suggestions for:** {title}\n\n'
                response_text += f'**Current Tags:** {", ".join(current_tags) if current_tags else "None"}\n\n'

                if suggested_tags:
                    response_text += (
                        f'**Suggested Tags:** {", ".join(suggested_tags)}\n\n'
                    )
                    response_text += f'**Reasoning:** {reasoning}\n\n'
                    response_text += '💡 **Note:** Use `update_article_metadata` to apply these suggestions.'
                else:
                    response_text += '✅ No additional tags suggested. Current tags appear comprehensive.'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text}]
                )

            else:
                # Suggest tags for all articles
                result = self.service_manager.tag.suggest_additional()

                response_text = '🏷️ **Tag Suggestions Complete**\n\n'
                response_text += '📊 **Summary:**\n'
                response_text += (
                    f'  - Articles processed: {result["articles_processed"]}\n'
                )
                response_text += f'  - Articles updated: {result["articles_updated"]}\n'
                response_text += f'  - Tags added: {result["tags_added"]}\n'
                response_text += (
                    f'  - Vocabulary size: {result.get("vocabulary_size", 0)}\n\n'
                )

                if result['articles_updated'] > 0:
                    response_text += '✅ Additional tags have been suggested and applied to articles that could benefit from better tagging.'
                else:
                    response_text += '✅ All articles already have comprehensive tags. No additional suggestions needed.'

                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': response_text}]
                )

        except Exception as e:
            return self.handle_error(e)


class ManageTagVocabularyMCPTool(NoInputTool):
    """MCP tool for viewing and managing the tag vocabulary."""

    @property
    def name(self) -> str:
        return 'manage_tag_vocabulary'

    @property
    def description(self) -> str:
        return 'View and analyze the current tag vocabulary, including usage statistics and tag distribution'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Get tag vocabulary and statistics."""
        try:
            # Extract all tags from the collection
            all_tags = self.service_manager.tag.extract_all_tags()

            if not all_tags:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': '📚 No tags found in the collection. Process some articles first to build a tag vocabulary.',
                        }
                    ]
                )

            # Get tag usage statistics by sampling articles
            tag_usage = {}
            sample_results = self.service_manager.rag.search(query='', k=100)

            for result in sample_results:
                metadata = result.get('metadata', {})
                article_tags = metadata.get('tags', [])

                for tag in article_tags:
                    tag_usage[tag] = tag_usage.get(tag, 0) + 1

            # Sort tags by usage
            sorted_tags = sorted(tag_usage.items(), key=lambda x: x[1], reverse=True)

            response_text = '🏷️ **Tag Vocabulary Management**\n\n'
            response_text += '📊 **Overview:**\n'
            response_text += f'  - Total unique tags: {len(all_tags)}\n'
            response_text += f'  - Tags in use: {len(tag_usage)}\n'
            response_text += f'  - Unused tags: {len(all_tags) - len(tag_usage)}\n\n'

            # Show most popular tags
            if sorted_tags:
                response_text += '🔥 **Most Popular Tags:**\n'
                for i, (tag, count) in enumerate(sorted_tags[:15], 1):
                    response_text += f'  {i:2d}. {tag} ({count} articles)\n'

                if len(sorted_tags) > 15:
                    response_text += f'  ... and {len(sorted_tags) - 15} more tags\n'
                response_text += '\n'

            # Show tags that might need consolidation (similar names)
            potentially_similar = []
            for i, tag1 in enumerate(all_tags):
                for _j, tag2 in enumerate(all_tags[i + 1 :], i + 1):
                    # Simple similarity check - contains one in the other
                    if (
                        tag1.lower() in tag2.lower()
                        or tag2.lower() in tag1.lower()
                        or (
                            abs(len(tag1) - len(tag2)) <= 2
                            and sum(
                                a != b
                                for a, b in zip(
                                    tag1.lower(), tag2.lower(), strict=False
                                )
                            )
                            <= 2
                        )
                    ):
                        potentially_similar.append((tag1, tag2))
                        if len(potentially_similar) >= 10:  # Limit to avoid spam
                            break
                if len(potentially_similar) >= 10:
                    break

            if potentially_similar:
                response_text += (
                    '🔍 **Potentially Similar Tags (may need consolidation):**\n'
                )
                for tag1, tag2 in potentially_similar[:10]:
                    usage1 = tag_usage.get(tag1, 0)
                    usage2 = tag_usage.get(tag2, 0)
                    response_text += f"  - '{tag1}' ({usage1}) ↔ '{tag2}' ({usage2})\n"
                response_text += '\n💡 Use `consolidate_tags` to merge similar tags automatically.\n\n'

            response_text += '🛠️ **Available Actions:**\n'
            response_text += '  - `consolidate_tags` - Merge similar tags using AI\n'
            response_text += '  - `suggest_tags` - Add missing tags to articles\n'

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': response_text.strip()}]
            )

        except Exception as e:
            return self.handle_error(e)


class ConsolidateAndRetagMCPTool(NoInputTool):
    """MCP tool for comprehensive tag consolidation and retagging."""

    @property
    def name(self) -> str:
        return 'consolidate_and_retag'

    @property
    def description(self) -> str:
        return 'Perform comprehensive tag consolidation and suggest additional tags for all articles in one operation'

    async def execute(self, _arguments: dict[str, Any]) -> MCPToolCallResult:
        """Consolidate tags and suggest additional tags."""
        try:
            # Use the tag service's comprehensive consolidation and retagging
            result = self.service_manager.tag.consolidate_and_retag()

            response_text = '🏷️ **Comprehensive Tag Management Complete**\n\n'
            response_text += '📊 **Summary:**\n'
            response_text += f'  - Articles processed: {result["articles_processed"]}\n'
            response_text += f'  - Articles updated: {result["articles_updated"]}\n'
            response_text += f'  - Tags consolidated: {result["tags_consolidated"]}\n'
            response_text += f'  - Additional tags added: {result["tags_added"]}\n'
            response_text += f'  - Original tag count: {result["original_tag_count"]}\n'
            response_text += f'  - Final tag count: {result["final_tag_count"]}\n\n'

            # Show some consolidation mappings
            if result.get('consolidation_mappings'):
                mappings = result['consolidation_mappings']
                if mappings:
                    response_text += '🔄 **Sample Tag Consolidations:**\n'
                    for old_tag, new_tag in list(mappings.items())[:5]:
                        response_text += f"  - '{old_tag}' → '{new_tag}'\n"

                    if len(mappings) > 5:
                        response_text += (
                            f'  ... and {len(mappings) - 5} more consolidations\n'
                        )
                    response_text += '\n'

            efficiency_improvement = 0
            if result['original_tag_count'] > 0:
                efficiency_improvement = (
                    (result['original_tag_count'] - result['final_tag_count'])
                    / result['original_tag_count']
                ) * 100

            response_text += '📈 **Impact:**\n'
            response_text += (
                f'  - Tag vocabulary reduced by {efficiency_improvement:.1f}%\n'
            )
            response_text += '  - Improved organization and searchability\n'
            response_text += '  - Enhanced tag consistency across collection\n\n'

            response_text += '✅ Your research collection now has a clean, consolidated tag vocabulary with AI-suggested enhancements.'

            return MCPToolCallResult(content=[{'type': 'text', 'text': response_text}])

        except Exception as e:
            return self.handle_error(e)

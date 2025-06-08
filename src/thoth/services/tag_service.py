"""
Tag service for managing tag consolidation and suggestions.

This module consolidates tag-related operations from TagConsolidator
and related components.
"""

from typing import Any

from thoth.analyze.tag_consolidator import TagConsolidator
from thoth.knowledge.graph import CitationGraph
from thoth.services.base import BaseService, ServiceError


class TagService(BaseService):
    """
    Service for managing tag operations.

    This service consolidates:
    - Tag extraction from citation graph
    - Tag consolidation and normalization
    - Tag suggestions for articles
    - Tag vocabulary management
    """

    def __init__(
        self,
        config=None,
        tag_consolidator: TagConsolidator | None = None,
        citation_tracker: CitationGraph = None,
        llm_service=None,
    ):
        """
        Initialize the TagService.

        Args:
            config: Optional configuration object
            tag_consolidator: Optional TagConsolidator instance
            citation_tracker: Citation tracker instance for accessing graph
            llm_service: LLM service instance
        """
        super().__init__(config)
        self._tag_consolidator = tag_consolidator
        self._citation_tracker = citation_tracker
        self._consolidator: TagConsolidator | None = None
        self._llm_service = llm_service

    def initialize(self) -> None:
        """Initialize the tag service."""
        self.logger.info('Tag service initialized')

    @property
    def tag_consolidator(self) -> TagConsolidator:
        """Get or create the tag consolidator."""
        if self._tag_consolidator is None:
            self._tag_consolidator = TagConsolidator(
                consolidate_model=self.config.tag_consolidator_llm_config.consolidate_model,
                suggest_model=self.config.tag_consolidator_llm_config.suggest_model,
                map_model=self.config.tag_consolidator_llm_config.map_model,
                openrouter_api_key=self.config.api_keys.openrouter_key,
                prompts_dir=self.config.prompts_dir,
                model_kwargs=self.config.tag_consolidator_llm_config.model_settings.model_dump(),
            )
        return self._tag_consolidator

    def extract_all_tags(self) -> list[str]:
        """
        Extract all unique tags from the citation graph.

        Returns:
            list[str]: All unique tags

        Raises:
            ServiceError: If extraction fails
        """
        try:
            if not self._citation_tracker:
                raise ServiceError('Citation tracker not available')

            tags = self.tag_consolidator.extract_all_tags_from_graph(
                self._citation_tracker
            )

            self.log_operation('tags_extracted', count=len(tags))

            return tags

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'extracting tags')) from e

    def consolidate_tags(self, existing_tags: list[str]) -> dict[str, Any]:
        """
        Consolidate similar tags into canonical forms.

        Args:
            existing_tags: List of existing tags to consolidate

        Returns:
            dict[str, Any]: Consolidation results including mappings

        Raises:
            ServiceError: If consolidation fails
        """
        try:
            self.validate_input(existing_tags=existing_tags)

            if not existing_tags:
                return {
                    'tag_mappings': {},
                    'consolidated_tags': [],
                    'reasoning': {},
                }

            response = self.tag_consolidator.consolidate_tags(existing_tags)

            result = {
                'tag_mappings': response.tag_mappings,
                'consolidated_tags': response.consolidated_tags,
                'reasoning': response.reasoning,
            }

            self.log_operation(
                'tags_consolidated',
                input_count=len(existing_tags),
                output_count=len(response.consolidated_tags),
            )

            return result

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'consolidating tags')) from e

    def suggest_tags(
        self,
        title: str,
        abstract: str,
        current_tags: list[str],
        available_tags: list[str],
    ) -> dict[str, Any]:
        """
        Suggest additional tags for an article.

        Args:
            title: Article title
            abstract: Article abstract
            current_tags: Currently assigned tags
            available_tags: Available tag vocabulary

        Returns:
            dict[str, Any]: Suggested tags and reasoning

        Raises:
            ServiceError: If suggestion fails
        """
        try:
            self.validate_input(
                title=title,
                abstract=abstract,
                available_tags=available_tags,
            )

            if not abstract or not available_tags:
                return {
                    'suggested_tags': [],
                    'reasoning': 'No abstract or available tags',
                }

            response = self.tag_consolidator.suggest_additional_tags(
                title=title,
                abstract=abstract,
                current_tags=current_tags or [],
                available_tags=available_tags,
            )

            result = {
                'suggested_tags': response.suggested_tags,
                'reasoning': response.reasoning,
            }

            self.log_operation(
                'tags_suggested',
                article=title,
                suggestions=len(response.suggested_tags),
            )

            return result

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f"suggesting tags for '{title}'")
            ) from e

    def consolidate_and_retag_all(self) -> dict[str, Any]:
        """
        Consolidate all tags and retag all articles.

        Returns:
            dict[str, Any]: Statistics about the operation

        Raises:
            ServiceError: If operation fails
        """
        try:
            if not self._citation_tracker:
                raise ServiceError('Citation tracker not available')

            # Extract existing tags
            existing_tags = self.extract_all_tags()
            if not existing_tags:
                return {
                    'articles_processed': 0,
                    'articles_updated': 0,
                    'tags_consolidated': 0,
                    'tags_added': 0,
                    'original_tag_count': 0,
                    'final_tag_count': 0,
                }

            # Consolidate tags
            consolidation_result = self.consolidate_tags(existing_tags)
            all_available_tags = consolidation_result['consolidated_tags']

            # Process each article
            stats = self._process_articles_for_tags(
                consolidation_result['tag_mappings'],
                all_available_tags,
            )

            # Add consolidation info to stats
            stats.update(
                {
                    'tags_consolidated': len(consolidation_result['tag_mappings']),
                    'original_tag_count': len(existing_tags),
                    'final_tag_count': len(all_available_tags),
                    'consolidation_mappings': consolidation_result['tag_mappings'],
                    'all_available_tags': all_available_tags,
                }
            )

            self.log_operation(
                'all_tags_consolidated_and_retagged',
                articles_processed=stats['articles_processed'],
                articles_updated=stats['articles_updated'],
                tags_added=stats['tags_added'],
            )

            return stats

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, 'consolidating and retagging all articles')
            ) from e

    def consolidate_only(self) -> dict[str, Any]:
        """
        Consolidate tags without suggesting new ones.

        Returns:
            dict[str, Any]: Statistics about the operation

        Raises:
            ServiceError: If operation fails
        """
        try:
            if not self._citation_tracker:
                raise ServiceError('Citation tracker not available')

            # Extract existing tags
            existing_tags = self.extract_all_tags()
            if not existing_tags:
                return {
                    'articles_processed': 0,
                    'articles_updated': 0,
                    'tags_consolidated': 0,
                    'original_tag_count': 0,
                    'final_tag_count': 0,
                }

            # Consolidate tags
            consolidation_result = self.consolidate_tags(existing_tags)

            # Apply consolidation mappings only
            stats = self._apply_tag_mappings(consolidation_result['tag_mappings'])

            # Add consolidation info to stats
            stats.update(
                {
                    'tags_consolidated': len(consolidation_result['tag_mappings']),
                    'original_tag_count': len(existing_tags),
                    'final_tag_count': len(consolidation_result['consolidated_tags']),
                    'consolidation_mappings': consolidation_result['tag_mappings'],
                    'all_available_tags': consolidation_result['consolidated_tags'],
                }
            )

            self.log_operation(
                'tags_consolidated_only',
                articles_processed=stats['articles_processed'],
                articles_updated=stats['articles_updated'],
            )

            return stats

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'consolidating tags only')) from e

    def suggest_additional_tags_all(self) -> dict[str, Any]:
        """
        Suggest additional tags for all articles.

        Returns:
            dict[str, Any]: Statistics about the operation

        Raises:
            ServiceError: If operation fails
        """
        try:
            if not self._citation_tracker:
                raise ServiceError('Citation tracker not available')

            # Get available tags
            available_tags = self.extract_all_tags()
            if not available_tags:
                return {
                    'articles_processed': 0,
                    'articles_updated': 0,
                    'tags_added': 0,
                    'vocabulary_size': 0,
                }

            # Process articles for suggestions
            stats = self._suggest_tags_for_all_articles(available_tags)

            stats['vocabulary_size'] = len(available_tags)

            self.log_operation(
                'additional_tags_suggested',
                articles_processed=stats['articles_processed'],
                tags_added=stats['tags_added'],
            )

            return stats

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, 'suggesting additional tags for all articles')
            ) from e

    def _process_articles_for_tags(
        self,
        tag_mappings: dict[str, str],
        available_tags: list[str],
    ) -> dict[str, Any]:
        """Process all articles to apply tag mappings and suggest new tags."""
        articles_processed = 0
        articles_updated = 0
        tags_added = 0

        for _article_id, node_data in self._citation_tracker.graph.nodes(data=True):
            analysis_dict = node_data.get('analysis')
            metadata = node_data.get('metadata', {})

            if not analysis_dict:
                continue

            # Get article info
            title = metadata.get('title', _article_id)
            abstract = analysis_dict.get('abstract', '')
            current_tags = analysis_dict.get('tags', [])

            # Apply tag mappings
            updated_tags = []
            for tag in current_tags or []:
                canonical_tag = tag_mappings.get(tag, tag)
                updated_tags.append(canonical_tag)

            # Suggest additional tags if we have an abstract
            additional_tags = []
            if abstract and available_tags:
                try:
                    suggestion_result = self.suggest_tags(
                        title=title,
                        abstract=abstract,
                        current_tags=updated_tags,
                        available_tags=available_tags,
                    )
                    additional_tags = suggestion_result['suggested_tags']
                    tags_added += len(additional_tags)
                except Exception as e:
                    self.logger.warning(
                        f'Failed to suggest tags for article {_article_id}: {e}'
                    )

            # Combine and deduplicate tags
            final_tags = list(set(updated_tags + additional_tags))

            # Update if changed
            if final_tags != current_tags:
                analysis_dict['tags'] = final_tags
                articles_updated += 1

            articles_processed += 1

        # Save the updated graph
        if articles_updated > 0:
            self._citation_tracker._save_graph()

        return {
            'articles_processed': articles_processed,
            'articles_updated': articles_updated,
            'tags_added': tags_added,
        }

    def _apply_tag_mappings(self, tag_mappings: dict[str, str]) -> dict[str, Any]:
        """Apply tag mappings to all articles without suggesting new tags."""
        articles_processed = 0
        articles_updated = 0

        for _article_id, node_data in self._citation_tracker.graph.nodes(data=True):
            analysis_dict = node_data.get('analysis')

            if not analysis_dict:
                continue

            current_tags = analysis_dict.get('tags', [])

            # Apply tag mappings
            updated_tags = []
            for tag in current_tags or []:
                canonical_tag = tag_mappings.get(tag, tag)
                updated_tags.append(canonical_tag)

            # Remove duplicates while preserving order
            final_tags = list(dict.fromkeys(updated_tags))

            # Update if changed
            if final_tags != current_tags:
                analysis_dict['tags'] = final_tags
                articles_updated += 1

            articles_processed += 1

        # Save the updated graph
        if articles_updated > 0:
            self._citation_tracker._save_graph()

        return {
            'articles_processed': articles_processed,
            'articles_updated': articles_updated,
        }

    def _suggest_tags_for_all_articles(
        self, available_tags: list[str]
    ) -> dict[str, Any]:
        """Suggest additional tags for all articles."""
        articles_processed = 0
        articles_updated = 0
        total_tags_added = 0

        for _article_id, node_data in self._citation_tracker.graph.nodes(data=True):
            analysis_dict = node_data.get('analysis')
            metadata = node_data.get('metadata', {})

            if not analysis_dict:
                continue

            # Get article info
            title = metadata.get('title', _article_id)
            abstract = analysis_dict.get('abstract', '')
            current_tags = analysis_dict.get('tags', [])

            # Skip if no abstract
            if not abstract:
                articles_processed += 1
                continue

            # Suggest additional tags
            try:
                suggestion_result = self.suggest_tags(
                    title=title,
                    abstract=abstract,
                    current_tags=current_tags or [],
                    available_tags=available_tags,
                )
                suggested_tags = suggestion_result['suggested_tags']

                if suggested_tags:
                    # Combine and deduplicate
                    final_tags = list(
                        dict.fromkeys((current_tags or []) + suggested_tags)
                    )

                    # Update
                    analysis_dict['tags'] = final_tags
                    articles_updated += 1
                    total_tags_added += len(suggested_tags)

            except Exception as e:
                self.logger.warning(
                    f'Failed to suggest tags for article {_article_id}: {e}'
                )

            articles_processed += 1

        # Save the updated graph
        if articles_updated > 0:
            self._citation_tracker._save_graph()

        return {
            'articles_processed': articles_processed,
            'articles_updated': articles_updated,
            'tags_added': total_tags_added,
        }

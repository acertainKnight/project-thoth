"""
Tag Consolidator for Thoth.

This module handles the consolidation of existing tags across the citation graph
and the suggestion of additional relevant tags for articles based on their abstracts.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from thoth.utilities.models import (
    ConsolidatedTagsResponse,
    SingleTagMappingResponse,
    TagConsolidationResponse,
    TagSuggestionResponse,
)
from thoth.utilities import OpenRouterClient


class TagConsolidatorError(Exception):
    """Exception raised for errors in the tag consolidation process."""

    pass


class TagConsolidator:
    """
    Tag Consolidator for Thoth.

    This class provides functionality to consolidate existing tags across the
    citation graph and suggest additional relevant tags for articles based on
    their abstracts and the consolidated tag vocabulary.
    """

    def __init__(
        self,
        consolidate_model: str = 'openai/gpt-4o-mini',
        map_model: str = 'openai/gpt-4o-mini',
        suggest_model: str = 'openai/gpt-4o-mini',
        openrouter_api_key: str | None = None,
        prompts_dir: str | Path = 'templates/prompts',
        model_kwargs: dict[str, Any] | None = None,
    ):
        """
        Initialize the TagConsolidator.

        Args:
            model: The model to use for API calls (e.g., 'openai/gpt-4o-mini').
            openrouter_api_key: The OpenRouter API key (optional, uses env var if not
            provided).
            prompts_dir: Directory containing Jinja2 prompt templates.
            model_kwargs: Additional keyword arguments for the model.
        """
        self.consolidate_model = consolidate_model
        self.map_model = map_model
        self.suggest_model = suggest_model
        self.consolidate_prompts_dir = (
            Path(prompts_dir) / self.consolidate_model.split('/')[0]
        )
        self.map_prompts_dir = Path(prompts_dir) / self.map_model.split('/')[0]
        self.suggest_prompts_dir = Path(prompts_dir) / self.suggest_model.split('/')[0]
        self.model_kwargs = model_kwargs if model_kwargs else {}

        # Initialize the LLM
        self.consolidate_llm = OpenRouterClient(
            api_key=openrouter_api_key,
            model=consolidate_model,
            **self.model_kwargs,
        )
        self.map_llm = OpenRouterClient(
            api_key=openrouter_api_key,
            model=map_model,
            **self.model_kwargs,
        )
        self.suggest_llm = OpenRouterClient(
            api_key=openrouter_api_key,
            model=suggest_model,
            **self.model_kwargs,
        )

        # Create structured LLMs for different response types
        self.consolidate_llm = self.consolidate_llm.with_structured_output(
            ConsolidatedTagsResponse,
            include_raw=False,
            method='json_schema',
        )

        self.single_mapping_llm = self.map_llm.with_structured_output(
            SingleTagMappingResponse,
            include_raw=False,
            method='json_schema',
        )

        self.suggestion_llm = self.suggest_llm.with_structured_output(
            TagSuggestionResponse,
            include_raw=False,
            method='json_schema',
        )

        # Initialize Jinja environment
        self.consolidate_jinja_env = Environment(
            loader=FileSystemLoader(self.consolidate_prompts_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.map_jinja_env = Environment(
            loader=FileSystemLoader(self.map_prompts_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.suggest_jinja_env = Environment(
            loader=FileSystemLoader(self.suggest_prompts_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Load prompts
        self.consolidated_tags_prompt = self._create_prompt_from_template(
            'consolidate_tags.j2', self.consolidate_jinja_env
        )
        self.single_mapping_prompt = self._create_prompt_from_template(
            'map_single_tag.j2', self.map_jinja_env
        )
        self.suggestion_prompt = self._create_prompt_from_template(
            'suggest_additional_tags.j2', self.suggest_jinja_env
        )

        # Build analysis chains
        self.consolidated_tags_chain = (
            self.consolidated_tags_prompt | self.consolidate_llm
        )
        self.single_mapping_chain = self.single_mapping_prompt | self.single_mapping_llm
        self.suggestion_chain = self.suggestion_prompt | self.suggestion_llm

        logger.info('TagConsolidator initialized with two-step consolidation approach')

    def _create_prompt_from_template(
        self, template_name: str, loader: Environment
    ) -> ChatPromptTemplate:
        """
        Create a ChatPromptTemplate from a Jinja2 template file.

        Args:
            template_name: Name of the template file (e.g., "consolidate_tags.j2").

        Returns:
            ChatPromptTemplate: The prompt template for use in LangChain.

        Raises:
            FileNotFoundError: If the template file doesn't exist.
        """
        template_source, _filename, _uptodate = loader.loader.get_source(
            loader, template_name
        )
        return ChatPromptTemplate.from_template(
            template_source, template_format='jinja2'
        )

    def extract_all_tags_from_graph(self, citation_tracker) -> list[str]:
        """
        Extract all unique tags from all articles in the citation graph.

        Args:
            citation_tracker: The CitationTracker instance containing the graph.

        Returns:
            list[str]: A list of all unique tags found across all articles.

        Example:
            >>> consolidator = TagConsolidator()
            >>> tags = consolidator.extract_all_tags_from_graph(citation_tracker)
            >>> len(tags)
            45
        """
        logger.info('Extracting all tags from citation graph...')
        all_tags = set()

        for _article_id, node_data in citation_tracker.graph.nodes(data=True):
            analysis_dict = node_data.get('analysis')
            if analysis_dict and 'tags' in analysis_dict:
                tags = analysis_dict['tags']
                if tags:
                    all_tags.update(tags)

        unique_tags = sorted(list(all_tags))
        logger.info(
            f'Extracted {len(unique_tags)} unique tags from {len(citation_tracker.graph.nodes)} articles'
        )
        return unique_tags

    def consolidate_tags(self, existing_tags: list[str]) -> TagConsolidationResponse:
        """
        Consolidate similar tags using a two-step LLM analysis approach.

        Args:
            existing_tags: List of existing tags to consolidate.

        Returns:
            TagConsolidationResponse: The consolidation mapping and canonical tags.

        Raises:
            TagConsolidatorError: If the consolidation fails.

        Example:
            >>> consolidator = TagConsolidator()
            >>> tags = ['#ml', '#machine_learning', '#ai', '#artificial_intelligence']
            >>> response = consolidator.consolidate_tags(tags)
            >>> response.consolidated_tags
            ['#machine_learning', '#artificial_intelligence']
        """
        if not existing_tags:
            logger.warning('No existing tags provided for consolidation')
            return TagConsolidationResponse(
                tag_mappings={}, consolidated_tags=[], reasoning={}
            )

        logger.info(
            f'Starting two-step consolidation for {len(existing_tags)} existing tags...'
        )

        try:
            # Step 1: Get the consolidated tags list and new tag suggestions
            logger.info(
                'Step 1: Getting consolidated canonical tags and new tag suggestions...'
            )
            consolidated_response = self.consolidated_tags_chain.invoke(
                {'existing_tags': existing_tags}
            )

            canonical_tags = consolidated_response.consolidated_tags
            suggested_category_tags = consolidated_response.suggested_category_tags
            suggested_aggregate_tags = consolidated_response.suggested_aggregate_tags

            # Combine all tags into the final consolidated list
            all_tags = (
                canonical_tags + suggested_category_tags + suggested_aggregate_tags
            )
            final_consolidated_tags = sorted(
                list(set(all_tags))
            )  # Remove duplicates and sort

            logger.info(
                f'Step 1 completed: Identified {len(canonical_tags)} canonical tags'
            )
            logger.info(
                f'  - Suggested {len(suggested_category_tags)} category tags: {suggested_category_tags}'
            )
            logger.info(
                f'  - Suggested {len(suggested_aggregate_tags)} aggregate tags: {suggested_aggregate_tags}'
            )
            logger.info(
                f'  - Total consolidated vocabulary: {len(final_consolidated_tags)} tags'
            )

            # Step 2: Map each original tag to a canonical tag
            logger.info('Step 2: Mapping each original tag to canonical form...')
            tag_mappings = {}

            for original_tag in existing_tags:
                try:
                    mapping_response = self.single_mapping_chain.invoke(
                        {'original_tag': original_tag, 'canonical_tags': canonical_tags}
                    )
                    tag_mappings[original_tag] = mapping_response.canonical_tag
                    logger.debug(
                        f'Mapped: {original_tag} -> {mapping_response.canonical_tag}'
                    )

                except Exception as e:
                    logger.warning(f'Failed to map tag {original_tag}: {e}')
                    # Fallback: if mapping fails, see if the tag exists in canonical
                    # list, otherwise keep as-is
                    if original_tag in canonical_tags:
                        tag_mappings[original_tag] = original_tag
                    else:
                        # Find closest match or keep original
                        tag_mappings[original_tag] = original_tag
                        logger.warning(
                            f'Using original tag as fallback: {original_tag}'
                        )

            logger.info(f'Step 2 completed: Mapped {len(tag_mappings)} tags')

            # Create the final response
            result = TagConsolidationResponse(
                tag_mappings=tag_mappings,
                consolidated_tags=final_consolidated_tags,
                reasoning=consolidated_response.reasoning,
            )

            logger.info(
                f'Two-step tag consolidation completed. Mapped {len(result.tag_mappings)} tags, resulting in {len(result.consolidated_tags)} total tags ({len(canonical_tags)} canonical + {len(suggested_category_tags)} category + {len(suggested_aggregate_tags)} aggregate)'
            )
            return result

        except Exception as e:
            logger.error(f'Tag consolidation failed: {e}')
            raise TagConsolidatorError(f'Failed to consolidate tags: {e}') from e

    def suggest_additional_tags(
        self,
        title: str,
        abstract: str,
        current_tags: list[str],
        available_tags: list[str],
    ) -> TagSuggestionResponse:
        """
        Suggest additional relevant tags for an article based on its abstract.

        Args:
            title: The title of the article.
            abstract: The abstract of the article.
            current_tags: Currently assigned tags for the article.
            available_tags: The available tag vocabulary to choose from.

        Returns:
            TagSuggestionResponse: The suggested additional tags and reasoning.

        Raises:
            TagConsolidatorError: If the suggestion fails.

        Example:
            >>> consolidator = TagConsolidator()
            >>> response = consolidator.suggest_additional_tags(
            ...     'Deep Learning for Computer Vision',
            ...     'This paper presents a novel deep learning approach...',
            ...     ['#machine_learning'],
            ...     ['#deep_learning', '#computer_vision', '#neural_networks'],
            ... )
            >>> response.suggested_tags
            ['#deep_learning', '#computer_vision']
        """
        if not abstract:
            logger.warning(
                f'No abstract provided for article "{title}", cannot suggest tags'
            )
            return TagSuggestionResponse(suggested_tags=[], reasoning={})

        if not available_tags:
            logger.warning('No available tags vocabulary provided, cannot suggest tags')
            return TagSuggestionResponse(suggested_tags=[], reasoning={})

        logger.info(f'Suggesting additional tags for article: {title}')

        try:
            result = self.suggestion_chain.invoke(
                {
                    'title': title,
                    'abstract': abstract,
                    'current_tags': current_tags or [],
                    'available_tags': available_tags,
                }
            )

            logger.info(
                f'Suggested {len(result.suggested_tags)} additional tags for "{title}"'
            )
            return result

        except Exception as e:
            logger.error(f'Tag suggestion failed for "{title}": {e}')
            raise TagConsolidatorError(
                f'Failed to suggest tags for "{title}": {e}'
            ) from e

    def consolidate_and_retag_all_articles(self, citation_tracker) -> dict[str, Any]:
        """
        Perform complete tag consolidation and re-tagging for all articles in the graph.

        This method:
        1. Extracts all existing tags from the citation graph
        2. Consolidates similar tags into canonical forms
        3. Updates existing tags with their canonical equivalents
        4. Suggests additional relevant tags for each article
        5. Updates the citation graph with the new tags

        Args:
            citation_tracker: The CitationTracker instance containing the graph.

        Returns:
            dict[str, Any]: Summary statistics of the consolidation and re-tagging
                process.

        Example:
            >>> consolidator = TagConsolidator()
            >>> stats = consolidator.consolidate_and_retag_all_articles(
            ...     citation_tracker
            ... )
            >>> stats['articles_processed']
            25
        """
        logger.info('Starting complete tag consolidation and re-tagging process...')

        # Step 1: Extract all existing tags
        existing_tags = self.extract_all_tags_from_graph(citation_tracker)
        if not existing_tags:
            logger.warning('No existing tags found in the citation graph')
            return {
                'articles_processed': 0,
                'tags_consolidated': 0,
                'tags_added': 0,
                'original_tag_count': 0,
                'final_tag_count': 0,
            }

        # Step 2: Consolidate tags
        consolidation_response = self.consolidate_tags(existing_tags)
        canonical_tags = consolidation_response.consolidated_tags

        # Step 3: Process each article
        articles_processed = 0
        tags_added = 0
        updated_articles = {}

        for article_id, node_data in citation_tracker.graph.nodes(data=True):
            analysis_dict = node_data.get('analysis')
            metadata = node_data.get('metadata', {})

            if not analysis_dict:
                logger.debug(
                    f'No analysis data found for article {article_id}, skipping'
                )
                continue

            # Get article info
            title = metadata.get('title', article_id)
            abstract = analysis_dict.get('abstract', '')
            current_tags = analysis_dict.get('tags', [])

            # Step 3a: Apply tag consolidation mappings to current tags
            updated_tags = []
            for tag in current_tags or []:
                canonical_tag = consolidation_response.tag_mappings.get(tag, tag)
                updated_tags.append(canonical_tag)

            # Step 3b: Suggest additional tags if we have an abstract
            additional_tags = []
            if abstract and canonical_tags:
                try:
                    suggestion_response = self.suggest_additional_tags(
                        title=title,
                        abstract=abstract,
                        current_tags=updated_tags,
                        available_tags=canonical_tags,
                    )
                    additional_tags = suggestion_response.suggested_tags
                    tags_added += len(additional_tags)
                except TagConsolidatorError as e:
                    logger.warning(
                        f'Failed to suggest tags for article {article_id}: {e}'
                    )

            # Step 3c: Combine and deduplicate tags
            final_tags = list(set(updated_tags + additional_tags))

            # Step 3d: Update the analysis with new tags
            if final_tags != current_tags:
                analysis_dict['tags'] = final_tags
                updated_articles[article_id] = {
                    'original_tags': current_tags,
                    'final_tags': final_tags,
                    'added_tags': additional_tags,
                }
                logger.info(
                    f'Updated tags for "{title}": {len(current_tags or [])} -> {len(final_tags)} tags'
                )

            # Step 3e: Save the updated graph
            if updated_articles:
                citation_tracker._save_graph()
                logger.info('Saved updated citation graph with consolidated tags')

            articles_processed += 1

        # Step 5: Return summary statistics
        stats = {
            'articles_processed': articles_processed,
            'articles_updated': len(updated_articles),
            'tags_consolidated': len(consolidation_response.tag_mappings),
            'tags_added': tags_added,
            'original_tag_count': len(existing_tags),
            'final_tag_count': len(canonical_tags),
            'consolidation_mappings': consolidation_response.tag_mappings,
            'canonical_tags': canonical_tags,
            'updated_articles': updated_articles,
        }

        logger.info(
            f'Tag consolidation and re-tagging completed. '
            f'Processed {articles_processed} articles, '
            f'updated {len(updated_articles)} articles, '
            f'consolidated {len(consolidation_response.tag_mappings)} tags, '
            f'added {tags_added} new tags'
        )

        return stats

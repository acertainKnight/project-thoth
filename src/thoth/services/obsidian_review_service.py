"""
Obsidian Review Service for importing article review decisions back to database.

This service handles parsing Obsidian markdown files with YAML frontmatter
containing user review decisions (liked/disliked/skipped) and updating the
database accordingly.
"""

from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from loguru import logger

try:
    import yaml
except ImportError:
    logger.error(
        "PyYAML is required for Obsidian review parsing. "
        "Install it with: pip install pyyaml"
    )
    raise


class ObsidianReviewService:
    """Service for processing Obsidian article review files."""

    def __init__(self, article_match_repository):
        """
        Initialize the Obsidian review service.

        Args:
            article_match_repository: Repository for article research matches
        """
        self.match_repo = article_match_repository

    async def apply_review_decisions(
        self, review_file_path: Path
    ) -> dict[str, int]:
        """
        Parse Obsidian review file and apply user decisions to database.

        This method extracts article review decisions from an Obsidian markdown
        file with YAML frontmatter and updates the database accordingly:
        - "liked" → Sets bookmark=True, user_rating=5
        - "disliked" → Sets user_rating=1
        - "skip" → Marks as viewed only
        - "pending" → No action (unchanged)

        Args:
            review_file_path: Path to the Obsidian markdown file

        Returns:
            dict[str, int]: Summary statistics with keys:
                - "liked": Number of articles marked as liked
                - "disliked": Number of articles marked as disliked
                - "skipped": Number of articles skipped
                - "updated": Total number of articles updated
                - "errors": Number of errors encountered

        Raises:
            FileNotFoundError: If review_file_path does not exist
            ValueError: If file format is invalid

        Example:
            >>> service = ObsidianReviewService(match_repo)
            >>> stats = await service.apply_review_decisions(
            ...     Path("vault/reviews/memory-systems.md")
            ... )
            >>> print(f"Updated {stats['updated']} articles")
        """
        if not review_file_path.exists():
            raise FileNotFoundError(
                f"Review file not found: {review_file_path}"
            )

        try:
            content = review_file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to read review file {review_file_path}: {e}")
            raise ValueError(f"Could not read review file: {e}")

        # Initialize statistics
        stats = {
            'liked': 0,
            'disliked': 0,
            'skipped': 0,
            'updated': 0,
            'errors': 0,
        }

        # Extract YAML frontmatter
        if not content.startswith('---'):
            raise ValueError(
                "Invalid file format: Expected YAML frontmatter starting with '---'"
            )

        try:
            # Split content into frontmatter and body
            parts = content.split('---', 2)
            if len(parts) < 3:
                raise ValueError(
                    "Invalid file format: Could not find closing '---' for frontmatter"
                )

            frontmatter = parts[1].strip()
            data = yaml.safe_load(frontmatter)

            if not isinstance(data, dict):
                raise ValueError(
                    "Invalid YAML frontmatter: Expected a dictionary"
                )

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML frontmatter: {e}")
            raise ValueError(f"Invalid YAML format: {e}")

        # Extract question_id if present
        question_id = data.get('question_id')
        if question_id:
            logger.info(f"Processing reviews for question: {question_id}")

        # Extract articles array
        articles = data.get('articles', [])
        if not articles:
            logger.warning(
                f"No articles found in review file: {review_file_path}"
            )
            return stats

        logger.info(f"Processing {len(articles)} article reviews")

        # Process each article
        for idx, article in enumerate(articles):
            try:
                # Extract article data
                article_id_str = article.get('id')
                if not article_id_str:
                    logger.warning(
                        f"Article at index {idx} missing 'id' field, skipping"
                    )
                    stats['errors'] += 1
                    continue

                # Convert to UUID
                try:
                    # Handle both article_id and match_id
                    if 'match_id' in article:
                        match_id = UUID(article['match_id'])
                    else:
                        # If only article_id is provided, we need to look it up
                        # For now, assume 'id' refers to match_id
                        match_id = UUID(article_id_str)
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Invalid UUID format for article {article_id_str}: {e}"
                    )
                    stats['errors'] += 1
                    continue

                # Get status and notes
                status = article.get('status', 'pending').lower()
                notes = article.get('notes', '').strip()

                # Apply decision based on status
                if status == 'pending':
                    # No action for pending articles
                    continue

                elif status == 'liked':
                    # Set bookmark and high rating
                    success_bookmark = await self.match_repo.set_bookmark(
                        match_id, True
                    )
                    success_rating = await self.match_repo.set_user_rating(
                        match_id, 5, notes if notes else None
                    )

                    if success_bookmark and success_rating:
                        stats['liked'] += 1
                        stats['updated'] += 1
                        logger.debug(
                            f"Marked article {match_id} as liked (bookmarked + rating 5)"
                        )
                    else:
                        logger.warning(
                            f"Failed to fully update article {match_id}"
                        )
                        stats['errors'] += 1

                elif status == 'disliked':
                    # Set low rating
                    success = await self.match_repo.set_user_rating(
                        match_id, 1, notes if notes else None
                    )

                    if success:
                        stats['disliked'] += 1
                        stats['updated'] += 1
                        logger.debug(
                            f"Marked article {match_id} as disliked (rating 1)"
                        )
                    else:
                        logger.warning(
                            f"Failed to update article {match_id}"
                        )
                        stats['errors'] += 1

                elif status == 'skip':
                    # Mark as viewed only
                    success = await self.match_repo.mark_as_viewed(match_id)

                    if success:
                        stats['skipped'] += 1
                        stats['updated'] += 1
                        logger.debug(f"Marked article {match_id} as skipped")
                    else:
                        logger.warning(
                            f"Failed to mark article {match_id} as viewed"
                        )
                        stats['errors'] += 1

                else:
                    logger.warning(
                        f"Unknown status '{status}' for article {match_id}, skipping"
                    )
                    stats['errors'] += 1

            except Exception as e:
                logger.error(
                    f"Error processing article at index {idx}: {e}",
                    exc_info=True,
                )
                stats['errors'] += 1

        # Log summary
        logger.info(
            f"Review processing complete: {stats['updated']} updated, "
            f"{stats['liked']} liked, {stats['disliked']} disliked, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )

        return stats

    async def validate_review_file(
        self, review_file_path: Path
    ) -> dict[str, Any]:
        """
        Validate an Obsidian review file without applying changes.

        Args:
            review_file_path: Path to the Obsidian markdown file

        Returns:
            dict[str, Any]: Validation results with keys:
                - "valid": bool indicating if file is valid
                - "article_count": Number of articles found
                - "errors": List of validation errors
                - "warnings": List of validation warnings

        Example:
            >>> service = ObsidianReviewService(match_repo)
            >>> validation = await service.validate_review_file(
            ...     Path("vault/reviews/test.md")
            ... )
            >>> if validation['valid']:
            ...     await service.apply_review_decisions(review_file_path)
        """
        result = {
            'valid': False,
            'article_count': 0,
            'errors': [],
            'warnings': [],
        }

        # Check file exists
        if not review_file_path.exists():
            result['errors'].append(f"File not found: {review_file_path}")
            return result

        try:
            content = review_file_path.read_text(encoding='utf-8')
        except Exception as e:
            result['errors'].append(f"Could not read file: {e}")
            return result

        # Validate YAML frontmatter
        if not content.startswith('---'):
            result['errors'].append(
                "Invalid format: Expected YAML frontmatter starting with '---'"
            )
            return result

        try:
            parts = content.split('---', 2)
            if len(parts) < 3:
                result['errors'].append(
                    "Invalid format: Could not find closing '---' for frontmatter"
                )
                return result

            frontmatter = parts[1].strip()
            data = yaml.safe_load(frontmatter)

            if not isinstance(data, dict):
                result['errors'].append(
                    "Invalid YAML: Expected a dictionary"
                )
                return result

        except yaml.YAMLError as e:
            result['errors'].append(f"Invalid YAML format: {e}")
            return result

        # Validate articles array
        articles = data.get('articles', [])
        if not articles:
            result['warnings'].append("No articles found in file")

        result['article_count'] = len(articles)

        # Validate each article structure
        valid_statuses = {'pending', 'liked', 'disliked', 'skip'}
        for idx, article in enumerate(articles):
            if not isinstance(article, dict):
                result['errors'].append(
                    f"Article at index {idx} is not a dictionary"
                )
                continue

            # Check for required fields
            if 'id' not in article and 'match_id' not in article:
                result['errors'].append(
                    f"Article at index {idx} missing 'id' or 'match_id' field"
                )

            # Validate UUID format
            article_id = article.get('id') or article.get('match_id')
            if article_id:
                try:
                    UUID(article_id)
                except (ValueError, TypeError):
                    result['errors'].append(
                        f"Article at index {idx} has invalid UUID: {article_id}"
                    )

            # Validate status
            status = article.get('status', 'pending').lower()
            if status not in valid_statuses:
                result['warnings'].append(
                    f"Article at index {idx} has unknown status: '{status}'"
                )

        # Set overall validity
        result['valid'] = len(result['errors']) == 0

        return result

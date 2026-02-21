"""
Obsidian Review Service for importing article review decisions back to database.

This service handles parsing Obsidian markdown files with YAML frontmatter
containing user review decisions (liked/disliked/skipped) and updating the
database accordingly.
"""

from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger

try:
    import yaml
except ImportError:
    logger.error(
        'PyYAML is required for Obsidian review parsing. '
        'Install it with: pip install pyyaml'
    )
    raise

from thoth.ingestion.pdf_downloader import download_pdf  # noqa: I001
from thoth.config import Config


class ObsidianReviewService:
    """Service for processing Obsidian article review files."""

    def __init__(self, article_match_repository):
        """
        Initialize the Obsidian review service.

        Args:
            article_match_repository: Repository for article research matches
        """
        self.match_repo = article_match_repository

    async def apply_review_decisions(self, review_file_path: Path) -> dict[str, int]:
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
            ...     Path('vault/reviews/memory-systems.md')
            ... )
            >>> print(f'Updated {stats["updated"]} articles')
        """
        if not review_file_path.exists():
            raise FileNotFoundError(f'Review file not found: {review_file_path}')

        try:
            content = review_file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f'Failed to read review file {review_file_path}: {e}')
            raise ValueError(f'Could not read review file: {e}')  # noqa: B904

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
                raise ValueError('Invalid YAML frontmatter: Expected a dictionary')

        except yaml.YAMLError as e:
            logger.error(f'Failed to parse YAML frontmatter: {e}')
            raise ValueError(f'Invalid YAML format: {e}')  # noqa: B904

        # Extract question_id if present
        question_id = data.get('question_id')
        if question_id:
            logger.info(f'Processing reviews for question: {question_id}')

        # Extract articles array from YAML frontmatter
        articles = data.get('articles', [])

        # If no articles in frontmatter, try parsing markdown body (dashboard format)
        if not articles:
            logger.info(
                f'No articles in YAML frontmatter, attempting to parse markdown body...'  # noqa: F541
            )
            markdown_body = parts[2] if len(parts) > 2 else ''
            articles = self._parse_dashboard_markdown(
                markdown_body, data.get('question_id')
            )

        if not articles:
            logger.warning(f'No articles found in review file: {review_file_path}')
            return stats

        logger.info(f'Processing {len(articles)} article reviews')

        # Process each article
        for idx, article in enumerate(articles):
            try:
                # Check if this is dashboard format (title-based) or YAML format (ID-based)  # noqa: W505
                is_dashboard_format = article.get('format') == 'dashboard'

                if is_dashboard_format:
                    # Dashboard format: look up match ID by title
                    title = article.get('title')
                    if not title:
                        logger.warning(
                            f'Dashboard article at index {idx} missing title, skipping'
                        )
                        stats['errors'] += 1
                        continue

                    # Look up match ID from database by title
                    match_id = await self._lookup_match_id_by_title(title, question_id)

                    if not match_id:
                        logger.warning(
                            f"Could not find match ID for article: '{title}'"
                        )
                        stats['errors'] += 1
                        continue

                else:
                    # YAML frontmatter format: extract ID directly
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
                            f'Invalid UUID format for article {article_id_str}: {e}'
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
                            f'Marked article {match_id} as liked (bookmarked + rating 5)'
                        )

                        # Attempt to download PDF automatically
                        try:
                            article_info = await self._get_article_info(match_id)
                            if article_info and article_info.get('pdf_url'):
                                await self._download_article_pdf(
                                    article_info['pdf_url'],
                                    article_info.get('title', 'unknown'),
                                    match_id,
                                )
                        except Exception as e:
                            logger.warning(
                                f'Could not download PDF for article {match_id}: {e}'
                            )
                            # Don't fail the like operation if PDF download fails

                    else:
                        logger.warning(f'Failed to fully update article {match_id}')
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
                            f'Marked article {match_id} as disliked (rating 1)'
                        )
                    else:
                        logger.warning(f'Failed to update article {match_id}')
                        stats['errors'] += 1

                elif status == 'skip':
                    # Mark as viewed only
                    success = await self.match_repo.mark_as_viewed(match_id)

                    if success:
                        stats['skipped'] += 1
                        stats['updated'] += 1
                        logger.debug(f'Marked article {match_id} as skipped')
                    else:
                        logger.warning(f'Failed to mark article {match_id} as viewed')
                        stats['errors'] += 1

                else:
                    logger.warning(
                        f"Unknown status '{status}' for article {match_id}, skipping"
                    )
                    stats['errors'] += 1

            except Exception as e:
                logger.error(
                    f'Error processing article at index {idx}: {e}',
                    exc_info=True,
                )
                stats['errors'] += 1

        # Log summary
        logger.info(
            f'Review processing complete: {stats["updated"]} updated, '
            f'{stats["liked"]} liked, {stats["disliked"]} disliked, '
            f'{stats["skipped"]} skipped, {stats["errors"]} errors'
        )

        return stats

    def _parse_dashboard_markdown(
        self,
        markdown_body: str,
        question_id: str | None = None,  # noqa: ARG002
    ) -> list[dict]:
        """
        Parse dashboard markdown format for article reviews.

        Dashboard format has articles with inline status fields like:
        ### 1. Article Title
        **Status:** `like` ← Change to `like`, `dislike`, or `skip`
        **Relevance:** 95.2%

        This parser extracts articles from the markdown body by matching:
        - Article headers (###)
        - Status fields (**Status:** `value`)
        - Extracts match IDs from database by matching titles

        Args:
            markdown_body: The markdown content (after YAML frontmatter)
            question_id: Research question ID to query for match IDs

        Returns:
            list[dict]: Parsed articles with 'id', 'status', 'title' fields
        """
        import re
        from uuid import UUID  # noqa: F401

        articles = []

        if not markdown_body.strip():
            return articles

        # Match article sections: ### N. Title ... **Status:** `value`
        # Pattern matches from article header to next article or end
        article_pattern = re.compile(
            r'###\s+\d+\.\s+(?P<title>[^\n]+)\n'  # Header: ### 1. Title
            r'.*?'  # Any content between
            r'\*\*Status:\*\*\s+`(?P<status>\w+)`',  # Status field
            re.DOTALL | re.MULTILINE,
        )

        matches = article_pattern.finditer(markdown_body)

        for match in matches:
            title = match.group('title').strip()
            status = match.group('status').lower()

            # Normalize status values
            # Dashboard uses: like, dislike, skip, pending
            # Database expects: liked, disliked, skip, pending
            if status == 'like':
                status = 'liked'
            elif status == 'dislike':
                status = 'disliked'

            # For dashboard format, we need to look up match IDs by title
            # This requires querying the database, which we'll defer to the caller
            # For now, store title and let the processing loop look it up
            articles.append(
                {
                    'title': title,
                    'status': status,
                    'format': 'dashboard',  # Flag to indicate this needs title-based lookup
                }
            )

        logger.info(f'Parsed {len(articles)} articles from dashboard markdown format')

        return articles

    async def _lookup_match_id_by_title(
        self,
        title: str,
        question_id: str | None = None,
    ) -> UUID | None:
        """
        Look up article_research_matches.id by article title.

        Args:
            title: Article title to search for
            question_id: Optional research question ID to narrow search

        Returns:
            Match UUID if found, None otherwise
        """
        from thoth.services.postgres_service import PostgresService  # noqa: F401

        # We need access to PostgreSQL to query for match IDs
        # The repository pattern doesn't expose this, so we'll need to query directly
        # Get the postgres service from the match repository
        if hasattr(self.match_repo, 'postgres'):
            pg = self.match_repo.postgres
        else:
            logger.error('Cannot look up match ID: repository missing postgres service')
            return None

        try:
            if question_id:
                # Query with question filter for precision
                query = """
                    SELECT rqm.id
                    FROM research_question_matches rqm
                    JOIN paper_metadata pm ON rqm.paper_id = pm.id
                    WHERE pm.title = $1 AND rqm.question_id = $2
                    LIMIT 1
                """
                result = await pg.fetchval(query, title, question_id)
            else:
                # Query without question filter
                query = """
                    SELECT rqm.id
                    FROM research_question_matches rqm
                    JOIN paper_metadata pm ON rqm.paper_id = pm.id
                    WHERE pm.title = $1
                    LIMIT 1
                """
                result = await pg.fetchval(query, title)

            if result:
                return UUID(str(result))
            return None

        except Exception as e:
            logger.error(f"Error looking up match ID for title '{title}': {e}")
            return None

    async def _get_article_info(self, match_id: UUID) -> dict | None:
        """
        Get article information (title, pdf_url) from a match ID.

        Args:
            match_id: Article research match UUID

        Returns:
            dict with title, pdf_url, etc. or None
        """
        if not hasattr(self.match_repo, 'postgres'):
            logger.error('Cannot get article info: repository missing postgres service')
            return None

        try:
            pg = self.match_repo.postgres
            query = """
                SELECT pm.title, pm.pdf_url, pm.url, pm.authors
                FROM research_question_matches rqm
                JOIN paper_metadata pm ON rqm.paper_id = pm.id
                WHERE rqm.id = $1
            """
            result = await pg.fetchrow(query, match_id)

            if result:
                return {
                    'title': result['title'],
                    'pdf_url': result['pdf_url'],
                    'url': result['url'],
                    'authors': result['authors'],
                }
            return None

        except Exception as e:
            logger.error(f'Error getting article info for match {match_id}: {e}')
            return None

    async def _download_article_pdf(
        self, pdf_url: str, title: str, match_id: UUID
    ) -> None:
        """
        Download PDF for an article to the configured PDF directory.

        Args:
            pdf_url: URL to the PDF file
            title: Article title (for filename)
            match_id: Match ID (for logging)
        """
        if not pdf_url or not pdf_url.lower().endswith('.pdf'):
            logger.debug(f'Article {match_id} has no valid PDF URL, skipping download')
            return

        try:
            from thoth.mcp.auth import get_current_user_paths

            user_paths = get_current_user_paths()
            config = Config.get_instance()
            pdf_dir = user_paths.pdf_dir if user_paths else config.pdf_dir

            # Sanitize filename from title
            safe_title = ''.join(
                c for c in title if c.isalnum() or c in (' ', '-', '_')
            ).strip()
            safe_title = safe_title[:100]  # Limit length

            # Download PDF (runs synchronously in executor)
            import asyncio

            pdf_path = await asyncio.to_thread(
                download_pdf, pdf_url, pdf_dir, f'{safe_title}.pdf'
            )

            logger.success(f"📥 Downloaded PDF for '{title}' to {pdf_path}")

        except Exception as e:
            logger.error(f'Failed to download PDF for article {match_id}: {e}')
            raise

    async def validate_review_file(self, review_file_path: Path) -> dict[str, Any]:
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
            ...     Path('vault/reviews/test.md')
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
            result['errors'].append(f'File not found: {review_file_path}')
            return result

        try:
            content = review_file_path.read_text(encoding='utf-8')
        except Exception as e:
            result['errors'].append(f'Could not read file: {e}')
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
                result['errors'].append('Invalid YAML: Expected a dictionary')
                return result

        except yaml.YAMLError as e:
            result['errors'].append(f'Invalid YAML format: {e}')
            return result

        # Validate articles array
        articles = data.get('articles', [])
        if not articles:
            result['warnings'].append('No articles found in file')

        result['article_count'] = len(articles)

        # Validate each article structure
        valid_statuses = {'pending', 'liked', 'disliked', 'skip'}
        for idx, article in enumerate(articles):
            if not isinstance(article, dict):
                result['errors'].append(f'Article at index {idx} is not a dictionary')
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
                        f'Article at index {idx} has invalid UUID: {article_id}'
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

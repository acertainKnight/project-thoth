"""
Discovery Dashboard Service - Automatic monitoring and updating of discovery results.

This service provides automatic, user-friendly discovery workflows:
1. Auto-exports new discovery results to Obsidian dashboard
2. Monitors dashboard for user sentiment changes (like/dislike/skip)
3. Auto-imports sentiment changes back to database
4. No manual API calls required - everything is automatic!

The user simply opens the dashboard in Obsidian, reviews articles, and changes
the status field. The service automatically detects and processes these changes.
"""

import asyncio
from datetime import datetime, timedelta  # noqa: F401
from pathlib import Path
from typing import Optional

from loguru import logger
from watchdog.events import FileModifiedEvent, FileSystemEventHandler  # noqa: F401
from watchdog.observers.polling import PollingObserver

from thoth.config import config
from thoth.services.obsidian_review_service import ObsidianReviewService
from thoth.services.postgres_service import PostgresService


class DiscoveryDashboardWatcher(FileSystemEventHandler):
    """
    File system event handler for discovery dashboard changes.

    Monitors the dashboard directory for changes to review markdown files
    and automatically processes sentiment updates.
    """

    def __init__(
        self,
        dashboard_service: 'DiscoveryDashboardService',
        loop: asyncio.AbstractEventLoop,
    ):
        """Initialize the watcher with reference to dashboard service and event loop."""
        super().__init__()
        self.service = dashboard_service
        self.loop = loop  # Store reference to event loop for scheduling async tasks
        self.processing_files = set()  # Track files being processed to avoid loops
        logger.info('Dashboard file watcher initialized')

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process markdown files in the dashboard directory
        if not file_path.suffix.lower() == '.md':
            return

        # Check if this is a dashboard review file
        if not self._is_dashboard_file(file_path):
            return

        # Skip if we're currently writing this file (auto-export/regeneration)
        if str(file_path) in self.service.writing_files:
            logger.debug(f"Skipping {file_path.name} - we're writing it")
            return

        # Avoid processing the same file multiple times
        if str(file_path) in self.processing_files:
            logger.debug(f'Skipping {file_path.name} - already processing')
            return

        logger.info(f'📝 Detected change in dashboard file: {file_path.name}')

        # Schedule processing (debounced to avoid rapid-fire updates)
        # Use run_coroutine_threadsafe since we're in a watchdog thread
        asyncio.run_coroutine_threadsafe(
            self._process_dashboard_change(file_path), self.loop
        )

    def _is_dashboard_file(self, file_path: Path) -> bool:
        """Check if file is in the dashboard directory."""
        try:
            dashboard_dir = self.service.dashboard_dir
            return file_path.is_relative_to(dashboard_dir)
        except (ValueError, AttributeError):
            return False

    async def _process_dashboard_change(self, file_path: Path):
        """
        Process a dashboard file change with debouncing.

        Waits a short period to allow multiple rapid edits to settle,
        then processes the final state.
        """
        self.processing_files.add(str(file_path))

        try:
            # Debounce: wait 2 seconds for rapid edits to settle
            await asyncio.sleep(2)

            # Import sentiment changes from the dashboard file
            await self.service.import_dashboard_changes(file_path)

        except Exception as e:
            logger.error(f'Error processing dashboard change for {file_path.name}: {e}')
        finally:
            self.processing_files.discard(str(file_path))


class DiscoveryDashboardService:
    """
    Automatic discovery dashboard service.

    Provides a seamless, user-friendly workflow:
    1. Automatically exports new discovery results to Obsidian dashboard
    2. Monitors dashboard for user changes (sentiment updates)
    3. Automatically imports changes back to database
    4. Updates dashboard with latest statistics

    No manual CLI commands or API calls required!
    """

    def __init__(
        self,
        postgres_service: PostgresService,
        obsidian_review_service: ObsidianReviewService,
        dashboard_dir: Optional[Path] = None,  # noqa: UP007
        check_interval: int = 60,
        auto_export: bool = True,
        auto_import: bool = True,
    ):
        """
        Initialize the discovery dashboard service.

        Args:
            postgres_service: PostgreSQL service for data access
            obsidian_review_service: Service for processing review files
            dashboard_dir: Directory for dashboard files (default: vault/Research/Dashboard/)
            check_interval: Seconds between automatic export checks (default: 60)
            auto_export: Enable automatic export of new results (default: True)
            auto_import: Enable automatic import of sentiment changes (default: True)
        """  # noqa: W505
        self.pg = postgres_service
        self.review_service = obsidian_review_service
        self.check_interval = check_interval
        self.auto_export = auto_export
        self.auto_import = auto_import

        # Set up dashboard directory
        vault_root = Path(config.vault_root)
        self.dashboard_dir = dashboard_dir or (vault_root / 'Research' / 'Dashboard')
        self.dashboard_dir.mkdir(parents=True, exist_ok=True)

        # Track last export time per question
        self.last_export_times: dict[str, datetime] = {}

        # File watcher for automatic import
        self.observer: Optional[PollingObserver] = None  # noqa: UP007
        self.watcher: Optional[DiscoveryDashboardWatcher] = None  # noqa: UP007

        # Track files we're writing to prevent file watcher loops
        self.writing_files: set[str] = set()

        logger.info(
            f'Discovery dashboard service initialized:\n'
            f'  Dashboard dir: {self.dashboard_dir}\n'
            f'  Check interval: {check_interval}s\n'
            f'  Auto-export: {auto_export}\n'
            f'  Auto-import: {auto_import}'
        )

    async def start(self):
        """
        Start the automatic dashboard service.

        Begins monitoring for:
        1. New discovery results (auto-export)
        2. Dashboard file changes (auto-import)
        """
        logger.info('🚀 Starting discovery dashboard service...')

        # Start file watcher for auto-import
        if self.auto_import:
            await self._start_file_watcher()

        # Start background task for auto-export
        if self.auto_export:
            asyncio.create_task(self._auto_export_loop())  # noqa: RUF006

        logger.success('✅ Discovery dashboard service started')

    async def stop(self):
        """Stop the automatic dashboard service."""
        logger.info('Stopping discovery dashboard service...')

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            logger.info('File watcher stopped')

        logger.success('Discovery dashboard service stopped')

    async def _start_file_watcher(self):
        """Start monitoring dashboard directory for changes."""
        # Get the current event loop to pass to the watcher
        loop = asyncio.get_running_loop()
        self.watcher = DiscoveryDashboardWatcher(self, loop)
        self.observer = PollingObserver(timeout=1)

        self.observer.schedule(self.watcher, str(self.dashboard_dir), recursive=False)

        self.observer.start()
        logger.info(f'📁 Watching dashboard directory: {self.dashboard_dir}')

    async def _auto_export_loop(self):
        """
        Background loop that checks for new discovery results and auto-exports.

        Runs every check_interval seconds, checking each research question
        for new matches that haven't been exported yet.
        """
        logger.info(
            f'📊 Auto-export loop started (checking every {self.check_interval}s)'
        )

        while True:
            try:
                await asyncio.sleep(self.check_interval)
                await self._check_and_export_new_results()
            except asyncio.CancelledError:
                logger.info('Auto-export loop cancelled')
                break
            except Exception as e:
                logger.error(f'Error in auto-export loop: {e}')
                # Continue despite errors

    async def _check_and_export_new_results(self):
        """
        Check all research questions for new results and export to dashboard.

        For each research question:
        1. Count new matches since last export
        2. If new matches exist, export to dashboard
        3. Update last export timestamp
        """
        # Get all active research questions
        query = """
            SELECT id, name, created_at
            FROM research_questions
            WHERE is_active = true
            ORDER BY created_at DESC
        """

        questions = await self.pg.fetch(query)

        if not questions:
            return

        for question in questions:
            question_id = question['id']
            question_name = question['name']

            # Check if there are new matches since last export
            new_count = await self._count_new_matches(question_id)

            if new_count > 0:
                logger.info(
                    f"📋 Found {new_count} new matches for '{question_name}' - "
                    f'exporting to dashboard...'
                )

                await self.export_to_dashboard(
                    question_id=question_id, question_name=question_name
                )

                self.last_export_times[str(question_id)] = datetime.now()

    async def _count_new_matches(self, question_id: str) -> int:
        """
        Count matches that are new since last export.

        Args:
            question_id: Research question UUID

        Returns:
            Number of new matches
        """
        last_export = self.last_export_times.get(str(question_id))

        if last_export:
            # Count matches added since last export
            query = """
                SELECT COUNT(*)
                FROM article_research_matches
                WHERE question_id = $1
                    AND matched_at > $2
                    AND user_sentiment IS NULL
            """
            count = await self.pg.fetchval(query, question_id, last_export)
        else:
            # First export - count all matches without sentiment
            query = """
                SELECT COUNT(*)
                FROM article_research_matches
                WHERE question_id = $1
                    AND user_sentiment IS NULL
            """
            count = await self.pg.fetchval(query, question_id)

        return count or 0

    async def export_to_dashboard(
        self,
        question_id: str,
        question_name: str,
        min_relevance: float = 0.5,
        limit: int = 100,
    ) -> Path:
        """
        Export discovery results to Obsidian dashboard file.

        Creates or updates a markdown file with:
        - YAML frontmatter with metadata and statistics
        - Interactive table of articles with status fields
        - Instructions for reviewing articles

        Args:
            question_id: Research question UUID
            question_name: Research question name
            min_relevance: Minimum relevance score (0.0-1.0)
            limit: Maximum articles to include

        Returns:
            Path to the generated dashboard file
        """
        logger.info(f"Exporting dashboard for '{question_name}'...")

        # Get article matches from database
        matches = await self._fetch_matches(question_id, min_relevance, limit)

        if not matches:
            logger.warning(f"No matches found for '{question_name}'")
            return None

        # Generate dashboard file
        dashboard_file = (
            self.dashboard_dir
            / f'{self._sanitize_filename(question_name)}_Dashboard.md'
        )

        # Get statistics
        stats = await self._get_statistics(question_id)

        # Generate dashboard content
        content = self._generate_dashboard_content(
            question_name=question_name,
            question_id=question_id,
            matches=matches,
            stats=stats,
        )

        # Write dashboard file (mark as writing to prevent file watcher loop)
        self.writing_files.add(str(dashboard_file))
        try:
            dashboard_file.write_text(content, encoding='utf-8')

            # Wait briefly for file watcher to process (if it does)
            await asyncio.sleep(0.5)
        finally:
            self.writing_files.discard(str(dashboard_file))

        logger.success(
            f'✅ Dashboard exported: {dashboard_file.name}\n'
            f'   Articles: {len(matches)} | '
            f'   Liked: {stats["liked"]} | '
            f'   Disliked: {stats["disliked"]} | '
            f'   Pending: {stats["pending"]}'
        )

        return dashboard_file

    async def import_dashboard_changes(self, dashboard_file: Path):
        """
        Import sentiment changes from dashboard file to database.

        Reads the dashboard markdown file, extracts sentiment decisions
        from YAML frontmatter, and updates the database. After importing,
        regenerates the dashboard with updated statistics and filtered articles.

        Args:
            dashboard_file: Path to the dashboard markdown file
        """
        logger.info(f'Importing changes from: {dashboard_file.name}')

        try:
            # Use ObsidianReviewService to parse and apply changes
            results = await self.review_service.apply_review_decisions(dashboard_file)

            if results and results.get('updated', 0) > 0:
                logger.success(
                    f'✅ Imported sentiment changes:\n'
                    f'   Liked: {results.get("liked", 0)}\n'
                    f'   Disliked: {results.get("disliked", 0)}\n'
                    f'   Skipped: {results.get("skipped", 0)}'
                )

                # Extract question info from dashboard frontmatter
                question_info = await self._extract_dashboard_metadata(dashboard_file)

                if question_info:
                    # Regenerate dashboard with updated stats and filtered articles
                    logger.info(f'🔄 Regenerating dashboard with updated data...')  # noqa: F541
                    await self.export_to_dashboard(
                        question_id=question_info['question_id'],
                        question_name=question_info['question_name'],
                    )
                    logger.success(f'✅ Dashboard regenerated successfully')  # noqa: F541

            else:
                logger.debug(f'No changes detected in {dashboard_file.name}')

        except Exception as e:
            logger.error(f'Failed to import dashboard changes: {e}')

    async def _fetch_matches(
        self, question_id: str, min_relevance: float, limit: int
    ) -> list[dict]:
        """Fetch article matches for a research question (pending only)."""
        query = """
            SELECT
                arm.id,
                arm.article_id,
                arm.relevance_score,
                arm.user_sentiment,
                arm.sentiment_recorded_at,
                arm.user_rating,
                a.title,
                a.authors,
                a.publication_date,
                a.abstract,
                a.url,
                a.pdf_url
            FROM article_research_matches arm
            JOIN discovered_articles a ON arm.article_id = a.id
            WHERE arm.question_id = $1
                AND arm.relevance_score >= $2
                AND arm.user_sentiment IS NULL
            ORDER BY
                arm.relevance_score DESC,
                COALESCE(arm.user_rating, 0) DESC,
                a.publication_date DESC NULLS LAST
            LIMIT $3
        """

        matches = await self.pg.fetch(query, question_id, min_relevance, limit)
        return [dict(match) for match in matches]

    async def _extract_dashboard_metadata(self, dashboard_file: Path) -> Optional[dict]:  # noqa: UP007
        """
        Extract question_id and question_name from dashboard YAML frontmatter.

        Args:
            dashboard_file: Path to the dashboard markdown file

        Returns:
            dict with 'question_id' and 'question_name', or None if not found
        """
        try:
            content = dashboard_file.read_text(encoding='utf-8')

            if not content.startswith('---'):
                return None

            parts = content.split('---', 2)
            if len(parts) < 3:
                return None

            import yaml

            frontmatter = yaml.safe_load(parts[1].strip())

            if not isinstance(frontmatter, dict):
                return None

            question_id = frontmatter.get('question_id')
            question_name = frontmatter.get('question_name')

            if question_id and question_name:
                return {'question_id': question_id, 'question_name': question_name}

        except Exception as e:
            logger.warning(
                f'Could not extract metadata from {dashboard_file.name}: {e}'
            )

        return None

    async def _get_statistics(self, question_id: str) -> dict:
        """Get sentiment statistics for a research question."""
        query = """
            SELECT
                COUNT(*) FILTER (WHERE user_sentiment = 'like') as liked,
                COUNT(*) FILTER (WHERE user_sentiment = 'dislike') as disliked,
                COUNT(*) FILTER (WHERE user_sentiment = 'skip') as skipped,
                COUNT(*) FILTER (WHERE user_sentiment IS NULL) as pending,
                COUNT(*) as total
            FROM article_research_matches
            WHERE question_id = $1
        """

        result = await self.pg.fetchrow(query, question_id)
        return (
            dict(result)
            if result
            else {'liked': 0, 'disliked': 0, 'skipped': 0, 'pending': 0, 'total': 0}
        )

    def _generate_dashboard_content(
        self, question_name: str, question_id: str, matches: list[dict], stats: dict
    ) -> str:
        """Generate dashboard markdown content with interactive elements."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Build YAML frontmatter
        frontmatter = f"""---
question_name: {question_name}
question_id: {question_id}
last_updated: {now}
total_articles: {stats['total']}
liked: {stats['liked']}
disliked: {stats['disliked']}
skipped: {stats['skipped']}
pending: {stats['pending']}
auto_generated: true
dashboard_version: 1.0
---

# Discovery Dashboard: {question_name}

> 🤖 **Automatic Dashboard** - This file updates automatically
>
> **How to use:**
> 1. Review articles below
> 2. Change `status:` field to `like`, `dislike`, or `skip`
> 3. Save the file - changes sync automatically!
>
> No CLI commands or API calls needed! 🎉

## 📊 Statistics

| Metric | Count |
|--------|-------|
| 📚 Total Articles | {stats['total']} |
| 👍 Liked | {stats['liked']} |
| 👎 Disliked | {stats['disliked']} |
| ⏭️ Skipped | {stats['skipped']} |
| ⏳ Pending Review | {stats['pending']} |

---

## 📋 Articles to Review

"""

        # Build article entries
        for i, match in enumerate(matches, 1):
            status = match['user_sentiment'] or 'pending'
            relevance = match['relevance_score']
            title = match['title']
            authors = match['authors'] or 'Unknown'
            abstract = (
                (match['abstract'] or '')[:200] + '...'
                if match['abstract']
                else 'No abstract available'
            )
            url = match['url'] or 'No URL'

            article_entry = f"""
### {i}. {title}

**Status:** `{status}` ← Change to `like`, `dislike`, or `skip`
**Relevance:** {relevance:.2%}
**Authors:** {authors}

**Abstract:** {abstract}

**Link:** [{url}]({url})

---

"""
            frontmatter += article_entry

        # Add footer
        footer = f"""
---

## 🔄 Automatic Updates

This dashboard automatically:
- ✅ Updates when new articles are discovered
- ✅ Syncs your review decisions to the database
- ✅ Refreshes statistics in real-time
- ✅ No manual commands needed!

**Last updated:** {now}

"""
        frontmatter += footer

        return frontmatter

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize research question name for use as filename."""
        # Replace invalid filename characters
        invalid_chars = '<>:"/\\|?*'
        filename = name
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Replace spaces with underscores
        filename = filename.replace(' ', '_')

        # Limit length
        return filename[:100]

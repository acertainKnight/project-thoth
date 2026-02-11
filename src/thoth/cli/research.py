"""
CLI commands for research question management and Obsidian review workflow.

This module provides commands for:
- Exporting article matches to Obsidian review files
- Applying review decisions from Obsidian back to the database
"""

import asyncio
from pathlib import Path
from uuid import UUID

from loguru import logger

from thoth.pipeline import ThothPipeline
from thoth.repositories.article_research_match_repository import (
    ArticleResearchMatchRepository,
)
from thoth.repositories.research_question_repository import ResearchQuestionRepository
from thoth.services.discovery_dashboard_service import DiscoveryDashboardService
from thoth.services.obsidian_review_service import ObsidianReviewService
from thoth.utilities.vault_path_resolver import VaultPathResolver


async def run_export_review(args, pipeline: ThothPipeline) -> int:
    """
    Export article matches for a research question to an Obsidian review file.

    This generates a markdown file with YAML frontmatter and a Dataview table
    that allows users to review discovered articles in Obsidian and mark their
    decisions (liked, disliked, skip).

    Args:
        args: Command line arguments
        pipeline: ThothPipeline instance

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    try:
        # Get question identifier
        question_identifier = args.question
        if not question_identifier:
            logger.error('Question name or ID is required')
            return 1

        # Initialize repositories
        postgres_service = pipeline.services.postgres
        match_repo = ArticleResearchMatchRepository(postgres_service)
        question_repo = ResearchQuestionRepository(postgres_service)

        # Try to find question by name first, then by UUID
        question = None
        try:
            # Try as UUID first
            question_id = UUID(question_identifier)
            question = await question_repo.get(question_id)
        except ValueError:
            # Not a valid UUID, try by name
            # Assume default user for CLI (TODO: Add user context)
            user_id = args.user_id if hasattr(args, 'user_id') else 'default'
            question = await question_repo.get_by_name(user_id, question_identifier)

        if not question:
            logger.error(
                f'Research question not found: {question_identifier}\n'
                'Try using the UUID instead of the name, or check that the question exists.'
            )
            return 1

        question_id = question['id']
        question_name = question['name']
        logger.info(f'Found research question: {question_name} ({question_id})')

        # Initialize review service
        vault_resolver = VaultPathResolver(pipeline.config)
        review_service = ObsidianReviewService(
            config=pipeline.config,
            match_repository=match_repo,
            question_repository=question_repo,
            vault_path_resolver=vault_resolver,
        )

        # Determine output path
        output_path = None
        if args.output_path:
            output_path = Path(args.output_path)
            # If directory, use default filename
            if output_path.is_dir():
                safe_name = review_service._sanitize_filename(question_name)
                output_path = output_path / f'{safe_name}_Review.md'

        # Generate review file
        logger.info('Generating Obsidian review file...')
        result_path = await review_service.generate_obsidian_review_file(
            question_id=question_id,
            output_path=output_path,
            min_relevance=args.min_relevance,
            limit=args.limit,
        )

        logger.info(f'Review file generated successfully: {result_path}')
        logger.info(
            '\nNext steps:\n'
            '1. Open the file in Obsidian\n'
            '2. Review articles and update status in YAML frontmatter\n'
            '3. Run: thoth research apply-review --file <path>'
        )

        return 0

    except ValueError as e:
        logger.error(f'Validation error: {e}')
        return 1
    except RuntimeError as e:
        logger.error(f'Generation failed: {e}')
        return 1
    except Exception as e:
        logger.exception(f'Unexpected error exporting review: {e}')
        return 1


async def run_start_dashboard(args, pipeline: ThothPipeline) -> int:
    """
    Start the automatic discovery dashboard service.

    This service provides a seamless workflow:
    1. Automatically exports new discovery results to Obsidian dashboard
    2. Monitors dashboard files for sentiment changes
    3. Automatically imports changes back to database

    No manual CLI commands or API calls required!

    Args:
        args: Command line arguments
        pipeline: ThothPipeline instance

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    try:
        logger.info('Starting automatic discovery dashboard service...')

        # Initialize repositories
        postgres_service = pipeline.services.postgres
        match_repo = ArticleResearchMatchRepository(postgres_service)
        question_repo = ResearchQuestionRepository(postgres_service)  # noqa: F841

        # Initialize review service
        review_service = ObsidianReviewService(
            article_match_repository=match_repo,
        )

        # Initialize dashboard service
        dashboard_dir = Path(args.dashboard_dir) if args.dashboard_dir else None
        dashboard_service = DiscoveryDashboardService(
            postgres_service=postgres_service,
            obsidian_review_service=review_service,
            dashboard_dir=dashboard_dir,
            check_interval=args.check_interval,
            auto_export=not args.no_auto_export,
            auto_import=not args.no_auto_import,
        )

        # Start the service
        await dashboard_service.start()

        logger.success(
            'Dashboard service started!\n\n'
            'The service is now:\n'
            f'  Checking for new results every {args.check_interval} seconds\n'
            f'  Watching {dashboard_service.dashboard_dir}\n'
            f'  Auto-export: {"enabled" if not args.no_auto_export else "disabled"}\n'
            f'  Auto-import: {"enabled" if not args.no_auto_import else "disabled"}\n\n'
            'Open dashboard files in Obsidian and start reviewing!\n'
            'Changes you make will sync automatically.\n\n'
            'Press Ctrl+C to stop the service.'
        )

        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info('\n\nStopping dashboard service...')
            await dashboard_service.stop()
            logger.success('Dashboard service stopped')

        return 0

    except Exception as e:
        logger.exception(f'Failed to start dashboard service: {e}')
        return 1


async def run_apply_review(args, pipeline: ThothPipeline) -> int:
    """
    Apply review decisions from an Obsidian review file to the database.

    Reads the YAML frontmatter from the review file and updates the database
    with bookmarks, ratings, and notes based on user decisions.

    Args:
        args: Command line arguments
        pipeline: ThothPipeline instance

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    try:
        # Validate file path
        review_file = Path(args.file)
        if not review_file.exists():
            logger.error(f'Review file not found: {review_file}')
            return 1

        if not review_file.is_file():
            logger.error(f'Path is not a file: {review_file}')
            return 1

        logger.info(f'Reading review file: {review_file}')

        # Initialize repositories
        postgres_service = pipeline.services.postgres
        match_repo = ArticleResearchMatchRepository(postgres_service)
        question_repo = ResearchQuestionRepository(postgres_service)

        # Initialize review service
        vault_resolver = VaultPathResolver(pipeline.config)
        review_service = ObsidianReviewService(
            config=pipeline.config,
            match_repository=match_repo,
            question_repository=question_repo,
            vault_path_resolver=vault_resolver,
        )

        # Extract question_id from file if not provided
        import yaml

        content = review_file.read_text(encoding='utf-8')
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                question_id = UUID(frontmatter.get('question_id'))
            else:
                logger.error('Invalid review file: malformed YAML frontmatter')
                return 1
        else:
            logger.error('Invalid review file: missing YAML frontmatter')
            return 1

        logger.info(f'Processing reviews for question ID: {question_id}')

        # Dry run check
        if args.dry_run:
            logger.info('DRY RUN MODE - No changes will be made to the database')
            logger.info(f'Would process review file: {review_file}')

            # Parse and show what would be done
            articles = frontmatter.get('articles', [])
            preview_stats = {'liked': 0, 'disliked': 0, 'skip': 0, 'pending': 0}

            for article in articles:
                status = article.get('status', 'pending')
                if status in preview_stats:
                    preview_stats[status] += 1

            logger.info('\nReview summary (would be applied):')
            logger.info(f'  Liked: {preview_stats["liked"]}')
            logger.info(f'  Disliked: {preview_stats["disliked"]}')
            logger.info(f'  Skipped: {preview_stats["skip"]}')
            logger.info(f'  Pending: {preview_stats["pending"]} (no action)')
            logger.info('\nRun without --dry-run to apply changes')

            return 0

        # Apply decisions
        logger.info('Applying review decisions to database...')
        stats = await review_service.apply_review_decisions(
            review_file=review_file,
            question_id=question_id,
        )

        # Display results
        logger.info('\nReview decisions applied successfully!')
        logger.info('\nSummary:')
        logger.info(f'  Liked: {stats["liked"]} (bookmarked, rating=5)')
        logger.info(f'  Disliked: {stats["disliked"]} (rating=1)')
        logger.info(f'  Skipped: {stats["skip"]} (marked as viewed)')

        if stats['errors'] > 0:
            logger.warning(f'  Errors: {stats["errors"]} (check logs)')

        return 0

    except ValueError as e:
        logger.error(f'Validation error: {e}')
        return 1
    except RuntimeError as e:
        logger.error(f'Failed to apply decisions: {e}')
        return 1
    except Exception as e:
        logger.exception(f'Unexpected error applying review: {e}')
        return 1


def configure_subparser(subparsers) -> None:
    """
    Configure the subparser for research commands.

    Args:
        subparsers: Subparser collection from argparse
    """
    # Create research command group
    research_parser = subparsers.add_parser(
        'research',
        help='Research question management and review workflow',
    )
    research_subparsers = research_parser.add_subparsers(
        dest='research_command',
        help='Research command to run',
        required=True,
    )

    # Export review command
    export_parser = research_subparsers.add_parser(
        'export-review',
        help='Export article matches to Obsidian review file',
    )
    export_parser.add_argument(
        'question',
        type=str,
        help='Research question name or UUID',
    )
    export_parser.add_argument(
        '--output-path',
        type=str,
        help='Output file path (default: vault/Research/Questions/)',
    )
    export_parser.add_argument(
        '--min-relevance',
        type=float,
        default=0.5,
        help='Minimum relevance score (0.0-1.0, default: 0.5)',
    )
    export_parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of articles to include (default: 100)',
    )
    export_parser.add_argument(
        '--user-id',
        type=str,
        default='default',
        help='User ID for multi-user setups (default: "default")',
    )

    # Async wrapper for export
    def export_wrapper(args, pipeline):
        return asyncio.run(run_export_review(args, pipeline))

    export_parser.set_defaults(func=export_wrapper)

    # Apply review command
    apply_parser = research_subparsers.add_parser(
        'apply-review',
        help='Apply review decisions from Obsidian file to database',
    )
    apply_parser.add_argument(
        'file',
        type=str,
        help='Path to the review markdown file',
    )
    apply_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them',
    )

    # Async wrapper for apply
    def apply_wrapper(args, pipeline):
        return asyncio.run(run_apply_review(args, pipeline))

    apply_parser.set_defaults(func=apply_wrapper)

    # Start dashboard command
    dashboard_parser = research_subparsers.add_parser(
        'start-dashboard',
        help='Start automatic discovery dashboard service (auto-export and auto-import)',
    )
    dashboard_parser.add_argument(
        '--dashboard-dir',
        type=str,
        help='Dashboard directory (default: vault/Research/Dashboard/)',
    )
    dashboard_parser.add_argument(
        '--check-interval',
        type=int,
        default=60,
        help='Seconds between automatic export checks (default: 60)',
    )
    dashboard_parser.add_argument(
        '--no-auto-export',
        action='store_true',
        help='Disable automatic export of new results',
    )
    dashboard_parser.add_argument(
        '--no-auto-import',
        action='store_true',
        help='Disable automatic import of sentiment changes',
    )

    # Async wrapper for dashboard
    def dashboard_wrapper(args, pipeline):
        return asyncio.run(run_start_dashboard(args, pipeline))

    dashboard_parser.set_defaults(func=dashboard_wrapper)

    # Scheduler command (for running research question discovery scheduler)
    scheduler_parser = research_subparsers.add_parser(
        'scheduler',
        help='Run the research question discovery scheduler',
    )

    def scheduler_wrapper(args, pipeline):
        from thoth.cli.research_scheduler import run_research_scheduler

        return run_research_scheduler(args, pipeline)

    scheduler_parser.set_defaults(func=scheduler_wrapper)

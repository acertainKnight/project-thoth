"""
Memory CLI commands for managing memory jobs and summarization.

Provides command-line interface for memory management tasks including
episodic summarization scheduling and memory maintenance operations.
"""

import json

import click
from loguru import logger

from thoth.memory import MemoryJobConfig, get_shared_scheduler, get_shared_store


@click.group(name='memory')
def memory_cli():
    """Memory management commands."""
    pass


@memory_cli.group(name='jobs')
def jobs():
    """Memory job management commands."""
    pass


@jobs.command()
def list_jobs():
    """List available memory jobs and their configurations."""
    try:
        scheduler = get_shared_scheduler()

        click.echo('Available Memory Jobs:')
        click.echo('=' * 50)

        available_jobs = scheduler.get_available_jobs()
        for job_name, job_info in available_jobs.items():
            click.echo(f'\n📋 {job_name}')
            click.echo(f'   Description: {job_info["description"]}')

            default_config = job_info['default_config']
            click.echo(f'   Default interval: {default_config["interval_hours"]} hours')
            click.echo(f'   Default time: {default_config["time_of_day"] or "Any"}')
            click.echo(f'   Default enabled: {default_config["enabled"]}')

            if default_config['job_parameters']:
                click.echo('   Parameters:')
                for param, value in default_config['job_parameters'].items():
                    click.echo(f'     - {param}: {value}')

    except Exception as e:
        logger.error(f'Failed to list memory jobs: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@jobs.command()
def status():
    """Show status of all scheduled memory jobs."""
    try:
        scheduler = get_shared_scheduler()
        status = scheduler.get_schedule_status()

        click.echo(
            f'Memory Scheduler Status: {"🟢 Running" if status["running"] else "🔴 Stopped"}'
        )
        click.echo(f'Total jobs: {status["total_jobs"]}')
        click.echo(f'Enabled jobs: {status["enabled_jobs"]}')

        if status['jobs']:
            click.echo('\n📅 Scheduled Jobs:')
            click.echo('=' * 60)

            for job in status['jobs']:
                name = job['name']
                enabled = '🟢 Enabled' if job['enabled'] else '🔴 Disabled'
                configured = (
                    '✅ Configured' if job['configured'] else '❌ Not configured'
                )

                click.echo(f'\n{name}')
                click.echo(f'  Status: {enabled}, {configured}')
                click.echo(f'  Description: {job["description"]}')
                click.echo(f'  Interval: {job["interval_hours"]} hours')
                click.echo(f'  Time of day: {job["time_of_day"] or "Any"}')
                click.echo(f'  Last run: {job["last_run"] or "Never"}')
                click.echo(f'  Next run: {job["next_run"] or "Not scheduled"}')
                click.echo(f'  Run count: {job["run_count"]}')

                if job.get('last_result'):
                    result = job['last_result']
                    status_icon = '✅' if result.get('status') == 'success' else '❌'
                    click.echo(
                        f'  Last result: {status_icon} {result.get("summary", "No summary")}'
                    )
        else:
            click.echo('\nNo jobs scheduled.')

    except Exception as e:
        logger.error(f'Failed to get job status: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@jobs.command()
@click.argument('job_name')
@click.option('--enabled/--disabled', default=True, help='Enable or disable the job')
@click.option('--interval-hours', type=int, help='Interval between runs in hours')
@click.option('--time-of-day', help='Preferred time to run (HH:MM format)')
@click.option('--days-of-week', help='Days of week to run (comma-separated, 0=Monday)')
@click.option('--parameters', help='Job parameters as JSON string')
def add(
    job_name: str,
    enabled: bool,
    interval_hours: int | None,
    time_of_day: str | None,
    days_of_week: str | None,
    parameters: str | None,
):
    """Add a memory job to the scheduler."""
    try:
        scheduler = get_shared_scheduler()
        available_jobs = scheduler.get_available_jobs()

        if job_name not in available_jobs:
            click.echo(f'❌ Unknown job: {job_name}')
            click.echo('Available jobs:')
            for name in available_jobs.keys():
                click.echo(f'  - {name}')
            return

        # Use defaults if not specified
        default_config = available_jobs[job_name]['default_config']

        # Parse days of week
        days_list = None
        if days_of_week:
            try:
                days_list = [int(d.strip()) for d in days_of_week.split(',')]
            except ValueError:
                click.echo(
                    '❌ Invalid days-of-week format. Use comma-separated numbers (0=Monday)'
                )
                return

        # Parse parameters
        job_parameters = default_config['job_parameters'].copy()
        if parameters:
            try:
                custom_params = json.loads(parameters)
                job_parameters.update(custom_params)
            except json.JSONDecodeError:
                click.echo('❌ Invalid JSON in parameters')
                return

        config = MemoryJobConfig(
            enabled=enabled,
            interval_hours=interval_hours or default_config['interval_hours'],
            time_of_day=time_of_day or default_config['time_of_day'],
            days_of_week=days_list or default_config['days_of_week'],
            job_parameters=job_parameters,
        )

        scheduler.add_job(job_name, config)
        click.echo(f'✅ Added memory job: {job_name}')

    except Exception as e:
        logger.error(f'Failed to add memory job: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@jobs.command()
@click.argument('job_name')
def remove(job_name: str):
    """Remove a memory job from the scheduler."""
    try:
        scheduler = get_shared_scheduler()
        scheduler.remove_job(job_name)
        click.echo(f'✅ Removed memory job: {job_name}')

    except Exception as e:
        logger.error(f'Failed to remove memory job: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@jobs.command()
@click.argument('job_name')
@click.option('--user-id', help='Run for specific user (episodic_summarization only)')
def run(job_name: str, user_id: str | None):
    """Run a memory job immediately."""
    try:
        scheduler = get_shared_scheduler()

        click.echo(f'Running memory job: {job_name}')
        if user_id:
            click.echo(f'Target user: {user_id}')

        result = scheduler.run_job_now(job_name, user_id)

        if 'error' in result:
            click.echo(f'❌ Job failed: {result["error"]}')
            return

        status = result.get('status', 'unknown')
        click.echo(f'Job status: {status}')

        if job_name == 'episodic_summarization':
            if status == 'success':
                summaries = result.get('summaries_created', 0)
                memories = result.get('memories_analyzed', 0)
                cleaned = result.get('memories_cleaned', 0)
                click.echo(f'📊 Created {summaries} summaries from {memories} memories')
                if cleaned > 0:
                    click.echo(f'🧹 Cleaned up {cleaned} old memories')

            elif status == 'completed':
                total_summaries = result.get('total_summaries_created', 0)
                successful_users = result.get('successful_users', 0)
                failed_users = result.get('failed_users', 0)
                click.echo(f'📊 Processed {successful_users} users successfully')
                click.echo(f'📊 Created {total_summaries} total summaries')
                if failed_users > 0:
                    click.echo(f'❌ {failed_users} users failed processing')

            elif status == 'insufficient_memories':
                count = result.get('memory_count', 0)
                required = result.get('min_required', 0)
                click.echo(f'⚠️  Insufficient memories: {count} < {required}')

        click.echo('✅ Job completed')

    except Exception as e:
        logger.error(f'Failed to run memory job: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@jobs.command()
def start():
    """Start the memory scheduler."""
    try:
        scheduler = get_shared_scheduler()
        scheduler.start()
        click.echo('✅ Memory scheduler started')

    except Exception as e:
        logger.error(f'Failed to start memory scheduler: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@jobs.command()
def stop():
    """Stop the memory scheduler."""
    try:
        scheduler = get_shared_scheduler()
        scheduler.stop()
        click.echo('✅ Memory scheduler stopped')

    except Exception as e:
        logger.error(f'Failed to stop memory scheduler: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@memory_cli.group(name='summarize')
def summarize():
    """Memory summarization commands."""
    pass


@summarize.command()
@click.argument('user_id')
@click.option(
    '--analysis-window',
    type=int,
    default=168,
    help='Analysis window in hours (default: 168 = 1 week)',
)
@click.option(
    '--min-memories',
    type=int,
    default=10,
    help='Minimum memories required for summarization',
)
@click.option(
    '--cleanup/--no-cleanup',
    default=False,
    help='Clean up old memories after summarization',
)
def user(user_id: str, analysis_window: int, min_memories: int, cleanup: bool):
    """Summarize episodic memories for a specific user."""
    try:
        from thoth.memory.summarization import MemorySummarizationJob

        store = get_shared_store()
        summarizer_job = MemorySummarizationJob(
            memory_store=store,
            analysis_window_hours=analysis_window,
            min_memories_threshold=min_memories,
            cleanup_after_summary=cleanup,
        )

        click.echo(f'Summarizing memories for user: {user_id}')
        click.echo(f'Analysis window: {analysis_window} hours')
        click.echo(f'Minimum memories: {min_memories}')
        click.echo(f'Cleanup after: {"Yes" if cleanup else "No"}')

        result = summarizer_job.run_summarization(user_id)

        status = result.get('status')
        if status == 'success':
            summaries = result.get('summaries_created', 0)
            memories = result.get('memories_analyzed', 0)
            themes = result.get('themes_identified', 0)
            cleaned = result.get('memories_cleaned', 0)

            click.echo('✅ Summarization completed!')
            click.echo(f'📊 Analyzed: {memories} memories')
            click.echo(f'🎯 Identified: {themes} themes')
            click.echo(f'📝 Created: {summaries} summaries')
            if cleaned > 0:
                click.echo(f'🧹 Cleaned: {cleaned} old memories')

            # Show summary details
            summaries_list = result.get('summaries', [])
            if summaries_list:
                click.echo('\n📋 Generated Summaries:')
                for i, summary in enumerate(summaries_list, 1):
                    click.echo(
                        f'  {i}. {summary.get("theme", "Unknown")} - {summary.get("source_memories", 0)} memories'
                    )

        elif status == 'insufficient_memories':
            count = result.get('memory_count', 0)
            click.echo(f'⚠️  Insufficient memories: {count} < {min_memories}')

        else:
            click.echo(
                f'❌ Summarization failed: {result.get("message", "Unknown error")}'
            )

    except Exception as e:
        logger.error(f'Failed to summarize memories: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@summarize.command()
@click.option(
    '--analysis-window', type=int, default=168, help='Analysis window in hours'
)
@click.option('--min-memories', type=int, default=10, help='Minimum memories required')
def all_users(analysis_window: int, min_memories: int):
    """Summarize memories for all users with episodic memories."""
    try:
        from thoth.memory.summarization import MemorySummarizationJob

        store = get_shared_store()
        summarizer_job = MemorySummarizationJob(
            memory_store=store,
            analysis_window_hours=analysis_window,
            min_memories_threshold=min_memories,
            cleanup_after_summary=False,
        )

        click.echo('Summarizing memories for all users...')

        result = summarizer_job.run_for_all_users()

        status = result.get('status')
        if status == 'completed':
            total_users = result.get('total_users', 0)
            successful = result.get('successful_users', 0)
            failed = result.get('failed_users', 0)
            total_summaries = result.get('total_summaries_created', 0)

            click.echo('✅ Batch summarization completed!')
            click.echo(f'👥 Total users: {total_users}')
            click.echo(f'✅ Successful: {successful}')
            click.echo(f'❌ Failed: {failed}')
            click.echo(f'📝 Total summaries: {total_summaries}')

        elif status == 'no_users_found':
            click.echo('⚠️  No users with episodic memories found')

        else:
            click.echo(
                f'❌ Batch summarization failed: {result.get("message", "Unknown error")}'
            )

    except Exception as e:
        logger.error(f'Failed to summarize all users: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@memory_cli.group(name='stats')
def stats():
    """Memory statistics commands."""
    pass


@stats.command()
@click.argument('user_id')
def user_stats(user_id: str):
    """Show memory statistics for a specific user."""
    try:
        store = get_shared_store()

        click.echo(f'Memory Statistics for User: {user_id}')
        click.echo('=' * 50)

        stats = store.get_memory_stats(user_id)

        if 'error' in stats:
            click.echo(f'❌ Error: {stats["error"]}')
            return

        # Basic memory stats
        click.echo(f'Total memories: {stats.get("total_memories", 0)}')
        click.echo(f'Core memories: {stats.get("core_memories", 0)}')
        click.echo(f'Episodic memories: {stats.get("episodic_memories", 0)}')
        click.echo(f'Archival memories: {stats.get("archival_memories", 0)}')
        click.echo(f'Average salience: {stats.get("avg_salience", 0):.3f}')

        # Scope-specific salience
        for scope in ['core', 'episodic', 'archival']:
            scope_salience = stats.get(f'{scope}_avg_salience')
            if scope_salience is not None:
                click.echo(f'Average {scope} salience: {scope_salience:.3f}')

        # Retrieval metrics
        retrieval_metrics = stats.get('retrieval_metrics')
        if retrieval_metrics and retrieval_metrics.get('status') != 'no_data':
            click.echo('\n🔍 Retrieval Performance:')
            click.echo(f'Total queries: {retrieval_metrics.get("total_queries", 0)}')
            click.echo(
                f'Average search time: {retrieval_metrics.get("avg_search_time", 0):.3f}s'
            )
            click.echo(
                f'Activity level: {retrieval_metrics.get("activity_level", "unknown")}'
            )

            # Content preferences
            content_prefs = retrieval_metrics.get('content_preferences', {})
            if content_prefs:
                click.echo('Content preferences:')
                for content_type, count in list(content_prefs.items())[:3]:
                    click.echo(f'  - {content_type}: {count}')

    except Exception as e:
        logger.error(f'Failed to get user stats: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@stats.command()
def system_stats():
    """Show system-wide memory and retrieval performance statistics."""
    try:
        store = get_shared_store()

        click.echo('System Memory Performance Statistics')
        click.echo('=' * 50)

        performance = store.get_retrieval_performance()

        if performance.get('status') == 'error':
            click.echo(f'❌ Error: {performance.get("message")}')
            return

        if performance.get('status') == 'retrieval_pipeline_not_available':
            click.echo('⚠️  Retrieval pipeline not available')
            return

        if performance.get('status') == 'no_data':
            click.echo('⚠️  No retrieval data available')
            return

        # Performance metrics
        click.echo(f'Total queries: {performance.get("total_queries", 0)}')
        click.echo(
            f'Average search latency: {performance.get("avg_search_latency", 0):.3f}s'
        )
        click.echo(
            f'Average result count: {performance.get("avg_result_count", 0):.1f}'
        )
        click.echo(f'Cache hit rate: {performance.get("cache_hit_rate", 0):.1%}')
        click.echo(
            f'Average relevance score: {performance.get("avg_relevance_score", 0):.3f}'
        )
        click.echo(f'Unique users: {performance.get("unique_users", 0)}')

        # Pipeline configuration
        config = performance.get('pipeline_config', {})
        if config:
            click.echo('\n⚙️  Pipeline Configuration:')
            click.echo(
                f'Semantic search: {"✅ Enabled" if config.get("semantic_search_enabled") else "❌ Disabled"}'
            )
            click.echo(
                f'Caching: {"✅ Enabled" if config.get("caching_enabled") else "❌ Disabled"}'
            )
            click.echo(f'Cache TTL: {config.get("cache_ttl", 0)} seconds')
            click.echo(f'Max results: {config.get("max_results", 0)}')

    except Exception as e:
        logger.error(f'Failed to get system stats: {e}')
        click.echo(f'❌ Error: {e}', err=True)


if __name__ == '__main__':
    memory_cli()

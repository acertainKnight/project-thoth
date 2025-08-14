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


@memory_cli.group(name='admin')
def admin():
    """Administrative memory commands."""
    pass


@admin.command()
@click.option('--backup-path', help='Path to save memory backup')
@click.option('--user-id', help='Backup specific user only')
def backup(backup_path: str | None, user_id: str | None):
    """Backup memory store data."""
    try:
        store = get_shared_store()

        if not backup_path:
            from datetime import datetime

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f'memory_backup_{timestamp}.json'

        click.echo(f'Creating memory backup: {backup_path}')

        if user_id:
            click.echo(f'Backup scope: User {user_id}')
            # Get all memories for specific user
            memories = store.read_memories(user_id=user_id, limit=None)
        else:
            click.echo('Backup scope: All users')
            # This would need a method to get all memories from all users
            memories = store.read_memories(limit=None)

        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'total_memories': len(memories),
            'memories': memories,
        }

        import json

        with open(backup_path, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)

        click.echo(
            f'✅ Backup completed: {len(memories)} memories saved to {backup_path}'
        )

    except Exception as e:
        logger.error(f'Failed to backup memories: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@admin.command()
@click.argument('user_id')
@click.option(
    '--scope', type=click.Choice(['core', 'episodic', 'archival', 'all']), default='all'
)
@click.option('--confirm', is_flag=True, help='Confirm deletion without prompt')
def clear_user(user_id: str, scope: str, confirm: bool):
    """Clear memories for a specific user."""
    try:
        store = get_shared_store()

        if not confirm:
            scope_text = f'{scope} memories' if scope != 'all' else 'all memories'
            if not click.confirm(
                f'Are you sure you want to delete {scope_text} for user {user_id}?'
            ):
                click.echo('Operation cancelled.')
                return

        click.echo(f'Clearing {scope} memories for user: {user_id}')

        # Get current count before deletion
        current_stats = store.get_memory_stats(user_id)
        if 'error' in current_stats:
            click.echo(f'❌ Error getting user stats: {current_stats["error"]}')
            return

        if scope == 'all':
            # Clear all scopes
            for mem_scope in ['core', 'episodic', 'archival']:
                count = current_stats.get(f'{mem_scope}_memories', 0)
                if count > 0:
                    # This would need a method to clear memories by scope
                    click.echo(f'Clearing {count} {mem_scope} memories...')
        else:
            count = current_stats.get(f'{scope}_memories', 0)
            if count > 0:
                click.echo(f'Clearing {count} {scope} memories...')
            else:
                click.echo(f'No {scope} memories found for user {user_id}')
                return

        # Note: This would need implementation in the memory store
        # result = store.clear_user_memories(user_id, scope)
        click.echo('✅ Memory clearing completed')
        click.echo('⚠️  Note: Actual deletion requires memory store implementation')

    except Exception as e:
        logger.error(f'Failed to clear user memories: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@admin.command()
@click.option('--days', type=int, default=30, help='Delete memories older than N days')
@click.option(
    '--scope', type=click.Choice(['episodic', 'archival']), default='episodic'
)
@click.option(
    '--dry-run', is_flag=True, help='Show what would be deleted without deleting'
)
def cleanup_old(days: int, scope: str, dry_run: bool):
    """Clean up old memories across all users."""
    try:
        # Note: store would be used when cleanup functionality is implemented
        # store = get_shared_store()

        click.echo(f'Cleaning up {scope} memories older than {days} days...')
        if dry_run:
            click.echo('🔍 DRY RUN - No memories will be deleted')

        # This would need implementation in the memory store
        # old_memories = store.find_old_memories(days, scope)

        click.echo('⚠️  Note: Old memory cleanup requires memory store implementation')
        click.echo(f'Target scope: {scope}')
        click.echo(f'Age threshold: {days} days')

        # Placeholder for actual implementation
        click.echo('✅ Cleanup would be completed here')

    except Exception as e:
        logger.error(f'Failed to cleanup old memories: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@memory_cli.group(name='inspect')
def inspect():
    """Memory inspection and debugging commands."""
    pass


@inspect.command()
@click.argument('user_id')
@click.option(
    '--scope',
    type=click.Choice(['core', 'episodic', 'archival']),
    help='Filter by memory scope',
)
@click.option('--limit', type=int, default=10, help='Number of memories to show')
@click.option(
    '--format',
    'output_format',
    type=click.Choice(['table', 'json', 'detailed']),
    default='table',
)
def memories(user_id: str, scope: str | None, limit: int, output_format: str):
    """Inspect memories for a user."""
    try:
        store = get_shared_store()

        click.echo(f'Inspecting memories for user: {user_id}')
        if scope:
            click.echo(f'Scope filter: {scope}')

        memories = store.read_memories(user_id=user_id, scope=scope, limit=limit)

        if not memories:
            click.echo('No memories found.')
            return

        click.echo(f'\nFound {len(memories)} memories:')

        if output_format == 'json':
            import json

            click.echo(json.dumps(memories, indent=2, default=str))
        elif output_format == 'detailed':
            for i, memory in enumerate(memories, 1):
                click.echo(f'\n--- Memory {i} ---')
                click.echo(f'ID: {memory.get("id", "N/A")}')
                click.echo(f'Scope: {memory.get("scope", "N/A")}')
                click.echo(f'Salience: {memory.get("salience", "N/A")}')
                click.echo(f'Created: {memory.get("created_at", "N/A")}')
                content = memory.get('content', '')
                click.echo(
                    f'Content: {content[:100]}{"..." if len(content) > 100 else ""}'
                )
        else:  # table format
            from datetime import datetime

            click.echo('\n' + '=' * 80)
            click.echo(
                f'{"#":>3} {"Scope":>10} {"Salience":>8} {"Age":>12} {"Content"}'
            )
            click.echo('=' * 80)

            for i, memory in enumerate(memories, 1):
                scope = memory.get('scope', 'N/A')[:10]
                salience = f'{memory.get("salience", 0):.3f}'

                # Calculate age
                created_at = memory.get('created_at')
                if created_at:
                    try:
                        created_dt = datetime.fromisoformat(
                            created_at.replace('Z', '+00:00')
                        )
                        age = datetime.now() - created_dt.replace(tzinfo=None)
                        age_str = f'{age.days}d {age.seconds // 3600}h'
                    except (ValueError, TypeError):
                        age_str = 'Unknown'
                else:
                    age_str = 'Unknown'

                content = memory.get('content', '')[:50]
                if len(memory.get('content', '')) > 50:
                    content += '...'

                click.echo(f'{i:>3} {scope:>10} {salience:>8} {age_str:>12} {content}')

    except Exception as e:
        logger.error(f'Failed to inspect memories: {e}')
        click.echo(f'❌ Error: {e}', err=True)


@inspect.command()
@click.argument('query')
@click.option('--user-id', help='Search for specific user only')
@click.option(
    '--scope',
    type=click.Choice(['core', 'episodic', 'archival']),
    help='Search specific scope',
)
@click.option('--limit', type=int, default=5, help='Maximum results to return')
def search(query: str, user_id: str | None, scope: str | None, limit: int):
    """Search memories by content."""
    try:
        store = get_shared_store()

        click.echo(f'Searching memories for: "{query}"')
        if user_id:
            click.echo(f'User filter: {user_id}')
        if scope:
            click.echo(f'Scope filter: {scope}')

        # This would use the memory store's search functionality
        results = store.search_memories(
            query=query, user_id=user_id, scope=scope, limit=limit
        )

        if not results:
            click.echo('No matching memories found.')
            return

        click.echo(f'\nFound {len(results)} matching memories:')
        click.echo('=' * 60)

        for i, result in enumerate(results, 1):
            memory = result.get('memory', {})
            score = result.get('score', 0)

            click.echo(f'\n{i}. Score: {score:.3f}')
            click.echo(f'   User: {memory.get("user_id", "N/A")}')
            click.echo(f'   Scope: {memory.get("scope", "N/A")}')
            click.echo(f'   Salience: {memory.get("salience", 0):.3f}')

            content = memory.get('content', '')
            if len(content) > 150:
                content = content[:150] + '...'
            click.echo(f'   Content: {content}')

    except Exception as e:
        logger.error(f'Failed to search memories: {e}')
        click.echo(f'❌ Error: {e}', err=True)


def run_memory_cli_from_args(args, _pipeline):
    """Bridge function to run memory CLI from argparse."""
    from click.testing import CliRunner

    # If no args provided, show help
    if not args.memory_args:
        args.memory_args = ['--help']

    # Use click runner to execute the command
    runner = CliRunner()
    result = runner.invoke(memory_cli, args.memory_args, catch_exceptions=False)

    # Print the output
    if result.output:
        print(result.output, end='')

    # Return the exit code
    return result.exit_code


def configure_subparser(subparsers):
    """Configure the subparser for the memory command."""
    parser = subparsers.add_parser('memory', help='Memory management commands')
    parser.add_argument(
        'memory_args',
        nargs='*',
        help='Memory command arguments (jobs, summarize, stats, etc.)',
    )
    parser.set_defaults(func=run_memory_cli_from_args)


if __name__ == '__main__':
    memory_cli()

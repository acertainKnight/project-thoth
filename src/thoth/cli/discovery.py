import json
from pathlib import Path

from loguru import logger

from thoth.pipeline import ThothPipeline
from thoth.utilities.schemas import DiscoverySource, ScheduleConfig


def run_discovery_run(args, pipeline: ThothPipeline):
    """
    Run discovery for sources.
    """
    try:
        result = pipeline.services.discovery.run_discovery(
            source_name=args.source,
            max_articles=args.max_articles,
        )
        logger.info('Discovery run completed:')
        logger.info(f'  Articles found: {result.articles_found}')
        logger.info(f'  Articles filtered: {result.articles_filtered}')
        logger.info(f'  Articles downloaded: {result.articles_downloaded}')
        logger.info(f'  Execution time: {result.execution_time_seconds:.2f}s')
        if result.errors:
            logger.warning(f'  Errors encountered: {len(result.errors)}')
            for error in result.errors:
                logger.warning(f'    - {error}')
        return 0
    except Exception as e:
        logger.error(f'Error running discovery: {e}')
        return 1


def run_discovery_list(_args, pipeline: ThothPipeline):
    """List all discovery sources."""
    try:
        sources = pipeline.services.discovery.list_sources()
        if not sources:
            logger.info('No discovery sources configured.')
            return 0
        logger.info(f'Found {len(sources)} discovery sources:')
        logger.info('')
        for source in sources:
            logger.info(f'Name: {source.name}')
            logger.info(f'  Type: {source.source_type}')
            logger.info(f'  Description: {source.description}')
            logger.info(f'  Active: {source.is_active}')
            logger.info(f'  Last run: {source.last_run or "Never"}')
            if source.schedule_config:
                logger.info(
                    f'  Schedule: Every {source.schedule_config.interval_minutes} minutes'
                )
                logger.info(
                    f'  Max articles: {source.schedule_config.max_articles_per_run}'
                )
            logger.info('')
        return 0
    except Exception as e:
        logger.error(f'Error listing discovery sources: {e}')
        return 1


def run_discovery_show(args, pipeline: ThothPipeline):
    """
    Show detailed information about a discovery source.
    """
    try:
        source = pipeline.services.discovery.get_source(args.name)
        if not source:
            logger.error(f'Discovery source not found: {args.name}')
            return 1
        logger.info('Discovery Source Details:')
        logger.info(f'  Name: {source.name}')
        logger.info(f'  Type: {source.source_type}')
        logger.info(f'  Description: {source.description}')
        logger.info(f'  Active: {source.is_active}')
        logger.info(f'  Last run: {source.last_run or "Never"}')
        if source.schedule_config:
            logger.info(
                f'  Schedule: Every {source.schedule_config.interval_minutes} minutes'
            )
            logger.info(
                f'  Max articles: {source.schedule_config.max_articles_per_run}'
            )
        logger.info('')
        return 0
    except Exception as e:
        logger.error(f'Error showing discovery source: {e}')
        return 1


def run_discovery_create(args, pipeline: ThothPipeline):
    """
    Create a new discovery source.
    """
    try:
        config_data = {}
        if args.config_file:
            config_file = Path(args.config_file)
            if not config_file.exists():
                logger.error(f'Configuration file not found: {config_file}')
                return 1
            with open(config_file) as f:
                config_data = json.load(f)

        source_config = {
            'name': args.name,
            'source_type': args.type,
            'description': args.description,
            'is_active': True,
            'schedule_config': ScheduleConfig(
                interval_minutes=60,
                max_articles_per_run=50,
                enabled=True,
            ),
            'query_filters': [],
        }
        source_config.update(config_data)
        source = DiscoverySource(**source_config)
        pipeline.services.discovery.create_source(source)
        logger.info(f'Successfully created discovery source: {args.name}')
        logger.info(f'  Type: {args.type}')
        logger.info(f'  Description: {args.description}')
        return 0
    except Exception as e:
        logger.error(f'Error creating discovery source: {e}')
        return 1


def run_discovery_edit(args, pipeline: ThothPipeline):
    """
    Edit an existing discovery source.
    """
    try:
        source = pipeline.services.discovery.get_source(args.name)
        if not source:
            logger.error(f'Discovery source not found: {args.name}')
            return 1
        logger.info(f'Editing discovery source: {args.name}')
        if args.description:
            source.description = args.description
            logger.info(f'Updated description: {args.description}')
        if args.config_file:
            config_file = Path(args.config_file)
            if not config_file.exists():
                logger.error(f'Configuration file not found: {config_file}')
                return 1
            with open(config_file) as f:
                config_data = json.load(f)
            if 'api_config' in config_data:
                source.api_config = config_data['api_config']
                logger.info('Updated API configuration')
            if 'scraper_config' in config_data:
                source.scraper_config = config_data['scraper_config']
                logger.info('Updated scraper configuration')
            if 'schedule_config' in config_data:
                source.schedule_config = ScheduleConfig(
                    **config_data['schedule_config']
                )
                logger.info('Updated schedule configuration')
            if 'query_filters' in config_data:
                source.query_filters = config_data['query_filters']
                logger.info('Updated query filters')
        if args.active:
            source.is_active = args.active.lower() == 'true'
            logger.info(f'Updated active status: {source.is_active}')
        pipeline.services.discovery.update_source(source)
        logger.info(f'Successfully updated discovery source: {args.name}')
        logger.info(f'  Description: {source.description}')
        logger.info(f'  Active: {source.is_active}')
        return 0
    except Exception as e:
        logger.error(f'Error updating discovery source: {e}')
        return 1


def run_discovery_delete(args, pipeline: ThothPipeline):
    """
    Delete a discovery source.
    """
    try:
        source = pipeline.services.discovery.get_source(args.name)
        if not source:
            logger.error(f'Discovery source not found: {args.name}')
            return 1
        if not args.confirm:
            print('\nDiscovery Source Details:')
            print(f'  Name: {source.name}')
            print(f'  Type: {source.source_type}')
            print(f'  Description: {source.description}')
            print(f'  Active: {source.is_active}')
            print('\nAre you sure you want to delete this discovery source?')
            print('This action cannot be undone.')
            response = input('Type "delete" to confirm: ')
            if response.lower() != 'delete':
                logger.info('Deletion cancelled.')
                return 0
        pipeline.services.discovery.delete_source(args.name)
        logger.info(f'Successfully deleted discovery source: {args.name}')
        return 0
    except Exception as e:
        logger.error(f'Error deleting discovery source: {e}')
        return 1


def run_discovery_scheduler(args, pipeline: ThothPipeline):
    """
    Handle discovery scheduler commands.
    """
    import time

    try:
        if args.scheduler_command == 'start':
            pipeline.services.discovery.start_scheduler()
            logger.info('Discovery scheduler started. Press Ctrl+C to stop.')
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pipeline.services.discovery.stop_scheduler()
                logger.info('Discovery scheduler stopped.')
            return 0
        elif args.scheduler_command == 'status':
            status = pipeline.services.discovery.get_schedule_status()
            logger.info(f'Scheduler running: {status["running"]}')
            logger.info(f'Total sources: {status["total_sources"]}')
            logger.info(f'Enabled sources: {status["enabled_sources"]}')
            logger.info('')
            if status['sources']:
                logger.info('Sources:')
                for source in status['sources']:
                    logger.info(f'  {source["name"]}:')
                    logger.info(f'    Enabled: {source["enabled"]}')
                    logger.info(f'    Type: {source["source_type"]}')
                    logger.info(f'    Last run: {source["last_run"] or "Never"}')
                    logger.info(
                        f'    Next run: {source["next_run"] or "Not scheduled"}'
                    )
                    logger.info('')
            return 0
        else:
            logger.error(f'Unknown scheduler command: {args.scheduler_command}')
            return 1
    except Exception as e:
        logger.error(f'Error with scheduler command: {e}')
        return 1


def run_discovery_scheduler_stop(_args, pipeline: ThothPipeline):
    """Stop the discovery scheduler."""
    try:
        pipeline.services.discovery.stop_scheduler()
        logger.info('Discovery scheduler stopped.')
        return 0
    except Exception as e:
        logger.error(f'Error stopping discovery scheduler: {e}')
        return 1


def run_discovery_command(args, pipeline: ThothPipeline):
    """
    Handle discovery commands.
    """
    if not hasattr(args, 'discovery_command') or not args.discovery_command:
        logger.error('No discovery subcommand specified')
        return 1
    if args.discovery_command == 'run':
        return run_discovery_run(args, pipeline)
    elif args.discovery_command == 'list':
        return run_discovery_list(args, pipeline)
    elif args.discovery_command == 'create':
        return run_discovery_create(args, pipeline)
    elif args.discovery_command == 'edit':
        return run_discovery_edit(args, pipeline)
    elif args.discovery_command == 'delete':
        return run_discovery_delete(args, pipeline)
    elif args.discovery_command == 'scheduler':
        return run_discovery_scheduler(args, pipeline)
    elif args.discovery_command == 'show':
        return run_discovery_show(args, pipeline)
    else:
        logger.error(f'Unknown discovery command: {args.discovery_command}')
        return 1


def configure_subparser(subparsers):
    """Configure the subparser for the discovery command."""
    parser = subparsers.add_parser(
        'discovery', help='Manage article discovery sources and scheduling'
    )
    subparsers = parser.add_subparsers(
        dest='discovery_command', help='Discovery command to run'
    )

    run_parser = subparsers.add_parser('run', help='Run discovery for sources')
    run_parser.add_argument(
        '--source',
        type=str,
        help='Specific source to run (runs all active if not specified)',
    )
    run_parser.add_argument(
        '--max-articles', type=int, help='Maximum articles to process'
    )
    run_parser.set_defaults(func=run_discovery_run)

    list_parser = subparsers.add_parser('list', help='List all discovery sources')
    list_parser.set_defaults(func=run_discovery_list)

    show_parser = subparsers.add_parser(
        'show', help='Show detailed information about a discovery source'
    )
    show_parser.add_argument(
        '--name', type=str, required=True, help='Name of the discovery source to show'
    )
    show_parser.set_defaults(func=run_discovery_show)

    create_parser = subparsers.add_parser(
        'create', help='Create a new discovery source'
    )
    create_parser.add_argument(
        '--name', type=str, required=True, help='Name for the discovery source'
    )
    create_parser.add_argument(
        '--type',
        type=str,
        choices=['api', 'scraper'],
        required=True,
        help='Type of source',
    )
    create_parser.add_argument(
        '--description', type=str, required=True, help='Description of the source'
    )
    create_parser.add_argument(
        '--config-file', type=str, help='JSON file containing source configuration'
    )
    create_parser.set_defaults(func=run_discovery_create)

    edit_parser = subparsers.add_parser(
        'edit', help='Edit an existing discovery source'
    )
    edit_parser.add_argument(
        '--name', type=str, required=True, help='Name of the discovery source to edit'
    )
    edit_parser.add_argument(
        '--description', type=str, help='New description for the source'
    )
    edit_parser.add_argument(
        '--config-file',
        type=str,
        help='JSON file containing updated source configuration',
    )
    edit_parser.add_argument(
        '--active', type=str, choices=['true', 'false'], help='Set source active status'
    )
    edit_parser.set_defaults(func=run_discovery_edit)

    delete_parser = subparsers.add_parser('delete', help='Delete a discovery source')
    delete_parser.add_argument(
        '--name', type=str, required=True, help='Name of the discovery source to delete'
    )
    delete_parser.add_argument(
        '--confirm', action='store_true', help='Confirm deletion without prompting'
    )
    delete_parser.set_defaults(func=run_discovery_delete)

    scheduler_parser = subparsers.add_parser(
        'scheduler', help='Manage discovery scheduler'
    )
    scheduler_subparsers = scheduler_parser.add_subparsers(
        dest='scheduler_command', help='Scheduler command to run'
    )
    scheduler_start_parser = scheduler_subparsers.add_parser(
        'start', help='Start the discovery scheduler'
    )
    scheduler_start_parser.set_defaults(func=run_discovery_scheduler)
    scheduler_stop_parser = scheduler_subparsers.add_parser(
        'stop', help='Stop the discovery scheduler'
    )
    scheduler_stop_parser.set_defaults(func=run_discovery_scheduler_stop)
    scheduler_status_parser = scheduler_subparsers.add_parser(
        'status', help='Show scheduler status'
    )
    scheduler_status_parser.set_defaults(func=run_discovery_scheduler)
    parser.set_defaults(func=run_discovery_command)

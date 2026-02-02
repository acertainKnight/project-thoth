"""CLI command for running the research question discovery scheduler.

This runs the ResearchQuestionScheduler in a standalone container/process.
"""

import asyncio
import signal
from loguru import logger


def run_research_scheduler(args, pipeline):
    """Run the research question discovery scheduler."""
    logger.info('Starting Research Question Discovery Scheduler...')
    
    try:
        # Get services from pipeline
        service_manager = pipeline.services
        
        if not hasattr(service_manager, 'research_question'):
            logger.error('Research question service not available')
            return 1
            
        if not hasattr(service_manager, 'discovery_orchestrator'):
            logger.error('Discovery orchestrator service not available')
            return 1
        
        # Import scheduler
        from thoth.services.discovery_scheduler import ResearchQuestionScheduler
        
        # Create scheduler
        scheduler = ResearchQuestionScheduler(
            config=pipeline.config,
            research_question_service=service_manager.research_question,
            discovery_orchestrator=service_manager.discovery_orchestrator,
            postgres_service=service_manager.postgres,
        )
        
        # Create async runner
        async def run_scheduler():
            """Run scheduler in async context."""
            try:
                # Start scheduler
                await scheduler.start()
                logger.success('Research Question Scheduler started successfully!')
                logger.info('Checking for due questions every 5 minutes...')
                
                # Keep running until interrupted
                stop_event = asyncio.Event()
                
                def signal_handler(signum, frame):  # noqa: ARG001
                    logger.info('Shutdown signal received...')
                    stop_event.set()
                
                signal.signal(signal.SIGINT, signal_handler)
                signal.signal(signal.SIGTERM, signal_handler)
                
                # Wait for stop signal
                await stop_event.wait()
                
            finally:
                # Stop scheduler gracefully
                logger.info('Stopping research question scheduler...')
                await scheduler.stop()
                logger.success('Research question scheduler stopped')
        
        # Run the async function
        asyncio.run(run_scheduler())
        return 0
        
    except KeyboardInterrupt:
        logger.info('Scheduler stopped by user')
        return 0
    except Exception as e:
        logger.error(f'Failed to run research scheduler: {e}', exc_info=True)
        return 1

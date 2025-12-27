"""
Example usage of WorkflowExecutionService for browser-based article discovery.

This example demonstrates how to use the high-level WorkflowExecutionService
to execute browser workflows and extract articles.
"""

import asyncio
from uuid import UUID

from thoth.config import config
from thoth.discovery.browser import WorkflowExecutionService
from thoth.services.postgres_service import PostgresService
from thoth.utilities.schemas.browser_workflow import ExecutionParameters


async def main():
    """Demonstrate workflow execution service usage."""
    # Initialize PostgreSQL service
    postgres_service = PostgresService(config=config)
    await postgres_service.initialize()

    try:
        # Create workflow execution service
        service = WorkflowExecutionService(
            postgres_service=postgres_service,
            max_concurrent_browsers=3,
            default_timeout=30000,
            max_retries=3,
        )

        # Initialize service
        print('Initializing WorkflowExecutionService...')
        await service.initialize()
        print(f'Service initialized: {service.is_initialized}')

        # List active workflows
        print('\nFetching active workflows...')
        workflows = await service.list_active_workflows()
        print(f'Found {len(workflows)} active workflows')

        for workflow in workflows:
            print(f"  - {workflow.get('name')} ({workflow.get('id')})")

        # Execute a workflow (replace with actual workflow ID)
        if workflows:
            workflow_id = workflows[0]['id']
            print(f'\nExecuting workflow: {workflow_id}')

            # Define execution parameters
            parameters = ExecutionParameters(
                keywords=['machine learning', 'neural networks'],
                date_range='last_7d',
                subject='Computer Science',
            )

            # Execute workflow
            result = await service.execute_workflow(
                workflow_id=UUID(workflow_id) if isinstance(workflow_id, str) else workflow_id,
                parameters=parameters,
                max_articles=50,
            )

            # Print results
            print(f'\nExecution Results:')
            print(f'  Success: {result.stats.success}')
            print(f'  Articles extracted: {result.stats.articles_extracted}')
            print(f'  Duration: {result.stats.duration_ms}ms')
            print(f'  Pages visited: {result.stats.pages_visited}')

            if result.stats.error_message:
                print(f'  Error: {result.stats.error_message}')

            # Print articles
            if result.articles:
                print(f'\nExtracted Articles:')
                for i, article in enumerate(result.articles[:5], 1):
                    print(f'  {i}. {article.title}')
                    if article.authors:
                        print(f'     Authors: {", ".join(article.authors[:3])}')
                    if article.doi:
                        print(f'     DOI: {article.doi}')
                    print()

            # Print execution log summary
            if result.execution_log:
                print(f'\nExecution Log Summary:')
                for log_entry in result.execution_log[-5:]:
                    action = log_entry.get('action', 'unknown')
                    timestamp = log_entry.get('timestamp', '')
                    print(f'  [{timestamp}] {action}')

        else:
            print('\nNo active workflows found. Please create a workflow first.')
            print('\nExample workflow creation:')
            print('  1. Use the workflow management API')
            print('  2. Define workflow steps and extraction rules')
            print('  3. Test with execute_workflow()')

    finally:
        # Cleanup
        print('\nShutting down service...')
        await service.shutdown()
        await postgres_service.shutdown()
        print('Done!')


if __name__ == '__main__':
    asyncio.run(main())

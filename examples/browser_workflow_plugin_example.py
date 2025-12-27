"""Example usage of BrowserWorkflowPlugin for article discovery.

This example demonstrates how to use the browser workflow discovery plugin
to search for articles using browser automation workflows.
"""

import asyncio
from uuid import UUID

from thoth.discovery.plugins import BrowserWorkflowPlugin
from thoth.services.postgres_service import PostgresService
from thoth.utilities.schemas import ResearchQuery


async def main():
    """Example workflow execution via discovery plugin."""

    # Initialize PostgreSQL service
    postgres = PostgresService()
    await postgres.initialize()

    # Configure plugin with workflow ID
    config = {
        'workflow_id': 'your-workflow-uuid-here',  # Replace with actual workflow UUID
        'max_articles': 50,
        'timeout': 30000,  # 30 seconds
        'max_retries': 3,
    }

    # Create and initialize plugin
    plugin = BrowserWorkflowPlugin(
        postgres_service=postgres,
        config=config
    )
    await plugin.initialize()

    try:
        # Create research query
        query = ResearchQuery(
            name='Machine Learning Research',
            description='Find recent articles on machine learning advances',
            research_question='What are the latest advances in neural networks?',
            keywords=['machine learning', 'neural networks', 'deep learning'],
            required_topics=['artificial intelligence'],
            excluded_topics=['marketing', 'business'],
        )

        # Discover articles using browser workflow
        print(f"Executing browser workflow for query: {query.name}")
        articles = await plugin.discover_async(
            query=query,
            max_results=50,
        )

        # Display results
        print(f"\n✓ Found {len(articles)} articles")
        for i, article in enumerate(articles, 1):
            print(f"\n{i}. {article.title}")
            print(f"   Authors: {', '.join(article.authors[:3])}")
            print(f"   Source: {article.source}")
            print(f"   URL: {article.url}")
            if article.abstract:
                abstract_preview = article.abstract[:150]
                print(f"   Abstract: {abstract_preview}...")

    finally:
        # Cleanup
        await plugin.shutdown()
        await postgres.cleanup()


if __name__ == '__main__':
    asyncio.run(main())

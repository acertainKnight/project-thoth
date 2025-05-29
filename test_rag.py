#!/usr/bin/env python3
"""
Test script for Thoth RAG functionality.

This script tests the basic RAG operations:
1. Indexing documents
2. Searching the knowledge base
3. Asking questions
"""

import sys

from loguru import logger

from thoth.pipeline import ThothPipeline


def test_rag_system():
    """Test the RAG system functionality."""
    logger.info('Testing Thoth RAG System...')

    try:
        # Initialize pipeline
        pipeline = ThothPipeline()

        # Test 1: Get RAG stats
        logger.info('\nTest 1: Getting RAG stats...')
        stats = pipeline.get_rag_stats()
        logger.info(f'Current document count: {stats.get("document_count", 0)}')
        logger.info(f'Collection name: {stats.get("collection_name", "Unknown")}')

        # Test 2: Index knowledge base (if not already indexed)
        if stats.get('document_count', 0) == 0:
            logger.info('\nTest 2: Indexing knowledge base...')
            index_stats = pipeline.index_knowledge_base()
            logger.info(f'Indexed {index_stats["total_files"]} files')
            logger.info(f'Created {index_stats["total_chunks"]} chunks')
        else:
            logger.info(
                f'\nKnowledge base already contains {stats["document_count"]} documents'
            )

        # Test 3: Search knowledge base
        logger.info('\nTest 3: Searching knowledge base...')
        test_queries = [
            'machine learning',
            'neural networks',
            'transformer architecture',
            'attention mechanism',
        ]

        for query in test_queries:
            logger.info(f"\nSearching for: '{query}'")
            results = pipeline.search_knowledge_base(query, k=2)

            if results:
                logger.info(f'Found {len(results)} results:')
                for i, result in enumerate(results, 1):
                    logger.info(
                        f'  {i}. {result["title"]} (score: {result["score"]:.3f})'
                    )
            else:
                logger.info('  No results found')

        # Test 4: Ask questions
        logger.info('\nTest 4: Asking questions...')
        test_questions = [
            'What are the main topics in my research collection?',
            'What methodologies are discussed in the papers?',
        ]

        for question in test_questions:
            logger.info(f'\nQuestion: {question}')
            response = pipeline.ask_knowledge_base(question, k=3)
            logger.info(f'Answer: {response["answer"][:200]}...')

            if response.get('sources'):
                logger.info('Sources:')
                for source in response['sources']:
                    logger.info(f'  - {source["metadata"].get("title", "Unknown")}')

        logger.info('\n✅ RAG system test completed successfully!')

    except Exception as e:
        logger.error(f'❌ RAG system test failed: {e}')
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(test_rag_system())

#!/usr/bin/env python3
"""
Debug script to test embeddings initialization and identify potential issues.

This script helps diagnose the segmentation fault and "Killed" process issues
by testing the embedding manager initialization in a controlled environment.
"""

import sys
from pathlib import Path

# Add the src directory to the path so we can import thoth modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from loguru import logger

from thoth.rag.embeddings import EmbeddingManager
from thoth.utilities.config import get_config


def test_environment_safety():
    """Test if the environment is configured safely for embeddings."""
    logger.info('=== Testing Environment Safety ===')

    is_safe, issues = EmbeddingManager.check_environment_safety()

    if is_safe:
        logger.info('✅ Environment is configured safely for local embeddings')
    else:
        logger.warning('⚠️  Environment has potential issues:')
        for issue in issues:
            logger.warning(f'  - {issue}')

    return is_safe


def test_embedding_initialization(use_openai: bool = False):
    """Test embedding manager initialization."""
    logger.info(f'=== Testing Embedding Initialization (OpenAI: {use_openai}) ===')

    try:
        if use_openai:
            # Test with OpenAI embeddings (safer option)
            embedding_manager = EmbeddingManager(model='openai/text-embedding-3-small')
        else:
            # Test with local embeddings (potentially problematic)
            embedding_manager = EmbeddingManager(model='all-MiniLM-L6-v2')

        logger.info('✅ EmbeddingManager initialized successfully')

        # Test a simple embedding
        test_text = 'This is a test document for embeddings.'
        logger.info('Testing embedding generation...')

        embedding_model = embedding_manager.get_embedding_model()
        result = embedding_model.embed_query(test_text)

        logger.info(
            f'✅ Successfully generated embedding with {len(result)} dimensions'
        )
        return True

    except Exception as e:
        logger.error(f'❌ Failed to initialize embeddings: {e}')
        import traceback

        logger.error(f'Traceback: {traceback.format_exc()}')
        return False


def check_config():
    """Check the current configuration."""
    logger.info('=== Checking Configuration ===')

    try:
        config = get_config()
        logger.info(f'RAG embedding model: {config.rag_config.embedding_model}')

        # Check if OpenAI key is available
        openai_key = config.api_keys.openai_key
        if openai_key:
            logger.info('✅ OpenAI API key is configured')
        else:
            logger.warning('⚠️  OpenAI API key not configured')

        return config
    except Exception as e:
        logger.error(f'❌ Failed to load configuration: {e}')
        return None


def main():
    """Main debugging function."""
    logger.info('🔍 Starting Thoth Embeddings Debug Session')

    # Check configuration
    config = check_config()
    if not config:
        return 1

    # Test environment safety
    test_environment_safety()

    # Determine if we should test OpenAI or local embeddings
    has_openai_key = bool(config.api_keys.openai_key)
    current_model = config.rag_config.embedding_model
    is_openai_model = current_model.startswith('openai/')

    logger.info(f'Current embedding model: {current_model}')
    logger.info(f'Is OpenAI model: {is_openai_model}')
    logger.info(f'Has OpenAI key: {has_openai_key}')

    # Test current configuration
    logger.info('Testing current configuration...')
    success = test_embedding_initialization(use_openai=is_openai_model)

    if not success and not is_openai_model:
        logger.info('❌ Local embeddings failed. Trying OpenAI embeddings...')
        if has_openai_key:
            openai_success = test_embedding_initialization(use_openai=True)
            if openai_success:
                logger.info(
                    '✅ OpenAI embeddings work! Consider switching to avoid segfaults.'
                )
                logger.info(
                    'To switch to OpenAI embeddings, add this to your .env file:'
                )
                logger.info('RAG_EMBEDDING_MODEL=openai/text-embedding-3-small')
        else:
            logger.warning('No OpenAI key available to test fallback option')

    if success:
        logger.info('🎉 All tests passed!')
        return 0
    else:
        logger.error('💥 Tests failed - see messages above for debugging steps')
        return 1


if __name__ == '__main__':
    sys.exit(main())

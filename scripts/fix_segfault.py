#!/usr/bin/env python3
"""
Segmentation fault troubleshooting script for Thoth.

This script helps diagnose and fix segmentation fault issues
that occur when using ChromaDB with sentence-transformers.
"""

import os
import sys
from pathlib import Path


def configure_safe_environment() -> None:
    """Configure environment variables to prevent segmentation faults."""
    print('🔧 Configuring safe environment variables...')

    # Prevent threading issues that can cause segfaults
    env_vars = {
        'TOKENIZERS_PARALLELISM': 'false',
        'OMP_NUM_THREADS': '1',
        'MKL_NUM_THREADS': '1',
        'NUMEXPR_NUM_THREADS': '1',
        'TORCH_NUM_THREADS': '1',
        'CHROMA_MAX_BATCH_SIZE': '100',
        'CHROMA_SUBMIT_BATCH_SIZE': '100',
        'SQLITE_ENABLE_PREUPDATE_HOOK': '0',
        'SQLITE_ENABLE_FTS5': '0',
    }

    for key, value in env_vars.items():
        os.environ[key] = value
        print(f'  ✓ Set {key}={value}')


def check_dependencies() -> bool:
    """Check if problematic dependencies are installed."""
    print('\n🔍 Checking dependencies...')

    try:
        import chromadb

        print(f'  ✓ ChromaDB version: {chromadb.__version__}')
    except ImportError:
        print('  ❌ ChromaDB not installed')
        return False

    try:
        import sentence_transformers

        print(f'  ✓ sentence-transformers version: {sentence_transformers.__version__}')
    except ImportError:
        print('  ❌ sentence-transformers not installed')
        return False

    try:
        import torch

        print(f'  ✓ PyTorch version: {torch.__version__}')
        print(f'  ✓ CUDA available: {torch.cuda.is_available()}')
    except ImportError:
        print('  ❌ PyTorch not installed')
        return False

    return True


def test_embeddings() -> bool:
    """Test if embeddings can be created without segfault."""
    print('\n🧪 Testing embeddings creation...')

    try:
        from langchain_huggingface import HuggingFaceEmbeddings

        # Test with safe configuration
        embeddings = HuggingFaceEmbeddings(
            model_name='all-MiniLM-L6-v2',
            model_kwargs={'device': 'cpu', 'trust_remote_code': False},
            encode_kwargs={
                'normalize_embeddings': True,
                'batch_size': 8,
            },
            show_progress=False,
        )

        # Test with small batch
        test_texts = ['This is a test sentence.', 'Another test sentence.']
        result = embeddings.embed_documents(test_texts)

        print(f'  ✓ Successfully created embeddings for {len(test_texts)} texts')
        print(f'  ✓ Embedding dimension: {len(result[0])}')
        return True

    except Exception as e:
        print(f'  ❌ Failed to create embeddings: {e}')
        return False


def test_chromadb() -> bool:
    """Test if ChromaDB can be initialized without segfault."""
    print('\n📦 Testing ChromaDB initialization...')

    try:
        import tempfile

        import chromadb

        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use the new ChromaDB client initialization format (v0.5.0+)
            # No longer need chromadb.config.Settings - it's deprecated
            client = chromadb.PersistentClient(path=temp_dir)

            # Create a test collection
            collection = client.get_or_create_collection(
                name='test_collection', metadata={'description': 'Test collection'}
            )

            print('  ✓ Successfully created ChromaDB client')
            print(f'  ✓ Successfully created collection: {collection.name}')

            # Clean up
            client.delete_collection('test_collection')

        return True

    except Exception as e:
        print(f'  ❌ Failed to initialize ChromaDB: {e}')
        return False


def test_integration() -> bool:
    """Test integration between ChromaDB and embeddings."""
    print('\n🔗 Testing ChromaDB + embeddings integration...')

    try:
        import tempfile

        from langchain_chroma import Chroma
        from langchain_core.documents import Document
        from langchain_huggingface import HuggingFaceEmbeddings

        # Create embeddings
        embeddings = HuggingFaceEmbeddings(
            model_name='all-MiniLM-L6-v2',
            model_kwargs={'device': 'cpu', 'trust_remote_code': False},
            encode_kwargs={
                'normalize_embeddings': True,
                'batch_size': 4,
            },
            show_progress=False,
        )

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create vector store
            vector_store = Chroma(
                collection_name='test_integration',
                embedding_function=embeddings,
                persist_directory=temp_dir,
            )

            # Test adding documents in small batch
            test_docs = [
                Document(page_content='Test document 1', metadata={'source': 'test1'}),
                Document(page_content='Test document 2', metadata={'source': 'test2'}),
            ]

            # Add documents
            doc_ids = vector_store.add_documents(test_docs)
            print(f'  ✓ Successfully added {len(doc_ids)} documents')

            # Test search
            results = vector_store.similarity_search('test', k=1)
            print(f'  ✓ Successfully searched, found {len(results)} results')

        return True

    except Exception as e:
        print(f'  ❌ Integration test failed: {e}')
        return False


def clean_chromadb_cache() -> None:
    """Clean ChromaDB cache that might be corrupted."""
    print('\n🧹 Cleaning ChromaDB cache...')

    cache_dirs = [
        Path.home() / '.cache' / 'chroma',
        Path.home() / '.cache' / 'huggingface',
        Path('/tmp').glob('chroma_*'),
        Path('/tmp').glob('chromadb_*'),
    ]

    for cache_dir in cache_dirs:
        if isinstance(cache_dir, Path) and cache_dir.exists():
            try:
                import shutil

                shutil.rmtree(cache_dir)
                print(f'  ✓ Removed cache directory: {cache_dir}')
            except Exception as e:
                print(f'  ❌ Failed to remove {cache_dir}: {e}')


def main() -> None:
    """Main troubleshooting function."""
    print('🩺 Thoth Segmentation Fault Troubleshooter')
    print('=' * 50)

    # Configure safe environment first
    configure_safe_environment()

    # Check dependencies
    if not check_dependencies():
        print('\n❌ Missing dependencies. Please run: uv install')
        sys.exit(1)

    # Clean cache
    clean_chromadb_cache()

    # Run tests
    tests = [
        ('Embeddings', test_embeddings),
        ('ChromaDB', test_chromadb),
        ('Integration', test_integration),
    ]

    passed = 0
    for test_name, test_func in tests:
        if test_func():
            passed += 1
        else:
            print(f'\n❌ {test_name} test failed')

    print(f'\n📊 Test Results: {passed}/{len(tests)} tests passed')

    if passed == len(tests):
        print('\n✅ All tests passed! The segmentation fault issue should be resolved.')
        print('\n💡 Tips to prevent future segfaults:')
        print('  - Always set environment variables before importing ML libraries')
        print('  - Use smaller batch sizes when processing documents')
        print('  - Avoid concurrent ChromaDB operations')
        print('  - Keep ChromaDB and sentence-transformers updated')
    else:
        print('\n❌ Some tests failed. Try the following:')
        print('  1. Restart your terminal/shell')
        print("  2. Clear Python cache: python -Bc 'import sys; sys.exit(0)'")
        print('  3. Reinstall dependencies: uv install --force-reinstall')
        print('  4. Check system memory and available disk space')
        print('  5. Try running with: PYTHONPATH=. python scripts/fix_segfault.py')


if __name__ == '__main__':
    main()

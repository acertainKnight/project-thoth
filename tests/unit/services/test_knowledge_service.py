"""
Tests for KnowledgeService.

Basic tests for external knowledge management functionality.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from thoth.services.knowledge_service import KnowledgeService


@pytest.fixture
def mock_postgres_service():
    """Mock PostgreSQL service."""
    service = MagicMock()
    service.pool = MagicMock()
    return service


@pytest.fixture
def mock_rag_service():
    """Mock RAG service."""
    service = MagicMock()
    service.index_paper_by_id_async = AsyncMock(return_value=['doc_id_1', 'doc_id_2'])
    service.search_async = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_config():
    """Mock config."""
    config = MagicMock()
    config.secrets.mistral_api_key = 'test_key'
    return config


@pytest.fixture
def knowledge_service(mock_postgres_service, mock_rag_service, mock_config):
    """Create KnowledgeService instance."""
    return KnowledgeService(
        mock_postgres_service,
        mock_rag_service,
        mock_config,
    )


@pytest.mark.asyncio
async def test_create_collection(knowledge_service):
    """Test creating a knowledge collection."""
    collection_data = {
        'id': str(uuid4()),
        'name': 'Test Collection',
        'description': 'Test description',
    }

    knowledge_service.collection_repo.create = AsyncMock(return_value=collection_data)

    result = await knowledge_service.create_collection(
        'Test Collection', 'Test description'
    )

    assert result['name'] == 'Test Collection'
    assert result['description'] == 'Test description'
    knowledge_service.collection_repo.create.assert_called_once_with(
        'Test Collection', 'Test description'
    )


@pytest.mark.asyncio
async def test_list_collections(knowledge_service):
    """Test listing collections."""
    collections = [
        {'id': str(uuid4()), 'name': 'Collection 1', 'document_count': 5},
        {'id': str(uuid4()), 'name': 'Collection 2', 'document_count': 10},
    ]

    knowledge_service.collection_repo.list_all = AsyncMock(return_value=collections)

    result = await knowledge_service.list_collections()

    assert len(result) == 2
    assert result[0]['name'] == 'Collection 1'
    assert result[1]['document_count'] == 10


@pytest.mark.asyncio
async def test_get_collection_by_name(knowledge_service):
    """Test getting collection by name."""
    collection_data = {
        'id': str(uuid4()),
        'name': 'Test Collection',
    }

    knowledge_service.collection_repo.get_by_name = AsyncMock(
        return_value=collection_data
    )

    result = await knowledge_service.get_collection(name='Test Collection')

    assert result['name'] == 'Test Collection'
    knowledge_service.collection_repo.get_by_name.assert_called_once_with(
        'Test Collection'
    )


@pytest.mark.asyncio
async def test_delete_collection(knowledge_service):
    """Test deleting a collection."""
    collection_id = uuid4()

    knowledge_service.collection_repo.delete = AsyncMock(return_value=True)

    result = await knowledge_service.delete_collection(
        collection_id, delete_documents=False
    )

    assert result is True
    knowledge_service.collection_repo.delete.assert_called_once_with(
        collection_id, False
    )


@pytest.mark.asyncio
async def test_search_external_knowledge(knowledge_service, mock_rag_service):
    """Test searching external knowledge."""
    collection_id = uuid4()
    collection_data = {'id': str(collection_id), 'name': 'Test Collection'}

    knowledge_service.collection_repo.get_by_name = AsyncMock(
        return_value=collection_data
    )

    search_results = [
        {'content': 'Test content', 'metadata': {'title': 'Test Document'}}
    ]
    mock_rag_service.search_async.return_value = search_results

    result = await knowledge_service.search_external_knowledge(
        'test query',
        'Test Collection',
        k=5,
    )

    assert result == search_results
    mock_rag_service.search_async.assert_called_once()
    call_args = mock_rag_service.search_async.call_args
    assert call_args.kwargs['query'] == 'test query'
    assert call_args.kwargs['k'] == 5
    assert call_args.kwargs['filter']['document_category'] == 'external'
    assert call_args.kwargs['filter']['collection_id'] == str(collection_id)


@pytest.mark.asyncio
async def test_file_converter_supported_extensions():
    """Test that FileConverter reports correct supported extensions."""
    from thoth.services.file_converter import FileConverter

    extensions = FileConverter.get_supported_extensions()

    assert '.pdf' in extensions
    assert '.md' in extensions
    assert '.txt' in extensions
    assert '.html' in extensions
    assert '.epub' in extensions
    assert '.docx' in extensions


@pytest.mark.asyncio
async def test_file_converter_is_supported():
    """Test FileConverter.is_supported()."""
    from thoth.services.file_converter import FileConverter

    assert FileConverter.is_supported(Path('test.pdf')) is True
    assert FileConverter.is_supported(Path('test.md')) is True
    assert FileConverter.is_supported(Path('test.docx')) is True
    assert FileConverter.is_supported(Path('test.xyz')) is False

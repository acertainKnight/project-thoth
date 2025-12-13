"""Pytest configuration and shared fixtures."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config(temp_dir):
    """Create mock configuration for tests."""
    config = Mock()
    config.pdf_dir = str(temp_dir / 'vault' / 'thoth' / 'papers' / 'pdfs')
    config.notes_dir = str(temp_dir / 'vault' / 'thoth' / 'notes')
    config.markdown_dir = str(temp_dir / 'data' / 'markdown')
    config.workspace_dir = str(temp_dir)

    # Create directories
    Path(config.pdf_dir).mkdir(parents=True, exist_ok=True)
    Path(config.notes_dir).mkdir(parents=True, exist_ok=True)
    Path(config.markdown_dir).mkdir(parents=True, exist_ok=True)

    return config


@pytest.fixture
def sample_tracker_data():
    """Sample processed_pdfs.json data."""
    return {
        '/old/path/paper1.pdf': {
            'note_path': '/old/path/notes/paper1.md',
            'new_pdf_path': '/old/path/pdfs/paper1.pdf',
            'new_markdown_path': '/old/path/markdown/paper1_markdown.md',
            'processed_at': '2025-11-28T10:00:00'
        },
        '/old/path/paper2.pdf': {
            'note_path': '/old/path/notes/paper2.md',
            'new_pdf_path': '/old/path/pdfs/paper2.pdf',
            'new_markdown_path': '/old/path/markdown/paper2_markdown.md',
            'processed_at': '2025-11-28T11:00:00'
        }
    }


@pytest.fixture
def sample_citation_graph():
    """Sample citations.graphml data."""
    return {
        'nodes': [
            {
                'id': 'paper1',
                'title': 'Test Paper 1',
                'pdf_path': '/old/path/paper1.pdf',
                'markdown_path': '/old/path/markdown/paper1.md',
                'obsidian_path': '/old/path/notes/paper1.md'
            },
            {
                'id': 'paper2',
                'title': 'Test Paper 2',
                'pdf_path': 'paper2.pdf',  # Already normalized
                'markdown_path': 'paper2.md',
                'obsidian_path': 'paper2.md'
            }
        ],
        'edges': [
            {'source': 'paper1', 'target': 'paper2', 'type': 'citation'}
        ]
    }


@pytest.fixture
def sample_embeddings():
    """Sample embedding data for testing."""
    return [
        {
            'id': 'emb1',
            'paper_id': 'paper1',
            'embedding': [0.1] * 768,  # Simulated 768-dim vector
            'chunk_text': 'This is a test chunk of text from paper 1.'
        },
        {
            'id': 'emb2',
            'paper_id': 'paper2',
            'embedding': [0.2] * 768,
            'chunk_text': 'This is a test chunk of text from paper 2.'
        }
    ]


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = MagicMock()
    session.execute = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def mock_vector_store():
    """Create mock vector store."""
    store = MagicMock()
    store.add_documents = MagicMock(return_value=['id1', 'id2'])
    store.similarity_search = MagicMock(return_value=[])
    return store


@pytest.fixture
async def async_mock_db_session():
    """Create async mock database session."""
    session = MagicMock()
    session.execute = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session

"""
Tests for TagService.
"""

from unittest.mock import MagicMock

import pytest

from thoth.services.base import ServiceError
from thoth.services.llm_service import LLMService
from thoth.services.tag_service import TagService


@pytest.fixture
def mock_citation_tracker():
    """Create a mock citation tracker."""
    return MagicMock()


def test_tag_service_initialization(thoth_config, mock_citation_tracker):
    """Test that TagService can be initialized."""
    llm_service = LLMService(config=thoth_config)
    service = TagService(
        config=thoth_config,
        llm_service=llm_service,
        citation_tracker=mock_citation_tracker,
    )
    assert service is not None
    assert service.llm_service is not None
    assert service.citation_tracker is not None


@pytest.fixture
def tag_service_with_mock_data(thoth_config, mock_citation_tracker):
    """Create a TagService instance with mock data for testing."""
    llm_service = LLMService(config=thoth_config)
    # Mock the graph to return some tags
    mock_citation_tracker.graph.nodes.return_value = [
        ('id1', {'analysis': {'tags': ['tag1', 'tag2']}}),
        ('id2', {'analysis': {'tags': ['tag2', 'tag3']}}),
    ]
    service = TagService(
        config=thoth_config,
        llm_service=llm_service,
        citation_tracker=mock_citation_tracker,
    )
    return service


def test_consolidate_and_retag_no_tracker(thoth_config):
    """Test that consolidate_and_retag raises an error if no citation
    tracker is provided.
    """
    llm_service = LLMService(config=thoth_config)
    # Initialize service without a citation tracker
    service = TagService(
        config=thoth_config, llm_service=llm_service, citation_tracker=None
    )
    with pytest.raises(ServiceError, match='Citation tracker not available'):
        service.consolidate_and_retag()


def test_extract_all_tags(tag_service_with_mock_data):
    """Test extracting all unique tags from the mock graph."""
    tags = tag_service_with_mock_data.extract_all_tags()
    assert isinstance(tags, list)
    assert set(tags) == {'tag1', 'tag2', 'tag3'}


def test_initialize(tag_service_with_mock_data):
    """Test that the initialize method runs without error."""
    # The main point is to ensure no exceptions are raised
    tag_service_with_mock_data.initialize()


def test_extract_all_tags_handles_exception(monkeypatch, tag_service_with_mock_data):
    """Test that extract_all_tags handles exceptions gracefully."""

    # Arrange
    def mock_extract_all_tags_from_graph(*_args, **_kwargs):
        raise Exception('Extraction failed')

    monkeypatch.setattr(
        tag_service_with_mock_data.tag_consolidator,
        'extract_all_tags_from_graph',
        mock_extract_all_tags_from_graph,
    )

    # Act & Assert
    with pytest.raises(
        ServiceError,
        match='Error in TagService while extracting tags: Extraction failed',
    ):
        tag_service_with_mock_data.extract_all_tags()


def test_consolidate_tags_no_existing_tags(tag_service_with_mock_data):
    """Test that consolidate_tags returns an empty result if no tags are provided."""
    result = tag_service_with_mock_data.consolidate_tags([])
    assert result == {'tag_mappings': {}, 'consolidated_tags': [], 'reasoning': {}}


def test_consolidate_tags_handles_exception(monkeypatch, tag_service_with_mock_data):
    """Test that consolidate_tags handles exceptions gracefully."""

    # Arrange
    def mock_consolidate_tags(*_args, **_kwargs):
        raise Exception('Consolidation failed')

    monkeypatch.setattr(
        tag_service_with_mock_data.tag_consolidator,
        'consolidate_tags',
        mock_consolidate_tags,
    )

    # Act & Assert
    with pytest.raises(
        ServiceError,
        match='Error in TagService while consolidating tags: Consolidation failed',
    ):
        tag_service_with_mock_data.consolidate_tags(['tag1'])


def test_suggest_tags_no_abstract(tag_service_with_mock_data):
    """Test that suggest_tags returns an empty result if no abstract is provided."""
    result = tag_service_with_mock_data.suggest_tags(
        title='Test Title', abstract='', current_tags=[], available_tags=['tag1']
    )
    assert result == {
        'suggested_tags': [],
        'reasoning': 'No abstract or available tags',
    }


def test_suggest_tags_handles_exception(monkeypatch, tag_service_with_mock_data):
    """Test that suggest_tags handles exceptions gracefully."""

    # Arrange
    def mock_suggest_tags(*_args, **_kwargs):
        raise Exception('Suggestion failed')

    monkeypatch.setattr(
        tag_service_with_mock_data.tag_consolidator,
        'suggest_additional_tags',
        mock_suggest_tags,
    )

    # Act & Assert
    with pytest.raises(
        ServiceError,
        match="Error in TagService while suggesting tags for 'Test Title': Suggestion failed",
    ):
        tag_service_with_mock_data.suggest_tags(
            title='Test Title',
            abstract='Some abstract',
            current_tags=[],
            available_tags=['tag1'],
        )


def test_consolidate_and_retag(monkeypatch, tag_service_with_mock_data):
    """Test the consolidate_and_retag method."""
    # Arrange
    monkeypatch.setattr(
        tag_service_with_mock_data, 'extract_all_tags', lambda: ['tag1', 'tag2']
    )
    monkeypatch.setattr(
        tag_service_with_mock_data,
        'consolidate_tags',
        lambda _tags: {
            'tag_mappings': {'tag1': 'tagA'},
            'consolidated_tags': ['tagA', 'tag2'],
        },
    )
    monkeypatch.setattr(
        tag_service_with_mock_data,
        '_process_articles_for_tags',
        lambda _mappings, _available: {
            'articles_processed': 1,
            'articles_updated': 1,
            'tags_added': 1,
        },
    )

    # Act
    stats = tag_service_with_mock_data.consolidate_and_retag()

    # Assert
    assert stats['articles_processed'] == 1
    assert stats['tags_consolidated'] == 1
    assert stats['original_tag_count'] == 2
    assert stats['final_tag_count'] == 2


def test_consolidate_only(monkeypatch, tag_service_with_mock_data):
    """Test the consolidate_only method."""
    # Arrange
    monkeypatch.setattr(
        tag_service_with_mock_data, 'extract_all_tags', lambda: ['tag1', 'tag2']
    )
    monkeypatch.setattr(
        tag_service_with_mock_data,
        'consolidate_tags',
        lambda _tags: {
            'tag_mappings': {'tag1': 'tagA'},
            'consolidated_tags': ['tagA', 'tag2'],
        },
    )
    monkeypatch.setattr(
        tag_service_with_mock_data,
        '_apply_tag_mappings',
        lambda _mappings: {'articles_processed': 1, 'articles_updated': 1},
    )

    # Act
    stats = tag_service_with_mock_data.consolidate_only()

    # Assert
    assert stats['articles_processed'] == 1
    assert stats['tags_consolidated'] == 1


def test_suggest_additional(monkeypatch, tag_service_with_mock_data):
    """Test the suggest_additional method."""
    # Arrange
    monkeypatch.setattr(
        tag_service_with_mock_data, 'extract_all_tags', lambda: ['tag1', 'tag2']
    )
    monkeypatch.setattr(
        tag_service_with_mock_data,
        '_suggest_tags_for_all_articles',
        lambda _available: {
            'articles_processed': 1,
            'articles_updated': 1,
            'tags_added': 1,
        },
    )

    # Act
    stats = tag_service_with_mock_data.suggest_additional()

    # Assert
    assert stats['articles_processed'] == 1
    assert stats['tags_added'] == 1
    assert stats['vocabulary_size'] == 2

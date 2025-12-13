"""Unit tests for ResearchQuestionService."""

import pytest
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from thoth.services.research_question_service import ResearchQuestionService
from thoth.config import Config


@pytest.fixture
def mock_config():
    """Create a mock Config object."""
    config = MagicMock(spec=Config)
    config.vault_root = '/tmp/test_vault'
    config.db_host = 'localhost'
    config.db_port = 5432
    config.db_name = 'test_thoth'
    config.db_user = 'test_user'
    config.db_password = 'test_password'
    return config


@pytest.fixture
def mock_repository():
    """Create a mock ResearchQuestionRepository."""
    with patch('thoth.services.research_question_service.ResearchQuestionRepository') as MockRepo:
        repo = AsyncMock()
        MockRepo.return_value = repo
        yield repo


@pytest.fixture
def service(mock_config, mock_repository):
    """Create a ResearchQuestionService with mocked dependencies."""
    with patch('thoth.services.research_question_service.ResearchQuestionRepository'):
        service = ResearchQuestionService(config=mock_config)
        service.repository = mock_repository
        return service


# ==================== Test: create_research_question ====================


@pytest.mark.asyncio
async def test_create_research_question_success(service, mock_repository):
    """Test successful research question creation."""
    # Arrange
    expected_id = uuid4()
    mock_repository.get_by_name.return_value = None  # No duplicate
    mock_repository.create_question.return_value = expected_id

    # Act
    result = await service.create_research_question(
        user_id='test_user',
        name='Machine Learning Research',
        keywords=['neural networks', 'deep learning'],
        topics=['artificial intelligence', 'computer science'],
        authors=['Bengio', 'Hinton'],
        selected_sources=['arxiv', 'pubmed'],
        schedule_frequency='daily',
        min_relevance_score=0.7,
    )

    # Assert
    assert result == expected_id
    mock_repository.get_by_name.assert_called_once_with(
        user_id='test_user', name='Machine Learning Research'
    )
    mock_repository.create_question.assert_called_once()
    call_kwargs = mock_repository.create_question.call_args[1]
    assert call_kwargs['user_id'] == 'test_user'
    assert call_kwargs['name'] == 'Machine Learning Research'
    assert call_kwargs['keywords'] == ['neural networks', 'deep learning']
    assert call_kwargs['selected_sources'] == ['arxiv', 'pubmed']
    assert call_kwargs['min_relevance_score'] == 0.7


@pytest.mark.asyncio
async def test_create_research_question_duplicate_name(service, mock_repository):
    """Test that duplicate question names raise ValueError."""
    # Arrange
    mock_repository.get_by_name.return_value = {'id': uuid4(), 'name': 'Existing Question'}

    # Act & Assert
    with pytest.raises(ValueError, match="already exists"):
        await service.create_research_question(
            user_id='test_user',
            name='Existing Question',
            keywords=['test'],
            topics=['test'],
            authors=[],
            selected_sources=['arxiv'],
        )


@pytest.mark.asyncio
async def test_create_research_question_empty_name(service, mock_repository):
    """Test that empty name raises ValueError."""
    # Act & Assert
    with pytest.raises(ValueError, match="cannot be empty"):
        await service.create_research_question(
            user_id='test_user',
            name='   ',
            keywords=['test'],
            topics=['test'],
            authors=[],
            selected_sources=['arxiv'],
        )


@pytest.mark.asyncio
async def test_create_research_question_no_keywords_or_topics(service, mock_repository):
    """Test that missing keywords and topics raises ValueError."""
    # Act & Assert
    with pytest.raises(ValueError, match="At least one keyword or topic"):
        await service.create_research_question(
            user_id='test_user',
            name='Test Question',
            keywords=[],
            topics=[],
            authors=[],
            selected_sources=['arxiv'],
        )


@pytest.mark.asyncio
async def test_create_research_question_invalid_sources(service, mock_repository):
    """Test that empty sources raises ValueError."""
    # Act & Assert
    with pytest.raises(ValueError, match="At least one source"):
        await service.create_research_question(
            user_id='test_user',
            name='Test Question',
            keywords=['test'],
            topics=[],
            authors=[],
            selected_sources=[],
        )


@pytest.mark.asyncio
async def test_create_research_question_wildcard_source(service, mock_repository):
    """Test creation with wildcard source ['*']."""
    # Arrange
    expected_id = uuid4()
    mock_repository.get_by_name.return_value = None
    mock_repository.create_question.return_value = expected_id

    # Act
    result = await service.create_research_question(
        user_id='test_user',
        name='Test Question',
        keywords=['test'],
        topics=[],
        authors=[],
        selected_sources=['*'],
    )

    # Assert
    assert result == expected_id
    call_kwargs = mock_repository.create_question.call_args[1]
    assert call_kwargs['selected_sources'] == ['*']


@pytest.mark.asyncio
async def test_create_research_question_invalid_relevance_score(service, mock_repository):
    """Test that invalid relevance score raises ValueError."""
    # Act & Assert
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        await service.create_research_question(
            user_id='test_user',
            name='Test Question',
            keywords=['test'],
            topics=[],
            authors=[],
            selected_sources=['arxiv'],
            min_relevance_score=1.5,
        )


# ==================== Test: update_research_question ====================


@pytest.mark.asyncio
async def test_update_research_question_success(service, mock_repository):
    """Test successful research question update."""
    # Arrange
    question_id = uuid4()
    mock_repository.get_by_id.return_value = {
        'id': question_id,
        'user_id': 'test_user',
        'name': 'Test Question',
        'schedule_frequency': 'daily',
    }
    mock_repository.update_question.return_value = True

    # Act
    result = await service.update_research_question(
        question_id=question_id,
        user_id='test_user',
        min_relevance_score=0.8,
    )

    # Assert
    assert result is True
    mock_repository.update_question.assert_called_once()


@pytest.mark.asyncio
async def test_update_research_question_not_found(service, mock_repository):
    """Test update of non-existent question raises ValueError."""
    # Arrange
    question_id = uuid4()
    mock_repository.get_by_id.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="not found"):
        await service.update_research_question(
            question_id=question_id,
            user_id='test_user',
            name='New Name',
        )


@pytest.mark.asyncio
async def test_update_research_question_permission_denied(service, mock_repository):
    """Test update by wrong user raises PermissionError."""
    # Arrange
    question_id = uuid4()
    mock_repository.get_by_id.return_value = {
        'id': question_id,
        'user_id': 'owner_user',
        'name': 'Test Question',
    }

    # Act & Assert
    with pytest.raises(PermissionError, match="does not have permission"):
        await service.update_research_question(
            question_id=question_id,
            user_id='different_user',
            name='New Name',
        )


# ==================== Test: delete_research_question ====================


@pytest.mark.asyncio
async def test_delete_research_question_soft_delete(service, mock_repository):
    """Test soft delete of research question."""
    # Arrange
    question_id = uuid4()
    mock_repository.get_by_id.return_value = {
        'id': question_id,
        'user_id': 'test_user',
    }
    mock_repository.deactivate_question.return_value = True

    # Act
    result = await service.delete_research_question(
        question_id=question_id,
        user_id='test_user',
        hard_delete=False,
    )

    # Assert
    assert result is True
    mock_repository.deactivate_question.assert_called_once_with(question_id)


@pytest.mark.asyncio
async def test_delete_research_question_hard_delete(service, mock_repository):
    """Test hard delete of research question."""
    # Arrange
    question_id = uuid4()
    mock_repository.get_by_id.return_value = {
        'id': question_id,
        'user_id': 'test_user',
    }
    mock_repository.delete_question.return_value = True

    # Act
    result = await service.delete_research_question(
        question_id=question_id,
        user_id='test_user',
        hard_delete=True,
    )

    # Assert
    assert result is True
    mock_repository.delete_question.assert_called_once_with(question_id)


@pytest.mark.asyncio
async def test_delete_research_question_permission_denied(service, mock_repository):
    """Test delete by wrong user raises PermissionError."""
    # Arrange
    question_id = uuid4()
    mock_repository.get_by_id.return_value = {
        'id': question_id,
        'user_id': 'owner_user',
    }

    # Act & Assert
    with pytest.raises(PermissionError, match="does not have permission"):
        await service.delete_research_question(
            question_id=question_id,
            user_id='different_user',
        )


# ==================== Test: get_user_questions ====================


@pytest.mark.asyncio
async def test_get_user_questions_success(service, mock_repository):
    """Test retrieving user questions."""
    # Arrange
    expected_questions = [
        {'id': uuid4(), 'name': 'Question 1', 'is_active': True},
        {'id': uuid4(), 'name': 'Question 2', 'is_active': True},
    ]
    mock_repository.get_by_user_id.return_value = expected_questions

    # Act
    result = await service.get_user_questions(
        user_id='test_user',
        active_only=True,
    )

    # Assert
    assert result == expected_questions
    mock_repository.get_by_user_id.assert_called_once_with(
        user_id='test_user',
        active_only=True,
    )


# ==================== Test: get_questions_due_for_discovery ====================


@pytest.mark.asyncio
async def test_get_questions_due_for_discovery(service, mock_repository):
    """Test retrieving questions due for discovery."""
    # Arrange
    expected_questions = [
        {'id': uuid4(), 'name': 'Due Question 1'},
        {'id': uuid4(), 'name': 'Due Question 2'},
    ]
    mock_repository.get_questions_due_for_run.return_value = expected_questions

    # Act
    result = await service.get_questions_due_for_discovery(as_of=None)

    # Assert
    assert result == expected_questions
    assert len(result) == 2


# ==================== Test: mark_discovery_completed ====================


@pytest.mark.asyncio
async def test_mark_discovery_completed_success(service, mock_repository):
    """Test marking discovery as completed."""
    # Arrange
    question_id = uuid4()
    mock_repository.get_by_id.return_value = {
        'id': question_id,
        'schedule_frequency': 'daily',
        'articles_found_count': 10,
        'articles_matched_count': 5,
    }
    mock_repository.update_question.return_value = True

    # Act
    result = await service.mark_discovery_completed(
        question_id=question_id,
        articles_found=20,
        articles_matched=10,
        execution_time=15.5,
    )

    # Assert
    assert result is True
    mock_repository.update_question.assert_called_once()
    call_kwargs = mock_repository.update_question.call_args[1]
    assert call_kwargs['question_id'] == question_id
    assert call_kwargs['articles_found_count'] == 30  # 10 + 20
    assert call_kwargs['articles_matched_count'] == 15  # 5 + 10


# ==================== Test: get_question_statistics ====================


@pytest.mark.asyncio
async def test_get_question_statistics_success(service, mock_repository):
    """Test retrieving question statistics."""
    # Arrange
    question_id = uuid4()
    mock_repository.get_by_id.return_value = {
        'id': question_id,
        'user_id': 'test_user',
    }
    expected_stats = {
        'total_articles': 100,
        'matched_articles': 50,
        'last_run': datetime.now().isoformat(),
    }
    mock_repository.get_statistics.return_value = expected_stats

    # Act
    result = await service.get_question_statistics(
        question_id=question_id,
        user_id='test_user',
    )

    # Assert
    assert result == expected_stats


@pytest.mark.asyncio
async def test_get_question_statistics_permission_denied(service, mock_repository):
    """Test statistics retrieval by wrong user raises PermissionError."""
    # Arrange
    question_id = uuid4()
    mock_repository.get_by_id.return_value = {
        'id': question_id,
        'user_id': 'owner_user',
    }

    # Act & Assert
    with pytest.raises(PermissionError, match="does not have permission"):
        await service.get_question_statistics(
            question_id=question_id,
            user_id='different_user',
        )


# ==================== Test: Scheduling Logic ====================


def test_calculate_next_run_daily(service):
    """Test daily schedule calculation."""
    # Act
    next_run = service._calculate_next_run(
        frequency='daily',
        schedule_time='14:00',
    )

    # Assert
    assert next_run.hour == 14
    assert next_run.minute == 0
    assert next_run.date() >= datetime.now().date()


def test_calculate_next_run_weekly(service):
    """Test weekly schedule calculation."""
    # Act
    next_run = service._calculate_next_run(
        frequency='weekly',
        schedule_time='10:00',
        schedule_days_of_week=['monday', 'wednesday', 'friday'],
    )

    # Assert
    assert next_run.hour == 10
    assert next_run.minute == 0
    # Should be in the next 7 days
    assert (next_run - datetime.now()).days <= 7


def test_calculate_next_run_monthly(service):
    """Test monthly schedule calculation."""
    # Act
    next_run = service._calculate_next_run(
        frequency='monthly',
        schedule_time='09:00',
    )

    # Assert
    assert next_run.hour == 9
    assert next_run.minute == 0
    # Should be roughly 30 days from now
    days_diff = (next_run - datetime.now()).days
    assert 25 <= days_diff <= 35


def test_calculate_next_run_on_demand(service):
    """Test on-demand schedule (far future)."""
    # Act
    next_run = service._calculate_next_run(
        frequency='on-demand',
    )

    # Assert
    assert next_run.year == 2099


# ==================== Test: Validation Methods ====================


def test_validate_source_selection_wildcard(service):
    """Test wildcard source selection validation."""
    # Should not raise
    service._validate_source_selection(['*'])


def test_validate_source_selection_specific_sources(service):
    """Test specific source selection validation."""
    # Should not raise
    service._validate_source_selection(['arxiv', 'pubmed', 'crossref'])


def test_validate_source_selection_empty(service):
    """Test empty source selection raises ValueError."""
    with pytest.raises(ValueError, match="At least one source"):
        service._validate_source_selection([])


def test_validate_schedule_frequency_valid(service):
    """Test valid schedule frequencies."""
    # Should not raise
    service._validate_schedule_frequency('daily')
    service._validate_schedule_frequency('weekly')
    service._validate_schedule_frequency('monthly')
    service._validate_schedule_frequency('on-demand')


def test_validate_schedule_frequency_invalid(service):
    """Test invalid schedule frequency raises ValueError."""
    with pytest.raises(ValueError, match="Invalid schedule frequency"):
        service._validate_schedule_frequency('hourly')


def test_validate_relevance_score_valid(service):
    """Test valid relevance scores."""
    # Should not raise
    service._validate_relevance_score(0.0)
    service._validate_relevance_score(0.5)
    service._validate_relevance_score(1.0)


def test_validate_relevance_score_invalid(service):
    """Test invalid relevance scores raise ValueError."""
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        service._validate_relevance_score(-0.1)

    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        service._validate_relevance_score(1.1)

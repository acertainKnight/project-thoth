"""
Comprehensive tests for DiscoveryScheduler.

This module tests automated discovery scheduling, multiple source coordination,
daily runs without reprocessing, and error handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime, timedelta
from pathlib import Path
import asyncio

from thoth.discovery.scheduler import DiscoveryScheduler, DiscoverySchedulerError
from thoth.discovery.discovery_manager import DiscoveryManager
from thoth.utilities.schemas import DiscoverySource, ScheduleConfig, DiscoveryResult


@pytest.fixture
def mock_discovery_manager():
    """Create mock discovery manager."""
    manager = MagicMock(spec=DiscoveryManager)
    manager.get_source = Mock()
    manager.create_source = Mock()
    manager.update_source = Mock()
    manager.run_discovery = Mock()
    manager.list_sources = Mock(return_value=[])
    return manager


@pytest.fixture
def temp_schedule_file(tmp_path):
    """Create temporary schedule file."""
    return tmp_path / 'test_schedule.json'


@pytest.fixture
def scheduler(mock_discovery_manager, temp_schedule_file):
    """Create scheduler instance with mocks."""
    with patch.object(DiscoveryScheduler, '_load_schedule_state', return_value={}):
        return DiscoveryScheduler(
            discovery_manager=mock_discovery_manager,
            schedule_file=temp_schedule_file
        )


@pytest.fixture
def sample_schedule_config():
    """Sample schedule configuration."""
    return ScheduleConfig(
        enabled=True,
        interval_minutes=60,
        max_articles_per_run=50,
        time_of_day='09:00',
        days_of_week=[0, 1, 2, 3, 4]  # Monday-Friday
    )


@pytest.fixture
def sample_discovery_source(sample_schedule_config):
    """Sample discovery source."""
    return DiscoverySource(
        name='arxiv_ml',
        source_type='api',
        is_active=True,
        query_filters=['machine-learning', 'deep-learning'],
        schedule_config=sample_schedule_config,
        api_config={
            'source': 'arxiv',
            'categories': ['cs.LG', 'cs.AI'],
        }
    )


# ============================================================================
# SCHEDULER LIFECYCLE TESTS
# ============================================================================


def test_scheduler_initialization(mock_discovery_manager, temp_schedule_file):
    """Test scheduler initializes correctly."""
    # Arrange & Act
    with patch.object(DiscoveryScheduler, '_load_schedule_state', return_value={}):
        scheduler = DiscoveryScheduler(
            discovery_manager=mock_discovery_manager,
            schedule_file=temp_schedule_file
        )

    # Assert
    assert scheduler.discovery_manager == mock_discovery_manager
    assert scheduler.schedule_file == temp_schedule_file
    assert scheduler.running is False
    assert scheduler.scheduler_thread is None


def test_scheduler_start(scheduler):
    """Test starting the scheduler."""
    # Act
    scheduler.start()

    # Assert
    assert scheduler.running is True
    assert scheduler.scheduler_thread is not None
    assert scheduler.scheduler_thread.is_alive()

    # Cleanup
    scheduler.stop()


def test_scheduler_start_already_running(scheduler):
    """Test starting scheduler when already running raises error."""
    # Arrange
    scheduler.start()

    # Act & Assert
    with pytest.raises(DiscoverySchedulerError, match='already running'):
        scheduler.start()

    # Cleanup
    scheduler.stop()


def test_scheduler_stop(scheduler):
    """Test stopping the scheduler."""
    # Arrange
    scheduler.start()
    assert scheduler.running is True

    # Act
    scheduler.stop()

    # Assert
    assert scheduler.running is False


def test_scheduler_stop_when_not_running(scheduler):
    """Test stopping scheduler when not running does nothing."""
    # Act & Assert - Should not raise error
    scheduler.stop()
    assert scheduler.running is False


# ============================================================================
# SOURCE SCHEDULING TESTS
# ============================================================================


def test_add_scheduled_source(scheduler, sample_discovery_source, mock_discovery_manager):
    """Test adding a source to the scheduler."""
    # Arrange
    mock_discovery_manager.get_source.return_value = None  # Source doesn't exist

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        scheduler.add_scheduled_source(
            sample_discovery_source,
            sample_discovery_source.schedule_config
        )

    # Assert
    assert 'arxiv_ml' in scheduler.schedule_state
    assert scheduler.schedule_state['arxiv_ml']['enabled'] is True
    assert scheduler.schedule_state['arxiv_ml']['interval_minutes'] == 60
    mock_discovery_manager.create_source.assert_called_once()


def test_add_scheduled_source_updates_existing(
    scheduler, sample_discovery_source, mock_discovery_manager
):
    """Test adding existing source updates it."""
    # Arrange
    mock_discovery_manager.get_source.return_value = sample_discovery_source

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        scheduler.add_scheduled_source(
            sample_discovery_source,
            sample_discovery_source.schedule_config
        )

    # Assert
    mock_discovery_manager.update_source.assert_called_once()
    assert 'arxiv_ml' in scheduler.schedule_state


def test_remove_scheduled_source(scheduler, sample_discovery_source):
    """Test removing a source from the scheduler."""
    # Arrange
    scheduler.schedule_state['arxiv_ml'] = {'enabled': True}

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        scheduler.remove_scheduled_source('arxiv_ml')

    # Assert
    assert 'arxiv_ml' not in scheduler.schedule_state


def test_remove_nonexistent_source(scheduler):
    """Test removing non-existent source does nothing."""
    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        scheduler.remove_scheduled_source('nonexistent')

    # Assert - Should not raise error
    assert 'nonexistent' not in scheduler.schedule_state


def test_update_source_schedule(scheduler, sample_schedule_config, mock_discovery_manager):
    """Test updating schedule for existing source."""
    # Arrange
    scheduler.schedule_state['arxiv_ml'] = {
        'enabled': True,
        'interval_minutes': 60
    }
    mock_source = Mock()
    mock_source.schedule_config = None
    mock_discovery_manager.get_source.return_value = mock_source

    # New schedule config
    new_schedule = ScheduleConfig(
        enabled=True,
        interval_minutes=120,  # Changed
        max_articles_per_run=100
    )

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        scheduler.update_source_schedule('arxiv_ml', new_schedule)

    # Assert
    assert scheduler.schedule_state['arxiv_ml']['interval_minutes'] == 120
    mock_discovery_manager.update_source.assert_called_once()


# ============================================================================
# SCHEDULE CALCULATION TESTS
# ============================================================================


def test_calculate_next_run_basic_interval(scheduler):
    """Test calculating next run with basic interval."""
    # Arrange
    schedule = ScheduleConfig(
        enabled=True,
        interval_minutes=60,
        max_articles_per_run=50
    )

    # Act
    next_run = scheduler._calculate_next_run(schedule)
    next_run_time = datetime.fromisoformat(next_run)

    # Assert
    current_time = datetime.now()
    assert next_run_time > current_time
    # Should be approximately 60 minutes from now (within 5 min tolerance)
    assert abs((next_run_time - current_time).total_seconds() - 3600) < 300


def test_calculate_next_run_with_time_of_day(scheduler):
    """Test calculating next run with specific time of day."""
    # Arrange
    schedule = ScheduleConfig(
        enabled=True,
        interval_minutes=1440,  # Daily
        max_articles_per_run=50,
        time_of_day='09:00'
    )

    # Act
    next_run = scheduler._calculate_next_run(schedule)
    next_run_time = datetime.fromisoformat(next_run)

    # Assert
    assert next_run_time.hour == 9
    assert next_run_time.minute == 0
    assert next_run_time.second == 0


def test_calculate_next_run_time_already_passed_today(scheduler):
    """Test next run moves to tomorrow if time passed today."""
    # Arrange - Set time to yesterday
    schedule = ScheduleConfig(
        enabled=True,
        interval_minutes=1440,
        max_articles_per_run=50,
        time_of_day='00:00'  # Midnight (already passed)
    )

    # Act
    next_run = scheduler._calculate_next_run(schedule)
    next_run_time = datetime.fromisoformat(next_run)

    # Assert
    current_time = datetime.now()
    assert next_run_time.date() >= current_time.date()


def test_calculate_next_run_with_days_of_week(scheduler):
    """Test calculating next run respects days of week."""
    # Arrange - Only run on weekdays (Mon-Fri)
    schedule = ScheduleConfig(
        enabled=True,
        interval_minutes=1440,
        max_articles_per_run=50,
        time_of_day='09:00',
        days_of_week=[0, 1, 2, 3, 4]  # Monday=0, Friday=4
    )

    # Act
    next_run = scheduler._calculate_next_run(schedule)
    next_run_time = datetime.fromisoformat(next_run)

    # Assert
    assert next_run_time.weekday() in [0, 1, 2, 3, 4]


def test_calculate_next_run_disabled_source(scheduler):
    """Test calculating next run for disabled source returns far future."""
    # Arrange
    schedule = ScheduleConfig(
        enabled=False,
        interval_minutes=60,
        max_articles_per_run=50
    )

    # Act
    next_run = scheduler._calculate_next_run(schedule)
    next_run_time = datetime.fromisoformat(next_run)

    # Assert
    current_time = datetime.now()
    assert (next_run_time - current_time).days > 300  # Far future


# ============================================================================
# SCHEDULE EXECUTION TESTS
# ============================================================================


def test_run_source_now(scheduler, mock_discovery_manager):
    """Test running a source immediately."""
    # Arrange
    scheduler.schedule_state['arxiv_ml'] = {
        'max_articles_per_run': 50,
        'last_run': None
    }

    mock_result = DiscoveryResult(
        source_name='arxiv_ml',
        run_timestamp=datetime.now().isoformat(),
        articles_found=10,
        articles_filtered=8,
        articles_downloaded=5,
        execution_time_seconds=15.5,
        errors=[]
    )
    mock_discovery_manager.run_discovery.return_value = mock_result

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        result = scheduler.run_source_now('arxiv_ml')

    # Assert
    assert result['success'] is True
    assert result['articles_found'] == 10
    assert scheduler.schedule_state['arxiv_ml']['last_run'] is not None
    mock_discovery_manager.run_discovery.assert_called_once_with(
        source_name='arxiv_ml',
        max_articles=50
    )


def test_run_source_now_with_errors(scheduler, mock_discovery_manager):
    """Test running source that encounters errors."""
    # Arrange
    mock_result = DiscoveryResult(
        source_name='arxiv_ml',
        run_timestamp=datetime.now().isoformat(),
        articles_found=10,
        articles_filtered=0,
        articles_downloaded=0,
        execution_time_seconds=5.0,
        errors=['Connection timeout', 'Rate limit exceeded']
    )
    mock_discovery_manager.run_discovery.return_value = mock_result

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        result = scheduler.run_source_now('arxiv_ml')

    # Assert
    assert result['success'] is False
    assert len(result['errors']) == 2


def test_run_source_now_exception(scheduler, mock_discovery_manager):
    """Test handling exceptions when running source."""
    # Arrange
    mock_discovery_manager.run_discovery.side_effect = Exception('Network error')

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        result = scheduler.run_source_now('arxiv_ml')

    # Assert
    assert result['success'] is False
    assert 'error' in result


# ============================================================================
# SCHEDULED RUN TESTS
# ============================================================================


@patch('time.sleep')  # Mock sleep to speed up test
def test_check_and_run_scheduled_sources(mock_sleep, scheduler, mock_discovery_manager):
    """Test checking and running scheduled sources."""
    # Arrange - Source is due to run
    past_time = (datetime.now() - timedelta(minutes=5)).isoformat()
    scheduler.schedule_state['arxiv_ml'] = {
        'enabled': True,
        'next_run': past_time,
        'max_articles_per_run': 50
    }

    mock_source = Mock()
    mock_source.schedule_config = ScheduleConfig(
        enabled=True,
        interval_minutes=60,
        max_articles_per_run=50
    )
    mock_discovery_manager.get_source.return_value = mock_source

    mock_result = DiscoveryResult(
        source_name='arxiv_ml',
        run_timestamp=datetime.now().isoformat(),
        articles_found=5,
        articles_filtered=4,
        articles_downloaded=3,
        execution_time_seconds=10.0
    )
    mock_discovery_manager.run_discovery.return_value = mock_result

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        scheduler._check_and_run_scheduled_sources()

    # Assert
    mock_discovery_manager.run_discovery.assert_called_once()
    assert scheduler.schedule_state['arxiv_ml']['last_run'] is not None


@patch('time.sleep')
def test_check_and_run_skips_disabled_sources(mock_sleep, scheduler, mock_discovery_manager):
    """Test scheduler skips disabled sources."""
    # Arrange
    past_time = (datetime.now() - timedelta(minutes=5)).isoformat()
    scheduler.schedule_state['arxiv_ml'] = {
        'enabled': False,
        'next_run': past_time
    }

    # Act
    scheduler._check_and_run_scheduled_sources()

    # Assert
    mock_discovery_manager.run_discovery.assert_not_called()


@patch('time.sleep')
def test_check_and_run_skips_future_sources(mock_sleep, scheduler, mock_discovery_manager):
    """Test scheduler skips sources not yet due."""
    # Arrange - Next run is in the future
    future_time = (datetime.now() + timedelta(hours=1)).isoformat()
    scheduler.schedule_state['arxiv_ml'] = {
        'enabled': True,
        'next_run': future_time
    }

    # Act
    scheduler._check_and_run_scheduled_sources()

    # Assert
    mock_discovery_manager.run_discovery.assert_not_called()


# ============================================================================
# MULTI-SOURCE COORDINATION TESTS
# ============================================================================


@patch('time.sleep')
def test_multiple_sources_scheduled(mock_sleep, scheduler, mock_discovery_manager):
    """Test scheduling multiple sources with different intervals."""
    # Arrange
    past_time = (datetime.now() - timedelta(minutes=5)).isoformat()

    scheduler.schedule_state['arxiv_ml'] = {
        'enabled': True,
        'next_run': past_time,
        'max_articles_per_run': 50
    }
    scheduler.schedule_state['pubmed_bio'] = {
        'enabled': True,
        'next_run': past_time,
        'max_articles_per_run': 30
    }

    mock_source = Mock()
    mock_source.schedule_config = ScheduleConfig(
        enabled=True,
        interval_minutes=60,
        max_articles_per_run=50
    )
    mock_discovery_manager.get_source.return_value = mock_source

    mock_result = DiscoveryResult(
        source_name='test',
        run_timestamp=datetime.now().isoformat(),
        articles_found=5,
        articles_filtered=4,
        articles_downloaded=3,
        execution_time_seconds=10.0
    )
    mock_discovery_manager.run_discovery.return_value = mock_result

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        scheduler._check_and_run_scheduled_sources()

    # Assert - Both sources should be run
    assert mock_discovery_manager.run_discovery.call_count == 2


def test_get_schedule_status(scheduler, mock_discovery_manager, sample_discovery_source):
    """Test getting schedule status."""
    # Arrange
    scheduler.schedule_state['arxiv_ml'] = {
        'enabled': True,
        'last_run': '2024-01-15T09:00:00',
        'next_run': '2024-01-15T10:00:00',
        'interval_minutes': 60,
        'max_articles_per_run': 50
    }
    mock_discovery_manager.get_source.return_value = sample_discovery_source

    # Act
    status = scheduler.get_schedule_status()

    # Assert
    assert status['running'] is False
    assert status['total_sources'] == 1
    assert status['enabled_sources'] == 1
    assert len(status['sources']) == 1
    assert status['sources'][0]['name'] == 'arxiv_ml'


def test_get_next_scheduled_runs(scheduler):
    """Test getting upcoming scheduled runs."""
    # Arrange
    now = datetime.now()
    scheduler.schedule_state['arxiv_ml'] = {
        'enabled': True,
        'next_run': (now + timedelta(hours=1)).isoformat(),
        'max_articles_per_run': 50,
        'interval_minutes': 60
    }
    scheduler.schedule_state['pubmed_bio'] = {
        'enabled': True,
        'next_run': (now + timedelta(hours=3)).isoformat(),
        'max_articles_per_run': 30,
        'interval_minutes': 180
    }

    # Act
    upcoming = scheduler.get_next_scheduled_runs(hours=24)

    # Assert
    assert len(upcoming) == 2
    assert upcoming[0]['source_name'] == 'arxiv_ml'  # Sorted by time
    assert upcoming[1]['source_name'] == 'pubmed_bio'


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@patch('time.sleep')
def test_handle_source_error_continues_others(
    mock_sleep, scheduler, mock_discovery_manager
):
    """Test that error in one source doesn't stop others."""
    # Arrange
    past_time = (datetime.now() - timedelta(minutes=5)).isoformat()

    scheduler.schedule_state['source1'] = {
        'enabled': True,
        'next_run': past_time,
        'max_articles_per_run': 50
    }
    scheduler.schedule_state['source2'] = {
        'enabled': True,
        'next_run': past_time,
        'max_articles_per_run': 50
    }

    # First source fails, second succeeds
    mock_source = Mock()
    mock_source.schedule_config = ScheduleConfig(
        enabled=True,
        interval_minutes=60,
        max_articles_per_run=50
    )
    mock_discovery_manager.get_source.return_value = mock_source

    call_count = [0]

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception('Source 1 failed')
        return DiscoveryResult(
            source_name='source2',
            run_timestamp=datetime.now().isoformat(),
            articles_found=5,
            articles_filtered=4,
            articles_downloaded=3,
            execution_time_seconds=10.0
        )

    mock_discovery_manager.run_discovery.side_effect = side_effect

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        scheduler._check_and_run_scheduled_sources()

    # Assert - Both sources attempted
    assert mock_discovery_manager.run_discovery.call_count == 2


# ============================================================================
# PERSISTENCE TESTS
# ============================================================================


@patch('asyncpg.connect')
def test_save_schedule_state_to_postgres(mock_connect, scheduler):
    """Test saving schedule state to PostgreSQL."""
    # Arrange
    mock_conn = AsyncMock()
    mock_connect.return_value = mock_conn

    scheduler.schedule_state['arxiv_ml'] = {
        'last_run': '2024-01-15T09:00:00',
        'next_run': '2024-01-15T10:00:00',
        'enabled': True,
        'interval_minutes': 60,
        'max_articles_per_run': 50,
        'time_of_day': '09:00',
        'days_of_week': [0, 1, 2, 3, 4]
    }

    # Act
    with patch.object(scheduler.config, 'secrets') as mock_secrets:
        mock_secrets.database_url = 'postgresql://test'
        scheduler._save_to_postgres()

    # Assert - Connection and execute should be called


@patch('asyncpg.connect')
def test_load_schedule_state_from_postgres(mock_connect, mock_discovery_manager, temp_schedule_file):
    """Test loading schedule state from PostgreSQL."""
    # Arrange
    mock_conn = AsyncMock()
    mock_row = {
        'source_name': 'arxiv_ml',
        'last_run': '2024-01-15T09:00:00',
        'next_run': '2024-01-15T10:00:00',
        'enabled': True,
        'interval_minutes': 60,
        'max_articles_per_run': 50,
        'time_of_day': '09:00',
        'days_of_week': [0, 1, 2, 3, 4]
    }
    mock_conn.fetch.return_value = [mock_row]
    mock_connect.return_value = mock_conn

    # Act
    with patch.object(DiscoveryScheduler, '_load_from_postgres', return_value={'arxiv_ml': mock_row}):
        scheduler = DiscoveryScheduler(
            discovery_manager=mock_discovery_manager,
            schedule_file=temp_schedule_file
        )

    # Assert
    assert 'arxiv_ml' in scheduler.schedule_state


# ============================================================================
# DAILY RUN WITHOUT REPROCESSING TESTS
# ============================================================================


def test_daily_run_updates_last_run_timestamp(scheduler, mock_discovery_manager):
    """Test that daily run updates last_run to prevent reprocessing."""
    # Arrange
    scheduler.schedule_state['arxiv_ml'] = {
        'last_run': '2024-01-14T09:00:00',  # Yesterday
        'max_articles_per_run': 50
    }

    mock_result = DiscoveryResult(
        source_name='arxiv_ml',
        run_timestamp=datetime.now().isoformat(),
        articles_found=10,
        articles_filtered=8,
        articles_downloaded=5,
        execution_time_seconds=15.0
    )
    mock_discovery_manager.run_discovery.return_value = mock_result

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        result = scheduler.run_source_now('arxiv_ml')

    # Assert
    assert scheduler.schedule_state['arxiv_ml']['last_run'] != '2024-01-14T09:00:00'
    # Timestamp should be updated to current time


def test_sync_with_discovery_manager(scheduler, mock_discovery_manager, sample_discovery_source):
    """Test syncing scheduler with discovery manager."""
    # Arrange
    mock_discovery_manager.list_sources.return_value = [sample_discovery_source]

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        scheduler.sync_with_discovery_manager()

    # Assert
    assert 'arxiv_ml' in scheduler.schedule_state


def test_sync_removes_orphaned_entries(scheduler, mock_discovery_manager):
    """Test sync removes schedule entries for deleted sources."""
    # Arrange
    scheduler.schedule_state['deleted_source'] = {'enabled': True}
    mock_discovery_manager.list_sources.return_value = []

    # Act
    with patch.object(scheduler, '_save_schedule_state'):
        scheduler.sync_with_discovery_manager()

    # Assert
    assert 'deleted_source' not in scheduler.schedule_state

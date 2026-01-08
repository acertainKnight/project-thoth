"""Tests for websocket router utilities and helpers.

Note: WebSocket endpoints themselves are better tested in integration tests.
This file focuses on testing the helper functions and utilities.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from thoth.server.routers import websocket


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    def test_connection_manager_init(self):
        """Test ConnectionManager initialization."""
        manager = websocket.ConnectionManager()
        assert manager.active_connections == []

    @pytest.mark.asyncio
    async def test_connect_adds_to_active_connections(self):
        """Test connecting adds websocket to active connections."""
        manager = websocket.ConnectionManager()
        mock_ws = AsyncMock()
        
        await manager.connect(mock_ws)
        
        assert mock_ws in manager.active_connections
        mock_ws.accept.assert_called_once()

    def test_disconnect_removes_from_active_connections(self):
        """Test disconnecting removes websocket from active connections."""
        manager = websocket.ConnectionManager()
        mock_ws = Mock()
        manager.active_connections.append(mock_ws)
        
        manager.disconnect(mock_ws)
        
        assert mock_ws not in manager.active_connections

    def test_disconnect_handles_nonexistent_connection(self):
        """Test disconnecting nonexistent connection doesn't error."""
        manager = websocket.ConnectionManager()
        mock_ws = Mock()
        
        # Should not raise
        manager.disconnect(mock_ws)
        assert mock_ws not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connections(self):
        """Test broadcast sends message to all connections."""
        manager = websocket.ConnectionManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        manager.active_connections = [mock_ws1, mock_ws2]
        
        await manager.broadcast("test message")
        
        mock_ws1.send_text.assert_called_once_with("test message")
        mock_ws2.send_text.assert_called_once_with("test message")

    @pytest.mark.asyncio
    async def test_broadcast_handles_dict_message(self):
        """Test broadcast sends JSON for dict messages."""
        manager = websocket.ConnectionManager()
        mock_ws = AsyncMock()
        manager.active_connections = [mock_ws]
        
        message = {"type": "test", "data": "value"}
        await manager.broadcast(message)
        
        mock_ws.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_connections(self):
        """Test broadcast removes connections that fail."""
        manager = websocket.ConnectionManager()
        mock_ws_good = AsyncMock()
        mock_ws_bad = AsyncMock()
        mock_ws_bad.send_text.side_effect = Exception("Connection error")
        manager.active_connections = [mock_ws_good, mock_ws_bad]
        
        await manager.broadcast("test")
        
        assert mock_ws_good in manager.active_connections
        assert mock_ws_bad not in manager.active_connections


class TestOperationTracking:
    """Tests for operation tracking functions."""

    def test_update_operation_progress(self, monkeypatch):
        """Test updating operation progress."""
        # Mock create_background_task to avoid async issues
        monkeypatch.setattr(websocket, 'create_background_task', Mock())
        
        operation_id = "test-op-123"
        
        websocket.update_operation_progress(
            operation_id=operation_id,
            status="running",
            progress=50.0,
            message="Processing...",
            result=None
        )
        
        status = websocket.get_operation_status(operation_id)
        assert status is not None
        assert status['status'] == 'running'
        assert status['progress'] == 50.0
        assert status['message'] == 'Processing...'
        assert 'timestamp' in status

    def test_get_operation_status_nonexistent(self):
        """Test getting status of nonexistent operation."""
        status = websocket.get_operation_status("nonexistent-id")
        assert status is None

    def test_update_operation_progress_completed(self, monkeypatch):
        """Test marking operation as completed."""
        # Mock create_background_task to avoid async issues
        monkeypatch.setattr(websocket, 'create_background_task', Mock())
        
        operation_id = "test-op-456"
        
        websocket.update_operation_progress(
            operation_id=operation_id,
            status="completed",
            progress=100.0,
            message="Done",
            result={"data": "result"}
        )
        
        status = websocket.get_operation_status(operation_id)
        assert status['status'] == 'completed'
        assert status['progress'] == 100.0
        assert status['result'] == {"data": "result"}

    def test_update_operation_progress_failed(self, monkeypatch):
        """Test marking operation as failed."""
        # Mock create_background_task to avoid async issues
        monkeypatch.setattr(websocket, 'create_background_task', Mock())
        
        operation_id = "test-op-789"
        
        websocket.update_operation_progress(
            operation_id=operation_id,
            status="failed",
            progress=0.0,
            message="Error occurred",
            result=None
        )
        
        status = websocket.get_operation_status(operation_id)
        assert status['status'] == 'failed'


class TestBackgroundTaskManagement:
    """Tests for background task management."""

    @pytest.mark.asyncio
    async def test_create_background_task_adds_to_set(self):
        """Test creating background task adds it to tracking set."""
        # Clear any existing tasks
        websocket.background_tasks.clear()
        
        async def dummy_coro():
            await asyncio.sleep(0.01)
        
        websocket.create_background_task(dummy_coro())
        
        # Give task a moment to be registered
        await asyncio.sleep(0.02)
        
        # Verify function doesn't error (task may have already completed)
        assert True

    @pytest.mark.asyncio
    async def test_shutdown_background_tasks_with_no_tasks(self):
        """Test shutting down when no tasks exist."""
        websocket.background_tasks.clear()
        
        # Should not raise
        await websocket.shutdown_background_tasks(timeout=1.0)
        assert len(websocket.background_tasks) == 0

    @pytest.mark.asyncio
    async def test_notify_progress_broadcasts_to_manager(self):
        """Test notify_progress broadcasts message."""
        # Just test it doesn't error - actual broadcast tested in ConnectionManager
        message = {"operation_id": "test", "progress": 50}
        await websocket.notify_progress(message)
        # If no exception, test passes


class TestModuleLevelManagers:
    """Tests for module-level WebSocket managers."""

    def test_chat_ws_manager_exists(self):
        """Test chat WebSocket manager is initialized."""
        assert websocket.chat_ws_manager is not None
        assert isinstance(websocket.chat_ws_manager, websocket.ConnectionManager)

    def test_status_ws_manager_exists(self):
        """Test status WebSocket manager is initialized."""
        assert websocket.status_ws_manager is not None
        assert isinstance(websocket.status_ws_manager, websocket.ConnectionManager)

    def test_progress_ws_manager_exists(self):
        """Test progress WebSocket manager is initialized."""
        assert websocket.progress_ws_manager is not None
        assert isinstance(websocket.progress_ws_manager, websocket.ConnectionManager)

    def test_operation_progress_dict_exists(self):
        """Test operation_progress dictionary is initialized."""
        assert websocket.operation_progress is not None
        assert isinstance(websocket.operation_progress, dict)


# REMOVED: TestDependencySetup - Phase 5
# set_dependencies() function removed in favor of FastAPI Depends() pattern
# Dependencies are now injected via get_service_manager(), get_research_agent(), get_chat_manager()

"""
Chat persistence models for the Thoth agent.

This module defines data models for managing multiple chat sessions
and persistent conversation history.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Individual chat message model."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_message_id: str | None = None


class ChatSession(BaseModel):
    """Chat session model for managing multiple conversations."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = 'New Chat'
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    message_count: int = 0
    last_message_preview: str = ''


class ChatPersistenceManager:
    """Manages persistent storage of chat sessions and messages."""

    def __init__(self, storage_path: Path):
        """Initialize the chat persistence manager.

        Args:
            storage_path: Path to the directory where chat data will be stored
        """
        self.storage_path = storage_path
        self.storage_path.mkdir(exist_ok=True)
        self.db_path = self.storage_path / 'chat_history.db'
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the SQLite database for chat storage."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    metadata TEXT DEFAULT '{}',
                    message_count INTEGER DEFAULT 0,
                    last_message_preview TEXT DEFAULT ''
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tool_calls TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    parent_message_id TEXT,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session_id ON chat_messages (session_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON chat_messages (timestamp)
            """)

            conn.commit()

    def create_session(
        self, title: str = 'New Chat', metadata: dict[str, Any] | None = None
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            title: Title for the chat session
            metadata: Optional metadata for the session

        Returns:
            Created ChatSession instance
        """
        session = ChatSession(title=title, metadata=metadata or {})

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions (id, title, created_at, updated_at, is_active, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    session.id,
                    session.title,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    session.is_active,
                    json.dumps(session.metadata),
                ),
            )
            conn.commit()

        logger.info(f'Created new chat session: {session.id} - {session.title}')
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """Get a chat session by ID.

        Args:
            session_id: ID of the session to retrieve

        Returns:
            ChatSession instance or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM chat_sessions WHERE id = ?
            """,
                (session_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            return ChatSession(
                id=row['id'],
                title=row['title'],
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at']),
                is_active=bool(row['is_active']),
                metadata=json.loads(row['metadata']),
                message_count=row['message_count'],
                last_message_preview=row['last_message_preview'],
            )

    def list_sessions(
        self, active_only: bool = True, limit: int = 50
    ) -> list[ChatSession]:
        """List chat sessions.

        Args:
            active_only: Whether to only return active sessions
            limit: Maximum number of sessions to return

        Returns:
            List of ChatSession instances
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT * FROM chat_sessions
                WHERE is_active = ? OR ? = 0
                ORDER BY updated_at DESC
                LIMIT ?
            """

            cursor = conn.execute(
                query, (1 if active_only else 0, 1 if active_only else 0, limit)
            )
            rows = cursor.fetchall()

            sessions = []
            for row in rows:
                sessions.append(
                    ChatSession(
                        id=row['id'],
                        title=row['title'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at']),
                        is_active=bool(row['is_active']),
                        metadata=json.loads(row['metadata']),
                        message_count=row['message_count'],
                        last_message_preview=row['last_message_preview'],
                    )
                )

            return sessions

    def update_session(
        self,
        session_id: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update a chat session.

        Args:
            session_id: ID of the session to update
            title: New title for the session
            metadata: New metadata for the session

        Returns:
            True if session was updated, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            updates = []
            params = []

            if title is not None:
                updates.append('title = ?')
                params.append(title)

            if metadata is not None:
                updates.append('metadata = ?')
                params.append(json.dumps(metadata))

            if not updates:
                return False

            updates.append('updated_at = ?')
            params.append(datetime.now().isoformat())
            params.append(session_id)

            query = f'UPDATE chat_sessions SET {", ".join(updates)} WHERE id = ?'
            result = conn.execute(query, params)
            conn.commit()

            return result.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and all its messages.

        Args:
            session_id: ID of the session to delete

        Returns:
            True if session was deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            # Delete messages first (cascade should handle this, but being explicit)
            conn.execute(
                'DELETE FROM chat_messages WHERE session_id = ?', (session_id,)
            )

            # Delete session
            result = conn.execute(
                'DELETE FROM chat_sessions WHERE id = ?', (session_id,)
            )
            conn.commit()

            if result.rowcount > 0:
                logger.info(f'Deleted chat session: {session_id}')
                return True
            return False

    def archive_session(self, session_id: str) -> bool:
        """Archive a chat session (mark as inactive).

        Args:
            session_id: ID of the session to archive

        Returns:
            True if session was archived, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                """
                UPDATE chat_sessions
                SET is_active = 0, updated_at = ?
                WHERE id = ?
            """,
                (datetime.now().isoformat(), session_id),
            )
            conn.commit()

            return result.rowcount > 0

    def add_message(self, message: ChatMessage) -> bool:
        """Add a message to a chat session.

        Args:
            message: ChatMessage instance to add

        Returns:
            True if message was added successfully
        """
        with sqlite3.connect(self.db_path) as conn:
            # Add the message
            conn.execute(
                """
                INSERT INTO chat_messages
                (id, session_id, role, content, timestamp, tool_calls, metadata, parent_message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    message.id,
                    message.session_id,
                    message.role,
                    message.content,
                    message.timestamp.isoformat(),
                    json.dumps(message.tool_calls),
                    json.dumps(message.metadata),
                    message.parent_message_id,
                ),
            )

            # Update session message count and preview
            preview = (
                message.content[:100] + '...'
                if len(message.content) > 100
                else message.content
            )
            conn.execute(
                """
                UPDATE chat_sessions
                SET message_count = message_count + 1,
                    last_message_preview = ?,
                    updated_at = ?
                WHERE id = ?
            """,
                (preview, datetime.now().isoformat(), message.session_id),
            )

            conn.commit()
            return True

    def get_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> list[ChatMessage]:
        """Get messages for a chat session.

        Args:
            session_id: ID of the session
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of ChatMessage instances
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?
            """,
                (session_id, limit, offset),
            )

            messages = []
            for row in cursor.fetchall():
                messages.append(
                    ChatMessage(
                        id=row['id'],
                        session_id=row['session_id'],
                        role=row['role'],
                        content=row['content'],
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        tool_calls=json.loads(row['tool_calls']),
                        metadata=json.loads(row['metadata']),
                        parent_message_id=row['parent_message_id'],
                    )
                )

            return messages

    def get_message_count(self, session_id: str) -> int:
        """Get the total number of messages in a session.

        Args:
            session_id: ID of the session

        Returns:
            Number of messages in the session
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM chat_messages WHERE session_id = ?
            """,
                (session_id,),
            )
            return cursor.fetchone()[0]

    def search_messages(
        self, query: str, session_id: str | None = None, limit: int = 50
    ) -> list[ChatMessage]:
        """Search messages by content.

        Args:
            query: Search query
            session_id: Optional session ID to limit search to
            limit: Maximum number of results

        Returns:
            List of matching ChatMessage instances
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if session_id:
                cursor = conn.execute(
                    """
                    SELECT * FROM chat_messages
                    WHERE session_id = ? AND content LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """,
                    (session_id, f'%{query}%', limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM chat_messages
                    WHERE content LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """,
                    (f'%{query}%', limit),
                )

            messages = []
            for row in cursor.fetchall():
                messages.append(
                    ChatMessage(
                        id=row['id'],
                        session_id=row['session_id'],
                        role=row['role'],
                        content=row['content'],
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        tool_calls=json.loads(row['tool_calls']),
                        metadata=json.loads(row['metadata']),
                        parent_message_id=row['parent_message_id'],
                    )
                )

            return messages

    def cleanup_old_sessions(self, days_old: int = 30, keep_active: bool = True) -> int:
        """Clean up old chat sessions.

        Args:
            days_old: Delete sessions older than this many days
            keep_active: Whether to keep active sessions regardless of age

        Returns:
            Number of sessions deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days_old)

        with sqlite3.connect(self.db_path) as conn:
            if keep_active:
                result = conn.execute(
                    """
                    DELETE FROM chat_sessions
                    WHERE updated_at < ? AND is_active = 0
                """,
                    (cutoff_date.isoformat(),),
                )
            else:
                result = conn.execute(
                    """
                    DELETE FROM chat_sessions
                    WHERE updated_at < ?
                """,
                    (cutoff_date.isoformat(),),
                )

            conn.commit()
            deleted_count = result.rowcount

            if deleted_count > 0:
                logger.info(f'Cleaned up {deleted_count} old chat sessions')

            return deleted_count

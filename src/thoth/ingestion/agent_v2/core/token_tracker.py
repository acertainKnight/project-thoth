"""Token usage tracking utilities for the research assistant."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

from loguru import logger

from thoth.config import config


class TokenUsageTracker:
    """Persistent tracker for token usage by user."""

    def __init__(self, usage_file: Path | None = None) -> None:
        """Initialize the tracker and load existing usage data."""
        self.config = config
        self.usage_file = (
            usage_file or Path(self.config.output_dir) / 'token_usage.json'
        )

        self._usage: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'total_cost': 0.0,
            }
        )

        self._load_usage()

        if not self.usage_file.exists():
            self._save_usage()

    def _load_usage(self) -> None:
        """Load usage data from PostgreSQL."""
        try:
            self._load_from_postgres()
        except Exception as e:
            logger.error(f'Error loading token usage from PostgreSQL: {e}')

    def _load_from_postgres(self) -> None:
        """Load token usage from PostgreSQL."""
        import asyncpg
        import asyncio

        db_url = getattr(self.config.secrets, 'database_url', None) if hasattr(self.config, 'secrets') else None
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        async def load():
            conn = await asyncpg.connect(db_url)
            try:
                rows = await conn.fetch("SELECT * FROM token_usage")
                for row in rows:
                    record = self._usage[row['user_id']]
                    record['prompt_tokens'] = row['prompt_tokens']
                    record['completion_tokens'] = row['completion_tokens']
                    record['total_tokens'] = row['total_tokens']
                    record['total_cost'] = row['total_cost']
                logger.info(f'Loaded token usage for {len(rows)} users from PostgreSQL')
            finally:
                await conn.close()

        asyncio.get_event_loop().run_until_complete(load())

    def _save_usage(self) -> None:
        """Persist usage data to PostgreSQL."""
        try:
            self._save_to_postgres()
        except Exception as e:
            logger.error(f'Error saving token usage: {e}')

    def _save_to_postgres(self) -> None:
        """Save token usage to PostgreSQL."""
        import asyncpg
        import asyncio

        db_url = getattr(self.config.secrets, 'database_url', None) if hasattr(self.config, 'secrets') else None
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        async def save():
            conn = await asyncpg.connect(db_url)
            try:
                for user_id, stats in self._usage.items():
                    await conn.execute("""
                        INSERT INTO token_usage (user_id, prompt_tokens, completion_tokens, total_tokens, total_cost)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (user_id) DO UPDATE SET
                            prompt_tokens = EXCLUDED.prompt_tokens,
                            completion_tokens = EXCLUDED.completion_tokens,
                            total_tokens = EXCLUDED.total_tokens,
                            total_cost = EXCLUDED.total_cost,
                            updated_at = NOW()
                    """, user_id, stats['prompt_tokens'], stats['completion_tokens'],
                         stats['total_tokens'], stats['total_cost'])
                logger.debug(f'Saved token usage for {len(self._usage)} users to PostgreSQL')
            finally:
                await conn.close()

        asyncio.get_event_loop().run_until_complete(save())

    def add_usage(self, user_id: str, usage: dict[str, float]) -> None:
        """Add token usage for a user and persist it."""
        record = self._usage[user_id]
        record['prompt_tokens'] += usage.get('prompt_tokens', 0)
        record['completion_tokens'] += usage.get('completion_tokens', 0)
        record['total_tokens'] += usage.get('total_tokens', 0)
        if 'total_cost' in usage:
            record['total_cost'] += usage.get('total_cost', 0)
        self._save_usage()

    def get_usage(self, user_id: str) -> dict[str, int]:
        """Get accumulated usage for a user."""
        return dict(self._usage.get(user_id, {}))

    def reset_usage(self, user_id: str | None = None) -> None:
        """Reset usage for a user or all users."""
        if user_id is None:
            self._usage.clear()
        else:
            self._usage.pop(user_id, None)
        self._save_usage()

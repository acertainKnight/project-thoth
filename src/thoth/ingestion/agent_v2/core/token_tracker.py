"""Token usage tracking utilities for the research assistant."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

from loguru import logger

from thoth.utilities.config import get_config


class TokenUsageTracker:
    """Persistent tracker for token usage by user."""

    def __init__(self, usage_file: Path | None = None) -> None:
        """Initialize the tracker and load existing usage data."""
        self.config = get_config()
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
        """Load usage data from disk."""
        if self.usage_file.exists():
            try:
                with open(self.usage_file) as f:
                    data = json.load(f)
                for user, stats in data.items():
                    record = self._usage[user]
                    record['prompt_tokens'] = stats.get('prompt_tokens', 0)
                    record['completion_tokens'] = stats.get('completion_tokens', 0)
                    record['total_tokens'] = stats.get('total_tokens', 0)
                    record['total_cost'] = stats.get('total_cost', 0.0)
                logger.info(
                    f'Loaded token usage for {len(self._usage)} users from {self.usage_file}'
                )
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f'Error loading token usage file: {e}')

    def _save_usage(self) -> None:
        """Persist usage data to disk."""
        try:
            self.usage_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = self.usage_file.with_suffix('.json.tmp')
            data = {user: dict(stats) for user, stats in self._usage.items()}
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            if os.name == 'nt':
                if self.usage_file.exists():
                    self.usage_file.unlink()
                os.rename(temp_file, self.usage_file)
            else:
                os.rename(temp_file, self.usage_file)
        except Exception as e:
            logger.error(f'Error saving token usage: {e}')

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

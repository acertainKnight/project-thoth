"""API Keys screen for setup wizard.

Collects and validates API keys from LLM providers.
OpenAI is required for embeddings (Thoth RAG + Letta).
OpenRouter is required for all Thoth backend LLM tasks.
Mistral is required for OCR extraction of PDF documents.
Other providers are optional.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, ClassVar

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Checkbox, Input, Static

from ..config_manager import ConfigManager
from ..validators import APIKeyValidator
from .base import BaseScreen

# API key signup URLs for each provider
PROVIDER_KEY_URLS: dict[str, str] = {
    'openai': 'https://platform.openai.com/api-keys',
    'openrouter': 'https://openrouter.ai/keys',
    'anthropic': 'https://console.anthropic.com/settings/keys',
    'google': 'https://aistudio.google.com/apikey',
    'mistral': 'https://console.mistral.ai/api-keys',
    'cohere': 'https://dashboard.cohere.com/api-keys',
}


class APIKeysScreen(BaseScreen):
    """Screen for configuring LLM provider API keys."""

    # Optional providers metadata
    OPTIONAL_PROVIDERS: ClassVar[dict[str, str]] = {
        'anthropic': 'Anthropic',
        'google': 'Google Gemini',
        'cohere': 'Cohere (Reranking)',
    }

    def __init__(self, vault_path: Path | None = None) -> None:
        """Initialize API keys screen.

        Args:
            vault_path: Path to Obsidian vault for loading existing config.
        """
        super().__init__(
            title='Configure API Keys',
            subtitle='Enter your LLM provider API keys',
        )
        self.vault_path = vault_path
        self.existing_config: dict[str, Any] = {}
        self._prefetch_task: asyncio.Task[None] | None = None

        # Load existing config in __init__ so values are available in compose_content
        if vault_path:
            try:
                cm = ConfigManager(vault_path)
                existing = cm.load_existing()
                if existing:
                    self.existing_config = existing
                    logger.info('Loaded existing API key configuration')
            except Exception as e:
                logger.error(f'Error loading configuration: {e}')

    def compose_content(self) -> ComposeResult:
        """Compose API keys content.

        Returns:
            Content widgets
        """
        # Check if remote deployment -- keys are optional
        deployment_mode = 'local'
        if hasattr(self.app, 'wizard_data'):
            deployment_mode = self.app.wizard_data.get('deployment_mode', 'local')

        if deployment_mode == 'remote':
            yield Static(
                '[bold]API Keys[/bold] [dim](Optional for remote)[/dim]\n'
                '[dim]Your remote server already has keys configured.\n'
                'Only enter keys here if you want local overrides.\n'
                'Press Next to skip.[/dim]\n',
                classes='section-title',
            )
        else:
            yield Static(
                '[bold]Required API Keys[/bold]\n'
                '[dim]All three are needed for Thoth to function.[/dim]\n',
                classes='section-title',
            )

        # --- OpenAI (Required - embeddings) ---
        yield Static(
            '[bold cyan]1. OpenAI[/bold cyan] [yellow](Required)[/yellow]\n'
            '[dim]Powers embeddings for Thoth RAG + Letta memory.\n'
            f'Get key: {PROVIDER_KEY_URLS["openai"]}[/dim]',
        )
        yield Input(
            placeholder='sk-... (your OpenAI API key)',
            password=True,
            id='api-key-openai',
            value=self._get_existing_api_key('openai'),
        )

        # --- OpenRouter (Required - backend LLM) ---
        yield Static(
            '\n[bold cyan]2. OpenRouter[/bold cyan] [yellow](Required)[/yellow]\n'
            "[dim]Thoth's backend LLM for analysis, queries, and routing.\n"
            f'Get key (free tier available): {PROVIDER_KEY_URLS["openrouter"]}[/dim]',
        )
        yield Input(
            placeholder='sk-or-... (your OpenRouter API key)',
            password=True,
            id='api-key-openrouter',
            value=self._get_existing_api_key('openrouter'),
        )

        # --- Mistral (Required - OCR extraction) ---
        yield Static(
            '\n[bold cyan]3. Mistral AI[/bold cyan] [yellow](Required)[/yellow]\n'
            '[dim]Powers OCR extraction for PDF documents (uses mistral-ocr-latest).\n'
            f'Get key: {PROVIDER_KEY_URLS["mistral"]}[/dim]',
        )
        yield Input(
            placeholder='Mistral API key',
            password=True,
            id='api-key-mistral',
            value=self._get_existing_api_key('mistral'),
        )

        # --- Optional providers ---
        yield Static(
            '\n[bold]Additional Providers[/bold] [dim](Optional)[/dim]\n'
            '[dim]Add direct API access for more model choices. Enable with Space.[/dim]',
        )

        # Anthropic
        yield Checkbox(
            'Anthropic',
            id='enable-anthropic',
            value=self._is_provider_enabled('anthropic'),
        )
        with Vertical(id='config-anthropic', classes='provider-config'):
            yield Static(
                f'[dim]Get key: {PROVIDER_KEY_URLS["anthropic"]}[/dim]',
            )
            yield Input(
                placeholder='sk-ant-... (Anthropic API key)',
                password=True,
                id='api-key-anthropic',
                value=self._get_existing_api_key('anthropic'),
            )

        # Google
        yield Checkbox(
            'Google Gemini',
            id='enable-google',
            value=self._is_provider_enabled('google'),
        )
        with Vertical(id='config-google', classes='provider-config'):
            yield Static(
                f'[dim]Get key: {PROVIDER_KEY_URLS["google"]}[/dim]',
            )
            yield Input(
                placeholder='AIza... (Google API key)',
                password=True,
                id='api-key-google',
                value=self._get_existing_api_key('google'),
            )

        # Cohere (for production reranking)
        yield Checkbox(
            'Cohere (Advanced RAG)',
            id='enable-cohere',
            value=self._is_provider_enabled('cohere'),
        )
        with Vertical(id='config-cohere', classes='provider-config'):
            yield Static(
                '[dim]Production-grade reranking for RAG retrieval.\n'
                f'Get key: {PROVIDER_KEY_URLS["cohere"]}\n'
                'Optional - Thoth uses LLM reranking if not provided.[/dim]',
            )
            yield Input(
                placeholder='Cohere API key',
                password=True,
                id='api-key-cohere',
                value=self._get_existing_api_key('cohere'),
            )

    # Mapping from wizard provider IDs to settings.json apiKeys field names
    _KEY_FIELD_MAP: ClassVar[dict[str, str]] = {
        'openai': 'openaiKey',
        'openrouter': 'openrouterKey',
        'anthropic': 'anthropicKey',
        'google': 'googleApiKey',
        'mistral': 'mistralKey',
        'cohere': 'cohereKey',
    }

    def _is_provider_enabled(self, provider_id: str) -> bool:
        """Check if provider has a key stored in existing config.

        Args:
            provider_id: Provider identifier

        Returns:
            True if provider has a non-empty API key
        """
        return bool(self._get_existing_api_key(provider_id))

    def _get_existing_api_key(self, provider_id: str) -> str:
        """Get existing API key for provider from settings.json apiKeys section.

        Args:
            provider_id: Provider identifier

        Returns:
            API key or empty string
        """
        api_keys = self.existing_config.get('apiKeys', {})
        field_name = self._KEY_FIELD_MAP.get(provider_id, '')
        return str(api_keys.get(field_name) or '')

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """Validate API keys.

        OpenAI, OpenRouter, and Mistral are required for local deployment.
        For remote deployment, all keys are optional (server has them).

        Returns:
            Dict with api_keys data, or None if invalid
        """
        api_keys: dict[str, str] = {}

        # Check if remote -- keys are optional
        deployment_mode = 'local'
        if hasattr(self.app, 'wizard_data'):
            deployment_mode = self.app.wizard_data.get('deployment_mode', 'local')
        keys_required = deployment_mode == 'local'

        # --- Validate OpenAI ---
        openai_key_input = self.query_one('#api-key-openai', Input)
        openai_key = openai_key_input.value.strip()

        if not openai_key and keys_required:
            self.show_error('OpenAI API key is required (used for embeddings).')
            openai_key_input.focus()
            return None

        if openai_key:
            is_valid, error_msg = APIKeyValidator.validate('openai', openai_key)
            if not is_valid:
                self.show_error(f'OpenAI: {error_msg or "Invalid API key format"}')
                openai_key_input.focus()
                return None
            api_keys['openai'] = openai_key

        # --- Validate OpenRouter ---
        or_key_input = self.query_one('#api-key-openrouter', Input)
        or_key = or_key_input.value.strip()

        if not or_key and keys_required:
            self.show_error(
                'OpenRouter API key is required (Thoth backend LLM).\n'
                f'Get a free key at: {PROVIDER_KEY_URLS["openrouter"]}'
            )
            or_key_input.focus()
            return None

        if or_key:
            is_valid, error_msg = APIKeyValidator.validate('openrouter', or_key)
            if not is_valid:
                self.show_error(f'OpenRouter: {error_msg or "Invalid API key format"}')
                or_key_input.focus()
                return None
            api_keys['openrouter'] = or_key

        # --- Validate Mistral (required for OCR extraction) ---
        mistral_key_input = self.query_one('#api-key-mistral', Input)
        mistral_key = mistral_key_input.value.strip()

        if not mistral_key and keys_required:
            self.show_error(
                'Mistral API key is required (used for PDF OCR extraction).\n'
                f'Get a key at: {PROVIDER_KEY_URLS["mistral"]}'
            )
            mistral_key_input.focus()
            return None

        if mistral_key:
            is_valid, error_msg = APIKeyValidator.validate('mistral', mistral_key)
            if not is_valid:
                self.show_error(f'Mistral: {error_msg or "Invalid API key format"}')
                mistral_key_input.focus()
                return None
            api_keys['mistral'] = mistral_key

        # --- Validate optional providers ---
        for provider_id, provider_name in self.OPTIONAL_PROVIDERS.items():
            checkbox = self.query_one(f'#enable-{provider_id}', Checkbox)
            if not checkbox.value:
                continue

            key_input = self.query_one(f'#api-key-{provider_id}', Input)
            api_key = key_input.value.strip()

            if not api_key:
                self.show_error(f'Please enter an API key for {provider_name}')
                key_input.focus()
                return None

            is_valid, error_msg = APIKeyValidator.validate(provider_id, api_key)
            if not is_valid:
                self.show_error(
                    f'{provider_name}: {error_msg or "Invalid API key format"}'
                )
                key_input.focus()
                return None

            api_keys[provider_id] = api_key

        logger.info(f'API keys validated for {len(api_keys)} provider(s)')

        # Start background model prefetching for next screen
        self._prefetch_models(api_keys)

        return {'api_keys': api_keys}

    def _prefetch_models(self, api_keys: dict[str, str]) -> None:
        """Start background task to prefetch models for next screen.

        Args:
            api_keys: Dictionary of provider -> API key
        """
        from ..model_fetcher import (
            fetch_anthropic_models,
            fetch_letta_compatible_models,
            fetch_openai_chat_models,
            fetch_openai_embedding_models,
            fetch_openrouter_models,
        )

        async def prefetch() -> None:
            """Prefetch all model lists in parallel."""
            tasks = [
                fetch_openrouter_models(api_keys.get('openrouter')),
                fetch_openai_embedding_models(api_keys['openai']),
                fetch_openai_chat_models(api_keys['openai']),
                fetch_letta_compatible_models(api_keys),
            ]
            if 'anthropic' in api_keys:
                tasks.append(fetch_anthropic_models(api_keys['anthropic']))
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info('Model lists prefetched successfully')

        # Store reference so task is not garbage-collected (RUF006)
        self._prefetch_task = asyncio.create_task(prefetch())

    async def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes to show/hide provider configs.

        Args:
            event: Checkbox changed event
        """
        if event.checkbox.id and event.checkbox.id.startswith('enable-'):
            provider_id = event.checkbox.id.replace('enable-', '')
            try:
                config_container = self.query_one(f'#config-{provider_id}')
                config_container.display = event.value
            except Exception as e:
                logger.debug('Checkbox config container not ready: %s', e)

    async def on_next_screen(self) -> None:
        """Navigate to model selection screen."""
        from .model_selection import ModelSelectionScreen

        logger.info('Proceeding to model selection')
        await self.app.push_screen(ModelSelectionScreen())

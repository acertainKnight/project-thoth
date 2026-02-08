"""Configuration screen for setup wizard.

Allows users to configure LLM providers and API keys.
OpenAI is required (embeddings for Thoth + Letta).
OpenRouter is required (Thoth's default backend LLM).
Other providers are optional.

Model lists are fetched dynamically from provider APIs where possible.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, ClassVar

import httpx
from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Checkbox, Input, Label, Select, Static

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
}

# Fallback model lists (used if API calls fail)
FALLBACK_OPENAI_MODELS: list[str] = [
    'gpt-4o',
    'gpt-4o-mini',
    'gpt-4-turbo',
    'gpt-3.5-turbo',
]

FALLBACK_OPENROUTER_MODELS: list[str] = [
    'google/gemini-2.0-flash-exp:free',
    'anthropic/claude-3.5-sonnet',
    'openai/gpt-4o',
    'openai/gpt-4o-mini',
    'meta-llama/llama-3.1-70b-instruct',
    'mistralai/mistral-large-latest',
]

FALLBACK_ANTHROPIC_MODELS: list[str] = [
    'claude-sonnet-4-20250514',
    'claude-3-5-sonnet-20241022',
    'claude-3-5-haiku-20241022',
    'claude-3-opus-20240229',
]

FALLBACK_GOOGLE_MODELS: list[str] = [
    'gemini-2.0-flash-exp',
    'gemini-1.5-pro',
    'gemini-1.5-flash',
]

FALLBACK_MISTRAL_MODELS: list[str] = [
    'mistral-large-latest',
    'mistral-small-latest',
    'mistral-tiny',
]


async def _fetch_openai_models() -> list[str]:
    """Fetch available chat models from OpenAI API.

    Returns:
        Sorted list of model IDs, or fallback list on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get('https://api.openai.com/v1/models')
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                # Filter to chat models (gpt-*), skip instruct/embedding/etc
                chat_models = sorted(
                    m['id']
                    for m in data
                    if m['id'].startswith('gpt-')
                    and 'instruct' not in m['id']
                    and 'realtime' not in m['id']
                    and 'audio' not in m['id']
                )
                if chat_models:
                    return chat_models
    except Exception as e:
        logger.debug(f'Could not fetch OpenAI models: {e}')
    return FALLBACK_OPENAI_MODELS


async def _fetch_openrouter_models_structured() -> list[str]:
    """Fetch models from OpenRouter that support structured output.

    Filters by checking that "structured_outputs" is in the model's
    supported_parameters list, per the OpenRouter API docs:
    https://openrouter.ai/docs/features/structured-outputs

    Returns:
        Sorted list of model IDs, or fallback list on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get('https://openrouter.ai/api/v1/models')
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                structured = []
                for m in data:
                    supported = m.get('supported_parameters', [])
                    # Must support structured_outputs per OpenRouter API
                    if 'structured_outputs' not in supported:
                        continue
                    model_id = m.get('id', '')
                    # Skip deprecated, preview, and very obscure models
                    if ':beta' in model_id or model_id == 'auto':
                        continue
                    structured.append(model_id)

                if structured:
                    # Sort: free models first, then by name
                    def sort_key(mid: str) -> tuple[int, str]:
                        return (0 if ':free' in mid else 1, mid)

                    return sorted(structured, key=sort_key)
    except Exception as e:
        logger.debug(f'Could not fetch OpenRouter models: {e}')
    return FALLBACK_OPENROUTER_MODELS


async def _fetch_anthropic_models() -> list[str]:
    """Fetch available models from Anthropic API.

    Returns:
        List of model IDs, or fallback list on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                'https://api.anthropic.com/v1/models',
                headers={
                    'x-api-key': 'none',
                    'anthropic-version': '2023-06-01',
                },
            )
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                models = sorted(m['id'] for m in data if m.get('id'))
                if models:
                    return models
    except Exception as e:
        logger.debug(f'Could not fetch Anthropic models: {e}')
    return FALLBACK_ANTHROPIC_MODELS


class ConfigurationScreen(BaseScreen):
    """Screen for configuring LLM providers and settings."""

    # Optional providers metadata
    OPTIONAL_PROVIDERS: ClassVar[dict[str, dict[str, Any]]] = {
        'anthropic': {
            'name': 'Anthropic',
            'default_model': 'claude-sonnet-4-20250514',
        },
        'google': {
            'name': 'Google Gemini',
            'default_model': 'gemini-2.0-flash-exp',
        },
    }

    def __init__(self, vault_path: Path | None = None) -> None:
        """Initialize configuration screen.

        Args:
            vault_path: Path to Obsidian vault for loading existing config
        """
        super().__init__(
            title='Configure API Keys',
            subtitle='Set up LLM providers for Thoth and Letta',
        )
        self.vault_path = vault_path
        self.config_manager = (
            ConfigManager(vault_path) if vault_path else ConfigManager()
        )
        self.existing_config: dict[str, Any] = {}
        # Model lists (populated on mount)
        self.openai_models: list[str] = FALLBACK_OPENAI_MODELS
        self.openrouter_models: list[str] = FALLBACK_OPENROUTER_MODELS
        self.anthropic_models: list[str] = FALLBACK_ANTHROPIC_MODELS
        self.google_models: list[str] = FALLBACK_GOOGLE_MODELS
        self.mistral_models: list[str] = FALLBACK_MISTRAL_MODELS

    def on_mount(self) -> None:
        """Run when screen is mounted."""
        self._load_task = asyncio.create_task(self._init_screen())

    async def _init_screen(self) -> None:
        """Load config and fetch model lists concurrently."""
        # Load existing config
        try:
            existing = self.config_manager.load_existing()
            if existing:
                self.existing_config = existing
                logger.info('Loaded existing configuration')
        except Exception as e:
            logger.error(f'Error loading configuration: {e}')

        # Fetch models from APIs in parallel
        self.show_info('Fetching available models from providers...')
        openai_task = asyncio.create_task(_fetch_openai_models())
        openrouter_task = asyncio.create_task(_fetch_openrouter_models_structured())
        anthropic_task = asyncio.create_task(_fetch_anthropic_models())

        self.openai_models = await openai_task
        self.openrouter_models = await openrouter_task
        self.anthropic_models = await anthropic_task

        # Update the Select widgets with fetched models
        self._update_select('model-openai', self.openai_models, 'gpt-4o-mini')
        self._update_select(
            'model-openrouter',
            self.openrouter_models,
            'google/gemini-2.0-flash-exp:free',
        )
        self._update_select(
            'model-anthropic',
            self.anthropic_models,
            'claude-sonnet-4-20250514',
        )

        fetched_count = (
            len(self.openai_models)
            + len(self.openrouter_models)
            + len(self.anthropic_models)
        )
        self.show_info(f'Loaded {fetched_count} models from providers.')
        await asyncio.sleep(1.5)
        self.clear_messages()

    def _update_select(self, select_id: str, models: list[str], default: str) -> None:
        """Update a Select widget's options with a new model list.

        Args:
            select_id: The widget ID of the Select
            models: New list of model IDs
            default: Default model to select
        """
        try:
            select_widget = self.query_one(f'#{select_id}', Select)
            options = [(m, m) for m in models]
            select_widget.set_options(options)
            # Try to set the existing or default value
            existing = self._get_existing_model(
                select_id.replace('model-', ''), default
            )
            if existing in models:
                select_widget.value = existing
            elif default in models:
                select_widget.value = default
            elif models:
                select_widget.value = models[0]
        except Exception as e:
            logger.debug('Select widget not mounted yet: %s', e)

    def compose_content(self) -> ComposeResult:
        """Compose configuration content.

        Returns:
            Content widgets
        """
        yield Static(
            '[bold]Required API Keys[/bold]\n'
            '[dim]Both are needed for Thoth to function.[/dim]\n',
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
        yield Static('[dim]Letta agent model:[/dim]')
        yield Select(
            options=[(m, m) for m in self.openai_models],
            id='model-openai',
            value=self._get_existing_model('openai', 'gpt-4o-mini'),
        )

        # --- OpenRouter (Required - backend LLM) ---
        yield Static(
            '\n[bold cyan]2. OpenRouter[/bold cyan] [yellow](Required)[/yellow]\n'
            "[dim]Thoth's backend LLM for analysis, queries, and routing.\n"
            'Only models with structured output support are shown.\n'
            f'Get key (free tier available): {PROVIDER_KEY_URLS["openrouter"]}[/dim]',
        )
        yield Input(
            placeholder='sk-or-... (your OpenRouter API key)',
            password=True,
            id='api-key-openrouter',
            value=self._get_existing_api_key('openrouter'),
        )
        yield Static('[dim]Default model:[/dim]')
        yield Select(
            options=[(m, m) for m in self.openrouter_models],
            id='model-openrouter',
            value=self._get_existing_model(
                'openrouter', 'google/gemini-2.0-flash-exp:free'
            ),
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
            '[dim]Add direct API access. Enable with Space.[/dim]',
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
            yield Select(
                options=[(m, m) for m in self.anthropic_models],
                id='model-anthropic',
                value=self._get_existing_model('anthropic', 'claude-sonnet-4-20250514'),
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
            yield Select(
                options=[(m, m) for m in self.google_models],
                id='model-google',
                value=self._get_existing_model('google', 'gemini-2.0-flash-exp'),
            )

        # Mistral
        yield Checkbox(
            'Mistral AI',
            id='enable-mistral',
            value=self._is_provider_enabled('mistral'),
        )
        with Vertical(id='config-mistral', classes='provider-config'):
            yield Static(
                f'[dim]Get key: {PROVIDER_KEY_URLS["mistral"]}[/dim]',
            )
            yield Input(
                placeholder='Mistral API key',
                password=True,
                id='api-key-mistral',
                value=self._get_existing_api_key('mistral'),
            )
            yield Select(
                options=[(m, m) for m in self.mistral_models],
                id='model-mistral',
                value=self._get_existing_model('mistral', 'mistral-small-latest'),
            )

        # --- Advanced ---
        yield Static(
            '\n[bold]Advanced[/bold] [dim](defaults are fine)[/dim]',
        )
        yield Label('Temperature (0.0 - 2.0):')
        yield Input(
            placeholder='0.7',
            id='temperature',
            value=str(
                self.existing_config.get('llm_settings', {}).get('temperature', 0.7)
            ),
        )
        yield Label('Max Tokens:')
        yield Input(
            placeholder='4096',
            id='max-tokens',
            value=str(
                self.existing_config.get('llm_settings', {}).get('max_tokens', 4096)
            ),
        )

    def _is_provider_enabled(self, provider_id: str) -> bool:
        """Check if provider is enabled in existing config.

        Args:
            provider_id: Provider identifier

        Returns:
            True if provider is enabled
        """
        llm_settings = self.existing_config.get('llm_settings', {})
        providers = llm_settings.get('providers', {})
        provider_config = providers.get(provider_id, {})
        return bool(provider_config.get('enabled', False))

    def _get_existing_api_key(self, provider_id: str) -> str:
        """Get existing API key for provider.

        Args:
            provider_id: Provider identifier

        Returns:
            API key or empty string
        """
        llm_settings = self.existing_config.get('llm_settings', {})
        providers = llm_settings.get('providers', {})
        provider_config = providers.get(provider_id, {})
        return str(provider_config.get('api_key') or '')

    def _get_existing_model(self, provider_id: str, default: str) -> str:
        """Get existing model for provider.

        Args:
            provider_id: Provider identifier
            default: Default model name

        Returns:
            Model name or default model
        """
        llm_settings = self.existing_config.get('llm_settings', {})
        providers = llm_settings.get('providers', {})
        provider_config = providers.get(provider_id, {})
        return str(provider_config.get('model') or default)

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """Validate configuration settings.

        OpenAI and OpenRouter are both required.

        Returns:
            Dict with configuration data, or None if invalid
        """
        llm_settings: dict[str, Any] = {'providers': {}}

        # --- Validate OpenAI (required for embeddings) ---
        openai_key_input = self.query_one('#api-key-openai', Input)
        openai_key = openai_key_input.value.strip()

        if not openai_key:
            self.show_error('OpenAI API key is required (used for embeddings).')
            openai_key_input.focus()
            return None

        is_valid, error_msg = APIKeyValidator.validate('openai', openai_key)
        if not is_valid:
            self.show_error(f'OpenAI: {error_msg or "Invalid API key format"}')
            openai_key_input.focus()
            return None

        openai_model = self.query_one('#model-openai', Select).value
        llm_settings['providers']['openai'] = {
            'enabled': True,
            'api_key': openai_key,
            'model': openai_model,
        }

        # --- Validate OpenRouter (required for backend LLM) ---
        or_key_input = self.query_one('#api-key-openrouter', Input)
        or_key = or_key_input.value.strip()

        if not or_key:
            self.show_error(
                'OpenRouter API key is required (Thoth backend LLM).\n'
                f'Get a free key at: {PROVIDER_KEY_URLS["openrouter"]}'
            )
            or_key_input.focus()
            return None

        is_valid, error_msg = APIKeyValidator.validate('openrouter', or_key)
        if not is_valid:
            self.show_error(f'OpenRouter: {error_msg or "Invalid API key format"}')
            or_key_input.focus()
            return None

        or_model = self.query_one('#model-openrouter', Select).value
        llm_settings['providers']['openrouter'] = {
            'enabled': True,
            'api_key': or_key,
            'model': or_model,
        }

        # --- Validate optional providers ---
        for provider_id, info in self.OPTIONAL_PROVIDERS.items():
            checkbox = self.query_one(f'#enable-{provider_id}', Checkbox)
            if not checkbox.value:
                continue

            key_input = self.query_one(f'#api-key-{provider_id}', Input)
            api_key = key_input.value.strip()

            if not api_key:
                self.show_error(f'Please enter an API key for {info["name"]}')
                key_input.focus()
                return None

            is_valid, error_msg = APIKeyValidator.validate(provider_id, api_key)
            if not is_valid:
                self.show_error(
                    f'{info["name"]}: {error_msg or "Invalid API key format"}'
                )
                key_input.focus()
                return None

            model = self.query_one(f'#model-{provider_id}', Select).value
            llm_settings['providers'][provider_id] = {
                'enabled': True,
                'api_key': api_key,
                'model': model,
            }

        # --- Advanced settings ---
        try:
            temp_val = self.query_one('#temperature', Input).value or '0.7'
            temperature = float(temp_val)
            if not 0.0 <= temperature <= 2.0:
                self.show_error('Temperature must be between 0.0 and 2.0')
                return None
            llm_settings['temperature'] = temperature
        except ValueError:
            self.show_error('Invalid temperature value')
            return None

        try:
            tokens_val = self.query_one('#max-tokens', Input).value or '4096'
            max_tokens = int(tokens_val)
            if max_tokens < 1:
                self.show_error('Max tokens must be at least 1')
                return None
            llm_settings['max_tokens'] = max_tokens
        except ValueError:
            self.show_error('Invalid max tokens value')
            return None

        enabled = len(llm_settings['providers'])
        logger.info(f'Configuration validated with {enabled} provider(s)')
        return {'llm_settings': llm_settings}

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
        """Navigate to review screen.

        Skips dependency check and optional features (all enabled by default).
        """
        from .review import ReviewScreen

        if hasattr(self.app, 'wizard_data'):
            self.app.wizard_data.update(
                {
                    'rag_enabled': True,
                    'discovery_enabled': True,
                    'citations_enabled': True,
                    'local_embeddings': False,
                }
            )

        logger.info('Proceeding to review')
        await self.app.push_screen(ReviewScreen())

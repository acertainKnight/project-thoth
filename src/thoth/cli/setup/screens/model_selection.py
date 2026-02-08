"""Model Selection screen for setup wizard.

Configures all model choices with live dropdowns from provider APIs.
Includes visible essentials and an advanced collapsible section.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.widgets import Collapsible, Input, Label, Select, Static

from ..config_manager import ConfigManager
from ..model_fetcher import (
    ModelInfo,
    fetch_letta_compatible_models,
    fetch_openai_embedding_models,
    fetch_openrouter_models,
)
from .base import BaseScreen


class ModelSelectionScreen(BaseScreen):
    """Screen for configuring model selections and RAG/chunking settings."""

    def __init__(self) -> None:
        """Initialize model selection screen."""
        super().__init__(
            title='Configure Models',
            subtitle='Select models for each Thoth component',
        )
        self.vault_path: Path | None = None
        self.config_manager: ConfigManager | None = None
        self.existing_config: dict[str, Any] = {}
        self.api_keys: dict[str, str] = {}

        # Model lists (populated on mount)
        self.openrouter_models: list[ModelInfo] = []
        self.openai_embedding_models: list[str] = []
        self.letta_models: list[str] = []

        # Model context length cache for warnings
        self.model_context_lengths: dict[str, int] = {}

    def on_mount(self) -> None:
        """Run when screen is mounted."""
        # Get vault path, API keys, and Letta live models from wizard data
        self.vault_path = getattr(self.app, 'wizard_data', {}).get('vault_path')
        self.api_keys = getattr(self.app, 'wizard_data', {}).get('api_keys', {})
        self.letta_live_models: list[str] = getattr(self.app, 'wizard_data', {}).get(
            'letta_live_models', []
        )

        if self.vault_path:
            self.config_manager = ConfigManager(self.vault_path)

        # Start loading models and config
        self._load_task = asyncio.create_task(self._init_screen())

    async def _init_screen(self) -> None:
        """Load config and fetch model lists concurrently."""
        # Load existing config for defaults
        try:
            if self.config_manager:
                existing = self.config_manager.load_existing()
                if existing:
                    self.existing_config = existing
                    logger.info('Loaded existing configuration for defaults')
        except Exception as e:
            logger.error(f'Error loading configuration: {e}')

        # Fetch models from APIs in parallel
        self.show_info('Fetching available models from providers...')

        openrouter_task = asyncio.create_task(
            fetch_openrouter_models(self.api_keys.get('openrouter'))
        )
        embedding_task = asyncio.create_task(
            fetch_openai_embedding_models(self.api_keys['openai'])
        )
        letta_task = asyncio.create_task(
            fetch_letta_compatible_models(self.api_keys, self.letta_live_models)
        )

        self.openrouter_models = await openrouter_task
        self.openai_embedding_models = await embedding_task
        self.letta_models = await letta_task

        # Build context length cache
        for model in self.openrouter_models:
            if model.context_length > 0:
                self.model_context_lengths[model.id] = model.context_length

        # Update the Select widgets with fetched models
        self._update_visible_selects()
        self._update_advanced_selects()

        fetched_count = (
            len(self.openrouter_models)
            + len(self.openai_embedding_models)
            + len(self.letta_models)
        )
        self.show_info(f'Loaded {fetched_count} models from providers.')
        await asyncio.sleep(1.5)
        self.clear_messages()

    def _update_visible_selects(self) -> None:
        """Update Select widgets in visible section with fetched models."""
        # Document Analysis Model
        self._update_select(
            'model-doc-analysis',
            [m.id for m in self.openrouter_models],
            self._get_default('llm.default.model', 'google/gemini-2.5-flash'),
        )

        # Letta Chat Model
        self._update_select(
            'model-letta',
            self.letta_models,
            self._get_default(
                'memory.letta.agentModel', 'anthropic/claude-sonnet-4-20250514'
            ),
        )

        # Embedding Model
        self._update_select(
            'model-embedding',
            self.openai_embedding_models,
            self._get_default('rag.embeddingModel', 'text-embedding-3-small'),
        )

    def _update_advanced_selects(self) -> None:
        """Update Select widgets in advanced section with fetched models."""
        or_model_ids = [m.id for m in self.openrouter_models]

        self._update_select(
            'model-citation',
            or_model_ids,
            self._get_default('llm.citation.model', 'openai/gpt-4o-mini'),
        )
        self._update_select(
            'model-tag-consolidate',
            or_model_ids,
            self._get_default(
                'llm.tagConsolidator.consolidateModel', 'google/gemini-2.5-flash'
            ),
        )
        self._update_select(
            'model-tag-suggest',
            or_model_ids,
            self._get_default(
                'llm.tagConsolidator.suggestModel', 'google/gemini-2.5-flash'
            ),
        )
        self._update_select(
            'model-tag-map',
            or_model_ids,
            self._get_default(
                'llm.tagConsolidator.mapModel', 'google/gemini-2.5-flash'
            ),
        )
        self._update_select(
            'model-research',
            or_model_ids,
            self._get_default('llm.researchAgent.model', 'google/gemini-3-pro-preview'),
        )
        self._update_select(
            'model-scrape',
            or_model_ids,
            self._get_default('llm.scrapeFilter.model', 'google/gemini-2.5-flash'),
        )
        self._update_select(
            'model-rag-qa',
            or_model_ids,
            self._get_default('rag.qa.model', 'google/gemini-2.5-flash'),
        )
        self._update_select(
            'model-routing',
            or_model_ids,
            self._get_default(
                'llm.queryBasedRouting.routingModel', 'google/gemini-2.5-flash'
            ),
        )

    def _update_select(self, select_id: str, models: list[str], default: str) -> None:
        """
        Update a Select widget's options with a new model list.

        Args:
            select_id: The widget ID of the Select
            models: New list of model IDs
            default: Default model to select
        """
        try:
            select_widget = self.query_one(f'#{select_id}', Select)
            # Add "Recommended" prefix to the default option
            options = []
            for m in models:
                label = f'Recommended: {m}' if m == default else m
                options.append((label, m))

            select_widget.set_options(options)

            # Set default value
            if default in models:
                select_widget.value = default
            elif models:
                select_widget.value = models[0]
        except Exception as e:
            logger.debug(f'Could not update select {select_id}: {e}')

    def _get_default(self, config_path: str, fallback: str) -> str:
        """
        Get default value from existing config using dot notation.

        Args:
            config_path: Dot-separated path (e.g., "llm.default.model")
            fallback: Fallback value if not found

        Returns:
            Value from config or fallback
        """
        if not self.existing_config:
            return fallback

        parts = config_path.split('.')
        current: Any = self.existing_config
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return fallback
            else:
                return fallback
        return str(current) if current else fallback

    def compose_content(self) -> ComposeResult:
        """Compose model selection content.

        Returns:
            Content widgets
        """
        # Visible section - primary models
        yield Static(
            '[bold]Essential Models[/bold]\n'
            "[dim]These are the main models you'll interact with.[/dim]\n",
            classes='section-title',
        )

        yield Label('[cyan]Document Analysis Model[/cyan]')
        yield Static(
            '[dim]Processes and analyzes documents (PDF, markdown, etc.)\n'
            'Uses OpenRouter models with structured output support.[/dim]'
        )
        yield Select(
            options=[('Loading...', '')],
            id='model-doc-analysis',
        )
        yield Static(id='warning-doc-analysis', classes='context-warning hidden')

        yield Label('\n[cyan]Letta Chat Model[/cyan]')
        yield Static(
            '[dim]Powers your conversational research agent via Letta.\n'
            "Models are from your running Letta server, or Letta's tested model list.[/dim]"
        )
        yield Select(
            options=[('Loading...', '')],
            id='model-letta',
        )
        yield Static(id='warning-letta', classes='context-warning hidden')

        yield Label('\n[cyan]Embedding Model[/cyan]')
        yield Static(
            '[dim]Creates vector embeddings for semantic search (Thoth + Letta).\n'
            'Uses OpenAI embedding models.[/dim]'
        )
        yield Select(
            options=[('Loading...', '')],
            id='model-embedding',
        )

        # Advanced collapsible section
        yield Static(
            '\n[bold]Advanced Settings[/bold] [dim](Optional)[/dim]',
            classes='section-title',
        )

        with Collapsible(
            title='Secondary Models & RAG Configuration', collapsed=True, id='advanced'
        ):
            yield Static(
                "[dim]These settings use sensible defaults. Most users don't need to change them.[/dim]\n"
            )

            # Secondary model selections
            yield Static('[bold]Secondary Models[/bold]')

            yield Label('Citation Model')
            yield Static('[dim]Extracts and processes citations from documents[/dim]')
            yield Select(options=[('Loading...', '')], id='model-citation')
            yield Static(id='warning-citation', classes='context-warning hidden')

            yield Label('\nTag Consolidation Model')
            yield Static('[dim]Consolidates and merges similar tags[/dim]')
            yield Select(options=[('Loading...', '')], id='model-tag-consolidate')
            yield Static(id='warning-tag-consolidate', classes='context-warning hidden')

            yield Label('\nTag Suggestion Model')
            yield Static('[dim]Suggests tags for documents[/dim]')
            yield Select(options=[('Loading...', '')], id='model-tag-suggest')
            yield Static(id='warning-tag-suggest', classes='context-warning hidden')

            yield Label('\nTag Mapping Model')
            yield Static('[dim]Maps tags across documents[/dim]')
            yield Select(options=[('Loading...', '')], id='model-tag-map')
            yield Static(id='warning-tag-map', classes='context-warning hidden')

            yield Label('\nResearch Agent Model')
            yield Static('[dim]Powers autonomous research workflows[/dim]')
            yield Select(options=[('Loading...', '')], id='model-research')
            yield Static(id='warning-research', classes='context-warning hidden')

            yield Label('\nScrape Filter Model')
            yield Static('[dim]Filters and processes scraped web content[/dim]')
            yield Select(options=[('Loading...', '')], id='model-scrape')
            yield Static(id='warning-scrape', classes='context-warning hidden')

            yield Label('\nRAG QA Model')
            yield Static('[dim]Answers questions from retrieved documents[/dim]')
            yield Select(options=[('Loading...', '')], id='model-rag-qa')
            yield Static(id='warning-rag-qa', classes='context-warning hidden')

            yield Label('\nQuery Routing Model')
            yield Static('[dim]Routes queries to appropriate handlers[/dim]')
            yield Select(options=[('Loading...', '')], id='model-routing')
            yield Static(id='warning-routing', classes='context-warning hidden')

            # RAG and chunking settings
            yield Static('\n[bold]RAG & Chunking Settings[/bold]')

            yield Label('RAG Chunk Size (tokens)')
            yield Input(
                placeholder='1000',
                id='rag-chunk-size',
                value=str(self._get_default('rag.chunkSize', '1000')),
            )

            yield Label('RAG Chunk Overlap (tokens)')
            yield Input(
                placeholder='200',
                id='rag-chunk-overlap',
                value=str(self._get_default('rag.chunkOverlap', '200')),
            )

            yield Label('Document Processing Chunk Size (tokens)')
            yield Input(
                placeholder='4000',
                id='doc-chunk-size',
                value=str(self._get_default('llm.default.chunkSize', '4000')),
            )

            yield Label('Document Processing Chunk Overlap (tokens)')
            yield Input(
                placeholder='200',
                id='doc-chunk-overlap',
                value=str(self._get_default('llm.default.chunkOverlap', '200')),
            )

            yield Label('Document Processing Strategy')
            yield Static(
                '[dim]auto: Automatically choose based on document size\n'
                'direct: Process entire document at once\n'
                'map_reduce: Split, process, then combine\n'
                'refine: Iteratively refine results[/dim]'
            )
            yield Select(
                options=[
                    ('Auto (recommended)', 'auto'),
                    ('Direct', 'direct'),
                    ('Map-Reduce', 'map_reduce'),
                    ('Refine', 'refine'),
                ],
                id='doc-processing-strategy',
                value=self._get_default('llm.default.docProcessing', 'auto'),
            )

            yield Label('\nTemperature (0.0 - 2.0)')
            yield Input(
                placeholder='0.9',
                id='temperature',
                value=str(self._get_default('llm.default.temperature', '0.9')),
            )

            yield Label('Max Output Tokens')
            yield Input(
                placeholder='500000',
                id='max-output-tokens',
                value=str(self._get_default('llm.default.maxOutputTokens', '500000')),
            )

    async def on_select_changed(self, event: Select.Changed) -> None:
        """Handle model selection changes for context length validation.

        Args:
            event: Select changed event
        """
        if not event.select.id or not event.select.id.startswith('model-'):
            return

        model_id = str(event.value)
        if not model_id:
            return

        # Map select IDs to their max context length settings
        context_limits = {
            'model-doc-analysis': 8000,  # llm.default.maxContextLength
            'model-citation': 4000,  # llm.citation.maxContextLength
            'model-research': 100000,  # llm.researchAgent.maxContextLength
            'model-scrape': 50000,  # llm.scrapeFilter.maxContextLength
            'model-tag-consolidate': 8000,
            'model-tag-suggest': 8000,
            'model-tag-map': 8000,
            'model-rag-qa': 8000,
            'model-routing': 8000,
            'model-letta': 0,  # No fixed limit for Letta
        }

        max_context = context_limits.get(event.select.id, 0)
        if max_context == 0:
            return

        # Check model's actual context length
        model_context = self.model_context_lengths.get(model_id, 0)
        if model_context == 0:
            return  # Unknown context length, can't validate

        # Show/hide warning
        warning_id = event.select.id.replace('model-', 'warning-')
        try:
            warning_widget = self.query_one(f'#{warning_id}', Static)
            if max_context > model_context:
                warning_widget.update(
                    f'[yellow]⚠ Warning: {model_id} has a {model_context:,} token context window, '
                    f'but this component is configured for {max_context:,} tokens. This may cause errors.[/yellow]'
                )
                warning_widget.remove_class('hidden')
            else:
                warning_widget.update('')
                warning_widget.add_class('hidden')
        except Exception as e:
            logger.debug(f'Could not update warning widget: {e}')

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """Validate model selections and settings.

        Returns:
            Dict with model_settings data, or None if invalid
        """
        model_settings: dict[str, Any] = {}

        # Get visible model selections
        try:
            model_settings['llm'] = {
                'default': {
                    'model': self.query_one('#model-doc-analysis', Select).value,
                    'temperature': float(
                        self.query_one('#temperature', Input).value or '0.9'
                    ),
                    'chunkSize': int(
                        self.query_one('#doc-chunk-size', Input).value or '4000'
                    ),
                    'chunkOverlap': int(
                        self.query_one('#doc-chunk-overlap', Input).value or '200'
                    ),
                    'docProcessing': self.query_one(
                        '#doc-processing-strategy', Select
                    ).value,
                    'maxOutputTokens': int(
                        self.query_one('#max-output-tokens', Input).value or '500000'
                    ),
                },
                'citation': {
                    'model': self.query_one('#model-citation', Select).value,
                },
                'tagConsolidator': {
                    'consolidateModel': self.query_one(
                        '#model-tag-consolidate', Select
                    ).value,
                    'suggestModel': self.query_one('#model-tag-suggest', Select).value,
                    'mapModel': self.query_one('#model-tag-map', Select).value,
                },
                'researchAgent': {
                    'model': self.query_one('#model-research', Select).value,
                },
                'scrapeFilter': {
                    'model': self.query_one('#model-scrape', Select).value,
                },
                'queryBasedRouting': {
                    'routingModel': self.query_one('#model-routing', Select).value,
                },
            }

            embedding_model = self.query_one('#model-embedding', Select).value
            model_settings['rag'] = {
                'embeddingModel': embedding_model,
                'chunkSize': int(
                    self.query_one('#rag-chunk-size', Input).value or '1000'
                ),
                'chunkOverlap': int(
                    self.query_one('#rag-chunk-overlap', Input).value or '200'
                ),
                'qa': {
                    'model': self.query_one('#model-rag-qa', Select).value,
                },
            }

            model_settings['memory'] = {
                'letta': {
                    'agentModel': self.query_one('#model-letta', Select).value,
                    'filesystem': {
                        'embeddingModel': embedding_model,  # Same as RAG embedding
                    },
                }
            }

        except Exception as e:
            self.show_error(f'Error reading model selections: {e}')
            logger.error(f'Validation error: {e}')
            return None

        # Validate numeric inputs
        try:
            temp = float(self.query_one('#temperature', Input).value or '0.9')
            if not 0.0 <= temp <= 2.0:
                self.show_error('Temperature must be between 0.0 and 2.0')
                return None
        except ValueError:
            self.show_error('Invalid temperature value')
            return None

        logger.info('Model selections validated successfully')
        return {'model_settings': model_settings}

    async def on_next_screen(self) -> None:
        """Navigate to review screen.

        Skips dependency check (install.sh handles Docker, services start later)
        and optional features (all core features enabled by default).
        """
        from .review import ReviewScreen

        # Set default feature flags so downstream screens have them
        if hasattr(self.app, 'wizard_data'):
            getattr(self.app, 'wizard_data', {}).update(
                {
                    'rag_enabled': True,
                    'discovery_enabled': True,
                    'citations_enabled': True,
                    'local_embeddings': False,
                }
            )

        logger.info('Proceeding to review')
        await self.app.push_screen(ReviewScreen())

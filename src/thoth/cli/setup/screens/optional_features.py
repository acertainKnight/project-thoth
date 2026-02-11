"""
Optional features screen for setup wizard.

.. deprecated::
    This screen is no longer used in the wizard flow. All core features
    (RAG, Discovery, Citations) are enabled by default. The defaults are
    set directly in the model_selection and configuration screens.
    Kept for potential future use if features become truly optional.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Checkbox, Static

from .base import BaseScreen


class OptionalFeaturesScreen(BaseScreen):
    """Screen for configuring optional features."""

    def __init__(self) -> None:
        """Initialize optional features screen."""
        super().__init__(
            title='Optional Features',
            subtitle='Configure additional research capabilities',
        )
        self.rag_enabled = True  # Default enabled
        self.discovery_enabled = True
        self.citations_enabled = True
        self.local_embeddings = False  # Default to API-based (lightweight)

    def compose_content(self) -> ComposeResult:
        """
        Compose optional features content.

        Returns:
            Content widgets
        """
        yield Static(
            '[bold]Select Features:[/bold]\n'
            '[dim]Toggle features on/off with Space key.[/dim]\n',
            classes='section-title',
        )

        # RAG (Vector Database) - Core Feature
        with Vertical(classes='feature-section'):
            yield Static('[cyan]Vector Database (RAG)[/cyan]', classes='feature-header')
            yield Static(
                'Semantic search across your research papers.\n'
                '[dim]Uses API-based embeddings (OpenAI, etc.) - lightweight & fast[/dim]',
                classes='feature-description',
            )
            yield Checkbox(
                'Enable RAG & Semantic Search', id='rag-checkbox', value=True
            )

        # Discovery Service
        with Vertical(classes='feature-section'):
            yield Static('[cyan]Discovery Service[/cyan]', classes='feature-header')
            yield Static(
                'Auto-discover related papers via Semantic Scholar API.\n'
                '[dim]Storage: ~100MB per 1000 papers[/dim]',
                classes='feature-description',
            )
            yield Checkbox(
                'Enable Paper Discovery', id='discovery-checkbox', value=True
            )

        # Citation Resolution
        with Vertical(classes='feature-section'):
            yield Static('[cyan]Citation Resolution[/cyan]', classes='feature-header')
            yield Static(
                'Resolve citations via Crossref, OpenAlex, and ArXiv.\n'
                '[dim]~5-10s per citation[/dim]',
                classes='feature-description',
            )
            yield Checkbox(
                'Enable Citation Resolution', id='citations-checkbox', value=True
            )

        # Local Embeddings - Optional Heavy Feature (last, de-emphasized)
        with Vertical(classes='feature-section'):
            yield Static(
                '[yellow]Local ML Models[/yellow] [dim](Advanced)[/dim]',
                classes='feature-header',
            )
            yield Static(
                'PyTorch + sentence-transformers for offline embeddings.\n'
                '[red bold]+2-3GB disk | +4-8GB RAM | Slower than APIs[/red bold]\n'
                '[dim]Not recommended - API embeddings work better for most users.[/dim]',
                classes='feature-description',
            )
            yield Checkbox(
                'Install Local ML Models (Not Recommended)',
                id='local-embeddings-checkbox',
                value=False,
            )

        # Compact disk space estimate
        yield Static(
            '\n[yellow]Disk Estimate:[/yellow] '
            '[green]~2GB[/green] lightweight | '
            '[red]~5-10GB[/red] with local models',
            classes='help-text',
        )

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate optional features selection.

        Returns:
            Dict with selected features
        """
        # Get checkbox states
        try:
            rag_checkbox = self.query_one('#rag-checkbox', Checkbox)
            discovery_checkbox = self.query_one('#discovery-checkbox', Checkbox)
            citations_checkbox = self.query_one('#citations-checkbox', Checkbox)
            local_embeddings_checkbox = self.query_one(
                '#local-embeddings-checkbox', Checkbox
            )

            self.rag_enabled = rag_checkbox.value
            self.discovery_enabled = discovery_checkbox.value
            self.citations_enabled = citations_checkbox.value
            self.local_embeddings = local_embeddings_checkbox.value

        except Exception as e:
            logger.error(f'Error reading checkbox states: {e}')
            self.show_error(f'Failed to read feature selections: {e}')
            return None

        # Warn if user selected local embeddings
        if self.local_embeddings:
            logger.warning('User selected local embeddings (heavy installation)')
            self.show_warning(
                'Local embeddings will add 2-3GB to installation size and use significant memory. '
                'API-based embeddings are recommended for most users.'
            )

        logger.info(
            f'Optional features: RAG={self.rag_enabled}, '
            f'Discovery={self.discovery_enabled}, '
            f'Citations={self.citations_enabled}, '
            f'Local Embeddings={self.local_embeddings}'
        )

        return {
            'rag_enabled': self.rag_enabled,
            'discovery_enabled': self.discovery_enabled,
            'citations_enabled': self.citations_enabled,
            'local_embeddings': self.local_embeddings,
        }

    async def on_next_screen(self) -> None:
        """Navigate to review screen."""
        from .review import ReviewScreen

        logger.info('Proceeding to review')
        await self.app.push_screen(ReviewScreen())

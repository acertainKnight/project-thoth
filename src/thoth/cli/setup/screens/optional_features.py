"""
Optional features screen for setup wizard.

Configure optional components: RAG, Discovery, Citations.
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
            title="Optional Features",
            subtitle="Configure additional research capabilities",
        )
        self.rag_enabled = True  # Default enabled
        self.discovery_enabled = True
        self.citations_enabled = True

    def compose_content(self) -> ComposeResult:
        """
        Compose optional features content.

        Returns:
            Content widgets
        """
        yield Static("[bold]Select Features:[/bold]\n", classes="section-title")

        # RAG (Vector Database)
        with Vertical(classes="feature-section"):
            yield Static(
                "[cyan]Vector Database (RAG)[/cyan]",
                classes="feature-header",
            )
            yield Static(
                "Enable semantic search across your research papers using vector embeddings.\n"
                "[dim]Disk: ~500MB for embeddings | Memory: ~2GB during processing[/dim]",
                classes="feature-description",
            )
            yield Checkbox(
                "Enable RAG & Semantic Search",
                id="rag-checkbox",
                value=True,
            )

        # Discovery Service
        with Vertical(classes="feature-section"):
            yield Static(
                "\n[cyan]Discovery Service[/cyan]",
                classes="feature-header",
            )
            yield Static(
                "Automatically discover related papers using Semantic Scholar API.\n"
                "[dim]Network: API rate limits apply | Storage: ~100MB per 1000 papers[/dim]",
                classes="feature-description",
            )
            yield Checkbox(
                "Enable Paper Discovery",
                id="discovery-checkbox",
                value=True,
            )

        # Citation Resolution
        with Vertical(classes="feature-section"):
            yield Static(
                "\n[cyan]Citation Resolution[/cyan]",
                classes="feature-header",
            )
            yield Static(
                "Auto-resolve citations using Crossref, OpenAlex, and ArXiv.\n"
                "[dim]Network: Multiple API calls per paper | Processing: ~5-10s per citation[/dim]",
                classes="feature-description",
            )
            yield Checkbox(
                "Enable Citation Resolution",
                id="citations-checkbox",
                value=True,
            )

        # Disk space estimate
        yield Static(
            "\n[yellow]Estimated Total Disk Usage:[/yellow]",
            classes="section-title",
        )
        yield Static(
            "[dim]RAG: ~500MB | Discovery: ~100-500MB | Citations: minimal[/dim]\n"
            "[dim]Total: ~600MB-1GB for typical usage[/dim]",
            classes="help-text",
        )

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate optional features selection.

        Returns:
            Dict with selected features
        """
        # Get checkbox states
        try:
            rag_checkbox = self.query_one("#rag-checkbox", Checkbox)
            discovery_checkbox = self.query_one("#discovery-checkbox", Checkbox)
            citations_checkbox = self.query_one("#citations-checkbox", Checkbox)

            self.rag_enabled = rag_checkbox.value
            self.discovery_enabled = discovery_checkbox.value
            self.citations_enabled = citations_checkbox.value

        except Exception as e:
            logger.error(f"Error reading checkbox states: {e}")
            self.show_error(f"Failed to read feature selections: {e}")
            return None

        logger.info(
            f"Optional features: RAG={self.rag_enabled}, "
            f"Discovery={self.discovery_enabled}, "
            f"Citations={self.citations_enabled}"
        )

        return {
            "rag_enabled": self.rag_enabled,
            "discovery_enabled": self.discovery_enabled,
            "citations_enabled": self.citations_enabled,
        }

    async def on_next_screen(self) -> None:
        """Navigate to review screen."""
        from .review import ReviewScreen

        logger.info("Proceeding to review")
        await self.app.push_screen(ReviewScreen())

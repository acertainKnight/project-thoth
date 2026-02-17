"""
Review screen for setup wizard.

Display complete configuration summary before final confirmation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.widgets import Button, Static

# Note: ReviewScreen uses base on_button_pressed for cancel/back/next
from .base import BaseScreen


class ReviewScreen(BaseScreen):
    """Screen for reviewing complete configuration."""

    def __init__(self) -> None:
        """Initialize review screen."""
        super().__init__(
            title='Review Configuration',
            subtitle='Verify your settings before installation',
        )

    def compose_content(self) -> ComposeResult:
        """
        Compose review content.

        Returns:
            Content widgets
        """
        # Get wizard data
        wizard_data: dict[str, Any] = {}
        if hasattr(self.app, 'wizard_data'):
            wizard_data = self.app.wizard_data

        yield Static('[bold]Configuration Summary:[/bold]\n', classes='section-title')

        # Deployment Mode
        deployment_mode = wizard_data.get('deployment_mode', 'local')
        mode_text = (
            '[cyan]Local[/cyan] (Docker on this machine)'
            if deployment_mode == 'local'
            else '[cyan]Remote[/cyan] (Connect to existing server)'
        )
        yield Static(f'  [cyan]Deployment:[/cyan]    {mode_text}')

        # Server Endpoints (for remote mode)
        if deployment_mode == 'remote':
            thoth_api_url = wizard_data.get('thoth_api_url', 'http://localhost:8000')
            yield Static(f'  [cyan]Thoth Server:[/cyan]   {thoth_api_url}')

        # Vault Configuration (show host path when running in Docker)
        vault_path = wizard_data.get(
            'vault_path_host', wizard_data.get('vault_path', '[dim]Not set[/dim]')
        )
        yield Static(f'  [cyan]Obsidian Vault:[/cyan] {vault_path}')

        # API Keys Configuration
        api_keys = wizard_data.get('api_keys', {})
        provider_names = [pid.title() for pid in api_keys.keys()]
        providers_text = (
            ', '.join(provider_names)
            if provider_names
            else '[dim]None configured[/dim]'
        )
        yield Static(f'  [cyan]API Keys:[/cyan]        {providers_text}')

        # Model Configuration
        model_settings = wizard_data.get('model_settings', {})
        if model_settings:
            yield Static('\n  [bold]Model Configuration:[/bold]')

            # Essential models
            llm_config = model_settings.get('llm', {})
            if llm_config:
                default_cfg = llm_config.get('default', {})
                doc_model = default_cfg.get('model', 'Not set')
                yield Static(f'    • Document Analysis: {doc_model}')

            memory_config = model_settings.get('memory', {})
            if memory_config:
                letta_cfg = memory_config.get('letta', {})
                letta_model = letta_cfg.get('agentModel', 'Not set')
                yield Static(f'    • Letta Chat Agent: {letta_model}')

            rag_config = model_settings.get('rag', {})
            if rag_config:
                embedding_model = rag_config.get('embeddingModel', 'Not set')
                yield Static(f'    • Embeddings: {embedding_model}')

                # Advanced RAG settings
                hybrid = rag_config.get('hybridSearchEnabled', False)
                reranking = rag_config.get('rerankingEnabled', False)
                reranker = rag_config.get('rerankerProvider', 'auto')
                contextual = rag_config.get('contextualEnrichmentEnabled', False)
                adaptive = rag_config.get('adaptiveRoutingEnabled', False)

                hybrid_status = (
                    '[green]enabled[/green]' if hybrid else '[dim]disabled[/dim]'
                )
                rerank_status = (
                    f'[green]enabled ({reranker})[/green]'
                    if reranking
                    else '[dim]disabled[/dim]'
                )
                contextual_status = (
                    '[yellow]enabled (requires re-indexing)[/yellow]'
                    if contextual
                    else '[dim]disabled[/dim]'
                )
                adaptive_status = (
                    '[yellow]enabled[/yellow]' if adaptive else '[dim]disabled[/dim]'
                )

                yield Static(
                    f'    • Hybrid Search: {hybrid_status}\n'
                    f'    • Reranking: {rerank_status}\n'
                    f'    • Contextual Enrichment: {contextual_status}\n'
                    f'    • Adaptive Routing: {adaptive_status}'
                )

            # Advanced models (collapsed summary)
            if llm_config:
                citation_model = llm_config.get('citation', {}).get('model', 'Not set')
                research_model = llm_config.get('researchAgent', {}).get(
                    'model', 'Not set'
                )
                yield Static(
                    f'    [dim]• Citation: {citation_model}[/dim]\n'
                    f'    [dim]• Research Agent: {research_model}[/dim]\n'
                    f'    [dim]• + 6 more secondary models[/dim]'
                )

        # Letta Configuration
        letta_mode = wizard_data.get('letta_mode', 'self-hosted')
        letta_url = wizard_data.get('letta_url', 'http://localhost:8283')
        letta_available = wizard_data.get('letta_available', False)

        if letta_mode == 'cloud':
            has_key = bool(wizard_data.get('letta_api_key'))
            key_status = (
                '[green]configured[/green]' if has_key else '[red]missing[/red]'
            )
            yield Static(f'  [cyan]Letta Memory:[/cyan]   Cloud (key: {key_status})')
        elif letta_mode == 'remote':
            remote_status = (
                '[green]Reachable[/green]'
                if letta_available
                else '[yellow]Not verified[/yellow]'
            )
            yield Static(
                f'  [cyan]Letta Memory:[/cyan]   Remote Server ({remote_status})'
            )
            yield Static(f'  [cyan]Letta URL:[/cyan]      {letta_url}')
        else:
            local_status = (
                '[green]Running[/green]'
                if letta_available
                else "[yellow]Will start with 'thoth start'[/yellow]"
            )
            yield Static(
                f'  [cyan]Letta Memory:[/cyan]   Self-Hosted Docker ({local_status})'
            )

        # Database Configuration (only for local deployment)
        deployment_mode = wizard_data.get('deployment_mode', 'local')
        if deployment_mode == 'local':
            postgres_available = wizard_data.get('postgres_available', False)
            db_status = (
                '[green]Ready[/green]'
                if postgres_available
                else '[yellow]Will be started[/yellow]'
            )
            yield Static(f'  [cyan]PostgreSQL:[/cyan]     {db_status}')

        # Optional Features
        rag_enabled = wizard_data.get('rag_enabled', False)
        discovery_enabled = wizard_data.get('discovery_enabled', False)
        citations_enabled = wizard_data.get('citations_enabled', False)
        local_ml = wizard_data.get('local_embeddings', False)

        features = []
        if rag_enabled:
            features.append('Vector Search (RAG)')
        if discovery_enabled:
            features.append('Paper Discovery')
        if citations_enabled:
            features.append('Citation Resolution')
        if local_ml:
            features.append('[yellow]Local ML Models[/yellow]')

        features_text = ', '.join(features) if features else '[dim]None enabled[/dim]'
        yield Static(f'  [cyan]Features:[/cyan]       {features_text}')

        # Directory Paths
        if wizard_data.get('vault_path'):
            vault = Path(str(wizard_data['vault_path']))
            paths_config = wizard_data.get('paths_config', {})
            workspace_rel = paths_config.get('workspace', 'thoth/_thoth')
            pdf_rel = paths_config.get('pdf', 'thoth/papers/pdfs')
            notes_rel = paths_config.get('notes', 'thoth/notes')
            yield Static(
                f'  [cyan]Workspace:[/cyan]     {vault / workspace_rel}\n'
                f'  [cyan]PDF Dir:[/cyan]       {vault / pdf_rel}\n'
                f'  [cyan]Notes Dir:[/cyan]     {vault / notes_rel}'
            )

        # Disk Usage Estimate (only for local deployment)
        deployment_mode = wizard_data.get('deployment_mode', 'local')
        if deployment_mode == 'local':
            size_parts = ['~1.5GB base']
            if rag_enabled:
                size_parts.append('~500MB RAG')
            if local_ml:
                size_parts.append('[red]~3GB local ML[/red]')
            yield Static(
                f'\n  [yellow]Est. Disk:[/yellow]      {" + ".join(size_parts)}'
            )
        else:
            yield Static('\n  [green]No local Docker containers needed[/green]')

        # Edit instructions
        yield Static(
            '\n[dim]Use ← Back or Ctrl+B to go back and change settings.[/dim]',
            classes='help-text',
        )

    def compose_buttons(self) -> ComposeResult:
        """
        Compose navigation buttons.

        Returns:
            Button widgets
        """
        yield Button('Cancel & Exit', id='cancel', variant='error')
        yield Button('← Back', id='back', variant='default')
        yield Button('Install →', id='next', variant='success')

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate configuration and proceed to installation.

        Returns:
            Dict confirming review, or None if validation fails
        """
        # Basic validation
        if not hasattr(self.app, 'wizard_data'):
            self.show_error('No configuration data found')
            return None

        wizard_data = self.app.wizard_data

        # Check required fields
        if not wizard_data.get('vault_path'):
            self.show_error('Vault path is required')
            return None

        logger.info('Configuration review validated successfully')
        return {'review_confirmed': True}

    async def on_next_screen(self) -> None:
        """Navigate to installation screen."""
        from .installation import InstallationScreen

        logger.info('Proceeding to installation')
        await self.app.push_screen(InstallationScreen())

"""
Configuration screen for setup wizard.

Allows users to configure LLM providers, API keys, and model settings.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, ClassVar

from loguru import logger
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Checkbox, Input, Label, Select, Static

from ..config_manager import ConfigManager
from ..validators import APIKeyValidator
from .base import BaseScreen


class ConfigurationScreen(BaseScreen):
    """Screen for configuring LLM providers and settings."""

    # Available LLM providers and their models
    PROVIDERS: ClassVar[dict[str, dict[str, Any]]] = {
        "openai": {
            "name": "OpenAI",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
            "default_model": "gpt-4o-mini",
        },
        "anthropic": {
            "name": "Anthropic",
            "models": [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
            ],
            "default_model": "claude-3-5-sonnet-20241022",
        },
        "google": {
            "name": "Google",
            "models": [
                "gemini-2.0-flash-exp",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
            ],
            "default_model": "gemini-2.0-flash-exp",
        },
        "mistral": {
            "name": "Mistral AI",
            "models": ["mistral-large-latest", "mistral-small-latest", "mistral-tiny"],
            "default_model": "mistral-small-latest",
        },
        "openrouter": {
            "name": "OpenRouter",
            "models": [
                "anthropic/claude-3.5-sonnet",
                "google/gemini-2.0-flash-exp:free",
                "openai/gpt-4o",
            ],
            "default_model": "google/gemini-2.0-flash-exp:free",
        },
    }

    def __init__(self, vault_path: Path | None = None) -> None:
        """
        Initialize configuration screen.

        Args:
            vault_path: Path to Obsidian vault for loading existing config
        """
        super().__init__(
            title="Configure LLM Settings",
            subtitle="Set up your AI model providers and API keys",
        )
        self.vault_path = vault_path
        self.config_manager = (
            ConfigManager(vault_path) if vault_path else ConfigManager()
        )
        self.existing_config: dict[str, Any] = {}
        self.provider_configs: dict[str, dict[str, Any]] = {}

    def on_mount(self) -> None:
        """Run when screen is mounted."""
        self._load_task = asyncio.create_task(self.load_existing_config())

    async def load_existing_config(self) -> None:
        """Load existing configuration if available."""
        self.show_info("Loading existing configuration...")

        try:
            existing = self.config_manager.load_existing()
            if existing:
                self.existing_config = existing
                logger.info("Loaded existing configuration")
                self.show_info(
                    "Found existing configuration. Your settings will be preserved."
                )
            else:
                logger.info("No existing configuration found")
                self.clear_messages()

            self.refresh()

        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.show_error(f"Failed to load configuration: {e}")

    def compose_content(self) -> ComposeResult:
        """
        Compose configuration content.

        Returns:
            Content widgets
        """
        yield Static(
            "[bold]Configure at least one LLM provider:[/bold]",
            classes="section-title",
        )

        # Provider configuration sections
        for provider_id, provider_info in self.PROVIDERS.items():
            with Container(classes="provider-section"):
                # Provider header with checkbox
                with Horizontal(classes="provider-header"):
                    yield Checkbox(
                        f"[bold]{provider_info['name']}[/bold]",
                        id=f"enable-{provider_id}",
                        value=self._is_provider_enabled(provider_id),
                    )

                # Provider configuration (shown only if enabled)
                with Vertical(
                    id=f"config-{provider_id}", classes="provider-config"
                ):
                    # API Key input
                    yield Label("API Key:")
                    yield Input(
                        placeholder=f"Enter your {provider_info['name']} API key",
                        password=True,
                        id=f"api-key-{provider_id}",
                        value=self._get_existing_api_key(provider_id),
                    )

                    # Model selection
                    yield Label("Model:")
                    yield Select(
                        options=[
                            (model, model) for model in provider_info["models"]
                        ],
                        id=f"model-{provider_id}",
                        value=self._get_existing_model(provider_id, provider_info),
                    )

        # Advanced settings section
        yield Static(
            "\n[bold]Advanced Settings (Optional):[/bold]",
            classes="section-title",
        )

        with Vertical(classes="advanced-settings"):
            yield Label("Temperature (0.0 - 2.0):")
            yield Input(
                placeholder="0.7",
                id="temperature",
                value=str(
                    self.existing_config.get("llm_settings", {}).get(
                        "temperature", 0.7
                    )
                ),
            )

            yield Label("Max Tokens:")
            yield Input(
                placeholder="4096",
                id="max-tokens",
                value=str(
                    self.existing_config.get("llm_settings", {}).get(
                        "max_tokens", 4096
                    )
                ),
            )

    def _is_provider_enabled(self, provider_id: str) -> bool:
        """
        Check if provider is enabled in existing config.

        Args:
            provider_id: Provider identifier

        Returns:
            True if provider is enabled
        """
        llm_settings = self.existing_config.get("llm_settings", {})
        providers = llm_settings.get("providers", {})
        provider_config = providers.get(provider_id, {})
        return provider_config.get("enabled", False)

    def _get_existing_api_key(self, provider_id: str) -> str:
        """
        Get existing API key for provider.

        Args:
            provider_id: Provider identifier

        Returns:
            API key or empty string
        """
        llm_settings = self.existing_config.get("llm_settings", {})
        providers = llm_settings.get("providers", {})
        provider_config = providers.get(provider_id, {})
        return provider_config.get("api_key", "")

    def _get_existing_model(
        self, provider_id: str, provider_info: dict[str, Any]
    ) -> str:
        """
        Get existing model for provider.

        Args:
            provider_id: Provider identifier
            provider_info: Provider information dict

        Returns:
            Model name or default model
        """
        llm_settings = self.existing_config.get("llm_settings", {})
        providers = llm_settings.get("providers", {})
        provider_config = providers.get(provider_id, {})
        return provider_config.get("model", provider_info["default_model"])

    async def validate_and_proceed(self) -> dict[str, Any] | None:
        """
        Validate configuration settings.

        Returns:
            Dict with configuration data, or None if invalid
        """
        llm_settings: dict[str, Any] = {"providers": {}}
        enabled_count = 0

        # Validate each provider
        for provider_id, provider_info in self.PROVIDERS.items():
            # Check if provider is enabled
            checkbox = self.query_one(f"#enable-{provider_id}", Checkbox)
            if not checkbox.value:
                continue

            enabled_count += 1

            # Get API key
            api_key_input = self.query_one(f"#api-key-{provider_id}", Input)
            api_key = api_key_input.value.strip()

            # Validate API key
            if not api_key:
                self.show_error(
                    f"Please provide an API key for {provider_info['name']}"
                )
                return None

            is_valid, error_msg = APIKeyValidator.validate(provider_id, api_key)
            if not is_valid:
                self.show_error(
                    f"{provider_info['name']}: {error_msg or 'Invalid API key format'}"
                )
                return None

            # Get model
            model_select = self.query_one(f"#model-{provider_id}", Select)
            model = model_select.value

            # Store provider config
            llm_settings["providers"][provider_id] = {
                "enabled": True,
                "api_key": api_key,
                "model": model,
            }

        # Ensure at least one provider is configured
        if enabled_count == 0:
            self.show_error("Please enable and configure at least one LLM provider")
            return None

        # Get advanced settings
        try:
            temperature_input = self.query_one("#temperature", Input)
            temperature = float(temperature_input.value or "0.7")
            if not 0.0 <= temperature <= 2.0:
                self.show_error("Temperature must be between 0.0 and 2.0")
                return None
            llm_settings["temperature"] = temperature
        except ValueError:
            self.show_error("Invalid temperature value")
            return None

        try:
            max_tokens_input = self.query_one("#max-tokens", Input)
            max_tokens = int(max_tokens_input.value or "4096")
            if max_tokens < 1:
                self.show_error("Max tokens must be at least 1")
                return None
            llm_settings["max_tokens"] = max_tokens
        except ValueError:
            self.show_error("Invalid max tokens value")
            return None

        logger.info(
            f"Configuration validated with {enabled_count} provider(s) enabled"
        )
        return {"llm_settings": llm_settings}

    async def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """
        Handle checkbox changes to show/hide provider configs.

        Args:
            event: Checkbox changed event
        """
        if event.checkbox.id and event.checkbox.id.startswith("enable-"):
            provider_id = event.checkbox.id.replace("enable-", "")
            config_container = self.query_one(f"#config-{provider_id}")

            if event.value:
                config_container.display = True
            else:
                config_container.display = False

    async def on_next_screen(self) -> None:
        """Navigate to dependency check screen."""
        from .dependency_check import DependencyCheckScreen

        logger.info("Proceeding to dependency check")
        await self.app.push_screen(DependencyCheckScreen())

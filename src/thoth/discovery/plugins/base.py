from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, List, Dict, Type

from loguru import logger

from thoth.utilities.schemas import ResearchQuery, ScrapedArticleMetadata


class DiscoveryPlugin(Protocol):
    """Protocol that all discovery plugins must follow."""

    def discover(self, query: ResearchQuery, max_results: int) -> List[ScrapedArticleMetadata]:
        """Discover articles matching the given query."""

    def validate_config(self, config: dict) -> bool:
        """Validate plugin specific configuration."""

    def get_name(self) -> str:
        """Return the unique plugin name."""


class BaseDiscoveryPlugin(ABC):
    """Base class providing common discovery plugin functionality."""

    def __init__(self, config: dict | None = None) -> None:
        self.config: dict = config or {}
        self.logger = logger.bind(plugin=self.get_name())

    @abstractmethod
    def discover(self, query: ResearchQuery, max_results: int) -> List[ScrapedArticleMetadata]:
        """Discover articles for the provided query."""

    def validate_config(self, config: dict) -> bool:  # noqa: D401 - simple default
        """Validate the provided configuration."""
        return True

    def get_name(self) -> str:  # noqa: D401 - simple default
        """Return the plugin's name."""
        return self.__class__.__name__


class DiscoveryPluginRegistry:
    """Registry for managing discovery plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, Type[DiscoveryPlugin]] = {}

    def register(self, name: str, plugin_cls: Type[DiscoveryPlugin]) -> None:
        """Register a discovery plugin class."""
        self._plugins[name] = plugin_cls
        logger.debug(f"Registered discovery plugin: {name}")

    def create(self, name: str, *args, **kwargs) -> DiscoveryPlugin:
        """Instantiate a registered plugin."""
        if name not in self._plugins:
            raise ValueError(f"Plugin '{name}' not registered")
        plugin_cls = self._plugins[name]
        return plugin_cls(*args, **kwargs)  # type: ignore[call-arg]

    def list_plugins(self) -> List[str]:
        """List names of all registered plugins."""
        return list(self._plugins.keys())

    def get(self, name: str) -> Type[DiscoveryPlugin] | None:
        """Retrieve a registered plugin class by name."""
        return self._plugins.get(name)

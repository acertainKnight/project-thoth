from __future__ import annotations

from collections.abc import Callable

from loguru import logger

from .base_tool import BaseThothTool

"""Decorators for registering Thoth agent tools automatically."""

# Global registry for decorated tools
_registered_tools: dict[str, type[BaseThothTool]] = {}


def tool(
    cls: type[BaseThothTool] | None = None, *, name: str | None = None
) -> Callable[[type[BaseThothTool]], type[BaseThothTool]]:
    """Class decorator to register a tool.

    The decorator validates the tool class and stores it in the registry so it can
    be automatically discovered by the research assistant.
    """

    def _decorate(tool_cls: type[BaseThothTool]) -> type[BaseThothTool]:
        # Ensure subclass of BaseThothTool
        if not issubclass(tool_cls, BaseThothTool):
            raise TypeError('@tool can only be used with BaseThothTool subclasses')
        # Ensure _run implemented
        if '_run' not in tool_cls.__dict__ or tool_cls._run is BaseThothTool._run:
            raise TypeError(f'Tool {tool_cls.__name__} must implement _run method')
        field = getattr(tool_cls, 'model_fields', {}).get('name')
        default_name = field.default if field is not None else None
        tool_name = name or default_name or tool_cls.__name__
        if not tool_name:
            raise TypeError(f'Tool {tool_cls.__name__} must define a name')

        tool_cls.name = tool_name  # enforce resolved name

        if tool_name in _registered_tools:
            logger.warning(f'Overwriting existing tool registration: {tool_name}')
        _registered_tools[tool_name] = tool_cls
        logger.debug(f'Registered tool via decorator: {tool_name}')
        return tool_cls

    if cls is None:
        return _decorate
    return _decorate(cls)


def get_registered_tools() -> dict[str, type[BaseThothTool]]:
    """Return a copy of the registered tools mapping."""

    return dict(_registered_tools)

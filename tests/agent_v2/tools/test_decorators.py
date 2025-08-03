from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from thoth.ingestion.agent_v2.core.agent import ResearchAssistant
from thoth.ingestion.agent_v2.tools.base_tool import BaseThothTool
from thoth.ingestion.agent_v2.tools.decorators import get_registered_tools, tool
from thoth.services.service_manager import ServiceManager


def test_tool_decorator_registers_tool() -> None:
    @tool
    class DemoTool(BaseThothTool):
        name: str = 'demo_tool'
        description: str = 'A demo tool'

        def _run(self) -> str:  # type: ignore[override]
            return 'ok'

    registry = get_registered_tools()
    assert 'demo_tool' in registry
    assert registry['demo_tool'] is DemoTool


def test_tool_decorator_validation() -> None:
    with pytest.raises(TypeError):

        @tool
        class BadTool(BaseThothTool):
            name: str = 'bad'
            description: str = 'bad'
            # _run not implemented
            pass

    with pytest.raises(TypeError):

        @tool
        class NotATool:  # type: ignore[misc]
            def _run(self):
                pass


def _mock_service_manager() -> ServiceManager:
    sm = MagicMock(spec=ServiceManager)

    # Mock LLM service
    mock_llm_service = MagicMock()
    mock_llm_client = MagicMock()
    mock_llm_client.bind_tools.return_value.invoke = MagicMock(return_value='ok')
    mock_llm_service.get_client.return_value = mock_llm_client
    sm.llm = mock_llm_service

    # Mock other services
    sm.query = MagicMock()
    sm.discovery = MagicMock()
    sm.rag = MagicMock()
    sm.web_search = MagicMock()
    sm.pdf_locator = MagicMock()
    return sm


@patch('thoth.ingestion.agent_v2.core.agent.TokenUsageTracker')
@patch(
    'thoth.ingestion.agent_v2.core.agent.ResearchAssistant._build_graph',
    return_value=MagicMock(),
)
def test_auto_discovery(_, _mock_tracker) -> None:  # type: ignore[override]
    ra = ResearchAssistant(
        service_manager=_mock_service_manager(),
        enable_memory=False,
        use_mcp_tools=False,
    )
    # For non-MCP tools, manually register them since async_initialize isn't called
    ra._register_tools()
    ra.tools = ra.tool_registry.create_all_tools()
    names = ra.list_tools()
    assert 'list_queries' in names
    assert 'locate_pdf' in names

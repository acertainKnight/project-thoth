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
        name: str = "demo_tool"
        description: str = "A demo tool"

        def _run(self) -> str:  # type: ignore[override]
            return "ok"

    registry = get_registered_tools()
    assert "demo_tool" in registry
    assert registry["demo_tool"] is DemoTool


def test_tool_decorator_validation() -> None:
    with pytest.raises(TypeError):
        @tool
        class BadTool(BaseThothTool):
            name: str = "bad"
            description: str = "bad"
            # _run not implemented
            pass

    with pytest.raises(TypeError):
        @tool
        class NotATool:  # type: ignore[misc]
            def _run(self):
                pass


def _mock_service_manager() -> ServiceManager:
    sm = MagicMock(spec=ServiceManager)
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value.invoke = MagicMock(return_value="ok")
    sm.llm.get_client.return_value = mock_llm
    sm.query = MagicMock()
    sm.discovery = MagicMock()
    sm.rag = MagicMock()
    sm.web_search = MagicMock()
    sm.pdf_locator = MagicMock()
    return sm


@patch("thoth.ingestion.agent_v2.core.agent.TokenUsageTracker")
@patch("thoth.ingestion.agent_v2.core.agent.ResearchAssistant._build_graph", return_value=MagicMock())
def test_auto_discovery(_, mock_tracker) -> None:  # type: ignore[override]
    ra = ResearchAssistant(service_manager=_mock_service_manager(), enable_memory=False)
    names = ra.list_tools()
    assert "list_queries" in names
    assert "locate_pdf" in names

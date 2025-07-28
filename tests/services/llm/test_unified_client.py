from typing import Any

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from thoth.services.llm.protocols import UnifiedLLMClient
from thoth.utilities.anthropic_client import AnthropicClient
from thoth.utilities.openai_client import OpenAIClient
from thoth.utilities.openrouter import OpenRouterClient


class DummySchema(BaseModel):
    result: str


def test_clients_implement_protocol(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'x')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'x')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'x')

    clients: list[UnifiedLLMClient] = [
        OpenAIClient(api_key='x'),
        AnthropicClient(api_key='x', max_tokens=1),
        OpenRouterClient(api_key='x'),
    ]

    for client in clients:
        assert isinstance(client, UnifiedLLMClient)


def test_base_client_methods(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'x')

    monkeypatch.setattr(
        ChatOpenAI,
        'invoke',
        lambda *_args, **_kwargs: AIMessage(content='hello'),
    )
    monkeypatch.setattr(
        ChatOpenAI,
        'stream',
        lambda *_args, **_kwargs: iter(
            [AIMessage(content='a'), AIMessage(content='b')]
        ),
    )

    def _with_structured_output(
        _self, schema: type[BaseModel], **_
    ) -> UnifiedLLMClient:
        class _Struct(OpenAIClient):
            def invoke(self, _prompt: str, **_: Any) -> DummySchema:  # type: ignore[override]
                return schema(result='done')

        return _Struct(api_key='x')

    monkeypatch.setattr(ChatOpenAI, 'with_structured_output', _with_structured_output)

    client = OpenAIClient(api_key='x')

    assert client.invoke_text('hi') == 'hello'
    assert list(client.stream_text('hi')) == ['a', 'b']
    assert client.invoke_structured('hi', DummySchema) == DummySchema(result='done')

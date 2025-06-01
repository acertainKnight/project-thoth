#!/usr/bin/env python3
"""Simple test to verify LangGraph agent with tools works."""

import os

from langchain.tools import Tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from thoth.utilities.openrouter import OpenRouterClient

# Set up environment
os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_PROJECT'] = 'LangGraph Tool Test'


def list_queries_tool(_input: str) -> str:
    """List all available research queries."""
    return 'Available queries:\n- nlp_research\n- machine_learning'


def main():
    print('Testing LangGraph agent with tools...')

    # Create LLM
    llm = OpenRouterClient(model='google/gemini-2.5-flash-preview-05-20', temperature=0)

    # Create tools
    tools = [
        Tool(
            name='list_queries',
            description='List all available research queries.',
            func=list_queries_tool,
        )
    ]

    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # Create agent with bound LLM
    memory = MemorySaver()
    agent = create_react_agent(
        llm_with_tools,  # Use the LLM with tools already bound
        tools,
        checkpointer=memory,
    )

    # Test the agent
    print("\nInvoking agent with 'list queries'...")
    result = agent.invoke(
        {'messages': [{'role': 'user', 'content': 'list queries'}]},
        config={'configurable': {'thread_id': 'test'}},
    )

    print(f'\nResult type: {type(result)}')
    print(f'Result keys: {result.keys() if isinstance(result, dict) else "Not a dict"}')

    if isinstance(result, dict) and 'messages' in result:
        print(f'\nTotal messages: {len(result["messages"])}')
        for i, msg in enumerate(result['messages']):
            print(f'\nMessage {i}:')
            print(f'  Type: {type(msg).__name__}')
            if hasattr(msg, 'content'):
                print(f'  Content: {msg.content}')
            if hasattr(msg, 'tool_calls'):
                print(f'  Tool calls: {msg.tool_calls}')
            if hasattr(msg, 'name'):
                print(f'  Name: {msg.name}')


if __name__ == '__main__':
    main()

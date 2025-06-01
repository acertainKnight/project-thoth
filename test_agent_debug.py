#!/usr/bin/env python3
"""Test script to debug the research agent's response issue."""

from loguru import logger

from src.thoth.ingestion.agent import ResearchAssistantAgent

# Set up logging to see debug messages
logger.add('agent_debug.log', level='DEBUG')
logger.add(lambda msg: print(msg), level='INFO')  # Also print to console


def test_agent():
    """Test the research agent with different configurations."""

    print('=' * 80)
    print('Testing Research Agent')
    print('=' * 80)

    # Test 1: Try with modern agent
    print('\n1. Testing with modern agent (default)...')
    try:
        agent = ResearchAssistantAgent(
            use_tool_agent=True, enable_persistent_memory=False
        )

        # Check which agent is actually being used
        print(f'use_tool_agent: {agent.use_tool_agent}')
        print(f'use_modern_agent: {agent.use_modern_agent}')
        print(f'modern_agent exists: {agent.modern_agent is not None}')
        print(f'agent_executor exists: {agent.agent_executor is not None}')

        # Test simple command
        response = agent.chat('list queries')
        print(f'Response: {response}')

        if response.get('agent_response'):
            print(f'Agent said: {response["agent_response"]}')
        else:
            print('No agent response received!')

    except Exception as e:
        print(f'Error with modern agent: {e}')
        import traceback

        traceback.print_exc()

    # Test 2: Try with legacy mode
    print('\n\n2. Testing with legacy mode...')
    try:
        agent = ResearchAssistantAgent(
            use_tool_agent=False,  # Disable tool agent to use legacy mode
            enable_persistent_memory=False,
        )

        response = agent.chat('list queries')
        print(f'Response: {response}')

        if response.get('agent_response'):
            print(f'Agent said: {response["agent_response"]}')
        else:
            print('No agent response received!')

    except Exception as e:
        print(f'Error with legacy mode: {e}')
        import traceback

        traceback.print_exc()

    # Test 3: Direct tool testing
    print('\n\n3. Testing tools directly...')
    try:
        agent = ResearchAssistantAgent(
            use_tool_agent=True, enable_persistent_memory=False
        )

        # Get the tools
        tools = agent._create_tools()
        list_queries_tool = next((t for t in tools if t.name == 'list_queries'), None)

        if list_queries_tool:
            result = list_queries_tool.func('')
            print(f'Direct tool result: {result}')
        else:
            print('list_queries tool not found!')

    except Exception as e:
        print(f'Error testing tools directly: {e}')
        import traceback

        traceback.print_exc()

    # Test 4: Test with explicit tool request
    print('\n\n4. Testing with explicit tool request...')
    try:
        agent = ResearchAssistantAgent(
            use_tool_agent=True, enable_persistent_memory=False
        )

        # Try different phrasings
        test_messages = [
            'use the list_queries tool',
            'call list_queries',
            'I want to see my queries using the list_queries tool',
        ]

        for msg in test_messages:
            print(f"\nTrying: '{msg}'")
            response = agent.chat(msg)
            if response.get('agent_response'):
                print(f'Response: {response["agent_response"][:200]}...')
            else:
                print('No response!')

    except Exception as e:
        print(f'Error with explicit tool test: {e}')
        import traceback

        traceback.print_exc()

    print('\n' + '=' * 80)
    print('Testing complete. Check agent_debug.log for detailed logs.')


if __name__ == '__main__':
    test_agent()

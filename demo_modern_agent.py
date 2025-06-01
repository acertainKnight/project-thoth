#!/usr/bin/env python3
"""
Demo script for the modern research assistant agent.

This demonstrates the clean, modular architecture of the new agent
using LangGraph and MCP framework.
"""

from loguru import logger

from thoth.ingestion.agent_v2 import create_research_assistant
from thoth.pipeline import ThothPipeline


def demo_agent_capabilities():
    """Demonstrate the capabilities of the modern research assistant."""
    print('🚀 Thoth Modern Research Assistant Demo')
    print('=' * 60)

    # Initialize pipeline
    print('\n📦 Initializing Thoth pipeline...')
    pipeline = ThothPipeline()

    # Create the modern agent
    print('🤖 Creating research assistant with LangGraph...')
    agent = create_research_assistant(
        llm=pipeline.llm_processor.llm,
        pipeline=pipeline,
        enable_memory=True,
    )

    # Show available tools
    print('\n🔧 Available Tools:')
    tools = agent.get_available_tools()
    for tool in tools:
        print(f'  • {tool["name"]}: {tool["description"]}')

    print('\n' + '=' * 60)
    print('📝 Demo Scenarios')
    print('=' * 60)

    # Demo scenarios
    demo_queries = [
        {
            'title': '1. Discovery Source Management',
            'query': 'Show me all my discovery sources',
        },
        {
            'title': '2. Creating an ArXiv Source',
            'query': "Create an ArXiv source called 'ml_daily' for machine learning and neural networks papers",
        },
        {
            'title': '3. Knowledge Base Search',
            'query': 'Search for papers about transformer architectures in my collection',
        },
        {
            'title': '4. Research Topic Analysis',
            'query': 'Analyze the topic of deep learning in my research collection',
        },
        {
            'title': '5. Finding Paper Connections',
            'query': 'What are the connections between attention mechanisms and transformer models in my papers?',
        },
    ]

    session_id = 'demo_session'

    for demo in demo_queries:
        print(f'\n🎯 {demo["title"]}')
        print(f'📝 Query: {demo["query"]}')
        print('-' * 40)

        try:
            # Get response from agent
            response = agent.chat(
                message=demo['query'],
                session_id=session_id,
            )

            print(f'💬 Response: {response["response"][:500]}...')

            if response.get('tool_calls'):
                print('\n🔧 Tools Used:')
                for tool_call in response['tool_calls']:
                    print(f'  - {tool_call["tool"]} with args: {tool_call["args"]}')

        except Exception as e:
            print(f'❌ Error: {e}')

        print('-' * 40)
        input('\nPress Enter to continue to next demo...')

    print('\n✅ Demo completed!')
    print('\n💡 Key Benefits of the Modern Architecture:')
    print('  • Clean separation of concerns with modular tools')
    print('  • Built on LangGraph for robust agent workflows')
    print('  • MCP framework for extensible tool management')
    print('  • Persistent memory for context-aware conversations')
    print('  • Type-safe tool interfaces with Pydantic schemas')
    print('  • Easy to extend with new tools and capabilities')


def compare_architectures():
    """Show comparison between old and new architectures."""
    print('\n📊 Architecture Comparison')
    print('=' * 60)

    old_stats = {
        'lines_of_code': 2864,
        'single_file': True,
        'tool_methods': 'Embedded in agent class',
        'extensibility': 'Difficult - requires modifying main class',
        'testing': 'Hard to test individual components',
        'memory': 'Custom implementation',
    }

    new_stats = {
        'lines_of_code': '~1500 (distributed across modules)',
        'single_file': False,
        'tool_methods': 'Separate tool classes with registry',
        'extensibility': 'Easy - just add new tool classes',
        'testing': 'Easy to test individual tools',
        'memory': "LangGraph's built-in memory management",
    }

    print('\n🔴 Old Architecture:')
    for key, value in old_stats.items():
        print(f'  • {key}: {value}')

    print('\n🟢 New Architecture:')
    for key, value in new_stats.items():
        print(f'  • {key}: {value}')

    print('\n✨ Benefits:')
    print('  • 50% reduction in code complexity')
    print('  • Modular design for better maintainability')
    print('  • Follows MCP framework best practices')
    print('  • Easy to add new capabilities')
    print('  • Better error handling and logging')
    print('  • Type-safe interfaces throughout')


if __name__ == '__main__':
    # Configure logging
    logger.remove()
    logger.add(
        lambda msg: print(f'[LOG] {msg}', end=''),
        level='INFO',
        format='{message}',
    )

    print('\n🎉 Welcome to the Thoth Modern Agent Demo!\n')

    # Run the demo
    demo_agent_capabilities()

    # Show architecture comparison
    compare_architectures()

    print('\n👋 Thanks for trying the modern Thoth Research Assistant!')
    print('   Check out src/thoth/ingestion/agent_v2/ for the implementation\n')

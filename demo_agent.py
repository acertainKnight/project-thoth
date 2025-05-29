#!/usr/bin/env python3
"""
Demo script showing the enhanced Thoth Research Agent capabilities.

This script demonstrates how to interact with the agent to manage discovery sources.
"""


def demo_agent_usage():
    """Demonstrate agent usage examples."""
    print('🤖 Enhanced Thoth Research Agent - Discovery Management')
    print('=' * 60)

    print('\n📋 **Available Commands:**')

    print('\n🆘 **Help & Information:**')
    print("  • 'help' or '?' - Show all agent capabilities and commands")
    print("  • 'what can you do?' - Learn about the agent's features")

    print('\n🔍 **Discovery Source Management:**')
    print("  • 'list discovery sources' - Show all configured sources")
    print(
        '  • \'create an arxiv source called "ml_papers" for machine learning\' - Create ArXiv source'
    )
    print(
        '  • \'create a pubmed source called "bio_research" searching for neuroscience\' - Create PubMed source'
    )
    print("  • 'run discovery for arxiv_test' - Run specific source")
    print("  • 'run discovery with max 5 articles' - Run all sources with limit")
    print("  • 'edit arxiv_test source' - Modify existing source")
    print("  • 'delete old_source' - Remove a source")

    print('\n📝 **Research Query Management:**')
    print("  • 'create query' - Create new research query")
    print("  • 'list queries' - Show existing queries")

    print('\n🚀 **Getting Started:**')
    print('1. Run: python -m thoth agent')
    print("2. Type: 'help' to see all capabilities")
    print("3. Try: 'list discovery sources'")
    print(
        '4. Create: \'create an arxiv source called "my_research" for deep learning\''
    )
    print("5. Run: 'run discovery for my_research'")

    print('\n💡 **Example Conversation:**')
    print('You: help')
    print('Agent: Shows comprehensive list of all capabilities')
    print()
    print('You: list discovery sources')
    print('Agent: [Uses list_discovery_sources tool] Shows all sources with status')
    print()
    print('You: create an arxiv source called "ai_papers" for artificial intelligence')
    print('Agent: [Uses create_arxiv_source tool] Creates new ArXiv source')
    print()
    print('You: run discovery for ai_papers')
    print('Agent: [Uses run_discovery tool] Executes discovery and shows results')

    print('\n🔧 **New MCP Framework Features:**')
    print('✅ The agent now uses intelligent tool selection:')
    print('  • Natural language requests → Automatic tool selection')
    print('  • Create operations → create_arxiv_source, create_pubmed_source tools')
    print('  • List operations → list_queries, list_discovery_sources tools')
    print('  • Management → update_discovery_source, delete_discovery_source tools')
    print('  • Conversational requests → Legacy graph-based handlers for better UX')

    print('\n🎯 **MCP Framework Benefits:**')
    print('  • Model chooses appropriate tools automatically')
    print('  • No rigid keyword matching required')
    print('  • Graceful fallback to conversational mode')
    print('  • All functionality exposed as proper LangChain Tools')
    print('  • JSON-structured tool inputs for precision')


def demo_mcp_framework():
    """Demonstrate the new MCP framework capabilities."""
    print('\n' + '=' * 70)
    print('🛠️  Model Context Protocol (MCP) Framework Demonstration')
    print('=' * 70)

    print('\n📊 **Available Tools in MCP Framework:**')

    print('\n🔍 **Query Management Tools:**')
    print('  1. list_queries - Lists all research queries')
    print('  2. get_query - Gets detailed info about a specific query')
    print('  3. create_query - Creates new research query with JSON config')
    print('  4. delete_query - Deletes a query by name')

    print('\n🌐 **Discovery Source Tools:**')
    print('  5. list_discovery_sources - Lists all discovery sources with status')
    print('  6. get_discovery_source - Gets detailed source configuration')
    print('  7. create_discovery_source - Creates source with full JSON config')
    print('  8. create_arxiv_source - Creates ArXiv source with simplified params')
    print('  9. create_pubmed_source - Creates PubMed source with simplified params')
    print(' 10. update_discovery_source - Updates existing source configuration')
    print(' 11. delete_discovery_source - Deletes a source by name')
    print(' 12. run_discovery - Runs discovery with optional source/article limits')

    print('\n🎯 **Analysis Tools:**')
    print(' 13. evaluate_article - Evaluates articles against research queries')

    print('\n ℹ️  **Help Tools:**')  # noqa: RUF001
    print(' 14. get_help - Comprehensive help with tool usage examples')

    print('\n🔄 **Intelligent Request Routing:**')
    print('\n📋 **Tool-Calling Mode (Structured Requests):**')
    print('  • "Create an ArXiv source for deep learning" → create_arxiv_source tool')
    print('  • "List all my discovery sources" → list_discovery_sources tool')
    print('  • "Run discovery for my source" → run_discovery tool')
    print('  • "Delete the old_source" → delete_discovery_source tool')

    print('\n💬 **Legacy Mode (Conversational Requests):**')
    print('  • "Hello, what can you do?" → Conversational response')
    print('  • "Help me understand the system" → Detailed guidance')
    print('  • "Explain how this works" → Educational response')
    print('  • "Thank you" → Polite acknowledgment')

    print('\n🎯 **JSON Tool Input Examples:**')

    print('\n📝 **Create ArXiv Source:**')
    print('  Tool: create_arxiv_source')
    print(
        '  Input: {"name": "ml_papers", "keywords": ["machine learning", "neural networks"], "categories": ["cs.LG", "cs.AI"]}'
    )

    print('\n🔍 **Run Discovery:**')
    print('  Tool: run_discovery')
    print('  Input: {"source_name": "ml_papers", "max_articles": 10}')

    print('\n📊 **Create Research Query:**')
    print('  Tool: create_query')
    print(
        '  Input: {"name": "transformer_research", "research_question": "How do transformers work?", "keywords": ["transformer", "attention"], ...}'
    )

    print('\n✨ **Benefits of the MCP Framework:**')
    print('  ✅ Model intelligently selects appropriate tools')
    print('  ✅ Natural language → Structured tool calls')
    print('  ✅ All legacy functionality exposed as tools')
    print('  ✅ Graceful fallback for conversational requests')
    print('  ✅ JSON-structured inputs for precision')
    print('  ✅ Easy to extend with new tools')


if __name__ == '__main__':
    demo_agent_usage()
    demo_mcp_framework()
